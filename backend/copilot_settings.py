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
# When several providers work and none was chosen, the first that works is the default: a model on
# this machine first (nothing leaves it), then the hosted ones
ORDER = ["local", "openai", "huggingface", "portkey"]

# What the last check found, per provider: {ready, verified, why, models, checked}. Filled at startup
# (main.py) and by "Check again" in the interface; without a check, keys are only looked for.
_CHECKS: dict[str, dict] = {}


def _path(data_dir) -> Path:
    return Path(data_dir) / "copilot_settings.json"


def saved(data_dir) -> dict:
    p = _path(data_dir)
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except ValueError:
        return {}


def effective(data_dir) -> dict:
    """The settings in force: the interface's, else the environment's. Without a provider chosen in
    the interface, one named in the environment that does not work gives way to the first that does."""
    s = saved(data_dir)
    env_off = os.getenv("COPILOT_DISABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    provider = s.get("provider") or (os.getenv("LLM_PROVIDER") or "portkey").strip().lower()
    if provider not in PROVIDERS:
        provider = "portkey"
    if not s.get("provider") and _CHECKS and not _CHECKS.get(provider, {}).get("ready"):
        provider = next((p for p in ORDER if _CHECKS.get(p, {}).get("ready")), provider)
    info = PROVIDERS[provider]
    return {
        "enabled": bool(s["enabled"]) if "enabled" in s else not env_off,
        "provider": provider,
        "model": s.get("model") or os.getenv(info["model_env"]) or info["default_model"]
                 or next(iter(_CHECKS.get(provider, {}).get("models") or []), ""),   # a local server's first model
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


def _key(pid: str) -> str | None:
    info = PROVIDERS[pid]
    if not info["key"]:
        return None
    return os.getenv(info["key"]) or (os.getenv("HUGGING_FACE_HUB_TOKEN") if pid == "huggingface" else None)


def _verify(pid: str, base_url: str) -> dict:
    """Does the provider work? A key is checked with its own provider by a free request that uses
    no tokens (the list of models, or the token's owner); a local server is asked for its models."""
    import httpx
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if pid == "local":
        models, why = local_models(base_url)
        return {"ready": bool(models), "verified": bool(models), "models": models or [], "checked": now,
                "why": why or (None if models else "The server lists no models.")}
    key = _key(pid)
    if not key:
        return {"ready": False, "verified": False, "checked": now,
                "why": f"No {PROVIDERS[pid]['key']} in the backend's environment (shell or backend/.env)."}
    url = {"openai": "https://api.openai.com/v1/models",
           "huggingface": "https://huggingface.co/api/whoami-v2"}.get(pid)
    if url is None:                                           # Portkey: a gateway with no free check
        return {"ready": True, "verified": False, "checked": now, "why": None}
    try:
        r = httpx.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=8)
    except httpx.HTTPError as e:
        return {"ready": True, "verified": False, "checked": now,
                "why": f"Key found, but the provider could not be reached to check it ({type(e).__name__})."}
    if r.status_code in (401, 403):
        return {"ready": False, "verified": False, "checked": now,
                "why": f"The provider refused the {PROVIDERS[pid]['key']} key ({r.status_code}): wrong or expired."}
    return {"ready": r.is_success, "verified": r.is_success, "checked": now,
            "why": None if r.is_success else f"The provider answered {r.status_code} when the key was checked."}


def check_all(data_dir) -> dict:
    """Check every provider now; the result is kept for providers() and effective()."""
    base = effective(data_dir)["local_base_url"]
    found = {pid: _verify(pid, base) for pid in PROVIDERS}
    _CHECKS.clear()
    _CHECKS.update(found)
    return found


def checks_enabled() -> bool:
    return (os.getenv("URBANTRACE_LLM_CHECK") or "on").lower() not in ("off", "0", "false", "no")


def summary(data_dir) -> str:
    eff = effective(data_dir)
    ok = [PROVIDERS[p]["label"] + ("" if _CHECKS[p].get("verified") else " (key found, not verified)")
          for p in ORDER if _CHECKS.get(p, {}).get("ready")]
    state = f"on ({eff['provider']}, {eff['model'] or 'no model chosen'})" if eff["enabled"] else "off (rules only)"
    if not ok:
        return f"Copilot LLM is {state}; no provider is available (no key in the environment, no local server)."
    tail = "" if eff["enabled"] else " Turn it on with the LLM chip in the copilot bar."
    return f"Copilot LLM is {state}; available: {', '.join(ok)}.{tail}"


def providers(data_dir) -> list[dict]:
    """Each provider and whether it can be used, from the last check; without one, keys are only
    looked for and a local server is asked."""
    eff = effective(data_dir)
    out = []
    for pid in ORDER:
        info = PROVIDERS[pid]
        row = {"id": pid, "label": info["label"], "default_model": info["default_model"]}
        if pid in _CHECKS:
            row.update({k: v for k, v in _CHECKS[pid].items()})
        elif info["key"]:
            has = bool(_key(pid))
            row.update(ready=has, verified=False,
                       why=None if has else f"No {info['key']} in the backend's environment (shell or backend/.env).")
        else:
            row.update(_verify(pid, eff["local_base_url"]))
        out.append(row)
    return out
