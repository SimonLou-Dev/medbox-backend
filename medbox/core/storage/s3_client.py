"""S3 Client for async file storage operations."""

from __future__ import annotations

import uuid
from typing import BinaryIO

import aioboto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, status

from medbox.core.config.settings import settings


class S3Client:
    """Async S3 client for document storage."""

    def __init__(self) -> None:
        """Initialize S3 client with settings."""
        self.endpoint = settings.s3_endpoint
        self.region = settings.s3_region
        self.bucket = settings.s3_bucket
        self.access_key = settings.s3_access_key
        self.secret_key = settings.s3_secret_key

        self._session = aioboto3.Session()

    async def upload_file(
        self,
        file_data: BinaryIO,
        s3_key: str,
        mime_type: str,
    ) -> str:
        """Upload file to S3.

        Parameters
        ----------
        file_data : BinaryIO
            File data to upload
        s3_key : str
            S3 object key (path)
        mime_type : str
            MIME type of file

        Returns
        -------
        str
            S3 key of uploaded file

        Raises
        ------
        HTTPException
            If upload fails
        """
        try:
            async with self._session.client(
                "s3",
                endpoint_url=self.endpoint,
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            ) as s3:
                await s3.put_object(
                    Bucket=self.bucket,
                    Key=s3_key,
                    Body=file_data,
                    ContentType=mime_type,
                )
                return s3_key
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchBucket":
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "Storage configuration error: bucket not found",
                ) from e
            elif error_code == "AccessDenied":
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "Storage access denied",
                ) from e
            else:
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    f"Storage error: {error_code}",
                ) from e

    async def download_file(self, s3_key: str) -> bytes:
        """Download file from S3.

        Parameters
        ----------
        s3_key : str
            S3 object key

        Returns
        -------
        bytes
            File content

        Raises
        ------
        HTTPException
            If download fails or file not found
        """
        try:
            async with self._session.client(
                "s3",
                endpoint_url=self.endpoint,
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            ) as s3:
                response = await s3.get_object(Bucket=self.bucket, Key=s3_key)
                async with response["Body"] as stream:
                    return await stream.read()
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchKey":
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    f"File not found: {s3_key}",
                ) from e
            else:
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    f"Storage error: {error_code}",
                ) from e

    async def delete_file(self, s3_key: str) -> bool:
        """Delete file from S3.

        Parameters
        ----------
        s3_key : str
            S3 object key

        Returns
        -------
        bool
            True if deleted successfully

        Raises
        ------
        HTTPException
            If deletion fails
        """
        try:
            async with self._session.client(
                "s3",
                endpoint_url=self.endpoint,
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            ) as s3:
                await s3.delete_object(Bucket=self.bucket, Key=s3_key)
                return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Storage error during deletion: {error_code}",
            ) from e

    async def generate_presigned_url(
        self,
        s3_key: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate presigned URL for file download.

        Parameters
        ----------
        s3_key : str
            S3 object key
        expires_in : int
            URL expiration in seconds (default 1 hour)

        Returns
        -------
        str
            Presigned URL

        Raises
        ------
        HTTPException
            If URL generation fails
        """
        try:
            async with self._session.client(
                "s3",
                endpoint_url=self.endpoint,
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            ) as s3:
                url = await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": s3_key},
                    ExpiresIn=expires_in,
                )
                return url
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Failed to generate presigned URL: {error_code}",
            ) from e

    def build_s3_key(
        self,
        tenant_id: uuid.UUID,
        prescription_id: uuid.UUID,
        extension: str,
    ) -> str:
        """Build S3 key for prescription document.

        Parameters
        ----------
        tenant_id : UUID
            Tenant ID for multi-tenant isolation
        prescription_id : UUID
            Prescription ID
        extension : str
            File extension (e.g., "pdf", "jpg")

        Returns
        -------
        str
            S3 key path

        Examples
        --------
        >>> build_s3_key(tenant_id, prescription_id, "pdf")
        '550e8400-e29b-41d4-a716-446655440000/prescriptions/123e4567-e89b/ordonnance.pdf'
        """
        return f"{tenant_id}/prescriptions/{prescription_id}/ordonnance.{extension}"
