"""Optional server-side text-to-speech fallback (pyttsx3).
The dashboard uses browser speech synthesis by default; this is for future use."""


def is_available():
    try:
        import pyttsx3  # noqa: F401
    except ImportError:
        return False
    return True


def speak(text):
    try:
        import pyttsx3
    except ImportError:
        return False
    try:
        engine = pyttsx3.init()
        engine.say(str(text)[:300])
        engine.runAndWait()
        return True
    except Exception:  # driver errors vary by machine
        return False
