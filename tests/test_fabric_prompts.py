"""
AADAP — Fabric Prompt Tests
===============================
Tests for Fabric agent prompt templates and code generation prompts.
"""

from __future__ import annotations

import pytest

from aadap.agents.prompts.fabric import (
    FABRIC_CODE_SCHEMA,
    FABRIC_PYTHON_PROMPT,
    FABRIC_SCALA_PROMPT,
    FABRIC_SQL_PROMPT,
    build_fabric_code_gen_prompt,
    get_fabric_prompt,
)


class TestFabricPromptSchemas:
    def test_fabric_code_schema_has_required_fields(self):
        """Schema should define code, language, explanation, dependencies."""
        assert "code" in FABRIC_CODE_SCHEMA.fields
        assert "language" in FABRIC_CODE_SCHEMA.fields
        assert "explanation" in FABRIC_CODE_SCHEMA.fields
        assert "dependencies" in FABRIC_CODE_SCHEMA.fields
        assert "fabric_item_type" in FABRIC_CODE_SCHEMA.fields

    def test_python_prompt_targets_fabric(self):
        """Python prompt should mention Fabric."""
        assert "Fabric" in FABRIC_PYTHON_PROMPT.system_role

    def test_scala_prompt_targets_fabric(self):
        """Scala prompt should mention Fabric."""
        assert "Fabric" in FABRIC_SCALA_PROMPT.system_role

    def test_sql_prompt_targets_fabric(self):
        """SQL prompt should mention Fabric."""
        assert "Fabric" in FABRIC_SQL_PROMPT.system_role

    def test_python_prompt_mentions_notebookutils(self):
        """Python prompt should reference Fabric-native APIs."""
        constraints_text = " ".join(FABRIC_PYTHON_PROMPT.constraints)
        assert "notebookutils" in constraints_text

    def test_python_prompt_excludes_dbutils(self):
        """Python prompt should warn against dbutils."""
        constraints_text = " ".join(FABRIC_PYTHON_PROMPT.constraints)
        assert "dbutils" in constraints_text.lower()


class TestGetFabricPrompt:
    def test_python_returns_python_prompt(self):
        assert get_fabric_prompt("python") is FABRIC_PYTHON_PROMPT

    def test_scala_returns_scala_prompt(self):
        assert get_fabric_prompt("scala") is FABRIC_SCALA_PROMPT

    def test_sql_returns_sql_prompt(self):
        assert get_fabric_prompt("sql") is FABRIC_SQL_PROMPT

    def test_unknown_defaults_to_python(self):
        assert get_fabric_prompt("unknown") is FABRIC_PYTHON_PROMPT

    def test_case_insensitive(self):
        assert get_fabric_prompt("Python") is FABRIC_PYTHON_PROMPT
        assert get_fabric_prompt("SCALA") is FABRIC_SCALA_PROMPT
        assert get_fabric_prompt("SQL") is FABRIC_SQL_PROMPT


class TestBuildFabricCodeGenPrompt:
    def test_includes_task_title(self):
        prompt = build_fabric_code_gen_prompt(
            title="Create sales report",
            description=None,
            environment="SANDBOX",
            language="python",
        )
        assert "Create sales report" in prompt

    def test_includes_description(self):
        prompt = build_fabric_code_gen_prompt(
            title="ETL job",
            description="Extract data from source, transform, and load",
            environment="SANDBOX",
            language="python",
        )
        assert "Extract data from source" in prompt

    def test_includes_environment(self):
        prompt = build_fabric_code_gen_prompt(
            title="Test task",
            description=None,
            environment="PRODUCTION",
            language="sql",
        )
        assert "PRODUCTION" in prompt

    def test_includes_platform(self):
        prompt = build_fabric_code_gen_prompt(
            title="Test task",
            description=None,
            environment="SANDBOX",
            language="python",
        )
        assert "Fabric" in prompt

    def test_sql_prompt_mentions_delta(self):
        prompt = build_fabric_code_gen_prompt(
            title="Test SQL",
            description=None,
            environment="SANDBOX",
            language="sql",
        )
        assert "Delta" in prompt

    def test_scala_prompt_mentions_dataframe(self):
        prompt = build_fabric_code_gen_prompt(
            title="Test Scala",
            description=None,
            environment="SANDBOX",
            language="scala",
        )
        assert "DataFrame" in prompt
