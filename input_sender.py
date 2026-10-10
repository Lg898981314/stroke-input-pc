"""
输入发送器
- 把选中的汉字复制到剪贴板
- 模拟 Ctrl+V 把内容粘贴到当前焦点窗口
- 发送退格键（用 keybd_event，配合临时状态避免被钩子拦截）
"""

from __future__ import annotations

import time
import threading

import pyperclip
from pynput.keyboard import Controller, Key
import ctypes


class InputSender:
    """把字符发送到当前焦点窗口"""

    def __init__(self) -> None:
        self._kb = Controller()
        self._lock = threading.Lock()
        # 保存原始剪贴板内容，便于粘贴后恢复
        self._saved_clipboard: str | None = None

    def commit(self, text: str) -> None:
        """把 text 粘贴到当前焦点窗口"""
        if not text:
            return
        with self._lock:
            self._do_commit(text)

    def send_backspace(self, count: int = 1) -> None:
        """发送退格键到当前焦点窗口（用 keybd_event）"""
        if count <= 0:
            return
        with self._lock:
            user32 = ctypes.windll.user32
            VK_BACK = 0x08
            KEYEVENTF_KEYUP = 0x0002
            for _ in range(count):
                user32.keybd_event(VK_BACK, 0, 0, 0)
                user32.keybd_event(VK_BACK, 0, KEYEVENTF_KEYUP, 0)
                time.sleep(0.01)

    def _do_commit(self, text: str) -> None:
        # 备份原剪贴板（失败不致命）
        try:
            self._saved_clipboard = pyperclip.paste()
        except Exception:
            self._saved_clipboard = None

        try:
            pyperclip.copy(text)
        except Exception as e:
            print(f"[input_sender] 复制失败: {e}")
            return

        # 略微等待剪贴板就绪
        time.sleep(0.02)

        # 模拟 Ctrl+V
        try:
            with self._kb.pressed(Key.ctrl):
                self._kb.press("v")
                self._kb.release("v")
        except Exception as e:
            print(f"[input_sender] Ctrl+V 模拟失败: {e}")
            # 兜底：直接键入字符（中文效果一般，但至少不报错）
            try:
                self._kb.type(text)
            except Exception:
                pass

        # 等粘贴完成
        time.sleep(0.05)

        # 恢复原剪贴板
        if self._saved_clipboard is not None:
            try:
                pyperclip.copy(self._saved_clipboard)
            except Exception:
                pass
