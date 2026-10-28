"""Plug-in registration. No central lists: adding an agent or adapter never edits the orchestrator.

    @register_agent("identity")
    class IdentityAgent(BaseAgent): ...

    @register_adapter("anaf_v9")
    class AnafV9Adapter(BaseAdapter): ...

The orchestrator calls `discover_agents()` / `discover_adapters()`, which import every module
in the package so the decorators run, then reads the registry.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T", bound=type[Any])

AGENTS_PACKAGE = "verifirm.agents"
ADAPTERS_PACKAGE = "verifirm.adapters"

_agents: dict[str, type[Any]] = {}
_adapters: dict[str, type[Any]] = {}


class RegistryError(RuntimeError):
    pass


def _register(table: dict[str, type[Any]], kind: str, name: str) -> Callable[[T], T]:
    def decorator(cls: T) -> T:
        existing = table.get(name)
        if existing is not None and existing is not cls:
            raise RegistryError(f"{kind} {name!r} already registered by {existing.__module__}")
        table[name] = cls
        cls.name = name
        return cls

    return decorator


def register_agent(name: str) -> Callable[[T], T]:
    return _register(_agents, "agent", name)


def register_adapter(name: str) -> Callable[[T], T]:
    return _register(_adapters, "adapter", name)


def import_all(package_name: str) -> list[str]:
    """Import every module under `package_name` (recursively). Returns imported module names.

    Folders without __init__.py (e.g. tests/, prompts/) are not packages and are skipped.
    """
    package = importlib.import_module(package_name)
    imported = []
    for info in pkgutil.walk_packages(package.__path__, prefix=f"{package_name}."):
        importlib.import_module(info.name)
        imported.append(info.name)
    return imported


def discover_agents(package_name: str = AGENTS_PACKAGE) -> dict[str, type[Any]]:
    import_all(package_name)
    return dict(_agents)


def discover_adapters(package_name: str = ADAPTERS_PACKAGE) -> dict[str, type[Any]]:
    import_all(package_name)
    return dict(_adapters)


def registered_agents() -> dict[str, type[Any]]:
    return dict(_agents)


def registered_adapters() -> dict[str, type[Any]]:
    return dict(_adapters)


def get_adapter_class(name: str) -> type[Any]:
    try:
        return _adapters[name]
    except KeyError:
        raise RegistryError(
            f"no adapter registered as {name!r}; did you call discover_adapters()?"
        ) from None
