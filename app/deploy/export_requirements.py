from __future__ import annotations

import argparse
from pathlib import Path

TARGET_TO_REQUIREMENTS: dict[str, tuple[Path, str]] = {
    "agent-runtime": (
        Path("app/deploy/runtime.requirements.txt"),
        "google-cloud-aiplatform[agent_engines,adk]>=1.112\n"
        "cloudpickle>=3.1.0\n"
        "google-auth>=2.29.0\n"
        "httpx>=0.27.2\n"
        "pandas>=2.2.2\n"
        "pydantic>=2.9.0\n",
    ),
    "tool-api": (
        Path("cloudrun/tool_api/requirements.txt"),
        "fastapi>=0.115.0\nuvicorn[standard]>=0.30.6\ngoogle-cloud-firestore>=2.16.0\npydantic>=2.9.0\nh11>=0.16.0\n",
    ),
}


def resolve_target(target: str) -> tuple[Path, str]:
    try:
        return TARGET_TO_REQUIREMENTS[target]
    except KeyError as exc:
        valid_targets = ", ".join(sorted(TARGET_TO_REQUIREMENTS))
        raise ValueError(f"Unknown target '{target}'. Expected one of: {valid_targets}") from exc


def write_requirements(output_path: Path, content: str) -> Path:
    output_path.write_text(content, encoding="utf-8")
    return output_path


def export_target(target: str) -> Path:
    output_path, content = resolve_target(target)
    return write_requirements(output_path, content)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export runtime requirement files from predefined targets.")
    parser.add_argument("--target", required=True, choices=sorted(TARGET_TO_REQUIREMENTS))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = export_target(args.target)
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
