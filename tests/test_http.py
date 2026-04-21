import pytest
import requests
from unittest.mock import MagicMock
import sefaz_mg_cert_monitor as mod
from sefaz_mg_cert_monitor import fetch_page_with_status, fetch_page, discover_downloads_url


def _mock_response(text, status_code, ok=True):
    resp = MagicMock()
    resp.ok = ok
    resp.status_code = status_code
    resp.text = text
    resp.apparent_encoding = "utf-8"
    return resp


# ---------------------------------------------------------------------------
# fetch_page_with_status
# ---------------------------------------------------------------------------

def test_fetch_page_with_status_success(monkeypatch):
    monkeypatch.setattr(mod.SESSION, "get", lambda url, timeout: _mock_response("<html>ok</html>", 200))
    body, status = fetch_page_with_status("http://example.com")
    assert body == "<html>ok</html>"
    assert status == 200


def test_fetch_page_with_status_not_found(monkeypatch):
    monkeypatch.setattr(mod.SESSION, "get", lambda url, timeout: _mock_response(None, 404, ok=False))
    body, status = fetch_page_with_status("http://example.com/missing")
    assert body is None
    assert status == 404


def test_fetch_page_with_status_server_error(monkeypatch):
    monkeypatch.setattr(mod.SESSION, "get", lambda url, timeout: _mock_response(None, 500, ok=False))
    body, status = fetch_page_with_status("http://example.com")
    assert body is None
    assert status == 500


def test_fetch_page_with_status_network_error(monkeypatch):
    def raise_exc(url, timeout):
        raise requests.RequestException("Connection refused")
    monkeypatch.setattr(mod.SESSION, "get", raise_exc)
    body, status = fetch_page_with_status("http://example.com")
    assert body is None
    assert status == 0


def test_fetch_page_with_status_timeout(monkeypatch):
    def raise_timeout(url, timeout):
        raise requests.Timeout("timed out")
    monkeypatch.setattr(mod.SESSION, "get", raise_timeout)
    body, status = fetch_page_with_status("http://example.com")
    assert body is None
    assert status == 0


# ---------------------------------------------------------------------------
# fetch_page
# ---------------------------------------------------------------------------

def test_fetch_page_returns_body(monkeypatch):
    monkeypatch.setattr(mod.SESSION, "get", lambda url, timeout: _mock_response("<p>Hello</p>", 200))
    assert fetch_page("http://example.com") == "<p>Hello</p>"


def test_fetch_page_returns_none_on_404(monkeypatch):
    monkeypatch.setattr(mod.SESSION, "get", lambda url, timeout: _mock_response(None, 404, ok=False))
    assert fetch_page("http://example.com") is None


def test_fetch_page_returns_none_on_network_error(monkeypatch):
    def raise_exc(url, timeout):
        raise requests.RequestException("timeout")
    monkeypatch.setattr(mod.SESSION, "get", raise_exc)
    assert fetch_page("http://example.com") is None


# ---------------------------------------------------------------------------
# discover_downloads_url
# ---------------------------------------------------------------------------

def test_discover_finds_downloads_link(monkeypatch):
    html = """<html><body><a href="/spedmg/nfe/downloads/">Downloads</a></body></html>"""
    monkeypatch.setattr(mod, "fetch_page", lambda url: html)
    result = discover_downloads_url("NF-e")
    assert result is not None
    assert "downloads" in result.lower()


def test_discover_finds_download_singular(monkeypatch):
    html = """<html><body><a href="/spedmg/nfce/download/">Download</a></body></html>"""
    monkeypatch.setattr(mod, "fetch_page", lambda url: html)
    result = discover_downloads_url("NFC-e")
    assert result is not None


def test_discover_finds_documentos_link(monkeypatch):
    html = """<html><body><a href="/spedmg/nf3e/documentos/">Documentos</a></body></html>"""
    monkeypatch.setattr(mod, "fetch_page", lambda url: html)
    result = discover_downloads_url("NF3-e")
    assert result is not None
    assert "documentos" in result.lower()


def test_discover_finds_documento_singular(monkeypatch):
    html = """<html><body><a href="/spedmg/bpe/documento/">Documento</a></body></html>"""
    monkeypatch.setattr(mod, "fetch_page", lambda url: html)
    result = discover_downloads_url("BP-e")
    assert result is not None


def test_discover_no_matching_link(monkeypatch):
    html = """<html><body><a href="/legislacao/">Legislação</a></body></html>"""
    monkeypatch.setattr(mod, "fetch_page", lambda url: html)
    result = discover_downloads_url("NF-e")
    assert result is None


def test_discover_unknown_module_returns_none():
    result = discover_downloads_url("MODULO_INEXISTENTE")
    assert result is None


def test_discover_fetch_fails_returns_none(monkeypatch):
    monkeypatch.setattr(mod, "fetch_page", lambda url: None)
    result = discover_downloads_url("NF-e")
    assert result is None


def test_discover_resolves_relative_url(monkeypatch):
    html = """<html><body><a href="downloads/">Downloads</a></body></html>"""
    monkeypatch.setattr(mod, "fetch_page", lambda url: html)
    result = discover_downloads_url("NF-e")
    assert result is not None
    assert result.startswith("https://")
