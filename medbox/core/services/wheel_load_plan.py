"""Service de gestion des plans de chargement de roue.

Contient la "moulinette" : croisement des ordonnances pour calculer
la répartition des médicaments dans les 21 cases utiles de la roue.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from medbox.core.db.models.prescription_schedule_item import PrescriptionScheduleItem
from medbox.core.db.models.wheel_load_plan import WheelLoadPlan
from medbox.core.db.models.wheel_load_plan_prescription import WheelLoadPlanPrescription
from medbox.core.db.models.wheel_slot_prescription_item import WheelSlotPrescriptionItem
from medbox.core.db.repositories.prescription_schedule_item import (
    PrescriptionScheduleItemRepository,
)
from medbox.core.db.repositories.wheel_load_plan import WheelLoadPlanRepository
from medbox.core.db.session import async_session_local
from medbox.core.dto.wheel_load_plan import (
    FillingSlot,
    SlotMedicationItem,
    WheelLoadPlanConfirmRequest,
    WheelLoadPlanCreateRequest,
    WheelLoadPlanDetailResponse,
    WheelLoadPlanResponse,
)

# Cases utiles : indices 0 à 20 (case 22 = index 21 = vide, ignorée)
USABLE_SLOT_COUNT = 21

# Mapping moment → heure de distribution par défaut
MOMENT_DEFAULT_TIMES: dict[str, time] = {
    "matin": time(8, 0),
    "midi": time(12, 0),
    "après-midi": time(15, 0),
    "soir": time(19, 0),
    "nuit": time(22, 0),
}

# Horaires par défaut selon times_per_day si pas de moments définis
DEFAULT_TIMES_BY_FREQUENCY: dict[int, list[time]] = {
    1: [time(8, 0)],
    2: [time(8, 0), time(20, 0)],
    3: [time(8, 0), time(13, 0), time(19, 0)],
    4: [time(8, 0), time(12, 0), time(17, 0), time(21, 0)],
}


def _resolve_distribution_times(frequency: dict) -> list[time]:
    """Déduit les horaires de distribution depuis la fréquence d'un item."""
    moments = frequency.get("moments") or []
    times_per_day = frequency.get("times_per_day", 1) or 1

    if moments:
        resolved = [
            MOMENT_DEFAULT_TIMES[m] for m in moments if m in MOMENT_DEFAULT_TIMES
        ]
        if resolved:
            return sorted(set(resolved))

    return DEFAULT_TIMES_BY_FREQUENCY.get(times_per_day, [time(8, 0)])


