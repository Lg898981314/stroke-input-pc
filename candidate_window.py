"""
候选字窗口 UI（PyQt5）
- 紧贴当前光标位置显示
- 显示当前笔画序列、页码、候选字
- 候选字编号 1-9 对应主键盘数字键
- 上屏后自动隐藏
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette, QCursor

from stroke_input_method import InputState, STROKE_NAMES

# 配色：参考搜狗/微软拼音的深色浮窗
BG_COLOR = "#2b2b2b"
FG_COLOR = "#e0e0e0"
HIGHLIGHT_COLOR = "#4a9eff"
BORDER_COLOR = "#555555"


class CandidateWindow(QWidget):
    """候选字浮窗"""

    def __init__(self) -> None:
        super().__init__()
        self._init_ui()
        self._move_to_cursor()

    def _init_ui(self) -> None:
        # 无边框、置顶、不抢焦点（不会让其他应用失焦）、工具窗口（不在任务栏显示）
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        # 背景
        pal = self.palette()
        pal.setColor(QPalette.Window, QColor(BG_COLOR))
        pal.setColor(QPalette.WindowText, QColor(FG_COLOR))
        self.setPalette(pal)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {BG_COLOR};
                color: {FG_COLOR};
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
            }}
        """)

        # 布局：上方显示笔画序列，下方显示候选字
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(4)

        self.stroke_label = QLabel("笔画：")
        self.stroke_label.setStyleSheet(f"color: {HIGHLIGHT_COLOR}; font-size: 12px;")
        outer.addWidget(self.stroke_label)

        self.candidate_layout = QHBoxLayout()
        self.candidate_layout.setSpacing(8)
        outer.addLayout(self.candidate_layout)

        self.page_label = QLabel("")
        self.page_label.setStyleSheet("color: #888; font-size: 11px;")
        self.page_label.setAlignment(Qt.AlignRight)
        outer.addWidget(self.page_label)

        # 候选字标签列表
        self.candidate_labels: list[QLabel] = []
        for i in range(9):
            lbl = QLabel("")
            lbl.setStyleSheet("font-size: 16px;")
            self.candidate_layout.addWidget(lbl)
            self.candidate_labels.append(lbl)

        self.adjustSize()

    def _move_to_cursor(self) -> None:
        """紧贴当前鼠标位置显示（无法精确取系统光标位置时的兜底方案）"""
        # 优先尝试用 Qt 的鼠标位置
        pos = QCursor.pos()
        x, y = pos.x() + 10, pos.y() + 20
        # 防止超出屏幕
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
        # 笔画模式：必须有 sequence 或 candidates
        # 联想模式：必须有 last_char 和 phrase_candidates
        from stroke_input_method import MODE_PHRASE

        is_phrase_mode = (state.mode == MODE_PHRASE)
        has_content = (is_phrase_mode and state.phrase_candidates) or \
                      (not is_phrase_mode and (state.sequence or state.candidates))

        if not has_content:
            self.hide()
            return

        if is_phrase_mode:
            # 联想模式：标题显示首字
            head = state.last_char
            self.stroke_label.setText(f"联想：{head} ___")
        else:
            # 笔画模式：显示当前笔画序列
            seq_display = " ".join(STROKE_NAMES.get(c, c) for c in state.sequence)
            self.stroke_label.setText(f"笔画：{seq_display}")

        # 候选项
        page = state.current_page()
        for i, lbl in enumerate(self.candidate_labels):
            if i < len(page):
                num = i + 1
                lbl.setText(f"{num}.{page[i]}")
                lbl.setVisible(True)
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
