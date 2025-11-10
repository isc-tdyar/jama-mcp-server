"""JAMA Relationship Data Model

Pydantic models for JAMA relationships (traceability links between items)
"""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Relationship(BaseModel):
    """JAMA Connect relationship (traceability link between items)."""

    id: Optional[int] = Field(default=None, description="Unique relationship ID (read-only)")
    fromItem: int = Field(description="Source item ID")
    toItem: int = Field(description="Target item ID")
    relationshipType: int = Field(description="Relationship type ID")

    suspect: Optional[bool] = Field(
        default=False,
        description="Whether relationship is suspect (out of sync)"
    )

    createdDate: Optional[datetime] = Field(
        default=None,
        description="Creation timestamp (read-only)"
    )
    modifiedDate: Optional[datetime] = Field(
        default=None,
        description="Last modification timestamp (read-only)"
    )

    createdBy: Optional[int] = Field(default=None, description="Creator user ID")
    modifiedBy: Optional[int] = Field(default=None, description="Last modifier user ID")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 12345,
                "fromItem": 100,
                "toItem": 200,
                "relationshipType": 5,
                "suspect": False
            }
        }


class RelationshipCreate(BaseModel):
    """Data required to create a new JAMA relationship."""

    fromItem: int = Field(description="Source item ID")
    toItem: int = Field(description="Target item ID")
    relationshipType: int = Field(description="Relationship type ID")

    class Config:
        json_schema_extra = {
            "example": {
                "fromItem": 100,
                "toItem": 200,
                "relationshipType": 5
            }
        }


class RelationshipType(BaseModel):
    """JAMA relationship type definition."""

    id: Optional[int] = Field(default=None, description="Unique type ID")
    name: str = Field(description="Type name (e.g., 'implements', 'verifies')")
    forwardName: Optional[str] = Field(
        default=None,
        description="Forward direction label"
    )
    reverseName: Optional[str] = Field(
        default=None,
        description="Reverse direction label"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": 5,
                "name": "implements",
                "forwardName": "implements",
                "reverseName": "implemented by"
            }
        }
