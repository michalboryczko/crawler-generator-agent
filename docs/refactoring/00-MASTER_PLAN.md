# Refactoring Master Plan

## Overview

This document provides a comprehensive refactoring plan for the crawler-agent codebase. The plan is organized into multiple areas, each with its own detailed document.

## Current State Summary

- **Architecture**: Well-structured with clear separation (agents, tools, core, observability)
- **Code Quality**: Some duplication and typing issues identified
- **Testing**: Limited coverage (json_parser, observability modules only)
- **CI/CD**: No GitHub Actions configured yet
- **Static Analysis**: Ruff configured with basic rules

## Plan Documents

| Document | Area | Priority | Effort |
|----------|------|----------|--------|
| [01-ARCHITECTURE.md](01-ARCHITECTURE.md) | High-level architecture issues | High | Medium |
| [02-CODE_DUPLICATION.md](02-CODE_DUPLICATION.md) | Code duplication analysis | High | Low |
| [03-CODE_SMELLS.md](03-CODE_SMELLS.md) | Code-level improvements | Medium | Medium |
| [04-STATIC_ANALYSIS.md](04-STATIC_ANALYSIS.md) | Linters and static checks | Medium | Low |
| [05-TEST_COVERAGE.md](05-TEST_COVERAGE.md) | Test coverage plan | Medium | Medium |
| [06-CI_ACTIONS.md](06-CI_ACTIONS.md) | GitHub CI workflows | High | Low |

## Existing Plans

The existing `REFACTORING_PLAN.md` contains detailed implementation code for:

**[../REFACTORING_PLAN.md](../REFACTORING_PLAN.md)** - Detailed implementation plans:
- **Task 1**: JSON parsing duplication (4 identical methods) - with exact code changes
- **Task 2**: MemoryStore singleton fix - with two solution options
- **Task 3**: Orchestration tool factory - with complete implementation
- **Task 4**: Main function decomposition - with fully refactored code
- **Task 5**: System prompts extraction - with two approaches

**Relationship to this plan**: The documents in this `refactoring/` subdirectory provide a broader analysis and additional concerns (static analysis, testing, CI) while `REFACTORING_PLAN.md` provides ready-to-implement code for the core refactoring tasks.

## Recommended Execution Order

### Phase 1: Foundation
1. Set up CI/CD (06-CI_ACTIONS.md)
2. Enhance static analysis rules (04-STATIC_ANALYSIS.md)
3. Fix JSON parsing duplication (REFACTORING_PLAN.md Task 1)

### Phase 2: Core Refactoring
4. Fix MemoryStore singleton (REFACTORING_PLAN.md Task 2)
5. Refactor orchestration tools (REFACTORING_PLAN.md Task 3)
6. Decompose main function (REFACTORING_PLAN.md Task 4)

### Phase 3: Quality
7. Add type annotations (03-CODE_SMELLS.md)
8. Add key tests (05-TEST_COVERAGE.md)

### Phase 4: Polish
9. Extract system prompts (REFACTORING_PLAN.md Task 5)
10. Address remaining architecture improvements (01-ARCHITECTURE.md)

## Quick Wins

These items provide immediate value with minimal effort:

1. **Replace duplicated `_parse_json_response`** - Use existing `src/core/json_parser.py`
2. **Add CI workflow** - Basic test + lint pipeline
3. **Enable more Ruff rules** - Add typing, docstring, and security checks
4. **Add `__init__` type annotations** - Low effort, high readability improvement

## Dependencies

```
CI/CD setup
    └── Static analysis enhanced
            └── Code duplication fixed
                    └── Tests added
                            └── Architecture improvements
```

## Success Metrics

- [ ] All tests pass in CI
- [ ] Ruff reports 0 errors
- [ ] No duplicated JSON parsing code
- [ ] Key components have test coverage
- [ ] Type annotations on public APIs
