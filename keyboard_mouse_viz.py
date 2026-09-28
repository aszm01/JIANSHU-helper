# -*- coding: utf-8 -*-
"""
录屏键鼠助手（单分层窗 · 逐像素 alpha 版）
=========================================
功能：
  1. 全局捕获键盘 / 鼠标（切到任何软件都能感知）
  2. 右下角悬浮窗显示键盘鼠标线稿，按键 / 鼠标操作时半透明绿色高亮
  3. "开始 / 停止录制"、"导出记录"按钮直接画在悬浮窗上
  4. cog 齿轮（鼠标背部 Logo 位）-> 独立纯白设置窗口：
     背景透明度（含 3px 边框，不含绿标/线稿/cog）/ 鼠标穿透 / 位置固定
架构（单一分层窗口 UpdateLayeredWindow，逐像素 alpha）：
  主悬浮窗 = 一个 WS_EX_LAYERED|WS_EX_TOPMOST 的 Win32 弹窗，每帧把下列各层
  按顺序合成进一张 RGBA 位图后提交，层级从下到上：
     背景矩形（白，整块，alpha 由滑块控制）
       -> 绿色按键指示（半透明绿块）
       -> 线稿 + Arial 键帽文字（恒不透明）
       -> 按钮 / cog / 关闭（恒不透明）
  单窗口因此不存在 Z 序“夹住”、被 Tk 重新 raise、分层失效等问题。
  交互：pynput 全局鼠标钩子按屏幕坐标路由热区（按钮/cog/关闭/拖动），与窗口样式无关。
  鼠标穿透：主窗加 WS_EX_TRANSPARENT（点击全穿过），全局钩子仍只放行 cog。
  位置固定：路由层禁止拖动。
依赖：pynput, pillow, resvg-py
"""

import os
import sys
import time
import queue
import datetime
import ctypes
import ctypes.wintypes

import tkinter as tk

from PIL import Image, ImageDraw, ImageFont, ImageChops

