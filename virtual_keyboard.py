"""
虚拟笔画键盘窗口（可配置版 + 多主题 + 数字键盘 + 表情）
- 笔画按钮、符号从 config.json 读取
- 支持多主题切换（浅色/深色/蓝/绿/粉/橙）
- 数字键盘切换（123 按钮）
- 表情独立入口
- 换行按钮
- 始终置顶，不抢焦点
- 可拖动
"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QGridLayout,
    QFrame, QStackedLayout, QSizePolicy, QDialog, QScrollArea,
)
from PyQt5.QtCore import Qt, QSize, QEvent
from PyQt5.QtGui import QFont, QColor
import ctypes
from ctypes import wintypes

from stroke_input_method import StrokeInputMethod, InputState, MODE_PHRASE
from stroke_data import STROKE_NAMES
from config import get_config


# Windows 扩展样式常量
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
GWL_EXSTYLE = -20

user32 = ctypes.windll.user32


class NoFocusButton(QPushButton):
    """不抢焦点的按钮。点击时保存外部窗口焦点，点击完恢复。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._last_foreground = None

    def mousePressEvent(self, event):
        # 按下前先记录当前前台窗口
        try:
            self._last_foreground = user32.GetForegroundWindow()
        except Exception:
            self._last_foreground = None
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # 先恢复焦点，再发射 clicked 信号
        # 这样 clicked 的槽函数执行时，焦点已经在目标窗口了
        if self._last_foreground:
            try:
                user32.SetForegroundWindow(self._last_foreground)
            except Exception:
                pass
        super().mouseReleaseEvent(event)

    def get_last_foreground(self):
        return self._last_foreground


