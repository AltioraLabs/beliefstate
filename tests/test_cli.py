"""Tests for the beliefstate CLI (validate-config)."""

import json

import pytest

from beliefstate.cli import main


def _write(tmp_path, name, content):
    path = tmp_path / name
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_text(json.dumps(content), encoding="utf-8")
    return path


class TestValidateConfig:
    def test_valid_sqlite_config(self, tmp_path, capsys):
        path = _write(tmp_path, "config.json", {"store_type": "sqlite"})
        rc = main(["validate-config", "--config", str(path)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "Result: VALID" in out
        assert "[PASS]" in out

    def test_invalid_store_type(self, tmp_path, capsys):
        path = _write(tmp_path, "config.json", {"store_type": "mongodb"})
        rc = main(["validate-config", "--config", str(path)])
        out = capsys.readouterr().out
        assert rc == 1
        assert "Result: INVALID" in out
        assert "store_type" in out

    def test_invalid_field_type(self, tmp_path, capsys):
        path = _write(tmp_path, "config.json", {"belief_budget_tokens": "not-a-number"})
        rc = main(["validate-config", "--config", str(path)])
        out = capsys.readouterr().out
        assert rc == 1
        assert "Result: INVALID" in out
        assert "belief_budget_tokens" in out

    def test_missing_file(self, tmp_path, capsys):
        rc = main(["validate-config", "--config", str(tmp_path / "nope.json")])
        out = capsys.readouterr().out
        assert rc == 1
        assert "not found" in out

    def test_non_object_config(self, tmp_path, capsys):
        path = _write(tmp_path, "config.json", ["not", "an", "object"])
        rc = main(["validate-config", "--config", str(path)])
        out = capsys.readouterr().out
        assert rc == 1
        assert "Result: INVALID" in out

    def test_missing_store_dependency_reported(self, tmp_path, capsys):
        try:
            import redis  # noqa: F401

            pytest.skip("redis is installed; dependency-missing path not exercised")
        except ImportError:
            pass
        path = _write(tmp_path, "config.json", {"store_type": "redis"})
        rc = main(["validate-config", "--config", str(path)])
        out = capsys.readouterr().out
        assert rc == 1
        assert "missing dependency 'redis'" in out
        assert "beliefstate[redis]" in out

    def test_yaml_config(self, tmp_path, capsys):
        pytest.importorskip("yaml")
        path = _write(tmp_path, "config.yaml", "store_type: sqlite\nmax_beliefs: 10\n")
        rc = main(["validate-config", "--config", str(path)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "Result: VALID" in out

    def test_connection_check_sqlite_memory(self, tmp_path, capsys):
        path = _write(
            tmp_path,
            "config.json",
            {"store_type": "sqlite", "store_kwargs": {"db_path": ":memory:"}},
        )
        rc = main(["validate-config", "--config", str(path), "--check-connection"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "store connection healthy" in out
        assert "Result: VALID" in out


class TestCliDispatch:
    def test_no_command_prints_help(self, capsys):
        rc = main([])
        out = capsys.readouterr().out
        assert rc == 1
        assert "validate-config" in out