from pynput import keyboard, mouse

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(name):
    base = getattr(sys, "MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


IMG_PATH = resource_path("初始.png")
SVG_PATH = resource_path("键鼠.svg")
OUTPUT_DIR = app_dir()

# 键鼠热区布局（百分比坐标）：(标识, 上, 左, 宽, 高)
KEY_LAYOUT = [
    ("Escape", 1.1, 0.2, 3.2, 12.2), ("F1", 1.1, 5.4, 3.2, 12.2),
    ("F2", 1.1, 9.7, 3.2, 12.2), ("F3", 1.1, 14.0, 3.2, 12.2),
    ("F4", 1.1, 18.3, 3.2, 12.2), ("F5", 1.1, 23.2, 3.2, 12.2),
    ("F6", 1.1, 27.4, 3.2, 12.2), ("F7", 1.1, 31.7, 3.2, 12.2),
    ("F8", 1.1, 36.0, 3.2, 12.2), ("F9", 1.1, 40.9, 3.2, 12.2),
    ("F10", 1.1, 45.2, 3.2, 12.2), ("F11", 1.1, 49.5, 3.2, 12.2),
    ("F12", 1.1, 53.8, 3.2, 12.2), ("Delete", 1.1, 58.7, 4.4, 12.2),
    ("Backquote", 18.6, 0.2, 3.2, 12.2), ("Digit1", 18.6, 4.5, 3.2, 12.2),
    ("Digit2", 18.6, 8.7, 3.2, 12.2), ("Digit3", 18.6, 13.0, 3.2, 12.2),
    ("Digit4", 18.6, 17.2, 3.2, 12.2), ("Digit5", 18.6, 21.5, 3.2, 12.2),
    ("Digit6", 18.6, 25.8, 3.2, 12.2), ("Digit7", 18.6, 30.1, 3.2, 12.2),
    ("Digit8", 18.6, 34.3, 3.2, 12.2), ("Digit9", 18.6, 38.6, 3.2, 12.2),
    ("Digit0", 18.6, 42.9, 3.2, 12.2), ("Minus", 18.6, 47.1, 3.2, 12.2),
    ("Equal", 18.6, 51.4, 3.2, 12.2), ("Backspace", 18.6, 55.6, 7.6, 12.2),
    ("Tab", 35.6, 0.2, 5.8, 12.2), ("KeyQ", 35.6, 7.1, 3.2, 12.2),
    ("KeyW", 35.6, 11.3, 3.2, 12.2), ("KeyE", 35.6, 15.6, 3.2, 12.2),
    ("KeyR", 35.6, 19.9, 3.2, 12.2), ("KeyT", 35.6, 24.2, 3.2, 12.2),
    ("KeyY", 35.6, 28.5, 3.2, 12.2), ("KeyU", 35.6, 32.7, 3.2, 12.2),
    ("KeyI", 35.6, 37.0, 3.2, 12.2), ("KeyO", 35.6, 41.2, 3.2, 12.2),
    ("KeyP", 35.6, 45.5, 3.2, 12.2), ("BracketLeft", 35.6, 49.7, 3.2, 12.2),
    ("BracketRight", 35.6, 54.0, 3.2, 12.2), ("Backslash", 35.6, 58.2, 5.0, 12.2),
    ("CapsLock", 52.4, 0.2, 6.8, 12.2), ("KeyA", 52.4, 8.0, 3.2, 12.2),
    ("KeyS", 52.4, 12.3, 3.2, 12.2), ("KeyD", 52.4, 16.6, 3.2, 12.2),
    ("KeyF", 52.4, 20.9, 3.2, 12.2), ("KeyG", 52.4, 25.2, 3.2, 12.2),
    ("KeyH", 52.4, 29.4, 3.2, 12.2), ("KeyJ", 52.4, 33.7, 3.2, 12.2),
    ("KeyK", 52.4, 38.0, 3.2, 12.2), ("KeyL", 52.4, 42.2, 3.2, 12.2),
    ("Semicolon", 52.4, 46.5, 3.2, 12.2), ("Quote", 52.4, 50.7, 3.2, 12.2),
    ("Enter", 52.4, 54.9, 8.3, 12.2),
    ("ShiftLeft", 69.4, 0.2, 8.6, 12.2), ("KeyZ", 69.4, 9.7, 3.2, 12.2),
    ("KeyX", 69.4, 14.0, 3.2, 12.2), ("KeyC", 69.4, 18.2, 3.2, 12.2),
    ("KeyV", 69.4, 22.5, 3.2, 12.2), ("KeyB", 69.4, 26.7, 3.2, 12.2),
    ("KeyN", 69.4, 31.0, 3.2, 12.2), ("KeyM", 69.4, 35.2, 3.2, 12.2),
    ("Comma", 69.4, 39.5, 3.2, 12.2), ("Period", 69.4, 43.8, 3.2, 12.2),
    ("Slash", 69.4, 48.1, 3.2, 12.2), ("ShiftRight", 69.4, 52.2, 11.1, 12.2),
    ("ControlLeft", 86.4, 0.2, 5.9, 12.2), ("MetaLeft", 86.4, 7.1, 3.2, 12.2),
    ("AltLeft", 86.4, 11.3, 5.9, 12.2), ("Space", 86.4, 17.5, 32.6, 12.2),
    ("AltRight", 86.4, 50.4, 4.3, 12.2), ("ControlRight", 86.4, 55.6, 3.2, 12.2),
    ("ArrowUp", 69.4, 65.2, 3.2, 12.2), ("ArrowLeft", 86.4, 60.8, 3.2, 12.2),
    ("ArrowDown", 86.4, 65.2, 3.2, 12.2), ("ArrowRight", 86.4, 69.5, 3.2, 12.2),
    ("NumLock", 18.6, 70.4, 3.2, 12.2), ("NumpadDivide", 18.6, 74.7, 3.2, 12.2),
    ("NumpadMultiply", 18.6, 78.9, 3.2, 12.2), ("NumpadSubtract", 18.6, 83.2, 3.2, 12.2),
    ("Numpad7", 35.6, 70.4, 3.2, 12.2), ("Numpad8", 35.6, 74.7, 3.2, 12.2),
    ("Numpad9", 35.6, 78.9, 3.2, 12.2), ("NumpadAdd", 35.2, 83.2, 3.2, 29.9),
    ("Numpad4", 52.4, 70.4, 3.2, 12.2), ("Numpad5", 52.4, 74.7, 3.2, 12.2),
    ("Numpad6", 52.4, 78.9, 3.2, 12.2),
    ("Numpad1", 69.4, 70.4, 3.2, 12.2), ("Numpad2", 69.4, 74.7, 3.2, 12.2),
    ("Numpad3", 69.4, 78.9, 3.2, 12.2), ("NumpadEnter", 69.0, 83.2, 3.2, 29.9),
    ("Numpad0", 86.4, 74.7, 3.2, 12.2), ("NumpadDecimal", 86.4, 78.9, 3.2, 12.2),
    ("MouseLeft", 26.0, 90.0, 4.0, 25.0),
    ("MouseRight", 26.0, 95.0, 4.0, 25.0),
    ("MouseWheelUp", 27.4, 94.1, 0.8, 4.2),
    ("MouseWheel", 32.5, 94.1, 0.8, 5.6),
    ("MouseWheelDown", 39.0, 94.1, 0.8, 4.5),
    ("MouseSide1", 47.2, 88.5, 0.7, 7.3),
    ("MouseSide2", 55.4, 88.5, 0.7, 7.5),
]

BTN_START = (1.1, 70.4, 7.5, 13.5)
BTN_DOWNLOAD = (1.1, 78.9, 7.5, 13.5)
_BTN_GAP = BTN_DOWNLOAD[1] - (BTN_START[1] + BTN_START[2])
NOTICE = (1.1, BTN_DOWNLOAD[1] + BTN_DOWNLOAD[2] + _BTN_GAP, BTN_DOWNLOAD[2], BTN_DOWNLOAD[3])

WIDTH_DIVISOR = 4
BORDER = 3

VK_CAPITAL = 0x14
VK_NUMLOCK = 0x90

CHAR_MAP = {str(i): "Digit%d" % i for i in range(10)}
CHAR_MAP.update({ch: "Key" + ch.upper() for ch in "abcdefghijklmnopqrstuvwxyz"})
CHAR_MAP.update({
    "`": "Backquote", "-": "Minus", "=": "Equal",
    "[": "BracketLeft", "]": "BracketRight", "\\": "Backslash",
    ";": "Semicolon", "'": "Quote", ",": "Comma", ".": "Period", "/": "Slash",
    " ": "Space",
})

KEY_MAP = {
    keyboard.Key.esc: "Escape", keyboard.Key.f1: "F1", keyboard.Key.f2: "F2",
    keyboard.Key.f3: "F3", keyboard.Key.f4: "F4", keyboard.Key.f5: "F5",
    keyboard.Key.f6: "F6", keyboard.Key.f7: "F7", keyboard.Key.f8: "F8",
    keyboard.Key.f9: "F9", keyboard.Key.f10: "F10", keyboard.Key.f11: "F11",
    keyboard.Key.f12: "F12", keyboard.Key.delete: "Delete",
    keyboard.Key.tab: "Tab",
    keyboard.Key.shift: "ShiftLeft", keyboard.Key.shift_r: "ShiftRight",
    keyboard.Key.ctrl: "ControlLeft", keyboard.Key.ctrl_r: "ControlRight",
    keyboard.Key.alt: "AltLeft", keyboard.Key.alt_r: "AltRight",
    keyboard.Key.alt_gr: "AltRight",
    keyboard.Key.cmd: "MetaLeft", keyboard.Key.cmd_r: "MetaLeft",
    keyboard.Key.space: "Space", keyboard.Key.enter: "Enter",
    keyboard.Key.backspace: "Backspace", keyboard.Key.caps_lock: "CapsLock",
    keyboard.Key.num_lock: "NumLock",
    keyboard.Key.up: "ArrowUp", keyboard.Key.down: "ArrowDown",
    keyboard.Key.left: "ArrowLeft", keyboard.Key.right: "ArrowRight",
}
for _kname, _code in (("shift_l", "ShiftLeft"), ("ctrl_l", "ControlLeft"),
                      ("alt_l", "AltLeft"), ("cmd_l", "MetaLeft")):
    _k = getattr(keyboard.Key, _kname, None)
    if _k is not None:
        KEY_MAP[_k] = _code

_ALT_KEYS = tuple(k for k in (getattr(keyboard.Key, n, None)
                              for n in ("alt", "alt_l", "alt_r", "alt_gr")) if k is not None)
_CTRL_KEYS = tuple(k for k in (getattr(keyboard.Key, n, None)
                               for n in ("ctrl", "ctrl_l", "ctrl_r")) if k is not None)

NUMPAD_VK = {
    0x60: "Numpad0", 0x61: "Numpad1", 0x62: "Numpad2", 0x63: "Numpad3",
    0x64: "Numpad4", 0x65: "Numpad5", 0x66: "Numpad6", 0x67: "Numpad7",
    0x68: "Numpad8", 0x69: "Numpad9", 0x6A: "NumpadMultiply",
    0x6B: "NumpadAdd", 0x6D: "NumpadSubtract", 0x6E: "NumpadDecimal",
    0x6F: "NumpadDivide",
}

MOUSE_NAME = {0: "鼠标左", 1: "鼠标中", 2: "鼠标右", 3: "侧键后", 4: "侧键前"}

NUMPAD_DISPLAY = {
    "Numpad0": "小键盘0", "Numpad1": "小键盘1", "Numpad2": "小键盘2",
    "Numpad3": "小键盘3", "Numpad4": "小键盘4", "Numpad5": "小键盘5",
    "Numpad6": "小键盘6", "Numpad7": "小键盘7", "Numpad8": "小键盘8",
    "Numpad9": "小键盘9", "NumpadMultiply": "小键盘*", "NumpadAdd": "小键盘+",
    "NumpadSubtract": "小键盘-", "NumpadDecimal": "小键盘.", "NumpadDivide": "小键盘/",
}


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", ctypes.c_uint32), ("scanCode", ctypes.c_uint32),
                ("flags", ctypes.c_uint32), ("time", ctypes.c_uint32),
                ("dwExtraInfo", ctypes.c_size_t)]


