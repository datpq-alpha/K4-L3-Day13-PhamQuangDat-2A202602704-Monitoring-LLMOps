from __future__ import annotations

import html
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

from .metrics import percentile

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"


@dataclass(frozen=True)
class Panel:
    panel_id: str
    title: str
    primary: str
    details: tuple[str, ...]
    unit: str
    threshold: str
    healthy: bool


def _load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc)


def _window_records(
    records: list[dict[str, Any]],
    minutes: int,
) -> tuple[list[dict[str, Any]], datetime | None]:
    timestamps = [
        parsed
        for record in records
        if (parsed := _parse_timestamp(record.get("ts"))) is not None
    ]
    if not timestamps:
        return records, None

    window_end = max(timestamps)
    window_start = window_end - timedelta(minutes=minutes)
    filtered = [
        record
        for record in records
        if (parsed := _parse_timestamp(record.get("ts"))) is not None
        and window_start <= parsed <= window_end
    ]
    return filtered, window_end


def _number(record: dict[str, Any], field: str, default: float = 0.0) -> float:
    value = record.get(field, default)
    return float(value) if isinstance(value, (int, float)) else default


def build_dashboard(
    log_path: Path = DEFAULT_LOG_PATH,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))["dashboard"]
    records, window_end = _window_records(
        _load_records(log_path),
        int(config["time_range_minutes"]),
    )
    panel_config = {item["id"]: item for item in config["panels"]}

    requests = [record for record in records if record.get("event") == "request_received"]
    responses = [record for record in records if record.get("event") == "response_sent"]
    failures = [record for record in records if record.get("event") == "request_failed"]

    latencies = [int(_number(record, "latency_ms")) for record in responses]
    ttfts = [int(_number(record, "ttft_ms")) for record in responses]
    latency_values = {
        "p50": percentile(latencies, 50),
        "p95": percentile(latencies, 95),
        "p99": percentile(latencies, 99),
        "ttft_p95": percentile(ttfts, 95),
    }

    request_count = len(requests)
    response_count = len(responses)
    error_rate = (len(failures) / request_count * 100) if request_count else 0.0
    error_breakdown = Counter(
        str(record.get("error_type") or "unknown") for record in failures
    )
    retrieval_outcomes = [
        record
        for record in responses + failures
        if record.get("tool_name") == "retrieval"
        and record.get("tool_success") is not None
    ]
    retrieval_success = (
        sum(record.get("tool_success") is True for record in retrieval_outcomes)
        / len(retrieval_outcomes)
        * 100
        if retrieval_outcomes
        else 0.0
    )

    total_cost = sum(_number(record, "cost_usd") for record in responses)
    tokens_in = int(sum(_number(record, "tokens_in") for record in responses))
    tokens_out = int(sum(_number(record, "tokens_out") for record in responses))
    quality_values = [_number(record, "quality_score") for record in responses]
    quality_average = mean(quality_values) if quality_values else 0.0
    traffic_rate = request_count / int(config["time_range_minutes"])

    latency_threshold = panel_config["latency"]["threshold"]["value"]
    traffic_threshold = panel_config["traffic"]["threshold"]["value"]
    error_threshold = panel_config["errors"]["threshold"]["value"]
    cost_threshold = panel_config["cost"]["threshold"]["value"]
    token_threshold = panel_config["tokens"]["threshold"]["value"]
    quality_threshold = panel_config["quality"]["threshold"]["value"]

    panels = (
        Panel(
            "latency",
            panel_config["latency"]["title"],
            f"{latency_values['p95']:.0f} ms",
            (
                f"P50 {latency_values['p50']:.0f} ms",
                f"P99 {latency_values['p99']:.0f} ms",
                f"TTFT P95 {latency_values['ttft_p95']:.0f} ms",
            ),
            "ms",
            f"P95 ≤ {latency_threshold} ms",
            latency_values["p95"] <= latency_threshold,
        ),
        Panel(
            "traffic",
            panel_config["traffic"]["title"],
            f"{request_count} requests",
            (f"{traffic_rate:.2f} requests/min", f"{response_count} responses"),
            "requests/minute",
            f"Rate ≥ {traffic_threshold}/min",
            traffic_rate >= traffic_threshold,
        ),
        Panel(
            "errors",
            panel_config["errors"]["title"],
            f"{error_rate:.2f}% errors",
            (
                f"Retrieval success {retrieval_success:.2f}%",
                "Breakdown "
                + (", ".join(f"{key}: {value}" for key, value in error_breakdown.items()) or "none"),
            ),
            "percent",
            f"Error rate ≤ {error_threshold}% / retrieval ≥ 90%",
            error_rate <= error_threshold and retrieval_success >= 90,
        ),
        Panel(
            "cost",
            panel_config["cost"]["title"],
            f"${total_cost:.4f}",
            (f"{response_count} billable responses", "60-minute dashboard window"),
            "USD",
            f"Window total ≤ ${cost_threshold}",
            total_cost <= cost_threshold,
        ),
        Panel(
            "tokens",
            panel_config["tokens"]["title"],
            f"{tokens_in + tokens_out:,} total",
            (f"Input {tokens_in:,}", f"Output {tokens_out:,}"),
            "tokens",
            f"Each field sum ≤ {token_threshold:,}",
            max(tokens_in, tokens_out) <= token_threshold,
        ),
        Panel(
            "quality",
            panel_config["quality"]["title"],
            f"{quality_average:.3f}",
            (f"{len(quality_values)} scored responses", "Proxy range 0–1"),
            "score 0–1",
            f"Mean ≥ {quality_threshold}",
            quality_average >= quality_threshold,
        ),
    )

    return {
        "title": config["title"],
        "source": str(panel_config["latency"]["source"]),
        "time_range_minutes": int(config["time_range_minutes"]),
        "refresh_seconds": int(config["refresh_seconds"]),
        "window_end": window_end.isoformat() if window_end else "no data",
        "record_count": len(records),
        "panels": panels,
    }


