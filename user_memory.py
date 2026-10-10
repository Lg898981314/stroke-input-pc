"""
用户输入记忆模块
- 记录用户选过的每个字/词的使用次数
- 越常用的字/词，候选排序越靠前
- 自动持久化到本地 JSON 文件，下次启动自动加载
- 有上限保护，防止无限膨胀
"""

from __future__ import annotations

import json
import os
import sys
from typing import Dict, List

# 用户数据目录（可写）
def _get_user_dir() -> str:
    base = os.environ.get("APPDATA")
    if not base:
        base = os.path.expanduser("~")
    path = os.path.join(base, "StrokeInput")
    os.makedirs(path, exist_ok=True)
    return path

MEMORY_PATH = os.path.join(_get_user_dir(), "user_memory.json")
# 记忆上限（最多记多少个条目）
MAX_ENTRIES = 5000
# 权重：使用一次加多少分
SCORE_INCREMENT = 100
# 衰减：每次排序后整体轻微衰减，让长期不用的慢慢降下去（暂未启用，先简化）


class UserMemory:
    """用户输入记忆（使用次数统计 + 持久化）"""

    def __init__(self, path: str = MEMORY_PATH) -> None:
        self.path = path
        # 键：字或词组字符串；值：使用次数（整数）
        self.scores: Dict[str, int] = {}
        self._loaded = False

    def load(self) -> None:
        """从磁盘加载记忆"""
        if self._loaded:
            return
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.scores = {str(k): int(v) for k, v in data.items()
                                   if isinstance(v, (int, float))}
                    print(f"[user_memory] 已加载记忆：{len(self.scores)} 条")
            except Exception as e:
                print(f"[user_memory] 加载失败: {e}，将重新开始")
                self.scores = {}
        self._loaded = True

    def save(self) -> None:
        """保存到磁盘"""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.scores, f, ensure_ascii=False)
        except Exception as e:
            print(f"[user_memory] 保存失败: {e}")

    def add(self, item: str) -> None:
        """用户选了这个字/词，加一次分"""
        if not item:
            return
        self.load()
        current = self.scores.get(item, 0)
        self.scores[item] = current + SCORE_INCREMENT
        # 超限清理：淘汰最低分的
        if len(self.scores) > MAX_ENTRIES:
            # 按分数升序排，砍掉最低的 10%
            sorted_items = sorted(self.scores.items(), key=lambda x: x[1])
            cut = int(MAX_ENTRIES * 0.1)
            if cut < 1:
                cut = 1
            to_remove = sorted_items[:cut]
            for k, _ in to_remove:
                del self.scores[k]
        # 每次加分后自动保存（简单可靠）
        self.save()

    def get_score(self, item: str) -> int:
        """获取某个字/词的得分，没有则返回 0"""
        self.load()
        return self.scores.get(item, 0)

    def sort_items(self, items: List[str]) -> List[str]:
        """
        按记忆得分重排序：
        - 有记忆得分的排前面，得分越高越靠前
        - 没有记忆的保持原顺序排后面
        - 稳定排序
        """
        self.load()
        if not items:
            return items
        BIG = 10_000_000
        # 用负分数升序 = 高分局前；无记忆的用 BIG 排到后面
        return sorted(items, key=lambda c: (-self.scores.get(c, 0), items.index(c)))

    def clear(self) -> None:
        """清空记忆"""
        self.scores.clear()
        if os.path.exists(self.path):
            try:
                os.remove(self.path)
            except Exception:
                pass
        print("[user_memory] 记忆已清空")


# 单例
_memory_singleton: UserMemory | None = None


def get_memory() -> UserMemory:
    global _memory_singleton
    if _memory_singleton is None:
        _memory_singleton = UserMemory()
    return _memory_singleton
