"""Turning the copilot's LLM on and off, and choosing it, from the interface.

The copilot (dataset discovery, Step suggestions, the priority map's directions) works without an
LLM, with rules. With one, it judges against the collection's goal. Settings chosen in the
interface are kept in ``<data>/copilot_settings.json`` and override the environment
(``COPILOT_DISABLED``, ``LLM_PROVIDER``, ``*_MODEL``):

- ``enabled``: use an LLM or rules only;
- ``provider``: ``openai``, ``portkey``, ``huggingface`` (keys stay in ``backend/.env``; the
  interface never sees or stores them) or ``local``, a model on this machine behind an
  OpenAI-compatible server (Ollama, LM Studio, llama.cpp's llama-server, vLLM), which needs no key;
- ``model`` and, for ``local``, ``local_base_url``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

PROVIDERS = {
    "openai": {"label": "OpenAI", "key": "OPENAI_API_KEY", "model_env": "OPENAI_MODEL", "default_model": "gpt-5-mini"},
    "portkey": {"label": "Portkey gateway", "key": "PORTKEY_API_KEY", "model_env": "PORTKEY_MODEL",
                "default_model": "@vertexai/gemini-3-pro-preview"},
    "huggingface": {"label": "Hugging Face", "key": "HF_TOKEN", "model_env": "HF_MODEL", "default_model": "openai/gpt-oss-120b"},
    "local": {"label": "Local model", "key": None, "model_env": "LOCAL_LLM_MODEL", "default_model": ""},
}
DEFAULT_LOCAL_URL = "http://localhost:11434/v1"


def _path(data_dir) -> Path:
    return Path(data_dir) / "copilot_settings.json"


def saved(data_dir) -> dict:
    p = _path(data_dir)
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except ValueError:
        return {}


def effective(data_dir) -> dict:
    """The settings in force: the interface's, else the environment's."""
    s = saved(data_dir)
    env_off = os.getenv("COPILOT_DISABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    provider = s.get("provider") or (os.getenv("LLM_PROVIDER") or "portkey").strip().lower()
    if provider not in PROVIDERS:
        provider = "portkey"
    info = PROVIDERS[provider]
    return {
        "enabled": bool(s["enabled"]) if "enabled" in s else not env_off,
        "provider": provider,
        "model": s.get("model") or os.getenv(info["model_env"]) or info["default_model"],
        "local_base_url": s.get("local_base_url") or os.getenv("LOCAL_LLM_BASE_URL") or DEFAULT_LOCAL_URL,
        "source": "interface" if s else "environment",
    }


def save(data_dir, body: dict) -> dict:
    out = {k: body[k] for k in ("enabled", "provider", "model", "local_base_url") if k in body and body[k] is not None}
    if out.get("provider") and out["provider"] not in PROVIDERS:
        raise ValueError(f"Unknown provider {out['provider']!r}; choose one of {', '.join(PROVIDERS)}.")
    _path(data_dir).write_text(json.dumps(out, indent=1))
    return effective(data_dir)


def reset(data_dir):
    p = _path(data_dir)
    if p.exists():
        p.unlink()


def local_models(base_url: str) -> tuple[list[str] | None, str | None]:
    """The models a local OpenAI-compatible server offers, or (None, why not)."""
    import httpx
    try:
        r = httpx.get(base_url.rstrip("/") + "/models", timeout=2.0)
        r.raise_for_status()
        return sorted(m.get("id") for m in r.json().get("data", []) if m.get("id")), None
    except Exception as e:  # not running, wrong address, not OpenAI-compatible
        return None, f"No OpenAI-compatible server answered at {base_url} ({type(e).__name__})."


def providers(data_dir) -> list[dict]:
    """Each provider and whether it can be used: a key in the environment, or a local server running."""
    eff = effective(data_dir)
    out = []
    for pid, info in PROVIDERS.items():
        row = {"id": pid, "label": info["label"], "default_model": info["default_model"]}
        if info["key"]:
            has = bool(os.getenv(info["key"]) or (pid == "huggingface" and os.getenv("HUGGING_FACE_HUB_TOKEN")))
            row.update(ready=has, why=None if has else f"Set {info['key']} in backend/.env and restart the backend.")
        else:
            models, why = local_models(eff["local_base_url"])
            row.update(ready=bool(models), why=why or (None if models else "The server lists no models."), models=models or [])
        out.append(row)
    return out
