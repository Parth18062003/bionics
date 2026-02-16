"""
AADAP — Knowledge Graph Tests
================================
Tests for node/edge management and deprecated node exclusion.
"""

from __future__ import annotations

import pytest

from aadap.memory.knowledge_graph import KnowledgeEdge, KnowledgeGraph, KnowledgeNode


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def graph():
    return KnowledgeGraph()


def _make_node(label: str = "test-node", entity_type: str = "concept") -> KnowledgeNode:
    return KnowledgeNode(label=label, entity_type=entity_type)


# ── Add / Get Node ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_and_get_node(graph):
    """Add a node and retrieve it by ID."""
    node = _make_node("pipeline-pattern")
    node_id = await graph.add_node(node)
    retrieved = await graph.get_node(node_id)
    assert retrieved is not None
    assert retrieved.label == "pipeline-pattern"


@pytest.mark.asyncio
async def test_get_nonexistent_returns_none(graph):
    """get_node returns None for unknown IDs."""
    assert await graph.get_node("nonexistent") is None


@pytest.mark.asyncio
async def test_add_node_empty_label_raises(graph):
    """add_node raises ValueError on empty label."""
    node = _make_node(label="")
    with pytest.raises(ValueError, match="label"):
        await graph.add_node(node)


@pytest.mark.asyncio
async def test_add_node_empty_entity_type_raises(graph):
    """add_node raises ValueError on empty entity_type."""
    node = _make_node(entity_type="")
    with pytest.raises(ValueError, match="entity_type"):
        await graph.add_node(node)


# ── Deprecate Node ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_deprecate_excludes_from_get(graph):
    """Deprecated nodes are not returned by get_node."""
    node = _make_node()
    node_id = await graph.add_node(node)
    await graph.deprecate_node(node_id)
    assert await graph.get_node(node_id) is None


@pytest.mark.asyncio
async def test_deprecate_excludes_from_search(graph):
    """Deprecated nodes are not returned by search_nodes."""
    node = _make_node("searchable")
    await graph.add_node(node)
    await graph.deprecate_node(node.id)
    results = await graph.search_nodes("searchable")
    assert len(results) == 0


@pytest.mark.asyncio
async def test_deprecate_nonexistent_raises(graph):
    """deprecate_node raises KeyError for unknown node."""
    with pytest.raises(KeyError):
        await graph.deprecate_node("nonexistent")


# ── Search Nodes ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_by_label(graph):
    """search_nodes finds nodes by label substring match."""
    await graph.add_node(_make_node("data-pipeline"))
    await graph.add_node(_make_node("data-warehouse"))
    await graph.add_node(_make_node("ml-model"))

    results = await graph.search_nodes("data")
    assert len(results) == 2


@pytest.mark.asyncio
async def test_search_case_insensitive(graph):
    """search_nodes is case insensitive."""
    await graph.add_node(_make_node("DataPipeline"))
    results = await graph.search_nodes("datapipeline")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_search_with_entity_type_filter(graph):
    """search_nodes filters by entity_type when provided."""
    await graph.add_node(_make_node("pipeline-A", entity_type="etl"))
    await graph.add_node(_make_node("pipeline-B", entity_type="streaming"))

    results = await graph.search_nodes("pipeline", entity_type="etl")
    assert len(results) == 1
    assert results[0].entity_type == "etl"


# ── Edges ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_edge(graph):
    """Add an edge between two nodes."""
    n1 = _make_node("source")
    n2 = _make_node("target")
    await graph.add_node(n1)
    await graph.add_node(n2)

    edge = KnowledgeEdge(source_id=n1.id, target_id=n2.id, relation_type="depends_on")
    edge_id = await graph.add_edge(edge)
    assert edge_id == edge.id


@pytest.mark.asyncio
async def test_add_edge_missing_source_raises(graph):
    """add_edge raises KeyError when source node doesn't exist."""
    n2 = _make_node("target")
    await graph.add_node(n2)
    edge = KnowledgeEdge(source_id="nonexistent", target_id=n2.id, relation_type="uses")
    with pytest.raises(KeyError, match="Source"):
        await graph.add_edge(edge)


@pytest.mark.asyncio
async def test_add_edge_missing_target_raises(graph):
    """add_edge raises KeyError when target node doesn't exist."""
    n1 = _make_node("source")
    await graph.add_node(n1)
    edge = KnowledgeEdge(source_id=n1.id, target_id="nonexistent", relation_type="uses")
    with pytest.raises(KeyError, match="Target"):
        await graph.add_edge(edge)


@pytest.mark.asyncio
async def test_add_edge_deprecated_source_raises(graph):
    """add_edge raises ValueError when source node is deprecated."""
    n1 = _make_node("source")
    n2 = _make_node("target")
    await graph.add_node(n1)
    await graph.add_node(n2)
    await graph.deprecate_node(n1.id)

    edge = KnowledgeEdge(source_id=n1.id, target_id=n2.id, relation_type="uses")
    with pytest.raises(ValueError, match="deprecated"):
        await graph.add_edge(edge)


@pytest.mark.asyncio
async def test_add_edge_empty_relation_raises(graph):
    """add_edge raises ValueError on empty relation_type."""
    n1 = _make_node("source")
    n2 = _make_node("target")
    await graph.add_node(n1)
    await graph.add_node(n2)
    edge = KnowledgeEdge(source_id=n1.id, target_id=n2.id, relation_type="")
    with pytest.raises(ValueError, match="relation_type"):
        await graph.add_edge(edge)


# ── Get Neighbors ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_neighbors(graph):
    """get_neighbors returns target nodes of outgoing edges."""
    n1 = _make_node("source")
    n2 = _make_node("target-a")
    n3 = _make_node("target-b")
    await graph.add_node(n1)
    await graph.add_node(n2)
    await graph.add_node(n3)

    await graph.add_edge(KnowledgeEdge(source_id=n1.id, target_id=n2.id, relation_type="uses"))
    await graph.add_edge(KnowledgeEdge(source_id=n1.id, target_id=n3.id, relation_type="uses"))

    neighbors = await graph.get_neighbors(n1.id)
    assert len(neighbors) == 2


@pytest.mark.asyncio
async def test_get_neighbors_excludes_deprecated(graph):
    """get_neighbors excludes deprecated target nodes."""
    n1 = _make_node("source")
    n2 = _make_node("target")
    await graph.add_node(n1)
    await graph.add_node(n2)
    await graph.add_edge(KnowledgeEdge(source_id=n1.id, target_id=n2.id, relation_type="uses"))

    await graph.deprecate_node(n2.id)
    neighbors = await graph.get_neighbors(n1.id)
    assert len(neighbors) == 0


@pytest.mark.asyncio
async def test_get_neighbors_with_relation_filter(graph):
    """get_neighbors filters by relation_type when provided."""
    n1 = _make_node("source")
    n2 = _make_node("dep")
    n3 = _make_node("product")
    await graph.add_node(n1)
    await graph.add_node(n2)
    await graph.add_node(n3)

    await graph.add_edge(KnowledgeEdge(source_id=n1.id, target_id=n2.id, relation_type="depends_on"))
    await graph.add_edge(KnowledgeEdge(source_id=n1.id, target_id=n3.id, relation_type="produces"))

    neighbors = await graph.get_neighbors(n1.id, relation_type="depends_on")
    assert len(neighbors) == 1


@pytest.mark.asyncio
async def test_get_neighbors_nonexistent_raises(graph):
    """get_neighbors raises KeyError for unknown node."""
    with pytest.raises(KeyError):
        await graph.get_neighbors("nonexistent")
