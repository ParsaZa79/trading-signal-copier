from __future__ import annotations

from src.config import FeatureFlags


def test_feature_flags_default_to_disabled(monkeypatch):
    for name in (
        "STRATEGY_LAB_ENABLED",
        "OPEN_SIGNUP_ENABLED",
        "CODEX_BUILDER_ENABLED",
        "PAPER_LIVE_ENABLED",
        "PUBLIC_STRATEGY_PUBLISHING_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)

    flags = FeatureFlags()

    assert flags.strategy_lab_enabled is False
    assert flags.open_signup_enabled is False
    assert flags.codex_builder_enabled is False
    assert flags.paper_live_enabled is False
    assert flags.public_strategy_publishing_enabled is False


def test_feature_flags_accept_explicit_truthy_environment_values(monkeypatch):
    monkeypatch.setenv("STRATEGY_LAB_ENABLED", "true")
    monkeypatch.setenv("OPEN_SIGNUP_ENABLED", "1")
    monkeypatch.setenv("CODEX_BUILDER_ENABLED", "yes")
    monkeypatch.setenv("PAPER_LIVE_ENABLED", "on")
    monkeypatch.setenv("PUBLIC_STRATEGY_PUBLISHING_ENABLED", "TRUE")

    flags = FeatureFlags()

    assert flags.strategy_lab_enabled is True
    assert flags.open_signup_enabled is True
    assert flags.codex_builder_enabled is True
    assert flags.paper_live_enabled is True
    assert flags.public_strategy_publishing_enabled is True


def test_feature_flags_treat_unknown_values_as_disabled(monkeypatch):
    monkeypatch.setenv("STRATEGY_LAB_ENABLED", "sometimes")

    assert FeatureFlags().strategy_lab_enabled is False
