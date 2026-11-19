from .models import AssistantSettings


def jarvis(request):
    s = AssistantSettings.load()
    return {
        "jarvis_config": {
            "language": s.language,
            "voice_enabled": s.voice_enabled,
            "auto_listen": s.auto_listen,
            "voice_name": s.voice_name,
        }
    }
