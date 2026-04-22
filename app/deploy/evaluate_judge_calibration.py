# pyright: reportGeneralTypeIssues=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportReturnType=false, reportAssignmentType=false
from __future__ import annotations

import inspect
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.tools.config import settings

INPUT_CSV = Path("eval/judge_calibration.csv")
OUTPUT_JSON = Path("eval/results/judge_calibration_latest.json")
AUTORATER_CONFIG = {"flip_enabled": True, "sampling_count": 4}
CALIBRATION_RUNS = int(os.getenv("JUDGE_CALIBRATION_RUNS", "3"))


@dataclass
class CalibrationSummary:
    status: str
    message: str
    input_path: str
    output_path: str
    rows_total: int
    rows_scored: int
    human_label_column: str | None
    predicted_label_column: str | None
    agreement_rate: float | None
    preview_api_available: bool
    details: dict[str, Any]


def _normalize_winner(value: Any) -> str | None:
    normalized: str | None = None
    if value is None or (isinstance(value, float) and pd.isna(value)):
        pass
    else:
        text = str(value).strip().lower()
        group_map = {
            "a": {"a", "left", "response_a", "model_a", "1", "win_a", "winner_a"},
            "b": {"b", "right", "response_b", "model_b", "2", "win_b", "winner_b"},
            "tie": {"tie", "equal", "draw", "0", "both"},
        }
        normalized = text
        for canonical, aliases in group_map.items():
            if text in aliases:
                normalized = canonical
                break
    return normalized


def _find_first_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lowered = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    return None


def _extract_result_df(result: Any) -> pd.DataFrame | None:
    resolved: pd.DataFrame | None = result if isinstance(result, pd.DataFrame) else None
    for attr in (
        "results_df",
        "result_df",
        "dataframe",
        "df",
        "results",
        "metrics_table",
    ):
        if resolved is not None:
            break
        value = getattr(result, attr, None)
        if isinstance(value, pd.DataFrame):
            resolved = value
    if isinstance(result, dict) and resolved is None:
        for key in (
            "results_df",
            "result_df",
            "dataframe",
            "df",
            "results",
            "metrics_table",
        ):
            value = result.get(key)
            if isinstance(value, pd.DataFrame):
                resolved = value
                break
    return resolved


def _call_eval_task(
    eval_task_cls: Any,
    pairwise_metric_cls: Any,
    autorater_config_cls: Any,
    df: pd.DataFrame,
) -> Any:
    pairwise_metric = pairwise_metric_cls(
        metric="pairwise_quality",
        metric_prompt_template="Choose whether response A, response B, or tie better satisfies the prompt.",
    )
    autorater_config = autorater_config_cls(**AUTORATER_CONFIG)
    task = eval_task_cls(
        dataset=df,
        metrics=[pairwise_metric],
        autorater_config=autorater_config,
    )
    return task.evaluate()


def _run_eval_once(
    eval_task_cls: Any,
    pairwise_metric_cls: Any,
    autorater_config_cls: Any,
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, Any]:
    eval_result = _call_eval_task(eval_task_cls, pairwise_metric_cls, autorater_config_cls, df)
    result_df = _extract_result_df(eval_result) or pd.DataFrame()
    return result_df, eval_result


def _call_evaluate_autorater(evaluate_autorater: Any, pairwise_metric: Any, result_table: Any) -> Any:
    sig = inspect.signature(evaluate_autorater)
    params = set(sig.parameters.keys())
    candidate_payloads = [
        {"evaluate_autorater_input": result_table, "eval_metrics": [pairwise_metric]},
        {"dataset": result_table, "metrics": [pairwise_metric]},
        {"df": result_table, "metrics": [pairwise_metric]},
    ]
    last_error: Exception | None = None
    for payload in candidate_payloads:
        kwargs: dict[str, Any] = {}
        if "project" in params and settings.project_id:
            kwargs["project"] = settings.project_id
        if "location" in params and settings.location:
            kwargs["location"] = settings.location
        for key, value in payload.items():
            if key in params:
                kwargs[key] = value
        missing = [
            name
            for name, meta in sig.parameters.items()
            if meta.default is inspect._empty
            and meta.kind in (meta.POSITIONAL_OR_KEYWORD, meta.KEYWORD_ONLY)
            and name not in kwargs
        ]
        if missing:
            continue
        try:
            return evaluate_autorater(**kwargs)
        except Exception as exc:
            last_error = exc
    if last_error:
        return None
    return None


def _write_summary(summary: CalibrationSummary) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(asdict(summary), indent=2), encoding="utf-8")
    print(json.dumps(asdict(summary), indent=2))


def _to_dict_if_possible(value: Any) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    if hasattr(value, "to_dict"):
        parsed = value.to_dict()
    elif hasattr(value, "model_dump"):
        parsed = value.model_dump()
    elif isinstance(value, dict):
        parsed = value
    return parsed


def _find_predicted_column(df: pd.DataFrame) -> str | None:
    return _find_first_column(df, ["pairwise_choice", "predicted_winner", "winner", "label", "preference"])


def _build_merged(df: pd.DataFrame, human_col: str, pred_series: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "human": df[human_col].map(_normalize_winner),
            "pred": pred_series.map(_normalize_winner),
        }
    ).dropna(subset=["human", "pred"])


