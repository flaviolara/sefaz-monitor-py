import logging
import pytest
from unittest.mock import MagicMock, patch, call
import sefaz_mg_cert_monitor as mod
from sefaz_mg_cert_monitor import notify_email, notify_telegram, notify_webhook, send_notifications

CHANGES = [
    {
        "module": "NF-e",
        "url": "https://portalsped.fazenda.mg.gov.br/spedmg/nfe/downloads/",
        "update_date": "20/04/2026",
        "download_url": "/cert/cadeia.p7b",
        "popup_title": "Troca de Certificado",
        "popup_message": "Aviso de troca de certificado",
        "previous_date": "01/01/2026",
        "previous_hash": "old_hash",
        "new_hash": "new_hash",
    }
]


# ---------------------------------------------------------------------------
# notify_email
# ---------------------------------------------------------------------------

def test_notify_email_skips_without_smtp_host(monkeypatch):
    monkeypatch.setattr(mod, "SMTP_HOST", "")
    monkeypatch.setattr(mod, "MAIL_TO", "dest@example.com")
    with patch("sefaz_mg_cert_monitor.smtplib.SMTP") as mock_smtp:
        notify_email("Assunto", "Corpo")
        mock_smtp.assert_not_called()


def test_notify_email_skips_without_mail_to(monkeypatch):
    monkeypatch.setattr(mod, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(mod, "MAIL_TO", "")
    with patch("sefaz_mg_cert_monitor.smtplib.SMTP") as mock_smtp:
        notify_email("Assunto", "Corpo")
        mock_smtp.assert_not_called()


def test_notify_email_calls_sendmail(monkeypatch):
    monkeypatch.setattr(mod, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(mod, "SMTP_PORT", 587)
    monkeypatch.setattr(mod, "SMTP_USER", "user@example.com")
    monkeypatch.setattr(mod, "SMTP_PASS", "secret")
    monkeypatch.setattr(mod, "MAIL_FROM", "from@example.com")
    monkeypatch.setattr(mod, "MAIL_TO", "to@example.com")

    mock_server = MagicMock()
    with patch("sefaz_mg_cert_monitor.smtplib.SMTP") as mock_smtp_cls:
        mock_smtp_cls.return_value.__enter__ = lambda s: mock_server
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        notify_email("Assunto", "Corpo")
        mock_server.sendmail.assert_called_once()


def test_notify_email_multiple_recipients(monkeypatch):
    monkeypatch.setattr(mod, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(mod, "SMTP_PORT", 587)
    monkeypatch.setattr(mod, "SMTP_USER", "user@example.com")
    monkeypatch.setattr(mod, "SMTP_PASS", "secret")
    monkeypatch.setattr(mod, "MAIL_FROM", "from@example.com")
    monkeypatch.setattr(mod, "MAIL_TO", "a@b.com;c@d.com;e@f.com")

    mock_server = MagicMock()
    with patch("sefaz_mg_cert_monitor.smtplib.SMTP") as mock_smtp_cls:
        mock_smtp_cls.return_value.__enter__ = lambda s: mock_server
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        notify_email("Assunto", "Corpo")
        recipients = mock_server.sendmail.call_args[0][1]
        assert len(recipients) == 3


def test_notify_email_exception_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(mod, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(mod, "SMTP_PORT", 587)
    monkeypatch.setattr(mod, "SMTP_USER", "u")
    monkeypatch.setattr(mod, "SMTP_PASS", "p")
    monkeypatch.setattr(mod, "MAIL_FROM", "f@f.com")
    monkeypatch.setattr(mod, "MAIL_TO", "t@t.com")
    with patch("sefaz_mg_cert_monitor.smtplib.SMTP", side_effect=Exception("SMTP error")):
        with caplog.at_level(logging.ERROR, logger="sefaz_monitor"):
            notify_email("Assunto", "Corpo")
        assert "Falha" in caplog.text


# ---------------------------------------------------------------------------
# notify_telegram
# ---------------------------------------------------------------------------

def test_notify_telegram_skips_without_token(monkeypatch):
    monkeypatch.setattr(mod, "TELEGRAM_TOKEN", "")
    monkeypatch.setattr(mod, "TELEGRAM_CHAT_ID", "123456")
    with patch.object(mod.requests, "post") as mock_post:
        notify_telegram("Olá")
        mock_post.assert_not_called()


def test_notify_telegram_skips_without_chat_id(monkeypatch):
    monkeypatch.setattr(mod, "TELEGRAM_TOKEN", "token123")
    monkeypatch.setattr(mod, "TELEGRAM_CHAT_ID", "")
    with patch.object(mod.requests, "post") as mock_post:
        notify_telegram("Olá")
        mock_post.assert_not_called()


def test_notify_telegram_sends_message(monkeypatch):
    monkeypatch.setattr(mod, "TELEGRAM_TOKEN", "bot_token_abc")
    monkeypatch.setattr(mod, "TELEGRAM_CHAT_ID", "987654")
    with patch.object(mod.requests, "post") as mock_post:
        notify_telegram("<b>SEFAZ</b>: atualização")
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        url = call_args[0][0]
        data = call_args[1]["data"]
        assert "api.telegram.org" in url
        assert "bot_token_abc" in url
        assert data["chat_id"] == "987654"
        assert data["parse_mode"] == "HTML"


def test_notify_telegram_exception_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(mod, "TELEGRAM_TOKEN", "token")
    monkeypatch.setattr(mod, "TELEGRAM_CHAT_ID", "123")
    with patch.object(mod.requests, "post", side_effect=Exception("Network error")):
        with caplog.at_level(logging.ERROR, logger="sefaz_monitor"):
            notify_telegram("Olá")
        assert "Falha" in caplog.text


# ---------------------------------------------------------------------------
# notify_webhook
# ---------------------------------------------------------------------------

def test_notify_webhook_skips_without_url(monkeypatch):
    monkeypatch.setattr(mod, "WEBHOOK_URL", "")
    with patch.object(mod.requests, "post") as mock_post:
        notify_webhook({"event": "test"})
        mock_post.assert_not_called()


def test_notify_webhook_sends_json(monkeypatch):
    monkeypatch.setattr(mod, "WEBHOOK_URL", "https://hooks.example.com/notify")
    with patch.object(mod.requests, "post") as mock_post:
        payload = {"event": "sefaz_mg_cert_update", "changes": []}
        notify_webhook(payload)
        mock_post.assert_called_once_with(
            "https://hooks.example.com/notify",
            json=payload,
            timeout=15,
        )


def test_notify_webhook_exception_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(mod, "WEBHOOK_URL", "https://hooks.example.com/notify")
    with patch.object(mod.requests, "post", side_effect=Exception("Connection error")):
        with caplog.at_level(logging.ERROR, logger="sefaz_monitor"):
            notify_webhook({"event": "test"})
        assert "Falha" in caplog.text


# ---------------------------------------------------------------------------
# send_notifications
# ---------------------------------------------------------------------------

def test_send_notifications_calls_all_channels(monkeypatch):
    mock_email = MagicMock()
    mock_tg = MagicMock()
    mock_wh = MagicMock()
    monkeypatch.setattr(mod, "notify_email", mock_email)
    monkeypatch.setattr(mod, "notify_telegram", mock_tg)
    monkeypatch.setattr(mod, "notify_webhook", mock_wh)

    send_notifications(CHANGES)
    mock_email.assert_called_once()
    mock_tg.assert_called_once()
    mock_wh.assert_called_once()


def test_send_notifications_email_body_contains_module(monkeypatch):
    captured = {}

    def capture(subject, body):
        captured["subject"] = subject
        captured["body"] = body

    monkeypatch.setattr(mod, "notify_email", capture)
    monkeypatch.setattr(mod, "notify_telegram", lambda t: None)
    monkeypatch.setattr(mod, "notify_webhook", lambda p: None)

    send_notifications(CHANGES)
    assert "NF-e" in captured["body"]
    assert "20/04/2026" in captured["body"]
    assert "[SEFAZ-MG]" in captured["subject"]


def test_send_notifications_webhook_payload_has_changes(monkeypatch):
    captured = {}
    monkeypatch.setattr(mod, "notify_email", lambda s, b: None)
    monkeypatch.setattr(mod, "notify_telegram", lambda t: None)
    monkeypatch.setattr(mod, "notify_webhook", lambda p: captured.update(p))

    send_notifications(CHANGES)
    assert captured["event"] == "sefaz_mg_cert_update"
    assert len(captured["changes"]) == 1
    assert captured["changes"][0]["module"] == "NF-e"


def test_send_notifications_telegram_uses_html_tags(monkeypatch):
    captured = {}
    monkeypatch.setattr(mod, "notify_email", lambda s, b: None)
    monkeypatch.setattr(mod, "notify_telegram", lambda t: captured.update({"text": t}))
    monkeypatch.setattr(mod, "notify_webhook", lambda p: None)

    send_notifications(CHANGES)
    assert "<b>" in captured["text"]
