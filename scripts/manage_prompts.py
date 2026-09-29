from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio
from app.tracing import get_langfuse_client

PROMPT_V1 = "Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}"
PROMPT_V2 = (
    "Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}\n"
    "Instruction=Answer concisely using the retrieved context."
)


def _get_prompt(client: Any, name: str, label: str):
    client.clear_prompt_cache()
    try:
        return client.get_prompt(
            name,
            label=label,
            type="text",
            cache_ttl_seconds=0,
            fetch_timeout_seconds=5,
            max_retries=1,
        )
    except Exception:
        return None


def _version(prompt: Any | None) -> int | None:
    value = getattr(prompt, "version", None)
    return int(value) if value is not None else None


def setup(client: Any, name: str) -> None:
    baseline = _get_prompt(client, name, "baseline")
    if baseline is None:
        baseline = client.create_prompt(
            name=name,
            prompt=PROMPT_V1,
            labels=["baseline", "production"],
            type="text",
            commit_message="CP2 baseline prompt",
        )
        print(f"Created baseline/production version {_version(baseline)}")
    else:
        print(f"Baseline already exists at version {_version(baseline)}")

    candidate = _get_prompt(client, name, "candidate")
    if candidate is None:
        candidate = client.create_prompt(
            name=name,
            prompt=PROMPT_V2,
            labels=["candidate"],
            type="text",
            commit_message="CP2 concise candidate prompt",
        )
        print(f"Created candidate version {_version(candidate)}")
    else:
        print(f"Candidate already exists at version {_version(candidate)}")


def status(client: Any, name: str) -> None:
    for label in ("baseline", "candidate", "production"):
        prompt = _get_prompt(client, name, label)
        value = _version(prompt)
        print(f"{label}: version {value if value is not None else 'missing'}")


def move_production(client: Any, name: str, target_label: str) -> None:
    target = _get_prompt(client, name, target_label)
    target_version = _version(target)
    if target_version is None:
        raise RuntimeError(f"Prompt label '{target_label}' does not exist")
    client.update_prompt(
        name=name,
        version=target_version,
        new_labels=[target_label, "production"],
    )
    client.clear_prompt_cache()
    print(f"production -> version {target_version} ({target_label})")


def main() -> int:
    configure_utf8_stdio()
    load_dotenv(REPO_ROOT / ".env")
    parser = argparse.ArgumentParser(description="Manage CP2 Langfuse prompt labels")
    parser.add_argument(
        "action",
        choices=("setup", "status", "promote", "rollback"),
    )
    args = parser.parse_args()

    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        print("Missing LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY in .env")
        return 1

    name = os.getenv("LANGFUSE_PROMPT_NAME", "day13-chat")
    client = get_langfuse_client()
    if not client.auth_check():
        print("Langfuse authentication failed")
        return 1

    if args.action == "setup":
        setup(client, name)
    elif args.action == "status":
        status(client, name)
    elif args.action == "promote":
        move_production(client, name, "candidate")
    else:
        move_production(client, name, "baseline")

    client.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
