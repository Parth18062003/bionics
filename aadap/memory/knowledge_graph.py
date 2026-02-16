"""
AADAP — Knowledge Graph
=========================
PostgreSQL-backed Tier 4 knowledge graph using graph tables pattern.

Stores nodes (entities) and edges (relationships) with deprecation support.
Deprecated nodes are excluded from all query results.

Usage:
    from aadap.memory.knowledge_graph import KnowledgeGraph, KnowledgeNode, KnowledgeEdge

    graph = KnowledgeGraph()
    node_id = await graph.add_node(node)
    await graph.add_edge(edge)
    neighbors = await graph.get_neighbors(node_id)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ── Data Classes ────────────────────────────────────────────────────────

@dataclass
class KnowledgeNode:
    """A node in the knowledge graph."""

    label: str
    entity_type: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    properties: dict[str, Any] = field(default_factory=dict)
    is_deprecated: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class KnowledgeEdge:
    """A directed edge between two knowledge nodes."""

    source_id: str
    target_id: str
    relation_type: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    weight: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Knowledge Graph ─────────────────────────────────────────────────────

class KnowledgeGraph:
    """
    In-memory knowledge graph implementing the PostgreSQL graph table contract.

    Production deployment uses PostgreSQL graph tables.  This implementation
    provides the full contract for Phase 6 validation and unit testing.

    Invariant: deprecated nodes are excluded from all query results.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, KnowledgeNode] = {}
        self._edges: dict[str, KnowledgeEdge] = {}

    # ── Nodes ───────────────────────────────────────────────────────────

    async def add_node(self, node: KnowledgeNode) -> str:
        """Add a node to the graph.  Returns the node ID."""
        if not node.label or not node.label.strip():
            raise ValueError("Node label must not be empty.")
        if not node.entity_type or not node.entity_type.strip():
            raise ValueError("Node entity_type must not be empty.")
        self._nodes[node.id] = node
        return node.id

    async def get_node(self, node_id: str) -> KnowledgeNode | None:
        """Get a node by ID.  Returns None if not found or deprecated."""
        node = self._nodes.get(node_id)
        if node is None or node.is_deprecated:
            return None
        return node

    async def deprecate_node(self, node_id: str) -> None:
        """
        Mark a node as deprecated.

        Deprecated nodes are excluded from all queries (search, get_neighbors).
        """
        node = self._nodes.get(node_id)
        if node is None:
            raise KeyError(f"Node {node_id} not found.")
        node.is_deprecated = True

    async def search_nodes(
        self,
        label: str,
        entity_type: str | None = None,
    ) -> list[KnowledgeNode]:
        """
        Search nodes by label (case-insensitive substring match).

        Deprecated nodes are excluded.
        """
        label_lower = label.lower()
        results: list[KnowledgeNode] = []
        for node in self._nodes.values():
            if node.is_deprecated:
                continue
            if label_lower in node.label.lower():
                if entity_type is None or node.entity_type == entity_type:
                    results.append(node)
        return results

    # ── Edges ───────────────────────────────────────────────────────────

    async def add_edge(self, edge: KnowledgeEdge) -> str:
        """
        Add an edge between two nodes.

        Both source and target nodes must exist and not be deprecated.
        """
        source = self._nodes.get(edge.source_id)
        if source is None:
            raise KeyError(f"Source node {edge.source_id} not found.")
        if source.is_deprecated:
            raise ValueError(f"Source node {edge.source_id} is deprecated.")

        target = self._nodes.get(edge.target_id)
        if target is None:
            raise KeyError(f"Target node {edge.target_id} not found.")
        if target.is_deprecated:
            raise ValueError(f"Target node {edge.target_id} is deprecated.")

        if not edge.relation_type or not edge.relation_type.strip():
            raise ValueError("Edge relation_type must not be empty.")

        self._edges[edge.id] = edge
        return edge.id

    async def get_neighbors(
        self,
        node_id: str,
        relation_type: str | None = None,
    ) -> list[KnowledgeNode]:
        """
        Get all non-deprecated neighbors of a node (outgoing edges).

        Args:
            node_id: Source node ID.
            relation_type: Optional filter by edge relation type.

        Returns:
            List of non-deprecated target nodes.
        """
        node = self._nodes.get(node_id)
        if node is None:
            raise KeyError(f"Node {node_id} not found.")

        neighbors: list[KnowledgeNode] = []
        for edge in self._edges.values():
            if edge.source_id != node_id:
                continue
            if relation_type is not None and edge.relation_type != relation_type:
                continue
            target = self._nodes.get(edge.target_id)
            if target is not None and not target.is_deprecated:
                neighbors.append(target)
        return neighbors

    async def get_edges(
        self,
        node_id: str,
        direction: str = "outgoing",
    ) -> list[KnowledgeEdge]:
        """
        Get all edges for a node.

        Args:
            node_id: Node ID.
            direction: 'outgoing', 'incoming', or 'both'.
        """
        edges: list[KnowledgeEdge] = []
        for edge in self._edges.values():
            if direction in ("outgoing", "both") and edge.source_id == node_id:
                edges.append(edge)
            elif direction in ("incoming", "both") and edge.target_id == node_id:
                edges.append(edge)
        return edges
