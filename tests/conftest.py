import json
import pytest
import sefaz_mg_cert_monitor as mod

# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

HTML_WITH_POPUP_AND_DOWNLOAD = """\
<html><body>
  <h4>Troca de Certificado</h4>
  <p>O certificado será atualizado em 20/04/2026.
     <a href="/cert/cadeia_certificacao.p7b">Cadeia de Certificação</a>
  </p>
</body></html>
"""

HTML_WITH_DOWNLOAD_ONLY = """\
<html><body>
  <h2>Downloads NF-e</h2>
  <p>Atualizado dia 10/03/2026
     <a href="/downloads/cadeia.p7b">Cadeia de Certificação</a>
  </p>
</body></html>
"""

HTML_WITH_CHAVE_PUBLICA = """\
<html><body>
  <a href="/cert/chave_publica.pem">Chave Pública</a>
</body></html>
"""

HTML_V2 = """\
<html><body>
  <h4>Troca de Certificado</h4>
  <p>Atualizado dia 01/05/2026
     <a href="/cert/cadeia_v2.p7b">Cadeia de Certificação</a>
  </p>
</body></html>
"""

HTML_MINIMAL = "<html><body><p>Sem conteúdo relevante</p></body></html>"

HTML_DISCOVERY_DOWNLOADS = """\
<html><body>
<nav>
  <a href="/spedmg/nfe/downloads/">Downloads</a>
  <a href="/spedmg/nfe/legislacao/">Legislação</a>
</nav>
</body></html>
"""

HTML_DISCOVERY_DOCUMENTOS = """\
<html><body>
<nav>
  <a href="/spedmg/nf3e/documentos/">Documentos</a>
</nav>
</body></html>
"""

SAMPLE_CHANGE = {
    "module": "NF-e",
    "url": "https://portalsped.fazenda.mg.gov.br/spedmg/nfe/downloads/",
    "update_date": "20/04/2026",
    "download_url": "/cert/cadeia.p7b",
    "popup_title": "Troca de Certificado",
    "popup_message": "Aviso de troca",
    "previous_date": "01/01/2026",
    "previous_hash": "old_hash",
    "new_hash": "new_hash",
}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def patch_state(tmp_path, monkeypatch):
    """Redireciona STATE_DIR e STATE_FILE para diretório temporário."""
    state_dir = tmp_path / ".state_log"
    state_dir.mkdir()
    state_file = state_dir / "state.json"
    monkeypatch.setattr(mod, "STATE_DIR", state_dir)
    monkeypatch.setattr(mod, "STATE_FILE", state_file)
    return state_dir, state_file


@pytest.fixture
def saved_state(patch_state):
    """Cria um arquivo de estado pré-populado."""
    _, state_file = patch_state
    state = {
        "NF-e": {
            "hash": "abc123",
            "update_date": "01/01/2026",
            "download_url": "/cert/cadeia.p7b",
            "popup_title": None,
            "checked_at": "2026-01-01T10:00:00",
        }
    }
    state_file.write_text(json.dumps(state), encoding="utf-8")
    return state_file, state
