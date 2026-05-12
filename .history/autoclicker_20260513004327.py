"""
Aka's AutoClicker

Dependencias:   pip install pynput pystray pillow
Ejecutar:       python autoclicker.py
EXE:            pip install pyinstaller
                python -m PyInstaller --onefile --windowed --name "AkasAutoClicker" autoclicker
"""

import tkinter as tk
import threading
import time
import sys, os, math, random
import winreg
import ctypes

def _pip(pkg):
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

try:
    from pynput import mouse as pmouse, keyboard as pkeyboard
except ImportError:
    _pip("pynput")
    from pynput import mouse as pmouse, keyboard as pkeyboard

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    _pip("pystray"); _pip("pillow")
    import pystray
    from PIL import Image, ImageDraw

# ── ctypes mouse_event ────────────────────────────────────────────────────────
_u32 = ctypes.windll.user32
MOUSEEVENTF_LEFTDOWN   = 0x0002; MOUSEEVENTF_LEFTUP     = 0x0004
MOUSEEVENTF_RIGHTDOWN  = 0x0008; MOUSEEVENTF_RIGHTUP    = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020; MOUSEEVENTF_MIDDLEUP   = 0x0040
_DOWN = {"left":MOUSEEVENTF_LEFTDOWN, "right":MOUSEEVENTF_RIGHTDOWN, "middle":MOUSEEVENTF_MIDDLEDOWN}
_UP   = {"left":MOUSEEVENTF_LEFTUP,   "right":MOUSEEVENTF_RIGHTUP,   "middle":MOUSEEVENTF_MIDDLEUP}

def _send_click(button):
    _u32.mouse_event(_DOWN[button], 0, 0, 0, 0)
    time.sleep(0.002)
    _u32.mouse_event(_UP[button],   0, 0, 0, 0)

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
EXE_PATH = sys.executable if getattr(sys, 'frozen', False) else \
           f'"{sys.executable}" "{os.path.abspath(__file__)}"'

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

# ── Estado autoclicker ────────────────────────────────────────────────────────
class State:
    enabled        = False
    held_left      = False
    held_right     = False
    held_middle    = False
    interval_ms    = 50
    hold_delay_ms  = 300    # ms que hay que mantener antes de empezar
    _lock          = threading.Lock()
    _firing        = False

state = State()
_click_thread = None
_delay_timer  = None       # threading.Timer para el hold delay

def click_loop():
    while True:
        with state._lock:
            if not state.enabled: break
            buttons = []
            if state.held_left:   buttons.append("left")
            if state.held_right:  buttons.append("right")
            if state.held_middle: buttons.append("middle")
            if not buttons: break
            interval = state.interval_ms / 1000.0
            state._firing = True
        for btn in buttons:
            _send_click(btn)
        with state._lock:
            state._firing = False
        time.sleep(max(0.001, interval))

def _start_click_thread():
    """Arranca el hilo de clicks si el botón sigue pulsado tras el delay."""
    global _click_thread
    with state._lock:
        running = _click_thread and _click_thread.is_alive()
        should  = state.enabled and (state.held_left or state.held_right or state.held_middle)
    if should and not running:
        _click_thread = threading.Thread(target=click_loop, daemon=True)
        _click_thread.start()

def maybe_start_thread():
    """Espera hold_delay_ms y luego arranca si el botón sigue pulsado."""
    global _delay_timer
    if _delay_timer and _delay_timer.is_alive():
        _delay_timer.cancel()
    with state._lock:
        delay = state.hold_delay_ms / 1000.0
    if delay <= 0:
        _start_click_thread()
    else:
        _delay_timer = threading.Timer(delay, _start_click_thread)
        _delay_timer.daemon = True
        _delay_timer.start()

def _cancel_delay():
    global _delay_timer
    if _delay_timer and _delay_timer.is_alive():
        _delay_timer.cancel()

_BTN_ATTR = {
    pmouse.Button.left:   "held_left",
    pmouse.Button.right:  "held_right",
    pmouse.Button.middle: "held_middle",
}

def on_mouse_event(x, y, button, pressed):
    with state._lock:
        if state._firing: return
        attr = _BTN_ATTR.get(button)
        if attr: setattr(state, attr, pressed)
    if pressed:
        maybe_start_thread()
    else:
        _cancel_delay()  # soltaron antes del delay → click normal, no autoclick

mouse_listener = pmouse.Listener(on_click=on_mouse_event)
mouse_listener.start()

def on_key_press(key):
    if key == pkeyboard.Key.f6:
        app.after(0, app.toggle_enabled)

kb_listener = pkeyboard.Listener(on_press=on_key_press)
kb_listener.start()

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
    MSG = ("  *** AKA'S AUTOCLICKER v5.0 ***   "
           "HOLD ANY MOUSE BUTTON TO RAPID FIRE   "
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
    H = 480

    def __init__(self):
        super().__init__()
        self.title("Aka's AutoClicker")
        self.overrideredirect(True)
        self.resizable(False, False)
        self.geometry(f"{self.W}x{self.H}")
        self.configure(bg=BG)
        # borde exterior verde oscuro
        tk.Frame(self, bg=GREEN_DIM, bd=1).place(x=0,y=0,width=self.W,height=self.H)
        self._drag_x = 0
        self._drag_y = 0
        self._ontop  = False
        self._build()
        self._center()
        self._start_tray()

    def _build(self):
        # starfield de fondo
        StarField(self, self.W, self.H).place(x=0, y=0)

        # título graffiti con X y ONTOP integrados, arrancando en y=2
        gt = GraffitiTitle(
            self,
            on_close      = self._quit_app,
            on_ontop      = self._set_ontop,
            on_drag_start = self._drag_start,
            on_drag_move  = self._drag_move,
        )
        gt.place(x=0, y=2)

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
        for lbl,val in [("MAX",1),("50ms",50),("100ms",100),("250ms",250)]:
            tk.Button(pf, text=lbl, command=lambda v=val:self._set_interval(v),
                      font=("Courier New",8,"bold"), bg=GREY, fg=TEXT_MID,
                      activebackground=GREY2, activeforeground=GREEN,
                      relief="flat", bd=0, padx=8, pady=3,
                      cursor="hand2").pack(side="left", padx=(0,5))

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

        tk.Label(self, text="F6 = QUICK TOGGLE",
                 font=("Courier New",8), bg=BG, fg=TEXT_DIM).place(x=20, y=Y+306)

        make_sep(self, Y+324)
        Ticker(self).place(x=0, y=Y+332)

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
        except: pass
        self.after(0, self.destroy)

    # ── autoclicker ───────────────────────────────────────────────────────────
    def toggle_enabled(self):
        with state._lock:
            state.enabled = not state.enabled; on = state.enabled
        self._btn.set_active(on)
        self._status.config(
            text=">_ STATUS: ACTIVE — HOLD MOUSE BTN" if on else ">_ STATUS: STANDBY",
            fg=GREEN if on else TEXT_DIM)
        maybe_start_thread()

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

    def _center(self):
        self.update_idletasks()
        sw=self.winfo_screenwidth(); sh=self.winfo_screenheight()
        self.geometry(f"{self.W}x{self.H}+{(sw-self.W)//2}+{(sh-self.H)//2}")


app = App()
app.mainloop()