class WheelLoadPlanService:
    """Service de création et gestion des plans de chargement."""

    def __init__(self, tenant_id: UUID) -> None:
        self.tenant_id = tenant_id
        self.repo = WheelLoadPlanRepository(tenant_id=tenant_id)
        self.psi_repo = PrescriptionScheduleItemRepository(tenant_id=tenant_id)

    async def create(
        self,
        data: WheelLoadPlanCreateRequest,
        created_by_user_id: UUID,
    ) -> WheelLoadPlanDetailResponse:
        """Crée un plan de chargement et calcule la répartition (moulinette).

        Étapes :
        1. Valide roue, box et prescriptions
        2. Collecte tous les PrescriptionItems avec leurs fréquences
        3. Calcule les créneaux journaliers uniques (moments croisés)
        4. Répartit dans les 21 cases utiles
        5. Assigne les médicaments aux WheelSlots
        6. Retourne la liste de remplissage pour le soignant
        """
        async with async_session_local() as session:
            from medbox.core.db.models.prescription import Prescription
            from medbox.core.db.models.wheel import Wheel
            from medbox.core.db.models.wheel_slot import WheelSlot

            # Valider la roue
            wheel_result = await session.execute(
                select(Wheel)
                .where(Wheel.id == data.wheel_id)
                .where(Wheel.tenant_id == self.tenant_id)
                .options(selectinload(Wheel.slots))
            )
            wheel = wheel_result.scalar_one_or_none()
            if not wheel:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Roue introuvable",
                )
            if wheel.status not in ("prepared", "in_stock"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Roue non disponible (statut: {wheel.status})",
                )

            # Valider les prescriptions
            presc_result = await session.execute(
                select(Prescription)
                .where(Prescription.id.in_(data.prescription_ids))
                .where(Prescription.tenant_id == self.tenant_id)
                .where(Prescription.status == "active")
                .options(selectinload(Prescription.items))
            )
            prescriptions = presc_result.scalars().all()

            if len(prescriptions) != len(data.prescription_ids):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Une ou plusieurs prescriptions introuvables ou inactives",
                )

            # --- Moulinette : calcul des créneaux journaliers ---
            # Chaque créneau unique = un set de médicaments à distribuer ensemble
            # clé = time, valeur = liste (prescription_item, quantity)
            daily_slots: dict[time, list[tuple]] = {}

            for prescription in prescriptions:
                for item in prescription.items:
                    dist_times = _resolve_distribution_times(item.frequency or {})
                    for t in dist_times:
                        if t not in daily_slots:
                            daily_slots[t] = []
                        daily_slots[t].append((item, 1))

            sorted_times = sorted(daily_slots.keys())
            slots_per_day = len(sorted_times)

            if slots_per_day == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Aucun créneau de distribution calculable depuis les prescriptions",
                )

            days_covered = USABLE_SLOT_COUNT // slots_per_day
            total_slots = days_covered * slots_per_day

            # Récupérer les WheelSlots existants (indices 0 à USABLE_SLOT_COUNT-1)
            usable_wheel_slots = sorted(
                [s for s in wheel.slots if s.index < USABLE_SLOT_COUNT],
                key=lambda s: s.index,
            )

            # Créer les WheelSlots manquants si nécessaire
            for idx in range(total_slots):
                if not any(s.index == idx for s in usable_wheel_slots):
                    new_slot = WheelSlot(wheel_id=wheel.id, index=idx)
                    session.add(new_slot)
                    usable_wheel_slots.append(new_slot)

            await session.flush()

            # Vider les assignations existantes sur ces slots
            slot_ids = [s.id for s in usable_wheel_slots[:total_slots]]
            existing_links_result = await session.execute(
                select(WheelSlotPrescriptionItem).where(
                    WheelSlotPrescriptionItem.wheel_slot_id.in_(slot_ids)
                )
            )
            for link in existing_links_result.scalars().all():
                await session.delete(link)

            # Assigner médicaments aux slots
            filling_list: list[FillingSlot] = []
            slot_cursor = 0

            valid_until = data.valid_from

            for day in range(days_covered):
                for t in sorted_times:
                    if slot_cursor >= total_slots:
                        break

                    wheel_slot = usable_wheel_slots[slot_cursor]
                    medications_in_slot = daily_slots[t]

                    # Créer les liens WheelSlot ↔ PrescriptionItem
                    slot_medications: list[SlotMedicationItem] = []
                    for pitem, qty in medications_in_slot:
                        link = WheelSlotPrescriptionItem(
                            wheel_slot_id=wheel_slot.id,
                            prescription_item_id=pitem.id,
                            quantity=qty,
                        )
                        session.add(link)
                        slot_medications.append(
                            SlotMedicationItem(
                                prescription_item_id=pitem.id,
                                medication_label=pitem.medication_label,
                                dose=pitem.dose,
                                quantity=qty,
                            )
                        )

                    scheduled_at = datetime.combine(
                        data.valid_from.date() + timedelta(days=day),
                        t,
                    ).replace(tzinfo=UTC)

                    valid_until = max(valid_until, scheduled_at)

                    filling_list.append(
                        FillingSlot(
                            slot_index=wheel_slot.index,
                            case_number=wheel_slot.index + 1,
                            scheduled_at=scheduled_at,
                            distribution_time=t,
                            day_offset=day,
                            medications=slot_medications,
                        )
                    )

                    slot_cursor += 1

            # Créer le plan en DB
            plan = WheelLoadPlan(
                tenant_id=self.tenant_id,
                created_by_user_id=created_by_user_id,
                wheel_id=data.wheel_id,
                box_id=data.box_id,
                status="draft",
                valid_from=data.valid_from,
                valid_until=valid_until,
            )
            session.add(plan)
            await session.flush()

            # Lier les prescriptions au plan
            for presc_id in data.prescription_ids:
                session.add(
                    WheelLoadPlanPrescription(
                        plan_id=plan.id,
                        prescription_id=presc_id,
                    )
                )

            # Mettre à jour le statut de la roue
            wheel.status = "prepared"

            await session.commit()
            await session.refresh(plan)

        return WheelLoadPlanDetailResponse(
            id=plan.id,
            tenant_id=plan.tenant_id,
            wheel_id=plan.wheel_id,
            box_id=plan.box_id,
            status=plan.status,
            valid_from=plan.valid_from,
            valid_until=plan.valid_until,
            confirmed_at=plan.confirmed_at,
            total_slots_used=total_slots,
            days_covered=days_covered,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
            filling_list=filling_list,
        )

    async def get_filling_list(self, plan_id: UUID) -> WheelLoadPlanDetailResponse:
        """Récupère la liste de remplissage d'un plan existant."""
        plan = await self.repo.get(plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan introuvable",
            )

        async with async_session_local() as session:
            from medbox.core.db.models.wheel_slot import WheelSlot

            psi_result = await session.execute(
                select(PrescriptionScheduleItem)
                .where(PrescriptionScheduleItem.wheel_load_plan_id == plan_id)
                .options(
                    selectinload(PrescriptionScheduleItem.wheel_slot).selectinload(
                        WheelSlot.prescription_links
                    )
                )
                .order_by(PrescriptionScheduleItem.scheduled_at)
            )
            items = psi_result.scalars().all()

        filling_list = []
        for item in items:
            if not item.wheel_slot:
                continue
            slot = item.wheel_slot
            medications = [
                SlotMedicationItem(
                    prescription_item_id=link.prescription_item_id,
                    medication_label=link.prescription_item.medication_label
                    if link.prescription_item
                    else "",
                    dose=link.prescription_item.dose
                    if link.prescription_item
                    else None,
                    quantity=link.quantity,
                )
                for link in slot.prescription_links
            ]
            filling_list.append(
                FillingSlot(
                    slot_index=slot.index,
                    case_number=slot.index + 1,
                    scheduled_at=item.scheduled_at,
                    distribution_time=item.scheduled_at.time(),
                    day_offset=0,
                    medications=medications,
                )
            )

        days_covered = (
            (plan.valid_until - plan.valid_from).days + 1
            if plan.valid_from and plan.valid_until
            else 0
        )

        return WheelLoadPlanDetailResponse(
            id=plan.id,
            tenant_id=plan.tenant_id,
            wheel_id=plan.wheel_id,
            box_id=plan.box_id,
            status=plan.status,
            valid_from=plan.valid_from,
            valid_until=plan.valid_until,
            confirmed_at=plan.confirmed_at,
            total_slots_used=len(filling_list),
            days_covered=days_covered,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
            filling_list=filling_list,
        )

    async def confirm(
        self,
        plan_id: UUID,
        data: WheelLoadPlanConfirmRequest,
        user_id: UUID,
    ) -> WheelLoadPlanResponse:
        """Confirme le remplissage physique et crée les PrescriptionScheduleItems.

        Appelé quand le soignant a physiquement chargé la roue.
        Crée toutes les distributions planifiées en DB.
        """
        plan = await self.repo.get(plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan introuvable",
            )
        if plan.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Plan non confirmable (statut: {plan.status})",
            )

        box_id = data.box_id or plan.box_id
        if not box_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="box_id requis pour confirmer le plan",
            )

        async with async_session_local() as session:
            from medbox.core.db.models.wheel_slot import WheelSlot

            # Récupérer les slots du plan pour construire les schedule items
            slots_result = await session.execute(
                select(WheelSlot)
                .where(WheelSlot.wheel_id == plan.wheel_id)
                .where(WheelSlot.index < USABLE_SLOT_COUNT)
                .options(selectinload(WheelSlot.prescription_links))
                .order_by(WheelSlot.index)
            )
            slots = slots_result.scalars().all()

            if not slots:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Aucune case assignée sur cette roue",
                )

            # Recalculer les scheduled_at depuis valid_from + index de slot
            valid_from = plan.valid_from or datetime.now(tz=UTC)
            slots_per_day_result = await session.execute(
                select(WheelSlot.index)
                .where(WheelSlot.wheel_id == plan.wheel_id)
                .where(WheelSlot.index < USABLE_SLOT_COUNT)
            )
            slot_indices = [r[0] for r in slots_per_day_result.all()]
            # Déterminer le nombre de slots par jour à partir des slots existants
            # On recalcule à partir du plan original (valid_from → valid_until)
            if plan.valid_until and plan.valid_from:
                days = max((plan.valid_until - plan.valid_from).days, 1)
                slots_per_day = max(len(slot_indices) // days, 1)
            else:
                slots_per_day = len(slots)

            schedule_items = []
            for slot in slots:
                day_offset = slot.index // slots_per_day
                slot_in_day = slot.index % slots_per_day

                # Récupérer les prescription_items du slot pour déduire l'heure
                pitem_ids = [
                    lnk.prescription_item_id for lnk in slot.prescription_links
                ]
                if not pitem_ids:
                    continue

                from medbox.core.db.models.prescription_item import PrescriptionItem

                pitem_result = await session.execute(
                    select(PrescriptionItem).where(PrescriptionItem.id == pitem_ids[0])
                )
                first_pitem = pitem_result.scalar_one_or_none()
                if not first_pitem:
                    continue

                dist_times = _resolve_distribution_times(first_pitem.frequency or {})
                slot_time = dist_times[slot_in_day % len(dist_times)]

                scheduled_at = datetime.combine(
                    valid_from.date() + timedelta(days=day_offset),
                    slot_time,
                ).replace(tzinfo=UTC)

                schedule_items.append(
                    PrescriptionScheduleItem(
                        tenant_id=self.tenant_id,
                        wheel_load_plan_id=plan.id,
                        wheel_slot_id=slot.id,
                        box_id=box_id,
                        scheduled_at=scheduled_at,
                        status="pending",
                    )
                )

            session.add_all(schedule_items)

            # Mettre à jour le plan
            plan_obj = await session.get(WheelLoadPlan, plan.id)
            plan_obj.status = "active"
            plan_obj.confirmed_at = datetime.now(tz=UTC)
            plan_obj.box_id = box_id

            # Monter la roue sur la box
            from medbox.core.db.models.wheel import Wheel

            wheel_obj = await session.get(Wheel, plan.wheel_id)
            if wheel_obj:
                wheel_obj.status = "mounted"
                wheel_obj.box_id = box_id

            await session.commit()
            await session.refresh(plan_obj)

        return WheelLoadPlanResponse(
            id=plan_obj.id,
            tenant_id=plan_obj.tenant_id,
            wheel_id=plan_obj.wheel_id,
            box_id=plan_obj.box_id,
            status=plan_obj.status,
            valid_from=plan_obj.valid_from,
            valid_until=plan_obj.valid_until,
            confirmed_at=plan_obj.confirmed_at,
            total_slots_used=len(schedule_items),
            days_covered=(plan_obj.valid_until - plan_obj.valid_from).days + 1
            if plan_obj.valid_from and plan_obj.valid_until
            else 0,
            created_at=plan_obj.created_at,
            updated_at=plan_obj.updated_at,
        )

    async def list(self) -> list[WheelLoadPlanResponse]:
        """Liste tous les plans du tenant."""
        plans = await self.repo.list_by_tenant()
        results = []
        for p in plans:
            results.append(
                WheelLoadPlanResponse(
                    id=p.id,
                    tenant_id=p.tenant_id,
                    wheel_id=p.wheel_id,
                    box_id=p.box_id,
                    status=p.status,
                    valid_from=p.valid_from,
                    valid_until=p.valid_until,
                    confirmed_at=p.confirmed_at,
                    total_slots_used=0,
                    days_covered=0,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
            )
        return results
