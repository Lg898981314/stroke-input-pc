"""
候选字窗口 UI（PyQt5）
- 紧贴当前光标位置显示
- 显示当前笔画序列、页码、候选字
- 候选字编号 1-5 对应主键盘数字键
- 上屏后自动隐藏
- 支持多主题（跟随虚拟键盘的主题配色）
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette, QCursor

from stroke_input_method import InputState, STROKE_NAMES, MODE_CONFIRM
from config import get_config

# 默认主题（深色，和旧版一致）
DEFAULT_THEME = {
    "bg": "#2b2b2b",
    "text": "#e0e0e0",
    "highlight": "#4a9eff",
    "border": "#555555",
    "sub_text": "#888888",
}

# 各主题对应的浮动窗口配色
THEME_MAP = {
    "light": {
        "bg": "#ffffff",
        "text": "#1e293b",
        "highlight": "#3b82f6",
        "border": "#e2e8f0",
        "sub_text": "#94a3b8",
    },
    "dark": {
        "bg": "#1e293b",
        "text": "#f1f5f9",
        "highlight": "#60a5fa",
        "border": "#475569",
        "sub_text": "#94a3b8",
    },
    "blue": {
        "bg": "#eff6ff",
        "text": "#1e3a8a",
        "highlight": "#1d4ed8",
        "border": "#93c5fd",
        "sub_text": "#3b82f6",
    },
    "green": {
        "bg": "#f0fdf4",
        "text": "#14532d",
        "highlight": "#16a34a",
        "border": "#86efac",
        "sub_text": "#22c55e",
    },
    "pink": {
        "bg": "#fdf2f8",
        "text": "#831843",
        "highlight": "#db2777",
        "border": "#f9a8d4",
        "sub_text": "#ec4899",
    },
    "orange": {
        "bg": "#fff7ed",
        "text": "#7c2d12",
        "highlight": "#ea580c",
        "border": "#fdba74",
        "sub_text": "#f97316",
    },
}


class CandidateWindow(QWidget):
    """候选字浮窗"""

    def __init__(self) -> None:
        super().__init__()
        self._theme = DEFAULT_THEME
        self._init_ui()
        self._move_to_cursor()

    def _init_ui(self) -> None:
        # 无边框、置顶、不抢焦点、工具窗口（不在任务栏显示）
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        # 布局：上方显示笔画序列，下方显示候选字
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 6)
        outer.setSpacing(4)

        self.stroke_label = QLabel("笔画：")
        outer.addWidget(self.stroke_label)

        self.candidate_layout = QHBoxLayout()
        self.candidate_layout.setSpacing(8)
        outer.addLayout(self.candidate_layout)

        self.page_label = QLabel("")
        self.page_label.setAlignment(Qt.AlignRight)
        outer.addWidget(self.page_label)

        # 候选字标签列表（数量由配置决定）
        self.candidate_labels: list[QLabel] = []
        page_size = get_config().ui.get("page_size", 5)
        for i in range(page_size):
            lbl = QLabel("")
            lbl.setStyleSheet("font-size: 16px;")
            self.candidate_layout.addWidget(lbl)
            self.candidate_labels.append(lbl)

        self._apply_theme_style()
        self.adjustSize()

    def _apply_theme_style(self):
        c = self._theme
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {c['bg']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 6px;
            }}
        """)
        self.stroke_label.setStyleSheet(f"color: {c['highlight']}; font-size: 12px;")
        self.page_label.setStyleSheet(f"color: {c['sub_text']}; font-size: 11px;")

    def set_theme(self, theme_name: str) -> None:
        """设置主题（跟随虚拟键盘）"""
        self._theme = THEME_MAP.get(theme_name, DEFAULT_THEME)
        self._apply_theme_style()
        # 刷新候选标签颜色（首项高亮）
        # 这里只是改窗口整体样式，候选字的高亮在 update_state 里单独处理

    def _move_to_cursor(self) -> None:
        """紧贴当前鼠标位置显示"""
        pos = QCursor.pos()
        x, y = pos.x() + 10, pos.y() + 20
        screen = QApplication.primaryScreen().geometry()
        w = self.width() or 200
        h = self.height() or 60
        if x + w > screen.width():
            x = screen.width() - w - 4
        if y + h > screen.height():
            y = pos.y() - h - 10
        self.move(x, y)

    def update_state(self, state: InputState) -> None:
        """根据输入法状态刷新窗口内容"""
        is_confirm_mode = (state.mode == MODE_CONFIRM)
        has_content = (is_confirm_mode and state.confirm_items) or \
                      (not is_confirm_mode and (state.sequence or state.candidates))

        if not has_content:
            self.hide()
            return

        if is_confirm_mode:
            # 确认模式：标题显示当前字
            head = state.confirm_char
            self.stroke_label.setText(f"{head} ___")
        else:
            # 笔画模式：显示当前笔画序列
            seq_display = " ".join(STROKE_NAMES.get(c, c) for c in state.sequence)
            self.stroke_label.setText(f"笔画：{seq_display}")

        # 候选项
        page = state.current_page()
        highlight = self._theme["highlight"]
        text_color = self._theme["text"]
        for i, lbl in enumerate(self.candidate_labels):
            if i < len(page):
                num = i + 1
                lbl.setText(f"{num}.{page[i]}")
                lbl.setVisible(True)
                if i == 0:
                    lbl.setStyleSheet(f"font-size: 16px; color: {highlight}; font-weight: bold;")
                else:
                    lbl.setStyleSheet(f"font-size: 16px; color: {text_color};")
            else:
                lbl.setText("")
                lbl.setVisible(False)

        # 页码
        total = state.total_pages()
        if total > 1:
            self.page_label.setText(f"第 {state.current_page_index() + 1}/{total} 页  ( -/= 或 PgUp/PgDn )")
        else:
            self.page_label.setText("")

        self.adjustSize()
        self._move_to_cursor()
        if not self.isVisible():
            self.show()

    def show_for_status(self, enabled: bool) -> None:
        """开关状态变化时的提示"""
        if not enabled:
            self.hide()
