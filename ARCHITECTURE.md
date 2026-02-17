# SYSTEM ARCHITECTURE — AADAP

## Layered Architecture (6 Layers)

L6 Presentation — Next.js UI, REST API, Email  
L5 Orchestration — LangGraph Orchestrator, Scheduler, Approval Controller  
L4 Agent Layer — Developer, Validation, Optimization agents  
L3 Integration — Azure AI Foundry, Databricks API, Tool Registry  
L2 Memory — Redis, PostgreSQL + pgvector, Archive, Knowledge Graph  
L1 Infrastructure — AKS, Azure Monitor, Key Vault, Network Security

## Trust Boundaries
- Agents are untrusted workers
- Orchestrator is authoritative
- External systems are hostile by default

## Communication Model
- Orchestrator → Agents: async message + state snapshot
- Orchestrator → Memory: transactional
- No direct agent-to-agent mutation

## Authoritative Task State Machine

STATE_SET_VERSION: v1.0

AUTHORITATIVE STATES (25):
SUBMITTED
PARSING
PARSED
PARSE_FAILED
PLANNING
PLANNED
AGENT_ASSIGNMENT
AGENT_ASSIGNED
IN_DEVELOPMENT
CODE_GENERATED
DEV_FAILED
IN_VALIDATION
VALIDATION_PASSED
VALIDATION_FAILED
OPTIMIZATION_PENDING
IN_OPTIMIZATION
OPTIMIZED
APPROVAL_PENDING
IN_REVIEW
APPROVED
REJECTED
DEPLOYING
DEPLOYED
COMPLETED
CANCELLED

IMPLICIT (NON-STATES):
START, END

Any other state is invalid.

## Safety Architecture
Gate 1: Static analysis (AST)  
Gate 2: Pattern matching  
Gate 3: Semantic risk scoring  
Gate 4: Human approval

No gate may be bypassed.
