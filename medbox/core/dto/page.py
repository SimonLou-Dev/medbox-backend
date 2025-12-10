"""DTO de pagination."""

from collections.abc import Sequence
from typing import Generic, TypeVar

from pydantic import BaseModel

from medbox.core.db.repositories.base import Page

T = TypeVar("T")


class PaginatedDTO(BaseModel, Generic[T]):
    """DTO de pagination."""

    items: Sequence[T]
    page: int
    per_page: int
    total: int
    total_pages: int

    @staticmethod
    def to_dto_page(
        page_obj: Page,
        dto_cls: type[T],
    ) -> "PaginatedDTO"[T]:
        # Convertit chaque élément via from_model() du DTO
        items = [dto_cls.from_model(item) for item in page_obj.items]

        return PaginatedDTO[T](
            items=items,
            page=page_obj.page,
            per_page=page_obj.per_page,
            total=page_obj.total,
            total_pages=page_obj.total_pages,
        )
