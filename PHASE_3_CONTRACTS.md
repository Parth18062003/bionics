# PHASE 3 — AGENT FRAMEWORK CONTRACTS

## Objective
Create a reusable, governed agent execution framework.

## Modules in Scope
- BaseAgent abstraction
- Agent lifecycle management
- Agent pool manager
- Health check protocol
- Tool registry & permission enforcement
- Token accounting

## Modules
- agents/base.py
- agents/pool_manager.py
- agents/health.py
- agents/token_tracker.py
- agents/tools/registry.py
- integrations/llm_client.py

## Invariants
- Agents are stateless workers
- No agent bypasses orchestrator
- Tool access must be explicitly granted
- Token budget must be enforced per task

## Interfaces
- `accept_task(context) -> bool`
- `execute(context) -> result`
- `health_check() -> status`
- `register_tools()`

## Non-Goals
- No domain-specific logic
- No Databricks calls
- No memory persistence logic

## Required Tests
- Lifecycle transitions
- Tool permission enforcement
- Token exhaustion handling
- Health check timeouts

## Definition of Done
- Agents can be created, pooled, health-checked
- Forbidden tools raise exceptions
- Token limits enforced
