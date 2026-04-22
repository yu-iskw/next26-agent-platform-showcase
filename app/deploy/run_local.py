from __future__ import annotations

import asyncio

from google.adk.runners import InMemoryRunner

from app.agents.retailops_agent import app


async def main() -> None:
    runner = InMemoryRunner(app=app)
    prompts = [
        "What are the top 3 products by units sold?",
        "Which backpacks are low on stock?",
        "Recommend a reorder for the Trail Backpack Pro.",
    ]
    for prompt in prompts:
        print(f"\n=== USER ===\n{prompt}")
        response = await runner.run_debug(prompt)
        print(f"\n=== AGENT ===\n{response}")


if __name__ == "__main__":
    asyncio.run(main())
