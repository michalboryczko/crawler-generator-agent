"""Infrastructure layer - dependency injection and cross-cutting concerns."""

from .container import Container, get_container, init_container

__all__ = ["Container", "get_container", "init_container"]
