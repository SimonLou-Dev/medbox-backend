"""Repository Tenant."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from medbox.core.constants.enums import UserRoles
from medbox.core.db.models.box import Box
from medbox.core.db.models.patient import Patient
from medbox.core.db.models.tenant import Tenant
from medbox.core.db.models.user import User
from medbox.core.db.models.wheel import Wheel
from medbox.core.db.repositories.base import BaseRepository
from medbox.core.db.session import async_session_local
from medbox.core.dto.tenant import TenantResponse


class TenantRepository(BaseRepository[Tenant]):
    """Repository Tenant."""

    def __init__(self) -> None:
        """Constructeur."""
        super().__init__(Tenant)

    async def get_with_counts(self, m_id: UUID) -> TenantResponse:
        """Récupère un enregistrement via son identifiant avec les relations.

        Parameters
        ----------
        m_id : str
            Identifiant du tenant

        Returns
        -------
        TenantResponse
            L'objet si trouvé en DTO

        """
        async with async_session_local() as session:
            stmt = (
                select(
                    Tenant,
                    func.count(Patient.id).label("patient_count"),
                    func.count(Box.id).label("box_count"),
                    func.count(Wheel.id).label("wheel_count"),
                    func.count(
                        func.nullif(
                            User.role != UserRoles.CAREGIVER,
                            True,
                        ),
                    ).label("caregiver_count"),
                )
                .join(Patient, Patient.tenant_id == Tenant.id, isouter=True)
                .join(Box, Box.tenant_id == Tenant.id, isouter=True)
                .join(Wheel, Wheel.tenant_id == Tenant.id, isouter=True)
                .join(User, User.tenant_id == Tenant.id, isouter=True)
                .where(Tenant.id == m_id)
                .group_by(Tenant.id)
                .options(selectinload(Tenant.patients))
            )

            result = await session.execute(stmt)
            row = result.one_or_none()

            if not row:
                return None

            tenant, patient_count, box_count, wheel_count, caregiver_count = row

            return TenantResponse(
                id=tenant.id,
                name=tenant.name,
                patient_count=patient_count,
                caregiver_count=caregiver_count,
                box_count=box_count,
                wheel_count=wheel_count,
                created_at=tenant.created_at,
            )
