"""Application entry point."""

from __future__ import annotations

import logging
import os
import sys

from logs_asmr.constants import APP_DIR, APP_NAME

# FFmpeg (C library inside Qt multimedia) writes decoder warnings directly to
# OS file descriptor 2, bypassing Python's sys.stderr.  Redirect fd 2 to
# /dev/null but keep Python's stderr on the original fd for tracebacks.
_real_stderr_fd = os.dup(2)
os.dup2(os.open(os.devnull, os.O_WRONLY), 2)
sys.stderr = os.fdopen(_real_stderr_fd, "w", closefd=False)


def _set_macos_process_name() -> None:
    """Set the macOS menu bar and Dock name to APP_NAME instead of 'Python'."""
    if sys.platform != "darwin":
        return
    try:
        import ctypes
        import ctypes.util

        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))

        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.objc_msgSend.restype = ctypes.c_void_p
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        NSBundle = objc.objc_getClass(b"NSBundle")
        bundle = objc.objc_msgSend(NSBundle, objc.sel_registerName(b"mainBundle"))
        info = objc.objc_msgSend(bundle, objc.sel_registerName(b"infoDictionary"))

        NSString = objc.objc_getClass(b"NSString")
        sel_str = objc.sel_registerName(b"stringWithUTF8String:")
        objc.objc_msgSend.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_char_p,
        ]
        key = objc.objc_msgSend(NSString, sel_str, b"CFBundleName")
        val = objc.objc_msgSend(NSString, sel_str, APP_NAME.encode())

        objc.objc_msgSend.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        sel_set = objc.sel_registerName(b"setObject:forKey:")
        objc.objc_msgSend(info, sel_set, val, key)
    except Exception:
        pass


def _force_macos_dark_titlebar() -> None:
    """Force dark appearance on all macOS window title bars."""
    if sys.platform != "darwin":
        return
    try:
        import ctypes
        import ctypes.util

        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))

        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.objc_msgSend.restype = ctypes.c_void_p
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        # NSApp.setAppearance:([NSAppearance appearanceNamed:NSAppearanceNameDarkAqua])
        NSAppearance = objc.objc_getClass(b"NSAppearance")
        NSString = objc.objc_getClass(b"NSString")

        sel_str = objc.sel_registerName(b"stringWithUTF8String:")
        objc.objc_msgSend.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_char_p,
        ]
        dark_name = objc.objc_msgSend(NSString, sel_str, b"NSAppearanceNameDarkAqua")

        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        dark_appearance = objc.objc_msgSend(
            NSAppearance,
            objc.sel_registerName(b"appearanceNamed:"),
            dark_name,
        )

        NSApplication = objc.objc_getClass(b"NSApplication")
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        ns_app = objc.objc_msgSend(NSApplication, objc.sel_registerName(b"sharedApplication"))

        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        objc.objc_msgSend(ns_app, objc.sel_registerName(b"setAppearance:"), dark_appearance)
    except Exception:
        pass


def main() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)

    from logs_asmr.logging_setup import setup_logging

    setup_logging()
    logger = logging.getLogger("logs_asmr.app")
    logger.info("Starting %s", APP_NAME)

    _set_macos_process_name()

    from PyQt6.QtCore import QLockFile
    from PyQt6.QtWidgets import QApplication

    from logs_asmr.ui.theme import app_stylesheet

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setStyleSheet(app_stylesheet())
    _force_macos_dark_titlebar()

    # Single-instance check
    lock_file = QLockFile(str(APP_DIR / "logs_asmr.lock"))
    if not lock_file.tryLock(100):
        logger.warning("Another instance is already running, exiting")
        sys.exit(0)

    # Initialize database
    from logs_asmr.db.database import Database

    db = Database()

    # Check for --fake flag
    fake = "--fake" in sys.argv

    from logs_asmr.main_window import MainWindow

    window = MainWindow(db=db, fake=fake)
    window.show()
    logger.info("Window shown, entering event loop")

    exit_code = app.exec()
    db.close()
    lock_file.unlock()
    logger.info("Exiting with code %d", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
