import time
import threading
import sys
import hashlib
import random
import json
import os
import subprocess
import queue
import uuid
import importlib
from collections import deque
from pathlib import Path
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog, messagebox
from pynput.mouse import Listener as MouseListener
from pynput.keyboard import Listener as KeyListener
import ctypes
from ctypes import wintypes
from updater import confirm_update_startup, ensure_video_runtime, run_startup_check, run_update_worker

# The fancy app name is stored with escapes so the .py file stays encoding-safe.
APP_NAME = (
    "\U0001D56E\u0280\U0001D41A\U0001D5BF\U0001D45F\U0001D586"
    "\U0001D4FC\u1D07\U0001D5AC\U0001D5BA\u1D04\u0280\U0001D52C"
)
APP_VERSION = "1.0.10"
LEGACY_BACKGROUND_SHA256 = "8e5859b5216d545930ee7f442f14226ec12355cf57745ceb118dce5594b2211e"
VIDEO_DECODER_BUNDLE_NAME = "ffmpeg-win-x86_64-v9.0.2.exe"

# The temporary copy of this same EXE performs the replacement after this
# process closes. Handle it before constructing the clicker interface.
if len(sys.argv) > 1 and sys.argv[1] == "--autoclicker-apply-update":
    raise SystemExit(run_update_worker(sys.argv[2:]))

# Check GitHub and ask before the normal interface appears. Network failures
# are intentionally ignored so the clicker remains usable offline.
run_startup_check(APP_VERSION)
INSTAGRAM = "INSTAGRAM= @bekiryarbasar"
ICON_FILE = "ikon.ico"
BACKGROUND_IMAGE = "background_ui.png"
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "AutoClicker2"
CONFIG_FILE = CONFIG_DIR / "settings.json"
CUSTOM_BACKGROUND = CONFIG_DIR / "background"
BACKGROUND_OVERLAY_SCRIPT = r'''
Add-Type -AssemblyName System.Drawing
$src = [System.Drawing.Image]::FromFile($env:AC2_BG_IN)
try {
  $bmp = New-Object System.Drawing.Bitmap(510, 680)
  try {
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    try {
      $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
      $g.DrawImage($src, 0, 0, 510, 680)
    } finally { $g.Dispose() }
    $bmp.Save($env:AC2_BG_OUT, [System.Drawing.Imaging.ImageFormat]::Png)
  } finally { $bmp.Dispose() }
} finally { $src.Dispose() }
'''

VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS = 510, 680, 30
VIDEO_FRAME_BYTES = VIDEO_WIDTH * VIDEO_HEIGHT * 3
video_process = None
video_conversion_process = None
video_generation = 0
video_frame_queue = queue.Queue(maxsize=1)
video_photo = None
video_import_busy = False


def video_runtime_path():
    return CONFIG_DIR / "video-runtime" / "ffmpeg.exe"


def video_runtime_is_cached():
    path = video_runtime_path()
    try:
        with path.open("rb") as binary:
            if path.stat().st_size <= 1_000_000 or binary.read(2) != b"MZ":
                return False
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return digest == "3256173f3f8bffd7df12227c68adf68025edb1832273a9530688a7bb1ed8edec"
    except OSError:
        return False


def ffmpeg_executable():
    if getattr(sys, "frozen", False):
        bundled = resource_path(VIDEO_DECODER_BUNDLE_NAME)
        if bundled.is_file():
            return str(bundled)
        return str(ensure_video_runtime(video_runtime_path()))
    return importlib.import_module("imageio_ffmpeg").get_ffmpeg_exe()


def stop_video_playback():
    global video_process, video_generation
    video_generation += 1
    process, video_process = video_process, None
    if process is not None and process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                pass
    while True:
        try:
            video_frame_queue.get_nowait()
        except queue.Empty:
            break


def _decode_video_frames(process, generation):
    while generation == video_generation:
        try:
            frame = process.stdout.read(VIDEO_FRAME_BYTES)
        except (OSError, ValueError):
            break
        if len(frame) != VIDEO_FRAME_BYTES or generation != video_generation:
            break
        try:
            video_frame_queue.put_nowait(frame)
        except queue.Full:
            try:
                video_frame_queue.get_nowait()
                video_frame_queue.put_nowait(frame)
            except queue.Empty:
                pass


