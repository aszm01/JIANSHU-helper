# -*- coding: utf-8 -*-
"""
键鼠操作可视化记录器（原生版 · 还原网页版样式）
================================================
功能：
  1. 全局捕获键盘 / 鼠标（切到任何软件都能感知）
  2. 右下角悬浮窗显示键盘鼠标底图，按键 / 鼠标操作时半透明绿色高亮
  3. “开始 / 停止录制”、“导出记录”按钮直接浮在底图上
用法：
  - 点击底图上“开始”按钮，或按热键 Alt+*（也支持 Ctrl+Alt+R）切换录制
  - 录制中按钮变绿；停止后出现蓝色“下载”按钮，点击导出 .txt 记录
  - 按住悬浮窗（非按钮区域）拖动可移动位置
依赖：pynput, pillow
"""

import os
import sys
import time
import queue
import datetime
import ctypes

import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from pynput import keyboard, mouse

# ---------------------------------------------------------------------------
# 路径：脚本目录（源码）/ exe 目录（打包后）
# ---------------------------------------------------------------------------
def app_dir():
    """导出文件应写入的目录：源码运行时在脚本目录，exe 运行时在 exe 所在目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(name):
    """查找资源：打包后从 _MEIPASS 取，源码运行则从脚本目录取。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


IMG_PATH = resource_path("初始.png")
OUTPUT_DIR = app_dir()

