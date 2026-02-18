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
    BATCH_INGESTION_PROMPT,
    CDC_INGESTION_PROMPT,
    INGESTION_SCHEMA,
    STREAMING_INGESTION_PROMPT,
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
    "BATCH_INGESTION_PROMPT",
    "CATALOG_SCHEMA",
    "CDC_INGESTION_PROMPT",
    "DAG_BUILDER_PROMPT",
    "DEVELOPER_PROMPTS",
    "DLT_PIPELINE_PROMPT",
    "ETL_PIPELINE_SCHEMA",
    "FABRIC_PIPELINE_PROMPT",
    "INGESTION_SCHEMA",
    "JOB_CREATION_PROMPT",
    "JOB_SCHEDULER_SCHEMA",
    "OPTIMIZATION_PROMPTS",
    "ORCHESTRATOR_PROMPTS",
    "OutputSchemaViolation",
    "PERMISSION_GRANT_PROMPT",
    "PromptTemplate",
    "SCHEMA_DESIGN_PROMPT",
    "SCHEDULE_CONFIG_PROMPT",
    "STREAMING_INGESTION_PROMPT",
    "StructuredOutput",
    "TRANSFORMATION_PROMPT",
    "VALIDATION_PROMPTS",
    "get_etl_pipeline_prompt",
    "get_ingestion_prompt",
    "get_job_scheduler_prompt",
    "get_catalog_prompt",
    "validate_output",
]
