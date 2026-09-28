import io
import json
import zipfile
from pathlib import Path

import pytest

import browser
import config
import owner
import providers
import workspace


def test_safe_path_blocks_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(workspace, "BASE", tmp_path)
    with pytest.raises(workspace.WorkspaceError):
        workspace.safe_path("../etc/passwd", user_id="alice")
    ok = workspace.safe_path("app/index.html", user_id="alice")
    assert "alice" in str(ok)


def test_zip_slip_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(workspace, "BASE", tmp_path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil.txt", "nope")
        zf.writestr("ok.txt", "yes")
    extracted = workspace.import_zip(buf.getvalue(), user_id="bob")
    assert extracted == ["ok.txt"]
    assert not (tmp_path / "evil.txt").exists()


def test_browser_blocks_loopback():
    with pytest.raises(browser.BrowserError):
        browser._assert_public_url("http://127.0.0.1/")
    with pytest.raises(browser.BrowserError):
        browser._assert_public_url("http://localhost/admin")


def test_connection_info_labels_omegatech():
    info = providers.connection_info({
        "id": "claude",
        "kind": "http_get",
        "base_url": "https://omegatech-api.dixonomega.tech/api/ai",
        "path": "/Claude",
        "platform": "omegatech",
    })
    assert info["kind_label"] == "HTTP GET proxy"
    assert "omegatech-api.dixonomega.tech" in info["summary"]
    assert info["unofficial"] is True


def test_owner_key_match(monkeypatch):
    monkeypatch.setattr(config, "OWNER_KEY", "secret-owner")
    monkeypatch.setattr(config, "AUTH_MODE", "none")
    monkeypatch.setattr(config, "ALLOW_LOCAL_PROVIDER_EDIT", False)
    assert owner.is_owner("default", "secret-owner") is True
    assert owner.is_owner("default", "wrong") is False
    assert owner.is_owner("default", None) is False


def test_reserved_provider_ids(tmp_path, monkeypatch):
    pf = tmp_path / "providers.json"
    pf.write_text(json.dumps([]))
    monkeypatch.setattr(providers, "PROVIDERS_FILE", pf)
    with pytest.raises(providers.ProviderError, match="reserved"):
        providers.add_provider({
            "id": "auto",
            "kind": "openai_compatible",
            "base_url": "https://example.com/v1",
            "model": "x",
        })


def test_add_and_remove_provider(tmp_path, monkeypatch):
    pf = tmp_path / "providers.json"
    pf.write_text(json.dumps([]))
    monkeypatch.setattr(providers, "PROVIDERS_FILE", pf)
    cfg = providers.add_provider({
        "id": "test-llm",
        "name": "Test",
        "kind": "openai_compatible",
        "base_url": "https://api.example.com/v1",
        "model": "demo",
        "api_key_env": "DEMO_KEY",
    })
    assert cfg["id"] == "test-llm"
    assert "test-llm" in providers.list_provider_ids()
    redacted = providers.redact(cfg)
    assert redacted.get("api_key") in (None, "***")
    providers.remove_provider("test-llm")
    assert "test-llm" not in providers.list_provider_ids()


def test_providers_file_parent_created(tmp_path, monkeypatch):
    nested = tmp_path / "data" / "providers.json"
    monkeypatch.setattr(providers, "PROVIDERS_FILE", nested)
    providers.add_provider({
        "id": "nested-one",
        "kind": "http_get",
        "base_url": "https://example.com",
        "path": "/x",
    })
    assert nested.exists()
