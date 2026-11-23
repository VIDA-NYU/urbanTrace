"""Turning the copilot's LLM on and off from the interface (copilot_settings.py). No LLM is called."""
import copilot_settings
import main


def test_off_by_environment_on_by_interface(client, catalog, monkeypatch):
    monkeypatch.setenv("COPILOT_DISABLED", "1")
    body = client.get("/api/copilot/settings").json()
    assert body["settings"]["enabled"] is False and body["settings"]["source"] == "environment"
    assert main.copilot_disabled()
    r = client.post("/api/copilot/settings", json={"enabled": True, "provider": "local", "model": "qwen3:14b",
                                                   "local_base_url": "http://127.0.0.1:9/v1"})
    assert r.status_code == 200, r.text
    s = r.json()["settings"]
    assert (s["enabled"], s["provider"], s["model"], s["source"]) == (True, "local", "qwen3:14b", "interface")
    assert not main.copilot_disabled()
    local = next(p for p in r.json()["providers"] if p["id"] == "local")
    assert local["ready"] is False and "No OpenAI-compatible server" in local["why"]   # nothing listens on port 9
    client.delete("/api/copilot/settings")
    assert main.copilot_disabled()


def test_hosted_providers_need_a_key_in_the_environment(client, catalog, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    openai = next(p for p in client.get("/api/copilot/settings").json()["providers"] if p["id"] == "openai")
    assert openai["ready"] is False and "OPENAI_API_KEY" in openai["why"]
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-key")
    openai = next(p for p in client.get("/api/copilot/settings").json()["providers"] if p["id"] == "openai")
    assert openai["ready"] is True


def test_unknown_provider_is_a_400(client, catalog):
    assert client.post("/api/copilot/settings", json={"provider": "nope"}).status_code == 400


def test_test_needs_the_llm_on(client, catalog, monkeypatch):
    monkeypatch.setenv("COPILOT_DISABLED", "1")
    assert client.post("/api/copilot/test").status_code == 400


class _Resp:
    def __init__(self, code):
        self.status_code = code
        self.is_success = 200 <= code < 300


def test_keys_are_verified_with_their_provider(monkeypatch):
    import httpx
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-key")
    seen = []
    monkeypatch.setattr(httpx, "get", lambda url, **kw: seen.append(url) or _Resp(401))
    out = copilot_settings._verify("openai", "http://127.0.0.1:9/v1")
    assert out["ready"] is False and "refused" in out["why"]
    assert seen == ["https://api.openai.com/v1/models"]                      # a free request, no tokens
    monkeypatch.setattr(httpx, "get", lambda url, **kw: _Resp(200))
    assert copilot_settings._verify("openai", "")["verified"] is True
    monkeypatch.delenv("OPENAI_API_KEY")
    assert "No OPENAI_API_KEY" in copilot_settings._verify("openai", "")["why"]


def test_a_working_provider_is_offered_when_the_named_one_does_not_work(client, catalog, monkeypatch):
    # .env names portkey (no key); the startup check found OpenAI working: it becomes the default,
    # the LLM stays off until the analyst turns it on
    monkeypatch.setenv("COPILOT_DISABLED", "1")
    monkeypatch.setenv("LLM_PROVIDER", "portkey")
    checks = {"local": {"ready": False, "why": "none"}, "openai": {"ready": True, "verified": True},
              "huggingface": {"ready": True, "verified": True}, "portkey": {"ready": False, "why": "no key"}}
    monkeypatch.setattr(copilot_settings, "_CHECKS", checks)
    body = client.get("/api/copilot/settings").json()
    assert body["available"] == ["openai", "huggingface"]
    assert body["settings"]["provider"] == "openai" and body["settings"]["enabled"] is False
    assert "available: OpenAI, Hugging Face" in copilot_settings.summary(str(catalog))
    # A local server that works comes first, with its first model
    checks["local"] = {"ready": True, "verified": True, "models": ["qwen3:14b"]}
    s = client.get("/api/copilot/settings").json()["settings"]
    assert (s["provider"], s["model"]) == ("local", "qwen3:14b")
