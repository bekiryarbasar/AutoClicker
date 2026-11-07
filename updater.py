"""Single-file, transactional updater for AutoClicker on Windows."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

import tkinter as tk
from tkinter import messagebox

OWNER = "bekiryarbasar"
REPOSITORY = "AutoClicker"
APP_EXE = "AutoClicker.exe"
MAX_EXE_BYTES = 150 * 1024 * 1024
VIDEO_RUNTIME_ASSET = "AutoClicker-VideoRuntime.zip"
MAX_VIDEO_RUNTIME_ARCHIVE = 50 * 1024 * 1024
MAX_VIDEO_RUNTIME_EXE = 150 * 1024 * 1024
VIDEO_RUNTIME_EXE_SHA256 = "3256173f3f8bffd7df12227c68adf68025edb1832273a9530688a7bb1ed8edec"
API_TIMEOUT = 8


def _app_dir() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


def _version_tuple(value: str) -> tuple[int, ...] | None:
    match = re.fullmatch(r"v?(\d+(?:\.\d+){1,3})", str(value).strip(), re.I)
    if not match:
        return None
    parts = tuple(int(piece) for piece in match.group(1).split("."))
    return parts + (0,) * (4 - len(parts))


def _get(url: str, limit: int, accept: str, timeout: int = API_TIMEOUT) -> tuple[bytes, dict]:
    request = Request(url, headers={"Accept": accept, "User-Agent": "AutoClicker-Updater/1.0", "X-GitHub-Api-Version": "2022-11-28"})
    with urlopen(request, timeout=timeout) as response:
        length = response.headers.get("Content-Length")
        if length and int(length) > limit:
            raise ValueError("Dosya beklenenden büyük.")
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Dosya beklenenden büyük.")
    return data, {}


def _download_large(url: str, limit: int, accept: str, connect_timeout: int = 30, chunk_timeout: int = 30, total_timeout: int = 600) -> bytes:
    """Download large files via streaming to avoid short socket timeouts.

    urlopen's ``timeout`` only covers the initial connection and each individual
    socket read, so reading a large response body can still hit it on slow
    connections.  This helper opens the connection with *connect_timeout* and
    then reads the body in chunks, applying *chunk_timeout* per chunk and
    *total_timeout* for the whole transfer.
    """
    import socket as _socket
    _TIMEOUT_EXC = (TimeoutError, _socket.timeout, OSError)
    request = Request(url, headers={"Accept": accept, "User-Agent": "AutoClicker-Updater/1.0", "X-GitHub-Api-Version": "2022-11-28"})
    deadline = time.monotonic() + total_timeout
    with urlopen(request, timeout=connect_timeout) as response:
        length = response.headers.get("Content-Length")
        if length and int(length) > limit:
            raise ValueError("Dosya beklenenden büyük.")
        chunks: list[bytes] = []
        received = 0
        try:
            response.fp.raw.settimeout(chunk_timeout)  # type: ignore[attr-defined]
        except (AttributeError, _socket.error):
            pass
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("İndirme toplam süre limitini aştı.")
            try:
                chunk = response.read(256 * 1024)
            except _TIMEOUT_EXC as exc:
                raise TimeoutError(f"İndirme sırasında bağlantı zaman aşımına uğradı: {exc}") from exc
            if not chunk:
                break
            received += len(chunk)
            if received > limit:
                raise ValueError("Dosya beklenenden büyük.")
            chunks.append(chunk)
    return b"".join(chunks)


def ensure_video_runtime(destination: Path) -> Path:
    """Fetch and cache the optional video decoder only when video is selected."""
    destination = Path(destination)
    if destination.is_file() and destination.stat().st_size > 1_000_000:
        with destination.open("rb") as existing:
            if existing.read(2) == b"MZ":
                return destination

    api_url = f"https://api.github.com/repos/{quote(OWNER)}/{quote(REPOSITORY)}/releases/latest"
    raw, _ = _get(api_url, 2 * 1024 * 1024, "application/vnd.github+json")
    release = json.loads(raw)
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        raise ValueError("Video bileşenini sağlayan kararlı sürüm bulunamadı.")
    tag = release.get("tag_name", "")
    assets = [asset for asset in release.get("assets", []) if isinstance(asset, dict) and asset.get("name") == VIDEO_RUNTIME_ASSET]
    if len(assets) != 1:
        raise ValueError("Yayınlanan sürümde video bileşeni bulunamadı.")
    asset = assets[0]
    url = asset.get("browser_download_url", "")
    expected_digest = asset.get("digest", "")
    parsed = urlparse(url)
    expected_path = f"/{OWNER}/{REPOSITORY}/releases/download/{tag}/{VIDEO_RUNTIME_ASSET}"
    if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.path != expected_path:
        raise ValueError("Video bileşeninin indirme adresi güvenli değil.")
    if not isinstance(expected_digest, str) or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", expected_digest):
        raise ValueError("Video bileşeninin GitHub SHA-256 özeti bulunamadı.")

    archive_data = _download_large(url, MAX_VIDEO_RUNTIME_ARCHIVE, "application/octet-stream")
    if hashlib.sha256(archive_data).hexdigest() != expected_digest.split(":", 1)[1].lower():
        raise ValueError("Video bileşeninin SHA-256 doğrulaması başarısız oldu.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(io.BytesIO(archive_data), "r") as archive:
            entries = archive.infolist()
            if len(entries) != 1 or entries[0].filename != "ffmpeg.exe" or entries[0].is_dir():
                raise ValueError("Video bileşeni beklenen dosya yapısına sahip değil.")
            entry = entries[0]
            if not 1_000_000 <= entry.file_size <= MAX_VIDEO_RUNTIME_EXE:
                raise ValueError("Video bileşeninin boyutu beklenmiyor.")
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Video bileşeni sembolik bağlantı içeremez.")
            if archive.testzip() is not None:
                raise ValueError("Video bileşeninin ZIP arşivi bozuk.")
            with archive.open(entry, "r") as source, temporary.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)

        if temporary.stat().st_size != entry.file_size:
            raise ValueError("Video bileşeni eksik indirildi.")
        digest = hashlib.sha256()
        with temporary.open("rb") as binary:
            if binary.read(2) != b"MZ":
                raise ValueError("İndirilen bileşen geçerli bir Windows EXE değil.")
            binary.seek(0)
            for chunk in iter(lambda: binary.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != VIDEO_RUNTIME_EXE_SHA256:
            raise ValueError("Video bileşeninin dosya özeti beklenen değerle eşleşmiyor.")
        os.replace(temporary, destination)
        return destination
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _latest_release(current_version: str) -> dict | None:
    api = f"https://api.github.com/repos/{quote(OWNER)}/{quote(REPOSITORY)}/releases/latest"
    raw, _ = _get(api, 2 * 1024 * 1024, "application/vnd.github+json")
    release = json.loads(raw)
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        return None
    tag = release.get("tag_name", "")
    latest = _version_tuple(tag)
    current = _version_tuple(current_version)
    if latest is None or current is None or latest <= current:
        return None
    matches = [asset for asset in release.get("assets", []) if isinstance(asset, dict) and asset.get("name") == APP_EXE]
    if len(matches) != 1:
        raise ValueError("Yayında AutoClicker.exe bulunamadı.")
    asset = matches[0]
    url = asset.get("browser_download_url", "")
    digest = asset.get("digest", "")
    parsed = urlparse(url)
    expected_path = f"/{OWNER}/{REPOSITORY}/releases/download/{tag}/{APP_EXE}"
    if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.path != expected_path:
        raise ValueError("İndirme adresi güvenli GitHub Release adresi değil.")
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
        raise ValueError("GitHub sürüm dosyasının SHA-256 doğrulaması bulunamadı.")
    return {"version": ".".join(map(str, latest[:3])), "url": url, "sha256": digest.split(":", 1)[1].lower()}


def _wait_for_process(pid: int) -> None:
    if os.name != "nt":
        time.sleep(1.5)
        return
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if handle:
        try:
            kernel.WaitForSingleObject(handle, 60000)
        finally:
            kernel.CloseHandle(handle)


def run_update_worker(args: list[str]) -> int:
    """Replace the app after its original process exits; roll back if startup fails."""
    if len(args) != 4:
        return 2
    candidate, target, parent_pid, staging = Path(args[0]), Path(args[1]), int(args[2]), Path(args[3])
    backup = target.with_name(f".{target.name}.{uuid.uuid4().hex}.bak")
    replacement = target.with_name(f".{target.name}.{uuid.uuid4().hex}.new")
    marker = staging / "startup.ok"
    try:
        _wait_for_process(parent_pid)
        if not candidate.is_file() or not target.is_file():
            raise FileNotFoundError("Güncelleme dosyası bulunamadı.")
        shutil.copy2(target, backup)
        # Stage beside the destination so atomic replacement works even when
        # the system temporary folder and app folder are on different drives.
        shutil.copy2(candidate, replacement)
        os.replace(replacement, target)
        flags = getattr(subprocess, "DETACHED_PROCESS", 8) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 512)
        subprocess.Popen([str(target), f"--autoclicker-update-confirm={marker}"], cwd=str(target.parent), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True)
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            if marker.exists():
                backup.unlink(missing_ok=True)
                # Remove obsolete v1.0.0 sidecars after successful transition.
                for name in ("AutoClickerUpdater.exe", "updater_config.json"):
                    try:
                        (target.parent / name).unlink(missing_ok=True)
                    except OSError:
                        pass
                shutil.rmtree(staging, ignore_errors=True)
                return 0
            time.sleep(0.25)
        raise TimeoutError("Yeni sürüm başlatma onayını vermedi.")
    except Exception:
        try:
            replacement.unlink(missing_ok=True)
            if backup.exists():
                os.replace(backup, target)
                flags = getattr(subprocess, "DETACHED_PROCESS", 8) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 512)
                subprocess.Popen([str(target)], cwd=str(target.parent), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True)
        except Exception:
            pass
        shutil.rmtree(staging, ignore_errors=True)
        return 1


def run_startup_check(current_version: str) -> None:
    """Check before showing the app UI; offline users continue normally."""
    if not getattr(sys, "frozen", False):
        return
    # Remove transition files left by the former two-EXE release.
    for name in ("AutoClickerUpdater.exe", "updater_config.json"):
        try:
            (_app_dir() / name).unlink(missing_ok=True)
        except OSError:
            pass
    try:
        update = _latest_release(current_version)
    except Exception:
        return
    if not update:
        return
    dialog = tk.Tk()
    dialog.withdraw()
    try:
        accepted = messagebox.askyesno("Güncelleme bulundu", f"AutoClicker {update['version']} sürümü bulundu.\n\nGüncelleme şimdi indirilsin ve kurulsun mu?", parent=dialog)
        if not accepted:
            return
        try:
            data = _download_large(update["url"], MAX_EXE_BYTES, "application/octet-stream")
            if hashlib.sha256(data).hexdigest() != update["sha256"]:
                raise ValueError("İndirilen dosyanın SHA-256 değeri eşleşmedi.")
            if len(data) < 1_000_000 or not data.startswith(b"MZ"):
                raise ValueError("İndirilen dosya geçerli bir Windows uygulaması değil.")
            staging = Path(tempfile.mkdtemp(prefix="AutoClicker-update-"))
            candidate = staging / APP_EXE
            candidate.write_bytes(data)
            worker = Path(tempfile.gettempdir()) / f"AutoClicker-worker-{uuid.uuid4().hex}.exe"
            shutil.copy2(sys.executable, worker)
            flags = getattr(subprocess, "DETACHED_PROCESS", 8) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 512)
            subprocess.Popen([str(worker), "--autoclicker-apply-update", str(candidate), str(Path(sys.executable).resolve()), str(os.getpid()), str(staging)], cwd=tempfile.gettempdir(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True)
            raise SystemExit(0)
        except SystemExit:
            raise
        except Exception as error:
            messagebox.showerror("Güncelleme yapılamadı", f"Güncelleme indirilemedi veya doğrulanamadı.\n\n{error}", parent=dialog)
    finally:
        try:
            dialog.destroy()
        except tk.TclError:
            pass


def confirm_update_startup() -> None:
    """Tell the waiting updater the replacement reached the ready UI."""
    marker = next((arg.split("=", 1)[1] for arg in sys.argv[1:] if arg.startswith("--autoclicker-update-confirm=")), None)
    if marker:
        try:
            Path(marker).write_text("started", encoding="ascii")
        except OSError:
            pass
