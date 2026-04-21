import json
import pytest
from unittest.mock import MagicMock
import sefaz_mg_cert_monitor as mod
from sefaz_mg_cert_monitor import check_once

SINGLE_MODULE = {"NF-e": "https://portalsped.fazenda.mg.gov.br/spedmg/nfe/downloads/"}

HTML_V1 = """\
<html><body>
  <h4>Cadeia de Certificação</h4>
  <p>Atualizado dia 01/01/2026
     <a href="/cert/cadeia_v1.p7b">Cadeia de Certificação</a>
  </p>
</body></html>
"""

HTML_V2 = """\
<html><body>
  <h4>Cadeia de Certificação</h4>
  <p>Atualizado dia 01/05/2026
     <a href="/cert/cadeia_v2.p7b">Cadeia de Certificação</a>
  </p>
</body></html>
"""


@pytest.fixture(autouse=True)
def no_smtp(monkeypatch):
    """Garante que SMTP_HOST não está configurado por padrão."""
    monkeypatch.setattr(mod, "SMTP_HOST", "")
    monkeypatch.setattr(mod, "SMTP_PASS", "")


@pytest.fixture
def mock_notify(monkeypatch):
    m = MagicMock()
    monkeypatch.setattr(mod, "send_notifications", m)
    return m


# ---------------------------------------------------------------------------
# Primeira execução (estado inicial)
# ---------------------------------------------------------------------------

def test_check_once_first_run_returns_no_changes(monkeypatch, patch_state, mock_notify):
    monkeypatch.setattr(mod, "MONITORED_URLS", SINGLE_MODULE)
    monkeypatch.setattr(mod, "fetch_page_with_status", lambda url: (HTML_V1, 200))
    changes = check_once()
    assert changes == []


def test_check_once_first_run_no_notification(monkeypatch, patch_state, mock_notify):
    monkeypatch.setattr(mod, "MONITORED_URLS", SINGLE_MODULE)
    monkeypatch.setattr(mod, "fetch_page_with_status", lambda url: (HTML_V1, 200))
    check_once()
    mock_notify.assert_not_called()


def test_check_once_first_run_saves_state(monkeypatch, patch_state, mock_notify):
    _, state_file = patch_state
    monkeypatch.setattr(mod, "MONITORED_URLS", SINGLE_MODULE)
    monkeypatch.setattr(mod, "fetch_page_with_status", lambda url: (HTML_V1, 200))
    check_once()
    assert state_file.exists()
    state = json.loads(state_file.read_text())
    assert "NF-e" in state
    assert state["NF-e"]["hash"] != ""


# ---------------------------------------------------------------------------
# Segunda execução sem mudança
# ---------------------------------------------------------------------------

def test_check_once_no_change_second_run(monkeypatch, patch_state, mock_notify):
    monkeypatch.setattr(mod, "MONITORED_URLS", SINGLE_MODULE)
    monkeypatch.setattr(mod, "fetch_page_with_status", lambda url: (HTML_V1, 200))
    check_once()
    changes = check_once()
    assert changes == []
    mock_notify.assert_not_called()


# ---------------------------------------------------------------------------
# Mudança de conteúdo detectada
# ---------------------------------------------------------------------------

def test_check_once_detects_content_change(monkeypatch, patch_state, mock_notify):
    monkeypatch.setattr(mod, "MONITORED_URLS", SINGLE_MODULE)
    responses = iter([(HTML_V1, 200), (HTML_V2, 200)])
    monkeypatch.setattr(mod, "fetch_page_with_status", lambda url: next(responses))
    check_once()
    changes = check_once()
    assert len(changes) == 1
    assert changes[0]["module"] == "NF-e"


def test_check_once_change_contains_expected_fields(monkeypatch, patch_state, mock_notify):
    monkeypatch.setattr(mod, "MONITORED_URLS", SINGLE_MODULE)
    responses = iter([(HTML_V1, 200), (HTML_V2, 200)])
    monkeypatch.setattr(mod, "fetch_page_with_status", lambda url: next(responses))
    check_once()
    changes = check_once()
    c = changes[0]
    assert "module" in c
    assert "url" in c
    assert "new_hash" in c
    assert "previous_hash" in c


