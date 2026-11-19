"""Allowlisted desktop operations. No shell is ever used and no free-form
command strings from speech/text ever reach the operating system."""
import os
import shutil
import subprocess
import webbrowser
from pathlib import Path

WEBSITES = {"youtube": {"label": "YouTube", "url": "https://www.youtube.com"}}

APPS = {
    "chrome": {
        "label": "Google Chrome",
        "exe": "chrome.exe",
        "candidates": [
            r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
            r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
            r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
        ],
    },
    "vscode": {
        "label": "VS Code",
        "exe": "Code.exe",
        "candidates": [
            r"%LocalAppData%\Programs\Microsoft VS Code\Code.exe",
            r"%ProgramFiles%\Microsoft VS Code\Code.exe",
        ],
    },
    "calculator": {
        "label": "Calculator",
        "exe": "calc.exe",
        "candidates": [r"%SystemRoot%\System32\calc.exe"],
    },
    "notepad": {
        "label": "Notepad",
        "exe": "notepad.exe",
        "candidates": [r"%SystemRoot%\System32\notepad.exe"],
    },
}

SHUTDOWN_DELAY_SECONDS = 30


def _clean(path):
    return os.path.expandvars(str(path).strip().strip('"'))


def is_valid_executable(path):
    """True only for an existing file ending in .exe."""
    try:
        p = Path(_clean(path))
        return p.suffix.lower() == ".exe" and p.is_file()
    except (TypeError, ValueError, OSError):
        return False


def resolve_app(key, custom_path=""):
    app = APPS.get(key)
    if not app:
        return None
    for candidate in [custom_path, *app["candidates"]]:
        if candidate and is_valid_executable(candidate):
            return _clean(candidate)
    found = shutil.which(app["exe"])
    return found if found and found.lower().endswith(".exe") else None


def open_app(key, custom_path=""):
    """Returns (ok, message). `key` must be in APPS."""
    app = APPS.get(key)
    if not app:
        return False, "That application is not on the allowlist."
    path = resolve_app(key, custom_path)
    if not path:
        return False, f"{app['label']} was not found on this computer. Set its path in Settings."
    try:
        subprocess.Popen([path])  # argument list, no shell
    except OSError as exc:
        return False, f"Could not start {app['label']}: {exc.strerror or exc}"
    return True, f"Opening {app['label']}."


def open_website(key):
    site = WEBSITES.get(key)
    if not site:
        return False
    try:
        return bool(webbrowser.open(site["url"]))
    except webbrowser.Error:
        return False


def schedule_shutdown(delay=SHUTDOWN_DELAY_SECONDS):
    """Schedule a Windows shutdown. Call only after explicit UI confirmation."""
    if os.name != "nt":
        return False, "Shutdown is only supported on Windows."
    try:
        subprocess.run(["shutdown", "/s", "/t", str(int(delay))], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        return False, f"Could not schedule shutdown: {exc}"
    return True, f"Your computer will shut down in {int(delay)} seconds."


def abort_shutdown():
    if os.name != "nt":
        return False, "Shutdown is only supported on Windows."
    try:
        subprocess.run(["shutdown", "/a"], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        return False, "No shutdown was scheduled."
    return True, "Shutdown cancelled."


# ---- extra allowlisted actions: Google search, volume, screenshot ----
from datetime import datetime  # noqa: E402
from urllib.parse import quote_plus  # noqa: E402

MAX_SEARCH_LENGTH = 150
VOLUME_KEYS = {"up": 175, "down": 174, "mute": 173}  # Windows media key codes
VOLUME_STEPS = 5  # each press is about 2%


def open_google_search(query):
    """Open a Google search in the default browser. Only a URL is built."""
    query = " ".join(str(query).split())[:MAX_SEARCH_LENGTH]
    if not query:
        return False
    try:
        return bool(webbrowser.open("https://www.google.com/search?q=" + quote_plus(query)))
    except webbrowser.Error:
        return False


def change_volume(action):
    """action must be 'up', 'down' or 'mute'. The PowerShell script is built
    only from fixed integers, never from user text."""
    code = VOLUME_KEYS.get(action)
    if code is None:
        return False, "Unsupported volume action."
    if os.name != "nt":
        return False, "Volume control is only supported on Windows."
    steps = 1 if action == "mute" else VOLUME_STEPS
    script = f"$w=New-Object -ComObject WScript.Shell; 1..{int(steps)} | ForEach-Object {{ $w.SendKeys([char]{int(code)}) }}"
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       check=True, capture_output=True, timeout=10,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Could not change the volume: {exc}"
    return True, ""


def take_screenshot():
    """Save a full-screen PNG to Pictures/JARVIS Screenshots. Returns (ok, path_or_error)."""
    if os.name != "nt":
        return False, "Screenshots are only supported on Windows."
    try:
        from PIL import ImageGrab
    except ImportError:
        return False, "Pillow is not installed. Run: pip install Pillow"
    try:
        folder = Path.home() / "Pictures" / "JARVIS Screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
        ImageGrab.grab().save(path)
    except OSError as exc:
        return False, f"Could not save the screenshot: {exc}"
    return True, str(path)


# ---- more allowlisted launch targets: GitHub, WhatsApp, Telegram, This PC, Recycle Bin, Settings ----
WEBSITES["github"] = {"label": "GitHub", "url": "https://github.com"}

APPS["telegram"] = {
    "label": "Telegram",
    "exe": "Telegram.exe",
    "candidates": [
        r"%AppData%\Telegram Desktop\Telegram.exe",
        r"%LocalAppData%\Telegram Desktop\Telegram.exe",
        r"%ProgramFiles%\Telegram Desktop\Telegram.exe",
    ],
}

# Fixed argument lists only; nothing from speech is ever appended.
SYSTEM_TARGETS = {
    "this_pc": {"label": "This PC", "args": ["explorer.exe", "shell:MyComputerFolder"]},
    "recycle_bin": {"label": "Recycle Bin", "args": ["explorer.exe", "shell:RecycleBinFolder"]},
    "settings": {"label": "Windows Settings", "args": ["explorer.exe", "ms-settings:"]},
}

MESSENGERS = {
    "whatsapp": {"label": "WhatsApp", "uri": "whatsapp:", "web": "https://web.whatsapp.com"},
    "telegram": {"label": "Telegram", "uri": "tg:", "web": "https://web.telegram.org", "app": "telegram"},
}


def open_system_target(key):
    """Open This PC, Recycle Bin or Windows Settings. Returns (ok, error_message)."""
    target = SYSTEM_TARGETS.get(key)
    if not target:
        return False, "That target is not on the allowlist."
    if os.name != "nt":
        return False, f"Opening {target['label']} is only supported on Windows."
    try:
        subprocess.Popen(target["args"])
    except OSError as exc:
        return False, f"Could not open {target['label']}: {exc.strerror or exc}"
    return True, ""


def open_messenger(key, custom_path=""):
    """WhatsApp / Telegram: installed app first, then the app's URI scheme, then the web version.
    Returns (True, 'app' | 'web') or (False, 'failed')."""
    m = MESSENGERS.get(key)
    if not m:
        return False, "failed"
    if m.get("app") and open_app(m["app"], custom_path)[0]:
        return True, "app"
    if os.name == "nt":
        try:
            os.startfile(m["uri"])  # registered protocol handler of an installed app
            return True, "app"
        except OSError:
            pass
    try:
        opened = webbrowser.open(m["web"])
    except webbrowser.Error:
        opened = False
    return (True, "web") if opened else (False, "failed")
