"""
DeepSeek LLM via OpenAI-compatible APIs.

Providers (auto-detected from env):
  1. OpenRouter  — OPENROUTER_API_KEY  → https://openrouter.ai/api/v1
                   model: deepseek/deepseek-v4-pro
  2. DeepSeek    — DEEPSEEK_API_KEY    → https://api.deepseek.com
                   model: deepseek-v4-pro

Force provider with LLM_PROVIDER=openrouter|deepseek
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

ProviderName = Literal["openrouter", "deepseek"]

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = "deepseek/deepseek-v4-pro"

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_DEFAULT_MODEL = "deepseek-v4-pro"


def _env(name: str) -> str | None:
    val = (os.environ.get(name) or "").strip()
    return val or None


def resolve_provider() -> ProviderName | None:
    """Pick OpenRouter or DeepSeek from env. Prefer OpenRouter when its key is set."""
    forced = (_env("LLM_PROVIDER") or "").lower()
    has_or = bool(_env("OPENROUTER_API_KEY"))
    has_ds = bool(_env("DEEPSEEK_API_KEY"))

    if forced in {"openrouter", "or"}:
        return "openrouter" if has_or else None
    if forced in {"deepseek", "ds", "direct"}:
        return "deepseek" if has_ds else None

    # Auto: OpenRouter first (common for Iran / unified billing), else DeepSeek direct
    if has_or:
        return "openrouter"
    if has_ds:
        return "deepseek"
    return None


def deepseek_api_key() -> str | None:
    """Backward-compatible: any usable LLM key (OpenRouter or DeepSeek)."""
    provider = resolve_provider()
    if provider == "openrouter":
        return _env("OPENROUTER_API_KEY")
    if provider == "deepseek":
        return _env("DEEPSEEK_API_KEY")
    return _env("OPENROUTER_API_KEY") or _env("DEEPSEEK_API_KEY")


def deepseek_configured() -> bool:
    return resolve_provider() is not None


def _normalize_openrouter_model(model: str) -> str:
    """Map short DeepSeek names to OpenRouter slugs."""
    m = model.strip()
    aliases = {
        "deepseek-v4-pro": OPENROUTER_DEFAULT_MODEL,
        "v4-pro": OPENROUTER_DEFAULT_MODEL,
        "deepseek-chat": OPENROUTER_DEFAULT_MODEL,
        "deepseek-v4-flash": "deepseek/deepseek-v4-flash",
        "v4-flash": "deepseek/deepseek-v4-flash",
        "deepseek-reasoner": "deepseek/deepseek-r1",
    }
    if m in aliases:
        return aliases[m]
    if m.startswith("deepseek/") and m.count("/") == 1:
        return m
    if m.startswith("deepseek-") and "/" not in m:
        return f"deepseek/{m}"
    return m


def provider_config() -> dict[str, str]:
    """
    Resolved {provider, api_key, base_url, model} for the active backend.
    Raises if nothing is configured.
    """
    provider = resolve_provider()
    if provider is None:
        raise RuntimeError(
            "No LLM API key configured. Set OPENROUTER_API_KEY (recommended) "
            "or DEEPSEEK_API_KEY in .env — see .env.example."
        )

    if provider == "openrouter":
        key = _env("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("LLM_PROVIDER=openrouter but OPENROUTER_API_KEY is empty")
        raw_model = (
            _env("OPENROUTER_MODEL")
            or _env("DEEPSEEK_MODEL")
            or OPENROUTER_DEFAULT_MODEL
        )
        model = _normalize_openrouter_model(raw_model)
        base = (_env("OPENROUTER_BASE_URL") or OPENROUTER_BASE_URL).rstrip("/")
        return {
            "provider": "openrouter",
            "api_key": key,
            "base_url": base,
            "model": model,
        }

    key = _env("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("LLM_PROVIDER=deepseek but DEEPSEEK_API_KEY is empty")
    model = _env("DEEPSEEK_MODEL") or DEEPSEEK_DEFAULT_MODEL
    if model.startswith("deepseek/") and model.count("/") == 1:
        model = model.split("/", 1)[1]
    base = (_env("DEEPSEEK_BASE_URL") or DEEPSEEK_BASE_URL).rstrip("/")
    return {
        "provider": "deepseek",
        "api_key": key,
        "base_url": base,
        "model": model,
    }


def get_openai_compatible_client() -> Any:
    """OpenAI SDK pointed at OpenRouter or DeepSeek."""
    cfg = provider_config()
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Install the openai package: pip install openai>=1.40.0"
        ) from exc

    default_headers: dict[str, str] = {}
    if cfg["provider"] == "openrouter":
        # Optional ranking headers (OpenRouter docs)
        referer = _env("OPENROUTER_HTTP_REFERER") or "https://github.com/williams-glebas/animation-engine"
        title = _env("OPENROUTER_APP_TITLE") or "Story Narrative Tool"
        default_headers["HTTP-Referer"] = referer
        default_headers["X-Title"] = title

    return OpenAI(
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        default_headers=default_headers or None,
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
    if cfg["provider"] == "openrouter" or "deepseek" in cfg["model"].lower():
        create_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

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
