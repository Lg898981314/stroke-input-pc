"""
全局键盘钩子（Win32 WH_KEYBOARD_LL）
- 直接用 ctypes 调用 Windows 低级键盘钩子
- 可以选择性地拦截按键，让被拦截的按键不传到当前焦点窗口
- 未被拦截的按键照常传递给系统

按键事件分类：
    type:
        'numpad_digit' (value=0..9)    - NumPad 数字键
        'top_digit'    (value=1..10)   - 主键盘字母上方数字键 (10 表示 0)
        'space' / 'enter' / 'backspace' / 'escape' / 'f2'
        'page_up' / 'page_down'
        'minus' / 'equal'              - 主键盘 - 和 =
        'other'
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable, Dict, Optional

# ===== Win32 常量 =====
WH_KEYBOARD_LL = 13
HC_ACTION = 0

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# VK_xxx
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12       # Alt
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_PRIOR = 0x21      # PageUp
VK_NEXT = 0x22       # PageDown
VK_F2 = 0x71

VK_NUMPAD0 = 0x60
VK_NUMPAD9 = 0x69
VK_OEM_MINUS = 0xBD
VK_OEM_PLUS = 0xBB

VK_0 = 0x30
VK_9 = 0x39

# 反引号键（`~），在美式键盘上是 VK_OEM_3 (0xC0)
VK_OEM_3 = 0xC0


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


# WINFUNCTYPE（stdcall 调用约定）必须用在模块级声明，否则被 GC 会崩溃
HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long,        # LRESULT
    ctypes.c_int,         # int nCode
    wintypes.WPARAM,      # WPARAM
    wintypes.LPARAM,      # LPARAM
)


class KeyboardHook:
    """Win32 低级键盘钩子，选择性拦截按键"""

    def __init__(self, on_key_event: Callable[[dict], bool]) -> None:
        """
        on_key_event 接收事件 dict（字段见模块注释），返回 True 表示要拦截此按键
        （让它不到达当前焦点窗口），返回 False 表示放行。
        """
        self._callback = on_key_event
        self._hook: Optional[int] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        # 钩子函数对象必须保存引用避免被 GC
        self._hook_proc: Optional[HOOKPROC] = None
        # 强制拦截的 VK 码集合（在钩子层直接拦，不经过回调）
        self._force_block_vks: set = set()
        self._enabled: bool = True  # 输入法是否激活（决定是否强制拦截）

    # ---------- 启动 / 停止 ----------

    def set_enabled(self, enabled: bool) -> None:
        """设置输入法是否激活（影响强制拦截）"""
        self._enabled = enabled

    def set_force_block_vks(self, vks: set) -> None:
        """设置需要强制拦截的 VK 码集合（在钩子层直接拦截）"""
        self._force_block_vks = set(vks)

    def start(self) -> None:
        """在独立线程中启动钩子（有自己的消息循环）"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._message_loop, daemon=True)
        self._thread.start()

    def start_in_main_thread(self) -> None:
        """
        在当前线程（通常是 Qt 主线程）中安装钩子。
        调用者的线程必须有消息循环（如 Qt 的 app.exec_()）。
        这种方式更稳定，因为系统直接利用主线程的消息循环调度钩子。
        """
        if self._running:
            return
        self._running = True
        # 直接在当前线程安装钩子，不创建新线程
        # 钩子过程会在当前线程的消息循环中被调用
        self._install_hook()

    def stop(self) -> None:
        self._running = False
        if self._hook is not None:
            user32 = ctypes.windll.user32
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
        # 如果是独立线程模式，向钩子线程投递 WM_QUIT 唤醒退出
        if self._thread is not None and self._thread.ident is not None:
            user32 = ctypes.windll.user32
            # PostThreadMessageW 需要线程 ID
            WM_QUIT = 0x0012
            user32.PostThreadMessageW(self._thread.ident, WM_QUIT, 0, 0)
            self._thread.join(timeout=2.0)
            self._thread = None

    # ---------- 消息循环 ----------

    def _install_hook(self) -> None:
        """安装键盘钩子（在当前线程）"""
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # 声明 SetWindowsHookExW 的参数类型
        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int,        # idHook
            HOOKPROC,            # lpfn
            wintypes.HINSTANCE,  # hmod
            wintypes.DWORD,      # dwThreadId
        ]
        user32.SetWindowsHookExW.restype = wintypes.HHOOK

        user32.CallNextHookEx.argtypes = [
            wintypes.HHOOK,      # hhk
            ctypes.c_int,        # nCode
            wintypes.WPARAM,     # wParam
            wintypes.LPARAM,     # lParam
        ]
        user32.CallNextHookEx.restype = ctypes.c_long  # LRESULT

        user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL

        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE

        # 钩子函数
        def low_level_handler(nCode, wParam, lParam) -> int:
            if nCode == HC_ACTION:
                kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = kb.vkCode

                # 【第一层：强制拦截】输入法激活时，直接拦掉配置的笔画键
                # （不经过回调，避免任何中间环节出问题）
                if self._enabled and vk in self._force_block_vks:
                    if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        # keydown 时触发回调处理业务逻辑
                        evt = self._classify(vk)
                        try:
                            self._callback(evt)
                        except Exception as e:
                            print(f"[keyboard_hook] callback error: {e}")
                    # 无论 keydown 还是 keyup，都拦截
                    return 1

                # 只对 keydown 触发回调（包含 WM_KEYDOWN 和 WM_SYSKEYDOWN）
                if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    evt = self._classify(vk)
                    if evt["type"] != "other":
                        try:
                            block = bool(self._callback(evt))
                        except Exception as e:
                            print(f"[keyboard_hook] callback error: {e}")
                            block = False
                        if block:
                            # 返回非零阻止按键继续传递给下一个钩子/目标窗口
                            return 1
            # 调用链下一环（让按键通过）
            return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

        # 必须保存 hook_proc 引用避免被 GC（否则崩溃）
        self._hook_proc = HOOKPROC(low_level_handler)

        # 安装钩子
        self._hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._hook_proc,
            kernel32.GetModuleHandleW(None),
            0,
        )
        if not self._hook:
            err = ctypes.get_last_error()
            print(f"[keyboard_hook] SetWindowsHookExW 失败: err={err}")
            return

    def _message_loop(self) -> None:
        """独立线程的消息循环（start 方法使用）"""
        self._install_hook()
        if not self._hook:
            return

        user32 = ctypes.windll.user32

        # 消息循环（必须在装钩子的同一线程里）
        # 用 GetMessage 阻塞方式，保证钩子处理及时
        msg = wintypes.MSG()
        while self._running:
            bRet = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if bRet == -1:
                # 出错，退出
                break
            if bRet == 0:
                # WM_QUIT，退出
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # 卸载钩子
        if self._hook is not None:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None

    # ---------- 事件分类 ----------

    def _classify(self, vk: int) -> dict:
        # 检查 Ctrl 是否按下
        user32 = ctypes.windll.user32
        ctrl_pressed = (user32.GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0

        # Ctrl + ` ：显示/隐藏虚拟键盘
        if vk == VK_OEM_3 and ctrl_pressed:
            return {"type": "toggle_keyboard", "value": None, "vk": vk}

        # F2：开关
        if vk == VK_F2:
            return {"type": "f2", "value": None, "vk": vk}

        # Esc
        if vk == VK_ESCAPE:
            return {"type": "escape", "value": None, "vk": vk}

        # Backspace
        if vk == VK_BACK:
            return {"type": "backspace", "value": None, "vk": vk}

        # Space / Enter
        if vk == VK_SPACE:
            return {"type": "space", "value": None, "vk": vk}
        if vk == VK_RETURN:
            return {"type": "enter", "value": None, "vk": vk}

        # PageUp / PageDown
        if vk == VK_PRIOR:
            return {"type": "page_up", "value": None, "vk": vk}
        if vk == VK_NEXT:
            return {"type": "page_down", "value": None, "vk": vk}

        # NumPad 数字
        if VK_NUMPAD0 <= vk <= VK_NUMPAD9:
            return {"type": "numpad_digit", "value": vk - VK_NUMPAD0, "vk": vk}

        # 主键盘顶排数字
        if VK_0 <= vk <= VK_9:
            # '1'=0x31 .. '9'=0x39, '0'=0x30
            digit = vk - VK_0  # 0..9
            # 我们对外暴露的是 1..9 和 10 (代表 0)
            value = digit if digit != 0 else 10
            return {"type": "top_digit", "value": value, "vk": vk}

        # - / =
        if vk == VK_OEM_MINUS:
            return {"type": "minus", "value": None, "vk": vk}
        if vk == VK_OEM_PLUS:
            return {"type": "equal", "value": None, "vk": vk}

        return {"type": "other", "value": None, "vk": vk}
