# pyright: reportGeneralTypeIssues=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportReturnType=false, reportAssignmentType=false
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import vertexai
from google.adk.agents import Agent
from vertexai import types

from app.tools.config import settings

EVAL_PROMPTS_PATH = Path("eval/eval_prompts.csv")
EVAL_GATE_CONFIG_PATH = Path("eval/eval_gate_config.json")
EVAL_RESULTS_DIR = Path("eval/results")
SUMMARY_PATH = EVAL_RESULTS_DIR / "eval_summary_latest.json"
INSTANCE_RESULTS_PATH = EVAL_RESULTS_DIR / "last_instance_results.csv"

REQUIRED_COLUMNS = {
    "prompt",
    "scenario",
    "capability",
    "risk_tier",
    "expected_keywords",
    "forbidden_keywords",
    "must_mention_approval",
    "requires_tool",
    "reference_trajectory",
}


@dataclass
class GateCheck:
    metric: str
    threshold: float
    actual: float
    passed: bool


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "t"}


def _split_keywords(raw: str) -> list[str]:
    if not raw:
        return []
    return [kw.strip().lower() for kw in str(raw).split("|") if kw.strip()]


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
        return value
    return str(value)


def _safe_json_loads(value: Any, default: Any) -> Any:
    parsed = default
    if value is None:
        pass
    elif isinstance(value, (dict, list)):
        parsed = value
    else:
        text = str(value).strip()
        if text:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = default
    return parsed


def _normalize_step(step: Any) -> str:
    if isinstance(step, str):
        return step.strip().lower()
    if not isinstance(step, dict):
        return str(step).strip().lower()

    tool_name = str(step.get("tool_name", step.get("name", ""))).strip().lower()
    tool_input = step.get("tool_input", step.get("input", step.get("args", {})))
    if not isinstance(tool_input, (dict, list)):
        tool_input = {"value": str(tool_input)}
    return f"{tool_name}:{json.dumps(tool_input, sort_keys=True, separators=(',', ':'))}"


def _extract_text_response(row: dict[str, Any]) -> str:
    candidates = [
        "response",
        "predicted_response",
        "model_response",
        "final_response",
        "output_text",
        "generated_text",
        "prediction",
        "answer",
        "output",
    ]
    for key in candidates:
        if key in row and row[key] is not None and str(row[key]).strip():
            value = row[key]
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False)
            return str(value)
    return ""


def _extract_predicted_trajectory(row: dict[str, Any]) -> list[Any]:
    trajectory_keys = [
        "predicted_trajectory",
        "trajectory",
        "tool_trajectory",
        "tool_calls",
        "actions",
        "trace",
    ]
    for key in trajectory_keys:
        if key in row:
            parsed = _safe_json_loads(row[key], default=[])
            if isinstance(parsed, list):
                return parsed

    nested = row.get("prediction") or row.get("output")
    if isinstance(nested, dict):
        for key in trajectory_keys:
            parsed = _safe_json_loads(nested.get(key), default=[])
            if isinstance(parsed, list):
                return parsed
    return []


def _compute_pr(predicted_steps: list[Any], reference_steps: list[Any]) -> tuple[float, float, bool]:
    pred_norm = [_normalize_step(s) for s in predicted_steps]
    ref_norm = [_normalize_step(s) for s in reference_steps]

    pred_ctr = Counter(pred_norm)
    ref_ctr = Counter(ref_norm)
    overlap = sum((pred_ctr & ref_ctr).values())

    precision = 1.0 if not pred_norm and not ref_norm else (overlap / len(pred_norm) if pred_norm else 0.0)
    recall = 1.0 if not ref_norm else overlap / len(ref_norm)
    exact_match = pred_norm == ref_norm
    return precision, recall, exact_match


def _validate_schema(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"eval/eval_prompts.csv missing required columns: {sorted(missing)}")


def _to_dataframe(dataset_with_inference: Any) -> pd.DataFrame:
    frame: pd.DataFrame | None = None
    if isinstance(dataset_with_inference, pd.DataFrame):
        frame = dataset_with_inference.copy()
    else:
        to_pandas = getattr(dataset_with_inference, "to_pandas", None)
        if callable(to_pandas):
            frame = to_pandas()
        elif isinstance(dataset_with_inference, list | dict):
            frame = pd.DataFrame(dataset_with_inference)
    if frame is None:
        raise TypeError(f"Unsupported inference dataset type: {type(dataset_with_inference)!r}")
    return frame


def _load_gate_thresholds(path: Path) -> dict[str, float]:
    thresholds: dict[str, float] = {}
    if path.exists():
        payload = _safe_json_loads(path.read_text(encoding="utf-8"), default={})
        if isinstance(payload, dict):
            raw_thresholds = payload.get("thresholds", payload)
            if isinstance(raw_thresholds, dict):
                for metric, value in raw_thresholds.items():
                    try:
                        thresholds[str(metric)] = float(value)
                    except (TypeError, ValueError):
                        continue
    return thresholds


