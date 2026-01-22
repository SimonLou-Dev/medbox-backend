"""Tests for Global Medication repository and service layer."""

from datetime import date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from medbox.core.db.models.global_medication import GlobalMedication
from medbox.core.db.repositories.global_medication import GlobalMedicationRepository
from medbox.core.services.global_medication import GlobalMedicationService

pytestmark = pytest.mark.asyncio


class TestGlobalMedicationRepository:
    """Test GlobalMedicationRepository methods."""

    async def test_get_by_cis(self, db_session: AsyncSession) -> None:
        """Test fetching medication by CIS code."""
        # Setup
        med = GlobalMedication(
            cis=61504672,
            element_pharmaceutique="PARACETAMOL MYLAN 1 g, comprimé",
            forme_pharmaceutique="comprimé",
            voies_administration=["orale"],
            status_autorisation="Autorisation active",
            type_procedure="Procédure nationale",
            etat_commercialisation="Commercialisée",
            date_amm=date(2000, 1, 1),
            titulaire="MYLAN SAS",
            sync_date=datetime.now(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(med)
        await db_session.commit()

        # Test get_by_cis
        repo = GlobalMedicationRepository()
        retrieved = await repo.get_by_cis(61504672)
        assert retrieved is not None
        assert retrieved.cis == 61504672
        assert retrieved.element_pharmaceutique == "PARACETAMOL MYLAN 1 g, comprimé"
        assert retrieved.titulaire == "MYLAN SAS"

    async def test_get_by_cis_not_found(self, db_session: AsyncSession) -> None:
        """Test get_by_cis returns None when not found."""
        repo = GlobalMedicationRepository()
        retrieved = await repo.get_by_cis(999999999)
        assert retrieved is None

    async def test_search_by_name(self, db_session: AsyncSession) -> None:
        """Test searching medications by product name."""
        # Setup: Add multiple medications
        meds = [
            GlobalMedication(
                cis=61504672,
                element_pharmaceutique="PARACETAMOL MYLAN 1 g, comprimé",
                forme_pharmaceutique="comprimé",
                voies_administration=["orale"],
                status_autorisation="Autorisation active",
                type_procedure="Procédure nationale",
                etat_commercialisation="Commercialisée",
                date_amm=date(2000, 1, 1),
                titulaire="MYLAN SAS",
                sync_date=datetime.now(),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
            GlobalMedication(
                cis=60001234,
                element_pharmaceutique="DOLIPRANE 1000 mg, comprimé",
                forme_pharmaceutique="comprimé",
                voies_administration=["orale"],
                status_autorisation="Autorisation active",
                type_procedure="Procédure nationale",
                etat_commercialisation="Commercialisée",
                date_amm=date(1998, 5, 15),
                titulaire="SANOFI AVENTIS FRANCE",
                sync_date=datetime.now(),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
        ]
        db_session.add_all(meds)
        await db_session.commit()

        # Search for "paracetamol"
        repo = GlobalMedicationRepository()
        results, total = await repo.search("paracetamol", limit=10)
        assert total == 1
        assert len(results) == 1
        assert results[0].cis == 61504672

    async def test_search_by_manufacturer(self, db_session: AsyncSession) -> None:
        """Test searching medications by manufacturer."""
        # Setup
        meds = [
            GlobalMedication(
                cis=61504672,
                element_pharmaceutique="PARACETAMOL MYLAN 1 g, comprimé",
                forme_pharmaceutique="comprimé",
                voies_administration=["orale"],
                status_autorisation="Autorisation active",
                type_procedure="Procédure nationale",
                etat_commercialisation="Commercialisée",
                date_amm=date(2000, 1, 1),
                titulaire="MYLAN SAS",
                sync_date=datetime.now(),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
            GlobalMedication(
                cis=61234567,
                element_pharmaceutique="IBUPROFEN MYLAN 200 mg, comprimé",
                forme_pharmaceutique="comprimé",
                voies_administration=["orale"],
                status_autorisation="Autorisation active",
                type_procedure="Procédure nationale",
                etat_commercialisation="Commercialisée",
                date_amm=date(2001, 6, 10),
                titulaire="MYLAN SAS",
                sync_date=datetime.now(),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
        ]
        db_session.add_all(meds)
        await db_session.commit()

        # Search for "MYLAN"
        repo = GlobalMedicationRepository()
        results, total = await repo.search("mylan", limit=10)
        assert total == 2
        assert len(results) == 2

    async def test_search_case_insensitive(self, db_session: AsyncSession) -> None:
        """Test search is case-insensitive."""
        # Setup
        med = GlobalMedication(
            cis=61504672,
            element_pharmaceutique="PARACETAMOL MYLAN 1 g, comprimé",
            forme_pharmaceutique="comprimé",
            voies_administration=["orale"],
            status_autorisation="Autorisation active",
            type_procedure="Procédure nationale",
            etat_commercialisation="Commercialisée",
            date_amm=date(2000, 1, 1),
            titulaire="MYLAN SAS",
            sync_date=datetime.now(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(med)
        await db_session.commit()

        # Search with different cases
        repo = GlobalMedicationRepository()
        results_lower, _ = await repo.search("paracetamol", limit=10)
        results_upper, _ = await repo.search("PARACETAMOL", limit=10)
        results_mixed, _ = await repo.search("PaRaCeTaMoL", limit=10)

        assert len(results_lower) == 1
        assert len(results_upper) == 1
        assert len(results_mixed) == 1

    async def test_search_pagination(self, db_session: AsyncSession) -> None:
        """Test search pagination with offset."""
        # Setup: Add 15 medications
        for i in range(15):
            med = GlobalMedication(
                cis=60000000 + i,
                element_pharmaceutique=f"MEDICATION_{i}",
                forme_pharmaceutique="comprimé",
                voies_administration=["orale"],
                status_autorisation="Autorisation active",
                type_procedure="Procédure nationale",
                etat_commercialisation="Commercialisée",
                date_amm=date(2000, 1, 1),
                titulaire="TEST PHARMA",
                sync_date=datetime.now(),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db_session.add(med)
        await db_session.commit()

        # Test first page
        repo = GlobalMedicationRepository()
        results_p1, total = await repo.search("medication", limit=5, offset=0)
        assert total == 15
        assert len(results_p1) == 5

        # Test second page
        results_p2, _ = await repo.search("medication", limit=5, offset=5)
        assert len(results_p2) == 5
        assert results_p1[0].cis != results_p2[0].cis

    async def test_list_all(self, db_session: AsyncSession) -> None:
        """Test listing all medications with pagination."""
        # Setup: Add 10 medications
        for i in range(10):
            med = GlobalMedication(
                cis=60000000 + i,
                element_pharmaceutique=f"MED_{i}",
                forme_pharmaceutique="comprimé",
                voies_administration=["orale"],
                status_autorisation="Autorisation active",
                type_procedure="Procédure nationale",
                etat_commercialisation="Commercialisée",
                date_amm=date(2000, 1, 1),
                titulaire="PHARMA",
                sync_date=datetime.now(),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db_session.add(med)
        await db_session.commit()

        # List all
        repo = GlobalMedicationRepository()
        results, total = await repo.list_all(limit=100, offset=0)
        assert total == 10
        assert len(results) == 10

    async def test_count_total(self, db_session: AsyncSession) -> None:
        """Test counting total medications."""
        # Setup: Add 5 medications
        for i in range(5):
            med = GlobalMedication(
                cis=60000000 + i,
                element_pharmaceutique=f"MED_{i}",
                forme_pharmaceutique="comprimé",
                voies_administration=["orale"],
                status_autorisation="Autorisation active",
                type_procedure="Procédure nationale",
                etat_commercialisation="Commercialisée",
                date_amm=date(2000, 1, 1),
                titulaire="PHARMA",
                sync_date=datetime.now(),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db_session.add(med)
        await db_session.commit()

        # Count
        repo = GlobalMedicationRepository()
        total = await repo.count_total()
        assert total == 5


class TestGlobalMedicationService:
    """Test GlobalMedicationService methods."""

    async def test_get_by_cis_returns_response_dto(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test get_by_cis returns GlobalMedicationResponse DTO."""
        # Setup
        med = GlobalMedication(
            cis=61504672,
            element_pharmaceutique="PARACETAMOL MYLAN 1 g, comprimé",
            forme_pharmaceutique="comprimé",
            voies_administration=["orale"],
            status_autorisation="Autorisation active",
            type_procedure="Procédure nationale",
            etat_commercialisation="Commercialisée",
            date_amm=date(2000, 1, 1),
            titulaire="MYLAN SAS",
            sync_date=datetime.now(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(med)
        await db_session.commit()

        # Get via service
        repo = GlobalMedicationRepository()
        service = GlobalMedicationService(repo)
        result = await service.get_by_cis(61504672)

        assert result.cis == 61504672
        assert result.titulaire == "MYLAN SAS"

    async def test_search_returns_list_response(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test search returns GlobalMedicationListResponse DTO."""
        # Setup
        med = GlobalMedication(
            cis=61504672,
            element_pharmaceutique="PARACETAMOL MYLAN 1 g, comprimé",
            forme_pharmaceutique="comprimé",
            voies_administration=["orale"],
            status_autorisation="Autorisation active",
            type_procedure="Procédure nationale",
            etat_commercialisation="Commercialisée",
            date_amm=date(2000, 1, 1),
            titulaire="MYLAN SAS",
            sync_date=datetime.now(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(med)
        await db_session.commit()

        # Search via service
        repo = GlobalMedicationRepository()
        service = GlobalMedicationService(repo)
        result = await service.search("paracetamol")

        assert result.total == 1
        assert len(result.medications) == 1
        assert result.medications[0].cis == 61504672

    async def test_get_total_count(self, db_session: AsyncSession) -> None:
        """Test getting total medication count."""
        # Setup: Add 3 medications
        for i in range(3):
            med = GlobalMedication(
                cis=60000000 + i,
                element_pharmaceutique=f"MED_{i}",
                forme_pharmaceutique="comprimé",
                voies_administration=["orale"],
                status_autorisation="Autorisation active",
                type_procedure="Procédure nationale",
                etat_commercialisation="Commercialisée",
                date_amm=date(2000, 1, 1),
                titulaire="PHARMA",
                sync_date=datetime.now(),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db_session.add(med)
        await db_session.commit()

        # Get count
        repo = GlobalMedicationRepository()
        service = GlobalMedicationService(repo)
        total = await service.get_total_count()

        assert total == 3
