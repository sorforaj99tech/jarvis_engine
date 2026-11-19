from django.db import models


class AssistantSettings(models.Model):
    """Single-row table (pk=1) holding the user's preferences."""

    LANGUAGES = [("en-US", "English (en-US)"), ("bn-BD", "বাংলা / Bengali (bn-BD)")]

    language = models.CharField(max_length=10, choices=LANGUAGES, default="en-US")
    voice_enabled = models.BooleanField(default=True)
    auto_listen = models.BooleanField(default=False)
    voice_name = models.CharField(max_length=200, blank=True)
    chrome_path = models.CharField(max_length=500, blank=True)
    vscode_path = models.CharField(max_length=500, blank=True)
    calculator_path = models.CharField(max_length=500, blank=True)
    notepad_path = models.CharField(max_length=500, blank=True)
    telegram_path = models.CharField(max_length=500, blank=True)
    weather_city = models.CharField(max_length=80, blank=True, default="Jessore")

    class Meta:
        verbose_name_plural = "assistant settings"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def app_paths(self):
        return {
            "chrome": self.chrome_path,
            "vscode": self.vscode_path,
            "calculator": self.calculator_path,
            "notepad": self.notepad_path,
            "telegram": self.telegram_path,
        }


class CommandHistory(models.Model):
    STATUS_CHOICES = [("success", "Success"), ("error", "Failed"), ("pending", "Pending")]

    command_text = models.CharField(max_length=300)
    command_type = models.CharField(max_length=30)
    result = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name_plural = "command history"

    def __str__(self):
        return f"{self.command_text} [{self.status}]"
