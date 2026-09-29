from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from app.cli import configure_utf8_stdio
from app.main import app
from app.tracing import get_langfuse_client

SAMPLE_QUERIES = REPO_ROOT / "data" / "sample_queries.jsonl"
PROMPT_PROBE = {
    "user_id": "cp2-prompt-probe",
    "session_id": "cp2-prompt-versioning",
    "feature": "qa",
    "message": "Explain why metrics, logs, and traces work together.",
}


async def _post(
    client: httpx.AsyncClient,
    payload: dict,
    *,
    label: str,
    request_id: str | None = None,
) -> None:
    os.environ["LANGFUSE_PROMPT_LABEL"] = label
    headers = {"x-request-id": request_id} if request_id else None
    response = await client.post("/chat", json=payload, headers=headers)
    response.raise_for_status()
    body = response.json()
    print(
        f"[{response.status_code}] {body['correlation_id']} | "
        f"label={label} | {body['latency_ms']}ms"
    )


async def main_async() -> None:
    payloads = [
        json.loads(line)
        for line in SAMPLE_QUERIES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://cp2.local",
            timeout=30,
        ) as client:
            await _post(
                client,
                PROMPT_PROBE,
                label="baseline",
                request_id="req-ba5e0001",
            )
            await _post(
                client,
                PROMPT_PROBE,
                label="candidate",
                request_id="req-ca2d0002",
            )
            for payload in payloads:
                await _post(client, payload, label="production")

    os.environ["LANGFUSE_PROMPT_LABEL"] = "production"
    get_langfuse_client().flush()


def main() -> None:
    configure_utf8_stdio()
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