def test_check_once_sends_notification_on_change(monkeypatch, patch_state, mock_notify):
    monkeypatch.setattr(mod, "MONITORED_URLS", SINGLE_MODULE)
    responses = iter([(HTML_V1, 200), (HTML_V2, 200)])
    monkeypatch.setattr(mod, "fetch_page_with_status", lambda url: next(responses))
    check_once()
    check_once()
    mock_notify.assert_called_once()


def test_check_once_updates_state_after_change(monkeypatch, patch_state, mock_notify):
    _, state_file = patch_state
    monkeypatch.setattr(mod, "MONITORED_URLS", SINGLE_MODULE)
    responses = iter([(HTML_V1, 200), (HTML_V2, 200)])
    monkeypatch.setattr(mod, "fetch_page_with_status", lambda url: next(responses))
    check_once()
    old_state = json.loads(state_file.read_text())
    check_once()
    new_state = json.loads(state_file.read_text())
    assert old_state["NF-e"]["hash"] != new_state["NF-e"]["hash"]


# ---------------------------------------------------------------------------
# Falha de acesso / módulo inacessível
# ---------------------------------------------------------------------------

def test_check_once_skips_inaccessible_module(monkeypatch, patch_state, mock_notify):
    monkeypatch.setattr(mod, "MONITORED_URLS", SINGLE_MODULE)
    monkeypatch.setattr(mod, "fetch_page_with_status", lambda url: (None, 500))
    changes = check_once()
    assert changes == []


def test_check_once_404_triggers_autodiscovery(monkeypatch, patch_state, mock_notify):
    monkeypatch.setattr(mod, "MONITORED_URLS", SINGLE_MODULE)

    discovered_url = "https://portalsped.fazenda.mg.gov.br/spedmg/nfe/novos-downloads/"

    def mock_fetch(url):
        if url == SINGLE_MODULE["NF-e"]:
            return None, 404
        return HTML_V1, 200

    mock_discover = MagicMock(return_value=discovered_url)
    monkeypatch.setattr(mod, "fetch_page_with_status", mock_fetch)
    monkeypatch.setattr(mod, "discover_downloads_url", mock_discover)

    check_once()
    mock_discover.assert_called_once_with("NF-e")


def test_check_once_404_without_discovery_skips_module(monkeypatch, patch_state, mock_notify):
    _, state_file = patch_state
    monkeypatch.setattr(mod, "MONITORED_URLS", SINGLE_MODULE)
    monkeypatch.setattr(mod, "fetch_page_with_status", lambda url: (None, 404))
    monkeypatch.setattr(mod, "discover_downloads_url", lambda mod_name: None)
    check_once()
    # Módulo não salvo no estado pois não foi possível acessar
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    assert "NF-e" not in state


# ---------------------------------------------------------------------------
# Validação de segurança (SMTP sem senha)
# ---------------------------------------------------------------------------

def test_check_once_raises_if_smtp_host_without_pass(monkeypatch, patch_state):
    monkeypatch.setattr(mod, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(mod, "SMTP_PASS", "")
    with pytest.raises(RuntimeError, match="SEFAZ_SMTP_PASS"):
        check_once()


def test_check_once_ok_with_smtp_host_and_pass(monkeypatch, patch_state, mock_notify):
    monkeypatch.setattr(mod, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(mod, "SMTP_PASS", "secret")
    monkeypatch.setattr(mod, "MONITORED_URLS", SINGLE_MODULE)
    monkeypatch.setattr(mod, "fetch_page_with_status", lambda url: (HTML_V1, 200))
    # Não deve lançar exceção
    check_once()


# ---------------------------------------------------------------------------
# Múltiplos módulos
# ---------------------------------------------------------------------------

def test_check_once_handles_multiple_modules(monkeypatch, patch_state, mock_notify):
    two_modules = {
        "NF-e": "https://portalsped.fazenda.mg.gov.br/spedmg/nfe/downloads/",
        "NFC-e": "https://portalsped.fazenda.mg.gov.br/spedmg/nfce/Downloads/",
    }
    monkeypatch.setattr(mod, "MONITORED_URLS", two_modules)
    monkeypatch.setattr(mod, "fetch_page_with_status", lambda url: (HTML_V1, 200))
    check_once()
    state = json.loads(patch_state[1].read_text())
    assert "NF-e" in state
    assert "NFC-e" in state
