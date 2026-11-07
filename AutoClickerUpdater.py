"""Transactional Windows helper that replaces AutoClicker.exe safely."""

from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path


SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258
ERROR_INVALID_PARAMETER = 87
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def _show_error(message: str) -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, message, "AutoClicker güncellemesi", 0x10 | 0x1000)


def _wait_for_process_exit(pid: int, timeout_ms: int = 60_000) -> None:
    if os.name != "nt":
        raise OSError("Bu güncelleme yardımcısı yalnızca Windows içindir.")

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_int

    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error == ERROR_INVALID_PARAMETER:
            return
        raise OSError(error, "AutoClicker işlemi beklenemedi.")
    try:
        result = kernel32.WaitForSingleObject(handle, timeout_ms)
        if result == WAIT_TIMEOUT:
            raise TimeoutError("AutoClicker zamanında kapanmadı.")
        if result != WAIT_OBJECT_0:
            raise OSError("AutoClicker işleminin kapanışı doğrulanamadı.")
    finally:
        kernel32.CloseHandle(handle)


def _valid_executable(path: Path) -> bool:
    try:
        if not path.is_file() or not 1_000_000 <= path.stat().st_size <= 150 * 1024 * 1024:
            return False
        with path.open("rb") as handle:
            return handle.read(2) == b"MZ"
    except OSError:
        return False


def _launch(path: Path, arguments: list[str] | None = None) -> subprocess.Popen:
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(
        [str(path), *(arguments or [])],
        cwd=str(path.parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
        close_fds=True,
    )


def _confirm_new_app(process: subprocess.Popen, marker: Path, timeout_seconds: int = 45) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if marker.is_file():
            return True
        if process.poll() is not None:
            return False
        time.sleep(0.25)
    return marker.is_file()


def _cleanup_worker_later(token: str) -> None:
    if not getattr(sys, "frozen", False) or os.name != "nt":
        return
    worker = Path(sys.executable).resolve()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.MoveFileExW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
    kernel32.MoveFileExW.restype = ctypes.c_int
    # The worker is running from a temporary copy. Ask Windows to remove it
    # after process exit/reboot; it cannot safely delete its own image now.
    kernel32.MoveFileExW(str(worker), None, 0x00000004)


def apply_update(
    candidate_app: Path,
    candidate_helper: Path,
    target_app: Path,
    target_helper: Path,
    parent_pid: int,
    staging_dir: Path,
) -> None:
    token = uuid.uuid4().hex
    backup_app = target_app.with_name(f".{target_app.name}.{token}.rollback")
    backup_helper = target_helper.with_name(f".{target_helper.name}.{token}.rollback")
    replacement_app = target_app.with_name(f".{target_app.stem}.{token}.new{target_app.suffix}")
    replacement_helper = target_helper.with_name(
        f".{target_helper.stem}.{token}.new{target_helper.suffix}"
    )
    marker = Path(tempfile.gettempdir()) / f"AutoClicker-update-started-{token}.txt"
    new_process = None
    moved_app = False
    moved_helper = False

    try:
        if target_app.name.lower() != "autoclicker.exe" or target_helper.name.lower() != "autoclickerupdater.exe":
            raise ValueError("Hedef AutoClicker dosya adları beklenen biçimde değil.")
        if not _valid_executable(candidate_app) or not _valid_executable(candidate_helper):
            raise ValueError("Yeni EXE dosyalarından biri geçersiz veya eksik.")
        if not target_app.is_file() or not target_helper.is_file():
            raise FileNotFoundError("AutoClicker.exe veya AutoClickerUpdater.exe bulunamadı.")
        _wait_for_process_exit(parent_pid)

        shutil.copy2(candidate_app, replacement_app)
        shutil.copy2(candidate_helper, replacement_helper)
        if not _valid_executable(replacement_app) or not _valid_executable(replacement_helper):
            raise ValueError("Yeni EXE kopyaları doğrulanamadı.")
        os.replace(target_app, backup_app)
        moved_app = True
        os.replace(target_helper, backup_helper)
        moved_helper = True
        os.replace(replacement_app, target_app)
        os.replace(replacement_helper, target_helper)

        new_process = _launch(target_app, [f"--autoclicker-update-confirm={marker}"])
        if not _confirm_new_app(new_process, marker):
            raise RuntimeError("Yeni sürüm başlangıç doğrulamasını tamamlamadı.")

        for backup in (backup_app, backup_helper):
            try:
                backup.unlink()
            except OSError:
                pass
    except Exception as error:
        if new_process is not None and new_process.poll() is None:
            try:
                new_process.terminate()
                new_process.wait(timeout=5)
            except Exception:
                pass
        rollback_errors = []
        if moved_helper and backup_helper.is_file():
            try:
                if target_helper.exists():
                    target_helper.unlink()
                os.replace(backup_helper, target_helper)
            except Exception as rollback_error:
                rollback_errors.append(f"Yardımcı yedeği: {backup_helper}\n{rollback_error}")
        if moved_app and backup_app.is_file():
            try:
                if target_app.exists():
                    target_app.unlink()
                os.replace(backup_app, target_app)
            except Exception as rollback_error:
                rollback_errors.append(f"Uygulama yedeği: {backup_app}\n{rollback_error}")
        if rollback_errors:
            _show_error(
                "Güncelleme başarısız oldu ve otomatik geri yükleme tamamlanamadı.\n\n"
                + "\n\n".join(rollback_errors)
            )
            return
        if moved_app and target_app.is_file():
            try:
                _launch(target_app)
            except Exception as launch_error:
                _show_error(f"Eski sürüm geri yüklendi ancak başlatılamadı.\n\n{launch_error}")
                return
        _show_error(f"Güncelleme tamamlanamadı. Eski sürüm korunuyor.\n\n{error}")
    finally:
        for leftover in (replacement_app, replacement_helper, marker):
            try:
                leftover.unlink()
            except OSError:
                pass
        shutil.rmtree(staging_dir, ignore_errors=True)
        try:
            _cleanup_worker_later(token)
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("candidate_app", nargs="?")
    parser.add_argument("candidate_helper", nargs="?")
    parser.add_argument("target_app", nargs="?")
    parser.add_argument("target_helper", nargs="?")
    parser.add_argument("parent_pid", nargs="?", type=int)
    parser.add_argument("staging_dir", nargs="?")
    args = parser.parse_args()
    if (
        not args.apply or not args.candidate_app or not args.candidate_helper
        or not args.target_app or not args.target_helper or not args.parent_pid or not args.staging_dir
    ):
        return 2
    apply_update(
        Path(args.candidate_app), Path(args.candidate_helper),
        Path(args.target_app), Path(args.target_helper),
        args.parent_pid, Path(args.staging_dir),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
