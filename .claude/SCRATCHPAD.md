# Scratchpad: Complex Reasoning & Debugging

## Architecture Decisions

### Decision 1: llm.py Merge Strategy
**Problem**: Need to merge LLMClientFactory from feature/logging while preserving @traced_llm_client decorator from feature/logging-refactor.

**Options**:
A. Extract only LLMClientFactory class and add to existing file
B. Copy entire file and re-add observability decorators

**Decision**: Option A - Extract and merge. This is safer because:
1. Less risk of losing observability code
2. More surgical approach
3. Can verify decorator preservation line by line

### Decision 2: Agent Factory Support
**Problem**: Step 7 is marked optional - should we implement it?

**Decision**: YES, implement it. Reasons:
1. Without it, --multi-model flag is incomplete
2. Base agent is the foundation - if factory doesn't integrate here, it's useless
3. Low complexity to add Union type support

---

## Current Blockers
(None yet)

---

## Debug Notes
(Space for debugging complex issues)
