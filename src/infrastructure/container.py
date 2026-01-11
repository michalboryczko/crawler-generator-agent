"""Dependency injection container for the crawler agent.

This module provides a simple DI container that creates and manages
repository and service instances based on configuration.
"""

import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy.orm import sessionmaker

from ..repositories.base import AbstractMemoryRepository
from ..repositories.context_repository import AbstractContextRepository, InMemoryContextRepository
from ..repositories.inmemory import InMemoryRepository
from ..services.context_service import ContextService
from ..services.memory_service import MemoryService
from ..services.session_service import SessionService

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as DBSession

    from ..core.config import StorageConfig

logger = logging.getLogger(__name__)


@dataclass
class Container:
    """Dependency injection container.

    Manages the lifecycle of repositories and creates service instances
    for agents. Each agent gets its own MemoryService with isolated context.

    Usage:
        # Initialize from config at app startup
        container = Container.from_config(storage_config)

        # Create service for each agent
        main_service = container.memory_service("main_agent")
        discovery_service = container.memory_service("discovery_agent")

        # Access session service for tracking crawler runs
        session_service = container.session_service

        # Create context service for agent with persistence
        context_svc = container.context_service("main_agent")

    Attributes:
        repository: The shared memory repository instance
        session_id: The session ID for this workflow run
        session_service: Service for managing Session lifecycle
    """

    repository: AbstractMemoryRepository
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    _db_session_factory: "sessionmaker[DBSession] | None" = field(default=None, repr=False)
    _context_repository: AbstractContextRepository | None = field(default=None, repr=False)
    _services: dict[str, MemoryService] = field(default_factory=dict, repr=False)
    _context_services: dict[str, ContextService] = field(default_factory=dict, repr=False)
    _session_service: SessionService | None = field(default=None, repr=False)

    def memory_service(self, agent_name: str) -> MemoryService:
        """Get or create a MemoryService for an agent.

        Services are cached by agent name to ensure the same instance
        is returned for repeated calls with the same agent name.

        Args:
            agent_name: The name of the agent

        Returns:
            A MemoryService instance for the agent
        """
        if agent_name not in self._services:
            self._services[agent_name] = MemoryService(
                repository=self.repository,
                session_id=self.session_id,
                agent_name=agent_name,
            )
        return self._services[agent_name]

    def context_service(
        self,
        agent_name: str,
        instance_id: str | None = None,
        parent_instance_id: str | None = None,
    ) -> ContextService:
        """Get or create a ContextService for an agent.

        If no instance_id provided, creates a new AgentInstance.
        Services are cached by instance_id.

        Args:
            agent_name: The name of the agent
            instance_id: Optional existing instance ID (for resume)
            parent_instance_id: Optional parent instance ID (for sub-agents)

        Returns:
            A ContextService instance for the agent

        Raises:
            RuntimeError: If context persistence is not enabled
        """
        if self._context_repository is None:
            raise RuntimeError(
                "Context persistence not enabled. Set ENABLE_CONTEXT_PERSISTENCE=true"
            )

        # Generate or use provided instance_id
        if instance_id is None:
            instance = self._context_repository.create_instance(
                session_id=self.session_id,
                agent_name=agent_name,
                parent_id=parent_instance_id,
            )
            instance_id = str(instance.id)
            logger.debug(f"Created new agent instance: {instance_id} for {agent_name}")

        if instance_id not in self._context_services:
            self._context_services[instance_id] = ContextService(
                repository=self._context_repository,
                session_id=self.session_id,
                instance_id=instance_id,
            )

        return self._context_services[instance_id]

    @property
    def context_persistence_enabled(self) -> bool:
        """Check if context persistence is enabled.

        Returns:
            True if context persistence is available
        """
        return self._context_repository is not None

    @property
    def context_repository(self) -> AbstractContextRepository | None:
        """Get the context repository if available.

        Returns:
            The context repository or None if not enabled
        """
        return self._context_repository

    def clear_services(self) -> None:
        """Clear all cached service instances."""
        self._services.clear()
        self._context_services.clear()

    @property
    def session_service(self) -> SessionService:
        """Get the session service for managing crawler sessions.

        Returns:
            SessionService instance (persists to DB if configured, no-op otherwise)
        """
        if self._session_service is None:
            self._session_service = SessionService(self._db_session_factory)
        return self._session_service

    @classmethod
    def from_config(
        cls,
        config: "StorageConfig",
        session_id: str | None = None,
    ) -> "Container":
        """Create container from storage configuration.

        Args:
            config: Storage configuration (backend type, connection string)
            session_id: Optional session ID (generated if not provided)

        Returns:
            A configured Container instance
        """
        session_id = session_id or str(uuid.uuid4())
        db_session_factory = None
        context_repository: AbstractContextRepository | None = None
        repository: AbstractMemoryRepository

        # Check if context persistence is enabled
        enable_context = os.environ.get("ENABLE_CONTEXT_PERSISTENCE", "false").lower() == "true"

        if config.backend_type == "memory":
            repository = InMemoryRepository()
            if enable_context:
                context_repository = InMemoryContextRepository()
                logger.info("Context persistence enabled (in-memory)")
        elif config.backend_type == "sqlalchemy":
            if not config.database_url:
                raise ValueError("DATABASE_URL required when STORAGE_BACKEND=sqlalchemy")
            from ..repositories.sqlalchemy import SQLAlchemyRepository

            repository = SQLAlchemyRepository(
                connection_string=config.database_url,
            )
            # Get the session factory for SessionService
            db_session_factory = repository._session_factory

            if enable_context:
                from ..repositories.context_repository import SQLAlchemyContextRepository

                context_repository = SQLAlchemyContextRepository(db_session_factory)
                logger.info("Context persistence enabled (SQLAlchemy)")
        else:
            raise ValueError(f"Unknown backend type: {config.backend_type}")

        if enable_context and context_repository is None:
            logger.warning(
                "ENABLE_CONTEXT_PERSISTENCE=true but context repository could not be created"
            )

        return cls(
            repository=repository,
            session_id=session_id,
            _db_session_factory=db_session_factory,
            _context_repository=context_repository,
        )

    @classmethod
    def create_inmemory(
        cls,
        session_id: str | None = None,
        enable_context_persistence: bool = False,
    ) -> "Container":
        """Create a container with in-memory storage.

        Convenience method for testing and development.

        Args:
            session_id: Optional session ID
            enable_context_persistence: Whether to enable context persistence

        Returns:
            A Container with InMemoryRepository
        """
        context_repository = InMemoryContextRepository() if enable_context_persistence else None

        return cls(
            repository=InMemoryRepository(),
            session_id=session_id or str(uuid.uuid4()),
            _context_repository=context_repository,
        )


# Global container instance
_container: Container | None = None


def get_container() -> Container:
    """Get the global container instance.

    Raises:
        RuntimeError: If container has not been initialized

    Returns:
        The global Container instance
    """
    if _container is None:
        raise RuntimeError("Container not initialized. Call init_container() first.")
    return _container


def init_container(
    config: "StorageConfig | None" = None,
    session_id: str | None = None,
) -> Container:
    """Initialize the global container.

    Args:
        config: Storage configuration (uses in-memory if None)
        session_id: Optional session ID

    Returns:
        The initialized Container instance
    """
    global _container

    if config is None:
        _container = Container.create_inmemory(session_id)
    else:
        _container = Container.from_config(config, session_id)

    return _container


def reset_container() -> None:
    """Reset the global container (for testing)."""
    global _container
    _container = None
