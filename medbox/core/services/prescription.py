"""Service for prescription management."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status

from medbox.core.db.models.prescription import Prescription
from medbox.core.db.models.prescription_item import PrescriptionItem
from medbox.core.db.repositories.patient import PatientRepository
from medbox.core.db.repositories.prescription import PrescriptionRepository
from medbox.core.dto.prescription import (
    PrescriptionItemRequest,
    PrescriptionItemResponse,
    PrescriptionRequest,
    PrescriptionResponse,
    StatusUpdateRequest,
)
from medbox.core.storage.s3_client import S3Client

# File upload constraints
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}


class PrescriptionService:
    """Service for prescription management."""

    def __init__(
        self,
        tenant_id: UUID,
        prescription_repo: PrescriptionRepository | None = None,
        patient_repo: PatientRepository | None = None,
        s3_client: S3Client | None = None,
    ) -> None:
        """Initialize the service."""
        self.tenant_id = tenant_id
        self.prescription_repo = prescription_repo or PrescriptionRepository(
            tenant_id=tenant_id,
        )
        self.patient_repo = patient_repo or PatientRepository(tenant_id=tenant_id)
        self.s3_client = s3_client or S3Client()

    # ========== PRESCRIPTION CRUD ==========

    async def create(
        self,
        data: PrescriptionRequest,
        created_by_user_id: UUID | None = None,
    ) -> PrescriptionResponse:
        """Create a new prescription for a patient.

        Parameters
        ----------
        data : PrescriptionRequest
            Prescription data including items
        created_by_user_id : UUID | None
            User ID who created the prescription

        Returns
        -------
        PrescriptionResponse
            Created prescription with items

        Raises
        ------
        HTTPException
            404 if patient not found in tenant
            400 if validation fails
        """
        # Validate patient exists in tenant
        patient = await self.patient_repo.get(data.patient_id)
        if not patient:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Patient {data.patient_id} not found in tenant",
            )

        # Create prescription
        prescription = Prescription(
            id=uuid4(),
            tenant_id=self.tenant_id,
            patient_id=data.patient_id,
            created_by_user_id=created_by_user_id,
            title=data.title,
            c_notes=data.c_notes,
            status=data.status,
            start_date=data.start_date,
            end_date=data.end_date,
        )

        # Create items
        items = [
            PrescriptionItem(
                id=uuid4(),
                prescription_id=prescription.id,
                medication_cis=item.medication_cis,
                medication_label=item.medication_label,
                dose=item.dose.model_dump() if item.dose else None,
                frequency=item.frequency.model_dump(),
                extra_instructions=item.extra_instructions,
            )
            for item in data.items
        ]
        prescription.items = items

        # Save to database
        created = await self.prescription_repo.add(prescription)

        # Load relations for response
        created_with_relations = await self.prescription_repo.get(
            created.id,
            relations=["items", "patient"],
        )
        if not created_with_relations:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Failed to retrieve created prescription",
            )

        return PrescriptionResponse.model_validate(created_with_relations)

    async def get(self, prescription_id: UUID) -> PrescriptionResponse:
        """Get a prescription by ID with tenant check.

        Parameters
        ----------
        prescription_id : UUID
            Prescription ID

        Returns
        -------
        PrescriptionResponse
            Prescription with items and patient

        Raises
        ------
        HTTPException
            404 if not found or not in tenant
        """
        prescription = await self.prescription_repo.get(
            prescription_id,
            relations=["items", "items.medication", "patient"],
        )
        if not prescription:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Prescription {prescription_id} not found",
            )

        return PrescriptionResponse.model_validate(prescription)

    async def list_by_patient(
        self,
        patient_id: UUID,
        page: int = 1,
        per_page: int = 20,
        status: str | None = None,
    ) -> dict:
        """List prescriptions for a patient with pagination.

        Parameters
        ----------
        patient_id : UUID
            Patient ID
        page : int
            Page number (1-indexed)
        per_page : int
            Items per page
        status : str | None
            Filter by status (active/paused/stopped/expired)

        Returns
        -------
        dict
            Paginated response with items, total, page, per_page
        """
        # Validate patient exists
        patient = await self.patient_repo.get(patient_id)
        if not patient:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Patient {patient_id} not found in tenant",
            )

        # Get paginated prescriptions
        page_result = await self.prescription_repo.paginate_by_patient(
            patient_id=patient_id,
            page=page,
            per_page=per_page,
            status=status,
            relations=["items"],
        )

        return {
            "items": [
                PrescriptionResponse.model_validate(p) for p in page_result.items
            ],
            "total": page_result.total,
            "page": page_result.page,
            "per_page": page_result.per_page,
            "pages": page_result.pages,
        }

    async def update(
        self,
        prescription_id: UUID,
        data: PrescriptionRequest,
    ) -> PrescriptionResponse:
        """Update a prescription (replaces items).

        Parameters
        ----------
        prescription_id : UUID
            Prescription ID
        data : PrescriptionRequest
            Updated prescription data

        Returns
        -------
        PrescriptionResponse
            Updated prescription

        Raises
        ------
        HTTPException
            404 if not found
            400 if validation fails
        """
        # Load existing prescription
        prescription = await self._validate_prescription_in_tenant(prescription_id)

        # Validate patient
        if data.patient_id != prescription.patient_id:
            patient = await self.patient_repo.get(data.patient_id)
            if not patient:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    f"Patient {data.patient_id} not found in tenant",
                )

        # Update fields
        prescription.patient_id = data.patient_id
        prescription.title = data.title
        prescription.c_notes = data.c_notes
        prescription.status = data.status
        prescription.start_date = data.start_date
        prescription.end_date = data.end_date

        # Replace items (clear old, add new)
        prescription.items.clear()
        prescription.items = [
            PrescriptionItem(
                id=uuid4(),
                prescription_id=prescription.id,
                medication_cis=item.medication_cis,
                medication_label=item.medication_label,
                dose=item.dose.model_dump() if item.dose else None,
                frequency=item.frequency.model_dump(),
                extra_instructions=item.extra_instructions,
            )
            for item in data.items
        ]

        # Save
        updated = await self.prescription_repo.update(prescription)

        # Reload with relations
        updated_with_relations = await self.prescription_repo.get(
            updated.id,
            relations=["items", "patient"],
        )
        if not updated_with_relations:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Failed to retrieve updated prescription",
            )

        return PrescriptionResponse.model_validate(updated_with_relations)

    async def update_status(
        self,
        prescription_id: UUID,
        status_data: StatusUpdateRequest,
    ) -> PrescriptionResponse:
        """Update only the prescription status.

        Parameters
        ----------
        prescription_id : UUID
            Prescription ID
        status_data : StatusUpdateRequest
            New status

        Returns
        -------
        PrescriptionResponse
            Updated prescription
        """
        prescription = await self._validate_prescription_in_tenant(prescription_id)
        prescription.status = status_data.status

        updated = await self.prescription_repo.update(prescription)

        # Reload with relations
        updated_with_relations = await self.prescription_repo.get(
            updated.id,
            relations=["items", "patient"],
        )
        if not updated_with_relations:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Failed to retrieve updated prescription",
            )

        return PrescriptionResponse.model_validate(updated_with_relations)

    async def delete(self, prescription_id: UUID) -> bool:
        """Delete a prescription.

        Parameters
        ----------
        prescription_id : UUID
            Prescription ID

        Returns
        -------
        bool
            True if deleted

        Raises
        ------
        HTTPException
            404 if not found
        """
        prescription = await self._validate_prescription_in_tenant(prescription_id)

        # Delete document from S3 if exists
        if prescription.document_s3_key:
            try:
                await self.s3_client.delete_file(prescription.document_s3_key)
            except Exception:
                # Log but don't fail deletion if S3 delete fails
                pass

        await self.prescription_repo.delete(prescription_id)
        return True

    # ========== ITEM MANAGEMENT ==========

    async def add_item(
        self,
        prescription_id: UUID,
        item_data: PrescriptionItemRequest,
    ) -> PrescriptionResponse:
        """Add a new item to an existing prescription.

        Parameters
        ----------
        prescription_id : UUID
            Prescription ID
        item_data : PrescriptionItemRequest
            Item data to add

        Returns
        -------
        PrescriptionResponse
            Updated prescription with new item
        """
        # Load prescription with items
        prescription = await self._validate_prescription_in_tenant(
            prescription_id,
            relations=["items"],
        )

        # Create new item
        new_item = PrescriptionItem(
            id=uuid4(),
            prescription_id=prescription_id,
            medication_cis=item_data.medication_cis,
            medication_label=item_data.medication_label,
            dose=item_data.dose.model_dump() if item_data.dose else None,
            frequency=item_data.frequency.model_dump(),
            extra_instructions=item_data.extra_instructions,
        )

        # Add to list (SQLAlchemy tracks changes)
        prescription.items.append(new_item)

        # Save (merge pattern)
        updated = await self.prescription_repo.update(prescription)

        # Reload with relations
        updated_with_relations = await self.prescription_repo.get(
            updated.id,
            relations=["items", "patient"],
        )
        if not updated_with_relations:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Failed to retrieve updated prescription",
            )

        return PrescriptionResponse.model_validate(updated_with_relations)

    async def update_item(
        self,
        prescription_id: UUID,
        item_id: UUID,
        item_data: PrescriptionItemRequest,
    ) -> PrescriptionResponse:
        """Update an existing item in a prescription.

        Parameters
        ----------
        prescription_id : UUID
            Prescription ID
        item_id : UUID
            Item ID to update
        item_data : PrescriptionItemRequest
            Updated item data

        Returns
        -------
        PrescriptionResponse
            Updated prescription

        Raises
        ------
        HTTPException
            404 if item not found
        """
        # Load prescription with items
        prescription = await self._validate_prescription_in_tenant(
            prescription_id,
            relations=["items"],
        )

        # Find the item
        item = next((i for i in prescription.items if i.id == item_id), None)
        if not item:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Item {item_id} not found in prescription",
            )

        # Update fields
        item.medication_cis = item_data.medication_cis
        item.medication_label = item_data.medication_label
        item.dose = item_data.dose.model_dump() if item_data.dose else None
        item.frequency = item_data.frequency.model_dump()
        item.extra_instructions = item_data.extra_instructions

        # Save
        updated = await self.prescription_repo.update(prescription)

        # Reload with relations
        updated_with_relations = await self.prescription_repo.get(
            updated.id,
            relations=["items", "patient"],
        )
        if not updated_with_relations:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Failed to retrieve updated prescription",
            )

        return PrescriptionResponse.model_validate(updated_with_relations)

    async def delete_item(
        self,
        prescription_id: UUID,
        item_id: UUID,
    ) -> PrescriptionResponse:
        """Delete an item from a prescription.

        Parameters
        ----------
        prescription_id : UUID
            Prescription ID
        item_id : UUID
            Item ID to delete

        Returns
        -------
        PrescriptionResponse
            Updated prescription

        Raises
        ------
        HTTPException
            400 if trying to delete last item
            404 if item not found
        """
        # Load prescription with items
        prescription = await self._validate_prescription_in_tenant(
            prescription_id,
            relations=["items"],
        )

        # Check at least 2 items (don't allow empty prescription)
        if len(prescription.items) <= 1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Cannot delete last item - prescription must have at least 1 item",
            )

        # Find and remove item
        item = next((i for i in prescription.items if i.id == item_id), None)
        if not item:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Item {item_id} not found",
            )

        prescription.items.remove(item)

        # Save (cascade delete)
        updated = await self.prescription_repo.update(prescription)

        # Reload with relations
        updated_with_relations = await self.prescription_repo.get(
            updated.id,
            relations=["items", "patient"],
        )
        if not updated_with_relations:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Failed to retrieve updated prescription",
            )

        return PrescriptionResponse.model_validate(updated_with_relations)

    async def get_item(
        self,
        prescription_id: UUID,
        item_id: UUID,
    ) -> PrescriptionItemResponse:
        """Get a specific item from a prescription.

        Parameters
        ----------
        prescription_id : UUID
            Prescription ID
        item_id : UUID
            Item ID

        Returns
        -------
        PrescriptionItemResponse
            Item details

        Raises
        ------
        HTTPException
            404 if not found
        """
        prescription = await self._validate_prescription_in_tenant(
            prescription_id,
            relations=["items", "items.medication"],
        )

        item = next((i for i in prescription.items if i.id == item_id), None)
        if not item:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Item {item_id} not found",
            )

        return PrescriptionItemResponse.model_validate(item)

    # ========== DOCUMENT HANDLING ==========

    async def upload_document(
        self,
        prescription_id: UUID,
        file: UploadFile,
    ) -> PrescriptionResponse:
        """Upload a prescription document (ordonnance) to S3.

        Parameters
        ----------
        prescription_id : UUID
            Prescription ID
        file : UploadFile
            Document file (PDF/image)

        Returns
        -------
        PrescriptionResponse
            Updated prescription with document metadata

        Raises
        ------
        HTTPException
            400 if file validation fails
            404 if prescription not found
        """
        prescription = await self._validate_prescription_in_tenant(prescription_id)

        # Validate file
        if not file.content_type or file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Invalid file type. Allowed: {', '.join(ALLOWED_MIME_TYPES)}",
            )

        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"File too large. Max size: {MAX_FILE_SIZE / 1024 / 1024} MB",
            )

        # Delete old document if exists
        if prescription.document_s3_key:
            try:
                await self.s3_client.delete_file(prescription.document_s3_key)
            except Exception:
                # Log but continue
                pass

        # Build S3 key
        extension = Path(file.filename or "ordonnance.pdf").suffix.lstrip(".")
        s3_key = self.s3_client.build_s3_key(
            tenant_id=self.tenant_id,
            prescription_id=prescription_id,
            extension=extension,
        )

        # Upload to S3
        await self.s3_client.upload_file(
            file_data=BytesIO(file_content),
            s3_key=s3_key,
            mime_type=file.content_type,
        )

        # Update prescription metadata
        prescription.document_s3_key = s3_key
        prescription.document_file_name = file.filename
        prescription.document_file_size = file_size
        prescription.document_mime_type = file.content_type
        prescription.document_uploaded_at = datetime.now(UTC)

        # Save
        updated = await self.prescription_repo.update(prescription)

        # Reload with relations
        updated_with_relations = await self.prescription_repo.get(
            updated.id,
            relations=["items", "patient"],
        )
        if not updated_with_relations:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Failed to retrieve updated prescription",
            )

        return PrescriptionResponse.model_validate(updated_with_relations)

    async def get_document_url(self, prescription_id: UUID) -> str:
        """Generate a presigned URL for downloading the prescription document.

        Parameters
        ----------
        prescription_id : UUID
            Prescription ID

        Returns
        -------
        str
            Presigned URL (valid for 1 hour)

        Raises
        ------
        HTTPException
            404 if prescription or document not found
        """
        prescription = await self._validate_prescription_in_tenant(prescription_id)

        if not prescription.document_s3_key:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "No document attached to this prescription",
            )

        # Generate presigned URL (1 hour expiration)
        return await self.s3_client.generate_presigned_url(
            prescription.document_s3_key,
            expires_in=3600,
        )

    async def delete_document(self, prescription_id: UUID) -> bool:
        """Delete the prescription document from S3.

        Parameters
        ----------
        prescription_id : UUID
            Prescription ID

        Returns
        -------
        bool
            True if deleted

        Raises
        ------
        HTTPException
            404 if prescription or document not found
        """
        prescription = await self._validate_prescription_in_tenant(prescription_id)

        if not prescription.document_s3_key:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "No document attached to this prescription",
            )

        # Delete from S3
        await self.s3_client.delete_file(prescription.document_s3_key)

        # Clear metadata
        prescription.document_s3_key = None
        prescription.document_file_name = None
        prescription.document_file_size = None
        prescription.document_mime_type = None
        prescription.document_uploaded_at = None

        # Save
        await self.prescription_repo.update(prescription)

        return True

    # ========== PRIVATE HELPERS ==========

    async def _validate_prescription_in_tenant(
        self,
        prescription_id: UUID,
        relations: list[str] | None = None,
    ) -> Prescription:
        """Validate prescription exists and belongs to tenant.

        Parameters
        ----------
        prescription_id : UUID
            Prescription ID
        relations : list[str] | None
            Relations to load

        Returns
        -------
        Prescription
            Prescription object

        Raises
        ------
        HTTPException
            404 if not found or not in tenant
        """
        prescription = await self.prescription_repo.get(
            prescription_id,
            relations=relations,
        )
        if not prescription:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Prescription {prescription_id} not found",
            )
        return prescription
