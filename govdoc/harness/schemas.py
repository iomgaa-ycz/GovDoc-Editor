"""Harness DB 自定义表定义与创建。"""

from __future__ import annotations

from govdoc.harness.log import HarnessLog

PIPELINE_RUNS_COLUMNS: dict[str, str] = {
    "pipeline": "TEXT",
    "project_name": "TEXT",
    "input_file": "TEXT",
    "status": "TEXT",
    "duration_s": "REAL",
    "total_tokens": "INTEGER",
    "error": "TEXT",
}

PHASE_METRICS_COLUMNS: dict[str, str] = {
    "pipeline": "TEXT",
    "phase": "TEXT",
    "duration_s": "REAL",
    "tokens_in": "INTEGER",
    "tokens_out": "INTEGER",
    "status": "TEXT",
    "attempt_no": "INTEGER",
}

EXTRACT_RESULTS_COLUMNS: dict[str, str] = {
    "checkpoint_id": "TEXT",
    "title": "TEXT",
    "category": "TEXT",
    "description": "TEXT",
    "severity": "TEXT",
    "has_legal_basis": "INTEGER",
    "legal_basis_count": "INTEGER",
    "legal_basis_json": "TEXT",
}

AUDIT_RESULTS_COLUMNS: dict[str, str] = {
    "point_run_id": "TEXT",
    "checkpoint_id": "TEXT",
    "verdict": "TEXT",
    "verdict_json": "TEXT",
    "has_evidence": "INTEGER",
    "evidence_count": "INTEGER",
    "evidence_json": "TEXT",
    "has_case_refs": "INTEGER",
    "duration_s": "REAL",
    "status": "TEXT",
}

QUALITY_SCORES_COLUMNS: dict[str, str] = {
    "dimension": "TEXT",
    "score": "REAL",
    "passed": "INTEGER",
    "judge_reasoning": "TEXT",
}

API_CALLS_COLUMNS: dict[str, str] = {
    "method": "TEXT",
    "path": "TEXT",
    "status_code": "INTEGER",
    "duration_ms": "REAL",
    "request_size": "INTEGER",
    "response_size": "INTEGER",
    "error": "TEXT",
}

API_CONTRACTS_COLUMNS: dict[str, str] = {
    "endpoint": "TEXT",
    "check_name": "TEXT",
    "passed": "INTEGER",
    "detail": "TEXT",
}

ALL_TABLES: dict[str, dict[str, str]] = {
    "pipeline_runs": PIPELINE_RUNS_COLUMNS,
    "phase_metrics": PHASE_METRICS_COLUMNS,
    "extract_results": EXTRACT_RESULTS_COLUMNS,
    "audit_results": AUDIT_RESULTS_COLUMNS,
    "quality_scores": QUALITY_SCORES_COLUMNS,
    "api_calls": API_CALLS_COLUMNS,
    "api_contracts": API_CONTRACTS_COLUMNS,
}


def create_all_tables(log: HarnessLog) -> None:
    """在 harness.db 中创建全部 7 张自定义表。

    参数:
        log: 已初始化的 HarnessLog 实例。
    """
    for table_name, columns in ALL_TABLES.items():
        log.create_table(table_name, columns)
