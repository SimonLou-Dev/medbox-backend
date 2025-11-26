"""Repository générique."""

from collections.abc import Mapping, Sequence
from typing import Any, TypeVar
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeMeta

from medbox.core.db.session import async_session_local

ModelType = TypeVar("ModelType", bound=DeclarativeMeta)


class BaseRepository:
    """Repository générique fournissant les opérations CRUD usuelles."""

    def __init__(self, model: type[ModelType]) -> None:
        """Constructeur.

        Parameters
        ----------
        model : Type[ModelType]
            Modèle SQLAlchemy cible (ex: User).

        """
        self.model = model

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    async def get(self, m_id: UUID) -> ModelType | None:
        """Récupère un enregistrement via son identifiant.

        Parameters
        ----------
        m_id : Any
            Identifiant primaire (UUID ou int selon ton modèle).

        Returns
        -------
        Optional[ModelType]
            L'objet si trouvé, sinon None.

        """
        async with async_session_local() as session:
            stmt = select(self.model).where(self.model.id == m_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list(self) -> Sequence[ModelType]:
        """Renvoie l'ensemble des objets du modèle.

        Returns
        -------
        Sequence[ModelType]
            Liste des objets.

        """
        async with async_session_local() as session:
            stmt = select(self.model)
            res = await session.execute(stmt)
            return res.scalars().all()

    async def add(self, instance: ModelType) -> ModelType:
        """Ajoute un nouvel objet en base.

        Parameters
        ----------
        instance : ModelType
            Instance SQLAlchemy à persister.

        Returns
        -------
        ModelType
            L'objet créé.

        Raises
        ------
        HTTPException :
            En cas de violation d'unicité ou autre erreur d'intégrité.

        """
        async with async_session_local() as session:
            session.add(instance)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise HTTPException(400, "Object already exists") from exc
            await session.refresh(instance)
            return instance

    async def delete(self, m_id: UUID) -> bool:
        """Supprime un objet via son identifiant.

        Parameters
        ----------
        m_id : Any
            Identifiant primaire.

        Returns
        -------
        bool
            True si supprimé, False si l'objet n'existait pas.

        """
        async with async_session_local() as session:
            obj = await self.get(m_id)
            if not obj:
                return False

            await session.delete(obj)
            await session.commit()
            return True

    async def exists(self, **filters: object) -> bool:
        """Vérifie l'existence d'un objet selon des filtres.

        Parameters
        ----------
        **filters :
            Colonnes SQLAlchemy en equality match.

        Returns
        -------
        bool
            True si un objet correspondant existe.

        """
        async with async_session_local() as session:
            stmt = select(self.model).filter_by(**filters).limit(1)
            res = await session.execute(stmt)
            return res.scalar_one_or_none() is not None

    # -------------------------------------------------------------------------
    # Méthodes avancées
    # -------------------------------------------------------------------------

    async def first_or_create(
        self,
        *,
        defaults: Mapping[str, Any] | None = None,
        **filters: object,
    ) -> ModelType:
        """Récupère un objet correspondant aux filtres. Le crée s'il n'existe pas.

        Parameters
        ----------
        defaults : Optional[Mapping[str, Any]]
            Valeurs supplémentaires utilisées lors de la création.
        **filters :
            Conditions de recherche (WHERE).

        Returns
        -------
        ModelType
            L'objet existant ou nouvellement créé.

        Raises
        ------
        HTTPException :
            Si une violation d'unicité survient.

        """
        async with async_session_local() as session:
            stmt = select(self.model).filter_by(**filters).limit(1)
            result = await session.execute(stmt)
            instance = result.scalar_one_or_none()

            if instance:
                return instance

            data = {**filters, **(defaults or {})}
            instance = self.model(**data)

            session.add(instance)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                stmt = select(self.model).filter_by(**filters).limit(1)
                return (await session.execute(stmt)).scalar_one()

            await session.refresh(instance)
            return instance

    async def update_or_create(
        self,
        *,
        defaults: Mapping[str, Any],
        **filters: object,
    ) -> ModelType:
        """Met à jour un objet existant ou le crée s'il n'existe pas.

        Parameters
        ----------
        defaults : Mapping[str, Any]
            Champs à mettre à jour ou à utiliser lors de la création.
        **filters :
            Critères identifiant l'objet.

        Returns
        -------
        ModelType
            L'objet mis à jour ou créé.

        """
        async with async_session_local() as session:
            stmt = select(self.model).filter_by(**filters).limit(1)
            result = await session.execute(stmt)
            instance = result.scalar_one_or_none()

            if instance:
                for key, value in defaults.items():
                    setattr(instance, key, value)
                await session.commit()
                await session.refresh(instance)
                return instance

            data = {**filters, **defaults}
            instance = self.model(**data)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    # -------------------------------------------------------------------------
    # Pagination + Recherche
    # -------------------------------------------------------------------------

    async def paginate(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
    ) -> Sequence[ModelType]:
        """Renvoie une page d'objets.

        Parameters
        ----------
        page : int
            Numéro de page (>= 1).
        per_page : int
            Nombre d'éléments par page.

        Returns
        -------
        Sequence[ModelType]
            Les objets de la page demandée.

        """
        offset = (page - 1) * per_page

        async with async_session_local() as session:
            stmt = select(self.model).offset(offset).limit(per_page)
            res = await session.execute(stmt)
            return res.scalars().all()

    async def search(
        self,
        *,
        field: str,
        query: str,
        page: int = 1,
        per_page: int = 20,
    ) -> Sequence[ModelType]:
        """Recherche textuelle simple sur un champ du modèle.

        Parameters
        ----------
        field : str
            Nom du champ sur lequel faire la recherche.
        query : str
            Texte recherché (LIKE).
        page : int
            Page de résultats.
        per_page : int
            Nombre par page.

        Returns
        -------
        Sequence[ModelType]
            Liste paginée des résultats.

        Raises
        ------
        AttributeError :
            Si le champ n'existe pas sur le modèle.

        """
        column = getattr(self.model, field, None)
        if column is None:
            msg = f"{self.model.__name__} has no field '{field}'"
            raise AttributeError(msg)

        offset = (page - 1) * per_page

        async with async_session_local() as session:
            stmt = (
                select(self.model)
                .where(column.ilike(f"%{query}%"))
                .offset(offset)
                .limit(per_page)
            )
            res = await session.execute(stmt)
            return res.scalars().all()
