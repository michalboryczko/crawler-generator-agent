# GitHub CI Actions Plan

## Overview

Set up continuous integration to run tests and static analysis on every push and pull request.

## Workflow Files

### 1. Main CI Workflow

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main, develop, feature/*]
  pull_request:
    branches: [main, develop]

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.11

      - name: Install dependencies
        run: uv sync --dev

      - name: Run Ruff linter
        run: uv run ruff check .

      - name: Run Ruff formatter check
        run: uv run ruff format --check .

  test:
    name: Test
    runs-on: ubuntu-latest
    needs: lint  # Only run tests if lint passes
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.11

      - name: Install dependencies
        run: uv sync --dev

      - name: Run tests
        run: uv run pytest -v --tb=short

      - name: Run tests with coverage
        run: uv run pytest --cov=src --cov-report=xml

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage.xml
          fail_ci_if_error: false  # Don't fail if codecov is unavailable
        continue-on-error: true

  type-check:
    name: Type Check
    runs-on: ubuntu-latest
    needs: lint
    # Optional: Enable when mypy is configured
    if: false  # Set to true when ready
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.11

      - name: Install dependencies
        run: uv sync --dev

      - name: Run mypy
        run: uv run mypy src/
```

### 2. Dependency Security Check (Optional)

Create `.github/workflows/security.yml`:

```yaml
name: Security

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday

jobs:
  dependency-audit:
    name: Dependency Audit
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.11

      - name: Install dependencies
        run: uv sync --dev

      - name: Check for vulnerabilities
        run: uv run pip-audit
        continue-on-error: true  # Don't fail the build yet
```

---

## Required Dev Dependencies

Update `pyproject.toml` to add CI-required tools:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",      # ADD: Coverage reporting
    "ruff>=0.1.0",
    # Optional: Add when ready
    # "mypy>=1.8.0",
    # "pip-audit>=2.7.0",
]
```

---

## Directory Structure

```
.github/
└── workflows/
    ├── ci.yml              # Main CI workflow
    └── security.yml        # Optional security checks
```

---

## Implementation Steps

### Step 1: Create GitHub Workflows Directory

```bash
mkdir -p .github/workflows
```

### Step 2: Create CI Workflow

Copy the `ci.yml` content above to `.github/workflows/ci.yml`.

### Step 3: Update Dependencies

Add `pytest-cov` to dev dependencies:

```bash
uv add --dev pytest-cov
```

### Step 4: Test Locally

Before pushing, verify workflows work locally:

```bash
# Run linting
uv run ruff check .
uv run ruff format --check .

# Run tests
uv run pytest -v

# Run tests with coverage
uv run pytest --cov=src
```

### Step 5: Push and Verify

1. Commit and push changes
2. Go to GitHub repository → Actions tab
3. Verify workflow runs successfully

---

## Branch Protection Rules (Recommended)

After CI is working, configure branch protection:

1. Go to Repository → Settings → Branches
2. Add rule for `main` branch:
   - Require status checks to pass before merging
   - Select required checks: `Lint`, `Test`
   - Require branches to be up to date before merging

---

## Badge for README

Add CI status badge to `README.md`:

```markdown
![CI](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/ci.yml/badge.svg)
```

---

## Future Enhancements

### Phase 2: Enhanced Testing
```yaml
# Add to ci.yml
  test-matrix:
    name: Test (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12', '3.13']
    steps:
      # ... same as test job but with matrix.python-version
```

### Phase 3: Release Automation
```yaml
# .github/workflows/release.yml
name: Release
on:
  push:
    tags:
      - 'v*'
jobs:
  # Build and publish to PyPI
```

### Phase 4: Integration Tests
```yaml
# .github/workflows/integration.yml
name: Integration Tests
on:
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM
jobs:
  # Run longer integration tests
```

---

## Estimated CI Run Time

| Job | Duration | Runs On |
|-----|----------|---------|
| Lint | ~30 seconds | Every push |
| Test | ~1-2 minutes | Every push |
| Type Check | ~30 seconds | When enabled |
| Security | ~1 minute | Weekly/on main |

**Total per PR: ~2-3 minutes**
