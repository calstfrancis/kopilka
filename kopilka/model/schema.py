"""JSON schema validation."""

# JSON schema for budget.json
BUDGET_SCHEMA = {
    "type": "object",
    "properties": {
        "version": {"type": "string"},
        "metadata": {
            "type": "object",
            "properties": {
                "couple": {"type": "array", "items": {"type": "string"}},
                "created": {"type": "string"},
                "last_modified": {"type": "string"},
                "last_modified_by": {"type": "string"},
            }
        },
        "config": {
            "type": "object",
            "properties": {
                "currency": {"type": "string"},
                "sync_path": {"type": "string"},
            }
        },
        "income": {"type": "array"},
        "expenses_fixed": {"type": "array"},
        "debt": {"type": "array"},
        "categories": {"type": "array"},
        "spending": {"type": "array"},
    },
    "required": ["version", "metadata", "config"],
}


def validate_budget(data: dict) -> bool:
    """Validate budget data structure."""
    # TODO: Implement validation using jsonschema
    return True
