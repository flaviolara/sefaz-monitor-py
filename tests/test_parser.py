import hashlib
import pytest
from sefaz_mg_cert_monitor import parse_page


def _empty_hash() -> str:
    # 5 partes vazias unidas com "|" → "||||" (4 pipes)
    return hashlib.sha256("|".join([""] * 5).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Estrutura básica
# ---------------------------------------------------------------------------

def test_parse_empty_html_returns_nones():
    info = parse_page("<html><body></body></html>")
    assert info.popup_title is None
    assert info.popup_message is None
    assert info.download_text is None
    assert info.download_url is None
    assert info.update_date is None


def test_parse_empty_html_has_valid_hash():
    info = parse_page("<html><body></body></html>")
    assert len(info.raw_hash) == 64
    assert info.raw_hash == _empty_hash()


# ---------------------------------------------------------------------------
# Popup / alertas de certificado
# ---------------------------------------------------------------------------

def test_parse_detects_popup_h4():
    html = "<html><body><h4>Troca de Certificado</h4><p>Aviso</p></body></html>"
    info = parse_page(html)
    assert info.popup_title == "Troca de Certificado"


def test_parse_detects_popup_h3():
    html = "<html><body><h3>Cadeia de Certificação</h3><div>msg</div></body></html>"
    info = parse_page(html)
    assert info.popup_title == "Cadeia de Certificação"


def test_parse_detects_popup_h5():
    html = "<html><body><h5>Novo Certificado</h5><div>texto</div></body></html>"
    info = parse_page(html)
    assert info.popup_title == "Novo Certificado"


def test_parse_popup_includes_parent_message():
    html = """<html><body>
    <div><h4>Troca de Certificado</h4><p>O certificado foi atualizado.</p></div>
    </body></html>"""
    info = parse_page(html)
    assert info.popup_message is not None
    assert "Troca de Certificado" in info.popup_message


def test_parse_popup_fallback_via_text():
    html = "<html><body><span>Troca de Certificado em breve</span></body></html>"
    info = parse_page(html)
    assert info.popup_title == "Troca de Certificado"
    assert "em breve" in info.popup_message


def test_parse_no_popup_when_unrelated_headers():
    html = "<html><body><h4>Documentos Fiscais</h4></body></html>"
    info = parse_page(html)
    assert info.popup_title is None


# ---------------------------------------------------------------------------
# Links de download
# ---------------------------------------------------------------------------

def test_parse_download_link_cadeia_text():
    html = """<html><body>
    <a href="/cert/cadeia.p7b">Cadeia de Certificação</a>
    </body></html>"""
    info = parse_page(html)
    assert info.download_url == "/cert/cadeia.p7b"
    assert info.download_text == "Cadeia de Certificação"


def test_parse_download_link_chave_publica_href():
    html = """<html><body>
    <a href="/cert/chave_publica.pem">Baixar chave</a>
    </body></html>"""
    info = parse_page(html)
    assert info.download_url == "/cert/chave_publica.pem"


def test_parse_download_link_cadeia_in_href():
    html = """<html><body>
    <a href="/downloads/cadeia_cert.zip">Baixar</a>
    </body></html>"""
    info = parse_page(html)
    assert info.download_url == "/downloads/cadeia_cert.zip"


def test_parse_no_download_link():
    html = "<html><body><a href='/doc.pdf'>Documento qualquer</a></body></html>"
    info = parse_page(html)
    assert info.download_url is None


# ---------------------------------------------------------------------------
# Extração de data
# ---------------------------------------------------------------------------

def test_parse_date_with_dia():
    html = """<html><body>
    <p>Atualizado dia 15/04/2026
       <a href="/cert/cadeia.p7b">Cadeia de Certificação</a>
    </p>
    </body></html>"""
    info = parse_page(html)
    assert info.update_date == "15/04/2026"


def test_parse_date_without_dia():
    html = """<html><body>
    <p>Atualizada 01/01/2026 <a href="/cert/cadeia.p7b">Cadeia de Certificação</a></p>
    </body></html>"""
    info = parse_page(html)
    assert info.update_date == "01/01/2026"


def test_parse_date_case_insensitive():
    html = """<html><body>
    <p>ATUALIZADO dia 31/12/2025 <a href="/cert/cadeia.p7b">Cadeia de Certificação</a></p>
    </body></html>"""
    info = parse_page(html)
    assert info.update_date == "31/12/2025"


def test_parse_no_date_without_download_link():
    html = "<html><body><p>Atualizado dia 10/10/2026</p></body></html>"
    info = parse_page(html)
    # data só é extraída no contexto do link de download
    assert info.update_date is None


# ---------------------------------------------------------------------------
# Hash SHA-256
# ---------------------------------------------------------------------------

def test_parse_hash_is_deterministic():
    html = "<html><body><h4>Cadeia de Certificação</h4></body></html>"
    h1 = parse_page(html).raw_hash
    h2 = parse_page(html).raw_hash
    assert h1 == h2


def test_parse_hash_changes_with_different_download_url():
    html_a = """<html><body><a href="/cert/v1.p7b">Cadeia de Certificação</a></body></html>"""
    html_b = """<html><body><a href="/cert/v2.p7b">Cadeia de Certificação</a></body></html>"""
    assert parse_page(html_a).raw_hash != parse_page(html_b).raw_hash


def test_parse_hash_changes_with_different_date():
    base = """<html><body><p>Atualizado dia {d} <a href="/cert/cadeia.p7b">Cadeia de Certificação</a></p></body></html>"""
    h1 = parse_page(base.format(d="01/01/2026")).raw_hash
    h2 = parse_page(base.format(d="01/02/2026")).raw_hash
    assert h1 != h2


def test_parse_hash_is_hex_sha256():
    info = parse_page("<html><body></body></html>")
    int(info.raw_hash, 16)  # não lança exceção se for hex válido
    assert len(info.raw_hash) == 64
