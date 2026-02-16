"""
AADAP — Prompt Template Base
================================
Reusable prompt rendering and structured output validation.

Architecture layer: L4 (Agent Layer).
Source of truth: PHASE_4_CONTRACTS.md §Required Capabilities.

Design decisions:
- Prompt templates enforce role + constraints in every render
- Output validation is strict: JSON must conform to declared schema
- Self-correction prompts are built from validation errors
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


# ── Exceptions ──────────────────────────────────────────────────────────


class OutputSchemaViolation(Exception):
    """Raised when LLM output does not conform to the declared schema."""

    def __init__(self, errors: list[str], raw_output: str) -> None:
        self.errors = errors
        self.raw_output = raw_output
        super().__init__(
            f"Output schema violation: {'; '.join(errors)}"
        )


# ── StructuredOutput ────────────────────────────────────────────────────


@dataclass(frozen=True)
class StructuredOutput:
    """
    Describes the expected JSON output schema for an agent.

    Parameters
    ----------
    fields
        Mapping of field name → expected type name (e.g. ``{"code": "str"}``).
    required
        Set of field names that must be present.
    """

    fields: dict[str, str]
    required: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        # Validate that all required fields exist in the schema
        missing = self.required - set(self.fields.keys())
        if missing:
            raise ValueError(
                f"Required fields not in schema: {sorted(missing)}"
            )


# ── PromptTemplate ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class PromptTemplate:
    """
    Structured prompt template with role, constraints, and output schema.

    All prompts rendered by this class contain:
    1. System role declaration
    2. Explicit constraints
    3. Output format specification
    4. Task-specific context (injected at render time)
    """

    name: str
    system_role: str
    constraints: list[str]
    output_schema: StructuredOutput
    task_instruction: str

    def render(self, context: dict[str, Any]) -> str:
        """
        Render the full prompt with injected context.

        Parameters
        ----------
        context
            Task-specific key-value pairs interpolated into the
            task instruction via ``str.format_map``.

        Returns
        -------
        str
            Complete prompt string ready for LLM submission.
        """
        sections = [
            f"## ROLE\n{self.system_role}",
            self._render_constraints(),
            self._render_output_format(),
            f"## TASK\n{self.task_instruction.format_map(context)}",
        ]
        return "\n\n".join(sections)

    def _render_constraints(self) -> str:
        items = "\n".join(f"- {c}" for c in self.constraints)
        return f"## CONSTRAINTS\n{items}"

    def _render_output_format(self) -> str:
        schema_desc = json.dumps(
            self.output_schema.fields, indent=2
        )
        required = ", ".join(sorted(self.output_schema.required))
        return (
            f"## OUTPUT FORMAT\n"
            f"Respond with a single JSON object matching this schema:\n"
            f"```json\n{schema_desc}\n```\n"
            f"Required fields: {required}\n"
            f"Do NOT include any text outside the JSON object."
        )


# ── Output Validation ──────────────────────────────────────────────────


def validate_output(raw: str, schema: StructuredOutput) -> dict[str, Any]:
    """
    Parse and validate LLM output against a declared schema.

    Parameters
    ----------
    raw
        Raw string output from the LLM.
    schema
        Expected output schema.

    Returns
    -------
    dict
        Parsed and validated output.

    Raises
    ------
    OutputSchemaViolation
        If the output is not valid JSON or missing required fields.
    """
    errors: list[str] = []

    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [
            ln for ln in lines
            if not ln.strip().startswith("```")
        ]
        cleaned = "\n".join(lines)

    # Parse JSON
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise OutputSchemaViolation(
            errors=[f"Invalid JSON: {e}"],
            raw_output=raw,
        )

    if not isinstance(parsed, dict):
        raise OutputSchemaViolation(
            errors=["Output must be a JSON object (dict), "
                    f"got {type(parsed).__name__}"],
            raw_output=raw,
        )

    # Check required fields
    for req_field in schema.required:
        if req_field not in parsed:
            errors.append(f"Missing required field: '{req_field}'")

    if errors:
        raise OutputSchemaViolation(errors=errors, raw_output=raw)

    return parsed


# ── Self-correction Prompt Builder ─────────────────────────────────────


def build_correction_prompt(
    original_prompt: str,
    bad_output: str,
    error: OutputSchemaViolation,
) -> str:
    """
    Build a self-correction prompt from a schema violation.

    Parameters
    ----------
    original_prompt
        The original prompt that produced the bad output.
    bad_output
        The raw LLM output that failed validation.
    error
        The schema violation with error details.

    Returns
    -------
    str
        A correction prompt instructing the LLM to fix its output.
    """
    error_list = "\n".join(f"- {e}" for e in error.errors)
    return (
        f"{original_prompt}\n\n"
        f"## CORRECTION REQUIRED\n"
        f"Your previous response was invalid:\n"
        f"```\n{bad_output}\n```\n\n"
        f"Errors:\n{error_list}\n\n"
        f"Please respond again with a corrected JSON object. "
        f"Fix ALL errors listed above."
    )
