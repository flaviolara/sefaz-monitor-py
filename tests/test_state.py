import json
import pytest
from sefaz_mg_cert_monitor import load_state, save_state


def test_load_state_no_file(patch_state):
    assert load_state() == {}


def test_load_state_valid_json(patch_state):
    _, state_file = patch_state
    data = {"NF-e": {"hash": "abc123", "update_date": "01/01/2026"}}
    state_file.write_text(json.dumps(data), encoding="utf-8")
    assert load_state() == data


def test_load_state_corrupt_json(patch_state):
    _, state_file = patch_state
    state_file.write_text("isto não é json válido", encoding="utf-8")
    assert load_state() == {}


def test_load_state_empty_json_object(patch_state):
    _, state_file = patch_state
    state_file.write_text("{}", encoding="utf-8")
    assert load_state() == {}


def test_save_state_creates_file(patch_state):
    _, state_file = patch_state
    data = {"NF-e": {"hash": "def456"}}
    save_state(data)
    assert state_file.exists()


def test_save_state_content_is_correct(patch_state):
    _, state_file = patch_state
    data = {"CT-e": {"hash": "xyz", "update_date": "15/04/2026"}}
    save_state(data)
    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved == data


def test_save_state_round_trip(patch_state):
    data = {"MDF-e": {"hash": "roundtrip", "download_url": "/cert/mdfe.p7b"}}
    save_state(data)
    assert load_state() == data


def test_save_state_preserves_unicode(patch_state):
    data = {"NF-e": {"popup_title": "Troca de Certificação — aviso"}}
    save_state(data)
    loaded = load_state()
    assert loaded["NF-e"]["popup_title"] == "Troca de Certificação — aviso"


def test_save_state_overwrites_previous(patch_state):
    _, state_file = patch_state
    save_state({"NF-e": {"hash": "v1"}})
    save_state({"NF-e": {"hash": "v2"}})
    loaded = load_state()
    assert loaded["NF-e"]["hash"] == "v2"


def test_save_state_creates_dir_if_missing(tmp_path, monkeypatch):
    import sefaz_mg_cert_monitor as mod
    missing_dir = tmp_path / "new_state_dir"
    missing_file = missing_dir / "state.json"
    monkeypatch.setattr(mod, "STATE_DIR", missing_dir)
    monkeypatch.setattr(mod, "STATE_FILE", missing_file)
    save_state({"key": "value"})
    assert missing_file.exists()
