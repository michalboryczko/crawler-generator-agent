# Scratchpad - Complex Reasoning & Debugging

## Architecture Decisions

### Memory Tool Design
- Simple in-memory dict for MVP
- Keys: string identifiers
- Values: any JSON-serializable data
- Operations: read(key), write(key, value), search(pattern), list_keys()

### Agent Communication Pattern
- Direct function calls between agents (simpler for MVP)
- Shared memory for state passing
- Browser session passed as dependency injection

### Chrome DevTools MCP
- Need to figure out connection method
- Session must persist across agent calls
- Will investigate MCP protocol

---

## Current Problem Solving

(Empty - will be used during implementation)

---

## Debug Log

(Empty - will be used for troubleshooting)