# 键鼠热区布局（百分比坐标，与原网页版一致）：(标识, 上, 左, 宽, 高)
KEY_LAYOUT = [
    # 功能键行
    ("Escape", 1.1, 0.2, 3.2, 12.2), ("F1", 1.1, 5.4, 3.2, 12.2),
    ("F2", 1.1, 9.7, 3.2, 12.2), ("F3", 1.1, 14.0, 3.2, 12.2),
    ("F4", 1.1, 18.3, 3.2, 12.2), ("F5", 1.1, 23.2, 3.2, 12.2),
    ("F6", 1.1, 27.4, 3.2, 12.2), ("F7", 1.1, 31.7, 3.2, 12.2),
    ("F8", 1.1, 36.0, 3.2, 12.2), ("F9", 1.1, 40.9, 3.2, 12.2),
    ("F10", 1.1, 45.2, 3.2, 12.2), ("F11", 1.1, 49.5, 3.2, 12.2),
    ("F12", 1.1, 53.8, 3.2, 12.2), ("Delete", 1.1, 58.7, 4.4, 12.2),
    # 数字键行
    ("Backquote", 18.6, 0.2, 3.2, 12.2), ("Digit1", 18.6, 4.5, 3.2, 12.2),
    ("Digit2", 18.6, 8.7, 3.2, 12.2), ("Digit3", 18.6, 13.0, 3.2, 12.2),
    ("Digit4", 18.6, 17.2, 3.2, 12.2), ("Digit5", 18.6, 21.5, 3.2, 12.2),
    ("Digit6", 18.6, 25.8, 3.2, 12.2), ("Digit7", 18.6, 30.1, 3.2, 12.2),
    ("Digit8", 18.6, 34.3, 3.2, 12.2), ("Digit9", 18.6, 38.6, 3.2, 12.2),
    ("Digit0", 18.6, 42.9, 3.2, 12.2), ("Minus", 18.6, 47.1, 3.2, 12.2),
    ("Equal", 18.6, 51.4, 3.2, 12.2), ("Backspace", 18.6, 55.6, 7.6, 12.2),
    # QWERTY 行
    ("Tab", 35.6, 0.2, 5.8, 12.2), ("KeyQ", 35.6, 7.1, 3.2, 12.2),
    ("KeyW", 35.6, 11.3, 3.2, 12.2), ("KeyE", 35.6, 15.6, 3.2, 12.2),
    ("KeyR", 35.6, 19.9, 3.2, 12.2), ("KeyT", 35.6, 24.2, 3.2, 12.2),
    ("KeyY", 35.6, 28.5, 3.2, 12.2), ("KeyU", 35.6, 32.7, 3.2, 12.2),
    ("KeyI", 35.6, 37.0, 3.2, 12.2), ("KeyO", 35.6, 41.2, 3.2, 12.2),
    ("KeyP", 35.6, 45.5, 3.2, 12.2), ("BracketLeft", 35.6, 49.7, 3.2, 12.2),
    ("BracketRight", 35.6, 54.0, 3.2, 12.2), ("Backslash", 35.6, 58.2, 5.0, 12.2),
    # ASDF 行
    ("CapsLock", 52.4, 0.2, 6.8, 12.2), ("KeyA", 52.4, 8.0, 3.2, 12.2),
    ("KeyS", 52.4, 12.3, 3.2, 12.2), ("KeyD", 52.4, 16.6, 3.2, 12.2),
    ("KeyF", 52.4, 20.9, 3.2, 12.2), ("KeyG", 52.4, 25.2, 3.2, 12.2),
    ("KeyH", 52.4, 29.4, 3.2, 12.2), ("KeyJ", 52.4, 33.7, 3.2, 12.2),
    ("KeyK", 52.4, 38.0, 3.2, 12.2), ("KeyL", 52.4, 42.2, 3.2, 12.2),
    ("Semicolon", 52.4, 46.5, 3.2, 12.2), ("Quote", 52.4, 50.7, 3.2, 12.2),
    ("Enter", 52.4, 54.9, 8.3, 12.2),
    # ZXCV 行
    ("ShiftLeft", 69.4, 0.2, 8.6, 12.2), ("KeyZ", 69.4, 9.7, 3.2, 12.2),
    ("KeyX", 69.4, 14.0, 3.2, 12.2), ("KeyC", 69.4, 18.2, 3.2, 12.2),
    ("KeyV", 69.4, 22.5, 3.2, 12.2), ("KeyB", 69.4, 26.7, 3.2, 12.2),
    ("KeyN", 69.4, 31.0, 3.2, 12.2), ("KeyM", 69.4, 35.2, 3.2, 12.2),
    ("Comma", 69.4, 39.5, 3.2, 12.2), ("Period", 69.4, 43.8, 3.2, 12.2),
    ("Slash", 69.4, 48.1, 3.2, 12.2), ("ShiftRight", 69.4, 52.2, 11.1, 12.2),
    # 控制行
    ("ControlLeft", 86.4, 0.2, 5.9, 12.2), ("MetaLeft", 86.4, 7.1, 3.2, 12.2),
    ("AltLeft", 86.4, 11.3, 5.9, 12.2), ("Space", 86.4, 17.5, 32.6, 12.2),
    ("AltRight", 86.4, 50.4, 4.3, 12.2), ("ControlRight", 86.4, 55.6, 3.2, 12.2),
    # 方向键
    ("ArrowUp", 69.4, 65.2, 3.2, 12.2), ("ArrowLeft", 86.4, 60.8, 3.2, 12.2),
    ("ArrowDown", 86.4, 65.2, 3.2, 12.2), ("ArrowRight", 86.4, 69.5, 3.2, 12.2),
    # 小键盘
    ("NumLock", 18.6, 70.4, 3.2, 12.2), ("NumpadDivide", 18.6, 74.7, 3.2, 12.2),
    ("NumpadMultiply", 18.6, 78.9, 3.2, 12.2), ("NumpadSubtract", 18.6, 83.2, 3.2, 12.2),
    ("Numpad7", 35.6, 70.4, 3.2, 12.2), ("Numpad8", 35.6, 74.7, 3.2, 12.2),
    ("Numpad9", 35.6, 78.9, 3.2, 12.2), ("NumpadAdd", 35.2, 83.2, 3.2, 29.9),
    ("Numpad4", 52.4, 70.4, 3.2, 12.2), ("Numpad5", 52.4, 74.7, 3.2, 12.2),
    ("Numpad6", 52.4, 78.9, 3.2, 12.2),
    ("Numpad1", 69.4, 70.4, 3.2, 12.2), ("Numpad2", 69.4, 74.7, 3.2, 12.2),
    ("Numpad3", 69.4, 78.9, 3.2, 12.2), ("NumpadEnter", 69.0, 83.2, 3.2, 29.9),
    ("Numpad0", 86.4, 74.7, 3.2, 12.2), ("NumpadDecimal", 86.4, 78.9, 3.2, 12.2),
    # 鼠标按钮
    ("MouseLeft", 26.0, 90.0, 4.0, 25.0),
    ("MouseRight", 26.0, 95.0, 4.0, 25.0),
    ("MouseWheelUp", 27.4, 94.1, 0.8, 4.2),
    ("MouseWheel", 32.5, 94.1, 0.8, 5.6),
    ("MouseWheelDown", 39.0, 94.1, 0.8, 4.5),
    ("MouseSide1", 47.2, 88.5, 0.7, 7.3),
    ("MouseSide2", 55.4, 88.5, 0.7, 7.5),
]