def render_dashboard(
    log_path: Path = DEFAULT_LOG_PATH,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> str:
    dashboard = build_dashboard(log_path, config_path)
    cards = []
    for panel in dashboard["panels"]:
        status = "healthy" if panel.healthy else "breached"
        details = "".join(f"<li>{html.escape(item)}</li>" for item in panel.details)
        cards.append(
            f"""
            <section class="panel {status}" id="{html.escape(panel.panel_id)}">
              <div class="panel-heading">
                <h2>{html.escape(panel.title)}</h2>
                <span class="status">{status.upper()}</span>
              </div>
              <p class="primary">{html.escape(panel.primary)}</p>
              <p class="unit">Unit: {html.escape(panel.unit)}</p>
              <ul>{details}</ul>
              <div class="threshold">Threshold: {html.escape(panel.threshold)}</div>
            </section>
            """
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="{dashboard['refresh_seconds']}">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(dashboard['title'])}</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    body {{ margin: 0; background: #08111f; color: #e7edf7; }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 32px; }}
    header {{ display: flex; justify-content: space-between; gap: 24px; align-items: end; margin-bottom: 24px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    .meta {{ color: #93a4bd; font-size: 14px; line-height: 1.6; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; }}
    .panel {{ background: #101d30; border: 1px solid #263955; border-top: 4px solid #23c483; border-radius: 12px; padding: 20px; min-height: 240px; box-shadow: 0 12px 30px #0004; }}
    .panel.breached {{ border-top-color: #ff6b6b; }}
    .panel-heading {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; }}
    h2 {{ margin: 0; font-size: 16px; color: #c8d5e8; }}
    .status {{ font-size: 11px; font-weight: 800; color: #23c483; }}
    .breached .status {{ color: #ff6b6b; }}
    .primary {{ margin: 28px 0 4px; font-size: 34px; font-weight: 750; letter-spacing: -1px; }}
    .unit {{ margin: 0 0 18px; color: #7f93ae; font-size: 12px; text-transform: uppercase; }}
    ul {{ min-height: 48px; padding-left: 18px; color: #b5c4d9; line-height: 1.6; }}
    .threshold {{ margin-top: 16px; padding: 10px 12px; background: #08111f; border-radius: 8px; color: #9fb1c9; font-size: 13px; }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} header {{ align-items: start; flex-direction: column; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <div><h1>{html.escape(dashboard['title'])}</h1><div class="meta">Six-panel LLMOps runtime dashboard</div></div>
      <div class="meta">Source: {html.escape(dashboard['source'])}<br>Time range: latest {dashboard['time_range_minutes']} minutes<br>Window end: {html.escape(dashboard['window_end'])}<br>Refresh: {dashboard['refresh_seconds']}s · Records: {dashboard['record_count']}</div>
    </header>
    <div class="grid">{''.join(cards)}</div>
  </main>
</body>
</html>"""
