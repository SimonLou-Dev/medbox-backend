"""Repository Invitation."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import selectinload

from medbox.core.constants.enums import InviteStatus
from medbox.core.db.models.invitation import Invitation
from medbox.core.db.repositories.base import BaseRepository
from medbox.core.db.session import async_session_local


class InvitationRepository(BaseRepository[Invitation]):
    """Repository Invitation."""

    def __init__(self) -> None:
        """Constructeur."""
        super().__init__(Invitation)

    async def get_active_by_tenant(self, tenant_id: UUID) -> Invitation | None:
        """Recherche le code d'invitation actif (PENDING, non expiré) pour un tenant.

        Parameters
        ----------
        tenant_id : UUID
            Identifiant du tenant

        Returns
        -------
        Invitation | None
            L'invitation active ou None

        """
        async with async_session_local() as session:
            stmt = (
                select(self.model)
                .where(self.model.tenant_id == tenant_id)
                .where(self.model.expires_at > datetime.now(tz=UTC))
                .where(self.model.status == InviteStatus.PENDING)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Invitation | None:
        """Recherche une invitation via son code.

        Parameters
        ----------
        code : str
            Code à saisir par l'utilisateur

        Returns
        -------
        Invitation | None
            Invitation trouvée ou None

        """
        async with async_session_local() as session:
            stmt = select(self.model).where(self.model.code == code)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Invitation], int]:
        """Renvoie l'historique pagine des invitations d'un tenant.

        Parameters
        ----------
        tenant_id : UUID
            Identifiant du tenant
        limit : int
            Nombre max de resultats
        offset : int
            Decalage

        Returns
        -------
        tuple[Sequence[Invitation], int]
            (invitations, total)

        """
        async with async_session_local() as session:
            count_stmt = (
                select(func.count())
                .select_from(self.model)
                .where(self.model.tenant_id == tenant_id)
            )
            total = (await session.execute(count_stmt)).scalar_one()

            stmt = (
                select(self.model)
                .where(self.model.tenant_id == tenant_id)
                .order_by(self.model.created_at.desc())
                .offset(offset)
                .limit(limit)
                .options(
                    selectinload(self.model.sended_by_user),
                    selectinload(self.model.claimed_by_user),
                )
            )
            result = await session.execute(stmt)
            return result.scalars().all(), total

    async def count_by_tenant(self, tenant_id: UUID) -> dict[str, int]:
        """Renvoie le total et le nombre d'invitations pending pour un tenant.

        Parameters
        ----------
        tenant_id : UUID
            Identifiant du tenant

        Returns
        -------
        dict[str, int]
            {"total": ..., "pending": ...}

        """
        async with async_session_local() as session:
            stmt = (
                select(
                    func.count().label("total"),
                    func.count(case((self.model.status == InviteStatus.PENDING, 1))).label("pending"),
                )
                .where(self.model.tenant_id == tenant_id)
            )
            result = await session.execute(stmt)
            row = result.one()
            return {"total": row.total, "pending": row.pending}
