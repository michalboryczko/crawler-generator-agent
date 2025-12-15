# Static Analysis Tools and Linters

## Current State

Ruff is already configured in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
```

Currently enabled rules:
- **E**: pycodestyle errors
- **F**: Pyflakes (unused imports, undefined names)
- **I**: isort (import sorting)
- **N**: pep8-naming
- **W**: pycodestyle warnings

## Recommended Configuration

### Phase 1: Enhanced Ruff Configuration

Update `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
exclude = [
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
]

[tool.ruff.lint]
select = [
    # Current rules
    "E",      # pycodestyle errors
    "F",      # Pyflakes
    "I",      # isort
    "N",      # pep8-naming
    "W",      # pycodestyle warnings
    # New rules - Phase 1
    "UP",     # pyupgrade (modern Python syntax)
    "B",      # flake8-bugbear (common bugs)
    "SIM",    # flake8-simplify (simplifications)
    "RUF",    # Ruff-specific rules
]

ignore = [
    "E501",   # Line too long (handled by formatter)
]

[tool.ruff.lint.isort]
known-first-party = ["src"]
force-single-line = false
combine-as-imports = true

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101"]  # Allow assert in tests
"__init__.py" = ["F401"]  # Allow unused imports in __init__
```

### Phase 2: Add Type Checking Rules

After fixing existing code:

```toml
[tool.ruff.lint]
select = [
    # ... previous rules ...
    # Phase 2
    "ANN",    # flake8-annotations (type hints)
    "TCH",    # flake8-type-checking
]

[tool.ruff.lint.flake8-annotations]
allow-star-arg-any = true
suppress-none-returning = true
```

### Phase 3: Add Security and Documentation Rules

```toml
[tool.ruff.lint]
select = [
    # ... previous rules ...
    # Phase 3
    "S",      # flake8-bandit (security)
    "D",      # pydocstyle (docstrings)
    "C4",     # flake8-comprehensions
    "PTH",    # flake8-use-pathlib
]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.flake8-bandit]
hardcoded-tmp-directory = ["/tmp", "/var/tmp"]
```

---

## Type Checking with Mypy

Add mypy for static type checking:

### Installation

```bash
uv add --dev mypy types-requests
```

### Configuration

Add to `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = false  # Start permissive
check_untyped_defs = true
ignore_missing_imports = true

# Gradually enable strict mode per module
[[tool.mypy.overrides]]
module = "src.core.*"
disallow_untyped_defs = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

---

## Pre-commit Hooks

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies:
          - types-requests
        args: [--ignore-missing-imports]
```

### Installation

```bash
uv add --dev pre-commit
pre-commit install
```

---

## Implementation Plan

### Step 1: Update Ruff Configuration
1. Update `pyproject.toml` with Phase 1 rules
2. Run `ruff check --fix .` to auto-fix issues
3. Manually fix remaining issues
4. Commit changes

### Step 2: Add Mypy (Optional)
1. Add mypy to dev dependencies
2. Add mypy configuration
3. Run `mypy src/` and fix critical issues
4. Enable stricter rules gradually

### Step 3: Set Up Pre-commit
1. Create `.pre-commit-config.yaml`
2. Install pre-commit hooks
3. Run on all files: `pre-commit run --all-files`

### Step 4: CI Integration
See [06-CI_ACTIONS.md](06-CI_ACTIONS.md) for GitHub Actions setup.

---

## Commands Reference

```bash
# Run Ruff linter
ruff check .

# Run Ruff with auto-fix
ruff check --fix .

# Format code with Ruff
ruff format .

# Run mypy type checking
mypy src/

# Run all pre-commit hooks
pre-commit run --all-files
```

---

## Expected Results

After implementing these changes:

| Tool | Current Issues | Expected Issues |
|------|---------------|-----------------|
| Ruff | Unknown | 0 |
| Mypy | Not configured | 0 (gradual) |
| Pre-commit | Not configured | All hooks pass |
