# JARVIS Assistant

A local, voice-controlled desktop assistant for Windows built with Django 5.2 LTS, SQLite and the browser Web Speech API.

## Install and run (Windows, PowerShell)

```powershell
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process RemoteSigned` once in that window.
Open the dashboard at **http://127.0.0.1:8000/** (use `localhost` or `127.0.0.1` only).

Run the tests with `python manage.py test`.

## Voice and microphone

- Use **Google Chrome or Microsoft Edge**. Firefox does not support speech recognition.
- Click the mic (or Start Listening). When the browser asks, choose **Allow** for the microphone. If you denied it, click the lock icon in the address bar and allow it.
- Chrome and Edge send audio to their own cloud speech service, so recognition needs internet. This app stores no audio.
- Pick English (`en-US`) or Bengali (`bn-BD`) in the voice panel. Bengali recognition quality depends on the browser.
- Spoken replies use the browser voices installed on your PC. If no Bengali voice is installed, Bengali replies show as text only. Add one in Windows Settings > Time & language > Speech.
- "Auto-listening" listens again after each successful command. It never restarts after an error, and it cannot start by itself on page load because browsers need a click first.
- No microphone or unsupported browser? Type commands in the text box.

## Commands

| Say / type | Action |
|---|---|
| What time is it? / আজ কয়টা বাজে? | Tells the local time |
| What is today's date? / আজকের তারিখ বলো। | Tells the local date |
| Open Chrome / Calculator / Notepad / VS Code | Starts the allowlisted app |
| Open YouTube | Opens youtube.com in your default browser |
| Search Google for ... / গুগলে ... সার্চ করো | Opens a Google search in your default browser |
| What's the weather? / weather in Dhaka | Current weather (Open-Meteo, needs internet; default city in Settings) |
| Take a screenshot / স্ক্রিনশট নাও | Saves a PNG in `Pictures\JARVIS Screenshots` (needs Pillow) |
| Volume up / Volume down / Mute | Presses the Windows media volume keys (about 10% per step; mute toggles) |
| Open WhatsApp / Telegram | Starts the installed app; opens the web version if it is not installed |
| Open GitHub | Opens github.com in your default browser |
| Open This PC / Recycle Bin / Settings | Opens that Windows location (`এই পিসি খোলো`, `রিসাইকেল বিন খোলো`, `সেটিংস খোলো`) |
| Shutdown computer / কম্পিউটার বন্ধ করো। | Asks for confirmation (see below) |

## Application paths

Settings > Application shortcuts lets you set a full path to `chrome.exe`, `Code.exe`, `calc.exe`, `notepad.exe` and `Telegram.exe`. Blank means auto-detect common install locations. Only existing `.exe` files are accepted, and only the allowlisted apps and locations above can ever be launched.

The dashboard opens in a black, green and red theme by default. A light theme is available from the toggle in the top bar (remembered in your browser). Colors live as CSS variables at the top of `static/css/style.css`, so you can change the palette in one place.

## Shutdown confirmation

1. A shutdown command only opens a confirmation dialog. Nothing is shut down yet.
2. Click **Confirm Shutdown** within 60 seconds. The server checks a single-use token tied to your session.
3. Windows then shuts down after 30 seconds. Click **Abort shutdown** during that time (runs `shutdown /a`).
4. **Cancel** or Esc dismisses the request.

## Security notes

- Fixed allowlist of intents; no recognised text is ever passed to a shell (`subprocess` gets an argument list, never `shell=True`).
- All action endpoints are POST + CSRF protected, and answer only requests from `127.0.0.1` / `::1`.
- `ALLOWED_HOSTS` is limited to localhost. Do not run with `runserver 0.0.0.0:8000`.
- This is a development configuration (`DEBUG=True`, fixed `SECRET_KEY`). Change the key before any other use.

## Hero effect

The banner at the top of the dashboard is drawn by `static/js/fx.js` (plain canvas, no libraries): a pixel-grid star with a travelling wave and a dotted red curve with a moving green dot. It speeds up while JARVIS is listening, ripples on success or error, follows your pointer, pauses when scrolled out of view, and shows a still image if Windows has "Show animations" turned off. Edit `CELL` and `DOTS` at the top of the file to change its density.

## Packaging later

The project has no OS-specific imports outside `assistant/services/desktop_control.py`, so it works with PyInstaller (include `templates/` and `static/` as data files).

## Layout

`config/` settings and URLs, `assistant/` models, views, forms, tests, `assistant/services/` (command_handler, desktop_control, speech_service), `templates/`, `static/`.
