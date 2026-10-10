"""
笔画输入法主入口
- 初始化各模块
- 启动全局键盘钩子
- 启动 PyQt5 事件循环
- 协调键盘事件 -> 输入法状态 -> UI 刷新 -> 上屏
- 系统托盘图标 + 全局热键显示/隐藏虚拟键盘

按键映射（按九宫格手机笔画输入法位置对应）：
    笔画（横/竖/撇/捺/折）：NumPad 小键盘 7/8/9/4/5
                            （对应手机九宫格 1/2/3/4/5 的位置）
    选候选字（1-5）：       主键盘字母上方数字键 1-5
    翻页：                 主键盘 - / = 或 PgUp/PgDn
    上屏首候选：           空格 / Enter
    删除最后一笔：         Backspace
    清空当前输入：         Esc
    开关输入法：           F2
    显示/隐藏虚拟键盘：    Ctrl + `
"""

from __future__ import annotations

import sys
import threading

from PyQt5.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QAction,
)
from PyQt5.QtGui import QIcon, QPainter, QColor, QPen, QFont
from PyQt5.QtCore import QObject, pyqtSignal, Qt, QSize
from PyQt5.QtCore import QEvent

from stroke_data import get_data
from stroke_input_method import StrokeInputMethod, get_key_to_stroke
from candidate_window import CandidateWindow
from virtual_keyboard import VirtualKeyboard
from input_sender import InputSender
from keyboard_hook import KeyboardHook
from config import get_config


# 跨线程把事件塞到 Qt 主线程的桥
class QtBridge(QObject):
    """全局键盘钩子在自己的线程里跑；通过信号把事件传到 Qt 主线程"""
    candidates_updated = pyqtSignal(object)   # 携带 InputState
    status_changed = pyqtSignal(bool)
    commit_text = pyqtSignal(str)
    toggle_keyboard = pyqtSignal()  # 全局热键触发显示/隐藏键盘


