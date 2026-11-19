from django.contrib import admin

from .models import AssistantSettings, CommandHistory


@admin.register(CommandHistory)
class CommandHistoryAdmin(admin.ModelAdmin):
    list_display = ("command_text", "command_type", "status", "created_at")
    list_filter = ("status", "command_type")


admin.site.register(AssistantSettings)
