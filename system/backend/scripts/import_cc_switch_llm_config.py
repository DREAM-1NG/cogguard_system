"""Import Review LLM settings from the current CC-switch Codex provider.

The script reads the CC-switch SQLite database in read-only mode and writes only
the local .env file. It never prints API keys or stores them in tracked files.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_CC_SWITCH_DB = Path.home() / ".cc-switch" / "cc-switch.db"
DEFAULT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_CC_SWITCH_DB), help="Path to cc-switch.db")
    parser.add_argument("--env", default=str(DEFAULT_ENV_PATH), help="Target CogGuard system .env path")
    parser.add_argument("--provider-name", default="", help="Optional exact Codex provider name")
    parser.add_argument("--require-vision", default="true", choices=["true", "false"])
    parser.add_argument("--include-media-base64", default="true", choices=["true", "false"])
    args = parser.parse_args()

    provider = load_current_codex_provider(Path(args.db), provider_name=args.provider_name)
    env_path = Path(args.env)
    env_values = {
        "LLM_API_KEY": provider["api_key"],
        "LLM_API_BASE": provider["base_url"],
        "LLM_MODEL": provider["model"],
        "LLM_API_WIRE": provider["wire_api"],
        "LLM_INCLUDE_MEDIA_BASE64": args.include_media_base64,
        "LLM_REQUIRE_VISION": args.require_vision,
        "Review_EXTERNAL_RETRIEVAL_ENABLED": "false",
    }
    upsert_env(env_path, env_values)
    print(
        "Imported Review LLM config from CC-switch provider "
        f"'{provider['name']}' ({provider['id']})."
    )
    print(f"Target .env: {env_path}")
    print(
        "Imported fields: LLM_API_KEY=<redacted>, "
        f"LLM_API_BASE={provider['base_url']}, LLM_MODEL={provider['model']}, "
        f"LLM_API_WIRE={provider['wire_api']}, LLM_REQUIRE_VISION={args.require_vision}"
    )
    return 0


def load_current_codex_provider(db_path: Path, *, provider_name: str = "") -> dict[str, str]:
    if not db_path.exists():
        raise FileNotFoundError(f"CC-switch database not found: {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        if provider_name:
            row = conn.execute(
                """
                select id, name, settings_config
                from providers
                where app_type='codex' and name=?
                order by is_current desc
                limit 1
                """,
                (provider_name,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                select id, name, settings_config
                from providers
                where app_type='codex' and is_current=1
                limit 1
                """
            ).fetchone()
    finally:
        conn.close()
    if row is None:
        selector = f"name={provider_name!r}" if provider_name else "is_current=1"
        raise ValueError(f"No Codex provider found in CC-switch database ({selector})")
    settings_config = json.loads(row["settings_config"] or "{}")
    auth = settings_config.get("auth") or {}
    api_key = str(auth.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise ValueError(
            f"Codex provider '{row['name']}' does not contain OPENAI_API_KEY; "
            "ChatGPT token auth is not supported by this importer."
        )
    config_text = str(settings_config.get("config") or "")
    return {
        "id": str(row["id"]),
        "name": str(row["name"]),
        "api_key": api_key,
        "base_url": _toml_value(config_text, "base_url") or "https://api.openai.com/v1",
        "model": _toml_value(config_text, "model") or "gpt-4o",
        "wire_api": _normalize_wire_api(_toml_value(config_text, "wire_api") or "chat_completions"),
    }


def upsert_env(env_path: Path, values: dict[str, str]) -> None:
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else ""
        if key in values:
            output.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            output.append(line)
    if values.keys() - seen:
        if output and output[-1].strip():
            output.append("")
        output.append("# Review LLM / Agent Review imported from CC-switch")
        for key, value in values.items():
            if key not in seen:
                output.append(f"{key}={value}")
    env_path.write_text("\n".join(output) + "\n", encoding="utf-8")


def _toml_value(config_text: str, key: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=\s*['\"]([^'\"]+)['\"]\s*$", re.MULTILINE)
    match = pattern.search(config_text)
    return match.group(1).strip() if match else ""


def _normalize_wire_api(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    if normalized in {"responses", "response"}:
        return "responses"
    if normalized in {"chat", "chat_completion", "chat_completions", "completions"}:
        return "chat_completions"
    # CC-switch Codex configs often use Responses even for custom providers.
    return normalized or "chat_completions"


if __name__ == "__main__":
    raise SystemExit(main())
