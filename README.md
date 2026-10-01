<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/bel-mark-light-1024.png">
    <img src="assets/bel-mark-dark-1024.png" alt="Bel" width="120">
  </picture>
</p>

<h1 align="center">Bel</h1>

<p align="center">A Windows overlay: press a hotkey, pick a wedge, and get a todo list, a sticky note or a Claude chat floating above whatever you're doing.</p>

<p align="center">
  <a href="https://youtu.be/jrh_ZC58SSM">
    <img src="https://img.youtube.com/vi/jrh_ZC58SSM/maxresdefault.jpg" alt="Watch the Bel demo on YouTube" width="640">
  </a>
</p>

## Features

- **Pie menu** that opens around your cursor on a global hotkey. Wedges are editable from the Settings wedge.
- **Todo and Note cards**: small always-on-top cards that remember their contents between runs.
- **Chat with Claude** in a card that docks to the corners or edges of your screen, with streaming replies and follow-ups.
- **Chat commands** for your timetable, screenshots and screen OCR (see [Commands](#commands)).
- Runs from the system tray, and can start at logon.

## Requirements

- Windows 10 or 11
- Python 3.13 (only to run from source)
- [Claude Code](https://docs.claude.com/en/docs/claude-code) installed and logged in, so `claude` works in a terminal. The chat card runs it in the background.

## Install

1. Install [Claude Code](https://docs.claude.com/en/docs/claude-code) and log in, so `claude` works in a terminal.
2. Download `Bel-Setup-<version>.exe` from the [latest release](https://github.com/Marlve/bel/releases/latest) and run it.
3. Tick **Start Bel when I sign in to Windows** if you want it at logon, then finish the wizard. Bel launches and sits in the system tray.
4. Press **Ctrl+Shift+Space** to open the pie menu.

Windows may show a SmartScreen warning because the installer isn't code-signed. Choose **More info → Run anyway**. Bel checks for updates itself; to upgrade by hand, run the newer installer over the old one. It closes a running Bel first.

## Run from source

```powershell
git clone <this repo's url> bel
cd bel
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src\main.py
```

Press **Ctrl+Shift+Space**. The pie menu opens around your cursor; pick **Bel** to start chatting.

## Usage

### Hotkeys

| Keys | What it does |
| --- | --- |
| `Ctrl+Shift+Space` | Open or close the pie menu |
| `Ctrl+Alt+Space` | Put the keyboard back in the open chat |

Both can be changed in **Settings → Keys**: click a combo, then press the new one. A combo needs Ctrl, Shift or Alt with a letter or Space, or can be any F key.

> [!NOTE]
> Another app holding one of these combinations stops that hotkey from working. **Settings → Keys** shows which one is affected ("Another app has this combo"); pick a different combo there, or close the other app and press the same combo again.

Bel keeps to one instance. To quit it, right-click the tray icon and choose **Quit Bel**.

### Commands

Type these into the chat card's composer, or into the first message box that opens from the pie menu. Start a command with `!` and the rest of it shows dimmed; press **Tab** to fill it in (Tab again cycles when several match).

| Command | What it does |
| --- | --- |
| `! help` | List the commands |
| `! new` | Clear this chat and start a fresh conversation |
| `! today` / `! week` | Show what's on your timetable today or in the next 7 days |
| `! ss` | Drag over part of the screen; the crop is sent with your next message |
| `! read` | Drag over text on screen and it lands in the composer (offline OCR) |
| `! save` | File Bel's last reply into an Obsidian note (needs the vault, see below) |
| `? word` | Look a word or concept up in an Obsidian vault; without one, Bel just explains it |

### Calendar (optional)

`! today` and `! week` read a calendar's iCal link. Open **Settings** from the pie menu and paste the link into the **CALENDAR** field (a Google Calendar "secret address in iCal format" works). The field is masked because anyone with the link can read the calendar. Leave it empty if you don't need it; Bel can still work with a calendar through your own Claude account if you've connected one there.

### Obsidian vault

Open **Settings → Connect** and press **Browse** to choose your vault folder. Bel remembers it and reads it from then on (the first lookup after a change re-indexes it). A `6 Private` folder is never read, and can't be chosen as the vault.

Until you choose one there is no vault, and the vault features stay quiet: `? word` finds no notes and Bel answers it like a normal question, and `! save` has no notes to pick from. Nothing crashes, but nothing gets filed either. Everything else works without a vault.

## Build an exe or installer

```powershell
pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
```

This produces `dist\Bel\Bel.exe`. Quit Bel from the tray first, or the build stops with a message telling you to.

To build the installer, install [Inno Setup 6](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`) and run `scripts\build-installer.ps1`. It runs `build.ps1` and writes `dist\installer\Bel-Setup-<version>.exe`, with the version taken from `src\version.py`.

To start Bel at logon, run `scripts\install-autostart.ps1` once. `scripts\Stop Bel.bat`, `Start Bel.bat` and `Reset Bel.bat` are double-clickable helpers, and `scripts\Uninstall Bel.bat` removes the autostart entry.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Chat replies never arrive | Run `claude` in a terminal to check it's installed and logged in. |
| `! read` says there's no language pack | It reads Korean by default. Install the Korean language pack under Windows Settings > Time & language, or change `language` in `src/ocr.py`. |
| `! today` says no timetable link is set | Paste your calendar's iCal link into Settings, see [Calendar](#calendar-optional). |
| The hotkey does nothing | Another app has the combination, or another copy of Bel is running. Quit both and start Bel again. |

## Where Bel keeps its data

Everything lives under `%USERPROFILE%\.bel\`: card contents, wedge layout, the timetable link, and the chat's working folder. If a card ends up off-screen after a monitor change, run `scripts\Reset Bel.bat`. It moves the throwaway state aside into a backup folder and keeps your wedge layout and timetable link.

For the project's vocabulary, see [`CONTEXT.md`](CONTEXT.md).
