import json
import platform
import secrets
import time
from functools import wraps

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import PATH_FIELDS, SettingsForm
from .models import AssistantSettings, CommandHistory
from .services import command_handler, desktop_control, speech_service

LOCAL_ADDRS = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}
SHUTDOWN_SESSION_KEY = "jarvis_shutdown"
SHUTDOWN_TOKEN_TTL = 60  # seconds the confirmation dialog stays valid
MAX_COMMAND_LENGTH = 200
LANGS = {"en-US", "bn-BD"}


def local_only(view):
    """API endpoints answer requests from this machine only."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.META.get("REMOTE_ADDR") not in LOCAL_ADDRS:
            return JsonResponse({"ok": False, "error": "Local access only."}, status=403)
        return view(request, *args, **kwargs)
    return wrapper


def _error(message, status=400):
    return JsonResponse({"ok": False, "error": message}, status=status)


def _json_body(request):
    try:
        data = json.loads(request.body or b"")
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _history_dict(entry):
    return {
        "id": entry.id,
        "command_text": entry.command_text,
        "command_type": entry.command_type,
        "result": entry.result,
        "status": entry.status,
        "created_at": timezone.localtime(entry.created_at).strftime("%b %d, %I:%M %p"),
    }


def _stats():
    done = CommandHistory.objects.exclude(status="pending")
    total = done.count()
    last = CommandHistory.objects.first()
    return {
        "commands_today": CommandHistory.objects.filter(created_at__date=timezone.localdate()).count(),
        "success_rate": round(done.filter(status="success").count() * 100 / total) if total else None,
        "last_command": last.command_text if last else "",
    }


def dashboard(request):
    return render(request, "assistant/dashboard.html",
                  {"recent": CommandHistory.objects.all()[:6], "stats": _stats()})


def history(request):
    return render(request, "assistant/history.html", {"entries": CommandHistory.objects.all()[:100]})


def settings_view(request):
    instance = AssistantSettings.load()
    form = SettingsForm(request.POST or None, instance=instance)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Settings saved.")
            return redirect("settings")
        messages.error(request, "Some settings need attention. Fix the highlighted fields.")
    return render(request, "assistant/settings.html",
                  {"form": form, "path_fields": [form[n] for n in PATH_FIELDS]})


@local_only
@require_POST
def api_command(request):
    data = _json_body(request)
    if data is None:
        return _error("Request body must be valid JSON.")
    text = data.get("text")
    if not isinstance(text, str) or not text.strip():
        return _error("Command text is required.")
    text = text.strip()
    if len(text) > MAX_COMMAND_LENGTH:
        return _error(f"Command is too long (max {MAX_COMMAND_LENGTH} characters).")

    cfg = AssistantSettings.load()
    language = data.get("language") if data.get("language") in LANGS else cfg.language
    result = command_handler.handle_command(text, language, cfg.app_paths(), cfg.weather_city)
    payload = dict(result, ok=result["status"] != "error")

    if result["requires_confirmation"]:
        token = secrets.token_urlsafe(24)
        request.session[SHUTDOWN_SESSION_KEY] = {
            "token": token, "expires": time.time() + SHUTDOWN_TOKEN_TTL}
        payload.update(confirm_token=token, expires_in=SHUTDOWN_TOKEN_TTL)

    entry = CommandHistory.objects.create(
        command_text=text, command_type=result["command_type"],
        result=result["message"], status=result["status"])
    payload["history"] = _history_dict(entry)
    return JsonResponse(payload)


@local_only
@require_POST
def api_shutdown(request):
    data = _json_body(request)
    if data is None:
        return _error("Request body must be valid JSON.")
    token = data.get("token")
    stored = request.session.get(SHUTDOWN_SESSION_KEY)
    if data.get("confirm") is not True or not isinstance(token, str) or not stored:
        return _error("Shutdown was not confirmed.", 403)
    if time.time() > stored.get("expires", 0):
        request.session.pop(SHUTDOWN_SESSION_KEY, None)
        return _error("The confirmation expired. Ask again to shut down.", 403)
    if not secrets.compare_digest(token.encode(), stored["token"].encode()):
        return _error("Invalid confirmation token.", 403)

    request.session.pop(SHUTDOWN_SESSION_KEY, None)  # single use
    ok, message = desktop_control.schedule_shutdown(desktop_control.SHUTDOWN_DELAY_SECONDS)
    entry = CommandHistory.objects.create(
        command_text="Confirm shutdown", command_type="shutdown",
        result=message, status="success" if ok else "error")
    return JsonResponse({"ok": ok, "message": message, "history": _history_dict(entry),
                         "delay": desktop_control.SHUTDOWN_DELAY_SECONDS},
                        status=200 if ok else 500)


@local_only
@require_POST
def api_shutdown_cancel(request):
    request.session.pop(SHUTDOWN_SESSION_KEY, None)
    ok, message = desktop_control.abort_shutdown()
    return JsonResponse({"ok": True, "message": message if ok else "Shutdown request cancelled."})


@local_only
@require_GET
def api_status(request):
    return JsonResponse({
        "ok": True,
        "app": "JARVIS Assistant",
        "status": "online",
        "time": timezone.localtime().isoformat(timespec="seconds"),
        "platform": platform.system(),
        "commands_logged": CommandHistory.objects.count(),
        **_stats(),
        "server_tts_available": speech_service.is_available(),
    })
