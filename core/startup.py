"""Helpers for Windows startup and app relaunch behavior."""

from __future__ import annotations

import os
import sys

import config

try:
    import winreg  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - non-Windows
    winreg = None


_RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE_NAME = "ELITE IPTV DVR"


def _main_script_path() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))


def build_launch_command() -> str:
    """Return the command used for Windows autostart entries."""
    if getattr(sys, "frozen", False):
        command = f'"{sys.executable}"'
    else:
        command = f'"{sys.executable}" "{_main_script_path()}"'
    return command


def is_autostart_enabled() -> bool:
    if sys.platform != "win32" or winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, _RUN_VALUE_NAME)
            return bool(str(value).strip())
    except OSError:
        return False


def set_autostart_enabled(enabled: bool) -> bool:
    if sys.platform != "win32" or winreg is None:
        return False

    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH) as key:
            if enabled:
                winreg.SetValueEx(key, _RUN_VALUE_NAME, 0, winreg.REG_SZ, build_launch_command())
            else:
                try:
                    winreg.DeleteValue(key, _RUN_VALUE_NAME)
                except OSError:
                    pass
        return True
    except OSError:
        return False


def sync_autostart_setting(enabled: bool) -> bool:
    """Update the registry autostart entry and return whether the change succeeded."""
    config.AUTO_START_ON_BOOT = bool(enabled)
    return set_autostart_enabled(bool(enabled))
