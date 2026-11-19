from django import forms

from .models import AssistantSettings
from .services import desktop_control

PATH_FIELDS = ["chrome_path", "vscode_path", "calculator_path", "notepad_path", "telegram_path"]


class SettingsForm(forms.ModelForm):
    class Meta:
        model = AssistantSettings
        fields = ["language", "voice_enabled", "auto_listen", "voice_name", "weather_city", *PATH_FIELDS]
        labels = {
            "weather_city": "Default city for weather",
            "chrome_path": "Google Chrome (chrome.exe)",
            "vscode_path": "VS Code (Code.exe)",
            "calculator_path": "Calculator (calc.exe)",
            "notepad_path": "Notepad (notepad.exe)",
            "telegram_path": "Telegram (Telegram.exe)",
        }
        widgets = {
            "language": forms.Select(),
            "voice_name": forms.HiddenInput(),
            "weather_city": forms.TextInput(attrs={"placeholder": "e.g. Dhaka"}),
            **{f: forms.TextInput(attrs={"placeholder": "Auto-detect"}) for f in PATH_FIELDS},
        }

    def clean(self):
        cleaned = super().clean()
        for name in PATH_FIELDS:
            value = (cleaned.get(name) or "").strip().strip('"')
            cleaned[name] = value
            if value and not desktop_control.is_valid_executable(value):
                self.add_error(name, "Enter the full path of an existing .exe file.")
        return cleaned
