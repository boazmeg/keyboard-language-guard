"""Central configuration for Keyboard Language Guard.

All tunable values live here so the rest of the code (and the settings
screen) reads from a single source of truth. Settings persist to a JSON
file under the user's per-application config directory.
"""

import json
import os
import sys
from dataclasses import asdict, dataclass, fields

APP_NAME = "KeyboardLanguageGuard"


def config_dir() -> str:
    """Return the per-user directory where settings are stored."""
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(base, APP_NAME)


def config_path() -> str:
    return os.path.join(config_dir(), "settings.json")


# Preset sensitivity levels map a friendly label to a detection threshold.
# A lower threshold triggers more often (more sensitive) but risks more
# false positives; a higher threshold is stricter.
SENSITIVITY_PRESETS = {
    "high": 1.6,
    "balanced": 2.2,
    "strict": 3.0,
}


@dataclass
class Settings:
    """User-adjustable settings with safe defaults."""

    enabled: bool = True

    # Typing-pause timings before a check runs.
    idle_check_ms: int = 1400
    punctuation_check_ms: int = 850
    enter_check_ms: int = 350
    cooldown_seconds: float = 4.0

    # Detection tuning.
    min_check_chars: int = 8
    detection_threshold: float = 2.2

    # Privacy.
    ignore_secure_fields: bool = True

    # Onboarding.
    first_run_completed: bool = False

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from disk, falling back to defaults on any error."""
        path = config_path()
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (FileNotFoundError, ValueError, OSError):
            return cls()

        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in data.items() if k in known}
        try:
            return cls(**clean)
        except TypeError:
            return cls()

    def save(self) -> None:
        """Persist settings to disk, creating the directory if needed."""
        path = config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(asdict(self), handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def sensitivity_label(self) -> str:
        """Return the preset name closest to the current threshold."""
        best = min(
            SENSITIVITY_PRESETS.items(),
            key=lambda kv: abs(kv[1] - self.detection_threshold),
        )
        return best[0]

    def set_sensitivity(self, label: str) -> None:
        if label in SENSITIVITY_PRESETS:
            self.detection_threshold = SENSITIVITY_PRESETS[label]
