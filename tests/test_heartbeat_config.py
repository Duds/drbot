"""Tests for heartbeat config loader (SAD v7)."""

from __future__ import annotations


from remy.scheduler.heartbeat_config import HEARTBEAT_OK_RESPONSE, load_heartbeat_config


def test_heartbeat_ok_constant():
    assert HEARTBEAT_OK_RESPONSE == "HEARTBEAT_OK"


def test_load_heartbeat_config_when_both_missing(monkeypatch):
    """When HEARTBEAT.md and HEARTBEAT.example.md do not exist, returns minimal context."""
    monkeypatch.setattr(
        "remy.scheduler.heartbeat_config.settings",
        type("S", (), {"heartbeat_md_path": "/nonexistent/HEARTBEAT.md"})(),
    )
    result = load_heartbeat_config()
    assert "HEARTBEAT_OK" in result
    assert len(result) > 0


def test_load_heartbeat_config_hearts_md_only(tmp_path, monkeypatch):
    """When HEARTBEAT.md exists, returns its content."""
    public = tmp_path / "HEARTBEAT.md"
    public.write_text("# Public\n\nGoals: check overdue.")
    monkeypatch.setattr(
        "remy.scheduler.heartbeat_config.settings",
        type("S", (), {"heartbeat_md_path": str(public)})(),
    )
    result = load_heartbeat_config()
    assert "Public" in result
    assert "Goals: check overdue." in result


def test_load_heartbeat_config_fallback_to_example(tmp_path, monkeypatch):
    """When HEARTBEAT.md is missing but HEARTBEAT.example.md exists, use the example."""
    example = tmp_path / "HEARTBEAT.example.md"
    example.write_text("# Template\n\nGoals: check overdue.")
    base_path = tmp_path / "HEARTBEAT.md"
    assert not base_path.exists()
    monkeypatch.setattr(
        "remy.scheduler.heartbeat_config.settings",
        type("S", (), {"heartbeat_md_path": str(base_path)})(),
    )
    result = load_heartbeat_config()
    assert "Template" in result
    assert "Goals: check overdue." in result
