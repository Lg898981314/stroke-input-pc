"""
笔画输入法核心逻辑
- 维护当前已输入的笔画序列
- 按前缀查询候选字
- 选字后直接上屏
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from stroke_data import get_data, STROKE_NAMES
from user_memory import get_memory
from config import get_config


def get_page_size() -> int:
    """从配置读取每页候选数"""
    cfg = get_config()
    return int(cfg.ui.get("page_size", 5))


def get_key_to_stroke() -> dict:
    """从配置读取按键映射"""
    cfg = get_config()
    return dict(cfg.keymap)


MODE_STROKE = "stroke"   # 笔画输入模式


@dataclass
class InputState:
    """当前输入会话状态"""
    sequence: str = ""                          # 已输入笔画序列
    candidates: List[str] = field(default_factory=list)
    page_index: int = 0
    mode: str = MODE_STROKE                     # 只有笔画模式
    committed_chars: List[str] = field(default_factory=list)

    def reset(self) -> None:
        """清空所有输入状态"""
        self.sequence = ""
        self.candidates = []
        self.page_index = 0

    def current_page(self) -> List[str]:
        """当前页候选"""
        page_size = get_page_size()
        start = self.page_index * page_size
        return self.candidates[start:start + page_size]

    def total_pages(self) -> int:
        page_size = get_page_size()
        if not self.candidates:
            return 0
        return (len(self.candidates) + page_size - 1) // page_size

    def current_page_index(self) -> int:
        return self.page_index


class StrokeInputMethod:
    """笔画输入法状态机"""

    def __init__(self,
                 on_candidates_updated: Optional[Callable[[InputState], None]] = None,
                 on_commit: Optional[Callable[[str], None]] = None,
                 on_status_change: Optional[Callable[[bool], None]] = None) -> None:
        self.state = InputState()
        self.enabled = False
        self._data = get_data()
        self._memory = get_memory()
        self._on_candidates_updated = on_candidates_updated
        self._on_commit = on_commit
        self._on_status_change = on_status_change

    # ---------- 开关 ----------

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        if not self.enabled:
            self.state.reset()
        if self._on_status_change:
            self._on_status_change(self.enabled)
        return self.enabled

    def enable(self, value: bool) -> None:
        if self.enabled != value:
            self.toggle()

    # ---------- 笔画输入 ----------

    def add_stroke(self, key: str) -> bool:
        """添加一笔；key 为 NumPad 数字字符"""
        if not self.enabled:
            return False
        stroke = get_key_to_stroke().get(key)
        if not stroke:
            return False
        self.state.sequence += stroke
        self._refresh_candidates()
        return True

    def backspace(self) -> bool:
        """删除最后一笔；无笔画时返回 False 由外部处理删文字"""
        if not self.enabled:
            return False
        if not self.state.sequence:
            return False  # 空的时候 Backspace 由外部处理（删已上屏文字）
        self.state.sequence = self.state.sequence[:-1]
        if self.state.sequence:
            self._refresh_candidates()
        else:
            self.state.candidates = []
            self.state.page_index = 0
            self._notify_candidates()
        return True

    def escape(self) -> bool:
        """清空当前会话"""
        if not self.enabled:
            return False
        self.state.reset()
        self._notify_candidates()
        return True

    # ---------- 候选刷新 ----------

    def _refresh_candidates(self) -> None:
        # 前缀匹配，按字频 + 用户记忆排序
        base = self._data.lookup_prefix(self.state.sequence)
        self.state.candidates = self._memory.sort_items(base)
        self.state.page_index = 0
        self._notify_candidates()

    def _notify_candidates(self) -> None:
        if self._on_candidates_updated:
            self._on_candidates_updated(self.state)

    def page_next(self) -> bool:
        if not self.state.current_page():
            return False
        if self.state.current_page_index() + 1 < self.state.total_pages():
            self.state.page_index += 1
            self._notify_candidates()
            return True
        return False

    def page_prev(self) -> bool:
        if not self.state.current_page():
            return False
        if self.state.current_page_index() > 0:
            self.state.page_index -= 1
            self._notify_candidates()
            return True
        return False

    # ---------- 候选选择 ----------

    def select_index(self, idx: int) -> bool:
        """选择当前页第 idx 个候选（idx 从 0 开始），直接上屏"""
        if not self.enabled:
            return False
        page = self.state.current_page()
        if idx < 0 or idx >= len(page):
            return False
        char = page[idx]
        self._commit(char)
        self.state.committed_chars.append(char)
        self._memory.add(char)
        self.state.reset()
        self._notify_candidates()
        return True

    def select_first(self) -> bool:
        """空格/回车：选第一个候选，直接上屏"""
        if not self.state.current_page():
            return False
        return self.select_index(0)

    def _commit(self, text: str) -> None:
        if self._on_commit:
            self._on_commit(text)

    # ---------- 调试用 ----------

    def sequence_display(self) -> str:
        """把当前笔画序列转为可读符号"""
        return "".join(STROKE_NAMES.get(c, c) for c in self.state.sequence)
