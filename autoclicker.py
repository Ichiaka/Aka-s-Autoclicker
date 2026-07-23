"""
Aka's AutoClicker

Dependencias:   pip install pystray pillow
Ejecutar:       python autoclicker.py
EXE:            pip install pyinstaller
                python -m PyInstaller --onefile --windowed --name "AkasAutoClicker" autoclicker.py
"""

import tkinter as tk
import threading
import time
import sys, os, math, random, json
import winreg
import ctypes

def _pip(pkg):
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

try:
    import pystray
    from PIL import Image, ImageDraw, ImageTk
except ImportError:
    _pip("pystray"); _pip("pillow")
    import pystray
    from PIL import Image, ImageDraw, ImageTk

# ── ctypes mouse_event ────────────────────────────────────────────────────────
from ctypes import wintypes

_u32 = ctypes.windll.user32
ULONG_PTR = ctypes.c_size_t
LRESULT   = ctypes.c_ssize_t

_u32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                             wintypes.DWORD, ULONG_PTR]
_u32.mouse_event.restype  = None

MOUSEEVENTF_LEFTDOWN   = 0x0002; MOUSEEVENTF_LEFTUP     = 0x0004
MOUSEEVENTF_RIGHTDOWN  = 0x0008; MOUSEEVENTF_RIGHTUP    = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020; MOUSEEVENTF_MIDDLEUP   = 0x0040
_DOWN = {"left":MOUSEEVENTF_LEFTDOWN, "right":MOUSEEVENTF_RIGHTDOWN, "middle":MOUSEEVENTF_MIDDLEDOWN}
_UP   = {"left":MOUSEEVENTF_LEFTUP,   "right":MOUSEEVENTF_RIGHTUP,   "middle":MOUSEEVENTF_MIDDLEUP}

# Firma para marcar nuestros propios clicks inyectados y así no auto-dispararnos.
INJECTED_SIGNATURE = 0xACC11CE5

def _send_click(button):
    _u32.mouse_event(_DOWN[button], 0, 0, 0, INJECTED_SIGNATURE)
    time.sleep(0.002)
    _u32.mouse_event(_UP[button],   0, 0, 0, INJECTED_SIGNATURE)

# ── Paleta ────────────────────────────────────────────────────────────────────
BG        = "#050505"
GREEN     = "#00ff88"
GREEN2    = "#00cc66"
GREEN_DIM = "#004422"
CYAN      = "#00ffff"
RED_AC    = "#ff3333"
GREY      = "#1a1a1a"
GREY2     = "#2a2a2a"
TEXT_DIM  = "#336644"
TEXT_MID  = "#559966"
WHITE     = "#e8ffe8"

# ── Registro ──────────────────────────────────────────────────────────────────
APP_NAME = "AkasAutoClicker"
REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
# En modo script usa pythonw.exe para no abrir una consola al arrancar con Windows.
_PYW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
_RUN = _PYW if os.path.exists(_PYW) else sys.executable
EXE_PATH = sys.executable if getattr(sys, 'frozen', False) else \
           f'"{_RUN}" "{os.path.abspath(__file__)}"'

def is_in_startup():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY)
        winreg.QueryValueEx(key, APP_NAME); winreg.CloseKey(key); return True
    except FileNotFoundError: return False

def add_to_startup():
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, EXE_PATH); winreg.CloseKey(key)

def remove_from_startup():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, APP_NAME); winreg.CloseKey(key)
    except FileNotFoundError: pass

# ── Configuración persistente ─────────────────────────────────────────────────
CONFIG_DIR  = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
CONFIG_DEFAULTS = {
    "interval_ms":   50,
    "hold_delay_ms": 300,
    "ontop":         False,
    "taskbar":       False,
    "win_x":         None,
    "win_y":         None,
}

