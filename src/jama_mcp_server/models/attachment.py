"""JAMA Attachment Data Model

Pydantic models for JAMA attachments (files attached to items)
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class Attachment(BaseModel):
    """JAMA Connect attachment (file attached to an item)."""

    id: Optional[int] = Field(default=None, description="Unique attachment ID (read-only)")
    fileName: str = Field(description="Original file name")
    mimeType: Optional[str] = Field(default=None, description="MIME type of file")
    fileSize: Optional[int] = Field(default=None, description="File size in bytes")

    item: Optional[int] = Field(
        default=None,
        description="Item ID this attachment is associated with"
    )

    createdDate: Optional[datetime] = Field(
        default=None,
        description="Upload timestamp (read-only)"
    )
    modifiedDate: Optional[datetime] = Field(
        default=None,
        description="Last modification timestamp (read-only)"
    )

    createdBy: Optional[int] = Field(default=None, description="Uploader user ID")
    modifiedBy: Optional[int] = Field(default=None, description="Last modifier user ID")

    @field_validator('fileSize')
    @classmethod
    def validate_file_size(cls, v: Optional[int]) -> Optional[int]:
        """Validate file size is within JAMA limits (50MB)."""
        if v is not None and v > 50 * 1024 * 1024:  # 50MB in bytes
            raise ValueError(f"File size {v} bytes exceeds maximum of 50MB")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "id": 789,
                "fileName": "architecture-diagram.pdf",
                "mimeType": "application/pdf",
                "fileSize": 1024000,
                "item": 123
            }
        }


class AttachmentCreate(BaseModel):
    """Data required to create a new JAMA attachment.

    JAMA uses a 3-step upload process:
    1. Create attachment item (this model)
    2. Upload file content (binary)
    3. Associate attachment with item
    """

    fileName: str = Field(description="File name with extension")
    mimeType: Optional[str] = Field(default=None, description="MIME type")

    @field_validator('fileName')
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename is not empty and has reasonable length."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Filename cannot be empty")
        if len(v) > 255:
            raise ValueError(f"Filename too long (max 255 characters): {v}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "fileName": "requirements-spec.docx",
                "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            }
        }


class AttachmentMetadata(BaseModel):
    """Attachment metadata without file content."""

    id: int = Field(description="Attachment ID")
    fileName: str = Field(description="File name")
    mimeType: Optional[str] = Field(default=None, description="MIME type")
    fileSize: Optional[int] = Field(default=None, description="Size in bytes")
    item: Optional[int] = Field(default=None, description="Associated item ID")
    createdDate: Optional[datetime] = Field(default=None, description="Upload date")
    createdBy: Optional[int] = Field(default=None, description="Uploader user ID")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 789,
                "fileName": "design-mockup.png",
                "mimeType": "image/png",
                "fileSize": 256000,
                "item": 456,
                "createdDate": "2024-01-15T10:30:00Z",
                "createdBy": 12
            }
        }
