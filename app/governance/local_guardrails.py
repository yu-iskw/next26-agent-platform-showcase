"""Local policy simulation layer for development and testing.

⚠️  IMPORTANT: This module provides ONLY a development/test simulation.
    It is NOT a substitute for official platform governance features:
      - Vertex AI Agent Gateway  (preview)
      - Vertex AI Semantic Governance  (preview)
      - Vertex AI Model Armor  (GA in some regions)

    Do NOT use this in production as a security control.
    Use it only to:
      1. Validate policy test cases locally before platform enforcement is available.
      2. Document the intended behavior that the platform features will enforce.

See docs/governance-enforcement.md for the full mapping.

Status: runnable-now (local simulation only)
"""
from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Prompt injection / policy evasion patterns
# Mapped to future platform features — see docs/governance-enforcement.md
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bignore\b.{0,30}\b(previous|prior|above|all)\b.{0,30}\b(instructions?|prompts?|rules?)\b", re.IGNORECASE),
    re.compile(r"\breveal\b.{0,30}\b(system\s+prompt|instructions?|configuration)\b", re.IGNORECASE),
    re.compile(r"\bbypass\b.{0,30}\b(safety|rules?|guidelines?|restrictions?)\b", re.IGNORECASE),
    re.compile(r"\bact\s+as\b.{0,30}\b(different|another|new)\b.{0,30}\b(ai|model|assistant|bot)\b", re.IGNORECASE),
    re.compile(r"\bignore\b.{0,30}\bguidelines?\b", re.IGNORECASE),
    re.compile(r"\boverride\b.{0,30}\b(safety|policy|rules?)\b", re.IGNORECASE),
    re.compile(r"\bforget\b.{0,30}\b(your|all).{0,20}\b(instructions?|rules?)\b", re.IGNORECASE),
]

_EXFILTRATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(output|print|show|reveal|expose|dump|send|share)\b.{0,30}\b(customer|user|personal|sensitive)\b.{0,30}\bdata\b", re.IGNORECASE),
    re.compile(r"\b(extract|export|leak)\b.{0,30}\b(database|records?|pii|credentials?)\b", re.IGNORECASE),
    re.compile(r"\b(ignore|bypass)\b.{0,30}\b(privacy|confidential|classified)\b", re.IGNORECASE),
]

_UNSAFE_TOOL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(delete|drop|truncate|destroy)\b.{0,30}\b(all|every|entire)\b.{0,30}\b(data|orders?|records?|tables?)\b", re.IGNORECASE),
    re.compile(r"\b(approve|authorize)\b.{0,30}\b(all|every)\b.{0,30}\b(orders?|requests?|workflows?)\b.{0,20}\bwithout\b", re.IGNORECASE),
]


def is_content_blocked(content: str) -> bool:
    """Return True if content matches any local guardrail pattern.

    This is a development/test simulation. In production, use Model Armor or Agent Gateway.
    """
    for pattern in _INJECTION_PATTERNS + _EXFILTRATION_PATTERNS + _UNSAFE_TOOL_PATTERNS:
        if pattern.search(content):
            return True
    return False


def classify_content(content: str) -> dict[str, Any]:
    """Return a classification dict explaining which (if any) rule triggered.

    Useful for debugging guardrail behavior in tests.
    """
    triggered: list[str] = []

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(content):
            triggered.append(f"prompt_injection: {pattern.pattern[:60]}...")

    for pattern in _EXFILTRATION_PATTERNS:
        if pattern.search(content):
            triggered.append(f"data_exfiltration: {pattern.pattern[:60]}...")

    for pattern in _UNSAFE_TOOL_PATTERNS:
        if pattern.search(content):
            triggered.append(f"unsafe_tool_invocation: {pattern.pattern[:60]}...")

    return {
        "blocked": bool(triggered),
        "triggered_rules": triggered,
        "content_preview": content[:100],
        "note": (
            "This is a local simulation for dev/test only. "
            "Map to platform features: Agent Gateway, Semantic Governance, Model Armor."
        ),
    }


def validate_tool_call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Validate a tool call for obvious policy violations.

    Returns {'allowed': True} or {'allowed': False, 'reason': '...'}.
    """
    # Prevent bulk-delete operations
    if tool_name in ("delete_purchase_order", "bulk_delete_orders"):
        return {
            "allowed": False,
            "reason": f"Tool {tool_name!r} is not permitted via agent invocation. Use admin console.",
        }

    # Prevent approving all orders without review
    if tool_name == "approve_workflow":
        approver = arguments.get("approver", "")
        if not approver or approver in ("system", "auto", "bypass"):
            return {
                "allowed": False,
                "reason": "approve_workflow requires a named human approver.",
            }

    return {"allowed": True}
