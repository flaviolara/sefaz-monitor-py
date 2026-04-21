# SEFAZ-MG Certificate Monitor (Python)

Monitora as páginas do Portal SPED-MG e notifica quando há atualização na cadeia de certificados digitais.

## O que monitora

Varre as páginas de **Downloads** dos módulos NF-e, NFC-e, CT-e, CT-e OS, MDF-e, BP-e, NF3-e e NFCom, detectando:

- **Popup "Troca de Certificado"** — o aviso modal que aparece no site
- **Link de download da cadeia** — alterações na URL do .zip e na data de atualização
- Qualquer mudança textual relevante (via hash SHA256)

## Auto-Discovery

Se uma URL configurada retornar 404 (caso o portal mude os paths), o monitor automaticamente
acessa a página raiz do módulo, busca o link "Downloads" ou "Documentos" no menu lateral
e usa a URL correta. Isso protege contra mudanças de casing ou renomeação de paths.

## Ambiente de desenvolvimento

O projeto usa [mise](https://mise.jdx.dev/) para gerenciar a versão do Python e `.venv` para isolar os pacotes.

### Pré-requisitos

- [mise](https://mise.jdx.dev/) instalado e ativado no shell (`eval "$(mise activate zsh)"` no `~/.zshrc`)

### Configuração inicial

```bash
mise install          # instala a versão do Python definida em mise.toml
python -m venv .venv  # cria o ambiente virtual isolado
source .venv/bin/activate
pip install -r requirements.txt
```

O VSCode detecta o `.venv` automaticamente — o `settings.json` já aponta para `${workspaceFolder}/.venv/bin/python`.

## Instalação

```bash
pip install -r requirements.txt
chmod +x sefaz_mg_cert_monitor.py
```

## Uso

```bash
python sefaz_mg_cert_monitor.py              # execução única (ideal para cron)
python sefaz_mg_cert_monitor.py --daemon     # loop contínuo (padrão 1h)
python sefaz_mg_cert_monitor.py -d -i 1800   # intervalo customizado (30 min)
python sefaz_mg_cert_monitor.py --status     # exibe último estado
python sefaz_mg_cert_monitor.py --reset      # limpa estado
```

## Notificações

Configure via variáveis de ambiente (e-mail, Telegram, webhook). Veja `env.sample`.

## Cron

```cron
0 7-20 * * 1-5 /usr/bin/python3 /opt/sefaz-monitor/sefaz_mg_cert_monitor.py >> /var/log/sefaz_monitor.log 2>&1
```

## Systemd

```bash
sudo cp sefaz-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sefaz-monitor
```
