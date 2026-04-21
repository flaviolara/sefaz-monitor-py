import json
import sys
import pytest
from unittest.mock import MagicMock, patch
import sefaz_mg_cert_monitor as mod
from sefaz_mg_cert_monitor import cmd_status, cmd_reset, main


# ---------------------------------------------------------------------------
# cmd_status
# ---------------------------------------------------------------------------

def test_cmd_status_no_state(patch_state, capsys):
    cmd_status()
    out = capsys.readouterr().out
    assert "Nenhum estado salvo" in out


def test_cmd_status_shows_module_data(patch_state, capsys):
    _, state_file = patch_state
    state_file.write_text(json.dumps({
        "NF-e": {
            "update_date": "20/04/2026",
            "checked_at": "2026-04-20T10:00:00",
            "download_url": "/cert/cadeia.p7b",
        }
    }), encoding="utf-8")
    cmd_status()
    out = capsys.readouterr().out
    assert "NF-e" in out
    assert "20/04/2026" in out


def test_cmd_status_shows_nd_for_missing_fields(patch_state, capsys):
    _, state_file = patch_state
    state_file.write_text(json.dumps({
        "CT-e": {"update_date": None, "checked_at": None, "download_url": None}
    }), encoding="utf-8")
    cmd_status()
    out = capsys.readouterr().out
    assert "N/D" in out


def test_cmd_status_multiple_modules(patch_state, capsys):
    _, state_file = patch_state
    state_file.write_text(json.dumps({
        "NF-e": {"update_date": "01/01/2026", "checked_at": "2026-01-01T00:00:00", "download_url": None},
        "CT-e": {"update_date": "02/02/2026", "checked_at": "2026-02-02T00:00:00", "download_url": None},
    }), encoding="utf-8")
    cmd_status()
    out = capsys.readouterr().out
    assert "NF-e" in out
    assert "CT-e" in out


# ---------------------------------------------------------------------------
# cmd_reset
# ---------------------------------------------------------------------------

def test_cmd_reset_removes_existing_file(patch_state, capsys):
    _, state_file = patch_state
    state_file.write_text("{}", encoding="utf-8")
    assert state_file.exists()
    cmd_reset()
    assert not state_file.exists()


def test_cmd_reset_prints_confirmation(patch_state, capsys):
    cmd_reset()
    out = capsys.readouterr().out
    assert "resetado" in out.lower()


def test_cmd_reset_no_error_when_no_file(patch_state, capsys):
    _, state_file = patch_state
    assert not state_file.exists()
    cmd_reset()  # não deve lançar exceção


# ---------------------------------------------------------------------------
# main — roteamento CLI
# ---------------------------------------------------------------------------

def test_main_calls_cmd_status(patch_state):
    with patch.object(sys, "argv", ["prog", "--status"]):
        with patch.object(mod, "cmd_status") as mock_status:
            main()
            mock_status.assert_called_once()


def test_main_calls_cmd_status_short_flag(patch_state):
    with patch.object(sys, "argv", ["prog", "-s"]):
        with patch.object(mod, "cmd_status") as mock_status:
            main()
            mock_status.assert_called_once()


def test_main_calls_cmd_reset(patch_state):
    with patch.object(sys, "argv", ["prog", "--reset"]):
        with patch.object(mod, "cmd_reset") as mock_reset:
            main()
            mock_reset.assert_called_once()


def test_main_calls_cmd_reset_short_flag(patch_state):
    with patch.object(sys, "argv", ["prog", "-r"]):
        with patch.object(mod, "cmd_reset") as mock_reset:
            main()
            mock_reset.assert_called_once()


def test_main_default_calls_check_once(patch_state):
    with patch.object(sys, "argv", ["prog"]):
        with patch.object(mod, "check_once", return_value=[]) as mock_check:
            main()
            mock_check.assert_called_once()


def test_main_daemon_loops_multiple_times(patch_state):
    call_count = 0

    def mock_check():
        nonlocal call_count
        call_count += 1
        if call_count >= 3:
            raise KeyboardInterrupt

    with patch.object(sys, "argv", ["prog", "--daemon", "--interval", "1"]):
        with patch.object(mod, "check_once", side_effect=mock_check):
            with patch("time.sleep"):
                with pytest.raises(KeyboardInterrupt):
                    main()
    assert call_count >= 2


def test_main_daemon_sleeps_between_runs(patch_state):
    call_count = 0

    def mock_check():
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            raise KeyboardInterrupt

    sleep_calls = []
    with patch.object(sys, "argv", ["prog", "--daemon", "--interval", "300"]):
        with patch.object(mod, "check_once", side_effect=mock_check):
            with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
                with pytest.raises(KeyboardInterrupt):
                    main()
    assert 300 in sleep_calls


def test_main_daemon_handles_check_exception(patch_state, caplog):
    call_count = 0

    def mock_check():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("erro simulado")
        raise KeyboardInterrupt

    import logging
    with patch.object(sys, "argv", ["prog", "--daemon", "--interval", "1"]):
        with patch.object(mod, "check_once", side_effect=mock_check):
            with patch("time.sleep"):
                with caplog.at_level(logging.ERROR, logger="sefaz_monitor"):
                    with pytest.raises(KeyboardInterrupt):
                        main()
    assert "erro simulado" in caplog.text
