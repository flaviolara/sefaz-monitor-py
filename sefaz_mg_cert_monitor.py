#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SEFAZ-MG Certificate Update Monitor (Python)
=============================================
Monitora as páginas do portal SPED-MG buscando alterações nos avisos de
troca de certificado (popup "Troca de Certificado") e nos links de download
da cadeia de certificação.

Dependências:
    pip install requests beautifulsoup4

Uso:
    python sefaz_mg_cert_monitor.py              # execução única
    python sefaz_mg_cert_monitor.py --daemon      # loop contínuo (padrão: 1h)
    python sefaz_mg_cert_monitor.py --interval 1800
    python sefaz_mg_cert_monitor.py --status
    python sefaz_mg_cert_monitor.py --reset

Cron (a cada hora, seg-sex, 7h-20h):
    0 7-20 * * 1-5 /usr/bin/python3 /opt/sefaz-monitor/sefaz_mg_cert_monitor.py
"""

import argparse
import hashlib
import json
import logging
import os
import re
import smtplib
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
# URLs verificadas em 14/04/2026 — o servidor é case-sensitive!
# Cada módulo usa casing diferente no path. NF3-e usa "Documentos" em vez de "Downloads".
MONITORED_URLS: dict[str, str] = {
    "NF-e":    "https://portalsped.fazenda.mg.gov.br/spedmg/nfe/downloads/",
    "NFC-e":   "https://portalsped.fazenda.mg.gov.br/spedmg/nfce/Downloads/",
    "CT-e":    "https://portalsped.fazenda.mg.gov.br/spedmg/cte/downloadsPasta/",
    "CT-e OS": "https://portalsped.fazenda.mg.gov.br/spedmg/cteos/Downloads/",
    "MDF-e":   "https://portalsped.fazenda.mg.gov.br/spedmg/mdfe/downloads/",
    "BP-e":    "https://portalsped.fazenda.mg.gov.br/spedmg/bpe/Downloads/",
    "NF3-e":   "https://portalsped.fazenda.mg.gov.br/spedmg/nf3e/Documentos/",
    "NFCom":   "https://portalsped.fazenda.mg.gov.br/spedmg/nfcom/downloads/",
}

# Páginas raiz de cada módulo (usadas para auto-discovery se a URL falhar)
MODULE_ROOTS: dict[str, str] = {
    "NF-e":    "https://portalsped.fazenda.mg.gov.br/spedmg/nfe/",
    "NFC-e":   "https://portalsped.fazenda.mg.gov.br/spedmg/nfce/",
    "CT-e":    "https://portalsped.fazenda.mg.gov.br/spedmg/cte/",
    "CT-e OS": "https://portalsped.fazenda.mg.gov.br/spedmg/cteos/",
    "MDF-e":   "https://portalsped.fazenda.mg.gov.br/spedmg/mdfe/",
    "BP-e":    "https://portalsped.fazenda.mg.gov.br/spedmg/bpe/",
    "NF3-e":   "https://portalsped.fazenda.mg.gov.br/spedmg/nf3e/",
    "NFCom":   "https://portalsped.fazenda.mg.gov.br/spedmg/nfcom/",
}

STATE_DIR = Path.home() / ".sefaz_monitor"
STATE_FILE = STATE_DIR / "state.json"
LOG_FILE = STATE_DIR / "monitor.log"

# Notificações via variáveis de ambiente
SMTP_HOST = os.environ.get("SEFAZ_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SEFAZ_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SEFAZ_SMTP_USER", "")
SMTP_PASS = os.environ.get("SEFAZ_SMTP_PASS", "")
MAIL_FROM = os.environ.get("SEFAZ_MAIL_FROM", "")
MAIL_TO = os.environ.get("SEFAZ_MAIL_TO", "")  # separar com ;

TELEGRAM_TOKEN = os.environ.get("SEFAZ_TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("SEFAZ_TELEGRAM_CHAT_ID", "")

WEBHOOK_URL = os.environ.get("SEFAZ_WEBHOOK_URL", "")

DEFAULT_INTERVAL = 3600
HTTP_TIMEOUT = 30

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
STATE_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("sefaz_monitor")
logger.setLevel(logging.INFO)

from logging.handlers import RotatingFileHandler

file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=1_048_576, backupCount=5, encoding="utf-8"
)
console_handler = logging.StreamHandler(sys.stdout)

formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": f"SefazMG-CertMonitor/1.0 (Python/{sys.version_info.major}.{sys.version_info.minor})",
    "Accept": "text/html",
})


def fetch_page_with_status(url: str) -> tuple[Optional[str], int]:
    """Busca o HTML de uma página. Retorna (body, status_code)."""
    try:
        resp = SESSION.get(url, timeout=HTTP_TIMEOUT)
        if resp.ok:
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text, resp.status_code
        return None, resp.status_code
    except requests.RequestException as e:
        logger.error("Erro ao buscar %s: %s", url, e)
        return None, 0


def fetch_page(url: str) -> Optional[str]:
    """Busca o HTML de uma página."""
    body, _ = fetch_page_with_status(url)
    return body


def discover_downloads_url(mod_name: str) -> Optional[str]:
    """Auto-discovery: busca o link de downloads/documentos no menu lateral da página raiz."""
    root_url = MODULE_ROOTS.get(mod_name)
    if not root_url:
        return None

    logger.info("    Auto-discovery: buscando link de downloads em %s...", root_url)
    html = fetch_page(root_url)
    if not html:
        return None

    from urllib.parse import urljoin

    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        text = link.get_text(strip=True).lower()
        if text in ("downloads", "download", "documentos", "documento"):
            resolved = urljoin(root_url, link["href"])
            logger.info("    Auto-discovery: encontrado '%s' → %s", link.get_text(strip=True), resolved)
            return resolved

    logger.warning("    Auto-discovery: nenhum link de downloads encontrado em %s", root_url)
    return None


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
@dataclass
class PageInfo:
    popup_title: Optional[str] = None
    popup_message: Optional[str] = None
    download_text: Optional[str] = None
    download_url: Optional[str] = None
    update_date: Optional[str] = None
    raw_hash: str = ""


DATE_PATTERN = re.compile(
    r"atualiza\S*\s+(?:dia\s+)?(\d{1,2}/\d{1,2}/\d{4})", re.IGNORECASE
)
CERT_LINK_PATTERN = re.compile(r"cadeia\s+de\s+certifica", re.IGNORECASE)
CERT_HREF_PATTERN = re.compile(r"cadeia|chave_publica", re.IGNORECASE)
POPUP_PATTERN = re.compile(r"troca\s+de\s+certificado", re.IGNORECASE)


def parse_page(html: str) -> PageInfo:
    """Extrai informações relevantes do HTML."""
    soup = BeautifulSoup(html, "html.parser")
    info = PageInfo()

    # 1) Popup "Troca de Certificado"
    for h4 in soup.find_all(["h4", "h3", "h5"]):
        text = h4.get_text(strip=True)
        if re.search(r"certificado|cadeia|troca", text, re.IGNORECASE):
            info.popup_title = text
            parent = h4.parent
            if parent:
                info.popup_message = re.sub(r"\s+", " ", parent.get_text(strip=True))
            break

    # Fallback: busca qualquer nó com "Troca de Certificado"
    if not info.popup_title:
        for tag in soup.find_all(string=POPUP_PATTERN):
            block = tag.parent
            if block:
                info.popup_title = "Troca de Certificado"
                info.popup_message = re.sub(r"\s+", " ", block.get_text(strip=True))
                break

    # 2) Link de download da cadeia de certificação
    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text(strip=True)

        if CERT_LINK_PATTERN.search(text) or CERT_HREF_PATTERN.search(href):
            info.download_text = text
            info.download_url = href

            # Extrai data do contexto (texto do pai)
            context = link.parent.get_text(strip=True) if link.parent else text
            match = DATE_PATTERN.search(context)
            if match:
                info.update_date = match.group(1)
            break

    # 3) Hash SHA256 do conteúdo relevante
    parts = [
        info.popup_title or "",
        info.popup_message or "",
        info.download_text or "",
        info.download_url or "",
        info.update_date or "",
    ]
    info.raw_hash = hashlib.sha256("|".join(parts).encode()).hexdigest()

    return info


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Notificações
# ---------------------------------------------------------------------------
def notify_email(subject: str, body: str) -> None:
    if not SMTP_HOST or not MAIL_TO:
        return
    try:
        recipients = [r.strip() for r in MAIL_TO.split(";") if r.strip()]
        msg = MIMEMultipart()
        msg["From"] = f"SEFAZ-MG Monitor <{MAIL_FROM}>"
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(MAIL_FROM, recipients, msg.as_string())

        logger.info("E-mail enviado para %s", ", ".join(recipients))
    except Exception as e:
        logger.error("Falha ao enviar e-mail: %s", e)


def notify_telegram(text: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }, timeout=15)
        logger.info("Notificação Telegram enviada")
    except Exception as e:
        logger.error("Falha ao enviar Telegram: %s", e)


def notify_webhook(payload: dict) -> None:
    if not WEBHOOK_URL:
        return
    try:
        requests.post(WEBHOOK_URL, json=payload, timeout=15)
        logger.info("Webhook enviado")
    except Exception as e:
        logger.error("Falha ao enviar webhook: %s", e)


def send_notifications(changes: list[dict]) -> None:
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Texto plano
    lines = [
        "SEFAZ-MG — Atualização de Certificados Detectada",
        "=" * 50,
        "",
    ]
    for c in changes:
        lines.append(f"Módulo: {c['module']}")
        lines.append(f"URL: {c['url']}")
        lines.append(f"Data certificado: {c.get('update_date') or 'N/D'}")
        lines.append(f"Download: {c.get('download_url') or 'N/D'}")
        popup = c.get("popup_message") or "N/D"
        lines.append(f"Popup: {popup[:200]}")
        lines.append("")
    lines.append(f"Verificado em: {timestamp}")
    body = "\n".join(lines)

    subject = f"[SEFAZ-MG] Atualização de certificado detectada — {timestamp}"

    # E-mail
    notify_email(subject, body)

    # Telegram
    tg_lines = ["<b>SEFAZ-MG — Certificados Atualizados</b>\n"]
    for c in changes:
        tg_lines.append(f"<b>{c['module']}</b>: {c.get('update_date') or 'mudança detectada'}")
        if c.get("download_url"):
            tg_lines.append(f'<a href="{c["download_url"]}">Download</a>')
        tg_lines.append("")
    notify_telegram("\n".join(tg_lines))

    # Webhook
    notify_webhook({
        "event": "sefaz_mg_cert_update",
        "timestamp": datetime.now().isoformat(),
        "changes": changes,
    })

    # Console
    logger.warning(body)


# ---------------------------------------------------------------------------
# Monitor principal
# ---------------------------------------------------------------------------
def check_once() -> list[dict]:
    logger.info("Iniciando verificação...")

    state = load_state()
    changes: list[dict] = []

    for mod_name, url in MONITORED_URLS.items():
        logger.info("  Verificando %s (%s)...", mod_name, url)

        html, status = fetch_page_with_status(url)

        # Auto-discovery: se 404, busca o link correto na página raiz do módulo
        if html is None and status == 404:
            logger.warning("  %s: 404 na URL configurada, tentando auto-discovery...", mod_name)
            discovered = discover_downloads_url(mod_name)
            if discovered and discovered != url:
                html, status = fetch_page_with_status(discovered)
                if html:
                    url = discovered

        if not html:
            logger.warning("  Não foi possível acessar %s (HTTP %d)", mod_name, status)
            continue

        info = parse_page(html)
        prev_hash = (state.get(mod_name) or {}).get("hash")

        if prev_hash is None:
            logger.info("  %s: estado inicial registrado (data: %s)",
                        mod_name, info.update_date or "N/D")

        elif prev_hash != info.raw_hash:
            logger.warning("  %s: MUDANÇA DETECTADA!", mod_name)
            logger.info("    Hash anterior: %s", prev_hash)
            logger.info("    Hash novo:     %s", info.raw_hash)
            prev_date = (state.get(mod_name) or {}).get("update_date")
            logger.info("    Data anterior:  %s", prev_date or "N/D")
            logger.info("    Data nova:      %s", info.update_date or "N/D")

            changes.append({
                "module":        mod_name,
                "url":           url,
                "update_date":   info.update_date,
                "download_url":  info.download_url,
                "popup_title":   info.popup_title,
                "popup_message": info.popup_message,
                "previous_date": prev_date,
                "previous_hash": prev_hash,
                "new_hash":      info.raw_hash,
            })
        else:
            logger.info("  %s: sem alteração (data: %s)",
                        mod_name, info.update_date or "N/D")

        # Atualiza estado
        state[mod_name] = {
            "hash":         info.raw_hash,
            "update_date":  info.update_date,
            "download_url": info.download_url,
            "popup_title":  info.popup_title,
            "checked_at":   datetime.now().isoformat(),
        }

    save_state(state)

    if changes:
        send_notifications(changes)
        logger.warning("%d mudança(s) detectada(s)!", len(changes))
    else:
        logger.info("Nenhuma mudança detectada.")

    return changes


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def cmd_status() -> None:
    state = load_state()
    if not state:
        print("Nenhum estado salvo. Execute o monitor pelo menos uma vez.")
        return
    print("Estado atual:")
    print("-" * 60)
    for mod_name, data in state.items():
        print(f"  {mod_name}:")
        print(f"    Data certificado: {data.get('update_date') or 'N/D'}")
        print(f"    Último check:     {data.get('checked_at') or 'N/D'}")
        print(f"    Download:         {data.get('download_url') or 'N/D'}")
        print()


def cmd_reset() -> None:
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    print("Estado resetado.")


def main() -> None:
    parser = argparse.ArgumentParser(description="SEFAZ-MG Certificate Update Monitor")
    parser.add_argument("-d", "--daemon", action="store_true",
                        help="Executar em loop contínuo")
    parser.add_argument("-i", "--interval", type=int, default=DEFAULT_INTERVAL,
                        help=f"Intervalo entre verificações em segundos (padrão: {DEFAULT_INTERVAL})")
    parser.add_argument("-s", "--status", action="store_true",
                        help="Exibir último estado conhecido")
    parser.add_argument("-r", "--reset", action="store_true",
                        help="Limpar estado salvo")

    args = parser.parse_args()

    if args.status:
        cmd_status()
        return

    if args.reset:
        cmd_reset()
        return

    if args.daemon:
        logger.info("Modo daemon — intervalo: %ds", args.interval)
        while True:
            try:
                check_once()
            except Exception as e:
                logger.error("Erro na verificação: %s", e)
            logger.info("Próxima verificação em %ds...", args.interval)
            time.sleep(args.interval)
    else:
        check_once()


if __name__ == "__main__":
    main()
