from __future__ import annotations

import json
from pathlib import Path

from app.dashboard import build_dashboard, render_dashboard


def _write_records(path: Path) -> None:
    records = [
        {
            "ts": "2026-09-29T08:00:00Z",
            "event": "request_received",
            "service": "api",
        },
        {
            "ts": "2026-09-29T08:00:01Z",
            "event": "response_sent",
            "service": "api",
            "latency_ms": 800,
            "ttft_ms": 50,
            "cost_usd": 0.002,
            "tokens_in": 30,
            "tokens_out": 100,
            "quality_score": 0.9,
            "tool_name": "retrieval",
            "tool_success": True,
        },
    ]
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def test_dashboard_runtime_contains_six_populated_panels(tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    _write_records(log_path)

    dashboard = build_dashboard(log_path)

    assert len(dashboard["panels"]) == 6
    errors = next(panel for panel in dashboard["panels"] if panel.panel_id == "errors")
    assert "100.00%" in errors.details[0]
    assert errors.healthy is True


def test_dashboard_html_shows_runtime_contract(tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    _write_records(log_path)

    page = render_dashboard(log_path)

    assert page.count('<section class="panel') == 6
    assert "Time range: latest 60 minutes" in page
    assert "Threshold:" in page
    assert "Latency percentiles and TTFT" in page
