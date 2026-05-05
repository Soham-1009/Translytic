# Translytic — Live Video Player with Translated Captions + Video Preview
# Modernized UI: gradients, fullscreen-optimized layout, perfectly synced A/V
# -----------------------------------------------------------------------

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import time
import os
import glob
import subprocess
import sys
import warnings
import logging
import io
import shutil
import tempfile
import queue

warnings.filterwarnings("ignore")
logging.getLogger("moviepy").setLevel(logging.ERROR)

# ── DPI Awareness Fix (Windows) ─────────────────────────────
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ── Auto-install missing packages ───────────────────────────
REQUIRED_PACKAGES = [
    ("pygame",          "pygame"),
    ("opencv-python",   "cv2"),
    ("Pillow",          "PIL"),
    ("openai-whisper",  "whisper"),
    ("deep-translator", "deep_translator"),
    ("moviepy",         "moviepy"),
    ("tkinterdnd2",     "tkinterdnd2"),
    ("openai",          "openai"),
    ("gTTS",            "gtts"),
    ("pydub",           "pydub"),
]
for pkg, imp in REQUIRED_PACKAGES:
    try:
        __import__(imp)
    except ImportError:
        print(f"Installing {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

import pygame
import cv2
from PIL import Image, ImageTk, ImageDraw
import whisper
from deep_translator import GoogleTranslator
from moviepy import VideoFileClip
from tkinterdnd2 import DND_FILES, TkinterDnD
from gtts import gTTS
from pydub import AudioSegment

# ── FFmpeg availability check ────────────────────────────────
if not shutil.which("ffmpeg"):
    import tkinter as _tk
    _root = _tk.Tk(); _root.withdraw()
    messagebox.showerror("FFmpeg Required",
        "FFmpeg is not installed or not found in PATH.\n\n"
        "pydub and moviepy both require FFmpeg to work.\n"
        "Download it from: https://ffmpeg.org/download.html\n"
        "and make sure it is added to your system PATH.")
    _root.destroy()
    sys.exit(1)

# ── Optional OpenAI key for natural translations ─────────────
OPENAI_API_KEY = ""

# ── Colour palette ───────────────────────────────────────────
BG          = "#06060e"
SURFACE     = "#0e0e1a"
SURFACE2    = "#141422"
SURFACE3    = "#1c1c30"
SURFACE4    = "#26263e"
ACCENT      = "#7c6bf5"       # rich violet
ACCENT2     = "#b490ff"       # soft lilac
ACCENT_DIM  = "#3d2f8f"
ACCENT_GLOW = "#5b4cc9"       # subtle glow violet
CYAN        = "#22d3ee"       # teal/cyan secondary
CYAN_DIM    = "#0e4f5c"
GRAD_TOP    = "#160f30"       # header gradient top
GRAD_BTM    = "#0a0a14"       # header gradient bottom
CAP_BG      = "#080810"
TEXT        = "#eae6ff"
TEXT_MUTED  = "#504d6a"
TEXT_DIM    = "#706d88"
SUCCESS     = "#34d399"
ERROR       = "#fb7185"
WARN        = "#fbbf24"
GLOW        = "#6c5ce7"
BORDER      = "#2a2844"       # subtle card borders
BORDER_GLOW = "#3d35a0"       # accent glow border

FONT_TITLE  = ("Segoe UI Variable", 14, "bold")
FONT_BRAND  = ("Segoe UI Variable", 10)
FONT_UI     = ("Segoe UI",          11)
FONT_SMALL  = ("Segoe UI",          9)
FONT_MONO   = ("Cascadia Code",     9)
FONT_CAP    = ("Segoe UI Variable", 24, "bold")
FONT_TIME   = ("Segoe UI",          10)
FONT_LABEL  = ("Segoe UI Variable",  9)
FONT_BTN    = ("Segoe UI",          11)

VIDEO_W     = 1600
VIDEO_H     = 900

LANGUAGES = {
    "English":              "en",
    "Hindi":                "hi",
    "Marathi":              "mr",
    "Spanish":              "es",
    "French":               "fr",
    "German":               "de",
    "Japanese":             "ja",
    "Chinese (Simplified)": "zh-CN",
    "Arabic":               "ar",
    "Portuguese":           "pt",
}

# ── Gradient helpers ─────────────────────────────────────────

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def lerp_color(c1, c2, t):
    r = int(c1[0] + (c2[0] - c1[0]) * t)
    g = int(c1[1] + (c2[1] - c1[1]) * t)
    b = int(c1[2] + (c2[2] - c1[2]) * t)
    return f"#{r:02x}{g:02x}{b:02x}"

def draw_gradient_h(canvas, w, h, c1, c2):
    r1, r2 = hex_to_rgb(c1), hex_to_rgb(c2)
    steps = max(w, 1)
    for i in range(steps):
        col = lerp_color(r1, r2, i / steps)
        canvas.create_line(i, 0, i, h, fill=col)

def draw_gradient_v(canvas, w, h, c1, c2):
    r1, r2 = hex_to_rgb(c1), hex_to_rgb(c2)
    for i in range(h):
        col = lerp_color(r1, r2, i / max(h - 1, 1))
        canvas.create_line(0, i, w, i, fill=col)

def make_gradient_image(w, h, c1, c2, direction="vertical"):
    img = Image.new("RGB", (max(w, 1), max(h, 1)))
    draw = ImageDraw.Draw(img)
    r1, r2 = hex_to_rgb(c1), hex_to_rgb(c2)
    n = h if direction == "vertical" else w
    for i in range(n):
        t   = i / max(n - 1, 1)
        col = (
            int(r1[0] + (r2[0] - r1[0]) * t),
            int(r1[1] + (r2[1] - r1[1]) * t),
            int(r1[2] + (r2[2] - r1[2]) * t),
        )
        if direction == "vertical":
            draw.line([(0, i), (w, i)], fill=col)
        else:
            draw.line([(i, 0), (i, h)], fill=col)
    return img


# ── GradientFrame — a Frame with a vertical gradient bg ──────

class GradientFrame(tk.Canvas):
    def __init__(self, parent, c1, c2, **kwargs):
        super().__init__(parent, bd=0, highlightthickness=0, **kwargs)
        self._c1, self._c2 = c1, c2
        self._photo = None
        self.bind("<Configure>", self._redraw)

    def _redraw(self, event=None):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2 or h < 2:
            return
        img   = make_gradient_image(w, h, self._c1, self._c2)
        self._photo = ImageTk.PhotoImage(img)
        self.delete("bg")
        self.create_image(0, 0, anchor="nw", image=self._photo, tags="bg")
        self.tag_lower("bg")


# ── Utility functions ────────────────────────────────────────

def extract_audio(video_path, out="audio_temp.wav"):
    clip = VideoFileClip(video_path)
    try:
        if clip.audio is None:
            raise ValueError("This video does not have an audio track.")
        clip.audio.write_audiofile(out, logger=None)
    finally:
        clip.close()
    return out

_whisper_model = None

def transcribe(audio_path):
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = whisper.load_model("base")
    result = _whisper_model.transcribe(audio_path)
    segments = []
    for seg in result["segments"]:
        segments.append({
            "start":          seg["start"],
            "end":            seg["end"],
            "text":           seg["text"],
            "avg_logprob":    seg.get("avg_logprob", 0),
            "no_speech_prob": seg.get("no_speech_prob", 0),
            "confidence":     round(min(1.0, max(0.0, 1.0 + seg.get("avg_logprob", 0))) * 100, 1),
        })
    return segments

def translate_segments(segments, lang_code, lang_name, check_cancel=None):
    out = []
    if OPENAI_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            for seg in segments:
                if check_cancel and check_cancel():
                    raise InterruptedError("Cancelled")
                prompt = (f"Translate the following English text to casual, everyday, "
                          f"spoken {lang_name}. Keep it natural. Text: {seg['text']}")
                resp = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
                out.append({"start": seg["start"], "end": seg["end"],
                            "text": resp.choices[0].message.content.strip()})
            return out
        except InterruptedError:
            raise
        except Exception as e:
            print("OpenAI failed, falling back to Google Translate:", e)

    for seg in segments:
        if check_cancel and check_cancel():
            raise InterruptedError("Cancelled")
        try:
            txt = GoogleTranslator(source="auto", target=lang_code).translate(seg["text"])
        except Exception:
            txt = seg["text"]
        out.append({"start": seg["start"], "end": seg["end"], "text": txt.strip()})
    return out

def format_time(s):
    h, rem = divmod(int(s), 3600)
    m, sec = divmod(rem, 60)
    ms = int((s - int(s)) * 1000)
    return f"{h:02}:{m:02}:{sec:02},{ms:03}"

def to_srt(segments):
    out = ""
    for i, s in enumerate(segments):
        out += f"{i+1}\n{format_time(s['start'])} --> {format_time(s['end'])}\n{s['text']}\n\n"
    return out

def get_caption_at(segments, t):
    for s in segments:
        if s["start"] <= t <= s["end"]:
            return s["text"]
    return ""


def remove_file_silent(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def generate_tts_audio(segments, lang_code, duration, out_path, check_cancel=None):
    total_ms   = int(duration * 1000) + 500
    combined   = AudioSegment.silent(duration=total_ms)

    for i, seg in enumerate(segments):
        if check_cancel and check_cancel():
            raise InterruptedError("Cancelled")

        text = seg["text"].strip()
        if not text:
            continue

        try:
            tts = gTTS(text=text, lang=lang_code, slow=False)
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            buf.seek(0)
            clip = AudioSegment.from_file(buf, format="mp3")
        except Exception as e:
            print(f"TTS failed for segment {i}: {e}")
            continue

        start_ms = int(seg["start"] * 1000)
        seg_duration_ms = int((seg["end"] - seg["start"]) * 1000)
        if len(clip) > seg_duration_ms + 200:
            clip = clip[:seg_duration_ms + 200]

        if start_ms + len(clip) <= total_ms:
            combined = combined.overlay(clip, position=start_ms)

    combined.export(out_path, format="wav")
    return out_path


# ── Main Application ─────────────────────────────────────────

class CaptionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Translytic — Live Translated Player")
        self.root.geometry("1280x800")
        self.root.minsize(1024, 720)
        self.root.state("zoomed")
        self.root.configure(bg=BG)

        self.video_path         = None
        self.segments           = []
        self._busy              = False
        self._cancel_processing = False
        self._playing           = False
        self._paused            = False
        self._play_start_wall   = 0.0
        self._pause_offset      = 0.0
        self._duration          = 0.0
        self._audio_path        = None
        self._caption_job       = None
        self._cap               = None
        self._fps               = 30.0
        self._current_photo     = None
        self._last_cap_text     = None
        self._current_frame_idx = 0
        self._tts_audio_path    = None
        self._use_tts           = False
        self._display_fps       = 30       # cap display at 30fps regardless of video FPS
        self._tick_interval     = 33       # ms between display refreshes (1000/30)
        self._frame_queue       = queue.Queue(maxsize=2)  # decoded frames from bg thread
        self._decode_thread     = None
        self._decode_stop       = threading.Event()
        self._frame_image_id    = None     # reusable canvas image item id

        pygame.mixer.pre_init(44100, -16, 2, 1024)
        pygame.mixer.init()
        
        self._build_ui()
        self._setup_dnd()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        self._build_header()
        self._build_body()

    def _build_header(self):
        self.hdr = GradientFrame(self.root, GRAD_TOP, GRAD_BTM, height=54)
        self.hdr.grid(row=0, column=0, sticky="ew")

        # Accent glow line at the very top
        glow_line = tk.Frame(self.root, bg=ACCENT_GLOW, height=2)
        glow_line.grid(row=0, column=0, sticky="new")

        self.hdr.create_text(28, 20, anchor="w", text="◆", font=("Segoe UI", 18), fill=ACCENT)
        self.hdr.create_text(52, 18, anchor="w", text="Translytic", font=FONT_TITLE, fill=TEXT)
        self.hdr.create_text(52, 38, anchor="w", text="Live Translated Video Player", font=FONT_BRAND, fill=TEXT_MUTED)

    def _build_body(self):
        body = tk.Frame(self.root, bg=BG)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        self._build_controls(body)
        self._build_player(body)
        self._build_log(body)

    def _build_controls(self, parent):
        ctrl = tk.Frame(parent, bg=BG)
        ctrl.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ctrl.columnconfigure(1, weight=1)

        # ── File card ──
        fc = self._card(ctrl)
        fc.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        tk.Label(fc, text="🎥  VIDEO FILE", font=FONT_LABEL,
                 fg=CYAN, bg=SURFACE).grid(
            row=0, column=0, padx=(14, 10), pady=8, sticky="w")

        self.file_lbl = tk.Label(
            fc, text="No file selected",
            font=FONT_UI, fg=TEXT_MUTED,
            bg=SURFACE3, anchor="w", width=28,
            relief="flat", padx=8, pady=4)
        self.file_lbl.grid(row=0, column=1, padx=(0, 10), pady=6, sticky="w")

        self._btn(fc, "📂  Browse", self.pick_file, "secondary").grid(
            row=0, column=2, padx=(0, 6), pady=6)

        self.clear_btn = self._btn(fc, "✕", self._clear_video, "danger")
        self.clear_btn.grid(row=0, column=3, padx=(0, 10), pady=6)
        self.clear_btn.grid_remove()

        # ── Language card ──
        lc = self._card(ctrl)
        lc.grid(row=0, column=1, sticky="w", padx=(0, 10))

        tk.Label(lc, text="🌐  TRANSLATE TO", font=FONT_LABEL,
                 fg=CYAN, bg=SURFACE).grid(
            row=0, column=0, padx=(14, 10), pady=8, sticky="w")

        self.lang_var = tk.StringVar(value="Hindi")
        self._style_widgets()
        ttk.Combobox(
            lc, textvariable=self.lang_var,
            values=list(LANGUAGES.keys()),
            state="readonly", font=FONT_UI, width=20
        ).grid(row=0, column=1, padx=(0, 14), pady=6, sticky="w")

        # ── Action area ──
        action_frame = tk.Frame(ctrl, bg=BG)
        action_frame.grid(row=0, column=2, sticky="e")

        self.status_lbl = tk.Label(
            action_frame, text="● Ready",
            font=FONT_SMALL,
            fg=TEXT_MUTED, bg=BG)
        self.status_lbl.pack(side="left", padx=(0, 12))

        self.proc_btn = self._btn(
            action_frame, "⚡  Process & Play",
            self._start_processing, "primary")
        self.proc_btn.pack(side="left")

        self.cancel_btn = self._btn(
            action_frame, "⏹  Cancel",
            self._cancel_process, "danger")
        self.cancel_btn.pack_forget()

    def _build_player(self, parent):
        # Outer frame with accent glow border
        outer = tk.Frame(parent, bg=BORDER_GLOW, padx=1, pady=1)
        outer.grid(row=1, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        player_card = tk.Frame(outer, bg="#000000")
        player_card.grid(row=0, column=0, sticky="nsew")
        player_card.columnconfigure(0, weight=1)
        player_card.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(player_card, bg="#030308", width=VIDEO_W, height=VIDEO_H, highlightthickness=0, cursor="hand2")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", lambda e: self._toggle_play_pause())

        self._canvas_text = self.canvas.create_text(
            VIDEO_W // 2, VIDEO_H // 2,
            text="\u25b6  Drop a video here or click Browse",
            font=("Segoe UI Variable", 16), fill="#252540", justify="center"
        )

        self.canvas.bind("<Configure>", lambda e: self.canvas.coords(self._canvas_text, e.width / 2, e.height / 2), add="+")

        # Caption bar with gradient
        self._cap_bar_canvas = GradientFrame(player_card, "#08081a", "#040410", height=48)
        self._cap_bar_canvas.grid(row=1, column=0, sticky="ew")

        self._cap_text_item = self._cap_bar_canvas.create_text(
            0, 0, anchor="center", text="", font=FONT_CAP, fill="#ffffff", justify="center"
        )

        self._cap_bar_canvas.bind(
            "<Configure>",
            lambda e: self._cap_bar_canvas.coords(self._cap_text_item, e.width / 2, e.height / 2),
            add="+"
        )

        self._build_playback_bar(player_card)

    def _build_playback_bar(self, parent):
        pb_canvas = GradientFrame(parent, SURFACE, SURFACE2, height=60)
        pb_canvas.grid(row=2, column=0, sticky="ew")

        pb = tk.Frame(pb_canvas, bg=SURFACE)
        pb.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
        pb.columnconfigure(1, weight=1)

        btns = tk.Frame(pb, bg=SURFACE)
        btns.grid(row=0, column=0, padx=16, pady=12)

        self.play_pause_btn = self._btn(btns, "▶  Play", self._toggle_play_pause, "primary")
        self.stop_btn = self._btn(btns, "⏹  Stop", self._stop, "default")
        self.play_pause_btn.pack(side="left", padx=(0, 8))
        self.stop_btn.pack(side="left")

        seek_wrap = tk.Frame(pb, bg=SURFACE)
        seek_wrap.grid(row=0, column=1, sticky="ew", padx=16)
        seek_wrap.columnconfigure(0, weight=1)

        self.seek_var = tk.DoubleVar(value=0)
        self.seekbar = ttk.Scale(seek_wrap, from_=0, to=100, orient="horizontal", variable=self.seek_var, command=self._on_seek)
        self.seekbar.grid(row=0, column=0, sticky="ew", pady=(6, 2))

        time_row = tk.Frame(seek_wrap, bg=SURFACE)
        time_row.grid(row=1, column=0, sticky="ew")
        time_row.columnconfigure(0, weight=1)

        self.time_lbl = tk.Label(time_row, text="0:00 / 0:00", font=FONT_TIME, fg=TEXT_DIM, bg=SURFACE)
        self.time_lbl.grid(row=0, column=0, sticky="e")

        self.fps_lbl = tk.Label(time_row, text="", font=FONT_TIME, fg=TEXT_MUTED, bg=SURFACE)
        self.fps_lbl.grid(row=0, column=1, sticky="e", padx=(10, 0))

        right_btns = tk.Frame(pb, bg=SURFACE)
        right_btns.grid(row=0, column=2, padx=(0, 16), pady=12)

        self.tts_btn = self._btn(right_btns, "🔊  Original", self._toggle_audio_mode, "accent")
        self.tts_btn.config(state="disabled")
        self.tts_btn.pack(side="left", padx=(0, 8))

        self._btn(right_btns, "⬇  Export .srt", self._export_srt, "accent").pack(side="left")

    def _build_log(self, parent):
        sep = GradientFrame(parent, ACCENT_DIM, BG, height=2)
        sep.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        log_card = self._card(parent)
        log_card.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        log_card.columnconfigure(0, weight=1)

        log_hdr = tk.Frame(log_card, bg=SURFACE)
        log_hdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(8, 0))
        log_hdr.columnconfigure(0, weight=1)

        tk.Label(log_hdr, text="📋  ACTIVITY LOG", font=FONT_LABEL, fg=CYAN, bg=SURFACE).grid(row=0, column=0, sticky="w")

        self.progressbar = ttk.Progressbar(log_hdr, mode="indeterminate", length=200)
        self.progressbar.grid(row=0, column=1, sticky="e")

        self.prog_lbl = tk.Label(log_hdr, text="", font=FONT_SMALL, fg=ACCENT2, bg=SURFACE)
        self.prog_lbl.grid(row=0, column=2, sticky="e", padx=(10, 0))

        self.log_box = tk.Text(log_card, height=2, font=FONT_MONO, bg=SURFACE2, fg=TEXT_DIM,
                               relief="flat", bd=0, padx=14, pady=6, state="disabled",
                               insertbackground=ACCENT)
        self.log_box.grid(row=1, column=0, sticky="ew", padx=14, pady=(4, 8))

    def _card(self, parent):
        return tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)

    def _btn(self, parent, text, cmd, style="default"):
        styles = {
            "primary":   (ACCENT,     "#ffffff",  ACCENT_DIM,  "#ffffff"),
            "secondary": (SURFACE3,   TEXT_DIM,   SURFACE4,    TEXT),
            "accent":    (SURFACE3,   ACCENT2,    ACCENT_DIM,  "#ffffff"),
            "danger":    (SURFACE3,   ERROR,      "#3a1520",   ERROR),
            "default":   (SURFACE3,   TEXT_DIM,   SURFACE4,    TEXT),
        }
        bg, fg, hbg, hfg = styles.get(style, styles["default"])

        btn = tk.Button(
            parent, text=text, command=cmd, bg=bg, fg=fg,
            activebackground=hbg, activeforeground=hfg,
            disabledforeground=TEXT_MUTED,
            font=FONT_BTN, relief="flat", bd=0, padx=18, pady=6,
            cursor="hand2", highlightthickness=0
        )
        btn.bind("<Enter>", lambda e: btn.config(bg=hbg, fg=hfg))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg,  fg=fg))
        return btn

    def _style_widgets(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TCombobox",
            fieldbackground=SURFACE3, background=SURFACE3, foreground=TEXT,
            selectbackground=ACCENT, bordercolor=BORDER, arrowcolor=TEXT_DIM,
            relief="flat", padding=5)
        s.map("TCombobox",
            fieldbackground=[("readonly", SURFACE3)],
            foreground=[("readonly", TEXT)],
            background=[("readonly", SURFACE3)])
        s.configure("Horizontal.TScale",
            troughcolor=SURFACE4, background=ACCENT, sliderlength=16)
        s.configure("TProgressbar",
            troughcolor=SURFACE3, background=ACCENT, darkcolor=ACCENT,
            lightcolor=ACCENT2, bordercolor=SURFACE3)

    def _log(self, msg):
        self.root.after(0, lambda m=msg: self._append_log(m))

    def _append_log(self, msg):
        self.log_box.config(state="normal")
        self.log_box.insert(tk.END, msg + "\n")
        self.log_box.see(tk.END)
        self.log_box.config(state="disabled")

    def _set_status(self, msg, color=TEXT_MUTED):
        self.root.after(0, lambda: self.status_lbl.config(text=f"● {msg}", fg=color))

    def _set_prog(self, msg):
        self.root.after(0, lambda: self.prog_lbl.config(text=msg))

    def _busy_start(self):
        self._busy = True
        self._cancel_processing = False
        self.root.after(0, lambda: [
            self.proc_btn.pack_forget(),
            self.cancel_btn.pack(side="left"),
            self.progressbar.start(10),
        ])

    def _busy_stop(self):
        self._busy = False
        self.root.after(0, lambda: [
            self.cancel_btn.pack_forget(),
            self.proc_btn.pack(side="left"),
            self.progressbar.stop(),
            self._set_prog(""),
        ])

    def _setup_dnd(self):
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind("<<Drop>>", self._on_drop)

        # ── Keyboard shortcuts ──
        self.root.bind("<space>", lambda e: self._toggle_play_pause())
        self.root.bind("<Left>",  lambda e: self._seek_relative(-5))
        self.root.bind("<Right>", lambda e: self._seek_relative(5))

    def _seek_relative(self, delta):
        """Seek forward/backward by `delta` seconds."""
        if not self._audio_path or (not self._playing and not self._paused):
            return
        elapsed = time.time() - self._play_start_wall if self._playing else self._pause_offset
        new_t = max(0, min(elapsed + delta, self._duration - 0.5))
        self._on_seek(str(new_t))

    def _on_drop(self, event):
        if self._busy:
            messagebox.showwarning("Busy", "Cancel current process first.")
            return
        paths = self.root.tk.splitlist(event.data)
        path = paths[0] if paths else ""
        if path.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
            self._load_video_file(path)
        else:
            messagebox.showerror("Invalid file", "Please drop a video file.")

    def _draw_frame(self, frame):
        cw = self.canvas.winfo_width()  or VIDEO_W
        ch = self.canvas.winfo_height() or VIDEO_H
        fh, fw = frame.shape[:2]
        scale = min(cw / fw, ch / fh)
        nw, nh = int(fw * scale), int(fh * scale)
        # Use INTER_AREA for downscaling (high quality), INTER_LINEAR otherwise
        if nw < fw or nh < fh:
            interp = cv2.INTER_AREA
        else:
            interp = cv2.INTER_LINEAR
        frame = cv2.resize(frame, (nw, nh), interpolation=interp)
        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        photo = ImageTk.PhotoImage(Image.fromarray(rgb))
        self._current_photo = photo
        x = (cw - nw) // 2
        y = (ch - nh) // 2
        # Reuse the existing canvas image item instead of delete+create
        if self._frame_image_id is not None:
            self.canvas.coords(self._frame_image_id, x, y)
            self.canvas.itemconfig(self._frame_image_id, image=photo)
        else:
            self._frame_image_id = self.canvas.create_image(
                x, y, anchor="nw", image=photo, tags="frame"
            )

    def _show_thumbnail(self):
        if not self.video_path or not os.path.exists(self.video_path):
            return
        try:
            cap = cv2.VideoCapture(self.video_path)
            ret, frame = cap.read()
            cap.release()
            if ret:
                self._draw_frame(frame)
                self.canvas.itemconfig(self._canvas_text, text="")
        except Exception:
            pass

    def _open_cap(self):
        self._release_cap()
        if not self.video_path or not os.path.exists(self.video_path):
            raise FileNotFoundError("The selected video file is missing.")
        self._cap = cv2.VideoCapture(self.video_path)
        if not self._cap.isOpened():
            self._cap.release()
            self._cap = None
            raise RuntimeError("Could not open the selected video file.")
        raw_fps = self._cap.get(cv2.CAP_PROP_FPS)
        self._fps = raw_fps if raw_fps > 0 else 30.0
        # Display always capped at 30fps — Tkinter can't render faster reliably
        self._tick_interval = 33  # ~30 display fps
        self._current_frame_idx = 0
        self._log(f"Video FPS detected: {self._fps:.1f} — display capped at {self._display_fps}fps")
        self.root.after(0, lambda: self.fps_lbl.config(text=f"{self._fps:.0f} fps"))

    def _release_cap(self):
        # Stop decode thread first
        self._stop_decode_thread()
        if self._cap:
            self._cap.release()
            self._cap = None

    def _start_decode_thread(self):
        """Start background thread that decodes frames ahead of display."""
        self._stop_decode_thread()
        self._decode_stop.clear()
        # Clear any stale frames
        while not self._frame_queue.empty():
            try: self._frame_queue.get_nowait()
            except queue.Empty: break
        self._decode_thread = threading.Thread(
            target=self._decode_loop, daemon=True
        )
        self._decode_thread.start()

    def _stop_decode_thread(self):
        """Signal the decode thread to stop and wait for it."""
        self._decode_stop.set()
        if self._decode_thread and self._decode_thread.is_alive():
            self._decode_thread.join(timeout=0.5)
        self._decode_thread = None
        # Drain the queue
        while not self._frame_queue.empty():
            try: self._frame_queue.get_nowait()
            except queue.Empty: break

    def _decode_loop(self):
        """Background thread: reads frames from cv2 and pushes to queue.
        Seeks to the correct position based on wall-clock elapsed time.
        Only keeps the latest frame — the display thread consumes it."""
        while not self._decode_stop.is_set():
            if not self._cap or not self._cap.isOpened():
                break

            elapsed = time.time() - self._play_start_wall
            if elapsed >= self._duration:
                break

            target_frame = int(elapsed * self._fps)
            frames_behind = target_frame - self._current_frame_idx

            if frames_behind <= 0:
                # We're ahead of schedule, sleep briefly
                time.sleep(0.005)
                continue

            # Skip threshold — if too far behind, do a hard seek
            skip_threshold = max(10, int(self._fps * 0.3))

            if frames_behind > skip_threshold:
                # Hard seek — jump directly to target position
                self._cap.set(cv2.CAP_PROP_POS_MSEC, elapsed * 1000)
                self._current_frame_idx = target_frame
                ret, frame = self._cap.read()
                if ret:
                    self._current_frame_idx += 1
                    # Put frame in queue, drop old one if full
                    try:
                        self._frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                    self._frame_queue.put(frame)
            else:
                # Soft catch-up — read through frames, keep only the last
                last_frame = None
                for _ in range(frames_behind):
                    if self._decode_stop.is_set():
                        return
                    ret, frm = self._cap.read()
                    if not ret:
                        break
                    last_frame = frm
                    self._current_frame_idx += 1
                if last_frame is not None:
                    try:
                        self._frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                    self._frame_queue.put(last_frame)

            # Sleep a tiny bit to avoid busy-spinning
            time.sleep(0.002)

    def _seek_cap(self, seconds):
        if self._cap:
            self._cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
            self._current_frame_idx = int(seconds * self._fps)

    def pick_file(self):
        if self._busy:
            messagebox.showwarning("Busy", "Cancel current process first.")
            return
        path = filedialog.askopenfilename(
            title="Select video",
            filetypes=[("Video", "*.mp4 *.mov *.avi *.mkv *.webm")]
        )
        if path:
            self._load_video_file(path)

    def _load_video_file(self, path):
        self._stop()
        self._release_cap()
        remove_file_silent(self._audio_path)
        remove_file_silent(self._tts_audio_path)
        self._audio_path = None

        self.video_path      = path
        self.segments        = []
        self._tts_audio_path = None
        self._use_tts        = False
        self._duration       = 0.0
        self.root.after(0, lambda: self.tts_btn.config(
            text="🔊  Original", fg=ACCENT2, state="disabled"))
        name = os.path.basename(path)
        
        self.file_lbl.config(text=name[:42] + "…" if len(name) > 42 else name, fg=TEXT)
        self.clear_btn.grid() 
        
        self._set_status("File loaded", ACCENT2)
        self._log(f"Loaded: {name}")
        self.root.after(120, self._show_thumbnail)

    def _clear_video(self):
        if self._busy:
            messagebox.showwarning("Busy", "Cancel current process first.")
            return
            
        self._stop()
        self._release_cap()
        
        remove_file_silent(self._audio_path)
        remove_file_silent(self._tts_audio_path)
        self._audio_path = None
        self._tts_audio_path = None
        self._use_tts = False

        self.video_path = None
        self.segments = []
        self._duration = 0.0
        
        self.file_lbl.config(text="No file selected", fg=TEXT_MUTED)
        self.clear_btn.grid_remove() 
        self.tts_btn.config(text="🔊  Original", fg=ACCENT2, state="disabled")
        
        self._set_status("Ready", TEXT_MUTED)
        self._log("Video cleared.")
        
        self.canvas.delete("frame")
        self._frame_image_id = None
        self.canvas.itemconfig(self._canvas_text, text="\u25b6  Drop a video here or click Browse")
        self._current_photo = None
        
        self._cap_bar_canvas.itemconfig(self._cap_text_item, text="")

    def _cancel_process(self):
        if self._busy:
            self._cancel_processing = True
            self._set_status("Cancelling…", WARN)
            self._log("Cancellation requested…")

    def _start_processing(self):
        if self._busy: return
        if not self.video_path:
            messagebox.showerror("No file", "Please select a video first.")
            return
        if not os.path.exists(self.video_path):
            messagebox.showerror("Missing file", "The selected video file no longer exists.")
            return

        video_path = self.video_path
        lang_name = self.lang_var.get()
        lang_code = LANGUAGES.get(lang_name, "en")

        self._stop()
        remove_file_silent(self._audio_path)
        remove_file_silent(self._tts_audio_path)
        self._audio_path = None
        self._tts_audio_path = None
        self.segments = []
        self._use_tts = False
        self._duration = 0.0
        self.tts_btn.config(text="🔊  Original", fg=ACCENT2, state="disabled")

        self._busy_start()
        threading.Thread(
            target=self._process,
            args=(video_path, lang_name, lang_code),
            daemon=True,
        ).start()

    def _process(self, video_path, lang_name, lang_code):
        # Use tempfile for safer cleanup on crash
        audio_fd, audio_path = tempfile.mkstemp(suffix=".wav", prefix="translytic_audio_")
        os.close(audio_fd)
        tts_path = None

        def check_cancel():
            return self._cancel_processing

        def reset_partial_outputs():
            remove_file_silent(audio_path)
            remove_file_silent(tts_path)
            if self._audio_path == audio_path:
                self._audio_path = None
            if self._tts_audio_path == tts_path:
                self._tts_audio_path = None
            self.segments = []
            self._use_tts = False
            self._duration = 0.0
            self.root.after(0, lambda: self.tts_btn.config(
                text="🔊  Original", fg=ACCENT2, state="disabled"))

        try:
            if check_cancel(): raise InterruptedError("Cancelled")
            self._set_status("Extracting audio…", ACCENT)
            self._set_prog("Step 1 / 4")
            self._log("Step 1/4 — Extracting audio…")
            audio = extract_audio(video_path, out=audio_path)

            if check_cancel(): raise InterruptedError("Cancelled")
            with VideoFileClip(video_path) as clip:
                self._duration = clip.duration

            self._set_status("Transcribing…", ACCENT)
            self._set_prog("Step 2 / 4")
            self._log("Step 2/4 — Running Whisper…")
            raw = transcribe(audio)

            # ── Caption Validation: confidence analysis ──
            if raw:
                confidences = [s["confidence"] for s in raw]
                avg_conf = sum(confidences) / len(confidences)
                high_conf = sum(1 for c in confidences if c >= 60)
                low_conf  = sum(1 for c in confidences if c < 60)
                self._log(f"   ✔ Validation: Avg confidence {avg_conf:.1f}% "
                          f"| {high_conf} reliable, {low_conf} uncertain segments")
                for i, s in enumerate(raw):
                    if s["confidence"] < 60:
                        self._log(f"   ⚠ Low confidence ({s['confidence']}%): "
                                  f"\"{s['text'][:50]}…\"")
                    if s["no_speech_prob"] > 0.5:
                        self._log(f"   ⚠ Possible non-speech at {s['start']:.1f}s–{s['end']:.1f}s")

            if check_cancel(): raise InterruptedError("Cancelled")
            self._set_status(f"Translating → {lang_name}…", ACCENT)
            self._set_prog("Step 3 / 4")
            self._log(f"Step 3/4 — Translating {len(raw)} segments → {lang_name}…")
            translated_segments = translate_segments(raw, lang_code, lang_name, check_cancel)

            self._audio_path = audio
            self.segments = translated_segments
            n = len(translated_segments)

            if check_cancel(): raise InterruptedError("Cancelled")
            self._set_status("Generating dubbed audio…", ACCENT)
            self._set_prog("Step 4 / 4")
            self._log(f"Step 4/4 — Generating {lang_name} dubbed audio…")
            tts_fd, tts_path = tempfile.mkstemp(suffix=".wav", prefix="translytic_tts_")
            os.close(tts_fd)
            try:
                generate_tts_audio(
                    translated_segments, lang_code,
                    self._duration, tts_path, check_cancel
                )
                self._tts_audio_path = tts_path
                tts_path = None
                self._log(f"✓  Dubbed audio ready.")
                self.root.after(0, lambda: self.tts_btn.config(
                    text="🔊  Original", fg=ACCENT2, state="normal"))
            except InterruptedError:
                raise
            except Exception as e:
                self._log(f"TTS generation failed (captions still work): {e}")
                remove_file_silent(tts_path)
                tts_path = None
                self._tts_audio_path = None
                self._use_tts = False
                self.root.after(0, lambda: self.tts_btn.config(
                    text="🔊  Original", fg=ACCENT2, state="disabled"))

            self._set_status(f"Ready — {n} captions", SUCCESS)
            self._log(f"✓  Done! {n} captions ready. Playing…")

            self.root.after(0, lambda: [
                self.seekbar.config(to=self._duration),
                self._play(),
            ])

        except InterruptedError:
            reset_partial_outputs()
            self._log("Processing cancelled.")
            self._set_status("Cancelled", WARN)
        except Exception as e:
            reset_partial_outputs()
            err = str(e)
            self._log(f"ERROR: {err}")
            self.root.after(0, lambda: messagebox.showerror("Error", err))
            self._set_status("Failed", ERROR)
        finally:
            self._busy_stop()

    def _toggle_play_pause(self):
        if self._playing:
            self._pause()
        elif self._paused:
            self._play()
        elif self.segments:
            self._play()

    def _play(self):
        if not self.segments:
            messagebox.showwarning("Not ready", "Process the video first.")
            return

        active_audio = (
            self._tts_audio_path
            if self._use_tts and self._tts_audio_path
            else self._audio_path
        )
        if not active_audio or not os.path.exists(active_audio):
            messagebox.showerror("Playback error", "Processed audio is missing. Process the video again.")
            return

        if self._paused:
            try:
                # Re-open capture if it was released
                if not self._cap or not self._cap.isOpened():
                    self._open_cap()
                self._seek_cap(self._pause_offset)
                pygame.mixer.music.unpause()
            except Exception as e:
                self._release_cap()
                messagebox.showerror("Playback error", str(e))
                return
            self._play_start_wall = time.time() - self._pause_offset
            self._paused  = False
            self._playing = True
            self._set_status("Playing…", SUCCESS)
            self.play_pause_btn.config(text="⏸  Pause")
            self._start_decode_thread()
            self._tick()
            return

        if self._playing: return

        try:
            pygame.mixer.music.load(active_audio)
            self._open_cap()
            pygame.mixer.music.play()
        except Exception as e:
            self._release_cap()
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
            except Exception:
                pass
            messagebox.showerror("Playback error", str(e))
            return

        self._playing         = True
        self._paused          = False
        self._play_start_wall = time.time()
        self._pause_offset    = 0.0
        mode_label = "🗣  Dubbed" if self._use_tts else "🔉  Original"
        self._set_status(f"Playing ({mode_label})…", SUCCESS)
        self.play_pause_btn.config(text="⏸  Pause")
        self.canvas.itemconfig(self._canvas_text, text="")
        self._start_decode_thread()
        self._tick()

    def _pause(self):
        if not self._playing or self._paused: return
        pygame.mixer.music.pause()
        self._stop_decode_thread()
        self._pause_offset = time.time() - self._play_start_wall
        self._paused  = True
        self._playing = False
        self._set_status("Paused", WARN)
        self.play_pause_btn.config(text="▶  Play")
        if self._caption_job:
            self.root.after_cancel(self._caption_job)
            self._caption_job = None

    def _stop(self):
        self._playing = False
        self._paused  = False
        self._pause_offset = 0.0
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except Exception: pass
        if self._caption_job:
            self.root.after_cancel(self._caption_job)
            self._caption_job = None
        self._release_cap()
        self.canvas.delete("frame")  # remove orphaned canvas items
        self._frame_image_id = None  # reset so next play creates a fresh canvas item
        self._last_cap_text = None   # reset caption tracking
        self.play_pause_btn.config(text="▶  Play")
        self.root.after(0, lambda: [
            self._cap_bar_canvas.itemconfig(self._cap_text_item, text=""),
            self.seek_var.set(0),
            self.time_lbl.config(text="0:00 / 0:00"),
            self.fps_lbl.config(text=""),
            self._set_status("Stopped", TEXT_MUTED),
        ])

    def _tick(self):
        if not self._playing:
            return

        elapsed = time.time() - self._play_start_wall

        if elapsed >= self._duration:
            self._stop()
            self._show_thumbnail()
            return

        # Consume the latest decoded frame from the background thread
        frame = None
        try:
            frame = self._frame_queue.get_nowait()
        except queue.Empty:
            pass  # no new frame ready yet, skip this display tick

        if frame is not None:
            self._draw_frame(frame)

        # Caption update (only when text changes)
        cap_text = get_caption_at(self.segments, elapsed)
        if cap_text != self._last_cap_text:
            self._cap_bar_canvas.itemconfig(self._cap_text_item, text=cap_text)
            self._last_cap_text = cap_text

        # Seekbar + timestamp
        self.seek_var.set(elapsed)
        total = int(self._duration)
        cur   = int(elapsed)
        self.time_lbl.config(
            text=f"{cur // 60}:{cur % 60:02d} / {total // 60}:{total % 60:02d}"
        )

        # Schedule next display tick at 30fps
        self._caption_job = self.root.after(self._tick_interval, self._tick)

    def _on_seek(self, val):
        if not self._audio_path: return
        t = float(val)
        t = max(0, min(t, self._duration - 0.1))  # clamp to valid range
        if self._playing or self._paused:
            active_audio = (
                self._tts_audio_path
                if self._use_tts and self._tts_audio_path
                else self._audio_path
            )
            if not active_audio or not os.path.exists(active_audio):
                messagebox.showerror("Playback error", "Processed audio is missing. Process the video again.")
                return
            was_paused = self._paused
            # Stop decode thread BEFORE seeking to avoid race condition
            self._stop_decode_thread()
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.load(active_audio)

                # Re-open capture if needed
                if not self._cap or not self._cap.isOpened():
                    self._open_cap()
                self._seek_cap(t)

                if was_paused:
                    # Stay paused at new position — start then immediately pause
                    pygame.mixer.music.play(start=t)
                    pygame.mixer.music.pause()
                    self._pause_offset = t
                    self._play_start_wall = time.time() - t
                    self._paused  = True
                    self._playing = False
                    # Show the frame at the seek position
                    if self._cap:
                        ret, frame = self._cap.read()
                        if ret:
                            self._draw_frame(frame)
                    # Update caption at new position
                    cap_text = get_caption_at(self.segments, t)
                    self._cap_bar_canvas.itemconfig(self._cap_text_item, text=cap_text)
                    self._last_cap_text = cap_text
                else:
                    pygame.mixer.music.play(start=t)
                    self._play_start_wall = time.time() - t
                    self._pause_offset    = t
                    self._paused  = False
                    self._playing = True
                    self.play_pause_btn.config(text="⏸  Pause")
                    if self._caption_job:
                        self.root.after_cancel(self._caption_job)
                        self._caption_job = None
                    self._start_decode_thread()
                    self._tick()
            except Exception as e:
                self._release_cap()
                try:
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                except Exception:
                    pass
                self._playing = False
                self._paused = False
                self.play_pause_btn.config(text="▶  Play")
                messagebox.showerror("Playback error", str(e))

    def _toggle_audio_mode(self):
        if not self._tts_audio_path or not os.path.exists(self._tts_audio_path):
            messagebox.showinfo("Not available",
                "Dubbed audio is not ready yet. Process a video first.")
            self._tts_audio_path = None
            self._use_tts = False
            self.tts_btn.config(text="🔊  Original", fg=ACCENT2, state="disabled")
            return

        old_mode = self._use_tts
        self._use_tts = not self._use_tts
        label = "🗣  Dubbed" if self._use_tts else "🔊  Original"
        self.tts_btn.config(
            text=label,
            fg=ACCENT if self._use_tts else ACCENT2,
        )

        if self._playing:
            t = time.time() - self._play_start_wall
            active_audio = (
                self._tts_audio_path if self._use_tts else self._audio_path
            )
            if not active_audio or not os.path.exists(active_audio):
                self._use_tts = old_mode
                label = "🗣  Dubbed" if self._use_tts else "🔊  Original"
                self.tts_btn.config(
                    text=label,
                    fg=ACCENT if self._use_tts else ACCENT2,
                )
                messagebox.showerror("Playback error", "Processed audio is missing. Process the video again.")
                return
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.load(active_audio)
                pygame.mixer.music.play(start=t)
                self._play_start_wall = time.time() - t
                mode = "🗣  Dubbed" if self._use_tts else "🔉  Original"
                self._set_status(f"Playing ({mode})…", SUCCESS)
            except Exception as e:
                self._use_tts = old_mode
                label = "🗣  Dubbed" if self._use_tts else "🔊  Original"
                self.tts_btn.config(
                    text=label,
                    fg=ACCENT if self._use_tts else ACCENT2,
                )
                fallback_audio = self._tts_audio_path if old_mode else self._audio_path
                try:
                    if not fallback_audio or not os.path.exists(fallback_audio):
                        raise FileNotFoundError("Previous audio is missing.")
                    pygame.mixer.music.stop()
                    pygame.mixer.music.load(fallback_audio)
                    pygame.mixer.music.play(start=t)
                    self._play_start_wall = time.time() - t
                except Exception:
                    self._stop_decode_thread()
                    self._playing = False
                    self._paused = False
                    self.play_pause_btn.config(text="▶  Play")
                messagebox.showerror("Playback error", str(e))

    def _export_srt(self):
        if not self.segments:
            messagebox.showerror("Nothing to export", "Process the video first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".srt", initialfile="subtitles",
            filetypes=[("SubRip Subtitle", "*.srt")]
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(to_srt(self.segments))
            messagebox.showinfo("Saved", f"SRT saved to:\n{path}")

    def _on_close(self):
        self._cancel_processing = True
        self._stop()
        self._release_cap()
        pygame.mixer.quit()
        time.sleep(0.1)
        remove_file_silent(self._audio_path)
        remove_file_silent(self._tts_audio_path)
        # Clean up tempfile-generated files in system temp dir
        tmp_dir = tempfile.gettempdir()
        for pattern in ["translytic_audio_*.wav", "translytic_tts_*.wav"]:
            for f in glob.glob(os.path.join(tmp_dir, pattern)):
                remove_file_silent(f)
        self.root.destroy()


# ── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    # Clean up leftover temp files from previous runs
    tmp_dir = tempfile.gettempdir()
    for pattern in ["translytic_audio_*.wav", "translytic_tts_*.wav"]:
        for f in glob.glob(os.path.join(tmp_dir, pattern)):
            remove_file_silent(f)

    root = TkinterDnD.Tk()
    root.option_add("*tearOff", False)
    app = CaptionApp(root)
    root.mainloop()
