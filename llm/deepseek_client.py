"""
LLM via OpenAI-compatible APIs.

Providers (auto-detected from env):
  1. OpenAI     — OPENAI_API_KEY    → https://api.openai.com/v1
                  model: gpt-4o
  2. DeepSeek   — DEEPSEEK_API_KEY  → https://api.deepseek.com
                  model: deepseek-v4-pro

Force provider with LLM_PROVIDER=openai|deepseek
"""

from __future__ import annotations

import json
import os
from typing import Any, Literal

# Differentiated temperatures — creative agents high; Manager/Auditors deterministic.
AGENT_TEMPERATURES: dict[str, float] = {
    "manager": 0.10,
    "auditor": 0.00,
    "timing": 0.20,
    "narrative": 0.85,
    "nlp": 0.90,
    "semiotics": 0.80,
    "locomotion": 0.20,
    "physics": 0.15,
    "cinematography": 0.35,
    "acting": 0.85,
    "render": 0.20,
    "foley": 0.30,
    "emitter": 0.00,
}

ProviderName = Literal["openai", "deepseek"]

OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_DEFAULT_MODEL = "gpt-4o"

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_DEFAULT_MODEL = "deepseek-v4-pro"


def _env(name: str) -> str | None:
    val = (os.environ.get(name) or "").strip()
    return val or None


def resolve_provider() -> ProviderName | None:
    """Pick OpenAI or DeepSeek from env. Prefer OpenAI when its key is set."""
    forced = (_env("LLM_PROVIDER") or "").lower()
    has_oa = bool(_env("OPENAI_API_KEY"))
    has_ds = bool(_env("DEEPSEEK_API_KEY"))

    if forced in {"openai", "oa"}:
        return "openai" if has_oa else None
    if forced in {"deepseek", "ds", "direct"}:
        return "deepseek" if has_ds else None

    # Auto: OpenAI first
    if has_oa:
        return "openai"
    if has_ds:
        return "deepseek"
    return None


def deepseek_api_key() -> str | None:
    """Backward-compatible: any usable LLM key (OpenAI or DeepSeek)."""
    provider = resolve_provider()
    if provider == "openai":
        return _env("OPENAI_API_KEY")
    if provider == "deepseek":
        return _env("DEEPSEEK_API_KEY")
    return _env("OPENAI_API_KEY") or _env("DEEPSEEK_API_KEY")


def deepseek_configured() -> bool:
    return resolve_provider() is not None


def _normalize_model(model: str) -> str:
    """Normalize model name for the active provider."""
    m = model.strip()
    aliases = {
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
        "gpt-4": "gpt-4-turbo",
        "deepseek-v4-pro": "deepseek-v4-pro",
        "deepseek-chat": "deepseek/deepseek-v4-pro",
        "deepseek-v4-flash": "deepseek/deepseek-v4-flash",
    }
    return aliases.get(m, m)


def select_model_for_role(role: str) -> str:
    """
    Select model based on role.
    Fast roles use gpt-4o-mini; precision roles use gpt-4o.
    Override with LLM_MODEL env var.
    """
    override = _env("LLM_MODEL")
    if override:
        return override
    
    fast_roles = {"breakdown", "style", "locomotion", "emitter"}
    if role in fast_roles:
        return "gpt-4o-mini"
    return OPENAI_DEFAULT_MODEL  # gpt-4o


def provider_config() -> dict[str, str]:
    """
    Resolved {provider, api_key, base_url, model} for the active backend.
    Raises if nothing is configured.
    """
    provider = resolve_provider()
    if provider is None:
        raise RuntimeError(
            "No LLM API key configured. Set OPENAI_API_KEY "
            "or DEEPSEEK_API_KEY in .env — see .env.example."
        )

    if provider == "openai":
        key = _env("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("LLM_PROVIDER=openai but OPENAI_API_KEY is empty")
        raw_model = (
            _env("OPENAI_MODEL")
            or _env("LLM_MODEL")
            or OPENAI_DEFAULT_MODEL
        )
        model = _normalize_model(raw_model)
        base = (_env("OPENAI_BASE_URL") or OPENAI_BASE_URL).rstrip("/")
        return {
            "provider": "openai",
            "api_key": key,
            "base_url": base,
            "model": model,
        }

    key = _env("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("LLM_PROVIDER=deepseek but DEEPSEEK_API_KEY is empty")
    model = _env("DEEPSEEK_MODEL") or DEEPSEEK_DEFAULT_MODEL
    base = (_env("DEEPSEEK_BASE_URL") or DEEPSEEK_BASE_URL).rstrip("/")
    return {
        "provider": "deepseek",
        "api_key": key,
        "base_url": base,
        "model": model,
    }


def get_openai_compatible_client() -> Any:
    """OpenAI SDK pointed at OpenAI or DeepSeek."""
    cfg = provider_config()
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Install the openai package: pip install openai>=1.40.0"
        ) from exc

    return OpenAI(
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
    )


def chat_completion(
    *,
    role: str,
    system: str,
    user: str,
    temperature: float | None = None,
    max_tokens: int = 512,
    require_key: bool = False,
) -> str | None:
    """
    Single-turn DeepSeek chat (via OpenRouter or direct).

    Returns None when no key is set and require_key=False (offline CI /
    tools-only mode). Never fabricates LLM text.
    """
    if not deepseek_configured():
        if require_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY or DEEPSEEK_API_KEY required for this agent hop"
            )
        return None

    temp = (
        float(temperature)
        if temperature is not None
        else float(AGENT_TEMPERATURES.get(role, 0.4))
    )
    cfg = provider_config()
    client = get_openai_compatible_client()
    # DeepSeek-V4 on OpenRouter may burn max_tokens on hidden reasoning;
    # disable thinking for agent enrichment (faster + reliable content).
    create_kwargs: dict[str, Any] = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temp,
        "max_tokens": max(max_tokens, 128),
    }

    response = client.chat.completions.create(**create_kwargs)
    choice = response.choices[0].message
    content = getattr(choice, "content", None) or ""
    if not str(content).strip():
        # Fallback if a provider still returns reasoning-only
        for attr in ("reasoning_content", "reasoning"):
            alt = getattr(choice, attr, None)
            if alt and str(alt).strip():
                content = str(alt)
                break
    return str(content).strip() or None


def chat_json(
    *,
    role: str,
    system: str,
    user: str,
    temperature: float | None = None,
    require_key: bool = False,
) -> dict[str, Any] | None:
    """Ask for a JSON object; returns None offline or on parse failure."""
    raw = chat_completion(
        role=role,
        system=system + "\nRespond with a single JSON object only.",
        user=user,
        temperature=temperature,
        max_tokens=768,
        require_key=require_key,
    )
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
        return None