def load_config():
    cfg = dict(CONFIG_DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k in CONFIG_DEFAULTS:
            if k in data:
                cfg[k] = data[k]
    except Exception:
        pass
    return cfg

def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

# ── Estado autoclicker ────────────────────────────────────────────────────────
class State:
    enabled        = False
    held_left      = False
    held_middle    = False
    locked         = False   # autoclick fijado (toggle con el botón derecho)
    interval_ms    = 50
    hold_delay_ms  = 300    # ms que hay que mantener antes de empezar
    _lock_x        = 0       # ancla para cancelar el lock al mover el ratón
    _lock_y        = 0
    _lock          = threading.Lock()

state = State()
_ctl_lock     = threading.Lock()   # protege _click_thread y _delay_timer
_click_thread = None
_delay_timer  = None       # threading.Timer para el hold delay

def click_loop():
    while True:
        with state._lock:
            if not state.enabled: break
            buttons = []
            if state.locked or state.held_left: buttons.append("left")
            if state.held_middle:               buttons.append("middle")
            if not buttons: break
            interval = state.interval_ms / 1000.0
        for btn in buttons:
            _send_click(btn)
        time.sleep(max(0.001, interval))

def _start_click_thread():
    """Arranca el hilo de clicks si el botón sigue pulsado tras el delay."""
    global _click_thread
    with state._lock:
        should = state.enabled and (state.locked or state.held_left or state.held_middle)
    with _ctl_lock:
        running = _click_thread and _click_thread.is_alive()
        if should and not running:
            _click_thread = threading.Thread(target=click_loop, daemon=True)
            _click_thread.start()

def maybe_start_thread():
    """Espera hold_delay_ms y luego arranca si el botón sigue pulsado."""
    global _delay_timer
    with state._lock:
        delay = state.hold_delay_ms / 1000.0
    if delay <= 0:
        with _ctl_lock:
            if _delay_timer and _delay_timer.is_alive():
                _delay_timer.cancel()
        _start_click_thread()
    else:
        with _ctl_lock:
            if _delay_timer and _delay_timer.is_alive():
                _delay_timer.cancel()
            _delay_timer = threading.Timer(delay, _start_click_thread)
            _delay_timer.daemon = True
            _delay_timer.start()

def _cancel_delay():
    global _delay_timer
    with _ctl_lock:
        if _delay_timer and _delay_timer.is_alive():
            _delay_timer.cancel()

# ── Hook de ratón de bajo nivel (WH_MOUSE_LL) ─────────────────────────────────
# Distingue los clicks reales de los que inyectamos nosotros (vía dwExtraInfo),
# de modo que el autoclicker nunca se dispara a sí mismo ni pierde la liberación
# del botón durante el disparo rápido.
WH_MOUSE_LL    = 14
WH_KEYBOARD_LL = 13
WM_MOUSEMOVE  = 0x0200
WM_LBUTTONDOWN=0x0201; WM_LBUTTONUP=0x0202
WM_RBUTTONDOWN=0x0204; WM_RBUTTONUP=0x0205
WM_MBUTTONDOWN=0x0207; WM_MBUTTONUP=0x0208
WM_KEYDOWN=0x0100; WM_KEYUP=0x0101; WM_SYSKEYDOWN=0x0104; WM_SYSKEYUP=0x0105
VK_F6 = 0x75

MOVE_CANCEL_PX = 8      # umbral de movimiento (px) que cancela el lock

# Solo izquierdo y central disparan por "mantener pulsado". El derecho es toggle.
_MOUSE_MSG = {
    WM_LBUTTONDOWN:("held_left",   True),  WM_LBUTTONUP:("held_left",   False),
    WM_MBUTTONDOWN:("held_middle", True),  WM_MBUTTONUP:("held_middle", False),
}

class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt",          wintypes.POINT),
                ("mouseData",   wintypes.DWORD),
                ("flags",       wintypes.DWORD),
                ("time",        wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]

# ── Detección "cursor sobre nuestra ventana" ──────────────────────────────────
# Para que el autoclicker no actúe sobre su propia interfaz aunque esté activo.
GA_ROOT = 2
_app_hwnd = None
_u32.GetWindowRect.argtypes   = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_u32.GetWindowRect.restype    = wintypes.BOOL
_u32.IsWindowVisible.argtypes = [wintypes.HWND]
_u32.IsWindowVisible.restype  = wintypes.BOOL
_u32.GetAncestor.argtypes     = [wintypes.HWND, wintypes.UINT]
_u32.GetAncestor.restype      = wintypes.HWND

# ── Estilos para mostrar/ocultar en la barra de tareas ────────────────────────
GWL_EXSTYLE      = -20
WS_EX_TOOLWINDOW = 0x00000080   # oculta de la barra de tareas
WS_EX_APPWINDOW  = 0x00040000   # fuerza botón en la barra de tareas
SW_HIDE = 0; SW_SHOW = 5
try:
    _GetWL = _u32.GetWindowLongPtrW; _SetWL = _u32.SetWindowLongPtrW
except AttributeError:                              # Python de 32 bits
    _GetWL = _u32.GetWindowLongW;    _SetWL = _u32.SetWindowLongW
_GetWL.restype  = ctypes.c_ssize_t
_GetWL.argtypes = [wintypes.HWND, ctypes.c_int]
_SetWL.restype  = ctypes.c_ssize_t
_SetWL.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
_u32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_u32.ShowWindow.restype  = wintypes.BOOL

# métricas del escritorio virtual (abarca todos los monitores)
SM_XVIRTUALSCREEN=76; SM_YVIRTUALSCREEN=77; SM_CXVIRTUALSCREEN=78; SM_CYVIRTUALSCREEN=79
_u32.GetSystemMetrics.argtypes = [ctypes.c_int]
_u32.GetSystemMetrics.restype  = ctypes.c_int

def _over_own_window(x, y):
    hwnd = _app_hwnd
    if not hwnd or not _u32.IsWindowVisible(hwnd):
        return False
    rect = wintypes.RECT()
    if not _u32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    return rect.left <= x < rect.right and rect.top <= y < rect.bottom

def _handle_mouse(attr, pressed):
    with state._lock:
        setattr(state, attr, pressed)
    if pressed:
        maybe_start_thread()
    else:
        _cancel_delay()   # soltaron antes del delay → click normal, no autoclick

def _reflect_lock(on):
    if app is not None:
        app.after(0, app._reflect_lock, on)

def _toggle_lock(x, y):
    """Botón derecho: fija/quita el autoclick (clicks izquierdos en bucle)."""
    with state._lock:
        if not state.enabled:
            return
        state.locked  = not state.locked
        state._lock_x = x
        state._lock_y = y
        now_locked = state.locked
    if now_locked:
        _start_click_thread()          # arranca ya, sin hold-delay
    _reflect_lock(now_locked)

def _on_mouse_move(x, y):
    """Cualquier movimiento real más allá del umbral cancela el lock."""
    with state._lock:
        if not state.locked:
            return
        dx = x - state._lock_x; dy = y - state._lock_y
        if dx*dx + dy*dy < MOVE_CANCEL_PX*MOVE_CANCEL_PX:
            return
        state.locked = False
    _reflect_lock(False)

HOOKPROC = ctypes.CFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, ctypes.c_void_p)

