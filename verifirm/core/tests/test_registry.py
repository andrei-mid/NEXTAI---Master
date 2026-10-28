import pytest

from verifirm.core import registry


def test_duplicate_agent_name_is_rejected() -> None:
    try:

        @registry.register_agent("__test_dup")
        class A:
            pass

        with pytest.raises(registry.RegistryError):

            @registry.register_agent("__test_dup")
            class B:
                pass

    finally:
        # The registry is global: a leftover fake agent would be run by the orchestrator in
        # every later test of the same session.
        registry._agents.pop("__test_dup", None)


def test_discovery_finds_all_eight_agents() -> None:
    agents = registry.discover_agents()
    expected = {
        "identity",
        "financials",
        "tax",
        "litigation",
        "network",
        "sanctions",
        "media",
        "presence",
    }
    assert expected <= set(agents)


def test_discovery_finds_adapters() -> None:
    adapters = registry.discover_adapters()
    assert {"anaf_v9", "anaf_bilant", "onrc_bulk", "portal_just"} <= set(adapters)
