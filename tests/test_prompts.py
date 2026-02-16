"""
AADAP — Prompt Template Tests (Phase 4)
===========================================
Tests for prompt rendering, output validation, and self-correction
prompt building.

Covers:
- Prompt ``render()`` includes system role + constraints
- ``validate_output`` accepts valid JSON conforming to schema
- ``validate_output`` rejects malformed JSON / missing fields
- Prompt templates are non-empty and contain role declarations
"""

from __future__ import annotations

import json

import pytest

from aadap.agents.prompts.base import (
    OutputSchemaViolation,
    PromptTemplate,
    StructuredOutput,
    build_correction_prompt,
    validate_output,
)
from aadap.agents.prompts.developer import DEVELOPER_PROMPTS
from aadap.agents.prompts.optimization import OPTIMIZATION_PROMPTS
from aadap.agents.prompts.orchestrator import ORCHESTRATOR_PROMPTS
from aadap.agents.prompts.validation import VALIDATION_PROMPTS


# ── StructuredOutput Tests ──────────────────────────────────────────────


class TestStructuredOutput:
    def test_valid_schema(self):
        schema = StructuredOutput(
            fields={"name": "str", "age": "int"},
            required={"name"},
        )
        assert "name" in schema.fields
        assert "name" in schema.required

    def test_required_field_not_in_schema_raises(self):
        with pytest.raises(ValueError, match="Required fields not in schema"):
            StructuredOutput(
                fields={"name": "str"},
                required={"name", "missing_field"},
            )

    def test_empty_required_is_valid(self):
        schema = StructuredOutput(fields={"x": "str"})
        assert schema.required == set()


# ── PromptTemplate Tests ───────────────────────────────────────────────


class TestPromptTemplate:
    @pytest.fixture
    def sample_template(self):
        return PromptTemplate(
            name="test",
            system_role="You are a test agent.",
            constraints=["Must be accurate.", "Must be concise."],
            output_schema=StructuredOutput(
                fields={"result": "str"},
                required={"result"},
            ),
            task_instruction="Process: {input_data}",
        )

    def test_render_includes_role(self, sample_template):
        rendered = sample_template.render({"input_data": "hello"})
        assert "## ROLE" in rendered
        assert "You are a test agent." in rendered

    def test_render_includes_constraints(self, sample_template):
        rendered = sample_template.render({"input_data": "hello"})
        assert "## CONSTRAINTS" in rendered
        assert "Must be accurate." in rendered
        assert "Must be concise." in rendered

    def test_render_includes_output_format(self, sample_template):
        rendered = sample_template.render({"input_data": "hello"})
        assert "## OUTPUT FORMAT" in rendered
        assert "JSON" in rendered
        assert "result" in rendered

    def test_render_includes_task(self, sample_template):
        rendered = sample_template.render({"input_data": "hello"})
        assert "## TASK" in rendered
        assert "Process: hello" in rendered

    def test_render_interpolates_context(self, sample_template):
        rendered = sample_template.render({"input_data": "world"})
        assert "Process: world" in rendered


# ── validate_output Tests ──────────────────────────────────────────────


class TestValidateOutput:
    @pytest.fixture
    def schema(self):
        return StructuredOutput(
            fields={"code": "str", "language": "str"},
            required={"code", "language"},
        )

    def test_valid_json(self, schema):
        raw = json.dumps({"code": "print('hi')", "language": "python"})
        result = validate_output(raw, schema)
        assert result["code"] == "print('hi')"
        assert result["language"] == "python"

    def test_valid_json_with_extra_fields(self, schema):
        raw = json.dumps({"code": "x", "language": "py", "extra": 42})
        result = validate_output(raw, schema)
        assert result["extra"] == 42

    def test_strips_markdown_code_fence(self, schema):
        raw = '```json\n{"code": "x", "language": "py"}\n```'
        result = validate_output(raw, schema)
        assert result["code"] == "x"

    def test_invalid_json_raises(self, schema):
        with pytest.raises(OutputSchemaViolation, match="Invalid JSON"):
            validate_output("not json at all", schema)

    def test_missing_required_field_raises(self, schema):
        raw = json.dumps({"code": "x"})
        with pytest.raises(OutputSchemaViolation, match="Missing required field"):
            validate_output(raw, schema)

    def test_non_dict_json_raises(self, schema):
        raw = json.dumps([1, 2, 3])
        with pytest.raises(OutputSchemaViolation, match="must be a JSON object"):
            validate_output(raw, schema)

    def test_empty_required_set_accepts_any_dict(self):
        schema = StructuredOutput(fields={"x": "str"})
        result = validate_output('{"anything": 42}', schema)
        assert result == {"anything": 42}


# ── build_correction_prompt Tests ──────────────────────────────────────


class TestBuildCorrectionPrompt:
    def test_includes_original_prompt(self):
        error = OutputSchemaViolation(
            errors=["Missing field: 'x'"],
            raw_output='{"bad": true}',
        )
        result = build_correction_prompt("original prompt", '{"bad": true}', error)
        assert "original prompt" in result
        assert "CORRECTION REQUIRED" in result
        assert "Missing field: 'x'" in result
        assert '{"bad": true}' in result


# ── Agent-specific Prompt Collections ──────────────────────────────────


class TestAgentPromptCollections:
    """Verify all 4 agent prompt collections are non-empty and renderable."""

    @pytest.mark.parametrize("collection,key", [
        (ORCHESTRATOR_PROMPTS, "decision"),
        (DEVELOPER_PROMPTS, "code_generation"),
        (VALIDATION_PROMPTS, "code_review"),
        (OPTIMIZATION_PROMPTS, "optimize"),
    ])
    def test_prompt_exists(self, collection, key):
        assert key in collection
        template = collection[key]
        assert isinstance(template, PromptTemplate)
        assert template.name
        assert template.system_role

    @pytest.mark.parametrize("collection,key,context", [
        (ORCHESTRATOR_PROMPTS, "decision", {
            "title": "Test", "description": "Test task", "environment": "SANDBOX",
        }),
        (DEVELOPER_PROMPTS, "code_generation", {
            "task_description": "Read CSV", "environment": "SANDBOX", "context": "None",
        }),
        (VALIDATION_PROMPTS, "code_review", {
            "code": "print('hi')", "language": "python",
            "task_description": "Test", "environment": "SANDBOX",
        }),
        (OPTIMIZATION_PROMPTS, "optimize", {
            "code": "df.collect()", "context": "None", "environment": "SANDBOX",
        }),
    ])
    def test_prompt_renders(self, collection, key, context):
        template = collection[key]
        rendered = template.render(context)
        assert "## ROLE" in rendered
        assert "## CONSTRAINTS" in rendered
        assert "## OUTPUT FORMAT" in rendered
        assert "## TASK" in rendered
        assert len(rendered) > 100
