# Aka's AutoClicker

> Cracktro-style autoclicker for Windows. Hold any mouse button to rapid fire clicks.

---

## Features

- Hold any mouse button → sends clicks as fast as configured
- Adjustable interval (1ms – 500ms) with quick presets
- **F6** global hotkey to toggle on/off
- Always-on-top toggle
- Minimizes to system tray
- Boot with Windows option
- No titlebar — draggable from the header area

---

## Requirements

- Windows 10 / 11
- Python 3.8+

---

## Run from source

```bash
pip install pynput pystray pillow
python autoclicker.py
```

---

## Compile to .exe

```bash
pip install pyinstaller
python -m PyInstaller --onefile --windowed --name "AkasAutoClicker" autoclicker.py
```

The executable will be generated in the `dist/` folder.

> **Note:** If you move the `.exe` after enabling *Boot with Windows*, uncheck and re-check the option so the registry path updates.

---

## Usage

| Action | How |
|---|---|
| Toggle autoclicker | **F6** or the ACTIVATE button |
| Use autoclicker | Hold any mouse button while active |
| Change speed | Drag the slider or use the presets |
| Always on top | ONTOP toggle in the header |
| Boot with Windows | Check the option in the UI |
| Minimize to tray | Close the window (X minimizes to tray) |
| Quit completely | Right-click tray icon → Salir |

---

## Version History

| Version | Changes |
|---|---|
| **v6** | Hold delay configurable — tiempo de espera antes de activar el autoclick, permite clicks normales sin interferencia |
| **v1** | Primera versión. UI básica, slider de intervalo, inicio automático con Windows |