def _ll_mouse_proc(nCode, wParam, lParam):
    try:
        if nCode == 0 and lParam:                       # HC_ACTION
            ms = MSLLHOOKSTRUCT.from_address(lParam)
            if ms.dwExtraInfo != INJECTED_SIGNATURE:    # ignora nuestros propios clicks
                if wParam == WM_MOUSEMOVE:
                    _on_mouse_move(ms.pt.x, ms.pt.y)
                elif _over_own_window(ms.pt.x, ms.pt.y):
                    pass                # sobre nuestra ventana → no autoclicar, UI normal
                elif wParam in (WM_RBUTTONDOWN, WM_RBUTTONUP):
                    with state._lock:
                        enabled = state.enabled
                    if enabled:
                        if wParam == WM_RBUTTONDOWN:
                            _toggle_lock(ms.pt.x, ms.pt.y)
                        return 1        # bloquea el click derecho real mientras está activo
                else:
                    info = _MOUSE_MSG.get(wParam)
                    if info:
                        _handle_mouse(*info)
    except Exception:
        pass
    return _u32.CallNextHookEx(None, nCode, wParam, lParam)

_ll_mouse_proc_c = HOOKPROC(_ll_mouse_proc)   # referencia viva para evitar el GC
_u32.SetWindowsHookExW.restype  = wintypes.HHOOK
_u32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
_u32.CallNextHookEx.restype     = LRESULT
_u32.CallNextHookEx.argtypes    = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, ctypes.c_void_p]

# ── Hook de teclado de bajo nivel (WH_KEYBOARD_LL) — F6 = toggle ──────────────
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode",      wintypes.DWORD),
                ("scanCode",    wintypes.DWORD),
                ("flags",       wintypes.DWORD),
                ("time",        wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]

_f6_down = False

def _ll_kbd_proc(nCode, wParam, lParam):
    global _f6_down
    try:
        if nCode == 0 and lParam:
            kb = KBDLLHOOKSTRUCT.from_address(lParam)
            if kb.vkCode == VK_F6:
                if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    if not _f6_down:            # ignora la auto-repetición
                        _f6_down = True
                        if app is not None:
                            app.after(0, app.toggle_enabled)
                elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                    _f6_down = False
    except Exception:
        pass
    return _u32.CallNextHookEx(None, nCode, wParam, lParam)

_ll_kbd_proc_c = HOOKPROC(_ll_kbd_proc)   # referencia viva para evitar el GC

def _hook_thread():
    _u32.SetWindowsHookExW(WH_MOUSE_LL,    _ll_mouse_proc_c, None, 0)
    _u32.SetWindowsHookExW(WH_KEYBOARD_LL, _ll_kbd_proc_c,   None, 0)
    msg = wintypes.MSG()
    while _u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        _u32.TranslateMessage(ctypes.byref(msg))
        _u32.DispatchMessageW(ctypes.byref(msg))

def _start_input_listeners():
    global _app_hwnd
    try:
        _app_hwnd = _u32.GetAncestor(app.winfo_id(), GA_ROOT)
    except Exception:
        _app_hwnd = None
    threading.Thread(target=_hook_thread, daemon=True).start()