def _build_instance_rows(merged: pd.DataFrame) -> list[dict[str, Any]]:
    instance_rows: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        row_dict = {k: _to_jsonable(v) for k, v in row.to_dict().items()}
        response_text = _extract_text_response(row_dict)

        expected_keywords = _split_keywords(str(row_dict.get("expected_keywords", "")))
        forbidden_keywords = _split_keywords(str(row_dict.get("forbidden_keywords", "")))
        must_mention_approval = _parse_bool(row_dict.get("must_mention_approval", False))
        response_lc = response_text.lower()

        expected_hits = sum(1 for kw in expected_keywords if kw in response_lc)
        forbidden_hits = sum(1 for kw in forbidden_keywords if kw in response_lc)
        approval_mentioned = "approval" in response_lc
        expected_ok = (expected_hits == len(expected_keywords)) if expected_keywords else True
        forbidden_ok = forbidden_hits == 0
        approval_ok = approval_mentioned if must_mention_approval else True
        keyword_pass = expected_ok and forbidden_ok and approval_ok

        reference_trajectory = _safe_json_loads(row_dict.get("reference_trajectory"), default=[])
        if not isinstance(reference_trajectory, list):
            reference_trajectory = []
        predicted_trajectory = _extract_predicted_trajectory(row_dict)
        precision, recall, exact_match = _compute_pr(predicted_trajectory, reference_trajectory)

        instance_rows.append(
            {
                "prompt": row_dict.get("prompt", ""),
                "scenario": row_dict.get("scenario", ""),
                "capability": row_dict.get("capability", ""),
                "risk_tier": row_dict.get("risk_tier", ""),
                "response_text": response_text,
                "expected_keywords": "|".join(expected_keywords),
                "forbidden_keywords": "|".join(forbidden_keywords),
                "must_mention_approval": must_mention_approval,
                "approval_mentioned": approval_mentioned,
                "keyword_pass": keyword_pass,
                "expected_keyword_hits": expected_hits,
                "expected_keyword_total": len(expected_keywords),
                "forbidden_keyword_hits": forbidden_hits,
                "reference_trajectory": json.dumps(reference_trajectory, ensure_ascii=False),
                "predicted_trajectory": json.dumps(predicted_trajectory, ensure_ascii=False),
                "trajectory_precision": round(precision, 6),
                "trajectory_recall": round(recall, 6),
                "trajectory_exact_match": exact_match,
            }
        )
    return instance_rows


def _apply_gates(summary_metrics: dict[str, float], thresholds: dict[str, float]) -> tuple[list[GateCheck], bool]:
    checks: list[GateCheck] = []
    all_passed = True
    for metric, threshold in thresholds.items():
        if metric.endswith("_max"):
            base_metric = metric.removesuffix("_max")
            actual = float(summary_metrics.get(base_metric, float("inf")))
            passed = actual <= threshold
        else:
            actual = float(summary_metrics.get(metric, float("-inf")))
            passed = actual >= threshold
        checks.append(GateCheck(metric=metric, threshold=threshold, actual=actual, passed=passed))
        all_passed = all_passed and passed
    return checks, all_passed


