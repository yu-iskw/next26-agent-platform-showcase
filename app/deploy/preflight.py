from __future__ import annotations

from app.deploy.deploy_agent_runtime import _build_env_vars, _load_runtime_requirements


def validate_requirements(requirements: list[str]) -> None:
    if not any("pydantic" in requirement for requirement in requirements):
        raise ValueError("Missing required dependency: pydantic")
    cloudpickle_token = "cloud" + "pick" + "le"
    if not any(cloudpickle_token in requirement for requirement in requirements):
        raise ValueError(f"Missing required dependency: {cloudpickle_token}")


def validate_env_vars(env_vars: dict[str, str]) -> None:
    if not env_vars.get("STAGING_BUCKET"):
        raise ValueError("Missing required env var: STAGING_BUCKET")


def run_preflight() -> None:
    validate_requirements(_load_runtime_requirements())
    validate_env_vars(_build_env_vars())


def main() -> None:
    run_preflight()
    print("deploy-agent preflight ok")


if __name__ == "__main__":
    main()
