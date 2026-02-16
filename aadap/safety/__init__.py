"""
AADAP — Safety & Approval System (Phase 5)
=============================================
Multi-layer defense and approval workflow.

Safety Architecture (ARCHITECTURE.md):
    Gate 1: Static analysis (AST)
    Gate 2: Pattern matching
    Gate 3: Semantic risk scoring
    Gate 4: Human approval

No gate may be bypassed.

Public API:
    evaluate, request_approval, approve, reject
"""

from aadap.safety.static_analysis import StaticAnalyzer
from aadap.safety.pattern_matcher import PatternMatcher
from aadap.safety.semantic_analysis import SafetyPipeline, SemanticAnalyzer
from aadap.safety.approval_engine import ApprovalEngine, ApprovalStatus
from aadap.safety.routing import ApprovalRouter, RoutingAction

__all__ = [
    "StaticAnalyzer",
    "PatternMatcher",
    "SemanticAnalyzer",
    "SafetyPipeline",
    "ApprovalEngine",
    "ApprovalStatus",
    "ApprovalRouter",
    "RoutingAction",
]
