"""
main.py — Thin entrypoint for ELITE IPTV Recorder.
"""

import os
import shutil
import subprocess
import sys

import customtkinter as ctk
import tkinter.messagebox as mb

import config
from core.credentials import load_credentials


def _check_ffmpeg() -> bool:
    """
    Verify FFmpeg is available before the main window opens.
    On Windows, offer to auto-install via winget if it's missing.
    Returns True if the app should proceed, False if it should exit.
    """
    if shutil.which("ffmpeg"):
        return True

    if sys.platform != "win32":
        mb.showwarning(
            "FFmpeg Not Found",
            "FFmpeg was not found on your system.\n\n"
            "Install it with:\n"
            "  Mac:   brew install ffmpeg\n"
            "  Linux: sudo apt install ffmpeg\n\n"
            "The app will open, but recording and preview won't work until FFmpeg is installed."
        )
        return True

    install = mb.askyesno(
        "FFmpeg Not Found",
        "FFmpeg is required for recording and previewing streams, "
        "but it wasn't found on this PC.\n\n"
        "Install it automatically now?\n"
        "(Uses winget — built into Windows 10/11. Requires internet.)\n\n"
        "The app will close after installing. Reopen it to start recording."
    )

    if not install:
        return True

    try:
        result = subprocess.run(
            [
                "winget", "install", "Gyan.FFmpeg",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            timeout=300,
        )
        if result.returncode == 0:
            mb.showinfo(
                "FFmpeg Installed",
                "FFmpeg was installed successfully.\n\n"
                "Reopen the app to start recording."
            )
        else:
            mb.showerror(
                "Install Failed",
                "winget couldn't install FFmpeg automatically.\n\n"
                "Please install it manually:\n"
                "  1. Open Microsoft Store and install 'App Installer' (for winget)\n"
                "  2. Or download from: https://ffmpeg.org/download.html"
            )
    except FileNotFoundError:
        mb.showerror(
            "winget Not Found",
            "winget is not available on this PC.\n\n"
            "Please install FFmpeg manually from:\n"
            "https://ffmpeg.org/download.html\n\n"
            "Then reopen the app."
        )
    except subprocess.TimeoutExpired:
        mb.showerror(
            "Timeout",
            "The installation timed out. Please check your internet connection and try again,\n"
            "or install FFmpeg manually from https://ffmpeg.org/download.html"
        )

    return False


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme(os.path.join(config._BUNDLE_DIR, "ember.json"))

    load_credentials()

    if not _check_ffmpeg():
        sys.exit(0)

    from ui.app import IPTVRecorderApp

    app = IPTVRecorderApp()
    app.protocol("WM_DELETE_WINDOW", app._on_closing)
    app.mainloop()