# 控制按钮 / 提示框在底图上的位置（百分比）
# 开始：对齐 NumLock 左边 -> NumpadDivide 右边
# 下载：对齐 NumpadMultiply 左边 -> NumpadSubtract 右边
BTN_START = (1.1, 70.4, 7.5, 13.5)      # 开始/停止
BTN_DOWNLOAD = (1.1, 78.9, 7.5, 13.5)   # 导出
# 完成提示：放在下载按钮右侧，间距与"开始→下载"相同，尺寸与下载按钮相同
_BTN_GAP = BTN_DOWNLOAD[1] - (BTN_START[1] + BTN_START[2])
NOTICE = (1.1, BTN_DOWNLOAD[1] + BTN_DOWNLOAD[2] + _BTN_GAP, BTN_DOWNLOAD[2], BTN_DOWNLOAD[3])

# 悬浮窗宽度为屏幕宽度的几分之一（与网页版一致：屏幕宽度的 1/4）
WIDTH_DIVISOR = 4

# 锁定键虚拟键码（用于读取真实开关状态）
VK_CAPITAL = 0x14   # CapsLock
VK_NUMLOCK = 0x90   # NumLock

# 字符 -> 标识
CHAR_MAP = {str(i): "Digit%d" % i for i in range(10)}
CHAR_MAP.update({ch: "Key" + ch.upper() for ch in "abcdefghijklmnopqrstuvwxyz"})
CHAR_MAP.update({
    "`": "Backquote", "-": "Minus", "=": "Equal",
    "[": "BracketLeft", "]": "BracketRight", "\\": "Backslash",
    ";": "Semicolon", "'": "Quote", ",": "Comma", ".": "Period", "/": "Slash",
    " ": "Space",
})

# 特殊键 -> 标识
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
# 左修饰键：Windows 上 pynput 上报的是 ctrl_l / alt_l / shift_l / cmd_l（实测确认），
# 必须补上映射，否则左 Ctrl / 左 Alt / 左 Shift / 左 Win 不点亮也不记录。
for _kname, _code in (("shift_l", "ShiftLeft"), ("ctrl_l", "ControlLeft"),
                      ("alt_l", "AltLeft"), ("cmd_l", "MetaLeft")):
    _k = getattr(keyboard.Key, _kname, None)
    if _k is not None:
        KEY_MAP[_k] = _code

# 热键判定的修饰键集合（兼容 ctrl/ctrl_l/ctrl_r 等全部变体）
_ALT_KEYS = tuple(k for k in (getattr(keyboard.Key, n, None)
                              for n in ("alt", "alt_l", "alt_r", "alt_gr")) if k is not None)
_CTRL_KEYS = tuple(k for k in (getattr(keyboard.Key, n, None)
                               for n in ("ctrl", "ctrl_l", "ctrl_r")) if k is not None)

# 小键盘虚拟键码 -> 标识
NUMPAD_VK = {
    0x60: "Numpad0", 0x61: "Numpad1", 0x62: "Numpad2", 0x63: "Numpad3",
    0x64: "Numpad4", 0x65: "Numpad5", 0x66: "Numpad6", 0x67: "Numpad7",
    0x68: "Numpad8", 0x69: "Numpad9", 0x6A: "NumpadMultiply",
    0x6B: "NumpadAdd", 0x6D: "NumpadSubtract", 0x6E: "NumpadDecimal",
    0x6F: "NumpadDivide",
}

