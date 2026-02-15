# PHASE 4 — AGENT IMPLEMENTATION CONTRACTS

## Objective
Implement domain-specific agents.

## Agents in Scope
- Orchestrator Agent (decision logic)
- Databricks Python Agent
- Validation Agent
- PySpark Optimization Agent

## Modules
- agents/orchestrator_agent.py
- agents/developer_agent.py
- agents/validation_agent.py
- agents/optimization_agent.py
- agents/prompts/

## Invariants
- Agents must follow declared reasoning frameworks
- Max 3 self-correction attempts
- Output must conform to schema
- No direct execution without orchestrator authorization

## Required Capabilities
- Structured JSON outputs
- Prompt templates with role + constraints
- Self-correction & escalation logic

## Non-Goals
- No approval logic
- No UI integration
- No memory governance logic

## Required Tests
- Prompt format compliance
- Error recovery paths
- Escalation after retries

## Definition of Done
- Each agent processes sample input correctly
- Retry and escalation work as specified
