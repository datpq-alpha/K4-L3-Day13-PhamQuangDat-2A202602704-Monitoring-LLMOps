from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(relative_path: str) -> dict:
    return yaml.safe_load(
        (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    )


def test_error_panel_includes_success_events_for_retrieval_rate() -> None:
    dashboard = _load_yaml("config/dashboard.yaml")["dashboard"]
    errors = next(panel for panel in dashboard["panels"] if panel["id"] == "errors")

    assert "request_received" in errors["events"]
    assert "response_sent" in errors["events"]
    assert "request_failed" in errors["events"]
    assert "tool_success" in errors["fields"]


def test_slo_error_budget_is_consistent() -> None:
    slo = _load_yaml("config/slo.yaml")["primary_slo"]

    assert slo["target_percent"] + slo["error_budget_percent"] == 100
    assert slo["error_budget"]["allowed_bad_requests_per_1000"] == 5


def test_three_alerts_are_actionable_and_symptom_based() -> None:
    alerts = _load_yaml("config/alert_rules.yaml")["alerts"]

    assert len(alerts) == 3
    for alert in alerts:
        assert alert["type"] == "symptom-based"
        assert alert["severity"] in {"medium", "high", "critical"}
        assert alert["condition"]
        assert alert["duration"].endswith("m")
        assert alert["owner"]
        assert alert["channel"].startswith("#")
        assert alert["runbook"].startswith("docs/alerts.md#alert-")
        assert "TODO" not in str(alert)
