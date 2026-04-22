# Rollout notes

## What should work end-to-end now

- local ADK run
- BigQuery data seeding
- Cloud Run tool API deployment
- Agent Runtime deployment using the Python SDK
- SDK-based evaluation
- hybrid eval gate artifacts under `eval/results/`
- judge calibration script for preview autorater APIs

## What probably requires org/project access or preview enrollment

- Agent Gateway
- Semantic governance
- Model Armor attached through Agent Gateway
- some console-native evaluation simulation flows
- MCP-first runtime integrations depending on org rollout

## Why the design uses REST tools first

REST keeps the example runnable in any standard Google Cloud project. When remote MCP is ready in your environment, you can preserve:

- the domain tool contract
- the Cloud Run deployment
- the security boundary

and only change the transport and tool manifest layer.
