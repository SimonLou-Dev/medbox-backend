"""Data Transfer Objects for Global Medication."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class GlobalMedicationResponse(BaseModel):
    """Response DTO for a global medication.

    Used for API responses when returning medication information.
    Maps database fields to API response format.
    """

    model_config = ConfigDict(from_attributes=True)

    cis: int = Field(
        description="CIS Code (Code Identifiant de Spécialité) - Primary identifier from French BDPM API",
    )

    element_pharmaceutique: str = Field(
        description="Pharmaceutical element / product name (e.g., 'PARACETAMOL MYLAN 1 g, comprimé')",
    )

    forme_pharmaceutique: str = Field(
        description="Pharmaceutical form (tablet, capsule, syrup, etc.)",
    )

    voies_administration: list[str] | None = Field(
        default=None,
        description="Array of administration routes (e.g., ['orale', 'intramusculaire'])",
    )

    status_autorisation: str = Field(
        description='Authorization status (e.g., "Autorisation active", "Suspension")',
    )

    type_procedure: str = Field(
        description='Procedure type (e.g., "Procédure nationale", "Procédure centralisée")',
    )

    etat_commercialisation: str = Field(
        description='Commercialization state (e.g., "Commercialisée", "Non commercialisée")',
    )

    date_amm: date | None = Field(
        default=None,
        description="Marketing Authorization Date (Date d'Autorisation de Mise sur le Marché)",
    )

    titulaire: str = Field(
        description="License holder / manufacturer name (e.g., 'MYLAN SAS')",
    )

    sync_date: datetime = Field(
        description="Last successful sync from external French API",
    )

    created_at: datetime = Field(description="Record creation timestamp")
    updated_at: datetime = Field(description="Record last update timestamp")

    @staticmethod
    def _parse_date_amm(date_str: str | None) -> date | None:
        """Parse dateAMM string in DD/MM/YYYY format from French API.

        Parameters
        ----------
        date_str : str | None
            Date string in format "DD/MM/YYYY" (e.g., "08/07/1985")

        Returns
        -------
        date | None
            Parsed date object or None if invalid/missing

        """
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%d/%m/%Y").date()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def from_api(api_data: dict) -> GlobalMedicationResponse:
        """Create DTO from external API data.

        Parameters
        ----------
        api_data : dict
            Data dictionary from external API

        Returns
        -------
        GlobalMedicationResponse
            Medication DTO

        """
        return GlobalMedicationResponse(
            cis=api_data.get("cis"),
            element_pharmaceutique=api_data.get("elementPharmaceutique"),
            forme_pharmaceutique=api_data.get("formePharmaceutique"),
            voies_administration=api_data.get("voiesAdministration"),
            status_autorisation=api_data.get("statusAutorisation"),
            type_procedure=api_data.get("typeProcedure"),
            etat_commercialisation=api_data.get("etatComercialisation"),
            date_amm=GlobalMedicationResponse._parse_date_amm(
                api_data.get("dateAMM"),
            ),
            titulaire=api_data.get("titulaire"),
            sync_date=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )


class GlobalMedicationListResponse(BaseModel):
    """Response DTO for a list of global medications."""

    model_config = ConfigDict(from_attributes=True)

    medications: list[GlobalMedicationResponse] = Field(
        description="List of medications",
    )

    total: int = Field(description="Total number of medications in database")


class GlobalMedicationSearchRequest(BaseModel):
    """Request DTO for searching medications."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"query": "paracetamol", "limit": 20},
        },
    )

    query: str = Field(
        min_length=1,
        max_length=255,
        description="Search query for medication name or manufacturer",
    )

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    )