def _run_calibration(
    df: pd.DataFrame,
    human_col: str,
    eval_task_cls: Any,
    pairwise_metric_cls: Any,
    autorater_config_cls: Any,
    evaluate_autorater_fn: Any,
) -> CalibrationSummary:
    run_agreements: list[float] = []
    eval_result: Any = None
    result_df = pd.DataFrame()
    pred_col: str | None = None

    for run_idx in range(max(CALIBRATION_RUNS, 1)):
        run_result_df, run_eval_result = _run_eval_once(eval_task_cls, pairwise_metric_cls, autorater_config_cls, df)
        run_pred_col = _find_predicted_column(run_result_df)
        if run_pred_col:
            run_merged = _build_merged(df, human_col, run_result_df[run_pred_col])
            if not run_merged.empty:
                run_agreements.append(float((run_merged["human"] == run_merged["pred"]).mean()))
        if run_idx == 0:
            eval_result = run_eval_result
            result_df = run_result_df
            pred_col = run_pred_col

    if not pred_col:
        pred_col = _find_predicted_column(result_df)
    if not pred_col:
        return CalibrationSummary(
            status="error",
            message="Could not find predicted label column in EvalTask output.",
            input_path=str(INPUT_CSV),
            output_path=str(OUTPUT_JSON),
            rows_total=len(df),
            rows_scored=0,
            human_label_column=human_col,
            predicted_label_column=None,
            agreement_rate=None,
            preview_api_available=True,
            details={
                "result_columns": list(result_df.columns),
                "autorater_config": AUTORATER_CONFIG,
            },
        )

    merged = _build_merged(df, human_col, result_df[pred_col])
    agreement_rate = float((merged["human"] == merged["pred"]).mean()) if not merged.empty else None
    agreement_variance = float(pd.Series(run_agreements).var()) if len(run_agreements) > 1 else 0.0

    pairwise_metric = pairwise_metric_cls(
        metric="pairwise_quality",
        metric_prompt_template="Choose whether response A, response B, or tie better satisfies the prompt.",
    )
    autorater_eval = _call_evaluate_autorater(
        evaluate_autorater_fn,
        pairwise_metric,
        getattr(eval_result, "metrics_table", result_df),
    )
    autorater_output = _to_dict_if_possible(autorater_eval)

    return CalibrationSummary(
        status="ok",
        message="Judge calibration completed.",
        input_path=str(INPUT_CSV),
        output_path=str(OUTPUT_JSON),
        rows_total=len(df),
        rows_scored=len(merged),
        human_label_column=human_col,
        predicted_label_column=pred_col,
        agreement_rate=agreement_rate,
        preview_api_available=True,
        details={
            "autorater_config": AUTORATER_CONFIG,
            "calibration_runs": max(CALIBRATION_RUNS, 1),
            "run_agreements": run_agreements,
            "agreement_variance": agreement_variance,
            "result_columns": list(result_df.columns),
            "human_distribution": merged["human"].value_counts().to_dict(),
            "pred_distribution": merged["pred"].value_counts().to_dict(),
            "autorater_eval": autorater_output,
        },
    )


def main() -> None:
    if not INPUT_CSV.exists():
        _write_summary(
            CalibrationSummary(
                status="error",
                message=f"Input CSV not found: {INPUT_CSV}",
                input_path=str(INPUT_CSV),
                output_path=str(OUTPUT_JSON),
                rows_total=0,
                rows_scored=0,
                human_label_column=None,
                predicted_label_column=None,
                agreement_rate=None,
                preview_api_available=False,
                details={},
            )
        )
        return

    df = pd.read_csv(INPUT_CSV)
    human_col = _find_first_column(df, ["human_label", "human_preference", "winner", "label"])
    if not human_col:
        _write_summary(
            CalibrationSummary(
                status="error",
                message="Missing human label column in eval/judge_calibration.csv.",
                input_path=str(INPUT_CSV),
                output_path=str(OUTPUT_JSON),
                rows_total=len(df),
                rows_scored=0,
                human_label_column=None,
                predicted_label_column=None,
                agreement_rate=None,
                preview_api_available=False,
                details={"columns": list(df.columns)},
            )
        )
        return

    try:
        from vertexai.preview.evaluation import (
            AutoraterConfig,
            EvalTask,
            PairwiseMetric,
        )
        from vertexai.preview.evaluation.autorater_utils import evaluate_autorater
    except Exception as exc:
        _write_summary(
            CalibrationSummary(
                status="error",
                message=f"Vertex preview evaluation API unavailable: {exc}",
                input_path=str(INPUT_CSV),
                output_path=str(OUTPUT_JSON),
                rows_total=len(df),
                rows_scored=0,
                human_label_column=human_col,
                predicted_label_column=None,
                agreement_rate=None,
                preview_api_available=False,
                details={"autorater_config": AUTORATER_CONFIG},
            )
        )
        return

    try:
        summary = _run_calibration(
            df,
            human_col,
            EvalTask,
            PairwiseMetric,
            AutoraterConfig,
            evaluate_autorater,
        )
    except Exception as exc:
        summary = CalibrationSummary(
            status="error",
            message=f"Judge calibration run failed: {exc}",
            input_path=str(INPUT_CSV),
            output_path=str(OUTPUT_JSON),
            rows_total=len(df),
            rows_scored=0,
            human_label_column=human_col,
            predicted_label_column=None,
            agreement_rate=None,
            preview_api_available=True,
            details={"autorater_config": AUTORATER_CONFIG},
        )
    _write_summary(summary)


if __name__ == "__main__":
    main()
