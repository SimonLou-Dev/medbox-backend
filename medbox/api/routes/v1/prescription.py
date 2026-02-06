"""Router for prescription management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from medbox.core.dto.prescription import (
    PrescriptionItemRequest,
    PrescriptionItemResponse,
    PrescriptionRequest,
    PrescriptionResponse,
    StatusUpdateRequest,
)
from medbox.core.services import (
    CurrentUser,
    get_user_service,
)
from medbox.core.services.prescription import PrescriptionService
from medbox.core.services.user import UserService

router = APIRouter(tags=["Prescriptions"])

# ==============================================================================
# Dependencies
# ==============================================================================


async def get_prescription_service(
    user: CurrentUser,
    user_svc: Annotated[UserService, Depends(get_user_service)],
) -> PrescriptionService:
    """Create a prescription service instance.

    Args:
        user: Authenticated user
        user_svc: User service for tenant retrieval

    Returns:
        PrescriptionService: Configured service for the user's tenant

    """
    db_user = await user_svc.get_user_from_subject(user.subject)
    return PrescriptionService(tenant_id=db_user.tenant_id)


PrescriptionSvcDep = Annotated[PrescriptionService, Depends(get_prescription_service)]


# ==============================================================================
# Prescription CRUD Routes
# ==============================================================================


@router.post(
    "/patients/{patient_id}/prescriptions",
    status_code=status.HTTP_201_CREATED,
)
async def create_prescription(
    patient_id: UUID,
    body: PrescriptionRequest,
    user: CurrentUser,
    prescription_svc: PrescriptionSvcDep,
) -> PrescriptionResponse:
    """Create a new prescription for a patient.

    Requires the patient to belong to the user's tenant.

    Args:
        patient_id: Patient UUID
        body: Prescription data with items
        user: Authenticated user
        prescription_svc: Prescription service

    Returns:
        Created prescription with items

    Raises:
        HTTPException: 404 if patient not found in tenant
        HTTPException: 400 if validation fails (e.g., no items)

    """
    # Ensure patient_id matches
    if body.patient_id != patient_id:
        body.patient_id = patient_id

    return await prescription_svc.create(body)


@router.get("/patients/{patient_id}/prescriptions")
async def list_patient_prescriptions(
    patient_id: UUID,
    user: CurrentUser,
    prescription_svc: PrescriptionSvcDep,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: Annotated[
        str | None,
        Query(
            alias="status",
            description="Filter by status: active, paused, stopped, expired",
        ),
    ] = None,
) -> dict:
    """Get paginated list of prescriptions for a patient.

    Requires the patient to belong to the user's tenant.

    Args:
        patient_id: Patient UUID
        user: Authenticated user
        prescription_svc: Prescription service
        page: Page number (default 1)
        per_page: Items per page (default 20, max 100)
        status_filter: Optional status filter

    Returns:
        Paginated prescription list with metadata

    Raises:
        HTTPException: 404 if patient not found in tenant

    """
    return await prescription_svc.list_by_patient(
        patient_id=patient_id,
        page=page,
        per_page=per_page,
        status=status_filter,
    )


@router.get("/prescriptions/{prescription_id}")
async def get_prescription(
    prescription_id: UUID,
    user: CurrentUser,
    prescription_svc: PrescriptionSvcDep,
) -> PrescriptionResponse:
    """Get prescription details by ID.

    Requires the prescription to belong to the user's tenant.

    Args:
        prescription_id: Prescription UUID
        user: Authenticated user
        prescription_svc: Prescription service

    Returns:
        Prescription with items and patient info

    Raises:
        HTTPException: 404 if prescription not found in tenant

    """
    return await prescription_svc.get(prescription_id)


@router.patch("/prescriptions/{prescription_id}")
async def update_prescription(
    prescription_id: UUID,
    body: PrescriptionRequest,
    user: CurrentUser,
    prescription_svc: PrescriptionSvcDep,
) -> PrescriptionResponse:
    """Update a prescription (replaces all items).

    Requires the prescription to belong to the user's tenant.

    Args:
        prescription_id: Prescription UUID
        body: Updated prescription data
        user: Authenticated user
        prescription_svc: Prescription service

    Returns:
        Updated prescription

    Raises:
        HTTPException: 404 if prescription not found in tenant
        HTTPException: 400 if validation fails

    """
    return await prescription_svc.update(prescription_id, body)


@router.patch("/prescriptions/{prescription_id}/status")
async def update_prescription_status(
    prescription_id: UUID,
    body: StatusUpdateRequest,
    user: CurrentUser,
    prescription_svc: PrescriptionSvcDep,
) -> PrescriptionResponse:
    """Update only the prescription status.

    Requires the prescription to belong to the user's tenant.

    Args:
        prescription_id: Prescription UUID
        body: New status
        user: Authenticated user
        prescription_svc: Prescription service

    Returns:
        Updated prescription

    Raises:
        HTTPException: 404 if prescription not found in tenant
        HTTPException: 400 if invalid status

    """
    return await prescription_svc.update_status(prescription_id, body)


@router.delete(
    "/prescriptions/{prescription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_prescription(
    prescription_id: UUID,
    user: CurrentUser,
    prescription_svc: PrescriptionSvcDep,
) -> None:
    """Delete a prescription and its associated document.

    Requires the prescription to belong to the user's tenant.

    Args:
        prescription_id: Prescription UUID
        user: Authenticated user
        prescription_svc: Prescription service

    Raises:
        HTTPException: 404 if prescription not found in tenant

    """
    await prescription_svc.delete(prescription_id)


# ==============================================================================
# Item Management Routes
# ==============================================================================


@router.post(
    "/prescriptions/{prescription_id}/items",
    status_code=status.HTTP_201_CREATED,
)
async def add_prescription_item(
    prescription_id: UUID,
    body: PrescriptionItemRequest,
    user: CurrentUser,
    prescription_svc: PrescriptionSvcDep,
) -> PrescriptionResponse:
    """Add a new item to an existing prescription.

    Requires the prescription to belong to the user's tenant.

    Args:
        prescription_id: Prescription UUID
        body: Item data (medication, dose, frequency)
        user: Authenticated user
        prescription_svc: Prescription service

    Returns:
        Updated prescription with all items

    Raises:
        HTTPException: 404 if prescription not found in tenant

    """
    return await prescription_svc.add_item(prescription_id, body)


@router.get("/prescriptions/{prescription_id}/items/{item_id}")
async def get_prescription_item(
    prescription_id: UUID,
    item_id: UUID,
    user: CurrentUser,
    prescription_svc: PrescriptionSvcDep,
) -> PrescriptionItemResponse:
    """Get details of a specific prescription item.

    Requires the prescription to belong to the user's tenant.

    Args:
        prescription_id: Prescription UUID
        item_id: Item UUID
        user: Authenticated user
        prescription_svc: Prescription service

    Returns:
        Item details

    Raises:
        HTTPException: 404 if prescription or item not found

    """
    return await prescription_svc.get_item(prescription_id, item_id)


@router.patch("/prescriptions/{prescription_id}/items/{item_id}")
async def update_prescription_item(
    prescription_id: UUID,
    item_id: UUID,
    body: PrescriptionItemRequest,
    user: CurrentUser,
    prescription_svc: PrescriptionSvcDep,
) -> PrescriptionResponse:
    """Update an existing prescription item.

    Requires the prescription to belong to the user's tenant.

    Args:
        prescription_id: Prescription UUID
        item_id: Item UUID
        body: Updated item data
        user: Authenticated user
        prescription_svc: Prescription service

    Returns:
        Updated prescription with all items

    Raises:
        HTTPException: 404 if prescription or item not found

    """
    return await prescription_svc.update_item(prescription_id, item_id, body)


@router.delete(
    "/prescriptions/{prescription_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_prescription_item(
    prescription_id: UUID,
    item_id: UUID,
    user: CurrentUser,
    prescription_svc: PrescriptionSvcDep,
) -> None:
    """Delete a prescription item.

    Cannot delete the last item - prescription must have at least 1 item.

    Requires the prescription to belong to the user's tenant.

    Args:
        prescription_id: Prescription UUID
        item_id: Item UUID
        user: Authenticated user
        prescription_svc: Prescription service

    Raises:
        HTTPException: 404 if prescription or item not found
        HTTPException: 400 if trying to delete the last item

    """
    await prescription_svc.delete_item(prescription_id, item_id)


# ==============================================================================
# Document Handling Routes
# ==============================================================================


@router.post("/prescriptions/{prescription_id}/document")
async def upload_prescription_document(
    prescription_id: UUID,
    file: Annotated[UploadFile, File(description="PDF or image file (max 10 MB)")],
    user: CurrentUser,
    prescription_svc: PrescriptionSvcDep,
) -> PrescriptionResponse:
    """Upload a prescription document (ordonnance) to S3.

    Accepts PDF, JPEG, or PNG files up to 10 MB.

    Requires the prescription to belong to the user's tenant.

    Args:
        prescription_id: Prescription UUID
        file: Uploaded file
        user: Authenticated user
        prescription_svc: Prescription service

    Returns:
        Updated prescription with document metadata

    Raises:
        HTTPException: 404 if prescription not found
        HTTPException: 400 if file type or size invalid
        HTTPException: 500 if S3 upload fails

    """
    return await prescription_svc.upload_document(prescription_id, file)


@router.get("/prescriptions/{prescription_id}/document/url")
async def get_prescription_document_url(
    prescription_id: UUID,
    user: CurrentUser,
    prescription_svc: PrescriptionSvcDep,
) -> dict:
    """Generate a presigned URL to download the prescription document.

    URL expires after 1 hour.

    Requires the prescription to belong to the user's tenant.

    Args:
        prescription_id: Prescription UUID
        user: Authenticated user
        prescription_svc: Prescription service

    Returns:
        Dict with 'url' and 'expires_in' keys

    Raises:
        HTTPException: 404 if prescription or document not found

    """
    url = await prescription_svc.get_document_url(prescription_id)
    return {"url": url, "expires_in": 3600}


@router.delete(
    "/prescriptions/{prescription_id}/document",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_prescription_document(
    prescription_id: UUID,
    user: CurrentUser,
    prescription_svc: PrescriptionSvcDep,
) -> None:
    """Delete the prescription document from S3.

    Requires the prescription to belong to the user's tenant.

    Args:
        prescription_id: Prescription UUID
        user: Authenticated user
        prescription_svc: Prescription service

    Raises:
        HTTPException: 404 if prescription or document not found
        HTTPException: 500 if S3 deletion fails

    """
    await prescription_svc.delete_document(prescription_id)
