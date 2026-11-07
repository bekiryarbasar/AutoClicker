"""Safe GitHub Releases updater for the AutoClicker Windows build."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
import zipfile
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from tkinter import messagebox


CONFIG_NAME = "updater_config.json"
PACKAGE_NAME = "AutoClicker-Windows.zip"
CHECKSUMS_NAME = "SHA256SUMS.txt"
MAX_API_BYTES = 2 * 1024 * 1024
MAX_CHECKSUMS_BYTES = 16 * 1024
MAX_PACKAGE_BYTES = 100 * 1024 * 1024
MAX_EXE_BYTES = 150 * 1024 * 1024
MAX_HELPER_BYTES = 60 * 1024 * 1024
EXPECTED_PACKAGE_FILES = {
    "AutoClicker.exe",
    "AutoClickerUpdater.exe",
    CONFIG_NAME,
}


def _application_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _config_path() -> Path:
    return _application_directory() / CONFIG_NAME


def _load_repository() -> tuple[str, str] | None:
    try:
        data = json.loads(_config_path().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("check_for_updates", True) is not True:
        return None

    owner = data.get("owner", "")
    repo = data.get("repo", "")
    if not isinstance(owner, str) or not isinstance(repo, str):
        return None
    owner, repo = owner.strip(), repo.strip()
    safe_segment = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
    if not safe_segment.fullmatch(owner) or not safe_segment.fullmatch(repo):
        return None
    if owner in {".", ".."} or repo in {".", ".."}:
        return None
    return owner, repo


def _version_tuple(version: str) -> tuple[int, ...] | None:
    if not isinstance(version, str):
        return None
    match = re.fullmatch(r"v?(\d+(?:\.\d+){1,3})", version.strip(), re.IGNORECASE)
    if not match:
        return None
    try:
        parts = tuple(int(part) for part in match.group(1).split("."))
    except ValueError:
        return None
    return parts + (0,) * (4 - len(parts))


def _request_bytes(url: str, *, max_bytes: int, accept: str = "application/octet-stream") -> bytes:
    request = Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": "AutoClicker-Updater/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=20) as response:
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            raise ValueError("İndirilecek dosya izin verilen boyutu aşıyor.")
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("İndirilecek dosya izin verilen boyutu aşıyor.")
    return data


def _release_asset_url(owner: str, repo: str, tag: str, asset_name: str, assets: list[dict]) -> str | None:
    base_path = (
        f"/{quote(owner, safe='')}/{quote(repo, safe='')}/releases/download/"
        f"{quote(tag, safe='')}/"
    )
    found = [item for item in assets if isinstance(item, dict) and item.get("name") == asset_name]
    if len(found) != 1:
        return None
    url = found[0].get("browser_download_url")
    if not isinstance(url, str):
        return None
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com" or not parsed.path.startswith(base_path):
        return None
    return url


def _find_update(current_version: str) -> dict | None:
    repository = _load_repository()
    current = _version_tuple(current_version)
    if repository is None or current is None:
        return None
    owner, repo = repository
    api_url = f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/releases/latest"
    release = json.loads(_request_bytes(api_url, max_bytes=MAX_API_BYTES, accept="application/vnd.github+json"))
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        return None
    tag = release.get("tag_name")
    latest = _version_tuple(tag)
    if latest is None or latest <= current:
        return None
    assets = release.get("assets")
    if not isinstance(assets, list):
        return None
    package_url = _release_asset_url(owner, repo, tag, PACKAGE_NAME, assets)
    checksums_url = _release_asset_url(owner, repo, tag, CHECKSUMS_NAME, assets)
    if not package_url or not checksums_url:
        return None
    return {
        "tag": tag,
        "version": ".".join(str(part) for part in latest[:3]),
        "package_url": package_url,
        "checksums_url": checksums_url,
        "owner": owner,
        "repo": repo,
    }


def confirm_update_startup() -> None:
    """Signal to the helper that the replacement app reached UI startup."""
    prefix = "--autoclicker-update-confirm="
    marker = next((arg[len(prefix):] for arg in sys.argv[1:] if arg.startswith(prefix)), None)
    if not marker:
        return
    try:
        Path(marker).write_text("started", encoding="ascii")
    except OSError:
        pass


def start_update_check(root, current_version: str) -> None:
    """Check public GitHub Releases without blocking the clicker UI."""
    if not getattr(sys, "frozen", False):
        return

    def check_in_background() -> None:
        try:
            update = _find_update(current_version)
        except Exception:
            return
        if update is None:
            return
        try:
            root.after(0, lambda: _ask_to_update(root, update))
        except Exception:
            return

    threading.Thread(target=check_in_background, name="AutoClickerUpdateCheck", daemon=True).start()


def _ask_to_update(root, update: dict) -> None:
    try:
        if not root.winfo_exists():
            return
    except Exception:
        return
    install = messagebox.askyesno(
        "Güncelleme bulundu",
        f"AutoClicker {update['version']} sürümü bulundu.\n\n"
        "Güncelleme şimdi indirilip kurulacak ve program yeniden başlatılacak mı?",
        parent=root,
    )
    if not install:
        return

    def download_in_background() -> None:
        try:
            candidate_app, candidate_helper, staging_dir = _download_and_stage(update)
            try:
                root.after(0, lambda: _start_helper(root, candidate_app, candidate_helper, staging_dir))
            except Exception:
                shutil.rmtree(staging_dir, ignore_errors=True)
        except Exception as error:
            _show_error_when_ready(root, f"Güncelleme indirilemedi veya doğrulanamadı:\n{error}")

    threading.Thread(target=download_in_background, name="AutoClickerUpdateDownload", daemon=True).start()


def _checksum_for_package(text: str) -> str:
    for line in text.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        name = parts[1].lstrip("* ")
        digest = parts[0].lower()
        if name == PACKAGE_NAME and re.fullmatch(r"[0-9a-f]{64}", digest):
            return digest
    raise ValueError(f"{CHECKSUMS_NAME} içinde {PACKAGE_NAME} için SHA-256 bulunamadı.")


def _download_and_stage(update: dict) -> tuple[Path, Path, Path]:
    checksum_data = _request_bytes(update["checksums_url"], max_bytes=MAX_CHECKSUMS_BYTES)
    try:
        expected_digest = _checksum_for_package(checksum_data.decode("ascii"))
    except UnicodeDecodeError as error:
        raise ValueError("SHA-256 dosyası okunamıyor.") from error

    staging_dir = Path(tempfile.mkdtemp(prefix="AutoClicker-update-"))
    package_path = staging_dir / PACKAGE_NAME
    try:
        package_data = _request_bytes(update["package_url"], max_bytes=MAX_PACKAGE_BYTES)
        package_path.write_bytes(package_data)
        actual_digest = hashlib.sha256(package_data).hexdigest()
        if actual_digest != expected_digest:
            raise ValueError("Güncelleme dosyasının SHA-256 değeri eşleşmiyor.")

        candidate = staging_dir / "AutoClicker.exe"
        candidate_helper = staging_dir / "AutoClickerUpdater.exe"
        with zipfile.ZipFile(package_path, "r") as package:
            infos = package.infolist()
            names = [entry.filename for entry in infos]
            if len(names) != len(set(names)) or set(names) != EXPECTED_PACKAGE_FILES:
                raise ValueError("Güncelleme paketi beklenen dosya yapısına sahip değil.")
            total_uncompressed = 0
            info_by_name = {}
            for entry in infos:
                if entry.is_dir() or "/" in entry.filename or "\\" in entry.filename:
                    raise ValueError("Güncelleme paketinde geçersiz dosya yolu var.")
                if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Güncelleme paketi sembolik bağlantı içeremez.")
                total_uncompressed += entry.file_size
                info_by_name[entry.filename] = entry
            if total_uncompressed > MAX_EXE_BYTES + MAX_HELPER_BYTES + 4096:
                raise ValueError("Güncelleme paketi çok büyük.")
            app_info = info_by_name["AutoClicker.exe"]
            helper_info = info_by_name["AutoClickerUpdater.exe"]
            config_info = info_by_name[CONFIG_NAME]
            if not 1_000_000 <= app_info.file_size <= MAX_EXE_BYTES:
                raise ValueError("Yeni AutoClicker.exe boyutu beklenmiyor.")
            if not 1_000_000 <= helper_info.file_size <= MAX_HELPER_BYTES:
                raise ValueError("Güncelleme yardımcısının boyutu beklenmiyor.")
            if config_info.file_size > 4096:
                raise ValueError("Güncelleme ayar dosyası çok büyük.")
            release_config = json.loads(package.read(CONFIG_NAME).decode("utf-8"))
            if not isinstance(release_config, dict) or (
                release_config.get("owner"), release_config.get("repo")
            ) != (update["owner"], update["repo"]):
                raise ValueError("Paket farklı bir GitHub deposu için hazırlanmış.")
            if package.testzip() is not None:
                raise ValueError("Güncelleme paketindeki bir dosya bozuk.")
            with package.open("AutoClicker.exe") as source, candidate.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            with package.open("AutoClickerUpdater.exe") as source, candidate_helper.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)

        if candidate.stat().st_size != app_info.file_size:
            raise ValueError("Yeni program dosyası eksik indirildi.")
        with candidate.open("rb") as app_file:
            if app_file.read(2) != b"MZ":
                raise ValueError("İndirilen program geçerli bir Windows EXE değil.")
        if candidate_helper.stat().st_size != helper_info.file_size:
            raise ValueError("Güncelleme yardımcısı eksik indirildi.")
        with candidate_helper.open("rb") as helper_file:
            if helper_file.read(2) != b"MZ":
                raise ValueError("İndirilen güncelleme yardımcısı geçerli bir Windows EXE değil.")
        return candidate, candidate_helper, staging_dir
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise


def _start_helper(root, candidate_app: Path, candidate_helper: Path, staging_dir: Path) -> None:
    app_dir = _application_directory()
    target = app_dir / "AutoClicker.exe"
    helper = app_dir / "AutoClickerUpdater.exe"
    try:
        if not target.is_file() or not helper.is_file():
            raise FileNotFoundError("AutoClicker.exe veya AutoClickerUpdater.exe aynı klasörde bulunamadı.")
        worker_path = Path(tempfile.gettempdir()) / f"AutoClickerUpdater-{uuid.uuid4().hex}.exe"
        shutil.copy2(helper, worker_path)
        flags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        subprocess.Popen(
            [
                str(worker_path),
                "--apply",
                str(candidate_app),
                str(candidate_helper),
                str(target),
                str(helper),
                str(os.getpid()),
                str(staging_dir),
            ],
            cwd=str(tempfile.gettempdir()),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
        root.destroy()
    except Exception as error:
        shutil.rmtree(staging_dir, ignore_errors=True)
        _show_error_when_ready(root, f"Güncelleme başlatılamadı:\n{error}")


def _show_error_when_ready(root, message: str) -> None:
    def show() -> None:
        try:
            if root.winfo_exists():
                messagebox.showerror("Güncelleme yapılamadı", message[:1200], parent=root)
        except Exception:
            pass

    try:
        root.after(0, show)
    except Exception:
        pass
