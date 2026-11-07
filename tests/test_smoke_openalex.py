import subprocess

import pytest

from scripts.smoke_openalex import require_credentials, run_cli


def test_live_check_requires_explicit_credentials(monkeypatch):
    monkeypatch.delenv("OPENALEX_MAILTO", raising=False)
    monkeypatch.setenv("OPENALEX_API_KEY", " ")
    with pytest.raises(RuntimeError, match="OPENALEX_MAILTO, OPENALEX_API_KEY"):
        require_credentials()


def test_failed_cli_redacts_credentials_and_uses_isolated_directory(monkeypatch, tmp_path):
    mail, key = "smoke@example.com", "smoke-secret-key"

    def fail(args, **kwargs):
        assert kwargs["cwd"] == tmp_path
        assert kwargs["capture_output"]
        return subprocess.CompletedProcess(args, 1, f"mail={mail}", f"token={key}")

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(RuntimeError) as error:
        run_cli(["fetch"], tmp_path, (mail, key))
    assert "fetch failed" in str(error.value)
    assert mail not in str(error.value)
    assert key not in str(error.value)
