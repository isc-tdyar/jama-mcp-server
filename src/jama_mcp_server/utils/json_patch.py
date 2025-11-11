"""JSON Patch Utilities

Utilities for converting field dictionaries to JSON Patch operations (RFC 6902).
Used by jama_update_item to transform MCP tool parameters into the format expected
by py-jama-rest-client's patch_item() method.
"""

from typing import Dict, List, Any


def fields_to_json_patch(fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert a fields dictionary to JSON Patch operations.

    Args:
        fields: Dictionary mapping field names to values.
            Example: {"name": "New Name", "description": "<p>New desc</p>"}

    Returns:
        List of JSON Patch operations in RFC 6902 format.
        Example: [
            {"op": "replace", "path": "/fields/name", "value": "New Name"},
            {"op": "replace", "path": "/fields/description", "value": "<p>New desc</p>"}
        ]

    Raises:
        ValueError: If fields dict is empty
    """
    if not fields:
        raise ValueError("At least one field must be provided for update")

    patches = []
    for field_name, field_value in fields.items():
        patches.append({
            "op": "add",  # Use 'add' - works for both new and existing fields
            "path": f"/fields/{field_name}",
            "value": field_value
        })

    return patches


def validate_json_patch(patches: List[Dict[str, Any]]) -> bool:
    """Validate JSON Patch operations structure.

    Args:
        patches: List of JSON Patch operations to validate

    Returns:
        True if valid

    Raises:
        ValueError: If any operation is invalid
    """
    if not isinstance(patches, list):
        raise ValueError("Patches must be a list")

    if not patches:
        raise ValueError("Patches list cannot be empty")

    required_ops = {"replace", "add", "remove", "copy", "move", "test"}

    for i, patch in enumerate(patches):
        if not isinstance(patch, dict):
            raise ValueError(f"Patch {i} must be a dictionary")

        if "op" not in patch:
            raise ValueError(f"Patch {i} missing required 'op' field")

        if patch["op"] not in required_ops:
            raise ValueError(f"Patch {i} has invalid op '{patch['op']}', must be one of {required_ops}")

        if "path" not in patch:
            raise ValueError(f"Patch {i} missing required 'path' field")

        if not patch["path"].startswith("/"):
            raise ValueError(f"Patch {i} path must start with '/' (JSON Pointer format)")

        # 'value' is required for all ops except 'remove'
        if patch["op"] != "remove" and "value" not in patch:
            raise ValueError(f"Patch {i} with op='{patch['op']}' missing required 'value' field")

    return True
