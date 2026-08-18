import importlib

import config as config_module
from config import SENSITIVITY_PRESETS, Settings


def _redirect_config(tmp_path, monkeypatch):
    """Point the config module at a temporary settings file."""
    target = tmp_path / "settings.json"
    monkeypatch.setattr(config_module, "config_path", lambda: str(target))
    return target


def test_defaults_are_sane():
    s = Settings()
    assert s.enabled is True
    assert s.ignore_secure_fields is True
    assert s.first_run_completed is False
    assert s.detection_threshold == SENSITIVITY_PRESETS["balanced"]


def test_save_then_load_roundtrip(tmp_path, monkeypatch):
    _redirect_config(tmp_path, monkeypatch)
    s = Settings(idle_check_ms=900, detection_threshold=1.6, first_run_completed=True)
    s.save()

    loaded = Settings.load()
    assert loaded.idle_check_ms == 900
    assert loaded.detection_threshold == 1.6
    assert loaded.first_run_completed is True


def test_load_missing_file_returns_defaults(tmp_path, monkeypatch):
    _redirect_config(tmp_path, monkeypatch)
    loaded = Settings.load()
    assert loaded == Settings()


def test_load_ignores_unknown_keys(tmp_path, monkeypatch):
    target = _redirect_config(tmp_path, monkeypatch)
    target.write_text('{"idle_check_ms": 500, "unknown_key": 123}', encoding="utf-8")
    loaded = Settings.load()
    assert loaded.idle_check_ms == 500


def test_load_corrupt_file_returns_defaults(tmp_path, monkeypatch):
    target = _redirect_config(tmp_path, monkeypatch)
    target.write_text("not json{", encoding="utf-8")
    assert Settings.load() == Settings()


def test_sensitivity_label_and_setter():
    s = Settings()
    s.set_sensitivity("strict")
    assert s.detection_threshold == SENSITIVITY_PRESETS["strict"]
    assert s.sensitivity_label() == "strict"
