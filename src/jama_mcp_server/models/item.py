"""JAMA Item/Requirement Data Model

Pydantic models for JAMA items (requirements, specifications, etc.)
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class ItemLocation(BaseModel):
    """Location of an item within a project hierarchy."""

    parent: Optional[int] = Field(
        default=None,
        description="Parent item ID for hierarchical placement"
    )
    sortOrder: Optional[int] = Field(
        default=None,
        description="Position among siblings"
    )


class ItemFields(BaseModel):
    """Custom and standard fields for an item.

    Fields vary by project and item type. This model allows dynamic field handling.
    """

    name: str = Field(description="Item name/title (required)")
    description: Optional[str] = Field(default=None, description="Item description")

    # Allow arbitrary custom fields
    class Config:
        extra = "allow"


class Item(BaseModel):
    """JAMA Connect item (requirement, specification, test case, etc.)."""

    id: Optional[int] = Field(default=None, description="Unique item ID (read-only)")
    documentKey: Optional[str] = Field(
        default=None,
        description="Human-readable key (e.g., REQ-123)"
    )
    globalId: Optional[str] = Field(default=None, description="Global UUID")
    project: int = Field(description="Project ID containing this item")
    itemType: int = Field(description="Item type ID (e.g., requirement, spec)")
    location: Optional[ItemLocation] = Field(
        default=None,
        description="Hierarchical location"
    )
    fields: ItemFields = Field(description="Item fields (name, description, custom)")

    createdDate: Optional[datetime] = Field(
        default=None,
        description="Creation timestamp (read-only)"
    )
    modifiedDate: Optional[datetime] = Field(
        default=None,
        description="Last modification timestamp (read-only)"
    )
    lastActivityDate: Optional[datetime] = Field(
        default=None,
        description="Last activity timestamp (read-only)"
    )

    createdBy: Optional[int] = Field(default=None, description="Creator user ID")
    modifiedBy: Optional[int] = Field(default=None, description="Last modifier user ID")

    currentVersion: Optional[int] = Field(
        default=None,
        description="Current version number (read-only)"
    )
    locked: Optional[bool] = Field(
        default=False,
        description="Whether item is locked for editing"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "project": 123,
                "itemType": 45,
                "location": {"parent": 100},
                "fields": {
                    "name": "User Authentication Requirement",
                    "description": "System shall support OAuth 2.0 authentication"
                }
            }
        }


class ItemCreate(BaseModel):
    """Data required to create a new JAMA item."""

    project: int = Field(description="Project ID")
    itemType: int = Field(description="Item type ID")
    location: ItemLocation = Field(description="Hierarchical location")
    fields: ItemFields = Field(description="Item fields (name required, description optional)")

    class Config:
        json_schema_extra = {
            "example": {
                "project": 123,
                "itemType": 45,
                "location": {"parent": 100},
                "fields": {
                    "name": "New Requirement",
                    "description": "Requirement description"
                }
            }
        }


class ItemUpdate(BaseModel):
    """Data for updating an existing JAMA item.

    Supports both PATCH (partial update) and PUT (full replacement) semantics.
    """

    fields: Optional[ItemFields] = Field(
        default=None,
        description="Fields to update"
    )
    location: Optional[ItemLocation] = Field(
        default=None,
        description="New location in hierarchy"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "fields": {
                    "description": "Updated requirement description"
                }
            }
        }
