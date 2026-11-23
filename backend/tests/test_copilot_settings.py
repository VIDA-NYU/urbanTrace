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
