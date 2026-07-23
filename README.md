# Aka's AutoClicker

> Cracktro-style autoclicker for Windows. Hold a mouse button to rapid fire, or lock hands-free autofire with a right-click.

---

## Features

- **Hold left / middle** mouse button → sends clicks as fast as configured
- **Right-click = lock** hands-free left-click autofire; **move the mouse to cancel**
- Configurable **hold delay** — wait time before autofire kicks in (lets normal clicks through)
- Adjustable click interval (1 ms – 500 ms) with quick presets (`MAX · 10ms · 50ms · 100ms · 250ms`)
- **F6** global hotkey to toggle on/off (native low-level hook — no external input library)
- Never acts on its **own window** — the UI stays fully usable while active
- Remembers everything on exit: sliders, ONTOP, taskbar, **window position** (multi-monitor aware)
- Optional **Show in taskbar** toggle
- **Single instance** — launching again just focuses the running one
- Always-on-top toggle
- Minimizes to system tray, with a matching window/taskbar icon
- Boot with Windows option
- No titlebar — draggable from the header area

---

## Requirements

- Windows 10 / 11
- Python 3.8+

---

## Run from source

```bash
pip install pystray pillow
python autoclicker.py
```

> Uses only Win32 (`ctypes`) for the mouse/keyboard hooks — no `pynput` needed.

---

## Compile to .exe

```bash
python -m PyInstaller --onefile --windowed --name "AkasAutoClicker" --icon icon.ico --distpath bin autoclicker.py
```

The executable is generated in the `bin/` folder. Build artifacts (`build/`, `*.spec`) can be deleted afterwards.

> **Note:** If you move the `.exe` after enabling *Boot with Windows*, uncheck and re-check the option so the registry path updates.

---

## Usage

| Action | How |
|---|---|
| Toggle autoclicker | **F6** or the ACTIVATE button |
| Rapid fire | Hold **left** or **middle** mouse button while active |
| Lock hands-free autofire | **Right-click** while active (fires left clicks) |
| Cancel the lock | Move the mouse |
| Change speed | Drag the slider or use the presets |
| Hold delay | Drag the HOLD DELAY slider or presets |
| Always on top | ONTOP toggle in the header |
| Show in taskbar | Check *SHOW IN TASKBAR* in the UI |
| Boot with Windows | Check the option in the UI |
| Minimize to tray | Close the window (X minimizes to tray) |
| Quit completely | Right-click tray icon → Salir |

> While **active**, the right mouse button is used as the lock toggle (its normal context click is suppressed). Turn the autoclicker off (F6) to use right-click normally.

---

## Version History

| Version | Changes |
|---|---|
| **v7** | Right-click lock (hands-free left autofire, cancel on mouse move) · F6 rewritten as a native low-level hook (dropped `pynput`) · autoclicker ignores its own window · persistent settings + window position (multi-monitor) · Show-in-taskbar option · single-instance enforcement · custom exe/window icon · 10 ms preset |
| **v6** | Hold delay configurable — tiempo de espera antes de activar el autoclick, permite clicks normales sin interferencia |
| **v1** | Primera versión. UI básica, slider de intervalo, inicio automático con Windows |
