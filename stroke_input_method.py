"""
笔画输入法核心逻辑（含联想词组）
- 维护当前已输入的笔画序列
- 按前缀查询候选字
- 单字上屏后自动进入"联想模式"，提示以该字开头的词组
- 选词组后只补上首字之后的部分（避免首字重复）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from stroke_data import get_data, STROKE_NAMES
from user_memory import get_memory
from config import get_config

PAGE_SIZE = 9  # 每页候选数量（对应主键盘 1-9）


def get_key_to_stroke() -> dict:
    """从配置读取按键映射"""
    cfg = get_config()
    return dict(cfg.keymap)


MODE_STROKE = "stroke"   # 笔画输入模式
MODE_PHRASE = "phrase"   # 联想词组模式（单字上屏后自动进入）


@dataclass
class InputState:
    """当前输入会话状态"""
    # 笔画模式字段
    sequence: str = ""                          # 已输入笔画序列
    candidates: List[str] = field(default_factory=list)
    page_index: int = 0
    # 联想模式字段
    mode: str = MODE_STROKE                     # 'stroke' or 'phrase'
    last_char: str = ""                         # 最近上屏的字（联想首字）
    phrase_candidates: List[str] = field(default_factory=list)
    phrase_page: int = 0
    # 历史记录
    committed_chars: List[str] = field(default_factory=list)

    def reset_stroke(self) -> None:
        """清空笔画模式字段，保留其他"""
        self.sequence = ""
        self.candidates = []
        self.page_index = 0

    def reset_phrase(self) -> None:
        self.last_char = ""
        self.phrase_candidates = []
        self.phrase_page = 0
        self.mode = MODE_STROKE

    def reset_all(self) -> None:
        self.reset_stroke()
        self.reset_phrase()

    def current_page(self) -> List[str]:
        """当前模式的当前页候选（单字 or 词组）"""
        if self.mode == MODE_PHRASE:
            start = self.phrase_page * PAGE_SIZE
            return self.phrase_candidates[start:start + PAGE_SIZE]
        start = self.page_index * PAGE_SIZE
        return self.candidates[start:start + PAGE_SIZE]

    def total_pages(self) -> int:
        cands = self.phrase_candidates if self.mode == MODE_PHRASE else self.candidates
        if not cands:
            return 0
        return (len(cands) + PAGE_SIZE - 1) // PAGE_SIZE

    def current_page_index(self) -> int:
        return self.phrase_page if self.mode == MODE_PHRASE else self.page_index


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
        """添加一笔；key 为 NumPad 数字字符 '7'..'9' '4' '5'"""
        if not self.enabled:
            return False
        stroke = get_key_to_stroke().get(key)
        if not stroke:
            return False
        # 如果当前在联想模式，先退出（开始新字的输入）
        if self.state.mode == MODE_PHRASE:
            self.state.reset_phrase()
        self.state.sequence += stroke
        self._refresh_candidates()
        return True

    def backspace(self) -> bool:
        """删除最后一笔（联想模式下 Esc 等效）"""
        if not self.enabled:
            return False
        if self.state.mode == MODE_PHRASE:
            # 联想模式下 Backspace 退出联想
            self.state.reset_phrase()
            self._notify_candidates()
            return True
        if not self.state.sequence:
            return True
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
        # 前缀匹配包含 exact 字，并已按字频排序（高频字在前）
        # 先取基础候选
        base = self._data.lookup_prefix(self.state.sequence)
        # 再按用户自己的使用记忆重排（用过的字排更前）
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
            if self.state.mode == MODE_PHRASE:
                self.state.phrase_page += 1
            else:
                self.state.page_index += 1
            self._notify_candidates()
            return True
        return False

    def page_prev(self) -> bool:
        if not self.state.current_page():
            return False
        if self.state.current_page_index() > 0:
            if self.state.mode == MODE_PHRASE:
                self.state.phrase_page -= 1
            else:
                self.state.page_index -= 1
            self._notify_candidates()
            return True
        return False

    # ---------- 单字选择 ----------

    def select_index(self, idx: int) -> bool:
        """选择当前页第 idx 个候选（idx 从 0 开始）
        - 笔画模式：选单字，上屏，进入联想模式
        - 联想模式：选词组，补上首字之后的部分
        """
        if not self.enabled:
            return False
        page = self.state.current_page()
        if idx < 0 or idx >= len(page):
            return False

        if self.state.mode == MODE_PHRASE:
            return self._select_phrase(idx, page[idx])

        # 笔画模式：选单字
        char = page[idx]
        self._commit(char)
        self.state.committed_chars.append(char)
        # 记录到用户记忆，下次这个字会排更前
        self._memory.add(char)
        # 选字即完成：直接清空本次输入，候选窗口隐藏。
        # 不自动进入联想模式，避免用户还要再确认/退出一次。
        self.state.reset_all()
        self._notify_candidates()
        return True

    def select_first(self) -> bool:
        """空格/回车：选第一个候选"""
        if not self.state.current_page():
            return False
        return self.select_index(0)

    def _enter_phrase_mode(self, char: str) -> None:
        """单字上屏后进入联想模式"""
        phrases = self._data.lookup_phrases(char)
        if phrases:
            self.state.mode = MODE_PHRASE
            self.state.last_char = char
            self.state.phrase_candidates = phrases
            self.state.phrase_page = 0
            # 清空笔画字段
            self.state.sequence = ""
            self.state.candidates = []
            self.state.page_index = 0
        else:
            # 没有词组，直接清空准备下一次输入
            self.state.reset_all()
        self._notify_candidates()

    def _select_phrase(self, idx: int, phrase: str) -> bool:
        """选词组：只上屏首字之后的部分"""
        # 首字已经在笔画模式上屏过，这里补上剩余
        remaining = phrase[1:] if len(phrase) > 1 else ""
        if remaining:
            self._commit(remaining)
            self.state.committed_chars.append(remaining)
        # 记录到用户记忆
        self._memory.add(phrase)
        # 选完词组回到笔画模式
        self.state.reset_all()
        self._notify_candidates()
        return True

    def _commit(self, text: str) -> None:
        if self._on_commit:
            self._on_commit(text)

    # ---------- 调试用 ----------

    def sequence_display(self) -> str:
        """把当前笔画序列转为可读符号"""
        return "".join(STROKE_NAMES.get(c, c) for c in self.state.sequence)
