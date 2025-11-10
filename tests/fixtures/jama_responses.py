"""Mock JAMA API Response Data

Realistic mock responses for testing JAMA MCP tools.
Based on JAMA Connect REST API v1.0 response formats.
"""

from datetime import datetime
from typing import Dict, List, Any


# Project responses

MOCK_PROJECT_1 = {
    "id": 123,
    "projectKey": "PROJ",
    "name": "Test Project",
    "description": "A test project for unit tests",
    "isFolder": False,
    "createdDate": "2024-01-01T00:00:00.000Z",
    "modifiedDate": "2024-01-15T10:30:00.000Z",
    "createdBy": 1,
    "modifiedBy": 1
}

MOCK_PROJECT_2 = {
    "id": 456,
    "projectKey": "DEMO",
    "name": "Demo Project",
    "description": "Demo project for testing",
    "isFolder": False,
    "createdDate": "2024-02-01T00:00:00.000Z",
    "modifiedDate": "2024-02-10T14:20:00.000Z",
    "createdBy": 2,
    "modifiedBy": 2
}

MOCK_PROJECTS_LIST = {
    "meta": {
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "pageInfo": {
            "startIndex": 0,
            "resultCount": 2,
            "totalResults": 2
        }
    },
    "data": [MOCK_PROJECT_1, MOCK_PROJECT_2]
}


# Item responses

MOCK_ITEM_1 = {
    "id": 100,
    "documentKey": "PROJ-REQ-001",
    "globalId": "GID-100",
    "project": 123,
    "itemType": 45,
    "location": {
        "parent": None,
        "sortOrder": 1
    },
    "fields": {
        "name": "User Authentication Requirement",
        "description": "System shall support OAuth 2.0 authentication for users",
        "status": "Approved",
        "priority": "High"
    },
    "createdDate": "2024-01-05T10:00:00.000Z",
    "modifiedDate": "2024-01-10T15:30:00.000Z",
    "lastActivityDate": "2024-01-10T15:30:00.000Z",
    "createdBy": 1,
    "modifiedBy": 1,
    "currentVersion": 2,
    "locked": False
}

MOCK_ITEM_2 = {
    "id": 200,
    "documentKey": "PROJ-REQ-002",
    "globalId": "GID-200",
    "project": 123,
    "itemType": 45,
    "location": {
        "parent": 100,
        "sortOrder": 1
    },
    "fields": {
        "name": "Login Screen Design",
        "description": "Design mockup for OAuth login screen",
        "status": "Draft",
        "priority": "Medium"
    },
    "createdDate": "2024-01-06T11:00:00.000Z",
    "modifiedDate": "2024-01-08T09:15:00.000Z",
    "lastActivityDate": "2024-01-08T09:15:00.000Z",
    "createdBy": 2,
    "modifiedBy": 2,
    "currentVersion": 1,
    "locked": False
}

MOCK_ITEMS_LIST = {
    "meta": {
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "pageInfo": {
            "startIndex": 0,
            "resultCount": 2,
            "totalResults": 2
        }
    },
    "data": [MOCK_ITEM_1, MOCK_ITEM_2]
}


# Relationship responses

MOCK_RELATIONSHIP_1 = {
    "id": 12345,
    "fromItem": 100,
    "toItem": 200,
    "relationshipType": 5,
    "suspect": False,
    "createdDate": "2024-01-07T12:00:00.000Z",
    "modifiedDate": "2024-01-07T12:00:00.000Z",
    "createdBy": 1,
    "modifiedBy": 1
}

MOCK_RELATIONSHIP_TYPE = {
    "id": 5,
    "name": "implements",
    "forwardName": "implements",
    "reverseName": "implemented by"
}

MOCK_RELATIONSHIPS_LIST = {
    "meta": {
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "pageInfo": {
            "startIndex": 0,
            "resultCount": 1,
            "totalResults": 1
        }
    },
    "data": [MOCK_RELATIONSHIP_1]
}


# Attachment responses

MOCK_ATTACHMENT_1 = {
    "id": 789,
    "fileName": "architecture-diagram.pdf",
    "mimeType": "application/pdf",
    "fileSize": 1024000,
    "item": 100,
    "createdDate": "2024-01-09T13:00:00.000Z",
    "modifiedDate": "2024-01-09T13:00:00.000Z",
    "createdBy": 1,
    "modifiedBy": 1
}

