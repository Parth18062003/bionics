"""
AADAP — Prompt Templates (Phase 4)
======================================
Structured prompt framework for domain-specific agents.

Public API:
    PromptTemplate, StructuredOutput, OutputSchemaViolation,
    validate_output,
    ORCHESTRATOR_PROMPTS, DEVELOPER_PROMPTS,
    VALIDATION_PROMPTS, OPTIMIZATION_PROMPTS
"""

from aadap.agents.prompts.base import (
    OutputSchemaViolation,
    PromptTemplate,
    StructuredOutput,
    validate_output,
)
from aadap.agents.prompts.catalog import (
    CATALOG_SCHEMA,
    PERMISSION_GRANT_PROMPT,
    SCHEMA_DESIGN_PROMPT,
    get_catalog_prompt,
)
from aadap.agents.prompts.developer import DEVELOPER_PROMPTS
from aadap.agents.prompts.etl_pipeline import (
    DLT_PIPELINE_PROMPT,
    ETL_PIPELINE_SCHEMA,
    FABRIC_PIPELINE_PROMPT,
    TRANSFORMATION_PROMPT,
    get_etl_pipeline_prompt,
)
from aadap.agents.prompts.ingestion import (
    BATCH_INGESTION_DATABRICKS_PROMPT,
    BATCH_INGESTION_FABRIC_PROMPT,
    CDC_INGESTION_DATABRICKS_PROMPT,
    CDC_INGESTION_FABRIC_PROMPT,
    INGESTION_SCHEMA,
    INGESTION_PROMPTS,
    STREAMING_INGESTION_DATABRICKS_PROMPT,
    STREAMING_INGESTION_FABRIC_PROMPT,
    get_ingestion_prompt,
)
from aadap.agents.prompts.job_scheduler import (
    DAG_BUILDER_PROMPT,
    JOB_CREATION_PROMPT,
    JOB_SCHEDULER_SCHEMA,
    SCHEDULE_CONFIG_PROMPT,
    get_job_scheduler_prompt,
)
from aadap.agents.prompts.optimization import OPTIMIZATION_PROMPTS
from aadap.agents.prompts.orchestrator import ORCHESTRATOR_PROMPTS
from aadap.agents.prompts.validation import VALIDATION_PROMPTS

__all__ = [
    # Base classes
    "OutputSchemaViolation",
    "PromptTemplate",
    "StructuredOutput",
    "validate_output",
    # Catalog
    "CATALOG_SCHEMA",
    "PERMISSION_GRANT_PROMPT",
    "SCHEMA_DESIGN_PROMPT",
    "get_catalog_prompt",
    # Developer
    "DEVELOPER_PROMPTS",
    # ETL Pipeline
    "DLT_PIPELINE_PROMPT",
    "ETL_PIPELINE_SCHEMA",
    "FABRIC_PIPELINE_PROMPT",
    "TRANSFORMATION_PROMPT",
    "get_etl_pipeline_prompt",
    # Ingestion
    "BATCH_INGESTION_DATABRICKS_PROMPT",
    "BATCH_INGESTION_FABRIC_PROMPT",
    "CDC_INGESTION_DATABRICKS_PROMPT",
    "CDC_INGESTION_FABRIC_PROMPT",
    "INGESTION_SCHEMA",
    "INGESTION_PROMPTS",
    "STREAMING_INGESTION_DATABRICKS_PROMPT",
    "STREAMING_INGESTION_FABRIC_PROMPT",
    "get_ingestion_prompt",
    # Job Scheduler
    "DAG_BUILDER_PROMPT",
    "JOB_CREATION_PROMPT",
    "JOB_SCHEDULER_SCHEMA",
    "SCHEDULE_CONFIG_PROMPT",
    "get_job_scheduler_prompt",
    # Other agents
    "OPTIMIZATION_PROMPTS",
    "ORCHESTRATOR_PROMPTS",
    "VALIDATION_PROMPTS",
]
