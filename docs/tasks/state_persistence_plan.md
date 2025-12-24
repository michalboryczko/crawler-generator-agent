# Session State Persistence - Implementation Plan

## Overview

This plan implements event sourcing for agent context persistence, allowing session replay from any point.

## Requirements Summary

1. Each agent instance has unique UUID stored in DB with relation to session
2. Store all messages (system/user/assistant) with timestamps
3. Store all tool_calls and tool_execution results
4. Enable session replay from specific points
5. CLI commands: `--copy`, `--overwrite`, `--resume`

## Architecture Design

### Event Sourcing Model

Each interaction with an agent is stored as an immutable event. The agent context (messages list) is reconstructed by replaying events in sequence.

```
Session (1) ──── (N) AgentInstance (1) ──── (N) AgentContextEvent
```

### Event Types

| Type | Description | Content Structure |
|------|-------------|-------------------|
| `system_message` | Initial system prompt | `{role, content}` |
| `user_message` | User/task input | `{role, content}` |
| `assistant_message` | LLM response | `{role, content, tool_calls?}` |
| `tool_call` | Tool invocation | `{id, name, arguments}` |
| `tool_result` | Tool execution result | `{tool_call_id, content}` |

## Database Schema

### AgentInstance Table

```sql
CREATE TABLE agent_instances (
    id VARCHAR(64) PRIMARY KEY,  -- UUID
    session_id VARCHAR(64) NOT NULL REFERENCES sessions(id),
    agent_name VARCHAR(64) NOT NULL,
    parent_instance_id VARCHAR(64) REFERENCES agent_instances(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    INDEX idx_instance_session (session_id),
    INDEX idx_instance_parent (parent_instance_id)
);
```

### AgentContextEvent Table

```sql
CREATE TABLE agent_context_events (
    id SERIAL PRIMARY KEY,
    instance_id VARCHAR(64) NOT NULL REFERENCES agent_instances(id),
    sequence_number INTEGER NOT NULL,
    event_type VARCHAR(32) NOT NULL,  -- system_message, user_message, assistant_message, tool_call, tool_result
    content JSON NOT NULL,
    tool_call_id VARCHAR(64),  -- For tool_result events
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    INDEX idx_event_instance (instance_id),
    INDEX idx_event_sequence (instance_id, sequence_number),
    UNIQUE (instance_id, sequence_number)
);
```

## Implementation Phases

### Phase 1: Database Models

**Files to create:**
- `src/models/agent_instance.py` - AgentInstance SQLAlchemy model
- `src/models/context_event.py` - AgentContextEvent SQLAlchemy model

**Update:**
- `src/models/__init__.py` - Export new models

### Phase 2: Repository Layer

**Files to create:**
- `src/repositories/context_repository.py` - Abstract + SQLAlchemy implementation

**Interface:**
```python
class AbstractContextRepository(ABC):
    def create_instance(session_id, agent_name, parent_id=None) -> AgentInstance
    def get_instance(instance_id) -> AgentInstance | None
    def append_event(instance_id, event_type, content, tool_call_id=None) -> AgentContextEvent
    def get_events(instance_id, from_sequence=0) -> list[AgentContextEvent]
    def delete_events_after(instance_id, sequence_number) -> int
    def copy_events(source_instance_id, target_instance_id, up_to_sequence=None) -> int
```

### Phase 3: Context Service

**Files to create:**
- `src/services/context_service.py` - ContextService class

**API:**
```python
class ContextService:
    def __init__(repository, instance_id)

    # Message operations (wraps the messages list)
    def append_message(role, content, tool_calls=None, tool_call_id=None)
    def get_messages() -> list[dict]

    # Replay operations
    def replay_from_sequence(seq_num) -> list[dict]
    def get_last_sequence() -> int

    # Session management
    def copy_to_new_instance(target_instance_id, up_to_sequence=None)
    def truncate_after_sequence(sequence_number)
```

### Phase 4: Agent Integration

**Files to modify:**
- `src/agents/base.py` - Accept ContextService, use for message storage

**Changes:**
1. Add `context_service` parameter to `__init__`
2. Replace `messages: list` with `context_service.get_messages()`
3. Wrap all message appends with `context_service.append_message()`
4. Store tool calls and results as events

### Phase 5: Container Integration

**Files to modify:**
- `src/infrastructure/container.py` - Add context_service factory method

**Changes:**
1. Add `AbstractContextRepository` to container
2. Add `context_service(agent_name, instance_id=None)` method
3. Auto-create AgentInstance when not resuming

### Phase 6: CLI Commands

**Files to modify:**
- `main.py` - Add CLI arguments and handlers

**New arguments:**
```
--resume SESSION_ID           Resume from last point of existing session
--copy SOURCE_SESSION_ID      Copy session to new session
  --to-point SEQUENCE         Optional: copy only up to this sequence number
--overwrite SESSION_ID        Continue existing session
  --from-point SEQUENCE       Optional: delete events after this point first
```

### Phase 7: Alembic Migration

**Files to create:**
- `alembic/versions/xxx_add_context_events.py`

## File Structure After Implementation

```
src/
├── models/
│   ├── __init__.py          (updated)
│   ├── agent_instance.py    (new)
│   ├── context_event.py     (new)
│   ├── memory.py
│   ├── session.py
│   └── base.py
├── repositories/
│   ├── __init__.py          (updated)
│   ├── context_repository.py (new)
│   ├── base.py
│   ├── inmemory.py
│   └── sqlalchemy.py
├── services/
│   ├── __init__.py          (updated)
│   ├── context_service.py   (new)
│   ├── memory_service.py
│   └── session_service.py
├── agents/
│   └── base.py              (modified)
└── infrastructure/
    └── container.py         (modified)
```

## Testing Strategy

1. **Unit Tests:**
   - ContextRepository: CRUD operations, event ordering
   - ContextService: Message append/replay, truncation

2. **Integration Tests:**
   - Full agent run with context persistence
   - Session resume with correct state
   - Copy and overwrite operations

## Rollback Plan

- All changes are additive (new tables, new columns)
- BaseAgent can fall back to in-memory mode if no ContextService provided
- Feature flag via environment variable: `ENABLE_CONTEXT_PERSISTENCE=true`

## Success Criteria

1. Agent runs persist all messages to database
2. `--resume` correctly continues from last state
3. `--copy` creates new session with copied state
4. `--overwrite` truncates and continues
5. No performance regression for normal operations