class VirtualKeyboard(QWidget):
    """虚拟笔画键盘（可配置 + 多主题 + 数字键盘）"""

    # 主题列表（用于循环切换）
    THEME_NAMES = ["light", "dark", "blue", "green", "pink", "orange"]
    THEME_LABELS = ["浅色", "深色", "蓝色", "绿色", "粉色", "橙色"]

    def __init__(self, method: StrokeInputMethod | None = None):
        super().__init__()
        self.method = method
        self.cfg = get_config()

        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowTitle("笔画键盘")

        # 拖动用
        self._drag_pos = None

        # 面板状态：0=笔画主键盘  1=符号面板  2=数字键盘
        self._panel_index = 0
        self._sym_page_index = 0

        # 当前主题
        self._current_theme = self.cfg.ui.get("theme", "light")
        if self._current_theme not in self.THEME_NAMES:
            self._current_theme = "light"
        self._theme_colors = self._load_theme(self._current_theme)

        self._build_ui()
        self._apply_theme_style()

    # ---------- 主题 ----------

    def _load_theme(self, name: str) -> dict:
        """加载主题配色"""
        all_themes = self.cfg.get("themes", {})
        if name in all_themes:
            return all_themes[name]
        # 回退：默认浅色配色
        return {
            "bg": "#f8fafc",
            "title_bg": "#e2e8f0",
            "title_text": "#475569",
            "card_bg": "#ffffff",
            "text": "#1e293b",
            "sub_text": "#64748b",
            "stroke_bg": "#ffffff",
            "stroke_text": "#1e293b",
            "stroke_border": "#e2e8f0",
            "aux_bg": "#dbeafe",
            "aux_text": "#1d4ed8",
            "func_bg": "#f1f5f9",
            "func_text": "#475569",
            "punct_bg": "#ffffff",
            "punct_text": "#334155",
            "punct_border": "#e2e8f0",
            "cand_bg": "#ffffff",
            "cand_border": "#e2e8f0",
            "cand_active_bg": "#3b82f6",
            "cand_active_text": "#ffffff",
            "del_bg": "#fef3c7",
            "del_text": "#b45309",
            "clr_bg": "#fee2e2",
            "clr_text": "#b91c1c",
        }

    def _apply_theme_style(self):
        """根据当前主题设置整体样式"""
        c = self._theme_colors
        self.setStyleSheet(f"QWidget{{background:{c['bg']};}}")

    def cycle_theme(self):
        """切换到下一个主题"""
        idx = self.THEME_NAMES.index(self._current_theme) if self._current_theme in self.THEME_NAMES else 0
        next_idx = (idx + 1) % len(self.THEME_NAMES)
        self._current_theme = self.THEME_NAMES[next_idx]
        self._theme_colors = self._load_theme(self._current_theme)
        self._rebuild_all_styles()
        # 保存到配置
        self.cfg.data["ui"]["theme"] = self._current_theme
        self.cfg.save()

    def _rebuild_all_styles(self):
        """重建所有按钮样式（切换主题后调用）"""
        c = self._theme_colors

        # 标题栏
        self.title_bar.setStyleSheet(f"QWidget{{background:{c['title_bg']};border-radius:4px;}}")
        self.title_label.setStyleSheet(f"color:{c['title_text']}; font-size: 11px;")
        if self.method and self.method.enabled:
            self.status_label.setStyleSheet("color: #16a34a; font-size: 11px;")
        else:
            self.status_label.setStyleSheet("color: #94a3b8; font-size: 11px;")

        # 顶部候选条
        self.top_bar.setStyleSheet(f"QWidget{{background:{c['card_bg']};border-radius:6px;}}")
        self.stroke_label.setStyleSheet(f"color:{c['sub_text']};font-size:13px;padding:2px 4px;")

        # 候选字按钮
        for i, btn in enumerate(self.cand_buttons):
            btn.setStyleSheet(self._candidate_style(i))

        # 笔画按钮
        for btn in self._stroke_buttons:
            btn.setStyleSheet(self._stroke_style())

        # 左列符号
        for btn in self._left_col_buttons:
            btn.setStyleSheet(self._punct_style())

        # 符按钮
        self.btn_sym.setStyleSheet(self._aux_style(c['aux_bg'], c['aux_text']))
        # 数字按钮
        self.btn_num.setStyleSheet(self._aux_style(c['aux_bg'], c['aux_text']))
        # 表情按钮
        self.btn_emoji.setStyleSheet(self._aux_style(c['aux_bg'], c['aux_text']))

        # 右侧功能键
        self.btn_del.setStyleSheet(self._func_style(c['del_bg'], c['del_text']))
        self.btn_clr.setStyleSheet(self._func_style(c['clr_bg'], c['clr_text']))
        self.btn_enter.setStyleSheet(self._func_style(c['aux_bg'], c['aux_text']))
        self.btn_prev.setStyleSheet(self._func_style(c['func_bg'], c['func_text']))
        self.btn_next.setStyleSheet(self._func_style(c['func_bg'], c['func_text']))

        # 符号面板 Tab
        for i, btn in enumerate(self.tab_buttons):
            btn.setStyleSheet(self._tab_style(i == self._sym_page_index))

    # ---------- UI 构建 ----------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(3)

        # 标题栏（可拖动）
        self.title_bar = self._build_title_bar()
        outer.addWidget(self.title_bar)

        # 笔画序列显示 + 候选条
        self.top_bar = self._build_top_bar()
        outer.addWidget(self.top_bar)

        # 主键盘区 / 符面板 / 数字键盘
        self.stack = QStackedLayout()
        self._stroke_buttons = []
        self._left_col_buttons = []

        self.stack.addWidget(self._build_main_keyboard())  # 0
        self.stack.addWidget(self._build_symbol_panel())   # 1
        self.stack.addWidget(self._build_number_keyboard()) # 2
        outer.addLayout(self.stack)

    def _build_title_bar(self) -> QWidget:
        bar = QWidget()
        self.title_bar_widget = bar
        bar.setFixedHeight(22)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(6, 0, 6, 0)
        lay.setSpacing(3)

        self.title_label = QLabel("笔画输入法")
        lay.addWidget(self.title_label)

        self.status_label = QLabel("● 已启用")
        lay.addWidget(self.status_label)

        lay.addStretch(1)

        # 主题切换
        btn_theme = NoFocusButton("🎨")
        btn_theme.setFixedSize(20, 18)
        btn_theme.setStyleSheet(
            "NoFocusButton{border:none;color:#94a3b8;font-size:12px;}"
            "NoFocusButton:hover{background:#e2e8f0;border-radius:3px;}"
        )
        btn_theme.setToolTip("切换主题")
        btn_theme.clicked.connect(self.cycle_theme)
        lay.addWidget(btn_theme)

        # 关于
        btn_about = NoFocusButton("ℹ")
        btn_about.setFixedSize(20, 18)
        btn_about.setStyleSheet(
            "NoFocusButton{border:none;color:#94a3b8;font-size:12px;}"
            "NoFocusButton:hover{background:#e2e8f0;border-radius:3px;}"
        )
        btn_about.clicked.connect(self._show_about)
        lay.addWidget(btn_about)

        # 最小化
        btn_min = NoFocusButton("—")
        btn_min.setFixedSize(20, 18)
        btn_min.setStyleSheet(
            "NoFocusButton{border:none;color:#94a3b8;font-size:12px;}"
            "NoFocusButton:hover{background:#e2e8f0;border-radius:3px;}"
        )
        btn_min.clicked.connect(self.showMinimized)
        lay.addWidget(btn_min)

        btn_close = NoFocusButton("✕")
        btn_close.setFixedSize(20, 18)
        btn_close.setStyleSheet(
            "NoFocusButton{border:none;color:#94a3b8;font-size:11px;}"
            "NoFocusButton:hover{background:#fee2e2;color:#dc2626;border-radius:3px;}"
        )
        btn_close.clicked.connect(self.close)
        lay.addWidget(btn_close)

        return bar

    def _build_top_bar(self) -> QWidget:
        """笔画序列 + 候选字条（5 个候选）"""
        w = QWidget()
        self.top_bar_widget = w
        lay = QVBoxLayout(w)
        lay.setContentsMargins(5, 3, 5, 3)
        lay.setSpacing(2)

        self.stroke_label = QLabel("笔画：")
        lay.addWidget(self.stroke_label)

        # 候选字条（5 个）
        cand_row = QHBoxLayout()
        cand_row.setSpacing(3)
        self.cand_buttons: list[NoFocusButton] = []
        page_size = self.cfg.ui.get("page_size", 5)
        for i in range(page_size):
            btn = NoFocusButton()
            btn.setFixedSize(52, 44)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._candidate_style(i))
            btn.clicked.connect(lambda checked, idx=i: self._on_candidate_clicked(idx))
            cand_row.addWidget(btn)
            self.cand_buttons.append(btn)
        lay.addLayout(cand_row)

        return w

    def _build_main_keyboard(self) -> QWidget:
        """主键盘区：左列(符/123/😀) + 笔画3x3 + 右列(删除/重输/换行/翻页)"""
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        # 左侧列：符 / 123 / 😀 / 4个常用符号
        left = QWidget()
        left.setFixedWidth(38)
        l_col = QVBoxLayout(left)
        l_col.setContentsMargins(0, 0, 0, 0)
        l_col.setSpacing(2)

        # 符按钮
        self.btn_sym = NoFocusButton("符")
        self.btn_sym.setFixedHeight(36)
        self.btn_sym.setCursor(Qt.PointingHandCursor)
        self.btn_sym.clicked.connect(self._show_symbol_panel)
        l_col.addWidget(self.btn_sym)

        # 数字按钮（123）
        self.btn_num = NoFocusButton("123")
        self.btn_num.setFixedHeight(36)
        self.btn_num.setCursor(Qt.PointingHandCursor)
        self.btn_num.clicked.connect(self._show_number_panel)
        l_col.addWidget(self.btn_num)

        # 表情按钮
        self.btn_emoji = NoFocusButton("😀")
        self.btn_emoji.setFixedHeight(36)
        self.btn_emoji.setCursor(Qt.PointingHandCursor)
        self.btn_emoji.clicked.connect(self._show_emoji_panel)
        l_col.addWidget(self.btn_emoji)

        # 左列常用符号（2个）
        for ch in self.cfg.left_col_symbols[:4]:
            btn = NoFocusButton(ch)
            btn.setFixedHeight(34)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, c=ch: self._commit_punct(c))
            self._left_col_buttons.append(btn)
            l_col.addWidget(btn)

        l_col.addStretch(1)
        lay.addWidget(left)

        # 中间：笔画网格
        center = QWidget()
        grid = QGridLayout(center)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(3)

        key_font_size = self.cfg.ui.get("key_font_size", 26)

        for r, row_cfg in enumerate(self.cfg.stroke_button_rows):
            for c, btn_cfg in enumerate(row_cfg):
                btype = btn_cfg.get("type", "stroke")
                label = btn_cfg.get("label", "")
                if btype == "stroke":
                    stroke_num = btn_cfg.get("stroke", "1")
                    btn = self._make_stroke_btn(label, stroke_num, key_font_size)
                    self._stroke_buttons.append(btn)
                elif btype == "wildcard":
                    btn = NoFocusButton(label)
                    btn.setFixedHeight(54)
                    btn.setCursor(Qt.PointingHandCursor)
                    btn.clicked.connect(self._on_wildcard)
                elif btype == "symbol":
                    btn = NoFocusButton(label)
                    btn.setFixedHeight(54)
                    btn.setCursor(Qt.PointingHandCursor)
                    btn.clicked.connect(lambda checked, c=label: self._commit_punct(c))
                    self._stroke_buttons.append(btn)
                elif btype == "action":
                    action = btn_cfg.get("action", "")
                    btn = NoFocusButton(label)
                    btn.setFixedHeight(40)
                    btn.setCursor(Qt.PointingHandCursor)
                    if action == "segment":
                        btn.clicked.connect(self._on_segment)
                else:
                    btn = NoFocusButton(label)
                    btn.setFixedHeight(40)
                grid.addWidget(btn, r, c)

        lay.addWidget(center, 1)

        # 右侧：功能键列
        right = QWidget()
        right.setFixedWidth(52)
        r_col = QVBoxLayout(right)
        r_col.setContentsMargins(0, 0, 0, 0)
        r_col.setSpacing(2)

        self.btn_del = NoFocusButton("删除")
        self.btn_del.setFixedHeight(52)
        self.btn_del.setCursor(Qt.PointingHandCursor)
        self.btn_del.clicked.connect(self._on_delete)
        r_col.addWidget(self.btn_del)

        self.btn_clr = NoFocusButton("重输")
        self.btn_clr.setFixedHeight(40)
        self.btn_clr.setCursor(Qt.PointingHandCursor)
        self.btn_clr.clicked.connect(self._on_clear)
        r_col.addWidget(self.btn_clr)

        self.btn_enter = NoFocusButton("换行\n↵")
        self.btn_enter.setFixedHeight(52)
        self.btn_enter.setCursor(Qt.PointingHandCursor)
        self.btn_enter.clicked.connect(self._on_enter)
        r_col.addWidget(self.btn_enter)

        r_col.addStretch(1)

        self.btn_prev = NoFocusButton("◀")
        self.btn_prev.setFixedHeight(28)
        self.btn_prev.setCursor(Qt.PointingHandCursor)
        self.btn_prev.clicked.connect(self._on_page_prev)
        r_col.addWidget(self.btn_prev)

        self.btn_next = NoFocusButton("▶")
        self.btn_next.setFixedHeight(28)
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.clicked.connect(self._on_page_next)
        r_col.addWidget(self.btn_next)

        lay.addWidget(right)
        return w

    def _build_symbol_panel(self) -> QWidget:
        """符面板：顶部 Tab + 符号网格 + 返回"""
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        # Tab 按钮行（横向滚动）
        tab_scroll = QScrollArea()
        tab_scroll.setWidgetResizable(True)
        tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tab_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tab_scroll.setFixedHeight(28)
        tab_scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")

        tab_container = QWidget()
        self.tab_layout = QHBoxLayout(tab_container)
        self.tab_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_layout.setSpacing(2)
        self.tab_buttons: list[NoFocusButton] = []

        pages = self.cfg.symbol_pages
        self._sym_page_index = 0

        for i, page in enumerate(pages):
            name = page.get("name", f"第{i+1}页")
            btn = NoFocusButton(name)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._tab_style(i == 0))
            btn.clicked.connect(lambda checked, idx=i: self._switch_sym_page(idx))
            self.tab_layout.addWidget(btn)
            self.tab_buttons.append(btn)

        self.tab_layout.addStretch(1)
        tab_scroll.setWidget(tab_container)
        outer.addWidget(tab_scroll)

        # 符号网格
        sym_scroll = QScrollArea()
        sym_scroll.setWidgetResizable(True)
        sym_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sym_scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        sym_container = QWidget()
        self.sym_grid = QGridLayout(sym_container)
        self.sym_grid.setContentsMargins(3, 3, 3, 3)
        self.sym_grid.setSpacing(2)
        sym_scroll.setWidget(sym_container)
        outer.addWidget(sym_scroll, 1)

        # 底部：返回按钮
        bottom_row = QHBoxLayout()
        btn_back = NoFocusButton("← 返回")
        btn_back.setFixedHeight(32)
        btn_back.setCursor(Qt.PointingHandCursor)
        btn_back.clicked.connect(self._show_main_panel)
        bottom_row.addWidget(btn_back)
        outer.addLayout(bottom_row)

        # 填充第一页
        self._populate_symbols(0)
        return w

    def _build_number_keyboard(self) -> QWidget:
        """数字键盘：0-9 + . + , + = + 退格 + 换行"""
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        # 数字网格 4列 x 4行
        grid = QGridLayout()
        grid.setContentsMargins(3, 3, 3, 3)
        grid.setSpacing(2)

        number_keys = [
            ["1", "2", "3", "←"],
            ["4", "5", "6", "↵"],
            ["7", "8", "9", "返回"],
            [".", "0", ",", "？"],
        ]

        for r, row in enumerate(number_keys):
            for c, key in enumerate(row):
                btn = NoFocusButton(key)
                btn.setFixedHeight(42)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet(self._stroke_style())
                if key == "←":
                    btn.setStyleSheet(self._func_style("#fef3c7", "#b45309"))
                    btn.clicked.connect(self._on_delete)
                elif key == "↵":
                    btn.setStyleSheet(self._aux_style("#dbeafe", "#1d4ed8"))
                    btn.clicked.connect(self._on_enter)
                elif key == "返回":
                    btn.setStyleSheet(self._aux_style("#e0e7ff", "#4338ca"))
                    btn.clicked.connect(self._show_main_panel)
                else:
                    btn.clicked.connect(lambda checked, ch=key: self._commit_punct(ch))
                grid.addWidget(btn, r, c)

        outer.addLayout(grid)
        return w

    def _populate_symbols(self, page_idx: int):
        """填充指定页的符号"""
        # 清空现有
        while self.sym_grid.count():
            item = self.sym_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        pages = self.cfg.symbol_pages
        if page_idx >= len(pages):
            return
        page = pages[page_idx]
        rows = page.get("rows", [])

        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                if not ch:
                    continue
                btn = NoFocusButton(ch)
                btn.setFixedHeight(32)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet(self._punct_style())
                btn.clicked.connect(lambda checked, c=ch: self._commit_punct(c))
                self.sym_grid.addWidget(btn, r, c)

    def _switch_sym_page(self, idx: int):
        self._sym_page_index = idx
        self._populate_symbols(idx)
        for i, btn in enumerate(self.tab_buttons):
            btn.setStyleSheet(self._tab_style(i == idx))

    def _make_stroke_btn(self, label: str, stroke_num: str, font_size: int = 26) -> NoFocusButton:
        btn = NoFocusButton(label)
        btn.setFixedHeight(54)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(self._stroke_style(font_size))
        keymap = self.cfg.keymap
        key_for_stroke = None
        for k, v in keymap.items():
            if v == stroke_num:
                key_for_stroke = k
                break
        btn.clicked.connect(
            lambda checked, k=key_for_stroke:
                self._on_stroke_clicked(k) if k else None
        )
        return btn

    # ---------- 样式 ----------

    def _stroke_style(self, font_size: int = 26) -> str:
        c = self._theme_colors
        return f"""
            NoFocusButton{{
                background:{c['stroke_bg']}; color:{c['stroke_text']};
                border:1px solid {c['stroke_border']}; border-radius:7px;
                font-size:{font_size}px; font-weight:bold;
            }}
            NoFocusButton:hover{{background:rgba(0,0,0,0.04);}}
            NoFocusButton:pressed{{background:rgba(0,0,0,0.08);}}
        """

    def _aux_style(self, bg: str = "#f8fafc", color: str = "#475569") -> str:
        c = self._theme_colors
        return f"""
            NoFocusButton{{
                background:{bg}; color:{color};
                border:1px solid {c['stroke_border']}; border-radius:7px;
                font-size:14px; font-weight:bold;
            }}
            NoFocusButton:hover{{background:rgba(0,0,0,0.05);}}
            NoFocusButton:pressed{{background:rgba(0,0,0,0.1);}}
        """

    def _punct_style(self) -> str:
        c = self._theme_colors
        return f"""
            NoFocusButton{{
                background:{c['punct_bg']}; color:{c['punct_text']};
                border:1px solid {c['punct_border']}; border-radius:6px;
                font-size:16px;
            }}
            NoFocusButton:hover{{background:rgba(0,0,0,0.04);}}
            NoFocusButton:pressed{{background:rgba(0,0,0,0.08);}}
        """

    def _func_style(self, bg: str, color: str) -> str:
        return f"""
            NoFocusButton{{
                background:{bg}; color:{color};
                border:1px solid rgba(0,0,0,0.06); border-radius:7px;
                font-size:13px; font-weight:bold;
            }}
            NoFocusButton:hover{{background:rgba(0,0,0,0.05);}}
            NoFocusButton:pressed{{background:rgba(0,0,0,0.1);}}
        """

    def _candidate_style(self, idx: int) -> str:
        c = self._theme_colors
        font_size = self.cfg.ui.get("candidate_font_size", 22)
        if idx == 0:
            return f"""
                NoFocusButton{{
                    background:{c['cand_active_bg']}; color:{c['cand_active_text']};
                    border:1px solid {c['cand_active_bg']}; border-radius:7px;
                    font-size:{font_size}px; font-weight:bold;
                }}
                NoFocusButton:hover{{background:rgba(0,0,0,0.06);}}
            """
        return f"""
            NoFocusButton{{
                background:{c['cand_bg']}; color:{c['stroke_text']};
                border:1px solid {c['cand_border']}; border-radius:7px;
                font-size:{font_size - 2}px;
            }}
            NoFocusButton:hover{{background:rgba(0,0,0,0.04);}}
        """

    def _tab_style(self, active: bool) -> str:
        c = self._theme_colors
        if active:
            return f"""
                NoFocusButton{{
                    background:{c['cand_active_bg']}; color:{c['cand_active_text']};
                    border:1px solid {c['cand_active_bg']}; border-radius:8px;
                    font-size:12px; padding:2px 10px; font-weight:bold;
                }}
            """
        return f"""
            NoFocusButton{{
                background:{c['func_bg']}; color:{c['func_text']};
                border:1px solid {c['cand_border']}; border-radius:8px;
                font-size:12px; padding:2px 10px;
            }}
            NoFocusButton:hover{{background:rgba(0,0,0,0.04);}}
        """

    # ---------- 面板切换 ----------

    def _show_main_panel(self):
        self.stack.setCurrentIndex(0)
        self._panel_index = 0

    def _show_symbol_panel(self):
        self.stack.setCurrentIndex(1)
        self._panel_index = 1
        self._switch_sym_page(0)

    def _show_number_panel(self):
        self.stack.setCurrentIndex(2)
        self._panel_index = 2

    def _show_emoji_panel(self):
        """直接跳转到符号面板的表情页"""
        self.stack.setCurrentIndex(1)
        self._panel_index = 1
        # 找到表情页
        pages = self.cfg.symbol_pages
        for i, p in enumerate(pages):
            if p.get("name") == "表情":
                self._switch_sym_page(i)
                return
        self._switch_sym_page(0)

    # ---------- 事件回调 ----------

    def _on_stroke_clicked(self, key: str):
        if key and self.method and self.method.enabled:
            self.method.add_stroke(key)

    def _on_candidate_clicked(self, idx: int):
        if self.method and self.method.enabled:
            self.method.select_index(idx)

    def _on_delete(self):
        if not self.method or not self.method.enabled:
            return
        # 有笔画序列/候选时，删除最后一笔
        if self.method.state.sequence or self.method.state.mode == "phrase":
            self.method.backspace()
        else:
            # 没有笔画时，发送退格键到目标窗口
            try:
                import time
                VK_BACK = 0x08
                KEYEVENTF_KEYUP = 0x0002
                time.sleep(0.01)
                user32.keybd_event(VK_BACK, 0, 0, 0)
                user32.keybd_event(VK_BACK, 0, KEYEVENTF_KEYUP, 0)
            except Exception as e:
                print(f"[vk] send backspace error: {e}")

    def _on_clear(self):
        if self.method and self.method.enabled:
            self.method.escape()

    def _on_enter(self):
        """换行按钮：发送回车键到目标窗口"""
        try:
            import time
            VK_RETURN = 0x0D
            KEYEVENTF_KEYUP = 0x0002
            time.sleep(0.01)
            user32.keybd_event(VK_RETURN, 0, 0, 0)
            user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)
        except Exception as e:
            print(f"[vk] send enter error: {e}")

    def _on_page_prev(self):
        if self.method and self.method.enabled:
            self.method.page_prev()

    def _on_page_next(self):
        if self.method and self.method.enabled:
            self.method.page_next()

    def _on_wildcard(self):
        pass

    def _on_segment(self):
        pass

    def _commit_punct(self, ch: str):
        """直接上屏符号/数字"""
        if self.method and self.method.enabled and self.method._on_commit:
            self.method._on_commit(ch)

    # ---------- 状态更新 ----------

    def update_state(self, state: InputState) -> None:
        is_phrase = (state.mode == MODE_PHRASE)
        if is_phrase:
            self.stroke_label.setText(f"联想：{state.last_char} ___")
        else:
            seq_display = " ".join(STROKE_NAMES.get(c, c) for c in state.sequence)
            self.stroke_label.setText(f"笔画：{seq_display}")

        page = state.current_page()
        for i, btn in enumerate(self.cand_buttons):
            if i < len(page):
                btn.setText(page[i])
                btn.setVisible(True)
                btn.setStyleSheet(self._candidate_style(i))
            else:
                btn.setText("")
                btn.setVisible(False)

    def show_for_status(self, enabled: bool) -> None:
        if enabled:
            self.status_label.setText("● 已启用")
            self.status_label.setStyleSheet("color: #16a34a; font-size: 11px;")
        else:
            self.status_label.setText("○ 已关闭")
            self.status_label.setStyleSheet("color: #94a3b8; font-size: 11px;")

    # ---------- 拖动 ----------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ---------- 关于对话框 ----------

    def _show_about(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("关于")
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint)
        dlg.setFixedSize(360, 260)

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(8)

        title = QLabel("笔画输入法")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e293b;")
        lay.addWidget(title)

        subtitle = QLabel("v1.0  ·  电脑端笔画输入工具")
        subtitle.setStyleSheet("font-size: 12px; color: #64748b;")
        lay.addWidget(subtitle)

        lay.addSpacing(4)

        info = QLabel(
            "开发者：独立开发<br><br>"
            "本软件采用 <b>GNU GPL v3</b> 协议发布。<br>"
            "您可以自由复制、修改和分发本软件。<br><br>"
            "<span style=\"color:#94a3b8;font-size:11px;\">"
            "本软件按\"现状\"提供，不提供任何明示或暗示的担保，"
            "包括但不限于适销性、特定用途适用性和非侵权性的担保。"
            "在任何情况下，作者均不对因使用本软件而产生的"
            "任何索赔、损害或其他责任承担责任。"
            "</span>"
        )
        info.setTextFormat(Qt.RichText)
        info.setWordWrap(True)
        info.setStyleSheet("color:#334155;font-size:12px;")
        lay.addWidget(info, 1)

        btn_ok = QPushButton("确定")
        btn_ok.clicked.connect(dlg.accept)
        btn_ok.setStyleSheet(
            "QPushButton{background:#3b82f6;color:white;border:none;"
            "border-radius:6px;padding:8px 24px;font-weight:bold;}"
            "QPushButton:hover{background:#2563eb;}"
        )
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(btn_ok)
        lay.addLayout(btn_row)

        dlg.exec_()