def key_to_code(key):
    if isinstance(key, keyboard.Key):
        return KEY_MAP.get(key)
    if key is None:
        return None
    vk = getattr(key, "vk", None)
    ch = getattr(key, "char", None)
    if vk is not None and 0x60 <= vk <= 0x6F:
        return NUMPAD_VK.get(vk)
    if ch is not None:
        return CHAR_MAP.get(ch)
    return None


def key_to_display(key):
    if isinstance(key, keyboard.Key):
        names = {
            keyboard.Key.esc: "Escape", keyboard.Key.space: "Space",
            keyboard.Key.enter: "Enter", keyboard.Key.tab: "Tab",
            keyboard.Key.backspace: "Backspace", keyboard.Key.delete: "Delete",
            keyboard.Key.shift: "Shift", keyboard.Key.shift_r: "Shift",
            keyboard.Key.ctrl: "Ctrl", keyboard.Key.ctrl_r: "Ctrl",
            keyboard.Key.alt: "Alt", keyboard.Key.alt_r: "Alt",
            keyboard.Key.alt_gr: "Alt", keyboard.Key.cmd: "Win",
            keyboard.Key.cmd_r: "Win", keyboard.Key.caps_lock: "CapsLock",
            keyboard.Key.num_lock: "NumLock",
            keyboard.Key.up: "ArrowUp", keyboard.Key.down: "ArrowDown",
            keyboard.Key.left: "ArrowLeft", keyboard.Key.right: "ArrowRight",
        }
        for _kname, _disp in (("shift_l", "Shift"), ("ctrl_l", "Ctrl"),
                              ("alt_l", "Alt"), ("cmd_l", "Win")):
            _k = getattr(keyboard.Key, _kname, None)
            if _k is not None:
                names[_k] = _disp
        if key in names:
            return names[key]
        return str(key).replace("Key.", "")
    vk = getattr(key, "vk", None)
    ch = getattr(key, "char", None)
    if vk is not None and 0x60 <= vk <= 0x6F:
        code = NUMPAD_VK.get(vk)
        if code:
            return NUMPAD_DISPLAY.get(code, code)
    return ch if ch else "?"


# ---------------------------------------------------------------------------
# Win32 结构定义
# ---------------------------------------------------------------------------
class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_ulong), ("biWidth", ctypes.c_long),
                ("biHeight", ctypes.c_long), ("biPlanes", ctypes.c_ushort),
                ("biBitCount", ctypes.c_ushort), ("biCompression", ctypes.c_ulong),
                ("biSizeImage", ctypes.c_ulong), ("biX", ctypes.c_long),
                ("biY", ctypes.c_long), ("biClrUsed", ctypes.c_ulong),
                ("biClrImp", ctypes.c_ulong)]


class _BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SrcAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


_WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_uint,
                              ctypes.c_void_p, ctypes.c_void_p)


