"""Repository pour les utilisateurs."""

from collections.abc import Sequence
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import case, func, select

from medbox.core.constants.enums import UserRoles
from medbox.core.db.models.user import User
from medbox.core.db.repositories.base import BaseRepository
from medbox.core.db.session import async_session_local


class UserRepository(BaseRepository[User]):
    """Repository utilisateur."""

    def __init__(self, tenant_id: str | None = None) -> None:
        """Constructeur.

        Parameters
        ----------
        tenant_id : str | None
            ID du tenant pour scoper les données (optionnel).

        """
        super().__init__(User)
        self.tenant_id = tenant_id

    async def list(self) -> Sequence[User]:
        """Renvoie l'ensemble des utilisateurs, scoped by tenant si fourni.

        Returns
        -------
        Sequence[User]
            Liste des utilisateurs.

        """
        async with async_session_local() as session:
            stmt = select(self.model)

            # Scope by tenant if provided
            if self.tenant_id:
                stmt = stmt.where(self.model.tenant_id == self.tenant_id)

            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_by_subject(self, subject_id: str) -> User | None:
        """Récupère un enregistrement via son identifiant.

        Parameters
        ----------
        subject_id : str
            Identifiant du sujet keycloak.

        Returns
        -------
        Optional[ModelType]
            L'objet si trouvé, sinon None.

        """
        async with async_session_local() as session:
            stmt = select(self.model).where(self.model.keycloak_subject == subject_id)

            # Scope by tenant if provided
            if self.tenant_id:
                stmt = stmt.where(self.model.tenant_id == self.tenant_id)

            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_subject_or_fail(self, subject_id: str) -> User | None:
        """Récupère un enregistrement via son identifiant.

        Parameters
        ----------
        subject_id : str
            Identifiant du sujet keycloak.

        Returns
        -------
        ModelType
            L'objet

        Raise
        ------
        HTTPException
            Utilisateur non trouvé


        """
        async with async_session_local() as session:
            stmt = select(self.model).where(self.model.keycloak_subject == subject_id)
            result = await session.execute(stmt)
            usr = result.scalar_one_or_none()

            if not usr:
                raise HTTPException(
                    status_code=404,
                    detail="Impossible de trouver l'utilisateur",
                )
            return usr

    async def list_by_tenant(self, tenant_id: UUID) -> Sequence[User]:
        """Renvoie tous les utilisateurs d'un tenant.

        Parameters
        ----------
        tenant_id : UUID
            Identifiant du tenant

        Returns
        -------
        Sequence[User]
            Liste des utilisateurs du tenant.

        """
        async with async_session_local() as session:
            stmt = (
                select(self.model)
                .where(self.model.tenant_id == tenant_id)
                .order_by(self.model.created_at.desc())
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def count_by_tenant_and_role(self, tenant_id: UUID) -> dict[str, int]:
        """Renvoie les counts d'utilisateurs par role pour un tenant.

        Parameters
        ----------
        tenant_id : UUID
            Identifiant du tenant

        Returns
        -------
        dict[str, int]
            Counts par role + total.

        """
        async with async_session_local() as session:
            stmt = select(
                func.count().label("total"),
                func.count(case((self.model.role == UserRoles.TENANT_ADMIN, 1))).label(
                    "admin_count",
                ),
                func.count(case((self.model.role == UserRoles.CAREGIVER, 1))).label(
                    "caregiver_count",
                ),
                func.count(case((self.model.role == UserRoles.PATIENT, 1))).label(
                    "patient_role_count",
                ),
                func.count(case((self.model.role == UserRoles.DEFAULT, 1))).label(
                    "default_count",
                ),
            ).where(self.model.tenant_id == tenant_id)
            result = await session.execute(stmt)
            row = result.one()
            return {
                "total": row.total,
                "admin_count": row.admin_count,
                "caregiver_count": row.caregiver_count,
                "patient_role_count": row.patient_role_count,
                "default_count": row.default_count,
            }
