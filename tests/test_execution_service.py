"""
AADAP — ExecutionService Tests (Phase 8)
========================================
Tests for Phase 8 enhancements:
- task type classification
- capability agent routing
- optimization phase state transitions
- handling of new artifact types
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from aadap.agents.catalog_agent import CatalogAgent
from aadap.agents.etl_pipeline_agent import ETLPipelineAgent
from aadap.agents.ingestion_agent import IngestionAgent
from aadap.agents.job_scheduler_agent import JobSchedulerAgent
from aadap.integrations.databricks_client import MockDatabricksClient
from aadap.integrations.fabric_client import MockFabricClient
from aadap.integrations.llm_client import MockLLMClient
from aadap.db.models import Task
from aadap.orchestrator.state_machine import TaskState
from aadap.safety.static_analysis import RiskLevel, RiskResult
from aadap.services.execution import ExecutionService


@pytest.fixture
def service() -> ExecutionService:
    return ExecutionService(
        llm_client=MockLLMClient(default_response="SELECT 1"),
        databricks_client=MockDatabricksClient(),
        fabric_client=MockFabricClient(),
    )


def _task(
    *,
    title: str,
    description: str,
    metadata_: dict | None = None,
    environment: str = "SANDBOX",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        title=title,
        description=description,
        environment=environment,
        metadata_=metadata_ or {},
        token_budget=50_000,
    )


class TestTaskClassification:
    def test_classify_explicit_task_type(self, service: ExecutionService):
        task = _task(
            title="x",
            description="y",
            metadata_={"task_type": "catalog"},
        )
        assert service._classify_task_type(cast(Task, task)) == "catalog"

    def test_classify_keyword_ingestion(self, service: ExecutionService):
        task = _task(
            title="Build pipeline",
            description="Ingest data from Kafka stream into bronze table",
        )
        assert service._classify_task_type(cast(Task, task)) == "ingestion"

    def test_classify_fallback_developer(self, service: ExecutionService):
        task = _task(title="General code",
                     description="Create helper function")
        assert service._classify_task_type(cast(Task, task)) == "developer"


class TestCapabilityAgentFactory:
    def test_get_capability_agent_ingestion(self, service: ExecutionService):
        agent = service._get_capability_agent(
            task_type="ingestion",
            platform="databricks",
            environment="SANDBOX",
        )
        assert isinstance(agent, IngestionAgent)

    def test_get_capability_agent_etl(self, service: ExecutionService):
        agent = service._get_capability_agent(
            task_type="etl_pipeline",
            platform="fabric",
            environment="SANDBOX",
        )
        assert isinstance(agent, ETLPipelineAgent)

    def test_get_capability_agent_scheduler(self, service: ExecutionService):
        agent = service._get_capability_agent(
            task_type="job_scheduler",
            platform="databricks",
            environment="SANDBOX",
        )
        assert isinstance(agent, JobSchedulerAgent)

    def test_get_capability_agent_catalog(self, service: ExecutionService):
        agent = service._get_capability_agent(
            task_type="catalog",
            platform="fabric",
            environment="SANDBOX",
        )
        assert isinstance(agent, CatalogAgent)

    def test_get_capability_agent_none_for_generic(self, service: ExecutionService):
        agent = service._get_capability_agent(
            task_type="developer",
            platform="databricks",
            environment="SANDBOX",
        )
        assert agent is None

    def test_capability_agents_receive_adapter_by_default(self, service: ExecutionService):
        agent = service._get_capability_agent(
            task_type="ingestion",
            platform="databricks",
            environment="SANDBOX",
        )
        assert agent is not None
        assert getattr(agent, "_platform_adapter", None) is not None

    def test_generate_only_mode_disables_adapter(self, service: ExecutionService):
        agent = service._get_capability_agent(
            task_type="ingestion",
            platform="databricks",
            environment="SANDBOX",
            generate_only=True,
        )
        assert agent is not None
        assert getattr(agent, "_platform_adapter", None) is None


class TestExecuteTaskPhase8:
    @pytest.mark.asyncio
    async def test_execute_task_includes_optimization_transitions(
        self,
        service: ExecutionService,
    ):
        task = _task(
            title="Create ETL",
            description="Create a PySpark ETL pipeline",
            metadata_={"language": "python", "platform": "databricks"},
        )

        transitions: list[tuple[TaskState, TaskState]] = []

        async def record_transition(task_id, from_state, to_state):
            transitions.append((from_state, to_state))

        service._load_task = AsyncMock(return_value=task)
        service._transition = AsyncMock(side_effect=record_transition)
        service._classify_task_type = MagicMock(return_value="developer")
        service._generate_code = AsyncMock(return_value="print('generated')")
        service._set_task_metadata = AsyncMock(return_value=None)
        service._persist_approval_request = AsyncMock(return_value=None)
        service._store_artifact = AsyncMock(return_value=uuid.uuid4())
        service._execute_on_databricks = AsyncMock(return_value={
            "status": "SUCCESS",
            "output": "ok",
            "error": None,
            "job_id": "job-1",
            "duration_ms": 123,
        })
        service._run_optimization_phase = AsyncMock(return_value=(
            "print('optimized')",
            {"applied": True, "platform": "databricks"},
        ))

        setattr(service, "_analyzer", SimpleNamespace(
            evaluate=lambda code, language="python": RiskResult(
                passed=True,
                risk_level=RiskLevel.LOW,
                findings=(),
                gate="static_analysis",
            ),
        ))

        result = await service.execute_task(task.id)

        assert result["status"] == "COMPLETED"
        assert (TaskState.VALIDATION_PASSED,
                TaskState.OPTIMIZATION_PENDING) in transitions
        assert (TaskState.OPTIMIZATION_PENDING,
                TaskState.IN_OPTIMIZATION) in transitions
        assert (TaskState.IN_OPTIMIZATION, TaskState.OPTIMIZED) in transitions

    @pytest.mark.asyncio
    async def test_execute_task_routes_to_capability_agent_and_persists_artifacts(
        self,
        service: ExecutionService,
    ):
        task = _task(
            title="Ingest events",
            description="Ingest data from Event Hub to bronze",
            metadata_={"language": "python", "platform": "fabric"},
        )

        service._load_task = AsyncMock(return_value=task)
        service._transition = AsyncMock(return_value=None)
        service._classify_task_type = MagicMock(return_value="ingestion")
        service._execute_capability_agent = AsyncMock(return_value=(
            "print('capability code')",
            [
                {"type": "pipeline_definition", "content": {"name": "ingest_pipe"}},
                {"type": "ingestion_config", "content": {"mode": "streaming"}},
            ],
        ))
        service._persist_capability_artifacts = AsyncMock(return_value=None)
        service._generate_code = AsyncMock(return_value="print('fallback')")
        service._set_task_metadata = AsyncMock(return_value=None)
        service._persist_approval_request = AsyncMock(return_value=None)
        service._store_artifact = AsyncMock(return_value=uuid.uuid4())
        service._run_optimization_phase = AsyncMock(return_value=(
            "print('optimized')",
            {"applied": True, "platform": "fabric"},
        ))
        service._execute_on_fabric = AsyncMock(return_value={
            "status": "SUCCESS",
            "output": "ok",
            "error": None,
            "job_id": "fabric-job-1",
            "duration_ms": 222,
        })
        setattr(service, "_analyzer", SimpleNamespace(
            evaluate=lambda code, language="python": RiskResult(
                passed=True,
                risk_level=RiskLevel.LOW,
                findings=(),
                gate="static_analysis",
            ),
        ))

        result = await service.execute_task(task.id)

        assert result["status"] == "COMPLETED"
        service._execute_capability_agent.assert_awaited_once()
        service._persist_capability_artifacts.assert_awaited_once()
        service._generate_code.assert_not_called()

    @pytest.mark.asyncio
    async def test_production_stops_at_approval_pending_after_optimization(
        self,
        service: ExecutionService,
    ):
        task = _task(
            title="Create table",
            description="Create schema and table",
            metadata_={"task_type": "catalog",
                       "language": "sql", "platform": "databricks"},
            environment="PRODUCTION",
        )

        transitions: list[tuple[TaskState, TaskState]] = []

        async def record_transition(task_id, from_state, to_state):
            transitions.append((from_state, to_state))

        service._load_task = AsyncMock(return_value=task)
        service._transition = AsyncMock(side_effect=record_transition)
        service._execute_capability_agent = AsyncMock(return_value=(
            "CREATE TABLE t (id INT)",
            [{"type": "job_config", "content": {"x": 1}}],
        ))
        service._persist_capability_artifacts = AsyncMock(return_value=None)
        service._set_task_metadata = AsyncMock(return_value=None)
        service._persist_approval_request = AsyncMock(return_value=None)
        service._store_artifact = AsyncMock(return_value=uuid.uuid4())
        service._run_optimization_phase = AsyncMock(return_value=(
            "CREATE TABLE t (id INT)",
            {"applied": False, "reason": "Language not supported",
                "platform": "databricks"},
        ))
        setattr(service, "_analyzer", SimpleNamespace(
            evaluate=lambda code, language="sql": RiskResult(
                passed=True,
                risk_level=RiskLevel.LOW,
                findings=(),
                gate="static_analysis",
            ),
        ))

        result = await service.execute_task(task.id)

        assert result["status"] == "APPROVAL_PENDING"
        assert (TaskState.IN_OPTIMIZATION, TaskState.OPTIMIZED) in transitions
        assert (TaskState.OPTIMIZED, TaskState.APPROVAL_PENDING) in transitions


class TestInvariantEnforcement:
    @pytest.mark.asyncio
    async def test_resume_after_approval_requires_decision_explanation(
        self,
        service: ExecutionService,
    ):
        task = _task(
            title="Resume deployment",
            description="Requires approval",
            metadata_={"approval_id": str(uuid.uuid4())},
        )
        task.current_state = TaskState.APPROVAL_PENDING.value

        with pytest.raises(RuntimeError, match="INV-09"):
            await service._resume_after_approval(cast(Task, task))


class TestExecutionServiceFactory:
    def test_create_fails_when_required_config_missing(self, monkeypatch):
        import aadap.services.execution as execution_mod

        monkeypatch.setattr(
            execution_mod,
            "get_settings",
            lambda: SimpleNamespace(
                azure_openai_api_key=None,
                azure_openai_endpoint=None,
                azure_openai_deployment_name=None,
                databricks_host=None,
                fabric_tenant_id=None,
                fabric_client_id=None,
                fabric_client_secret=None,
                fabric_workspace_id=None,
            ),
        )

        with pytest.raises(RuntimeError, match="Missing"):
            ExecutionService.create()

    def test_create_uses_real_clients_when_config_present(self, monkeypatch):
        import aadap.services.execution as execution_mod

        monkeypatch.setattr(
            execution_mod,
            "get_settings",
            lambda: SimpleNamespace(
                azure_openai_api_key="set",
                azure_openai_endpoint="https://example.openai.azure.com",
                azure_openai_deployment_name="gpt-4o",
                databricks_host="https://adb.example.com",
                fabric_tenant_id="tenant",
                fabric_client_id="client",
                fabric_client_secret="secret",
                fabric_workspace_id="workspace",
            ),
        )
        monkeypatch.setattr(
            execution_mod.AzureOpenAIClient,
            "from_settings",
            classmethod(lambda cls: MockLLMClient(default_response="ok")),
        )
        monkeypatch.setattr(
            execution_mod.DatabricksClient,
            "from_settings",
            classmethod(lambda cls: MockDatabricksClient()),
        )
        monkeypatch.setattr(
            execution_mod.FabricClient,
            "from_settings",
            classmethod(lambda cls: MockFabricClient()),
        )

        service = ExecutionService.create()
        assert isinstance(service, ExecutionService)
