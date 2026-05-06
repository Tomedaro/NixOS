"""Shared schema helpers for read-only agent context providers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def generated_at_iso(now_epoch: int | None = None) -> str:
    if now_epoch is None:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    return datetime.fromtimestamp(now_epoch, timezone.utc).isoformat(timespec="seconds")


def provider_result(
    name: str,
    *,
    available: bool,
    facts: dict[str, Any] | None = None,
    signals: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    freshness: str = "unknown",
    source_paths: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "context_provider.v1",
        "name": name,
        "available": bool(available),
        "freshness": freshness,
        "facts": facts or {},
        "signals": signals or [],
        "warnings": warnings or [],
        "source_paths": source_paths or [],
    }


def provider_unavailable(
    name: str,
    reason: str,
    *,
    source_paths: list[str] | None = None,
) -> dict[str, Any]:
    return provider_result(
        name,
        available=False,
        warnings=[reason],
        freshness="unavailable",
        source_paths=source_paths,
    )


def context_hub_snapshot(
    providers: list[dict[str, Any]],
    *,
    now_epoch: int | None = None,
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    facts: dict[str, dict[str, Any]] = {}

    for provider in providers:
        name = str(provider.get("name") or "unknown")
        provider_facts = provider.get("facts")
        facts[name] = provider_facts if isinstance(provider_facts, dict) else {}

        for warning in provider.get("warnings", []) or []:
            warnings.append({"provider": name, "warning": str(warning)})

    return {
        "schema_version": "context_hub.v1",
        "generated_at": generated_at_iso(now_epoch),
        "provider_count": len(providers),
        "available_providers": [
            str(provider.get("name"))
            for provider in providers
            if provider.get("available")
        ],
        "providers": providers,
        "facts": facts,
        "warnings": warnings,
    }