# ── Tray icon ─────────────────────────────────────────────────────────────────
def _make_tray_icon():
    img  = Image.new("RGBA", (64, 64), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    pts  = [(16,2),(48,2),(62,16),(62,48),(48,62),(16,62),(2,48),(2,16)]
    draw.polygon(pts, fill=(5,5,5,255), outline=(0,255,136,255))
    draw.polygon([(32,10),(44,50),(40,50),(36,36),(28,36),(24,50),(20,50)],
                 fill=(0,255,136,255))
    draw.rectangle([27,28,37,33], fill=(5,5,5,255))
    return img

# ── Widgets ───────────────────────────────────────────────────────────────────

class StarField(tk.Canvas):
    def __init__(self, parent, w, h):
        super().__init__(parent, width=w, height=h, bg=BG, highlightthickness=0)
        self._stars = []
        for _ in range(26):
            x=random.randint(0,w); y=random.randint(0,h)
            r=random.choice([1,1,2]); sp=random.uniform(0.3,1.2)
            col=random.choice([GREEN,CYAN,GREEN2,TEXT_MID])
            dot=self.create_oval(x-r,y-r,x+r,y+r,fill=col,outline="")
            self._stars.append({"id":dot,"sp":sp,"t":random.randint(0,60),"r":r})
        self._anim()
    def _anim(self):
        for s in self._stars:
            s["t"]+=1
            bright=abs(math.sin(s["t"]*s["sp"]*0.08))>0.6
            self.itemconfig(s["id"],fill=(GREEN if s["r"]>1 else CYAN) if bright else GREEN_DIM)
        self.after(80,self._anim)


class GraffitiTitle(tk.Canvas):
    """
    Título graffiti + botón X (esquina superior derecha del logo)
    + toggle ONTOP — todo integrado en el mismo canvas.
    El canvas completo es arrastrable.
    """
    W, H = 320, 92

    def __init__(self, parent, on_close, on_ontop, on_drag_start, on_drag_move):
        super().__init__(parent, width=self.W, height=self.H,
                         bg=BG, highlightthickness=0, cursor="fleur")
        self._t        = 0
        self._on_close = on_close
        self._ontop_cb = on_ontop
        self._ontop    = False

        self._draw()

        # drag desde cualquier parte del canvas (excepto los botones)
        self.bind("<ButtonPress-1>",  on_drag_start)
        self.bind("<B1-Motion>",      on_drag_move)
        self._animate()

    def _draw(self):
        # glow difuso
        for r,col in [(44,"#001a0a"),(32,"#002e12"),(20,"#004422"),(12,"#005530")]:
            self.create_oval(160-r*2,45-r,160+r*2,45+r,fill=col,outline="")

        # "Aka's" con capas
        for dx,dy,col in [(3,3,GREEN_DIM),(2,2,"#008844"),(0,0,GREEN)]:
            self.create_text(82+dx,34+dy,text="Aka's",
                             font=("Impact",26,"bold"),fill=col,anchor="center")
        # "AutoClicker" con capas
        for dx,dy,col in [(3,3,GREEN_DIM),(2,2,"#008844"),(0,0,GREEN)]:
            self.create_text(175+dx,65+dy,text="AutoClicker",
                             font=("Impact",22,"bold"),fill=col,anchor="center")

        # subrayado irregular
        self.create_line(18,43,30,46,58,44,102,46,142,43,148,45,
                         fill=CYAN,width=2,smooth=True)
        # flecha izquierda
        self.create_polygon(8,32,16,26,16,30,28,30,28,34,16,34,16,38,
                            fill=CYAN,outline="")
        # estrellas
        for cx,cy,r,col in [(14,72,3,GREEN2)]:
            pts=[]
            for i in range(10):
                a=math.pi/2+i*2*math.pi/10; rad=r if i%2==0 else r*0.45
                pts.extend([cx+rad*math.cos(a),cy-rad*math.sin(a)])
            self.create_polygon(pts,fill=col,outline="")

        # tag autor
        self.create_text(308,84,text="by Aka",font=("Courier New",7),
                         fill=TEXT_DIM,anchor="e")
        # línea superior
        self.create_line(0,2,self.W,2,fill=GREEN_DIM,width=1)

        # glow pulsante
        self._glow1=self.create_text(82,34,text="Aka's",
                                     font=("Impact",26,"bold"),
                                     fill=WHITE,anchor="center",state="hidden")
        self._glow2=self.create_text(175,65,text="AutoClicker",
                                     font=("Impact",22,"bold"),
                                     fill=WHITE,anchor="center",state="hidden")

        # ── Botón X — esquina superior derecha del logo ────────────────────
        # Fondo del botón X
        S = 22
        X0, Y0 = self.W - S - 4, 4        # posición esquina superior derecha
        self._x_bg = self.create_rectangle(X0, Y0, X0+S, Y0+S,
                                           fill=BG, outline=GREEN_DIM, width=1,
                                           tags="xbtn")
        p = 5
        self._x_l1 = self.create_line(X0+p, Y0+p, X0+S-p, Y0+S-p,
                                      fill=RED_AC, width=2, tags="xbtn")
        self._x_l2 = self.create_line(X0+p, Y0+S-p, X0+S-p, Y0+p,
                                      fill=RED_AC, width=2, tags="xbtn")

        self.tag_bind("xbtn", "<Enter>",
                      lambda e: self.itemconfig(self._x_bg,
                                                fill="#1a0000", outline=RED_AC))
        self.tag_bind("xbtn", "<Leave>",
                      lambda e: self.itemconfig(self._x_bg,
                                                fill=BG, outline=GREEN_DIM))
        self.tag_bind("xbtn", "<ButtonRelease-1>",
                      lambda e: self._on_close())
        # Evitar que el clic en X dispare el drag
        self.tag_bind("xbtn", "<ButtonPress-1>",  lambda e: "break")
        self.tag_bind("xbtn", "<B1-Motion>",       lambda e: "break")

        # ── Toggle ONTOP — junto a la X ────────────────────────────────────
        TX = X0 - 50
        self.create_text(TX - 2, Y0 + 11,
                         text="ONTOP", font=("Courier New", 7),
                         fill=TEXT_DIM, anchor="e", tags="ontop_lbl")
        # track
        TW, TH = 34, 18
        self._ot_bg = self.create_rectangle(TX, Y0+2, TX+TW, Y0+2+TH,
                                            fill=GREY2, outline=GREEN_DIM,
                                            width=1, tags="ontop")
        # knob
        self._ot_kn = self.create_oval(TX+1, Y0+3, TX+TH-1, Y0+3+TH-2,
                                       fill=GREEN_DIM, outline=GREEN_DIM,
                                       tags="ontop")
        self.tag_bind("ontop", "<ButtonRelease-1>", self._toggle_ontop)
        self.tag_bind("ontop", "<ButtonPress-1>",   lambda e: "break")
        self.tag_bind("ontop", "<B1-Motion>",        lambda e: "break")
        self.tag_bind("ontop_lbl", "<ButtonRelease-1>", self._toggle_ontop)

        # guardar coords para animar knob
        self._ot_tx = TX
        self._ot_y0 = Y0
        self._ot_tw = TW
        self._ot_th = TH

    def set_ontop(self, on):
        if bool(on) != self._ontop:
            self._toggle_ontop()

    def _toggle_ontop(self, e=None):
        self._ontop = not self._ontop
        TX = self._ot_tx; Y0 = self._ot_y0; TH = self._ot_th; TW = self._ot_tw
        if self._ontop:
            self.coords(self._ot_kn, TX+TW-TH+1, Y0+3, TX+TW-1, Y0+3+TH-2)
            self.itemconfig(self._ot_bg, fill=GREEN_DIM, outline=GREEN)
            self.itemconfig(self._ot_kn, fill=GREEN, outline=GREEN)
        else:
            self.coords(self._ot_kn, TX+1, Y0+3, TX+TH-1, Y0+3+TH-2)
            self.itemconfig(self._ot_bg, fill=GREY2, outline=GREEN_DIM)
            self.itemconfig(self._ot_kn, fill=GREEN_DIM, outline=GREEN_DIM)
        self._ontop_cb(self._ontop)

    def _animate(self):
        self._t += 1
        s = "normal" if abs(math.sin(self._t*0.04)) > 0.97 else "hidden"
        self.itemconfig(self._glow1, state=s)
        self.itemconfig(self._glow2, state=s)
        self.after(40, self._animate)


class Ticker(tk.Canvas):
    MSG = ("  *** AKA'S AUTOCLICKER v6.0 ***   "
           "HOLD LEFT/MIDDLE TO RAPID FIRE   "
           "RIGHT-CLICK = LOCK AUTOFIRE — MOVE MOUSE TO CANCEL   "
           "F6 = TOGGLE ON/OFF   "
           "GREETINGS TO: THE SCENE, OLD SCHOOL CODERS, DEMO LOVERS   "
           "THIS TOOL IS 100% FREE   "
           "CODED WITH LOVE AND CAFFEINE   ")
    W = 320
    def __init__(self, parent):
        super().__init__(parent,width=self.W,height=22,bg="#001108",highlightthickness=0)
        self._x=self.W; self._id=None; self.after(10,self._init_text)
    def _init_text(self):
        self._id=self.create_text(self._x,11,text=self.MSG*3,
                                  font=("Courier New",9,"bold"),fill=GREEN,anchor="w")
        self._scroll()
    def _scroll(self):
        if not self._id: self.after(30,self._scroll); return
        self._x-=2
        bbox=self.bbox(self._id)
        if bbox and bbox[2]<0: self._x=self.W
        self.coords(self._id,self._x,11); self.after(30,self._scroll)


class CrackButton(tk.Canvas):
    W,H=280,44
    def __init__(self,parent,text,command,active_text=None,active_fg=None):
        super().__init__(parent,width=self.W,height=self.H,bg=BG,
                         highlightthickness=0,cursor="hand2")
        self._text=text; self._act_text=active_text or text
        self._act_fg=active_fg or RED_AC; self._active=False; self._cmd=command; self._t=0
        self._bg=self.create_polygon(6,0,self.W-6,0,self.W,6,self.W,self.H-6,
            self.W-6,self.H,6,self.H,0,self.H-6,0,6,fill=GREEN_DIM,outline=GREEN,width=1)
        self._inner=self.create_polygon(8,2,self.W-8,2,self.W-2,8,self.W-2,self.H-8,
            self.W-8,self.H-2,8,self.H-2,2,self.H-8,2,8,fill="",outline=GREEN_DIM,width=1)
        for pts in [[0,0,12,0,0,12],[self.W,0,self.W-12,0,self.W,12],
                    [0,self.H,12,self.H,0,self.H-12],
                    [self.W,self.H,self.W-12,self.H,self.W,self.H-12]]:
            self.create_polygon(pts,fill=GREEN2,outline="")
        self._lbl=self.create_text(self.W//2,self.H//2,text=f"[ {text} ]",
                                   font=("Impact",13),fill=GREEN,anchor="center")
        self.bind("<ButtonPress-1>",  lambda e: self.move(self._lbl,1,1))
        self.bind("<ButtonRelease-1>",self._on_up)
        self.bind("<Enter>",lambda e: self.itemconfig(self._bg,
            outline=CYAN if not self._active else RED_AC))
        self.bind("<Leave>",lambda e: self.itemconfig(self._bg,
            outline=GREEN if not self._active else RED_AC))
        self._anim()
    def _on_up(self,e): self.move(self._lbl,-1,-1); self._cmd()
    def set_active(self,on):
        self._active=on
        if on:
            self.itemconfig(self._bg,fill="#220000",outline=RED_AC)
            self.itemconfig(self._lbl,text=f"[ {self._act_text} ]",fill=self._act_fg)
        else:
            self.itemconfig(self._bg,fill=GREEN_DIM,outline=GREEN)
            self.itemconfig(self._lbl,text=f"[ {self._text} ]",fill=GREEN)
    def _anim(self):
        self._t+=1
        if not self._active:
            self.itemconfig(self._inner,
                outline=GREEN2 if abs(math.sin(self._t*0.05))>0.9 else GREEN_DIM)
        self.after(50,self._anim)


class CrackSlider(tk.Canvas):
    W,H=280,28; TX0=8; TX1=272; TY=14
    def __init__(self,parent,from_,to,value,command):
        super().__init__(parent,width=self.W,height=self.H,bg=BG,
                         highlightthickness=0,cursor="hand2")
        self._from=from_; self._to=to; self._val=value; self._cmd=command
        self.create_line(self.TX0,self.TY,self.TX1,self.TY,fill=GREY2,width=3)
        for i in range(11):
            x=self.TX0+i*(self.TX1-self.TX0)//10; h=5 if i%5==0 else 3
            self.create_line(x,self.TY-h,x,self.TY+h,fill=GREEN_DIM,width=1)
        self._fill =self.create_line(self.TX0,self.TY,self.TX0,self.TY,fill=GREEN,width=3)
        self._thumb=self.create_polygon(0,-7,7,0,0,7,-7,0,fill=GREEN,outline=CYAN,width=1)
        self._update()
        self.bind("<ButtonPress-1>",self._press); self.bind("<B1-Motion>",self._drag)
    def _v2x(self,v): return self.TX0+(v-self._from)/(self._to-self._from)*(self.TX1-self.TX0)
    def _x2v(self,x):
        r=(x-self.TX0)/(self.TX1-self.TX0)
        return max(self._from,min(self._to,int(self._from+r*(self._to-self._from))))
    def _update(self):
        x=self._v2x(self._val)
        self.coords(self._fill,self.TX0,self.TY,x,self.TY)
        self.coords(self._thumb,x,self.TY-7,x+7,self.TY,x,self.TY+7,x-7,self.TY)
    def _press(self,e): self._val=self._x2v(e.x); self._update(); self._cmd(self._val)
    def _drag(self,e):  self._val=self._x2v(e.x); self._update(); self._cmd(self._val)
    def set(self,v): self._val=max(self._from,min(self._to,int(v))); self._update()


def make_sep(parent,y,width=320):
    c=tk.Canvas(parent,width=width,height=8,bg=BG,highlightthickness=0)
    c.place(x=0,y=y)
    c.create_line(0,4,width,4,fill=GREEN_DIM,width=1)
    c.create_rectangle(width//2-4,1,width//2+4,7,fill=GREEN2,outline="")


# ── App ───────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    W = 320
    H = 504

    def __init__(self):
        super().__init__()
        self._cfg = load_config()
        with state._lock:
            state.interval_ms   = self._cfg["interval_ms"]
            state.hold_delay_ms = self._cfg["hold_delay_ms"]
        self.title("Aka's AutoClicker")
        self.overrideredirect(True)
        self.resizable(False, False)
        self.geometry(f"{self.W}x{self.H}")
        self.configure(bg=BG)
        # icono de ventana (barra de tareas / Alt-Tab) igual que el del tray
        try:
            self._icon_img = ImageTk.PhotoImage(_make_tray_icon())
            self.iconphoto(True, self._icon_img)
        except Exception:
            pass
        # borde exterior verde oscuro
        tk.Frame(self, bg=GREEN_DIM, bd=1).place(x=0,y=0,width=self.W,height=self.H)
        self._drag_x = 0
        self._drag_y = 0
        self._ontop  = False
        self._build()
        self._apply_saved_toggles()   # ontop/taskbar primero…
        self._place_window()          # …y la posición al final, para que no la muevan
        self._start_tray()

    def _apply_saved_toggles(self):
        if self._cfg.get("ontop"):
            self._gt.set_ontop(True)
        if self._cfg.get("taskbar"):
            self._set_taskbar(True)

    def _build(self):
        # starfield de fondo
        StarField(self, self.W, self.H).place(x=0, y=0)

        # título graffiti con X y ONTOP integrados, arrancando en y=2
        self._gt = GraffitiTitle(
            self,
            on_close      = self._quit_app,
            on_ontop      = self._set_ontop,
            on_drag_start = self._drag_start,
            on_drag_move  = self._drag_move,
        )
        self._gt.place(x=0, y=2)

        Y = 94   # justo debajo del título

        make_sep(self, Y)

        # ── hold delay ────────────────────────────────────────────────────────
        hf = tk.Frame(self, bg=BG)
        hf.place(x=20, y=Y+10)
        tk.Label(hf, text=":: HOLD DELAY ::",
                 font=("Courier New",8,"bold"), bg=BG, fg=TEXT_MID).pack(side="left")
        self._hd_lbl = tk.Label(hf, text=f"[ {state.hold_delay_ms} ms ]",
                                font=("Courier New",8,"bold"), bg=BG, fg=CYAN)
        self._hd_lbl.pack(side="left", padx=8)

        self._hd_slider = CrackSlider(self, 0, 1000, state.hold_delay_ms, self._on_hd_slider)
        self._hd_slider.place(x=20, y=Y+28)

        hpf = tk.Frame(self, bg=BG)
        hpf.place(x=20, y=Y+62)
        for lbl,val in [("0ms",0),("100ms",100),("300ms",300),("500ms",500)]:
            tk.Button(hpf, text=lbl, command=lambda v=val: self._set_hd(v),
                      font=("Courier New",8,"bold"), bg=GREY, fg=TEXT_MID,
                      activebackground=GREY2, activeforeground=GREEN,
                      relief="flat", bd=0, padx=8, pady=3,
                      cursor="hand2").pack(side="left", padx=(0,5))

        make_sep(self, Y+90)

        # ── click interval ────────────────────────────────────────────────────
        rf = tk.Frame(self, bg=BG)
        rf.place(x=20, y=Y+100)
        tk.Label(rf, text=":: CLICK INTERVAL ::",
                 font=("Courier New",8,"bold"), bg=BG, fg=TEXT_MID).pack(side="left")
        self._ms_lbl = tk.Label(rf, text=f"[ {state.interval_ms} ms ]",
                                font=("Courier New",8,"bold"), bg=BG, fg=CYAN)
        self._ms_lbl.pack(side="left", padx=8)

        self._slider = CrackSlider(self, 1, 500, state.interval_ms, self._on_slider)
        self._slider.place(x=20, y=Y+118)

        pf = tk.Frame(self, bg=BG)
        pf.place(x=20, y=Y+152)
        for lbl,val in [("MAX",1),("10ms",10),("50ms",50),("100ms",100),("250ms",250)]:
            tk.Button(pf, text=lbl, command=lambda v=val:self._set_interval(v),
                      font=("Courier New",8,"bold"), bg=GREY, fg=TEXT_MID,
                      activebackground=GREY2, activeforeground=GREEN,
                      relief="flat", bd=0, padx=6, pady=3,
                      cursor="hand2").pack(side="left", padx=(0,4))

        make_sep(self, Y+180)

        self._btn = CrackButton(self, text="ACTIVATE",
                                command=self.toggle_enabled,
                                active_text="DEACTIVATE", active_fg=RED_AC)
        self._btn.place(x=20, y=Y+192)

        self._status = tk.Label(self, text=">_ STATUS: STANDBY",
                                font=("Courier New",9,"bold"), bg=BG, fg=TEXT_DIM)
        self._status.place(x=20, y=Y+246)

        make_sep(self, Y+264)

        cbf = tk.Frame(self, bg=BG)
        cbf.place(x=20, y=Y+276)
        self._startup_var = tk.BooleanVar(value=is_in_startup())
        tk.Checkbutton(cbf, text="  BOOT WITH WINDOWS",
                       variable=self._startup_var,
                       command=self._toggle_startup,
                       font=("Courier New",9,"bold"), bg=BG, fg=TEXT_MID,
                       selectcolor=GREEN_DIM, activebackground=BG,
                       activeforeground=GREEN, relief="flat",
                       cursor="hand2").pack(anchor="w")

        tbf = tk.Frame(self, bg=BG)
        tbf.place(x=20, y=Y+300)
        self._taskbar_var = tk.BooleanVar(value=self._cfg.get("taskbar", False))
        tk.Checkbutton(tbf, text="  SHOW IN TASKBAR",
                       variable=self._taskbar_var,
                       command=self._toggle_taskbar,
                       font=("Courier New",9,"bold"), bg=BG, fg=TEXT_MID,
                       selectcolor=GREEN_DIM, activebackground=BG,
                       activeforeground=GREEN, relief="flat",
                       cursor="hand2").pack(anchor="w")

        tk.Label(self, text="F6 = QUICK TOGGLE   ·   RIGHT-CLICK = LOCK",
                 font=("Courier New",8), bg=BG, fg=TEXT_DIM).place(x=20, y=Y+330)

        make_sep(self, Y+348)
        Ticker(self).place(x=0, y=Y+356)

    # ── drag ──────────────────────────────────────────────────────────────────
    def _drag_start(self, e):
        self._drag_x = e.x_root - self.winfo_x()
        self._drag_y = e.y_root - self.winfo_y()

    def _drag_move(self, e):
        self.geometry(f"+{e.x_root-self._drag_x}+{e.y_root-self._drag_y}")

    # ── ontop ─────────────────────────────────────────────────────────────────
    def _set_ontop(self, on):
        self._ontop = on
        self.attributes("-topmost", on)

    # ── barra de tareas ─────────────────────────────────────────────────────────
    def _set_taskbar(self, on):
        try:
            self.update_idletasks()
            hwnd  = _u32.GetAncestor(self.winfo_id(), GA_ROOT)
            x, y  = self.winfo_x(), self.winfo_y()   # preservar posición
            style = _GetWL(hwnd, GWL_EXSTYLE)
            if on:
                style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            else:
                style = (style & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
            _SetWL(hwnd, GWL_EXSTYLE, style)
            _u32.ShowWindow(hwnd, SW_HIDE)      # re-mostrar para refrescar la barra
            _u32.ShowWindow(hwnd, SW_SHOW)
            self.geometry(f"+{x}+{y}")          # restaurar posición tras el re-show
            self.attributes("-topmost", self._ontop)
        except Exception:
            pass

    def _toggle_taskbar(self):
        self._set_taskbar(self._taskbar_var.get())

    # ── tray ──────────────────────────────────────────────────────────────────
    def _start_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("Mostrar",   self._show_from_tray, default=True),
            pystray.MenuItem("Toggle F6", lambda i,it: self.after(0,self.toggle_enabled)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir",     self._quit_app),
        )
        self._tray = pystray.Icon("AkasAC", _make_tray_icon(),
                                  "Aka's AutoClicker", menu)
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _show_from_tray(self, icon=None, item=None):
        self.after(0, self._show_window)

    def _show_window(self):
        self.deiconify(); self.lift()
        self.attributes("-topmost", self._ontop)

    def iconify(self):
        self.withdraw()

    def _quit_app(self, icon=None, item=None):
        try: self._tray.stop()
        except Exception: pass
        self.after(0, self._shutdown)

    def _shutdown(self):
        self._save_current_config()
        self.destroy()

    def _save_current_config(self):
        with state._lock:
            interval = state.interval_ms
            hold     = state.hold_delay_ms
        try:
            x, y = self.winfo_x(), self.winfo_y()
        except Exception:
            x, y = self._cfg.get("win_x"), self._cfg.get("win_y")
        save_config({
            "interval_ms":   interval,
            "hold_delay_ms": hold,
            "ontop":         self._ontop,
            "taskbar":       bool(self._taskbar_var.get()),
            "win_x":         x,
            "win_y":         y,
        })

    # ── autoclicker ───────────────────────────────────────────────────────────
    def toggle_enabled(self):
        with state._lock:
            state.enabled = not state.enabled; on = state.enabled
            if not on: state.locked = False   # al desactivar, se suelta el lock
        self._btn.set_active(on)
        self._refresh_status()
        maybe_start_thread()

    def _refresh_status(self):
        with state._lock:
            on = state.enabled
        self._status.config(
            text=">_ STATUS: ACTIVE — HOLD / RIGHT-LOCK" if on else ">_ STATUS: STANDBY",
            fg=GREEN if on else TEXT_DIM)

    def _reflect_lock(self, on):
        if on:
            self._status.config(text=">_ STATUS: LOCKED — MOVE MOUSE TO CANCEL", fg=CYAN)
        else:
            self._refresh_status()

    def _on_hd_slider(self, val):
        v = int(val)
        with state._lock: state.hold_delay_ms = v
        self._hd_lbl.config(text=f"[ {v} ms ]")

    def _set_hd(self, val):
        self._hd_slider.set(val); self._on_hd_slider(val)

    def _on_slider(self, val):
        v = int(val)
        with state._lock: state.interval_ms = v
        self._ms_lbl.config(text=f"[ {v} ms ]")

    def _set_interval(self, val):
        self._slider.set(val); self._on_slider(val)

    def _toggle_startup(self):
        if self._startup_var.get(): add_to_startup()
        else: remove_from_startup()

    def _place_window(self):
        self.update_idletasks()
        x = self._cfg.get("win_x"); y = self._cfg.get("win_y")
        if x is None or y is None:                 # primera ejecución → centrar
            sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
            x = (sw - self.W)//2; y = (sh - self.H)//2
        else:                                      # clamp al escritorio virtual (multi-monitor)
            vx = _u32.GetSystemMetrics(SM_XVIRTUALSCREEN)
            vy = _u32.GetSystemMetrics(SM_YVIRTUALSCREEN)
            vw = _u32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            vh = _u32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
            x = max(vx, min(int(x), vx + vw - self.W))
            y = max(vy, min(int(y), vy + vh - self.H))
        self.geometry(f"{self.W}x{self.H}+{int(x)}+{int(y)}")


app = App()
_start_input_listeners()   # arranca hook de ratón + teclado con la app ya creada
app.mainloop()
