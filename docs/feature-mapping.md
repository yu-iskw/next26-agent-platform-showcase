# Feature mapping

| Capability announced at Next '26              | Included here | Implementation detail                                                           | Maturity                                             |
| --------------------------------------------- | ------------: | ------------------------------------------------------------------------------- | ---------------------------------------------------- |
| Gemini Enterprise Agent Platform              |            ✅ | ADK app + Agent Runtime deploy script                                           | Public docs                                          |
| Agent Development Kit graph / workflow agents |            ✅ | Root + specialist sub-agents, sequential-friendly design                        | Public docs                                          |
| Agent-to-Agent orchestration                  |         ✅/⚠️ | Multi-agent composition now; external A2A as future extension                   | Mixed                                                |
| Agent Registry                                |            ⚠️ | Expected post-deploy console registration flow                                  | Console / platform                                   |
| Agent Identity                                |            ✅ | `identity_type=AGENT_IDENTITY` in runtime deployment                            | Public docs                                          |
| Agent Gateway                                 |            ⚠️ | Example config only                                                             | Private preview                                      |
| Model Armor integration                       |            ⚠️ | Example config attached to gateway                                              | Preview/private preview path                         |
| Agent Observability                           |            ✅ | Telemetry env vars + GCP logs/traces/metrics                                    | Public docs                                          |
| Agent Evaluation                              |            ✅ | Eval SDK script and sample dataset                                              | Public docs                                          |
| Simulated sessions                            |            ⚠️ | Console-first note and workflow guide                                           | Preview                                              |
| Memory Bank                                   |         ✅/⚠️ | Runtime-ready and helper patterns                                               | Public docs; feature setup still required            |
| Sessions                                      |            ✅ | Local runner and deployed runtime flow                                          | Public docs                                          |
| Long-running agents                           |         ✅/⚠️ | Order / approval workflow code pattern; runtime semantics depend on environment | Partial                                              |
| BigQuery Data Agent style analytics           |            ✅ | BigQuery tools and warehouse seed                                               | Public                                               |
| Knowledge Catalog                             |            ⚠️ | Architectural hook / migration notes                                            | Emerging                                             |
| Smart Storage                                 |            ⚠️ | Storage-first corpus layout; future auto-tagging integration                    | Preview                                              |
| Cloud Run integration                         |            ✅ | Tool API on Cloud Run                                                           | Public                                               |
| Cloud Run remote MCP                          |            ⚠️ | Migration notes from REST tool API                                              | GA platform feature, but repo keeps REST as baseline |