def _show_video_frame(generation):
    global background_image, video_photo
    if generation != video_generation:
        return
    try:
        frame = video_frame_queue.get_nowait()
    except queue.Empty:
        frame = None
    if frame is not None:
        try:
            video_photo = ImageTk.PhotoImage(Image.frombytes("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), frame))
            background_image = video_photo
            canvas.itemconfigure(background_item, image=video_photo)
        except (OSError, tk.TclError):
            stop_video_playback()
            return
    if video_process is not None and video_process.poll() is not None:
        stop_video_playback()
        messagebox.showerror("Video oynatılamadı", "Seçilen video açılamadı. Başka bir video deneyin.", parent=root)
        return
    try:
        root.after(max(1, 1000 // VIDEO_FPS), lambda: _show_video_frame(generation))
    except tk.TclError:
        pass


def start_video_playback(video_path):
    global video_process
    stop_video_playback()
    command = [
        ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-stream_loop", "-1", "-re",
        "-i", str(video_path), "-an", "-vf",
        f"fps={VIDEO_FPS},scale=510:680:force_original_aspect_ratio=increase,crop=510:680,setsar=1",
        "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1",
    ]
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    video_process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, bufsize=VIDEO_FRAME_BYTES, creationflags=no_window)
    generation = video_generation
    threading.Thread(target=_decode_video_frames, args=(video_process, generation),
                     name="AutoClickerVideoDecoder", daemon=True).start()
    root.after(50, lambda: _show_video_frame(generation))


def _transcode_video(source_path, temporary_path):
    global video_conversion_process
    command = [
        ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(source_path),
        "-map", "0:v:0", "-an", "-vf",
        f"fps={VIDEO_FPS},scale=510:680:force_original_aspect_ratio=increase,crop=510:680,setsar=1",
        "-c:v", "libx264", "-preset", "veryfast", "-b:v", "900k", "-maxrate", "1100k",
        "-bufsize", "2200k", "-threads", "1", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(temporary_path),
    ]
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
    video_conversion_process = process
    try:
        _, error_output = process.communicate(timeout=600)
    except subprocess.TimeoutExpired as error:
        process.kill()
        process.communicate()
        raise TimeoutError("Video hazırlığı 10 dakikayı geçti.") from error
    finally:
        video_conversion_process = None
    if process.returncode != 0 or not temporary_path.is_file() or temporary_path.stat().st_size == 0:
        details = error_output.decode("utf-8", errors="replace")[-500:].strip()
        raise OSError(details or "Video dosyası dönüştürülemedi.")


def _finish_video_import(temporary_path, error):
    global video_import_busy
    video_import_busy = False
    try:
        root.title(APP_NAME)
        if error is not None:
            temporary_path.unlink(missing_ok=True)
            messagebox.showerror("Video eklenemedi", f"Video hazırlanamadı:\n{error}", parent=root)
            return
        stop_video_playback()
        video_path = CONFIG_DIR / "background_video.mp4"
        os.replace(temporary_path, video_path)
        CONFIG_FILE.write_text(json.dumps({"background": str(video_path), "media_type": "video", "overlay_version": 0}, ensure_ascii=False), encoding="utf-8")
        load_saved_background()
    except (OSError, tk.TclError) as error:
        temporary_path.unlink(missing_ok=True)
        messagebox.showerror("Video eklenemedi", str(error), parent=root)


def import_video_background(source_path):
    global video_import_busy
    if video_import_busy:
        messagebox.showinfo("Video hazırlanıyor", "Önce mevcut video hazırlığının bitmesini bekleyin.", parent=root)
        return
    bundled_decoder = getattr(sys, "frozen", False) and resource_path(VIDEO_DECODER_BUNDLE_NAME).is_file()
    if getattr(sys, "frozen", False) and not bundled_decoder and not video_runtime_is_cached():
        accepted = messagebox.askyesno(
            "Video bileşeni indirilecek",
            "Video oynatmak için yaklaşık 39 MB'lık bileşen bir kez indirilecek ve bilgisayarınızda saklanacak. Devam edilsin mi?",
            parent=root,
        )
        if not accepted:
            return
    video_import_busy = True
    root.title(f"{APP_NAME} — Video hazırlanıyor")
    temporary_path = CONFIG_DIR / f".background-video-{uuid.uuid4().hex}.mp4"

    def worker():
        error = None
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            _transcode_video(source_path, temporary_path)
        except Exception as caught:
            error = caught
        try:
            root.after(0, lambda: _finish_video_import(temporary_path, error))
        except tk.TclError:
            temporary_path.unlink(missing_ok=True)

    threading.Thread(target=worker, name="AutoClickerVideoImport", daemon=True).start()


def _restore_saved_video(video_path):
    bundled = resource_path(VIDEO_DECODER_BUNDLE_NAME)
    if bundled.is_file() or video_runtime_is_cached():
        start_video_playback(video_path)
        return
    import_video_background(video_path)


def render_photo_background(source_path, output_path):
    conversion_env = os.environ.copy()
    conversion_env["AC2_BG_IN"] = str(source_path)
    conversion_env["AC2_BG_OUT"] = str(output_path)
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", BACKGROUND_OVERLAY_SCRIPT],
        capture_output=True, text=True, timeout=30, env=conversion_env,
    )
    if result.returncode != 0 or not Path(output_path).is_file():
        raise OSError(result.stderr.strip() or "Fotoğraf dönüştürülemedi.")


def resource_path(relative_path):
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_path / relative_path

# ================= SETTINGS =================
click_settings = {
    "left": {"label": "SOL", "cps": 15, "bind": "f6", "pressing": False, "random_cps": False},
    "right": {"label": "SAG", "cps": 15, "bind": "f7", "pressing": False, "random_cps": False},
}

click_times = {name: deque() for name in click_settings}
click_times_lock = threading.Lock()

is_binding = False
bind_buttons = {}
held_keys = set()
behavior_mode = "hold"

# ================= WINDOWS SENDINPUT =================
class MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    )


class INPUT_UNION(ctypes.Union):
    _fields_ = (("mi", MOUSEINPUT),)


class INPUT(ctypes.Structure):
    _fields_ = (("type", wintypes.DWORD), ("union", INPUT_UNION))


INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010

SendInput = ctypes.windll.user32.SendInput
SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
SendInput.restype = wintypes.UINT

click_lock = threading.Lock()


def send_mouse(flag):
    inp = INPUT(INPUT_MOUSE, INPUT_UNION(mi=MOUSEINPUT(0, 0, 0, flag, 0, None)))
    SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def click_once(button_name):
    if button_name == "left":
        down, up = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP
    else:
        down, up = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP

    with click_lock:
        send_mouse(down)
        time.sleep(0.002)
        send_mouse(up)


# ================= CLICK ENGINE =================
def click_loop(button_name):
    next_click = time.perf_counter()

    while True:
        settings = click_settings[button_name]

        if settings["pressing"] and not is_binding:
            target_cps = max(1, settings["cps"])
            if settings["random_cps"]:
                # Vary the speed from target-3 CPS up to the selected CPS.
                actual_cps = random.randint(max(1, target_cps - 3), target_cps)
            else:
                actual_cps = target_cps
            interval = 1.0 / actual_cps
            now = time.perf_counter()

            if now >= next_click:
                click_once(button_name)
                with click_times_lock:
                    click_times[button_name].append(time.perf_counter())
                next_click += interval

                # If the game/system stalls briefly, do not spam delayed clicks.
                if next_click < now:
                    next_click = now + interval
            else:
                # Wait for the next click instead of waking every millisecond.
                # The click schedule remains independent of mouse movement.
                time.sleep(next_click - now)
        else:
            next_click = time.perf_counter()
            time.sleep(0.01)


# ================= INPUT LISTENING =================
def normalize_key(key):
    return str(key).replace("'", "").replace("Key.", "").lower()


def set_status(text, color):
    root.after(0, lambda: canvas.itemconfigure(status_label, text=text, fill=color))


def update_status():
    active = [
        settings["label"]
        for settings in click_settings.values()
        if settings["pressing"]
    ]

    if active:
        set_status(" + ".join(active) + " TIKLIYOR", "#00FF00")
    else:
        set_status("BEKLEMEDE", "#FF4444")


def stop_all_clicking():
    for settings in click_settings.values():
        settings["pressing"] = False
    update_status()


def on_press(key):
    if is_binding:
        return

    pressed_key = normalize_key(key)
    if pressed_key in held_keys:
        return
    held_keys.add(pressed_key)
    changed = False

    for settings in click_settings.values():
        if pressed_key == settings["bind"]:
            if behavior_mode == "hold":
                settings["pressing"] = True
            else:
                settings["pressing"] = not settings["pressing"]
            changed = True

    if changed:
        update_status()


def on_release(key):
    released_key = normalize_key(key)
    held_keys.discard(released_key)
    if behavior_mode != "hold":
        return

    changed = False
    for settings in click_settings.values():
        if released_key == settings["bind"] and settings["pressing"]:
            settings["pressing"] = False
            changed = True
    if changed:
        update_status()


def on_click(x, y, button, pressed):
    if is_binding:
        return

    mouse_button = str(button).split(".")[-1].lower()
    changed = False

    for settings in click_settings.values():
        if mouse_button == settings["bind"]:
            if behavior_mode == "hold":
                settings["pressing"] = pressed
            elif pressed:
                settings["pressing"] = not settings["pressing"]
            changed = True

    if changed:
        update_status()


# ================= BINDING =================
def start_binding(button_name):
    global is_binding

    if is_binding:
        return

    is_binding = True
    stop_all_clicking()

    canvas.itemconfigure(bind_buttons[button_name], text="BIR TUSA BASIN...", fill="orange")

    key_listener = [None]
    mouse_listener = [None]

    def stop_all():
        if key_listener[0]:
            key_listener[0].stop()
        if mouse_listener[0]:
            mouse_listener[0].stop()
        finish_binding(button_name)

    def capture_key(key):
        click_settings[button_name]["bind"] = normalize_key(key)
        stop_all()
        return False

    def capture_mouse(x, y, button, pressed):
        if not pressed:
            return True

        mouse_button = str(button).split(".")[-1].lower()

        # Ignore left click because it is usually the UI button click.
        # Also avoid assigning a clicker to trigger itself.
        if mouse_button == "left" or mouse_button == button_name:
            return True

        click_settings[button_name]["bind"] = mouse_button
        stop_all()
        return False

    key_listener[0] = KeyListener(on_press=capture_key)
    mouse_listener[0] = MouseListener(on_click=capture_mouse)

    key_listener[0].start()
    mouse_listener[0].start()


def finish_binding(button_name):
    global is_binding
    is_binding = False

    def refresh_button():
        settings = click_settings[button_name]
        canvas.itemconfigure(
            bind_buttons[button_name],
            text=f"{settings['label']} TETIK: {settings['bind'].upper()}",
            fill="white",
        )

    root.after(0, refresh_button)


# ================= UI =================
root = tk.Tk()
root.title(APP_NAME)
root.geometry("510x680")
root.resizable(False, False)

try:
    root.iconbitmap(str(resource_path(ICON_FILE)))
except tk.TclError:
    pass

background_image = tk.PhotoImage(file=str(resource_path(BACKGROUND_IMAGE)))
canvas = tk.Canvas(root, width=510, height=680, highlightthickness=0, bd=0)
canvas.pack(fill="both", expand=True)
background_item = canvas.create_image(0, 0, image=background_image, anchor="nw")

def backed_text(*args, **kwargs):
    """Draw readable text over the plain black default background."""
    return canvas.create_text(*args, **kwargs)

def load_saved_background():
    global background_image
    try:
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        saved_path = Path(config.get("background", ""))
        if config.get("overlay_version", 0) == 1:
            clean_path = saved_path.with_name("background.png")
            if clean_path.is_file():
                saved_path = clean_path
                config.update(background=str(clean_path), overlay_version=0)
                CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        if saved_path.is_file():
            # Remove only the exact old personal image that was left selected
            # on the author's machine; other users' chosen backgrounds remain.
            digest = hashlib.sha256(saved_path.read_bytes()).hexdigest()
            if digest == LEGACY_BACKGROUND_SHA256:
                saved_path.unlink(missing_ok=True)
                config.update(background="", overlay_version=0)
                CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
                return
            if config.get("media_type") == "video":
                if getattr(sys, "frozen", False) and not video_runtime_is_cached():
                    root.after(100, lambda path=saved_path: _restore_saved_video(path))
                else:
                    start_video_playback(saved_path)
                return
            stop_video_playback()
            background_image = tk.PhotoImage(file=str(saved_path))
            canvas.itemconfigure(background_item, image=background_image)
        else:
            stop_video_playback()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass


def choose_background():
    if video_import_busy:
        messagebox.showinfo("Video hazırlanıyor", "Mevcut video hazırlığı bitince yeni bir arka plan seçebilirsiniz.", parent=root)
        return
    selected = filedialog.askopenfilename(
        parent=root,
        title="Arka plan fotoğrafı veya videosu seç",
        filetypes=[
            ("Fotoğraf ve videolar", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.mp4 *.mov *.m4v *.avi *.mkv *.webm"),
            ("Videolar", "*.mp4 *.mov *.m4v *.avi *.mkv *.webm"),
            ("Fotoğraflar", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
            ("Tüm dosyalar", "*.*"),
        ],
    )
    if not selected:
        return
    suffix = Path(selected).suffix.lower()
    if suffix in {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}:
        import_video_background(selected)
        return
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        png_path = CONFIG_DIR / "background.png"
        render_photo_background(selected, png_path)
        CONFIG_FILE.write_text(
            json.dumps({"background": str(png_path), "media_type": "image", "overlay_version": 0}, ensure_ascii=False),
            encoding="utf-8",
        )
        load_saved_background()
    except (OSError, ValueError, subprocess.SubprocessError, tk.TclError) as error:
        messagebox.showerror("Fotoğraf açılamadı", f"Bu fotoğraf kullanılamadı:\n{error}", parent=root)

def translucent_button(x1, y1, x2, y2, text, font, tag, fill="#050B10"):
    return backed_text(
        (x1 + x2) / 2, (y1 + y2) / 2,
        text=text, fill="white", font=font,
        tags=(tag,),
    )


backed_text(255, 28, text=APP_NAME, fill="#65D9FF", font=("Arial", 18, "bold"))
background_button = backed_text(477, 28, text="📁", fill="white", font=("Arial", 14, "bold"))
canvas.create_rectangle(458, 13, 496, 43, outline="#26343B", fill="#000000", tags=("background_button_box",))
canvas.tag_raise(background_button)
backed_text(255, 63, text="DURUM", fill="#E1E8EC", font=("Arial", 9))
status_label = backed_text(255, 84, text="BEKLEMEDE", fill="#FF4444", font=("Arial", 15, "bold"))

def toggle_behavior_mode():
    global behavior_mode
    stop_all_clicking()
    behavior_mode = "toggle" if behavior_mode == "hold" else "hold"
    if behavior_mode == "hold":
        canvas.itemconfigure(behavior_mode_button, text="ÇALIŞMA MODU: BASILI TUT")
        canvas.itemconfigure(behavior_mode_help, text="Tetik tuşunu basılı tut; bırakınca tıklama durur.")
    else:
        canvas.itemconfigure(behavior_mode_button, text="ÇALIŞMA MODU: AÇ/KAPAT")
        canvas.itemconfigure(behavior_mode_help, text="Bir kez bas başlat; tekrar bas durdur.")


behavior_mode_button = translucent_button(
    30, 105, 480, 145,
    "ÇALIŞMA MODU: BASILI TUT",
    ("Arial", 10, "bold"), "mode_button",
)
behavior_mode_help = backed_text(
    255, 161,
    text="Tetik tuşunu basılı tut; bırakınca tıklama durur.",
    fill="#F2F2F2", font=("Arial", 9),
)

panel_geometry = {
    "left": {"top": 180, "slider": 263, "bind": 314},
    "right": {"top": 376, "slider": 459, "bind": 510},
}
random_checks = {}
slider_knobs = {}
cps_labels = {}


def set_cps_from_x(button_name, x):
    left, right = 52, 458
    ratio = max(0.0, min(1.0, (x - left) / (right - left)))
    cps = int(round(1 + ratio * 59))
    click_settings[button_name]["cps"] = cps
    center_x = left + (cps - 1) / 59 * (right - left)
    center_y = panel_geometry[button_name]["slider"]
    knob_radius = 8
    canvas.coords(
        slider_knobs[button_name],
        center_x - knob_radius,
        center_y - knob_radius,
        center_x + knob_radius,
        center_y + knob_radius,
    )
    canvas.itemconfigure(cps_labels[button_name], text=f"{cps} CPS")


def update_random_checkbox(button_name):
    checked = click_settings[button_name]["random_cps"]
    canvas.itemconfigure(random_checks[button_name], text="✓" if checked else "")


def draw_click_panel(button_name):
    settings = click_settings[button_name]
    top = panel_geometry[button_name]["top"]
    slider_y = panel_geometry[button_name]["slider"]
    bind_y = panel_geometry[button_name]["bind"]
    backed_text(48, top + 20, text=f"{settings['label']} TIK CPS", anchor="w", fill="white", font=("Arial", 12, "bold"))

    canvas.create_rectangle(48, top + 39, 68, top + 59, fill="#071018", stipple="gray25", outline="#E7F2F7", width=1)
    random_checks[button_name] = canvas.create_text(58, top + 49, text="", fill="#70E0FF", font=("Arial", 14, "bold"))
    backed_text(78, top + 49, text="CPS dalgalansın (seçilenden 3 düşük - seçilen CPS)", anchor="w", fill="#F2F2F2", font=("Arial", 9))

    canvas.create_line(52, slider_y, 458, slider_y, fill="#E2EDF2", width=3)
    knob_x = 52 + (settings["cps"] - 1) / 59 * (458 - 52)
    slider_knobs[button_name] = canvas.create_oval(knob_x - 8, slider_y - 8, knob_x + 8, slider_y + 8, fill="#5DD8FF", outline="white", width=1)
    cps_labels[button_name] = backed_text(49, slider_y + 24, text=f"{settings['cps']} CPS", anchor="w", fill="#FFFFFF", font=("Arial", 11, "bold"))
    bind_buttons[button_name] = translucent_button(
        48, bind_y, 462, bind_y + 34,
        f"{settings['label']} TETIK: {settings['bind'].upper()}",
        ("Arial", 10, "bold"), f"bind_{button_name}",
    )


draw_click_panel("left")
draw_click_panel("right")
backed_text(255, 583, text="Sol ve sağ tık için tetik tuşlarını panellerden değiştirebilirsin.", fill="#FFFFFF", font=("Arial", 9))
backed_text(255, 610, text=INSTAGRAM, fill="#F2F2F2", font=("Arial", 9, "bold"))
cps_readout = backed_text(255, 651, text="SOL: 0 CPS  |  SAG: 0 CPS", fill="#8EE5FF", font=("Arial", 11, "bold"))
version_readout = backed_text(500, 672, text=f"v{APP_VERSION}", fill="#B8B8B8", font=("Arial", 8), anchor="se")


def handle_canvas_click(event):
    x, y = event.x, event.y
    if 30 <= x <= 480 and 105 <= y <= 145:
        toggle_behavior_mode()
        return
    if 456 <= x <= 498 and 10 <= y <= 46:
        choose_background()
        return

    for name, positions in panel_geometry.items():
        top = positions["top"]
        if 47 <= x <= 70 and top + 38 <= y <= top + 61:
            click_settings[name]["random_cps"] = not click_settings[name]["random_cps"]
            update_random_checkbox(name)
            return
        if 45 <= x <= 465 and positions["slider"] - 12 <= y <= positions["slider"] + 12:
            set_cps_from_x(name, x)
            canvas.bind("<B1-Motion>", lambda drag_event, button=name: set_cps_from_x(button, drag_event.x))
            return
        if 48 <= x <= 462 and positions["bind"] <= y <= positions["bind"] + 34:
            start_binding(name)
            return


canvas.bind("<Button-1>", handle_canvas_click)
load_saved_background()


def refresh_cps_readout():
    now = time.perf_counter()
    measured = {}
    with click_times_lock:
        for name, timestamps in click_times.items():
            while timestamps and now - timestamps[0] > 1.0:
                timestamps.popleft()
            measured[name] = len(timestamps)
    canvas.itemconfigure(cps_readout, text=f"SOL: {measured['left']} CPS  |  SAG: {measured['right']} CPS")
    root.after(250, refresh_cps_readout)


refresh_cps_readout()

# ================= START =================
KeyListener(on_press=on_press, on_release=on_release).start()
MouseListener(on_click=on_click).start()
threading.Thread(target=click_loop, args=("left",), daemon=True).start()
threading.Thread(target=click_loop, args=("right",), daemon=True).start()


def close_application():
    stop_video_playback()
    if video_conversion_process is not None and video_conversion_process.poll() is None:
        try:
            video_conversion_process.terminate()
        except OSError:
            pass
    root.destroy()


root.protocol("WM_DELETE_WINDOW", close_application)

confirm_update_startup()
root.mainloop()