MOUSE_NAME = {0: "鼠标左", 1: "鼠标中", 2: "鼠标右", 3: "侧键后", 4: "侧键前"}

# 小键盘键位的中文显示名（供记录导出用）
NUMPAD_DISPLAY = {
    "Numpad0": "小键盘0", "Numpad1": "小键盘1", "Numpad2": "小键盘2",
    "Numpad3": "小键盘3", "Numpad4": "小键盘4", "Numpad5": "小键盘5",
    "Numpad6": "小键盘6", "Numpad7": "小键盘7", "Numpad8": "小键盘8",
    "Numpad9": "小键盘9", "NumpadMultiply": "小键盘*", "NumpadAdd": "小键盘+",
    "NumpadSubtract": "小键盘-", "NumpadDecimal": "小键盘.", "NumpadDivide": "小键盘/",
}


# 低级键盘钩子事件结构（区分主键盘/小键盘回车用）
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
    # 小键盘数字/符号：pynput 上报 KeyCode(vk=0x60-0x6F, char=None)，必须按 vk 映射，
    # 否则记录里显示为 "?"
    if vk is not None and 0x60 <= vk <= 0x6F:
        code = NUMPAD_VK.get(vk)
        if code:
            return NUMPAD_DISPLAY.get(code, code)
    return ch if ch else "?"


