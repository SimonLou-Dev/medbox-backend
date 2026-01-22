"""Global Medication model - French BDPM reference data.

This model represents medications from the French public database (BDPM).
Data is synced from the external API (https://medicaments-api.giygas.dev)
and is NOT tenant-scoped (shared across all tenants).
"""

from __future__ import annotations

from datetime import date, datetime
from functools import partial

from sqlalchemy import JSON, Date, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from medbox.core.db.base import Base


class GlobalMedication(Base):
    """Global medication reference from French BDPM.

    Used for:
    - Prescription line lookups to identify medications by name/CIS code
    - Medication search for prescribers
    - Ensuring prescribed medications are valid in the BDPM

    Synced automatically from external French Medications API (2x daily).
    """

    __tablename__ = "global_medications"

    # Primary key: CIS Code (Code Identifiant de Spécialité)
    cis: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Core medication information from French API
    element_pharmaceutique: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Pharmaceutical element / product name",
    )

    forme_pharmaceutique: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Pharmaceutical form (tablet, capsule, etc.)",
    )

    voies_administration: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Array of administration routes",
    )

    status_autorisation: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment='Authorization status (e.g., "Autorisation active")',
    )

    type_procedure: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment='Procedure type (e.g., "Procédure nationale")',
    )

    etat_commercialisation: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment='Commercialization state (e.g., "Commercialisée")',
    )

    date_amm: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Marketing Authorization Date",
    )

    titulaire: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="License holder / manufacturer name",
    )

    # Sync metadata
    sync_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=partial(datetime.now),
        comment="Last successful sync from external API",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=partial(datetime.now),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=partial(datetime.now),
    )

    # Indices for common search operations
    __table_args__ = (
        Index(
            "idx_global_medications_element_pharmaceutique",
            "element_pharmaceutique",
        ),
        Index("idx_global_medications_titulaire", "titulaire"),
    )
