"""
AADAP — Task Routing Service
================================
Integrates deterministic keyword-based routing with LLM-based orchestration.

Architecture layer: L5 (Orchestration).

Routing Strategy:
1. Exact match from task metadata (capability explicitly specified) → use that
2. High-confidence keyword match (score >= 2) → use deterministic routing
3. Ambiguous cases → delegate to OrchestratorAgent (LLM-based)

This ensures deterministic behavior for clear cases while leveraging
LLM intelligence for ambiguous task descriptions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from aadap.agents.orchestrator_agent import KNOWN_AGENT_TYPES, classify_task_type
from aadap.core.logging import get_logger
from aadap.integrations.llm_client import BaseLLMClient

logger = get_logger(__name__)


# ── Capability Task Types ────────────────────────────────────────────────

CAPABILITY_TASK_TYPES: set[str] = {
    "ingestion",
    "etl_pipeline",
    "job_scheduler",
    "catalog",
}

# Keywords for deterministic routing
_TASK_TYPE_KEYWORDS: dict[str, list[str]] = {
    "ingestion": [
        "ingest", "autoloader", "auto loader", "copy activity",
        "streaming", "kafka", "event hub", "cdc",
    ],
    "etl_pipeline": [
        "etl", "elt", "pipeline", "dlt", "delta live",
        "data factory", "transformation", "medallion",
    ],
    "job_scheduler": [
        "schedule", "cron", "trigger", "dag", "workflow", "job",
    ],
    "catalog": [
        "catalog", "schema", "grant", "permission", "revoke",
        "unity catalog", "lakehouse", "governance", "ddl",
    ],
}

# Minimum score for high-confidence keyword match
HIGH_CONFIDENCE_THRESHOLD = 2


@dataclass(frozen=True)
class RoutingDecision:
    """Result of task routing."""

    agent_type: str
    confidence: float
    routing_method: str  # "explicit" | "keyword" | "llm"
    sub_tasks: list[dict[str, Any]] | None = None
    reasoning: str | None = None


class TaskRouter:
    """
    Routes tasks to appropriate agents using a tiered strategy.

    Tier 1: Explicit capability in metadata
    Tier 2: High-confidence keyword match
    Tier 3: LLM-based orchestration (OrchestratorAgent)
    """

    def __init__(
        self,
        llm_client: BaseLLMClient | None = None,
        use_llm_fallback: bool = True,
    ) -> None:
        """
        Initialize the task router.

        Parameters
        ----------
        llm_client
            LLM client for OrchestratorAgent. If None, LLM fallback is disabled.
        use_llm_fallback
            Whether to use LLM for ambiguous cases. Default True.
        """
        self._llm_client = llm_client
        self._use_llm_fallback = use_llm_fallback and llm_client is not None

    def route(
        self,
        task_id: uuid.UUID,
        title: str,
        description: str,
        metadata: dict[str, Any] | None = None,
        environment: str = "SANDBOX",
    ) -> RoutingDecision:
        """
        Route a task to the appropriate agent.

        Parameters
        ----------
        task_id
            Task identifier for logging.
        title
            Task title.
        description
            Task description.
        metadata
            Task metadata (may contain explicit capability).
        environment
            Execution environment.

        Returns
        -------
        RoutingDecision
            The routing decision with agent type and confidence.
        """
        metadata = metadata or {}

        # Tier 1: Explicit capability in metadata
        explicit = metadata.get("task_type") or metadata.get("capability")
        if isinstance(explicit, str):
            normalized = explicit.strip().lower()
            if normalized in KNOWN_AGENT_TYPES:
                logger.info(
                    "router.explicit_routing",
                    task_id=str(task_id),
                    agent_type=normalized,
                )
                return RoutingDecision(
                    agent_type=normalized,
                    confidence=1.0,
                    routing_method="explicit",
                    reasoning=f"Explicit capability: {explicit}",
                )

        # Tier 2: Deterministic keyword matching
        keyword_result = self._keyword_routing(title, description)
        if keyword_result:
            agent_type, score = keyword_result
            if score >= HIGH_CONFIDENCE_THRESHOLD:
                confidence = min(score / 5.0, 0.95)  # Cap at 0.95 for keyword
                logger.info(
                    "router.keyword_routing",
                    task_id=str(task_id),
                    agent_type=agent_type,
                    score=score,
                    confidence=confidence,
                )
                return RoutingDecision(
                    agent_type=agent_type,
                    confidence=confidence,
                    routing_method="keyword",
                    reasoning=f"Keyword match score: {score}",
                )

            # Low-confidence keyword match - try LLM if available
            if self._use_llm_fallback:
                llm_decision = self._llm_routing(
                    task_id, title, description, environment, agent_type
                )
                if llm_decision:
                    return llm_decision

            # No LLM, use keyword result with low confidence
            logger.info(
                "router.keyword_low_confidence",
                task_id=str(task_id),
                agent_type=agent_type,
                score=score,
            )
            return RoutingDecision(
                agent_type=agent_type,
                confidence=score / 5.0,
                routing_method="keyword",
                reasoning=f"Low-confidence keyword match (score: {score}), no LLM fallback",
            )

        # Tier 3: LLM-based routing for completely ambiguous cases
        if self._use_llm_fallback:
            llm_decision = self._llm_routing(
                task_id, title, description, environment, None
            )
            if llm_decision:
                return llm_decision

        # Default fallback to developer agent
        logger.info(
            "router.default_fallback",
            task_id=str(task_id),
            agent_type="developer",
        )
        return RoutingDecision(
            agent_type="developer",
            confidence=0.5,
            routing_method="fallback",
            reasoning="No keyword match, LLM not available or failed",
        )

    def _keyword_routing(
        self,
        title: str,
        description: str,
    ) -> tuple[str, int] | None:
        """
        Perform keyword-based routing.

        Returns (agent_type, score) or None if no match.
        """
        text = f"{title}\n{description}".lower()
        scores: dict[str, int] = {}

        for task_type, keywords in _TASK_TYPE_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score:
                scores[task_type] = score

        if not scores:
            # Check using the existing classify_task_type function
            result = classify_task_type(description)
            if result:
                return result, 1
            return None

        best_type = max(scores, key=scores.get)
        return best_type, scores[best_type]

    def _llm_routing(
        self,
        task_id: uuid.UUID,
        title: str,
        description: str,
        environment: str,
        hint: str | None,
    ) -> RoutingDecision | None:
        """
        Use OrchestratorAgent for LLM-based routing.

        Returns None if LLM routing fails or is disabled.
        """
        if not self._llm_client:
            return None

        try:
            # Import here to avoid circular dependency
            from aadap.agents.orchestrator_agent import OrchestratorAgent
            from aadap.agents.base import AgentContext
            import asyncio

            orchestrator = OrchestratorAgent(
                agent_id=f"router-{task_id.hex[:8]}",
                llm_client=self._llm_client,
            )

            task_data = {
                "title": title,
                "description": description,
                "environment": environment,
            }

            if hint:
                task_data["capability_hint"] = hint

            context = AgentContext(
                task_id=task_id,
                task_data=task_data,
            )

            # Run the orchestrator synchronously (it's async internally)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # We're in an async context, use create_task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._run_orchestrator(orchestrator, context)
                    )
                    result = future.result()
            else:
                result = asyncio.run(self._run_orchestrator(orchestrator, context))

            if result.success and result.output:
                agent_assignment = result.output.get("agent_assignment", "developer")
                if agent_assignment in KNOWN_AGENT_TYPES:
                    logger.info(
                        "router.llm_routing",
                        task_id=str(task_id),
                        agent_type=agent_assignment,
                    )
                    return RoutingDecision(
                        agent_type=agent_assignment,
                        confidence=0.85,
                        routing_method="llm",
                        sub_tasks=result.output.get("sub_tasks"),
                        reasoning=result.output.get("reasoning"),
                    )
        except Exception as exc:
            logger.warning(
                "router.llm_failed",
                task_id=str(task_id),
                error=str(exc),
            )

        return None

    async def _run_orchestrator(self, orchestrator, context):
        """Run orchestrator agent async."""
        await orchestrator.accept_task(context)
        return await orchestrator.execute(context)


# Module-level router instance
_ROUTER: TaskRouter | None = None


def get_task_router() -> TaskRouter:
    """Get or create the module-level router."""
    global _ROUTER
    if _ROUTER is None:
        from aadap.integrations.llm_client import AzureOpenAIClient
        try:
            llm = AzureOpenAIClient.from_settings()
            _ROUTER = TaskRouter(llm_client=llm, use_llm_fallback=True)
        except Exception:
            # LLM not configured, use keyword-only routing
            _ROUTER = TaskRouter(llm_client=None, use_llm_fallback=False)
    return _ROUTER


def route_task(
    task_id: uuid.UUID,
    title: str,
    description: str,
    metadata: dict[str, Any] | None = None,
    environment: str = "SANDBOX",
) -> RoutingDecision:
    """
    Convenience function for task routing.

    Uses the module-level router instance.
    """
    router = get_task_router()
    return router.route(task_id, title, description, metadata, environment)