class KeyboardMouseViz:
    def __init__(self):
        self._set_dpi_aware()
        self.u32 = ctypes.windll.user32
        self.g32 = ctypes.windll.gdi32
        self.k32 = ctypes.windll.kernel32
        self.u32.DefWindowProcW.restype = ctypes.c_long
        self.u32.DefWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                           ctypes.c_void_p, ctypes.c_void_p]

        # 隐藏 Tk root：只做消息泵 / after 定时 / 设置窗父
        self.root = tk.Tk()
        self.root.title("录屏键鼠助手")
        self.root.withdraw()

        self.records = []
        self.is_recording = False
        self.start_time = 0.0
        self.last_event_time = 0.0

        self.event_queue = queue.Queue()
        self.lit = set()           # 当前点亮的 code
        self.pressed = set()
        self.lock_state = {}
        self._drag_off = None
        self._after_ids = set()
        self._lock_tick = 0
        self._wheel_timer = {}

        # 设置状态
        self.bg_alpha = 1.0
        self.click_through = False
        self.pos_fixed = False
        self.settings_open = False
        self.set_win = None
        self._slider_state = {}

        # UI 状态
        self.dl_visible = False
        self.notice_text = ""
        self.notice_until = 0.0
        self.mouse_pos = (0, 0)
        self._hover_tag = None

        self._build_resources()
        self._create_main_window()
        self._start_listeners()
        self._refresh_lock_states()
        self._render()
        self._after(15, self._poll_events)
        try:
            self.root.mainloop()
        except Exception:
            pass
        self._shutdown()

    # ------------------------------------------------------------ DPI/工作区
    def _set_dpi_aware(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    def _work_area(self):
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
        r = RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)
        return (r.left, r.top, r.right - r.left, r.bottom - r.top)

    # ------------------------------------------------------------ 资源构建
    def _build_resources(self):
        import re as _re
        import io as _io
        self.img_w = self.root.winfo_screenwidth() // WIDTH_DIVISOR
        self.img_h = max(1, int(self.img_w * 317 / 1264))
        self.win_w = self.img_w + BORDER * 2
        self.win_h = self.img_h + BORDER * 2

        # 线稿（含 Arial 键帽文字，内部透明）
        try:
            import resvg_py as _resvg
            _svg = _io.open(SVG_PATH, encoding="utf-8").read()
            _s2 = _re.sub(r'viewBox="[^"]*"', 'viewBox="8 10 1264 317"', _svg, count=1)
            _s2 = _re.sub(r'width="[^"]*"', 'width="%d"' % self.img_w, _s2, count=1)
            _s2 = _re.sub(r'height="[^"]*"', 'height="%d"' % self.img_h, _s2, count=1)
            _png = _resvg.svg_to_bytes(_s2)
            self.line_art = Image.open(_io.BytesIO(_png)).convert("RGBA")
        except Exception:
            img = Image.open(IMG_PATH).convert("RGBA")
            self.line_art = img.resize((self.img_w, self.img_h), Image.LANCZOS)

        wa = self._work_area()
        self.win_x = wa[0] + wa[2] - self.win_w - 12
        self.win_y = wa[1] + wa[3] - self.win_h - 12

        # 绿色按键块（PIL 小图缓存）：code -> (RGBA 小图, x0, y0) 内容坐标
        self.green_tiles = {}
        for c, t, l, w, h in KEY_LAYOUT:
            x = int(l / 100 * self.img_w); y = int(t / 100 * self.img_h)
            ww = int(w / 100 * self.img_w); hh = int(h / 100 * self.img_h)
            if ww < 1 or hh < 1:
                continue
            if c.startswith("Mouse"):
                x0, y0, x1, y1 = x, y, x + ww, y + hh
                radius = min(ww, hh) * 0.35
            else:
                x0 = max(0, x - 1); y0 = max(0, y - 1)
                x1 = min(self.img_w, x + ww + 1); y1 = min(self.img_h, y + hh + 3)
                radius = 4
            g = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
            ImageDraw.Draw(g).rounded_rectangle(
                [0, 0, x1 - x0 - 1, y1 - y0 - 1], radius=radius,
                fill=(76, 175, 80, 153))
            self.green_tiles[c] = (g, x0, y0)

        # cog 齿轮（FontAwesome，黑色）
        self.cog_size = max(22, int(self.img_w * 0.045))
        cog = Image.new("RGBA", (self.cog_size, self.cog_size), (0, 0, 0, 0))
        try:
            cf = ImageFont.truetype(resource_path("fa-solid-900.ttf"), self.cog_size)
            ImageDraw.Draw(cog).text((self.cog_size / 2.0, self.cog_size / 2.0),
                                     "\uf013", font=cf, fill=(0, 0, 0, 255),
                                     anchor="mm")
        except Exception:
            pass
        self.cog_img = cog

        # 按钮中文字体（微软雅黑，中文显示）
        self.btn_font = ImageFont.truetype(
            "C:\\Windows\\Fonts\\msyhbd.ttc",
            max(8, int(self.img_h * 0.065)))
        self.notice_font = ImageFont.truetype(
            "C:\\Windows\\Fonts\\msyhbd.ttc",
            max(8, int(self.img_h * 0.05)))

    def _cog_center(self):
        return (int(0.945 * self.img_w), int(0.75 * self.img_h))

    def _in_cog(self, cx, cy):
        """圆形热区：以齿轮中心为圆心，半径=齿轮外缘（含中心空洞），+2px 容差"""
        cx0, cy0 = self._cog_center()
        r = self.cog_size / 2.0 + 2
        return (cx - cx0) ** 2 + (cy - cy0) ** 2 <= r * r

    # ------------------------------------------------------------ 主窗口
    def _create_main_window(self):
        self._wnd_cb = _WNDPROC(self._wndproc)

        class WC(ctypes.Structure):
            _fields_ = [("style", ctypes.c_uint), ("lpfnWndProc", _WNDPROC),
                        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                        ("hInstance", ctypes.c_void_p), ("hIcon", ctypes.c_void_p),
                        ("hCursor", ctypes.c_void_p), ("hbr", ctypes.c_void_p),
                        ("menu", ctypes.c_wchar_p), ("name", ctypes.c_wchar_p)]

        self._wc = WC()
        self._wc.lpfnWndProc = self._wnd_cb
        self._wc.name = "KbMouseVizCls"
        self._hinst = self.k32.GetModuleHandleW(None)
        self._wc.hInstance = self._hinst
        self.u32.RegisterClassW(ctypes.byref(self._wc))

        self.hwnd = self.u32.CreateWindowExW(
            0x80000 | 0x8, "KbMouseVizCls", "录屏键鼠助手", 0x80000000,
            self.win_x, self.win_y, self.win_w, self.win_h,
            0, 0, self._hinst, 0)
        self.u32.ShowWindow(self.hwnd, 5)

    def _wndproc(self, h, m, w, l):
        return self.u32.DefWindowProcW(h, m, w, l)

    # ------------------------------------------------------------ 渲染合成
    def _render(self):
        W, H = self.win_w, self.win_h
        C = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(C)

        # 1) 背景矩形：整块白色，alpha 由滑块控制
        a = int(round(self.bg_alpha * 255))
        d.rectangle([0, 0, W - 1, H - 1], fill=(255, 255, 255, a))

        # 2) 绿色按键指示（内容区偏移 BORDER）
        for code in self.lit:
            tile = self.green_tiles.get(code)
            if tile:
                g, gx, gy = tile
                C.alpha_composite(g, (BORDER + gx, BORDER + gy))

        # 3) 线稿 + Arial 文字（恒不透明）
        C.alpha_composite(self.line_art, (BORDER, BORDER))

        # 4) 控件（按钮 / cog / 关闭 / notice）
        self._paint_controls(C)

        self._submit(C)

    def _pos_rect(self, pos):
        t, l, w, h = pos
        x1 = BORDER + int(l / 100 * self.img_w)
        y1 = BORDER + int(t / 100 * self.img_h)
        x2 = BORDER + int((l + w) / 100 * self.img_w)
        y2 = BORDER + int((t + h) / 100 * self.img_h)
        return x1, y1, x2, y2

    def _paint_controls(self, C):
        d = ImageDraw.Draw(C)

        # 开始 / 录制
        x1, y1, x2, y2 = self._pos_rect(BTN_START)
        col = (67, 160, 71) if self.is_recording else (244, 67, 54)
        d.rounded_rectangle([x1, y1, x2, y2], radius=min(8, (y2 - y1) // 2), fill=col)
        self._center_text(d, (x1 + x2) // 2, (y1 + y2) // 2,
                          "录制" if self.is_recording else "开始", self.btn_font)

        # 下载
        if self.dl_visible:
            x1, y1, x2, y2 = self._pos_rect(BTN_DOWNLOAD)
            d.rounded_rectangle([x1, y1, x2, y2], radius=min(8, (y2 - y1) // 2),
                                fill=(33, 150, 243))
            self._center_text(d, (x1 + x2) // 2, (y1 + y2) // 2, "下载", self.btn_font)

        # notice
        if self.notice_text and time.time() < self.notice_until:
            x1, y1, x2, y2 = self._pos_rect(NOTICE)
            d.rounded_rectangle([x1, y1, x2, y2], radius=min(8, (y2 - y1) // 2),
                                fill=(76, 175, 80))
            self._center_text(d, (x1 + x2) // 2, (y1 + y2) // 2,
                              self.notice_text, self.notice_font)

        # cog
        cx, cy = self._cog_center()
        C.alpha_composite(self.cog_img,
                         (BORDER + cx - self.cog_size // 2,
                          BORDER + cy - self.cog_size // 2))

        # 关闭 X（正方形，悬停红底白 X）
        side = int(self.img_h * 0.135)
        x1 = BORDER + self.img_w - side
        y1 = BORDER
        x2 = x1 + side; y2 = y1 + side
        hover = (self._hover_tag == "close")
        if hover:
            d.rectangle([x1, y1, x2, y2], fill=(232, 17, 35))
            xcol = (255, 255, 255)
        else:
            xcol = (51, 51, 51)
        p = side * 0.26
        lw = max(2, int(side * 0.075))
        d.line([x1 + p, y1 + p, x2 - p, y2 - p], fill=xcol, width=lw)
        d.line([x2 - p, y1 + p, x1 + p, y2 - p], fill=xcol, width=lw)

    def _center_text(self, d, cx, cy, text, font):
        bb = d.textbbox((0, 0), text, font=font)
        dx = (bb[0] + bb[2]) / 2.0
        dy = (bb[1] + bb[3]) / 2.0
        d.text((cx - dx, cy - dy), text, font=font, fill=(255, 255, 255, 255))

    def _submit(self, img):
        W, H = img.size
        hdcScreen = self.u32.GetDC(0)
        hdcMem = self.g32.CreateCompatibleDC(hdcScreen)
        bi = _BITMAPINFO()
        bi.biSize = ctypes.sizeof(_BITMAPINFO)
        bi.biWidth = W; bi.biHeight = -H
        bi.biPlanes = 1; bi.biBitCount = 32; bi.biCompression = 0
        pbits = ctypes.c_void_p()
        hbmp = self.g32.CreateDIBSection(hdcMem, ctypes.byref(bi), 0,
                                         ctypes.byref(pbits), 0, 0)
        self.g32.SelectObject(hdcMem, hbmp)

        raw = img.tobytes()
        # C 级向量 premultiply（替代 Python 逐像素循环，避免卡顿）：
        # 拆 R,G,B,A -> 各自乘 alpha/255 -> 以 B,G,R,A 顺序重组，得 premultiplied BGRA
        r, g, b, a = img.split()
        r = ImageChops.multiply(r, a)
        g = ImageChops.multiply(g, a)
        b = ImageChops.multiply(b, a)
        raw = Image.merge("RGBA", (b, g, r, a)).tobytes()
        ctypes.memmove(pbits, raw, len(raw))

        bf = _BLENDFUNCTION(0, 0, 255, 1)
        size = ctypes.wintypes.SIZE(W, H)
        src = ctypes.wintypes.POINT(0, 0)
        pos = ctypes.wintypes.POINT(self.win_x, self.win_y)
        self.u32.UpdateLayeredWindow(self.hwnd, hdcScreen,
                                     ctypes.byref(pos), ctypes.byref(size),
                                     hdcMem, ctypes.byref(src), 0,
                                     ctypes.byref(bf), 2)
        self.g32.DeleteObject(hbmp)
        self.g32.DeleteDC(hdcMem)
        self.u32.ReleaseDC(0, hdcScreen)

    def _move_window(self, x, y):
        self.win_x, self.win_y = x, y
        self.u32.SetWindowPos(self.hwnd, 0, x, y, 0, 0,
                              0x0001 | 0x0010)  # NOSIZE | NOACTIVATE

    # ------------------------------------------------------------ 设置窗口
    SET_WIN_W = 260
    SET_WIN_H = 120

    def _toggle_settings(self):
        if self.settings_open:
            self._close_settings()
        else:
            self._open_settings()

    def _open_settings(self):
        if self.settings_open:
            return
        self.settings_open = True
        w, h = self.SET_WIN_W, self.SET_WIN_H
        sx = self.win_x + self.win_w - w
        sy = self.win_y - h - 8
        if sy < 0:
            sy = self.win_y + BORDER + 4
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#ffffff")
        win.geometry("%dx%d+%d+%d" % (w, h, sx, sy))

        side = 28
        xcv = tk.Canvas(win, width=side, height=side, bg="#ffffff",
                        highlightthickness=0, bd=0)

        def draw_x(color, bg):
            xcv.delete("all"); xcv.configure(bg=bg)
            xcv.create_rectangle(0, 0, side, side, fill=bg, outline="")
            xcv.create_line(8, 8, side - 8, side - 8, fill=color, width=2)
            xcv.create_line(side - 8, 8, 8, side - 8, fill=color, width=2)

        draw_x("#333333", "#ffffff")
        xcv.place(x=w - side - 6, y=6)
        xcv.bind("<Button-1>", lambda e: self._close_settings())
        xcv.bind("<Enter>", lambda e: draw_x("#ffffff", "#e81123"))
        xcv.bind("<Leave>", lambda e: draw_x("#333333", "#ffffff"))

        self.set_win = win
        # 先弹空窗让 Tk 空闲，再延迟构建子控件，避免主线程卡顿（沙漏）
        self._after(10, lambda: self._build_settings_items(win))

    def _build_settings_items(self, win):
        font = ("Microsoft YaHei", 10, "bold")
        # 铺满窗口、垫在最底层的“拖动画布”：点空白区即拖它。
        drag = tk.Canvas(win, width=self.SET_WIN_W, height=self.SET_WIN_H,
                         bg="#ffffff", highlightthickness=0, bd=0)
        drag.place(x=0, y=0)
        drag.tk.call("lower", drag._w)  # Canvas.lower 被图元方法占用，走底层整体降级
        self.drag_bg = drag
        self.title_lbl = tk.Label(win, text="背景透明度", bg="#ffffff", fg="#333333",
                                  font=font)
        self.title_lbl.place(x=16, y=12)
        self.alpha_pct = tk.Label(win, text="%d%%" % int(self.bg_alpha * 100),
                                  bg="#ffffff", fg="#333333", font=font)
        self.alpha_pct.place(relx=1.0, x=-44, y=12, anchor="ne")
        self._slider_state = {"alpha": self.bg_alpha}
        cv = tk.Canvas(win, width=232, height=20, bg="#ffffff",
                       highlightthickness=0, bd=0)
        cv.place(x=16, y=36)
        self.slider_canvas = cv
        self._slider_redraw(cv)
        cv.bind("<ButtonPress-1>", lambda e: self._slider_press(e, cv))
        cv.bind("<B1-Motion>", lambda e: self._slider_drag(e, cv))

        self.ct_btn = self._make_toggle_btn(win, 16, 64, "鼠标穿透",
                                            self.click_through,
                                            lambda: self._set_click_through(not self.click_through))
        self.fix_btn = self._make_toggle_btn(win, 138, 64, "位置固定",
                                             self.pos_fixed,
                                             lambda: self._set_pos_fixed(not self.pos_fixed))

        # 拖动：只在底层拖动画布 / 标题 / 百分比上绑定；
        # 关键：不在 Toplevel(win) 上绑定，否则滑块等子控件会经 bindtag 连带触发。
        self._sd_off = None
        for wgt in (drag, self.title_lbl, self.alpha_pct):
            wgt.bind("<Button-1>", self._sd_start)
            wgt.bind("<B1-Motion>", self._sd_move)

    def _sd_start(self, e):
        if self.set_win is None:
            self._sd_off = None
            return
        self._sd_off = (e.x_root - self.set_win.winfo_x(),
                        e.y_root - self.set_win.winfo_y())

    def _sd_move(self, e):
        off = getattr(self, "_sd_off", None)
        if off and self.set_win is not None:
            self.set_win.geometry("+%d+%d" % (e.x_root - off[0], e.y_root - off[1]))

    def _make_toggle_btn(self, win, x, y, text, on, cb):
        b = tk.Canvas(win, width=106, height=34, bg="#ffffff",
                      highlightthickness=0, bd=0)
        b.place(x=x, y=y)
        b.text = text
        self._toggle_draw(b, text, on)
        b.bind("<Button-1>", lambda e: cb())
        return b

    def _toggle_draw(self, b, text, on):
        b.delete("all")
        bg = "#4CAF50" if on else "#e0e0e0"
        fg = "#ffffff" if on else "#333333"
        b.create_rectangle(0, 0, 106, 34, fill=bg, outline="")
        b.create_text(53, 17, text=text, fill=fg,
                      font=("Microsoft YaHei", 10, "bold"))

    def _set_click_through(self, on):
        self.click_through = on
        self._toggle_draw(self.ct_btn, self.ct_btn.text, on)
        ex = self.u32.GetWindowLongW(self.hwnd, -20)
        if on:
            ex |= 0x20
        else:
            ex &= ~0x20
        self.u32.SetWindowLongW(self.hwnd, -20, ex)
        self.u32.SetWindowPos(self.hwnd, 0, 0, 0, 0, 0,
                              0x0001 | 0x0002 | 0x0020 | 0x0010)

    def _set_pos_fixed(self, on):
        self.pos_fixed = on
        self._toggle_draw(self.fix_btn, self.fix_btn.text, on)

    # 滑块
    def _slider_redraw(self, cv):
        cv.delete("all")
        av = self._slider_state.get("alpha", 1.0)
        tx, ty, tw, th = 20, 6, 192, 8
        fw = int(tw * av)
        if fw > 2:
            cv.create_rectangle(tx, ty, tx + fw, ty + th, fill="#000000", outline="")

    def _slider_press(self, e, cv):
        self._slider_set(e, cv)

    def _slider_drag(self, e, cv):
        self._slider_set(e, cv)

    def _slider_set(self, e, cv):
        av = max(0.0, min(1.0, (e.x - 20) / 192.0))
        self._slider_state["alpha"] = av
        self._slider_redraw(cv)
        try:
            self.alpha_pct.config(text="%d%%" % int(av * 100))
        except Exception:
            pass
        self.bg_alpha = av
        self._render()

    def _close_settings(self):
        if not self.settings_open:
            return
        self.settings_open = False
        if self.set_win is not None:
            try:
                self.set_win.destroy()
            except Exception:
                pass
        self.set_win = None

    # ------------------------------------------------------------ 提示
    def _show_notice(self, text):
        self.notice_text = text
        self.notice_until = time.time() + 2.5
        self._render()

    # ------------------------------------------------------------ 关闭
    def _after(self, ms, func):
        def run(tid):
            self._after_ids.discard(tid)
            func()
        tid = self.root.after(ms, lambda: run(tid))
        self._after_ids.add(tid)
        return tid

    def _shutdown(self):
        try:
            self._close_settings()
        except Exception:
            pass
        for s in ("kb_listener", "mouse_listener"):
            try:
                getattr(self, s).stop()
            except Exception:
                pass
        for tid in list(self._after_ids):
            try:
                self.root.after_cancel(tid)
            except Exception:
                pass
        try:
            self.u32.DestroyWindow(self.hwnd)
        except Exception:
            pass
        try:
            self.k32.TerminateProcess(self.k32.GetCurrentProcess(), 0)
        except Exception:
            os._exit(0)

    # ------------------------------------------------------------ 监听
    def _start_listeners(self):
        self.kb_listener = keyboard.Listener(on_press=self._on_key_press,
                                             on_release=self._on_key_release)
        self.mouse_listener = mouse.Listener(on_click=self._on_mouse_click,
                                            on_scroll=self._on_mouse_scroll,
                                            on_move=self._on_mouse_move)
        self.kb_listener.daemon = True
        self.mouse_listener.daemon = True
        self.kb_listener.start()
        self.mouse_listener.start()
        self._install_enter_hook()

    def _install_enter_hook(self):
        self._enter_queue = []
        try:
            u32 = self.u32
            u32.SetWindowsHookExW.restype = ctypes.c_void_p
            u32.SetWindowsHookExW.argtypes = [ctypes.c_int, ctypes.c_void_p,
                                              ctypes.c_void_p, ctypes.c_uint32]
            u32.CallNextHookEx.restype = ctypes.c_long
            u32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                           ctypes.c_size_t, ctypes.c_void_p]
            self.k32.GetModuleHandleW.restype = ctypes.c_void_p
            hookproc = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int,
                                          ctypes.c_size_t, ctypes.c_void_p)
            self._hook_cb = hookproc(self._ll_hook)
            self._enter_hook = u32.SetWindowsHookExW(
                13, self._hook_cb, self.k32.GetModuleHandleW(None), 0)
        except Exception:
            self._enter_hook = None

    def _ll_hook(self, nCode, wParam, lParam):
        if nCode >= 0 and wParam in (0x0100, 0x0101):
            try:
                kb = ctypes.cast(lParam, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
                if kb.vkCode == 0x0D:
                    ext = bool(kb.flags & 0x01)
                    up = wParam == 0x0101
                    self._enter_queue.append((ext, up, time.time()))
                    if len(self._enter_queue) > 8:
                        self._enter_queue.pop(0)
            except Exception:
                pass
        try:
            return self.u32.CallNextHookEx(self._enter_hook, nCode, wParam, lParam)
        except Exception:
            return 0

    def _enter_code(self):
        now = time.time()
        while self._enter_queue and now - self._enter_queue[0][2] > 0.1:
            self._enter_queue.pop(0)
        if self._enter_queue:
            ext, _u, _t = self._enter_queue.pop(0)
            return "NumpadEnter" if ext else "Enter"
        return "Enter"

    def _key_info(self, key):
        code = key_to_code(key)
        disp = key_to_display(key)
        if key is keyboard.Key.enter:
            code = self._enter_code()
            disp = "小键盘回车" if code == "NumpadEnter" else "Enter"
        return code, disp

    def _on_key_press(self, key):
        if isinstance(key, keyboard.KeyCode) and key.char == "*":
            if any(k in self.pressed for k in _ALT_KEYS):
                self._after(0, self.toggle_recording)
                return
        if isinstance(key, keyboard.KeyCode) and key.char and key.char.lower() == "r":
            if (any(k in self.pressed for k in _CTRL_KEYS)
                    and any(k in self.pressed for k in _ALT_KEYS)):
                self._after(0, self.toggle_recording)
                return
        self.pressed.add(key)
        code, disp = self._key_info(key)
        self.event_queue.put(("key_press", code))
        if self.is_recording and code not in (None, "CapsLock", "NumLock"):
            self._record("keyboard", "press", key=disp, code=code)

    def _on_key_release(self, key):
        self.pressed.discard(key)
        code, disp = self._key_info(key)
        self.event_queue.put(("key_release", code))
        if self.is_recording and code not in (None, "CapsLock", "NumLock"):
            self._record("keyboard", "release", key=disp, code=code)

    def _on_mouse_click(self, x, y, button, pressed):
        btn = self._btn_index(button)
        self.event_queue.put(("mouse_down" if pressed else "mouse_up", btn))
        if self.is_recording:
            self._record("mouse", "down" if pressed else "up", button=btn, x=x, y=y)
        if button == mouse.Button.left:
            if pressed:
                self._route_click(x, y)
            else:
                self._drag_off = None

    def _to_content(self, x, y):
        return (x - (self.win_x + BORDER), y - (self.win_y + BORDER))

    def _hit_rect(self, name):
        if name == "start":
            return self._content_rect(BTN_START)
        if name == "download":
            return self._content_rect(BTN_DOWNLOAD)
        if name == "close":
            side = int(self.img_h * 0.135)
            return (self.img_w - side, 0, self.img_w, side)
        if name == "cog":
            cs = max(22, int(self.img_w * 0.045))
            cx, cy = self._cog_center()
            return (cx - cs // 2, cy - cs // 2, cx + cs // 2, cy + cs // 2)

    def _content_rect(self, pos):
        t, l, w, h = pos
        x1 = int(l / 100 * self.img_w); y1 = int(t / 100 * self.img_h)
        x2 = int((l + w) / 100 * self.img_w); y2 = int((t + h) / 100 * self.img_h)
        return (x1, y1, x2, y2)

    def _route_click(self, x, y):
        if not (self.win_x <= x <= self.win_x + self.win_w
                and self.win_y <= y <= self.win_y + self.win_h):
            return
        cx, cy = self._to_content(x, y)
        if self.click_through:
            if self._in_cog(cx, cy):
                self._after(0, self._toggle_settings)
            return
        for name in ("start", "download", "close"):
            x1, y1, x2, y2 = self._hit_rect(name)
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                self._hit_action(name)
                return
        if self._in_cog(cx, cy):
            self._after(0, self._toggle_settings)
            return
        if not self.pos_fixed:
            self._drag_off = (x - self.win_x, y - self.win_y)

    def _hit_action(self, name):
        if name == "start":
            self._after(0, self.toggle_recording)
        elif name == "download":
            self._after(0, self.export_record)
        elif name == "close":
            self._after(0, self._shutdown)
        elif name == "cog":
            self._after(0, self._toggle_settings)

    def _on_mouse_move(self, x, y):
        self.mouse_pos = (x, y)
        if self.click_through:
            return
        # 计算悬停热区（仅在窗口范围内）
        tag = None
        if (self.win_x <= x <= self.win_x + self.win_w
                and self.win_y <= y <= self.win_y + self.win_h):
            cx, cy = self._to_content(x, y)
            for name in ("start", "download", "close"):
                x1, y1, x2, y2 = self._hit_rect(name)
                if x1 <= cx <= x2 and y1 <= cy <= y2:
                    tag = name; break
            if tag is None and self._in_cog(cx, cy):
                tag = "cog"
        if tag != self._hover_tag:
            self._hover_tag = tag
            self._render()

    def _on_mouse_scroll(self, x, y, dx, dy):
        direction = "down" if dy < 0 else "up"
        self.event_queue.put(("mouse_scroll", direction))
        if self.is_recording:
            self._record("mouse", "scroll", direction=direction, x=x, y=y)

    def _btn_index(self, button):
        return {mouse.Button.left: 0, mouse.Button.middle: 1,
                mouse.Button.right: 2, mouse.Button.x1: 3,
                mouse.Button.x2: 4}.get(button, 0)

    # ------------------------------------------------------------ 记录
    def _record(self, kind, action, **kw):
        now = time.time()
        delay = now - self.last_event_time if self.last_event_time else 0.0
        self.last_event_time = now
        self.records.append({"type": kind, "action": action,
                             "timestamp": now - self.start_time, "delay": delay, **kw})

    def toggle_recording(self):
        if not self.is_recording:
            self.records = []
            self.start_time = time.time()
            self.last_event_time = 0.0
            self.is_recording = True
        else:
            self.is_recording = False
            self.dl_visible = True
        self._render()

    # ------------------------------------------------------------ 导出
    def export_record(self):
        if not self.records:
            self._show_notice("尚无记录")
            return
        lines = ["键鼠操作记录", "=" * 50,
                 "记录时间: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 "操作总数: %d" % len(self.records),
                 "=" * 50, ""]
        idx = 1
        for r in self.records:
            delay_ms = int(round(r["delay"] * 1000))
            if r["type"] == "keyboard":
                k = {"ArrowUp": "上", "ArrowDown": "下",
                     "ArrowLeft": "左", "ArrowRight": "右"}.get(r["key"], r["key"])
                lines.append("%d. %s：%s" % (idx, "按下" if r["action"] == "press" else "松开", k)); idx += 1
                lines.append("%d. 延迟：%dms" % (idx, delay_ms)); idx += 1
            else:
                if r["action"] == "scroll":
                    name = "滚轮上" if r["direction"] == "up" else "滚轮下"
                    lines.append("%d. %s" % (idx, name)); idx += 1
                else:
                    label = "按下" if r["action"] == "down" else "松开"
                    name = MOUSE_NAME.get(r["button"], "鼠标%d" % r["button"])
                    if r["button"] in (0, 2):
                        lines.append("%d. %s：%s（x%d，y%d）" % (idx, label, name, r["x"], r["y"]))
                    else:
                        lines.append("%d. %s：%s" % (idx, label, name))
                    idx += 1
                lines.append("%d. 延迟：%dms" % (idx, delay_ms)); idx += 1

        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fname = os.path.join(OUTPUT_DIR, "键鼠记录_%s.txt" % ts)
        with open(fname, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self._show_notice("已导出")

    # ------------------------------------------------------------ 可视化
    def _poll_events(self):
        try:
            while True:
                evt = self.event_queue.get_nowait()
                kind = evt[0]
                if kind == "key_press":
                    self._light(evt[1])
                elif kind == "key_release":
                    self._unlight(evt[1])
                elif kind == "mouse_down":
                    self._light_mouse(evt[1])
                elif kind == "mouse_up":
                    self._unlight_mouse(evt[1])
                elif kind == "mouse_scroll":
                    self._flash_wheel(evt[1])
        except queue.Empty:
            pass

        if self._drag_off is not None and not self.pos_fixed:
            pt = ctypes.wintypes.POINT()
            self.u32.GetCursorPos(ctypes.byref(pt))
            self._move_window(pt.x - self._drag_off[0], pt.y - self._drag_off[1])

        self._lock_tick += 1
        if self._lock_tick % 20 == 0:
            self._refresh_lock_states()

        # notice 过期重绘
        if self.notice_text and time.time() >= self.notice_until:
            self.notice_text = ""
            self._render()

        self._after(15, self._poll_events)

    def _light(self, code):
        if code is None:
            return
        if code in ("CapsLock", "NumLock"):
            self._refresh_lock_states()
            return
        if code not in self.lit:
            self.lit.add(code)
            self._render()

    def _unlight(self, code):
        if code in ("CapsLock", "NumLock"):
            return
        if code in self.lit:
            self.lit.discard(code)
            self._render()

    def _get_lock_state(self, vk):
        try:
            return bool(self.u32.GetKeyState(vk) & 1)
        except Exception:
            return False

    def _refresh_lock_states(self):
        for code, vk in (("CapsLock", VK_CAPITAL), ("NumLock", VK_NUMLOCK)):
            state = self._get_lock_state(vk)
            if self.lock_state.get(code) != state:
                self.lock_state[code] = state
                if state:
                    self.lit.add(code)
                else:
                    self.lit.discard(code)
                self._render()

    def _light_mouse(self, btn):
        code = {0: "MouseLeft", 1: "MouseWheel", 2: "MouseRight",
                3: "MouseSide2", 4: "MouseSide1"}.get(btn)
        if code and code not in self.lit:
            self.lit.add(code); self._render()

    def _unlight_mouse(self, btn):
        code = {0: "MouseLeft", 1: "MouseWheel", 2: "MouseRight",
                3: "MouseSide2", 4: "MouseSide1"}.get(btn)
        if code and code in self.lit:
            self.lit.discard(code); self._render()

    def _flash_wheel(self, direction):
        code = "MouseWheelUp" if direction == "up" else "MouseWheelDown"
        if code in self._wheel_timer:
            tid = self._wheel_timer.pop(code)
            try:
                self.root.after_cancel(tid)
            except Exception:
                pass
            self._after_ids.discard(tid)
        self.lit.add(code); self._render()
        self._wheel_timer[code] = self._after(150, lambda: self._clear_wheel(code))

    def _clear_wheel(self, code):
        self._wheel_timer.pop(code, None)
        self.lit.discard(code); self._render()


if __name__ == "__main__":
    if not os.path.exists(SVG_PATH):
        print("缺少 键鼠.svg，请放到脚本同目录。")
    else:
        KeyboardMouseViz()
