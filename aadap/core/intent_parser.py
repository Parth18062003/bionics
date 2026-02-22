"""
AADAP — Intent Parser
=========================
Sophisticated intent parsing and requirement extraction system.

This module provides the intelligence layer that sits between user requests
and agent execution, enabling:
- Intent classification and entity extraction
- Requirement decomposition and clarification
- Context-aware task enrichment
- Ambiguity detection and resolution

Architecture layer: L3.5 (Intent Layer) — between API (L6) and Agents (L4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aadap.core.logging import get_logger

logger = get_logger(__name__)


# ── Intent Types ────────────────────────────────────────────────────────


class IntentType(StrEnum):
    """Classification of user intent."""

    # Data operations
    INGEST_DATA = "ingest_data"
    TRANSFORM_DATA = "transform_data"
    QUERY_DATA = "query_data"
    EXPORT_DATA = "export_data"

    # Pipeline operations
    CREATE_PIPELINE = "create_pipeline"
    MODIFY_PIPELINE = "modify_pipeline"
    SCHEDULE_JOB = "schedule_job"
    MONITOR_JOB = "monitor_job"

    # Schema operations
    CREATE_TABLE = "create_table"
    MODIFY_SCHEMA = "modify_schema"
    GRANT_ACCESS = "grant_access"
    REVOKE_ACCESS = "revoke_access"

    # Exploration
    LIST_RESOURCES = "list_resources"
    DESCRIBE_RESOURCE = "describe_resource"
    PREVIEW_DATA = "preview_data"

    # Code operations
    GENERATE_CODE = "generate_code"
    OPTIMIZE_CODE = "optimize_code"
    VALIDATE_CODE = "validate_code"
    EXECUTE_CODE = "execute_code"

    # Unknown
    UNKNOWN = "unknown"


class ComplexityLevel(StrEnum):
    """Complexity assessment for task planning."""

    SIMPLE = "simple"         # Single operation, clear parameters
    MODERATE = "moderate"     # Multiple steps, some inference needed
    COMPLEX = "complex"       # Multi-stage pipeline, significant inference
    AMBIGUOUS = "ambiguous"   # Unclear intent, needs clarification


class Platform(StrEnum):
    """Target platform detection."""

    DATABRICKS = "databricks"
    FABRIC = "fabric"
    BOTH = "both"
    UNSPECIFIED = "unspecified"


# ── Extracted Entities ───────────────────────────────────────────────────


@dataclass
class ExtractedEntities:
    """Entities extracted from user request."""

    # Data entities
    tables: list[str] = field(default_factory=list)
    schemas: list[str] = field(default_factory=list)
    catalogs: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)

    # File entities
    file_paths: list[str] = field(default_factory=list)
    file_formats: list[str] = field(default_factory=list)

    # Pipeline entities
    pipeline_names: list[str] = field(default_factory=list)
    job_names: list[str] = field(default_factory=list)
    schedule_expressions: list[str] = field(default_factory=list)

    # Security entities
    principals: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)

    # Configuration
    constraints: dict[str, Any] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tables": self.tables,
            "schemas": self.schemas,
            "catalogs": self.catalogs,
            "columns": self.columns,
            "file_paths": self.file_paths,
            "file_formats": self.file_formats,
            "pipeline_names": self.pipeline_names,
            "job_names": self.job_names,
            "schedule_expressions": self.schedule_expressions,
            "principals": self.principals,
            "permissions": self.permissions,
            "constraints": self.constraints,
            "parameters": self.parameters,
        }


# ── Clarification Request ───────────────────────────────────────────────


@dataclass
class ClarificationRequest:
    """Request for clarification when intent is ambiguous."""

    question: str
    options: list[str] | None = None
    field_name: str | None = None
    required: bool = True
    default: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "question": self.question,
            "options": self.options,
            "field_name": self.field_name,
            "required": self.required,
            "default": self.default,
        }


# ── Parsed Intent ────────────────────────────────────────────────────────


@dataclass
class ParsedIntent:
    """Complete parsed intent from user request."""

    # Core intent
    intent_type: IntentType
    complexity: ComplexityLevel
    confidence: float  # 0.0 to 1.0

    # Extracted information
    entities: ExtractedEntities
    raw_request: str

    # Target platform
    platform: Platform = Platform.UNSPECIFIED

    # Task routing
    recommended_agent: str | None = None
    task_mode: str = "generate_code"
    operation_type: str | None = None

    # Clarification
    needs_clarification: bool = False
    clarification_requests: list[ClarificationRequest] = field(
        default_factory=list)

    # Enriched context
    inferred_context: dict[str, Any] = field(default_factory=dict)
    safety_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "intent_type": self.intent_type.value,
            "complexity": self.complexity.value,
            "confidence": self.confidence,
            "entities": self.entities.to_dict(),
            "platform": self.platform.value,
            "recommended_agent": self.recommended_agent,
            "task_mode": self.task_mode,
            "operation_type": self.operation_type,
            "needs_clarification": self.needs_clarification,
            "clarification_requests": [cr.to_dict() for cr in self.clarification_requests],
            "inferred_context": self.inferred_context,
            "safety_notes": self.safety_notes,
        }


# ── Intent Parser ────────────────────────────────────────────────────────


class IntentParser:
    """
    Sophisticated intent parser for understanding user requests.

    This class implements a multi-stage parsing pipeline:
    1. Pattern matching for known patterns
    2. Entity extraction using regex and heuristics
    3. Context inference from partial information
    4. Ambiguity detection and clarification generation
    """

    # Intent keywords mapping
    _INTENT_KEYWORDS: dict[IntentType, list[str]] = {
        IntentType.INGEST_DATA: [
            "ingest", "load data", "import", "copy data", "auto loader",
            "streaming", "kafka", "event hub", "cdc", "change data",
            "bulk load", "batch load", "file load",
        ],
        IntentType.TRANSFORM_DATA: [
            "transform", "etl", "elt", "pipeline", "dlt", "delta live",
            "medallion", "bronze", "silver", "gold", "data factory",
            "notebook", "process data",
        ],
        IntentType.QUERY_DATA: [
            "query", "select", "filter", "aggregate", "join",
            "search", "find", "get data", "read data",
        ],
        IntentType.EXPORT_DATA: [
            "export", "download", "extract", "dump", "output",
            "write to file", "save as",
        ],
        IntentType.CREATE_PIPELINE: [
            "create pipeline", "build pipeline", "new pipeline",
            "set up pipeline", "pipeline for", "workflow",
        ],
        IntentType.SCHEDULE_JOB: [
            "schedule", "cron", "trigger", "daily", "hourly", "weekly",
            "run every", "recurring", "automated run", "job",
        ],
        IntentType.CREATE_TABLE: [
            "create table", "new table", "define table", "ddl",
            "schema for", "table structure",
        ],
        IntentType.GRANT_ACCESS: [
            "grant", "give access", "permission", "allow", "authorize",
            "share", "privilege",
        ],
        IntentType.REVOKE_ACCESS: [
            "revoke", "remove access", "deny", "revoke permission",
            "take away",
        ],
        IntentType.LIST_RESOURCES: [
            "list", "show all", "display all", "what tables",
            "what schemas", "enumerate",
        ],
        IntentType.DESCRIBE_RESOURCE: [
            "describe", "show schema", "table structure", "columns of",
            "definition of", "details of",
        ],
        IntentType.PREVIEW_DATA: [
            "preview", "sample", "first rows", "head", "show data",
            "peek", "view data",
        ],
        IntentType.GENERATE_CODE: [
            "generate code", "write code", "create script", "develop",
            "implement", "build", "code for",
        ],
        IntentType.OPTIMIZE_CODE: [
            "optimize", "improve performance", "speed up", "tune",
            "make faster", "efficient",
        ],
        IntentType.EXECUTE_CODE: [
            "execute", "run", "submit", "deploy", "launch",
        ],
    }

    # Platform keywords
    _PLATFORM_KEYWORDS: dict[Platform, list[str]] = {
        Platform.DATABRICKS: [
            "databricks", "adb", "delta lake", "unity catalog",
            "databricks sql", "dbx", "spark", "pyspark",
        ],
        Platform.FABRIC: [
            "fabric", "lakehouse", "synapse", "onenote", "onelake", "fabrics", "azure fabrics", "microsoft fabrics",
            "datafactory", "notebookutils", "mssparkutils", "power bi",
        ],
    }

    # Agent routing map
    _AGENT_ROUTING: dict[IntentType, str] = {
        IntentType.INGEST_DATA: "ingestion",
        IntentType.TRANSFORM_DATA: "etl_pipeline",
        IntentType.CREATE_PIPELINE: "etl_pipeline",
        IntentType.SCHEDULE_JOB: "job_scheduler",
        IntentType.CREATE_TABLE: "catalog",
        IntentType.GRANT_ACCESS: "catalog",
        IntentType.REVOKE_ACCESS: "catalog",
        IntentType.LIST_RESOURCES: "developer",
        IntentType.DESCRIBE_RESOURCE: "developer",
        IntentType.PREVIEW_DATA: "developer",
        IntentType.QUERY_DATA: "developer",
        IntentType.GENERATE_CODE: "developer",
        IntentType.OPTIMIZE_CODE: "optimization",
        IntentType.EXECUTE_CODE: "developer",
    }

    # Entity patterns
    _TABLE_PATTERN = re.compile(
        r"(?:table|from|into|update)\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*){0,2})",
        re.IGNORECASE,
    )
    _SCHEMA_PATTERN = re.compile(
        r"(?:schema|database)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        re.IGNORECASE,
    )
    _CATALOG_PATTERN = re.compile(
        r"(?:catalog|workspace)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        re.IGNORECASE,
    )
    _FILE_PATH_PATTERN = re.compile(
        r"(?:path|file|location)\s+[\"']?([a-zA-Z0-9_./\-]+)[\"']?",
        re.IGNORECASE,
    )
    _SCHEDULE_PATTERN = re.compile(
        r"(?:every|each|run\s+(?:every|each)?)\s*(\d+)?\s*(second|minute|hour|day|week|month)s?",
        re.IGNORECASE,
    )
    _PRINCIPAL_PATTERN = re.compile(
        r"(?:user|group|service\s*principal)\s+[\"']?([a-zA-Z0-9_@\-\.]+)[\"']?",
        re.IGNORECASE,
    )
    _PERMISSION_PATTERN = re.compile(
        r"(?:grant|give|allow)\s+(select|insert|update|delete|all|read|write|modify|create|usage)",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        """Initialize the intent parser."""
        pass

    def parse(self, request: str, context: dict[str, Any] | None = None) -> ParsedIntent:
        """
        Parse a user request into structured intent.

        Parameters
        ----------
        request
            The raw user request string.
        context
            Optional additional context (metadata, user info, etc.)

        Returns
        -------
        ParsedIntent
            Structured representation of the parsed intent.
        """
        request_lower = request.lower()
        context = context or {}

        # Stage 1: Intent classification
        intent_type, confidence = self._classify_intent(request_lower)

        # Stage 2: Entity extraction
        entities = self._extract_entities(request, request_lower)

        # Stage 3: Platform detection
        platform = self._detect_platform(request_lower, context)

        # Stage 4: Complexity assessment
        complexity = self._assess_complexity(
            request=request,
            intent_type=intent_type,
            entities=entities,
            context=context,
        )

        # Stage 5: Agent routing
        recommended_agent = self._AGENT_ROUTING.get(intent_type, "developer")

        # Stage 6: Task mode and operation type
        task_mode, operation_type = self._determine_task_mode(
            intent_type=intent_type,
            complexity=complexity,
            entities=entities,
        )

        # Stage 7: Check for needed clarifications
        clarification_requests = self._check_clarifications(
            intent_type=intent_type,
            entities=entities,
            complexity=complexity,
            request=request,
        )

        # Stage 8: Infer additional context
        inferred_context = self._infer_context(
            intent_type=intent_type,
            entities=entities,
            platform=platform,
            context=context,
        )

        # Stage 9: Safety notes
        safety_notes = self._generate_safety_notes(
            intent_type=intent_type,
            entities=entities,
            request=request_lower,
        )

        return ParsedIntent(
            intent_type=intent_type,
            complexity=complexity,
            confidence=confidence,
            entities=entities,
            raw_request=request,
            platform=platform,
            recommended_agent=recommended_agent,
            task_mode=task_mode,
            operation_type=operation_type,
            needs_clarification=len(clarification_requests) > 0,
            clarification_requests=clarification_requests,
            inferred_context=inferred_context,
            safety_notes=safety_notes,
        )

    def _classify_intent(self, request_lower: str) -> tuple[IntentType, float]:
        """Classify the intent type with confidence score."""
        scores: dict[IntentType, int] = {}

        for intent_type, keywords in self._INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in request_lower)
            if score > 0:
                scores[intent_type] = score

        if not scores:
            return IntentType.UNKNOWN, 0.0

        best_intent = max(scores.keys(), key=lambda k: scores[k])
        total_matches = sum(scores.values())
        confidence = min(1.0, scores[best_intent] / max(total_matches, 1))

        return best_intent, confidence

    def _extract_entities(self, request: str, request_lower: str) -> ExtractedEntities:
        """Extract entities from the request."""
        entities = ExtractedEntities()

        # Extract table references
        table_matches = self._TABLE_PATTERN.findall(request)
        entities.tables = list(set(table_matches))

        # Extract schema references
        schema_matches = self._SCHEMA_PATTERN.findall(request)
        entities.schemas = list(set(schema_matches))

        # Extract catalog references
        catalog_matches = self._CATALOG_PATTERN.findall(request)
        entities.catalogs = list(set(catalog_matches))

        # Extract file paths
        file_matches = self._FILE_PATH_PATTERN.findall(request)
        entities.file_paths = list(set(file_matches))

        # Extract schedule expressions
        schedule_matches = self._SCHEDULE_PATTERN.findall(request_lower)
        for match in schedule_matches:
            count = match[0] or "1"
            unit = match[1]
            entities.schedule_expressions.append(f"every {count} {unit}s")

        # Extract principals
        principal_matches = self._PRINCIPAL_PATTERN.findall(request)
        entities.principals = list(set(principal_matches))

        # Extract permissions
        permission_matches = self._PERMISSION_PATTERN.findall(request_lower)
        entities.permissions = list(set(p.upper() for p in permission_matches))

        # Detect file formats
        format_keywords = ["csv", "json", "parquet",
                           "avro", "orc", "delta", "xml"]
        for fmt in format_keywords:
            if fmt in request_lower:
                entities.file_formats.append(fmt.upper())

        return entities

    def _detect_platform(self, request_lower: str, context: dict[str, Any]) -> Platform:
        """Detect the target platform."""
        # Check context first
        if "platform" in context:
            platform_str = context["platform"].lower()
            if "fabric" in platform_str:
                return Platform.FABRIC
            if "databricks" in platform_str:
                return Platform.DATABRICKS

        # Check request text
        databricks_score = sum(
            1 for kw in self._PLATFORM_KEYWORDS[Platform.DATABRICKS]
            if kw in request_lower
        )
        fabric_score = sum(
            1 for kw in self._PLATFORM_KEYWORDS[Platform.FABRIC]
            if kw in request_lower
        )

        if databricks_score > fabric_score:
            return Platform.DATABRICKS
        if fabric_score > databricks_score:
            return Platform.FABRIC
        if databricks_score > 0 and fabric_score > 0:
            return Platform.BOTH

        return Platform.UNSPECIFIED

    def _assess_complexity(
        self,
        request: str,
        intent_type: IntentType,
        entities: ExtractedEntities,
        context: dict[str, Any],
    ) -> ComplexityLevel:
        """Assess the complexity of the request."""
        # Simple heuristics for complexity
        word_count = len(request.split())

        # Check for multiple operations
        operation_indicators = [" and ", " then ",
                                " also ", " after ", " before "]
        multi_operation = any(ind in request.lower()
                              for ind in operation_indicators)

        # Check for conditional logic
        conditional_indicators = ["if ", "when ",
                                  "unless ", "case ", "depending "]
        has_conditionals = any(ind in request.lower()
                               for ind in conditional_indicators)

        # Check for vague language
        vague_terms = ["something", "some kind",
                       "like", "maybe", "perhaps", "might"]
        is_vague = any(term in request.lower() for term in vague_terms)

        # Check for missing critical information
        missing_info = False
        if intent_type in (IntentType.INGEST_DATA, IntentType.TRANSFORM_DATA):
            if not entities.tables and not entities.file_paths:
                missing_info = True
        if intent_type == IntentType.GRANT_ACCESS:
            if not entities.principals or not entities.permissions:
                missing_info = True

        # Determine complexity
        if is_vague or missing_info:
            return ComplexityLevel.AMBIGUOUS
        if multi_operation or has_conditionals or word_count > 100:
            return ComplexityLevel.COMPLEX
        if len(entities.tables) > 2 or len(entities.file_formats) > 1 or word_count > 50:
            return ComplexityLevel.MODERATE
        return ComplexityLevel.SIMPLE

    def _determine_task_mode(
        self,
        intent_type: IntentType,
        complexity: ComplexityLevel,
        entities: ExtractedEntities,
    ) -> tuple[str, str | None]:
        """Determine task mode and operation type."""
        # Map intent to task mode
        mode_mapping = {
            IntentType.LIST_RESOURCES: ("list", None),
            IntentType.DESCRIBE_RESOURCE: ("read", "get_schema"),
            IntentType.PREVIEW_DATA: ("read", "preview_table"),
            IntentType.QUERY_DATA: ("execute_code", "execute_query"),
            IntentType.EXECUTE_CODE: ("execute_code", None),
            IntentType.GENERATE_CODE: ("generate_code", None),
            IntentType.OPTIMIZE_CODE: ("generate_code", None),
            IntentType.GRANT_ACCESS: ("manage", "grant_permission"),
            IntentType.REVOKE_ACCESS: ("manage", "revoke_permission"),
            IntentType.CREATE_TABLE: ("manage", "create_table"),
            IntentType.SCHEDULE_JOB: ("generate_code", None),
        }

        task_mode, operation_type = mode_mapping.get(
            intent_type, ("generate_code", None)
        )

        # Override for list operations
        if intent_type == IntentType.LIST_RESOURCES:
            if entities.schemas:
                operation_type = "list_tables"
            elif entities.catalogs:
                operation_type = "list_schemas"
            else:
                operation_type = "list_catalogs"

        return task_mode, operation_type

    def _check_clarifications(
        self,
        intent_type: IntentType,
        entities: ExtractedEntities,
        complexity: ComplexityLevel,
        request: str,
    ) -> list[ClarificationRequest]:
        """Check if clarification is needed and generate questions."""
        clarifications: list[ClarificationRequest] = []

        if complexity == ComplexityLevel.AMBIGUOUS:
            # Generic clarification for vague requests
            clarifications.append(ClarificationRequest(
                question="Could you provide more specific details about what you'd like to accomplish?",
                required=True,
            ))

        # Intent-specific clarifications
        if intent_type == IntentType.INGEST_DATA:
            if not entities.tables and not entities.file_paths:
                clarifications.append(ClarificationRequest(
                    question="What is the source of the data you want to ingest?",
                    options=["File(s) from storage",
                             "Database table", "Streaming source", "API"],
                    field_name="source_type",
                    required=True,
                ))
            if not entities.file_formats:
                clarifications.append(ClarificationRequest(
                    question="What format is the source data in?",
                    options=["CSV", "JSON", "Parquet", "Delta", "Avro"],
                    field_name="file_format",
                    required=False,
                ))

        if intent_type == IntentType.GRANT_ACCESS:
            if not entities.principals:
                clarifications.append(ClarificationRequest(
                    question="Which user, group, or service principal should receive access?",
                    field_name="principal",
                    required=True,
                ))
            if not entities.permissions:
                clarifications.append(ClarificationRequest(
                    question="What permissions should be granted?",
                    options=["SELECT (read)", "MODIFY (read/write)",
                                      "ALL (full access)", "CREATE (create objects)"],
                    field_name="permission",
                    required=True,
                ))

        if intent_type == IntentType.SCHEDULE_JOB:
            if not entities.schedule_expressions:
                clarifications.append(ClarificationRequest(
                    question="How frequently should the job run?",
                    options=["Hourly", "Daily", "Weekly", "Custom schedule"],
                    field_name="schedule",
                    required=True,
                ))

        if intent_type == IntentType.CREATE_PIPELINE:
            if not entities.tables:
                clarifications.append(ClarificationRequest(
                    question="What are the source tables for this pipeline?",
                    field_name="source_tables",
                    required=False,
                ))

        return clarifications

    def _infer_context(
        self,
        intent_type: IntentType,
        entities: ExtractedEntities,
        platform: Platform,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Infer additional context from the request."""
        inferred: dict[str, Any] = {}

        # Infer default platform settings
        if platform == Platform.UNSPECIFIED:
            inferred["default_platform"] = "databricks"
        elif platform == Platform.BOTH:
            inferred["multi_platform"] = True

        # Infer data flow direction
        if intent_type == IntentType.INGEST_DATA:
            inferred["data_flow"] = "source_to_target"
            if entities.file_formats:
                inferred["source_format"] = entities.file_formats[0]

        if intent_type == IntentType.TRANSFORM_DATA:
            inferred["data_flow"] = "transform"
            inferred["requires_intermediate_tables"] = len(entities.tables) > 2

        # Infer environment sensitivity
        if any(word in str(context).lower() for word in ["prod", "production", "live"]):
            inferred["environment"] = "production"
            inferred["requires_approval"] = True
        else:
            inferred["environment"] = "sandbox"
            inferred["requires_approval"] = False

        # Infer operation category
        if intent_type in (IntentType.GRANT_ACCESS, IntentType.REVOKE_ACCESS):
            inferred["is_security_operation"] = True
            inferred["audit_required"] = True

        if intent_type in (IntentType.LIST_RESOURCES, IntentType.DESCRIBE_RESOURCE, IntentType.PREVIEW_DATA):
            inferred["is_read_only"] = True

        return inferred

    def _generate_safety_notes(
        self,
        intent_type: IntentType,
        entities: ExtractedEntities,
        request: str,
    ) -> list[str]:
        """Generate safety notes for the request."""
        notes: list[str] = []

        # Check for destructive patterns
        destructive_keywords = ["drop", "delete",
                                "truncate", "remove", "destroy"]
        if any(kw in request for kw in destructive_keywords):
            notes.append(
                "DESTRUCTIVE_OPERATION: This request may involve data deletion. Approval required.")

        # Check for production references
        prod_keywords = ["production", "prod", "live", "critical"]
        if any(kw in request for kw in prod_keywords):
            notes.append(
                "PRODUCTION_ENVIRONMENT: Production environment detected. Enhanced validation required.")

        # Check for security operations
        if intent_type in (IntentType.GRANT_ACCESS, IntentType.REVOKE_ACCESS):
            notes.append(
                "SECURITY_OPERATION: This request modifies access controls. Audit trail required.")

        # Check for broad permissions
        if "ALL" in entities.permissions or "all" in entities.permissions:
            notes.append(
                "BROAD_PERMISSION: Granting ALL permissions is a high-risk operation.")

        # Check for unfiltered data access
        if intent_type == IntentType.EXPORT_DATA:
            notes.append(
                "DATA_EXPORT: Data export detected. Verify data sensitivity classification.")

        return notes


# ── Convenience function ────────────────────────────────────────────────


def parse_intent(request: str, context: dict[str, Any] | None = None) -> ParsedIntent:
    """Parse a user request into structured intent.

    This is the main entry point for intent parsing.
    """
    parser = IntentParser()
    return parser.parse(request, context)
