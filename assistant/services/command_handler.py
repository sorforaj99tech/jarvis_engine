"""Turns recognised text into one of a few allowlisted intents.
Only fixed intents are produced; nothing here builds shell commands."""
import re
import string
from datetime import datetime

from . import desktop_control, weather_service

UNKNOWN_MESSAGE = "Sorry, I couldn't understand that command. Please try again."
_PUNCT = str.maketrans("", "", string.punctuation + "।॥“”‘’…")
BN_MONTHS = ["জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন", "জুলাই",
             "আগস্ট", "সেপ্টেম্বর", "অক্টোবর", "নভেম্বর", "ডিসেম্বর"]

# alias -> (kind, key); longest aliases are tested first
ALIASES = {
    "visual studio code": ("app", "vscode"), "vs code": ("app", "vscode"), "vscode": ("app", "vscode"),
    "ভিএস কোড": ("app", "vscode"), "ভিএসকোড": ("app", "vscode"),
    "chrome": ("app", "chrome"), "ক্রোম": ("app", "chrome"),
    "calculator": ("app", "calculator"), "ক্যালকুলেটর": ("app", "calculator"),
    "notepad": ("app", "notepad"), "নোটপ্যাড": ("app", "notepad"),
    "youtube": ("site", "youtube"), "ইউটিউব": ("site", "youtube"),
    "github": ("site", "github"), "git hub": ("site", "github"), "গিটহাব": ("site", "github"),
    "whatsapp": ("chat", "whatsapp"), "whats app": ("chat", "whatsapp"),
    "হোয়াটসঅ্যাপ": ("chat", "whatsapp"), "হোয়াটস অ্যাপ": ("chat", "whatsapp"), "হোয়াটসএপ": ("chat", "whatsapp"),
    "telegram": ("chat", "telegram"), "টেলিগ্রাম": ("chat", "telegram"),
    "this pc": ("system", "this_pc"), "my pc": ("system", "this_pc"), "my computer": ("system", "this_pc"),
    "this computer": ("system", "this_pc"), "এই পিসি": ("system", "this_pc"), "মাই কম্পিউটার": ("system", "this_pc"),
    "recycle bin": ("system", "recycle_bin"), "recyclebin": ("system", "recycle_bin"),
    "trash": ("system", "recycle_bin"), "রিসাইকেল বিন": ("system", "recycle_bin"),
    "settings": ("system", "settings"), "setting": ("system", "settings"),
    "সেটিংস": ("system", "settings"), "সেটিং": ("system", "settings"),
}
_ALIASES_SORTED = sorted(ALIASES, key=len, reverse=True)


def _t(en, bn, lang):
    return bn if lang == "bn-BD" else en


def _result(command_type, status, message, confirm=False):
    return {"command_type": command_type, "status": status, "message": message,
            "requires_confirmation": confirm}


def normalize(text):
    return " ".join(text.lower().translate(_PUNCT).split())


def _is_shutdown(t):
    en = re.search(r"\b(shut ?down|turn off|power off|switch off)\b", t) and \
        re.search(r"\b(computer|laptop|pc)\b", t)
    bn = "বন্ধ" in t and ("কম্পিউটার" in t or "ল্যাপটপ" in t)
    return bool(en or bn)


def _is_open(t):
    return bool(re.search(r"\b(open|launch|start|run)\b", t)) or \
        any(w in t for w in ("খোল", "খুল", "চালু", "ওপেন"))


def _search_query(t):
    m = re.match(r"(?:please )?(?:search(?: google)?(?: for)?|google(?: search)?|look up) (.+)", t)
    if m:
        return re.sub(r" on google$", "", m.group(1)).strip()
    if "গুগল" in t and any(w in t for w in ("সার্চ", "খোঁজ", "খুঁজ")):
        drop = {"গুগলে", "গুগল", "সার্চ", "করো", "করুন", "কর", "খোঁজো", "খুঁজো", "খোঁজ", "খুঁজে", "দেখো", "দাও"}
        return " ".join(w for w in t.split() if w not in drop)
    return None


def _weather_city(t, default):
    m = re.search(r"weather(?: like)? (?:in|at|for|of) (.+)", t)
    city = m.group(1) if m else default
    return re.sub(r"( today| now| right now| tomorrow)+$", "", city).strip()


def _volume_action(t):
    if re.search(r"\b(mute|unmute)\b", t) or "মিউট" in t:
        return "mute"
    if re.search(r"\b(up|increase|raise|louder|higher)\b", t) or "বাড়" in t:
        return "up"
    if re.search(r"\b(down|decrease|lower|reduce|quieter|softer)\b", t) or "কম" in t:
        return "down"
    return None


