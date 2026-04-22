"""A2A protocol models — typed request/response structures for inter-agent communication.

This implements an A2A-style adapter layer. It is NOT a claim of full official
A2A runtime compatibility. It demonstrates the agent-card pattern and delegation
protocol sufficient for local demo and for wiring into official Gemini Enterprise
A2A when preview access is granted.

Status: runnable-now (local mock mode)
         preview-scaffold (Gemini Enterprise A2A registration)

WARNING: Gemini Enterprise A2A registration is a preview feature. This module
provides the contract surface; actual registration requires preview program access.
See docs/a2a-architecture.md.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class A2ACapabilityType(str, Enum):
    TEXT = "text"
    TOOL_CALL = "tool_call"
    STRUCTURED_DATA = "structured_data"


class A2ATaskStatus(str, Enum):
    SUBMITTED = "submitted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DELEGATED = "delegated"


class A2ACapability(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)


class A2AAgentCard(BaseModel):
    """Agent card — the machine-readable identity and capability manifest for an agent.

    Follows the pattern described in Google Cloud Next '26 A2A documentation.
    See docs/examples/retailops-agent-card.json for the serialized form.
    """

    agent_id: str
    agent_name: str
    description: str
    version: str = "1.0.0"
    provider: str = ""
    endpoint_url: str = ""
    capabilities: list[A2ACapability] = Field(default_factory=list)
    supported_intents: list[str] = Field(default_factory=list)
    auth_type: str = "bearer"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class A2ATaskRequest(BaseModel):
    """A task request sent to an external agent."""

    task_id: str = Field(default_factory=lambda: f"task-{uuid.uuid4().hex[:10]}")
    intent: str
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    requesting_agent_id: str = ""
    timeout_seconds: float = 30.0


class A2ATaskResponse(BaseModel):
    """Response from an external agent."""

    task_id: str
    status: A2ATaskStatus
    result: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    correlation_id: str = ""
    responding_agent_id: str = ""
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class A2ARoutingRule(BaseModel):
    """Maps an intent pattern to an external agent."""

    intent_prefix: str
    target_agent_id: str
    priority: int = 0
    enabled: bool = True
