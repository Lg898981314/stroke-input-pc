"""
笔画输入法核心逻辑（字词混合候选模式）
- 维护当前已输入的笔画序列
- 按前缀查询候选字
- 选字后进入"字词混合候选"模式：候选 = [单字] + 联想词组
  - 选单字 → 直接上屏单字
  - 选词组 → 直接上屏整个词组
  - 都是一步确认，不需要两步
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
MODE_CONFIRM = "confirm"  # 字词混合候选模式（选字后，单字+联想词一起显示）


@dataclass
class InputState:
    """当前输入会话状态"""
    # 笔画模式字段
    sequence: str = ""                          # 已输入笔画序列
    candidates: List[str] = field(default_factory=list)
    page_index: int = 0
    # 模式
    mode: str = MODE_STROKE                     # 'stroke' or 'confirm'
    # 确认模式字段（字词混合候选）
    confirm_char: str = ""                      # 当前待确认的单字
    confirm_items: List[str] = field(default_factory=list)  # [单字, 词组1, 词组2, ...]
    confirm_page: int = 0
    # 历史记录
    committed_chars: List[str] = field(default_factory=list)

    def reset_stroke(self) -> None:
        """清空笔画模式字段"""
        self.sequence = ""
        self.candidates = []
        self.page_index = 0

    def reset_confirm(self) -> None:
        self.confirm_char = ""
        self.confirm_items = []
        self.confirm_page = 0
        self.mode = MODE_STROKE

    def reset_all(self) -> None:
        self.reset_stroke()
        self.reset_confirm()

    def current_page(self) -> List[str]:
        """当前模式的当前页候选"""
        page_size = get_page_size()
        if self.mode == MODE_CONFIRM:
            start = self.confirm_page * page_size
            return self.confirm_items[start:start + page_size]
        start = self.page_index * page_size
        return self.candidates[start:start + page_size]

    def total_pages(self) -> int:
        page_size = get_page_size()
        cands = self.confirm_items if self.mode == MODE_CONFIRM else self.candidates
        if not cands:
            return 0
        return (len(cands) + page_size - 1) // page_size

    def current_page_index(self) -> int:
        return self.confirm_page if self.mode == MODE_CONFIRM else self.page_index


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
            self.state.reset_all()
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
        # 如果在确认模式，先上屏当前字，再开始新字
        if self.state.mode == MODE_CONFIRM:
            self._commit_current_char()
            self.state.reset_confirm()
        self.state.sequence += stroke
        self._refresh_candidates()
        return True

    def backspace(self) -> bool:
        """删除最后一笔；确认模式下退回笔画模式"""
        if not self.enabled:
            return False
        if self.state.mode == MODE_CONFIRM:
            # 退回笔画模式，恢复之前的笔画候选
            self.state.reset_confirm()
            if self.state.sequence:
                self._refresh_candidates()
            else:
                self._notify_candidates()
            return True
        if not self.state.sequence:
            return True  # 空的时候 Backspace 由外部处理（删已上屏文字）
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
        self.state.reset_all()
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
            if self.state.mode == MODE_CONFIRM:
                self.state.confirm_page += 1
            else:
                self.state.page_index += 1
            self._notify_candidates()
            return True
        return False

    def page_prev(self) -> bool:
        if not self.state.current_page():
            return False
        if self.state.current_page_index() > 0:
            if self.state.mode == MODE_CONFIRM:
                self.state.confirm_page -= 1
            else:
                self.state.page_index -= 1
            self._notify_candidates()
            return True
        return False

    # ---------- 候选选择 ----------

    def select_index(self, idx: int) -> bool:
        """选择当前页第 idx 个候选（idx 从 0 开始）
        - 笔画模式：选字，进入确认模式（单字+联想词一起显示）
        - 确认模式：选单字 → 上屏单字；选词组 → 上屏整个词组
        """
        if not self.enabled:
            return False
        page = self.state.current_page()
        if idx < 0 or idx >= len(page):
            return False

        if self.state.mode == MODE_CONFIRM:
            return self._select_confirm(idx, page[idx])

        # 笔画模式：选字 → 进入确认模式
        char = page[idx]
        self._enter_confirm_mode(char)
        return True

    def select_first(self) -> bool:
        """空格/回车：选第一个候选"""
        if not self.state.current_page():
            return False
        # 笔画模式下，空格 = 选首字进入确认模式
        # 确认模式下，空格 = 上屏首项（单字或词组）
        return self.select_index(0)

    def _enter_confirm_mode(self, char: str) -> None:
        """选字后进入字词混合候选模式"""
        self.state.mode = MODE_CONFIRM
        self.state.confirm_char = char
        # 构建候选列表：第1个是单字本身，后面是联想词组
        phrases = self._data.lookup_phrases(char)
        items = [char] + phrases
        # 用用户记忆排一下词组部分（单字固定在第1位）
        if len(items) > 1:
            word_part = items[1:]
            word_part = self._memory.sort_items(word_part)
            items = [char] + word_part
        self.state.confirm_items = items
        self.state.confirm_page = 0
        # 清空笔画字段（笔画模式的数据保留在 sequence/candidates 里，Backspace 能退回）
        self._notify_candidates()

    def _select_confirm(self, idx: int, item: str) -> bool:
        """确认模式下选择候选"""
        if idx == 0:
            # 选的是单字本身 → 上屏单字
            self._commit(self.state.confirm_char)
            self.state.committed_chars.append(self.state.confirm_char)
            self._memory.add(self.state.confirm_char)
        else:
            # 选的是词组 → 直接上屏整个词组
            self._commit(item)
            self.state.committed_chars.append(item)
            self._memory.add(item)
        # 选完结束
        self.state.reset_all()
        self._notify_candidates()
        return True

    def _commit_current_char(self) -> None:
        """确认模式下，上屏当前单字（比如用户开始打新字时）"""
        if self.state.mode == MODE_CONFIRM and self.state.confirm_char:
            self._commit(self.state.confirm_char)
            self.state.committed_chars.append(self.state.confirm_char)
            self._memory.add(self.state.confirm_char)

    def _commit(self, text: str) -> None:
        if self._on_commit:
            self._on_commit(text)

    # ---------- 调试用 ----------

    def sequence_display(self) -> str:
        """把当前笔画序列转为可读符号"""
        return "".join(STROKE_NAMES.get(c, c) for c in self.state.sequence)
