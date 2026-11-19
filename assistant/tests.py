import json
from datetime import datetime
from unittest.mock import patch

from django.test import Client, SimpleTestCase, TestCase

from .models import CommandHistory
from .services import command_handler, desktop_control
from .views import SHUTDOWN_SESSION_KEY


class PageTests(TestCase):
    def test_dashboard_loads(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Hello, I'm JARVIS.")
        self.assertContains(r, "Start Listening")

    def test_settings_and_history_load(self):
        self.assertEqual(self.client.get("/settings/").status_code, 200)
        self.assertEqual(self.client.get("/history/").status_code, 200)

    def test_settings_rejects_non_exe_path(self):
        r = self.client.post("/settings/", {"language": "en-US", "chrome_path": r"C:\evil\run.bat"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "existing .exe file")

    def test_settings_save(self):
        r = self.client.post("/settings/", {"language": "bn-BD", "voice_enabled": "on"})
        self.assertRedirects(r, "/settings/")
        from .models import AssistantSettings
        self.assertEqual(AssistantSettings.load().language, "bn-BD")


class HandlerTests(SimpleTestCase):
    def test_time_english_and_bengali(self):
        self.assertTrue(command_handler.handle_command("What time is it?")["message"].startswith("The current time is"))
        self.assertIn("এখন সময়", command_handler.handle_command("এখন কয়টা বাজে?", "bn-BD")["message"])
        self.assertEqual(command_handler.handle_command("আজ কয়টা বাজে?")["command_type"], "time")

    def test_date_english_and_bengali(self):
        now = datetime.now()
        r = command_handler.handle_command("What is today's date?")
        self.assertEqual(r["command_type"], "date")
        self.assertIn(str(now.year), r["message"])
        self.assertIn("আজকের তারিখ", command_handler.handle_command("আজকের তারিখ বলো।", "bn-BD")["message"])

    @patch("assistant.services.desktop_control.open_app", return_value=(True, "Opening Google Chrome."))
    def test_open_allowlisted_app(self, mock_open):
        r = command_handler.handle_command("Open Chrome.", "en-US", {"chrome": ""})
        mock_open.assert_called_once_with("chrome", "")
        self.assertEqual((r["status"], r["message"]), ("success", "Opening Google Chrome."))

    @patch("assistant.services.desktop_control.open_app", return_value=(False, "Google Chrome was not found."))
    def test_missing_app_gives_error(self, _):
        r = command_handler.handle_command("open chrome")
        self.assertEqual(r["status"], "error")
        self.assertIn("not found", r["message"])

    @patch("assistant.services.desktop_control.open_website", return_value=True)
    def test_open_youtube(self, mock_site):
        r = command_handler.handle_command("Open YouTube")
        mock_site.assert_called_once_with("youtube")
        self.assertEqual(r["status"], "success")

    @patch("assistant.services.desktop_control.open_app")
    def test_non_allowlisted_app_rejected(self, mock_open):
        r = command_handler.handle_command("open cmd")
        self.assertEqual(r["status"], "error")
        mock_open.assert_not_called()

    def test_unknown_command(self):
        r = command_handler.handle_command("sing me a song")
        self.assertEqual(r["message"], "Sorry, I couldn't understand that command. Please try again.")
        self.assertEqual(r["command_type"], "unknown")

    def test_shutdown_needs_confirmation(self):
        for text in ("Shutdown computer.", "Turn off my laptop.", "কম্পিউটার বন্ধ করো।", "ল্যাপটপ বন্ধ করো।"):
            r = command_handler.handle_command(text)
            self.assertTrue(r["requires_confirmation"], text)
            self.assertEqual(r["command_type"], "shutdown")


class LaunchTargetTests(SimpleTestCase):
    @patch("assistant.services.desktop_control.open_system_target", return_value=(True, ""))
    def test_system_targets(self, mock_open):
        for text, key in (("Open This PC", "this_pc"), ("open recycle bin", "recycle_bin"),
                          ("Open Settings", "settings"), ("সেটিংস খোলো", "settings"),
                          ("রিসাইকেল বিন খোলো", "recycle_bin")):
            r = command_handler.handle_command(text)
            mock_open.assert_called_with(key)
            self.assertEqual(r["status"], "success", text)

    @patch("assistant.services.desktop_control.open_messenger", return_value=(True, "app"))
    def test_messengers_app(self, mock_open):
        r = command_handler.handle_command("Open WhatsApp")
        mock_open.assert_called_with("whatsapp", "")
        self.assertEqual(r["message"], "Opening WhatsApp.")
        command_handler.handle_command("টেলিগ্রাম খোলো", "bn-BD")
        mock_open.assert_called_with("telegram", "")

    @patch("assistant.services.desktop_control.open_messenger", return_value=(True, "web"))
    def test_messenger_web_fallback(self, _):
        self.assertIn("WhatsApp Web", command_handler.handle_command("open whatsapp")["message"])

    @patch("assistant.services.desktop_control.open_website", return_value=True)
    def test_github(self, mock_site):
        command_handler.handle_command("Open GitHub")
        mock_site.assert_called_once_with("github")

    def test_unknown_targets_rejected(self):
        self.assertFalse(desktop_control.open_system_target("cmd")[0])
        self.assertFalse(desktop_control.open_messenger("signal")[0])

    def test_shutdown_still_wins_over_my_computer(self):
        r = command_handler.handle_command("turn off my computer")
        self.assertEqual(r["command_type"], "shutdown")


class ExtraCommandTests(SimpleTestCase):
    @patch("assistant.services.desktop_control.open_google_search", return_value=True)
    def test_google_search(self, mock_search):
        r = command_handler.handle_command("Search Google for Django tutorials.")
        mock_search.assert_called_once_with("django tutorials")
        self.assertEqual((r["command_type"], r["status"]), ("search", "success"))
        r = command_handler.handle_command("গুগলে পাইথন শেখা সার্চ করো", "bn-BD")
        self.assertEqual(r["command_type"], "search")
        mock_search.assert_called_with("পাইথন শেখা")

    def test_search_without_query(self):
        self.assertEqual(command_handler.handle_command("search")["command_type"], "unknown")
        self.assertEqual(command_handler.handle_command("search for")["command_type"], "unknown")

    @patch("assistant.services.desktop_control.change_volume", return_value=(True, ""))
    def test_volume(self, mock_vol):
        for text, action in (("Volume up", "up"), ("turn the volume down", "down"), ("mute", "mute"),
                             ("ভলিউম বাড়াও", "up"), ("ভলিউম কমাও", "down")):
            command_handler.handle_command(text)
            mock_vol.assert_called_with(action)
        self.assertEqual(command_handler.handle_command("volume")["status"], "error")

    @patch("assistant.services.desktop_control.take_screenshot", return_value=(True, r"C:\\shots\\a.png"))
    def test_screenshot(self, _):
        r = command_handler.handle_command("Take a screenshot")
        self.assertEqual((r["command_type"], r["status"]), ("screenshot", "success"))
        self.assertIn("a.png", r["message"])

    @patch("assistant.services.weather_service.get_weather")
    def test_weather(self, mock_w):
        mock_w.return_value = (True, {"city": "Dhaka", "temp": 31, "feels": 35, "humidity": 70, "wind": 12,
                                      "condition": "partly cloudy"})
        r = command_handler.handle_command("What's the weather like in Dhaka today?")
        mock_w.assert_called_with("dhaka")
        self.assertIn("31°C", r["message"])
        command_handler.handle_command("weather", "en-US", None, "Jessore")
        mock_w.assert_called_with("Jessore")

    @patch("assistant.services.weather_service.get_weather", return_value=(False, "network"))
    def test_weather_network_error(self, _):
        r = command_handler.handle_command("weather in Dhaka")
        self.assertEqual(r["status"], "error")
        self.assertIn("internet", r["message"])

    @patch("assistant.services.desktop_control.subprocess.run")
    def test_volume_rejects_unknown_action(self, mock_run):
        self.assertFalse(desktop_control.change_volume("format c:")[0])
        mock_run.assert_not_called()


class DesktopControlTests(SimpleTestCase):
    @patch("assistant.services.desktop_control.subprocess.Popen")
    @patch("assistant.services.desktop_control.resolve_app", return_value=None)
    def test_missing_executable(self, _, mock_popen):
        ok, msg = desktop_control.open_app("chrome")
        self.assertFalse(ok)
        self.assertIn("not found", msg)
        mock_popen.assert_not_called()

    def test_unknown_key_and_bad_paths(self):
        self.assertFalse(desktop_control.open_app("powershell")[0])
        self.assertFalse(desktop_control.is_valid_executable(r"C:\x\script.bat"))
        self.assertFalse(desktop_control.is_valid_executable(""))


class ApiTests(TestCase):
    def post(self, url, data, client=None):
        return (client or self.client).post(url, json.dumps(data), content_type="application/json")

    def test_command_success_and_history(self):
        r = self.post("/api/command/", {"text": "What time is it?"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(CommandHistory.objects.count(), 1)
        self.assertEqual(CommandHistory.objects.first().status, "success")

    def test_unknown_command_logged_as_error(self):
        body = self.post("/api/command/", {"text": "blah blah"}).json()
        self.assertFalse(body["ok"])
        self.assertEqual(CommandHistory.objects.first().status, "error")

    def test_invalid_requests(self):
        self.assertEqual(self.client.post("/api/command/", "not json", content_type="application/json").status_code, 400)
        self.assertEqual(self.post("/api/command/", {"text": "   "}).status_code, 400)
        self.assertEqual(self.post("/api/command/", {"text": 5}).status_code, 400)
        self.assertEqual(self.post("/api/command/", {"text": "x" * 500}).status_code, 400)
        self.assertEqual(self.client.get("/api/command/").status_code, 405)
        self.assertEqual(self.client.get("/api/shutdown/").status_code, 405)

    def test_csrf_enforced(self):
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(self.post("/api/command/", {"text": "time"}, strict).status_code, 403)
        self.assertEqual(self.post("/api/shutdown/", {"confirm": True, "token": "x"}, strict).status_code, 403)

    def test_remote_address_blocked(self):
        r = self.client.get("/api/status/", REMOTE_ADDR="192.168.1.50")
        self.assertEqual(r.status_code, 403)

    def test_status(self):
        r = self.client.get("/api/status/")
        self.assertEqual(r.json()["status"], "online")

    @patch("assistant.views.desktop_control.schedule_shutdown", return_value=(True, "ok"))
    def test_shutdown_requires_prior_request(self, mock_sd):
        r = self.post("/api/shutdown/", {"confirm": True, "token": "guess"})
        self.assertEqual(r.status_code, 403)
        mock_sd.assert_not_called()

    @patch("assistant.views.desktop_control.schedule_shutdown", return_value=(True, "ok"))
    def test_shutdown_full_flow(self, mock_sd):
        body = self.post("/api/command/", {"text": "Shutdown computer"}).json()
        self.assertTrue(body["requires_confirmation"])
        mock_sd.assert_not_called()  # speech alone never shuts down
        token = body["confirm_token"]
        self.assertEqual(self.post("/api/shutdown/", {"confirm": False, "token": token}).status_code, 403)
        self.assertEqual(self.post("/api/shutdown/", {"confirm": True, "token": "wrong"}).status_code, 403)
        mock_sd.assert_not_called()
        r = self.post("/api/shutdown/", {"confirm": True, "token": token})
        self.assertEqual(r.status_code, 200)
        mock_sd.assert_called_once()
        # token is single-use
        self.assertEqual(self.post("/api/shutdown/", {"confirm": True, "token": token}).status_code, 403)
        self.assertEqual(mock_sd.call_count, 1)

    @patch("assistant.views.desktop_control.schedule_shutdown", return_value=(True, "ok"))
    def test_shutdown_token_expires(self, mock_sd):
        token = self.post("/api/command/", {"text": "Shutdown computer"}).json()["confirm_token"]
        s = self.client.session
        data = s[SHUTDOWN_SESSION_KEY]
        data["expires"] = 0
        s[SHUTDOWN_SESSION_KEY] = data
        s.save()
        self.assertEqual(self.post("/api/shutdown/", {"confirm": True, "token": token}).status_code, 403)
        mock_sd.assert_not_called()

    @patch("assistant.views.desktop_control.abort_shutdown", return_value=(False, "none"))
    def test_cancel_clears_token(self, _):
        token = self.post("/api/command/", {"text": "Shutdown computer"}).json()["confirm_token"]
        self.assertEqual(self.post("/api/shutdown/cancel/", {}).status_code, 200)
        self.assertEqual(self.post("/api/shutdown/", {"confirm": True, "token": token}).status_code, 403)
