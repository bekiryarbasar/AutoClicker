import time
import threading
import sys
import random
import json
import os
import subprocess
from collections import deque
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from pynput.mouse import Listener as MouseListener
from pynput.keyboard import Listener as KeyListener
import ctypes
from ctypes import wintypes
from updater import confirm_update_startup, run_startup_check, run_update_worker

# The fancy app name is stored with escapes so the .py file stays encoding-safe.
APP_NAME = (
    "\U0001D56E\u0280\U0001D41A\U0001D5BF\U0001D45F\U0001D586"
    "\U0001D4FC\u1D07\U0001D5AC\U0001D5BA\u1D04\u0280\U0001D52C"
)
APP_VERSION = "1.0.1"

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
    """Draw text over the smooth dark translucent treatment baked into the photo."""
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
            background_image = tk.PhotoImage(file=str(saved_path))
            canvas.itemconfigure(background_item, image=background_image)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass


def choose_background():
    selected = filedialog.askopenfilename(
        parent=root,
        title="Arka plan fotoğrafı seç",
        filetypes=[("Fotoğraflar", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("Tüm dosyalar", "*.*")],
    )
    if not selected:
        return
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        png_path = CONFIG_DIR / "background.png"
        render_photo_background(selected, png_path)
        CONFIG_FILE.write_text(
            json.dumps({"background": str(png_path), "overlay_version": 0}, ensure_ascii=False),
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

confirm_update_startup()
root.mainloop()
