"""DTO pour la pagination standardisée."""

from collections.abc import Sequence
from typing import ClassVar, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Métadonnées de pagination."""

    page: int = Field(description="Page courante (1-indexed)")
    per_page: int = Field(description="Nombre d'éléments par page")
    total: int = Field(description="Nombre total d'éléments")
    total_pages: int = Field(description="Nombre total de pages")
    has_next: bool = Field(description="Vrai s'il y a une page suivante")
    has_previous: bool = Field(description="Vrai s'il y a une page précédente")


class PagedResponse(BaseModel, Generic[T]):
    """Réponse paginée générique.

    Usage:
        @router.get("/users")
        async def list_users(
            page: int = Query(1, ge=1),
            per_page: int = Query(20, ge=1, le=100),
            repo: UserRepository = Depends(),
        ) -> PagedResponse[UserDTO]:
            '''Lister les users avec pagination.'''
            paged = await repo.paginate(page=page, per_page=per_page)
            return PagedResponse(
                data=[UserDTO.from_model(u) for u in paged.items],
                pagination=PaginationMeta(
                    page=paged.page,
                    per_page=paged.per_page,
                    total=paged.total,
                    total_pages=paged.total_pages,
                    has_next=paged.page < paged.total_pages,
                    has_previous=paged.page > 1,
                ),
            )

    """

    status: str = Field(default="ok")
    data: Sequence[T] = Field(description="Liste des éléments")
    pagination: PaginationMeta = Field(description="Métadonnées de pagination")

    model_config: ClassVar = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "ok",
                    "data": [
                        {"id": "1", "email": "user1@test.com"},
                        {"id": "2", "email": "user2@test.com"},
                    ],
                    "pagination": {
                        "page": 1,
                        "per_page": 20,
                        "total": 42,
                        "total_pages": 3,
                        "has_next": True,
                        "has_previous": False,
                    },
                },
            ],
        },
    }
