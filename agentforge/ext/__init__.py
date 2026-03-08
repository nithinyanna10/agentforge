from __future__ import annotations

import importlib.metadata
from typing import TYPE_CHECKING, Any, Callable

from agentforge.tools.base import Tool
from agentforge.utils.logging import get_logger

if TYPE_CHECKING:
    from agentforge.core.agent import Agent, AgentConfig
    from agentforge.llm.base import BaseLLMProvider

logger = get_logger(__name__)

# Global registries (module-level singletons)
_tool_registry: list[type[Tool]] = []
_agent_factories: dict[str, Callable[..., Agent]] = {}
ENTRY_POINT_GROUP = "agentforge.tools"


def register_tool(tool_class: type[Tool]) -> type[Tool]:
    """Register a tool class (not instance). Idempotent by class name."""
    name = getattr(tool_class, "name", None)
    if name is None:
        try:
            inst = tool_class.__new__(tool_class)
            name = getattr(inst, "name", tool_class.__name__)
        except Exception:
            name = tool_class.__name__
    existing = {getattr(c, "name", c.__name__): c for c in _tool_registry}
    if name not in existing:
        _tool_registry.append(tool_class)
        logger.debug("Registered tool class %s", name)
    return tool_class


def register_agent_factory(name: str, factory: Callable[..., Any]) -> None:
    """Register a callable that returns an Agent (e.g. for templates)."""
    _agent_factories[name] = factory
    logger.debug("Registered agent factory %r", name)


def get_registered_tools() -> list[type[Tool]]:
    """Return all registered tool classes (built-in + extensions)."""
    return list(_tool_registry)


def get_agent_factory(name: str) -> Callable[..., Any] | None:
    """Return the agent factory for *name* if registered."""
    return _agent_factories.get(name)


def list_agent_factories() -> list[str]:
    """Return names of all registered agent factories."""
    return list(_agent_factories.keys())


def discover_plugins() -> int:
    """Discover tools from entry point group ``agentforge.tools`` and register them. Returns count added."""
    count = 0
    try:
        for ep in importlib.metadata.entry_points(group=ENTRY_POINT_GROUP):
            try:
                tool_class = ep.load()
                if isinstance(tool_class, type) and issubclass(tool_class, Tool):
                    register_tool(tool_class)
                    count += 1
            except Exception as e:
                logger.warning("Failed to load plugin %s: %s", ep.name, e)
    except Exception as e:
        logger.debug("Entry point discovery skipped: %s", e)
    return count


def clear_registries() -> None:
    """Clear tool and agent factory registries (mainly for tests)."""
    global _tool_registry, _agent_factories
    _tool_registry.clear()
    _agent_factories.clear()