def handle_command(text, language="en-US", app_paths=None, weather_city=""):
    app_paths = app_paths or {}
    t = normalize(text)

    if _is_shutdown(t):
        return _result("shutdown", "pending",
                       _t("Please confirm before shutting down your computer.",
                          "কম্পিউটার বন্ধ করার আগে অনুগ্রহ করে নিশ্চিত করুন।", language),
                       confirm=True)

    query = _search_query(t)
    if query is not None:
        if not query:
            return _result("search", "error", _t("What should I search for?", "কী সার্চ করব?", language))
        if desktop_control.open_google_search(query):
            return _result("search", "success", _t(f"Searching Google for {query}.",
                                                   f"গুগলে {query} সার্চ করা হচ্ছে।", language))
        return _result("search", "error", _t("I couldn't open your browser.", "ব্রাউজার খুলতে পারিনি।", language))

    if _is_open(t):
        alias = next((a for a in _ALIASES_SORTED if a in t), None)
        if not alias:
            return _result("open_app", "error", _t(
                "I can open Chrome, VS Code, Calculator, Notepad, WhatsApp, Telegram, YouTube, GitHub, "
                "This PC, Recycle Bin and Settings.",
                "আমি Chrome, VS Code, Calculator, Notepad, WhatsApp, Telegram, YouTube, GitHub, "
                "This PC, Recycle Bin ও Settings খুলতে পারি।", language))
        kind, key = ALIASES[alias]
        if kind == "site":
            label = desktop_control.WEBSITES[key]["label"]
            ok = desktop_control.open_website(key)
            if ok:
                return _result("open_website", "success",
                               _t(f"Opening {label}.", f"{label} খোলা হচ্ছে।", language))
            return _result("open_website", "error", _t(
                f"I couldn't open {label} in your browser.",
                f"ব্রাউজারে {label} খুলতে পারিনি।", language))
        if kind == "system":
            label = desktop_control.SYSTEM_TARGETS[key]["label"]
            ok, err = desktop_control.open_system_target(key)
            if ok:
                return _result("open_app", "success", _t(f"Opening {label}.", f"{label} খোলা হচ্ছে।", language))
            return _result("open_app", "error", err)
        if kind == "chat":
            label = desktop_control.MESSENGERS[key]["label"]
            ok, mode = desktop_control.open_messenger(key, app_paths.get(key, ""))
            if not ok:
                return _result("open_app", "error", _t(f"I couldn't open {label}.", f"{label} খুলতে পারিনি।", language))
            if mode == "web":
                return _result("open_app", "success", _t(
                    f"The {label} app was not found, so I opened {label} Web.",
                    f"{label} অ্যাপ পাওয়া যায়নি, তাই {label} ওয়েব খোলা হয়েছে।", language))
            return _result("open_app", "success", _t(f"Opening {label}.", f"{label} খোলা হচ্ছে।", language))
        label = desktop_control.APPS[key]["label"]
        ok, msg = desktop_control.open_app(key, app_paths.get(key, ""))
        if ok:
            return _result("open_app", "success",
                           _t(f"Opening {label}.", f"{label} খোলা হচ্ছে।", language))
        return _result("open_app", "error", msg)

    if "weather" in t or "আবহাওয়া" in t:
        ok, data = weather_service.get_weather(_weather_city(t, weather_city))
        if ok:
            return _result("weather", "success", _t(
                f"Weather in {data['city']}: {data['temp']}°C, {data['condition']}. Feels like {data['feels']}°C, "
                f"humidity {data['humidity']}%, wind {data['wind']} km/h.",
                f"{data['city']}-এর আবহাওয়া: {data['temp']}°C, {data['condition']}। অনুভূত তাপমাত্রা {data['feels']}°C, "
                f"আর্দ্রতা {data['humidity']}%, বাতাস {data['wind']} কিমি/ঘণ্টা।", language))
        errors = {
            "no_city": ("Tell me a city, for example: weather in Dhaka. Or set a default city in Settings.",
                        "একটি শহরের নাম বলুন, অথবা Settings-এ ডিফল্ট শহর দিন।"),
            "not_found": ("I couldn't find that city.", "শহরটি খুঁজে পাইনি।"),
            "network": ("I couldn't get the weather. Check your internet connection.",
                        "আবহাওয়ার তথ্য আনতে পারিনি। ইন্টারনেট সংযোগ দেখুন।"),
        }
        return _result("weather", "error", _t(*errors[data], language))

    if any(k in t for k in ("screenshot", "screen shot", "স্ক্রিনশট", "স্ক্রিন শট")):
        ok, info = desktop_control.take_screenshot()
        if ok:
            return _result("screenshot", "success", _t(f"Screenshot saved to {info}",
                                                       f"স্ক্রিনশট সেভ হয়েছে: {info}", language))
        return _result("screenshot", "error", info)

    if re.search(r"\b(volume|louder|quieter|mute|unmute)\b", t) or "ভলিউম" in t or "মিউট" in t:
        action = _volume_action(t)
        if action is None:
            return _result("volume", "error", _t("Say volume up, volume down, or mute.",
                                                 "ভলিউম বাড়াও, ভলিউম কমাও, অথবা মিউট বলুন।", language))
        ok, err = desktop_control.change_volume(action)
        if not ok:
            return _result("volume", "error", err)
        msgs = {"up": ("Volume increased.", "ভলিউম বাড়ানো হয়েছে।"), "down": ("Volume decreased.", "ভলিউম কমানো হয়েছে।"),
                "mute": ("Mute toggled.", "মিউট টগল করা হয়েছে।")}
        return _result("volume", "success", _t(*msgs[action], language))

    if re.search(r"\bdate\b", t) or "তারিখ" in t:
        now = datetime.now()
        return _result("date", "success", _t(
            f"Today's date is {now:%B} {now.day}, {now.year}.",
            f"আজকের তারিখ {now.day} {BN_MONTHS[now.month - 1]} {now.year}।", language))

    if re.search(r"\btime\b", t) or any(k in t for k in ("কয়টা বাজে", "কটা বাজে", "সময়")):
        now = datetime.now().strftime("%I:%M %p").lstrip("0")
        return _result("time", "success", _t(
            f"The current time is {now}.", f"এখন সময় {now}।", language))

    return _result("unknown", "error", UNKNOWN_MESSAGE)
