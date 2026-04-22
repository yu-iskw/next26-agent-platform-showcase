from __future__ import annotations

from typing import Any

from vertexai import Client

from .config import settings


def init_vertex_client() -> Client:
    return Client(project=settings.project_id, location=settings.location)


def generate_memory(agent_resource_name: str, conversation_snippet: str, user_id: str) -> dict[str, Any]:
    """Generate a long-term memory using Agent Platform Memory Bank.

    This helper is intentionally thin because the exact Memory Bank shape is still evolving.
    It provides one place to adapt your code as the API surface settles.
    """
    client = init_vertex_client()
    response = client.agent_engines.memories.generate(
        name=agent_resource_name,
        user_id=user_id,
        text=conversation_snippet,
    )
    return {"status": "generated", "response": str(response)}


def retrieve_memories(agent_resource_name: str, query: str, user_id: str) -> dict[str, Any]:
    """Retrieve long-term memories for a user.

    Adjust request fields to match your currently enabled API version.
    """
    client = init_vertex_client()
    response = client.agent_engines.memories.retrieve(
        name=agent_resource_name,
        user_id=user_id,
        query=query,
    )
    return {"status": "retrieved", "response": str(response)}