class KeyboardMouseViz:
    def __init__(self):
        self._set_dpi_aware()
        self.root = tk.Tk()
        self.root.title("录屏键鼠助手")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#ffffff")
        self.root.option_add("*Font", ("Microsoft YaHei", 10))   # 全局默认字体：微软雅黑

        self.records = []
        self.is_recording = False
        self.start_time = 0.0
        self.last_event_time = 0.0

        self.event_queue = queue.Queue()
        self.hl_tiles = {}     # code -> (点亮图 PhotoImage, x, y)
        self.hl_items = {}     # code -> canvas 图项 id
        self._wheel_timer = {}
        self.pressed = set()
        self.lock_state = {}
        self._drag_off = None
        self._after_ids = set()
        self._lock_tick = 0
        self._hover_bg = {}
        self._hover_icons = {}

        self._build_ui()
        self._start_listeners()
        self._refresh_lock_states()
        self._after(15, self._poll_events)
        try:
            self.root.mainloop()
        except Exception:
            pass
        # 兜底：主循环结束（含 Alt+F4 / 系统关窗）时也执行清理，避免 Tcl 内存错误
        self._shutdown()

    # ------------------------------------------------------------- DPI/位置
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

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        img = Image.open(IMG_PATH).convert("RGBA")
        self.img_w = self.root.winfo_screenwidth() // WIDTH_DIVISOR
        self.img_h = int(self.img_w * img.height / img.width)
        # 底图（含透明通道）；按键高亮通过 alpha 合成到这张图上，实现真正半透明
        self.base_rgba = img.resize((self.img_w, self.img_h), Image.LANCZOS)
        self.current_photo = ImageTk.PhotoImage(self.base_rgba)

        wa = self._work_area()
        # 四周 3px 纯白边框：窗口外扩 6px，画布 pack 留白露出根窗口白底
        BORDER = 3
        win_w = self.img_w + BORDER * 2
        win_h = self.img_h + BORDER * 2
        pos_x = wa[0] + wa[2] - win_w - 12
        pos_y = wa[1] + wa[3] - win_h - 12
        self.root.geometry("%dx%d+%d+%d" % (win_w, win_h, pos_x, pos_y))

        self.canvas = tk.Canvas(self.root, width=self.img_w, height=self.img_h,
                                bg="#ffffff", highlightthickness=0, bd=0)
        self.bg_item = self.canvas.create_image(0, 0, anchor="nw", image=self.current_photo)
        self._prepare_tiles()
        self.canvas.pack(padx=BORDER, pady=BORDER)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)

        # 按钮字体：加粗、按窗口高度自适应（1/4 尺寸下保持可读）
        self.font = ("Microsoft YaHei", max(9, int(self.img_h * 0.075)), "bold")
        self._build_controls()

    def _build_controls(self):
        self.start_rect, self.start_text = self._button(BTN_START, "开始", "#f44336", "start")
        self.dl_rect, self.dl_text = self._button(BTN_DOWNLOAD, "下载", "#2196F3", "download")
        self._hide_download()

        # 关闭（Windows 风格 X：正方形，长=高，悬停红底白 X，独立设计不受开始/下载影响）
        side = int(self.img_h * 0.135)                    # 正方形边长（像素）
        side_pct = side / self.img_w * 100.0              # 换算成宽度百分比
        self.close_bg, self.close_icons = self._icon_button(
            (1.0, 100.0 - side_pct, side_pct, 13.5), "close", "close")

        top, left, w, h = NOTICE
        x1 = left / 100 * self.img_w; y1 = top / 100 * self.img_h
        x2 = (left + w) / 100 * self.img_w; y2 = (top + h) / 100 * self.img_h
        self.notice = self.canvas.create_rectangle(x1, y1, x2, y2, fill="#4CAF50", outline="", tags="notice")
        self.notice_text = self.canvas.create_text(
            (x1 + x2) / 2, (y1 + y2) / 2, text="", fill="white",
            font=("Microsoft YaHei", max(8, int(self.img_h * 0.05)), "bold"), tags="notice")
        self.canvas.itemconfigure("notice", state="hidden")

    def _button(self, pos, text, color, tag):
        top, left, w, h = pos
        x1 = left / 100 * self.img_w; y1 = top / 100 * self.img_h
        x2 = (left + w) / 100 * self.img_w; y2 = (top + h) / 100 * self.img_h
        rect = self._round_rect(x1, y1, x2, y2, radius=min(8, (y2 - y1) / 2),
                                fill=color, outline="", tags=tag)
        txt = self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=text,
                                      fill="white", font=self.font, tags=tag)
        self.canvas.tag_bind(tag, "<Button-1>", lambda e: self._on_control(tag))
        return rect, txt

    def _icon_button(self, pos, kind, tag):
        """Windows 标题栏风格图标按钮：默认无底色，悬停出现底色（关闭为红底白 X）。"""
        top, left, w, h = pos
        x1 = left / 100 * self.img_w; y1 = top / 100 * self.img_h
        x2 = (left + w) / 100 * self.img_w; y2 = (top + h) / 100 * self.img_h
        cx = (x1 + x2) / 2; cy = (y1 + y2) / 2
        bw = x2 - x1; bh = y2 - y1

        # 整块按钮热区（默认透明，悬停时改为底色；fill="" 仍可命中鼠标事件）
        hover = self.canvas.create_rectangle(x1, y1, x2, y2,
                                             fill="", outline="", tags=tag)

        # X：两条交叉线（正方形按钮内）
        padx, pady = bw * 0.24, bh * 0.24
        lw = max(2, int(bh * 0.075))
        icons = []
        icons.append(self.canvas.create_line(x1 + padx, y1 + pady, x2 - padx, y2 - pady,
                                             fill="#333333", width=lw, tags=tag))
        icons.append(self.canvas.create_line(x2 - padx, y1 + pady, x1 + padx, y2 - pady,
                                             fill="#333333", width=lw, tags=tag))

        self.canvas.tag_bind(tag, "<Enter>", lambda e: self._hover_on(tag))
        self.canvas.tag_bind(tag, "<Leave>", lambda e: self._hover_off(tag))
        self.canvas.tag_bind(tag, "<Button-1>", lambda e: self._on_control(tag))

        self._hover_bg[tag] = hover
        self._hover_icons[tag] = icons
        return hover, icons

    def _hover_on(self, tag):
        if tag == "close":
            self.canvas.itemconfigure(self._hover_bg[tag], fill="#e81123")
            for it in self._hover_icons[tag]:
                self.canvas.itemconfigure(it, fill="#ffffff")

    def _hover_off(self, tag):
        if tag == "close":
            self.canvas.itemconfigure(self._hover_bg[tag], fill="")
            for it in self._hover_icons[tag]:
                self.canvas.itemconfigure(it, fill="#333333")

    def _on_control(self, tag):
        if tag == "start":
            self.toggle_recording()
        elif tag == "download":
            self.export_record()
        elif tag == "close":
            self._shutdown()

    def _round_rect(self, x1, y1, x2, y2, radius, **kw):
        r = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r,
               x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r,
               x1, y1 + r, x1, y1]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    def _show_download(self):
        self.canvas.itemconfigure("download", state="normal")

    def _hide_download(self):
        self.canvas.itemconfigure("download", state="hidden")

    def _show_notice(self, text, color="#4CAF50"):
        self.canvas.itemconfigure("notice", state="normal")
        self.canvas.itemconfigure(self.notice, fill=color)
        self.canvas.itemconfigure(self.notice_text, text=text)
        self._after(2500, lambda: self.canvas.itemconfigure("notice", state="hidden"))

    # ------------------------------------------------------------------ 拖动
    def _on_press(self, e):
        # 点到按钮时不触发拖动（底图本身无标签，可正常拖动）
        cur = self.canvas.find_withtag("current")
        if cur and set(self.canvas.gettags(cur[0])) & {"start", "download", "close"}:
            return
        self._drag_off = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def _on_drag(self, e):
        if self._drag_off is None:
            return
        self.root.geometry("+%d+%d" % (e.x_root - self._drag_off[0], e.y_root - self._drag_off[1]))

    # ------------------------------------------------------------------ 关闭清理
    def _after(self, ms, func):
        """注册 after 回调并记录 id，便于关闭时统一取消，避免回调访问已销毁的控件。"""
        def _run(tid):
            self._after_ids.discard(tid)
            func()
        tid = self.root.after(ms, lambda: _run(tid))
        self._after_ids.add(tid)
        return tid

    def _shutdown(self):
        """干净退出：停监听 -> 取消挂起回调 -> 释放全部画布图项与图片引用 -> 立即终止进程。

        不调用 root.destroy() / 不进入 Tcl 终结逻辑：Windows 下 Tk 销毁阶段访问已释放的
        PhotoImage 会触发 "alloc: invalid block" 崩溃弹窗；退出用 TerminateProcess 裸终止，
        瞬时关闭且不再触发任何崩溃路径。
        """
        try:
            self.kb_listener.stop()
        except Exception:
            pass
        try:
            self.mouse_listener.stop()
        except Exception:
            pass
        for tid in list(self._after_ids):
            try:
                self.root.after_cancel(tid)
            except Exception:
                pass
        self._after_ids.clear()
        try:
            # 删除画布上所有图项（底图 + 全部点亮图 + 按钮），避免销毁时引用已释放图片
            self.canvas.delete("all")
        except Exception:
            pass
        self.hl_tiles.clear()
        self.hl_items.clear()
        self.current_photo = None
        try:
            self.root.quit()
        except Exception:
            pass
        # 立即终止进程：跳过 Tcl/CRT 终结与 DLL 卸载回调。
        # 打包成 exe 后 os._exit 会因 DLL 卸载回调阻塞约 2.5 秒（窗口迟迟不关），
        # TerminateProcess 不做任何清理、由内核直接销毁窗口，瞬时关闭。
        # 此时监听已停、画布已清、无未保存数据，裸终止是安全的。
        try:
            _kernel32 = ctypes.windll.kernel32
            # 必须声明 argtypes：伪句柄 -1 按 64 位句柄传递，否则 32 位截断导致调用失败
            _kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            _kernel32.TerminateProcess.restype = ctypes.c_int
            _kernel32.GetCurrentProcess.restype = ctypes.c_void_p
            _kernel32.TerminateProcess(_kernel32.GetCurrentProcess(), 0)
        except Exception:
            os._exit(0)

    # ------------------------------------------------------------------ 监听
    def _start_listeners(self):
        self.kb_listener = keyboard.Listener(on_press=self._on_key_press, on_release=self._on_key_release)
        self.mouse_listener = mouse.Listener(on_click=self._on_mouse_click, on_scroll=self._on_mouse_scroll)
        self.kb_listener.daemon = True
        self.mouse_listener.daemon = True
        self.kb_listener.start()
        self.mouse_listener.start()
        self._install_enter_hook()

    def _install_enter_hook(self):
        """安装低级键盘钩子，仅用于区分主键盘回车与小键盘回车。

        pynput 在 Windows 上把两者都上报为 Key.enter，无法区分；低级钩子事件的
        KBDLLHOOKSTRUCT.flags 含 LLKHF_EXTENDED(0x01)，小键盘回车带此标志。
        """
        self._enter_queue = []
        try:
            u32 = ctypes.windll.user32
            self._kuser32 = u32
            # 64 位系统必须声明完整签名，否则句柄被 32 位截断导致安装失败（返回 0）
            u32.SetWindowsHookExW.restype = ctypes.c_void_p
            u32.SetWindowsHookExW.argtypes = [ctypes.c_int, ctypes.c_void_p,
                                              ctypes.c_void_p, ctypes.c_uint32]
            u32.CallNextHookEx.restype = ctypes.c_long
            u32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                           ctypes.c_size_t, ctypes.c_void_p]
            # GetModuleHandleW 在 kernel32（user32 无此导出）
            k32 = ctypes.windll.kernel32
            k32.GetModuleHandleW.restype = ctypes.c_void_p
            _HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int,
                                           ctypes.c_size_t, ctypes.c_void_p)
            self._llhook_cb = _HOOKPROC(self._ll_hook)
            self._enter_hook = u32.SetWindowsHookExW(
                13, self._llhook_cb, k32.GetModuleHandleW(None), 0)
        except Exception:
            self._enter_hook = None

    def _ll_hook(self, nCode, wParam, lParam):
        if nCode >= 0 and wParam in (0x0100, 0x0101):  # WM_KEYDOWN / WM_KEYUP
            try:
                kb = ctypes.cast(lParam, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
                if kb.vkCode == 0x0D:  # VK_RETURN
                    ext = bool(kb.flags & 0x01)  # LLKHF_EXTENDED -> 小键盘回车
                    up = wParam == 0x0101
                    self._enter_queue.append((ext, up, time.time()))
                    if len(self._enter_queue) > 8:
                        self._enter_queue.pop(0)
            except Exception:
                pass
        try:
            return self._kuser32.CallNextHookEx(self._enter_hook, nCode, wParam, lParam)
        except Exception:
            return 0
    def _enter_code(self):
        """取出最近一次回车事件：扩展键（小键盘）返回 NumpadEnter，否则 Enter。"""
        now = time.time()
        while self._enter_queue and now - self._enter_queue[0][2] > 0.1:
            self._enter_queue.pop(0)
        if self._enter_queue:
            ext, _up, _ts = self._enter_queue.pop(0)
            return "NumpadEnter" if ext else "Enter"
        return "Enter"

    def _key_info(self, key):
        """返回 (code, display)。回车做扩展键区分，其余走既有映射。"""
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

    def _on_mouse_scroll(self, x, y, dx, dy):
        direction = "down" if dy < 0 else "up"
        self.event_queue.put(("mouse_scroll", direction))
        if self.is_recording:
            self._record("mouse", "scroll", direction=direction, x=x, y=y)

    def _btn_index(self, button):
        return {mouse.Button.left: 0, mouse.Button.middle: 1,
                mouse.Button.right: 2, mouse.Button.x1: 3,
                mouse.Button.x2: 4}.get(button, 0)

    # ------------------------------------------------------------------ 记录
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
            self.canvas.itemconfigure(self.start_rect, fill="#43a047")
            self.canvas.itemconfigure(self.start_text, text="录制")
        else:
            self.is_recording = False
            self.canvas.itemconfigure(self.start_rect, fill="#f44336")
            self.canvas.itemconfigure(self.start_text, text="开始")
            self._show_download()

    # ------------------------------------------------------------------ 导出
    def export_record(self):
        if not self.records:
            self._show_notice("尚无记录", "#ffb74d")
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
        self._show_notice("已导出", "#4CAF50")

    # ------------------------------------------------------------------ 可视化
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
        # 定时刷新 CapsLock / NumLock 真实开关状态（约每 300ms 一次）
        self._lock_tick += 1
        if self._lock_tick % 20 == 0:
            self._refresh_lock_states()
        self._after(15, self._poll_events)

    def _prepare_tiles(self):
        """启动时预合成每个键位的“点亮图”：底图区域 + 60% 绿色，运行时零合成、零延迟。

        键盘键的亮点区域比热点矩形向外扩 1~2px（实测键帽比热点高约 2~3px，热点顶部/底部
        会露出键帽原色，形成“白条”），扩边后点亮图完整盖住键帽；行间距约 5px，不会串行。
        """
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
            crop = self.base_rgba.crop((x0, y0, x1, y1))
            ov = Image.new("RGBA", crop.size, (0, 0, 0, 0))
            ImageDraw.Draw(ov).rounded_rectangle([0, 0, x1 - x0, y1 - y0], radius=radius,
                                                 fill=(76, 175, 80, 153))  # rgba(76,175,80,0.6)
            self.hl_tiles[c] = (ImageTk.PhotoImage(Image.alpha_composite(crop, ov)), x0, y0)

    def _draw(self, code):
        if code is None or code in self.hl_items:
            return
        tile = self.hl_tiles.get(code)
        if tile is None:
            return
        photo, x, y = tile
        self.hl_items[code] = self.canvas.create_image(x, y, anchor="nw", image=photo)

    def _clear(self, code):
        item = self.hl_items.pop(code, None)
        if item is not None:
            self.canvas.delete(item)

    def _light(self, code):
        if code is None:
            return
        if code in ("CapsLock", "NumLock"):
            self._refresh_lock_states()
            return
        self._draw(code)

    def _get_lock_state(self, vk):
        """读取锁定键真实状态（须在主线程调用，Tk 有消息泵）。"""
        try:
            return bool(ctypes.windll.user32.GetKeyState(vk) & 1)
        except Exception:
            return False

    def _refresh_lock_states(self):
        for code, vk in (("CapsLock", VK_CAPITAL), ("NumLock", VK_NUMLOCK)):
            state = self._get_lock_state(vk)
            if self.lock_state.get(code) != state:
                self.lock_state[code] = state
                if state:
                    self._draw(code)
                else:
                    self._clear(code)

    def _unlight(self, code):
        if code in ("CapsLock", "NumLock"):
            return
        self._clear(code)

    def _light_mouse(self, btn):
        code = {0: "MouseLeft", 1: "MouseWheel", 2: "MouseRight",
                3: "MouseSide2", 4: "MouseSide1"}.get(btn)
        if code:
            self._draw(code)

    def _unlight_mouse(self, btn):
        code = {0: "MouseLeft", 1: "MouseWheel", 2: "MouseRight",
                3: "MouseSide2", 4: "MouseSide1"}.get(btn)
        if code:
            self._clear(code)

    def _flash_wheel(self, direction):
        code = "MouseWheelUp" if direction == "up" else "MouseWheelDown"
        if code in self._wheel_timer:
            tid = self._wheel_timer.pop(code)
            try:
                self.root.after_cancel(tid)
            except Exception:
                pass
            self._after_ids.discard(tid)
        self._draw(code)
        self._wheel_timer[code] = self._after(150, lambda: self._clear_wheel(code))

    def _clear_wheel(self, code):
        self._wheel_timer.pop(code, None)
        self._clear(code)


if __name__ == "__main__":
    if not os.path.exists(IMG_PATH):
        print("缺少底图 初始.png，请放到脚本同目录。")
    else:
        KeyboardMouseViz()