MOCK_ATTACHMENTS_LIST = {
    "meta": {
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "pageInfo": {
            "startIndex": 0,
            "resultCount": 1,
            "totalResults": 1
        }
    },
    "data": [MOCK_ATTACHMENT_1]
}


# Item Type responses

MOCK_ITEM_TYPE_REQUIREMENT = {
    "id": 45,
    "name": "Requirement",
    "display": "Requirement",
    "category": "DEFAULT",
    "typeKey": "requirement",
    "image": "requirement.png"
}

MOCK_ITEM_TYPE_TEST_CASE = {
    "id": 50,
    "name": "Test Case",
    "display": "Test Case",
    "category": "TEST",
    "typeKey": "test_case",
    "image": "test_case.png"
}

MOCK_ITEM_TYPES_LIST = {
    "meta": {
        "status": "OK",
        "timestamp": datetime.now().isoformat()
    },
    "data": [MOCK_ITEM_TYPE_REQUIREMENT, MOCK_ITEM_TYPE_TEST_CASE]
}


# Baseline responses

MOCK_BASELINE_1 = {
    "id": 999,
    "name": "Release 1.0 Baseline",
    "description": "Baseline for Release 1.0",
    "project": 123,
    "createdDate": "2024-01-20T10:00:00.000Z",
    "createdBy": 1
}

MOCK_BASELINES_LIST = {
    "meta": {
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "pageInfo": {
            "startIndex": 0,
            "resultCount": 1,
            "totalResults": 1
        }
    },
    "data": [MOCK_BASELINE_1]
}


# Error responses

MOCK_ERROR_401 = {
    "meta": {
        "status": "Unauthorized",
        "timestamp": datetime.now().isoformat(),
        "message": "Authentication credentials are invalid or missing"
    }
}

MOCK_ERROR_403 = {
    "meta": {
        "status": "Forbidden",
        "timestamp": datetime.now().isoformat(),
        "message": "User does not have permission to access this resource"
    }
}

MOCK_ERROR_404 = {
    "meta": {
        "status": "Not Found",
        "timestamp": datetime.now().isoformat(),
        "message": "The requested resource was not found"
    }
}

MOCK_ERROR_409 = {
    "meta": {
        "status": "Conflict",
        "timestamp": datetime.now().isoformat(),
        "message": "Version conflict: item has been modified by another user"
    }
}

MOCK_ERROR_429 = {
    "meta": {
        "status": "Too Many Requests",
        "timestamp": datetime.now().isoformat(),
        "message": "Rate limit exceeded. Please retry after some time."
    }
}


# Test data helpers

def create_mock_item(
    item_id: int,
    name: str,
    project_id: int = 123,
    item_type_id: int = 45,
    **field_overrides
) -> Dict[str, Any]:
    """Create a mock item with custom fields.

    Args:
        item_id: Item ID
        name: Item name
        project_id: Project ID
        item_type_id: Item type ID
        **field_overrides: Additional fields to add/override

    Returns:
        Mock item dictionary
    """
    fields = {
        "name": name,
        "description": f"Description for {name}",
        "status": "Draft",
        "priority": "Medium"
    }
    fields.update(field_overrides)

    return {
        "id": item_id,
        "documentKey": f"ITEM-{item_id}",
        "globalId": f"GID-{item_id}",
        "project": project_id,
        "itemType": item_type_id,
        "location": {"parent": None, "sortOrder": 1},
        "fields": fields,
        "createdDate": datetime.now().isoformat(),
        "modifiedDate": datetime.now().isoformat(),
        "lastActivityDate": datetime.now().isoformat(),
        "createdBy": 1,
        "modifiedBy": 1,
        "currentVersion": 1,
        "locked": False
    }


def create_mock_relationship(
    from_item: int,
    to_item: int,
    relationship_type: int = 5,
    suspect: bool = False
) -> Dict[str, Any]:
    """Create a mock relationship.

    Args:
        from_item: Source item ID
        to_item: Target item ID
        relationship_type: Relationship type ID
        suspect: Whether relationship is suspect

    Returns:
        Mock relationship dictionary
    """
    return {
        "id": from_item * 1000 + to_item,  # Generate unique ID
        "fromItem": from_item,
        "toItem": to_item,
        "relationshipType": relationship_type,
        "suspect": suspect,
        "createdDate": datetime.now().isoformat(),
        "modifiedDate": datetime.now().isoformat(),
        "createdBy": 1,
        "modifiedBy": 1
    }
