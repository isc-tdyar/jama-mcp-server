"""Unit tests for JSON Patch utilities."""

import pytest
from jama_mcp_server.utils.json_patch import fields_to_json_patch, validate_json_patch


def test_fields_to_json_patch_single_field():
    """Test conversion of single field to JSON Patch."""
    fields = {"name": "Test Name"}
    patches = fields_to_json_patch(fields)

    assert len(patches) == 1
    assert patches[0] == {
        "op": "add",
        "path": "/fields/name",
        "value": "Test Name"
    }


def test_fields_to_json_patch_multiple_fields():
    """Test conversion of multiple fields to JSON Patch."""
    fields = {
        "name": "Updated Name",
        "description": "<p>Updated description</p>",
        "rationale$134": "<p>Updated rationale</p>",
        "workflow_status$134": 615
    }
    patches = fields_to_json_patch(fields)

    assert len(patches) == 4
    # Verify all fields are converted
    paths = {p["path"] for p in patches}
    assert "/fields/name" in paths
    assert "/fields/description" in paths
    assert "/fields/rationale$134" in paths
    assert "/fields/workflow_status$134" in paths

    # Verify all use 'add' operation
    assert all(p["op"] == "add" for p in patches)


def test_fields_to_json_patch_empty_fields():
    """Test that empty fields dict raises ValueError."""
    with pytest.raises(ValueError, match="At least one field must be provided"):
        fields_to_json_patch({})


def test_validate_json_patch_valid():
    """Test validation of valid JSON Patch operations."""
    patches = [
        {"op": "replace", "path": "/fields/name", "value": "Test"},
        {"op": "add", "path": "/fields/new_field", "value": "New"},
        {"op": "remove", "path": "/fields/old_field"}
    ]

    assert validate_json_patch(patches) is True


def test_validate_json_patch_invalid_not_list():
    """Test validation fails if patches is not a list."""
    with pytest.raises(ValueError, match="Patches must be a list"):
        validate_json_patch({"op": "replace"})


def test_validate_json_patch_empty_list():
    """Test validation fails if patches list is empty."""
    with pytest.raises(ValueError, match="Patches list cannot be empty"):
        validate_json_patch([])


def test_validate_json_patch_missing_op():
    """Test validation fails if operation missing 'op' field."""
    patches = [{"path": "/fields/name", "value": "Test"}]

    with pytest.raises(ValueError, match="missing required 'op' field"):
        validate_json_patch(patches)


def test_validate_json_patch_invalid_op():
    """Test validation fails for invalid operation type."""
    patches = [{"op": "invalid_op", "path": "/fields/name", "value": "Test"}]

    with pytest.raises(ValueError, match="has invalid op"):
        validate_json_patch(patches)


def test_validate_json_patch_missing_path():
    """Test validation fails if operation missing 'path' field."""
    patches = [{"op": "replace", "value": "Test"}]

    with pytest.raises(ValueError, match="missing required 'path' field"):
        validate_json_patch(patches)


def test_validate_json_patch_invalid_path_format():
    """Test validation fails if path doesn't start with '/'."""
    patches = [{"op": "replace", "path": "fields/name", "value": "Test"}]

    with pytest.raises(ValueError, match="path must start with '/'"):
        validate_json_patch(patches)


def test_validate_json_patch_missing_value():
    """Test validation fails if 'replace' operation missing 'value' field."""
    patches = [{"op": "replace", "path": "/fields/name"}]

    with pytest.raises(ValueError, match="missing required 'value' field"):
        validate_json_patch(patches)


def test_validate_json_patch_remove_no_value():
    """Test 'remove' operation doesn't require 'value' field."""
    patches = [{"op": "remove", "path": "/fields/name"}]

    assert validate_json_patch(patches) is True


def test_fields_to_json_patch_with_custom_fields():
    """Test conversion with JAMA custom fields (suffix with $itemTypeId)."""
    fields = {
        "name": "NEED Title",
        "description": "<p>NEED description</p>",
        "rationale$134": "<p>Justification for requirement</p>",
        "notable_customers_and_stakeholders$134": "<p>Customer feedback</p>",
        "workflow_status$134": 615,
        "priority$134": 1
    }
    patches = fields_to_json_patch(fields)

    assert len(patches) == 6

    # Verify custom field paths are correct
    custom_field_paths = [
        "/fields/rationale$134",
        "/fields/notable_customers_and_stakeholders$134",
        "/fields/workflow_status$134",
        "/fields/priority$134"
    ]

    generated_paths = {p["path"] for p in patches}
    for path in custom_field_paths:
        assert path in generated_paths


def test_fields_to_json_patch_preserves_value_types():
    """Test that field values of different types are preserved."""
    fields = {
        "name": "String Value",
        "priority": 1,  # int
        "enabled": True,  # bool
        "description": None,  # None
        "metadata": {"key": "value"}  # dict
    }
    patches = fields_to_json_patch(fields)

    # Find each patch and verify value type is preserved
    for patch in patches:
        field_name = patch["path"].split("/")[-1]
        assert patch["value"] == fields[field_name]
        assert type(patch["value"]) == type(fields[field_name])
