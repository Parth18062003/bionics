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
from aadap.agents.prompts.developer import DEVELOPER_PROMPTS
from aadap.agents.prompts.optimization import OPTIMIZATION_PROMPTS
from aadap.agents.prompts.orchestrator import ORCHESTRATOR_PROMPTS
from aadap.agents.prompts.validation import VALIDATION_PROMPTS

__all__ = [
    "DEVELOPER_PROMPTS",
    "OPTIMIZATION_PROMPTS",
    "ORCHESTRATOR_PROMPTS",
    "OutputSchemaViolation",
    "PromptTemplate",
    "StructuredOutput",
    "VALIDATION_PROMPTS",
    "validate_output",
]
