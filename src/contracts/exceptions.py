"""Contract system exceptions."""


class ContractValidationError(Exception):
    """Raised when agent output fails schema validation."""

    def __init__(self, message: str, errors: list[dict] | None = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []


class SchemaLoadError(Exception):
    """Raised when schema file cannot be loaded."""

    def __init__(self, schema_path: str, reason: str):
        super().__init__(f"Failed to load schema '{schema_path}': {reason}")
        self.schema_path = schema_path
        self.reason = reason
