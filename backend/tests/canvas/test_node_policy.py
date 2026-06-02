"""H1: registry-derived type sets are the single source of truth.

Lock the classification so adding/moving a node type can't silently drift the
sets the guards depend on.
"""
from agent.node import (
    registry,
    EMBEDDED_TYPES,
    AI_CREATABLE_TYPES,
    PERMANENT_TYPES,
    MANAGED_TYPES,
)


def test_embedded_types():
    assert EMBEDDED_TYPES == {"insights", "goals", "automations", "mech"}


def test_ai_creatable_types():
    assert AI_CREATABLE_TYPES == {"files", "logs", "usage", "workspace"}


def test_permanent_types():
    assert PERMANENT_TYPES == {"input", "memory", "config"}


def test_managed_types():
    # managed = not embedded, not ai_creatable → only internal bootstrap may create
    assert MANAGED_TYPES == {"input", "session", "memory", "config"}


def test_sets_partition_the_registry():
    # every type is either embedded or ai_creatable or managed, with no overlap
    assert EMBEDDED_TYPES | AI_CREATABLE_TYPES | MANAGED_TYPES == set(registry)
    assert EMBEDDED_TYPES & AI_CREATABLE_TYPES == set()
    assert EMBEDDED_TYPES & MANAGED_TYPES == set()
    assert AI_CREATABLE_TYPES & MANAGED_TYPES == set()


def test_permanent_is_subset_of_managed():
    # permanent (singleton core) types are managed, but session is managed yet not permanent
    assert PERMANENT_TYPES < MANAGED_TYPES
    assert "session" in MANAGED_TYPES and "session" not in PERMANENT_TYPES
