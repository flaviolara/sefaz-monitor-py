import os
import pytest
from sefaz_mg_cert_monitor import load_env_file


def test_load_env_missing_file():
    load_env_file("/nonexistent/path/.env")  # não deve lançar exceção


def test_load_env_loads_variable(tmp_path):
    env = tmp_path / ".env"
    env.write_text("_SEFAZ_TEST_A=hello123\n", encoding="utf-8")
    os.environ.pop("_SEFAZ_TEST_A", None)
    try:
        load_env_file(str(env))
        assert os.environ.get("_SEFAZ_TEST_A") == "hello123"
    finally:
        os.environ.pop("_SEFAZ_TEST_A", None)


def test_load_env_skips_comment_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# _SEFAZ_COMMENTED=value\n", encoding="utf-8")
    os.environ.pop("_SEFAZ_COMMENTED", None)
    load_env_file(str(env))
    assert "_SEFAZ_COMMENTED" not in os.environ


def test_load_env_skips_empty_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text("\n\n_SEFAZ_TEST_B=val\n\n", encoding="utf-8")
    os.environ.pop("_SEFAZ_TEST_B", None)
    try:
        load_env_file(str(env))
        assert os.environ.get("_SEFAZ_TEST_B") == "val"
    finally:
        os.environ.pop("_SEFAZ_TEST_B", None)


def test_load_env_skips_line_without_equals(tmp_path):
    env = tmp_path / ".env"
    env.write_text("NOEQUALSSIGN\n", encoding="utf-8")
    load_env_file(str(env))  # não deve lançar exceção


def test_load_env_does_not_override_existing(tmp_path):
    env = tmp_path / ".env"
    env.write_text("_SEFAZ_EXISTING=new_value\n", encoding="utf-8")
    os.environ["_SEFAZ_EXISTING"] = "original"
    try:
        load_env_file(str(env))
        assert os.environ["_SEFAZ_EXISTING"] == "original"
    finally:
        del os.environ["_SEFAZ_EXISTING"]


def test_load_env_handles_value_with_equals(tmp_path):
    env = tmp_path / ".env"
    env.write_text("_SEFAZ_URL=http://example.com?a=1&b=2\n", encoding="utf-8")
    os.environ.pop("_SEFAZ_URL", None)
    try:
        load_env_file(str(env))
        assert os.environ.get("_SEFAZ_URL") == "http://example.com?a=1&b=2"
    finally:
        os.environ.pop("_SEFAZ_URL", None)