def make_tray_icon() -> QIcon:
    """生成一个简单的托盘图标（蓝色笔形图案）"""
    size = 64
    pixmap = QIcon.fromTheme("input-keyboard").pixmap(size, size)
    if not pixmap.isNull():
        return QIcon(pixmap)
    # 回退：画一个简单的蓝色方块加白色"笔"字
    from PyQt5.QtGui import QPixmap
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    # 蓝色圆角背景
    painter.setBrush(QColor("#3b82f6"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(4, 4, size - 8, size - 8, 10, 10)
    # 白色"笔"字
    painter.setPen(QColor("#ffffff"))
    font = QFont("Microsoft YaHei", 28, QFont.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "笔")
    painter.end()
    return QIcon(pixmap)


def main() -> None:
    # 1. 预加载数据（首次会自动下载 Conway Stroke Data）
    print("[main] 加载笔画数据中 ...")
    get_data()
    print("[main] 数据就绪")

    # 2. 启动 Qt 应用
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 窗口全部关闭也不退出（托盘常驻）

    # 3. 创建组件
    window = CandidateWindow()          # 浮动候选窗口（跟随光标）
    vk = VirtualKeyboard(method=None)   # 虚拟键盘
    sender = InputSender()

    bridge = QtBridge()

    # 4. 创建输入法状态机
    method = StrokeInputMethod(
        on_candidates_updated=lambda state: bridge.candidates_updated.emit(state),
        on_commit=lambda text: bridge.commit_text.emit(text),
        on_status_change=lambda enabled: bridge.status_changed.emit(enabled),
    )
    # 把 method 注入虚拟键盘
    vk.method = method

    # 5. 系统托盘
    tray_icon = QSystemTrayIcon(make_tray_icon(), parent=app)
    tray_icon.setToolTip("笔画输入法（Ctrl+` 显示/隐藏键盘，F2 开关输入法）")

    tray_menu = QMenu()

    act_show = QAction("显示/隐藏虚拟键盘", tray_menu)
    act_show.setShortcut("Ctrl+`")

    def toggle_keyboard():
        if vk.isVisible():
            vk.hide()
        else:
            vk.show()
            vk.raise_()
            vk.activateWindow()

    act_show.triggered.connect(toggle_keyboard)
    tray_menu.addAction(act_show)

    act_enable = QAction("启用/关闭输入法", tray_menu)
    act_enable.setShortcut("F2")
    act_enable.triggered.connect(lambda: method.toggle())
    tray_menu.addAction(act_enable)

    tray_menu.addSeparator()

    act_quit = QAction("退出", tray_menu)
    act_quit.triggered.connect(app.quit)
    tray_menu.addAction(act_quit)

    tray_icon.setContextMenu(tray_menu)
    tray_icon.activated.connect(
        lambda reason: toggle_keyboard() if reason == QSystemTrayIcon.Trigger else None
    )
    tray_icon.show()

    # 全局热键信号 -> 切换键盘显示
    bridge.toggle_keyboard.connect(toggle_keyboard)

    # 6. 连接信号到 Qt 主线程的槽
    last_state = [None]

    def on_candidates_changed(state):
        last_state[0] = state
        if vk.isVisible() and not vk.isMinimized():
            window.hide()
        else:
            window.update_state(state)
        vk.update_state(state)

    def on_status_changed(enabled):
        window.show_for_status(enabled)
        vk.show_for_status(enabled)
        if enabled:
            tray_icon.setToolTip("笔画输入法 - 已启用（Ctrl+` 显示/隐藏键盘）")
        else:
            tray_icon.setToolTip("笔画输入法 - 已关闭（按 F2 启用）")

    def on_commit_text(text):
        sender.commit(text)

    bridge.candidates_updated.connect(on_candidates_changed)
    bridge.status_changed.connect(on_status_changed)
    bridge.commit_text.connect(on_commit_text)

    # 虚拟键盘显示/隐藏变化时，切换浮动窗口
    original_show_event = vk.showEvent
    original_hide_event = vk.hideEvent
    original_change_event = vk.changeEvent

    # 主题联动：虚拟键盘切换主题时，浮动窗口也跟着变
    original_cycle_theme = vk.cycle_theme

    def _on_theme_changed():
        window.set_theme(vk._current_theme)

    def vk_cycle_theme():
        original_cycle_theme()
        _on_theme_changed()

    vk.cycle_theme = vk_cycle_theme

    # 启动时同步主题
    window.set_theme(vk._current_theme)

    def _refresh_floating():
        if last_state[0] is None:
            return
        if vk.isVisible() and not vk.isMinimized():
            window.hide()
        else:
            window.update_state(last_state[0])

    def vk_shown(event):
        original_show_event(event)
        _refresh_floating()

    def vk_hidden(event):
        original_hide_event(event)
        _refresh_floating()

    def vk_changed(event):
        original_change_event(event)
        if event.type() == QEvent.WindowStateChange:
            _refresh_floating()

    vk.showEvent = vk_shown
    vk.hideEvent = vk_hidden
    vk.changeEvent = vk_changed

    # 7. 键盘事件 -> 输入法状态机
    # 回调返回 True 表示要拦截此按键（不传到当前焦点窗口）
    # 返回 False 表示放行（按键照常传到目标窗口）
    def on_key_event(evt: dict) -> bool:
        etype = evt["type"]

        # Ctrl+`：显示/隐藏虚拟键盘，无论是否激活都响应
        if etype == "toggle_keyboard":
            bridge.toggle_keyboard.emit()
            return True  # 拦截，避免 ` 打到输入框

        # F2：开关输入法，无论是否激活都响应且拦截
        if etype == "f2":
            method.toggle()
            return True

        # 未激活时所有按键都放行
        if not method.enabled:
            return False

        # 输入法激活时，处理我们关心的按键并拦截
        if etype == "numpad_digit":
            keymap = get_key_to_stroke()
            value_str = str(evt["value"])
            if value_str in keymap:
                method.add_stroke(value_str)
                return True
            return False

        if etype == "top_digit":
            idx = evt["value"] - 1
            # 根据配置的 page_size 决定范围
            page_size = get_config().ui.get("page_size", 5)
            if 0 <= idx < page_size:
                if method.select_index(idx):
                    return True
                return False
            return False

        has_candidates = bool(method.state.current_page())

        if etype == "space":
            if has_candidates:
                method.select_first()
                return True
            return False

        if etype == "enter":
            if has_candidates:
                method.select_first()
                return True
            return False

        if etype == "backspace":
            if method.state.sequence or method.state.mode == "confirm":
                method.backspace()
                return True
            return False

        if etype == "escape":
            if method.state.sequence or method.state.mode == "confirm":
                method.escape()
                return True
            return False

        if etype in ("page_up", "minus"):
            if has_candidates:
                method.page_prev()
                return True
            return False

        if etype in ("page_down", "equal"):
            if has_candidates:
                method.page_next()
                return True
            return False

        return False

    hook = KeyboardHook(on_key_event)

    # 设置强制拦截的 NumPad 笔画键（在钩子层直接拦截，确保不会漏）
    VK_NUMPAD0 = 0x60
    keymap = get_key_to_stroke()
    force_block_vks = set()
    for key_str in keymap:
        try:
            digit = int(key_str)
            force_block_vks.add(VK_NUMPAD0 + digit)
        except ValueError:
            pass
    hook.set_force_block_vks(force_block_vks)
    hook.set_enabled(True)
    print(f"[main] 强制拦截 NumPad 键: {[hex(v) for v in sorted(force_block_vks)]}")

    # 在 Qt 主线程中安装钩子（利用 Qt 的消息循环，更稳定）
    hook.start_in_main_thread()
    print("[main] 键盘钩子已启动")

    # 默认启用输入法并显示虚拟键盘
    method.enable(True)
    vk.show()
    print("[main] 虚拟键盘已显示，可点击笔画按钮输入")
    print("[main] 按 F2 可临时关闭/开启输入法")
    print("[main] 按 Ctrl+` 可显示/隐藏虚拟键盘")

    # 同步输入法状态到钩子（F2 开关时也要同步强制拦截状态）
    original_on_status = method._on_status_change

    def _on_status_sync(enabled):
        hook.set_enabled(enabled)
        if original_on_status:
            original_on_status(enabled)

    method._on_status_change = _on_status_sync

    # 8. 进入 Qt 事件循环
    try:
        app.exec_()
    finally:
        hook.stop()
        tray_icon.hide()
        print("[main] 已退出")


if __name__ == "__main__":
    main()