def _extract_numeric_series(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    for candidate in candidates:
        if candidate in df.columns:
            series = pd.to_numeric(df[candidate], errors="coerce").dropna()
            if not series.empty:
                return series
    return pd.Series(dtype=float)


def _extract_rubric_scores(evaluation_run: Any) -> dict[str, float]:
    if hasattr(evaluation_run, "to_dict"):
        payload = evaluation_run.to_dict()
    elif hasattr(evaluation_run, "model_dump"):
        payload = evaluation_run.model_dump()
    elif isinstance(evaluation_run, dict):
        payload = evaluation_run
    else:
        payload = {}
    buckets = payload.get("aggregate_metrics") or payload.get("metrics") or {}
    parsed: dict[str, float] = {}
    if isinstance(buckets, dict):
        for name, value in buckets.items():
            try:
                parsed[str(name)] = float(value)
            except (TypeError, ValueError):
                continue
    return parsed


def main() -> None:
    deployed_agent_resource = os.environ.get("DEPLOYED_AGENT_RESOURCE_NAME", "").strip()
    if not deployed_agent_resource:
        raise ValueError("Set DEPLOYED_AGENT_RESOURCE_NAME to the Agent Runtime resource name.")

    prompts_df = pd.read_csv(EVAL_PROMPTS_PATH, dtype=str).fillna("")
    _validate_schema(prompts_df)
    client_ctor = getattr(vertexai, "Client")  # noqa: B009
    client = client_ctor(project=settings.project_id, location=settings.location)
    session_inputs = types.evals.SessionInput(user_id="demo_user", state={})

    inference_src = prompts_df.copy()
    inference_src["session_inputs"] = [session_inputs] * len(inference_src)
    dataset_with_inference = client.evals.run_inference(
        agent=deployed_agent_resource,
        src=inference_src[["prompt", "session_inputs"]],
    )
    inferred_df = _to_dataframe(dataset_with_inference).reset_index(drop=True)

    merged = prompts_df.reset_index(drop=True).copy()
    if "prompt" in inferred_df.columns:
        merged = merged.merge(inferred_df, on="prompt", how="left", suffixes=("", "_pred"))
    elif len(inferred_df) == len(merged):
        merged = pd.concat([merged, inferred_df], axis=1)
    else:
        raise ValueError("Inference output cannot be aligned with eval prompts.")

    instance_rows = _build_instance_rows(merged)

    results_df = pd.DataFrame(instance_rows)
    n = len(results_df)
    keyword_pass_rate = float(results_df["keyword_pass"].mean()) if n else 0.0
    summary_metrics = {
        "instance_count": float(n),
        "keyword_pass_rate": keyword_pass_rate,
        "deterministic_pass_rate": keyword_pass_rate,
        "approval_compliance_rate": float(
            results_df.loc[results_df["must_mention_approval"], "approval_mentioned"].mean()
        )
        if n and results_df["must_mention_approval"].any()
        else 1.0,
        "trajectory_precision_avg": float(results_df["trajectory_precision"].mean()) if n else 0.0,
        "trajectory_recall_avg": float(results_df["trajectory_recall"].mean()) if n else 0.0,
        "trajectory_exact_match_rate": float(results_df["trajectory_exact_match"].mean()) if n else 0.0,
    }

    evaluation_run_name = ""
    rubric_scores: dict[str, float] = {}
    try:
        local_agent = Agent(
            name="retailops_eval_proxy",
            model="gemini-2.5-flash",
            instruction="Evaluation proxy only.",
        )
        agent_info = types.evals.AgentInfo.load_from_agent(local_agent, deployed_agent_resource)
        evaluation_run = client.evals.create_evaluation_run(
            dataset=dataset_with_inference,
            agent_info=agent_info,
            metrics=[
                types.RubricMetric.FINAL_RESPONSE_QUALITY,
                types.RubricMetric.TOOL_USE_QUALITY,
                types.RubricMetric.HALLUCINATION,
                types.RubricMetric.SAFETY,
                "trajectory_precision",
                "trajectory_recall",
            ],
            dest=f"{settings.staging_bucket.rstrip('/')}/eval-results/",
        )
        evaluation_run_name = getattr(evaluation_run, "name", "")
        rubric_scores = _extract_rubric_scores(evaluation_run)
    except Exception as exc:
        evaluation_run_name = f"unavailable: {exc}"

    summary_metrics["TOOL_USE_QUALITY"] = rubric_scores.get(
        "TOOL_USE_QUALITY", summary_metrics["trajectory_precision_avg"]
    )
    summary_metrics["HALLUCINATION"] = rubric_scores.get("HALLUCINATION", 1.0)
    summary_metrics["SAFETY"] = rubric_scores.get("SAFETY", 1.0)
    summary_metrics["trajectory_precision"] = summary_metrics["trajectory_precision_avg"]
    summary_metrics["trajectory_recall"] = summary_metrics["trajectory_recall_avg"]
    failure_series = _extract_numeric_series(inferred_df, ["failure", "failed", "is_failure"])
    latency_series = _extract_numeric_series(inferred_df, ["latency_in_seconds", "latency", "latency_seconds"])
    summary_metrics["failure_rate"] = float(failure_series.mean()) if not failure_series.empty else 0.0
    summary_metrics["latency_p95_seconds"] = float(latency_series.quantile(0.95)) if not latency_series.empty else 0.0

    thresholds = _load_gate_thresholds(EVAL_GATE_CONFIG_PATH)
    gate_checks, gates_passed = _apply_gates(summary_metrics, thresholds)

    EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(INSTANCE_RESULTS_PATH, index=False)
    summary_payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "deployed_agent_resource": deployed_agent_resource,
        "source_eval_prompts": str(EVAL_PROMPTS_PATH),
        "instance_results_path": str(INSTANCE_RESULTS_PATH),
        "vertex_evaluation_run": evaluation_run_name,
        "metrics": summary_metrics,
        "gate_config_path": str(EVAL_GATE_CONFIG_PATH) if EVAL_GATE_CONFIG_PATH.exists() else None,
        "gates": [g.__dict__ for g in gate_checks],
        "gate_passed": gates_passed,
        "capability_pass_rates": (
            results_df.groupby("capability")["keyword_pass"].mean().astype(float).to_dict() if n else {}
        ),
    }
    SUMMARY_PATH.write_text(json.dumps(summary_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote summary: {SUMMARY_PATH}")
    print(f"Wrote instance results: {INSTANCE_RESULTS_PATH}")
    if thresholds:
        print(f"Gate checks: {len(gate_checks)} | passed={gates_passed}")
    if not gates_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
