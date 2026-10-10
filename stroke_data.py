"""
笔画数据库加载器
负责自动下载 Conway Stroke Data、本地缓存、并构建笔画序列到汉字的查询索引

数据格式（每行）：
    <数字笔画序列>\t<连续汉字字符串>
其中笔画数字（按 Conway/Nokia 传统定义）：
    1 = 横（horizontal；提也算横）
    2 = 竖（vertical；竖钩也算竖）
    3 = 撇（left-slash）
    4 = 捺（right-press；点也算捺）
    5 = 折（turn；弯也算折）
"""

from __future__ import annotations

import os
import sys
import json
import urllib.request
import urllib.error
from typing import Dict, List, Iterable, Tuple


def _get_app_dir() -> str:
    """程序所在目录（源码模式下 main.py 目录；打包后 exe 目录）"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _get_bundle_dir() -> str:
    """
    打包后的数据/资源目录（PyInstaller 的 _MEIPASS），
    也就是 exe 旁边的 _internal 目录。
    源码模式下返回程序目录。
    """
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    if getattr(sys, "frozen", False):
        # 有些版本 PyInstaller 没有 _MEIPASS，试一下 _internal
        internal = os.path.join(os.path.dirname(sys.executable), "_internal")
        if os.path.isdir(internal):
            return internal
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _get_user_data_dir() -> str:
    """用户数据目录（%APPDATA%\\StrokeInput），可写，用于缓存和用户记忆"""
    base = os.environ.get("APPDATA")
    if not base:
        base = os.path.expanduser("~")
    path = os.path.join(base, "StrokeInput")
    os.makedirs(path, exist_ok=True)
    return path


APP_DIR = _get_app_dir()
BUNDLE_DIR = _get_bundle_dir()
USER_DATA_DIR = _get_user_data_dir()

# Conway Stroke Data 仓库（CC-BY-4.0，© 2021–2026 Conway）
DATA_URL = "https://raw.githubusercontent.com/stroke-input/stroke-input-data/master/sequence-characters.txt"
RANKING_URL = "https://raw.githubusercontent.com/stroke-input/stroke-input-data/master/ranking-simplified.txt"
PHRASES_URL = "https://raw.githubusercontent.com/stroke-input/stroke-input-data/master/phrases-simplified.txt"

# 内置数据文件路径（随程序一起发布，在 BUNDLE_DIR 下，即打包后的 _internal 目录）
BUILTIN_SEQ_PATH = os.path.join(BUNDLE_DIR, "sequence-characters.txt")
BUILTIN_RANKING_PATH = os.path.join(BUNDLE_DIR, "ranking-simplified.txt")
BUILTIN_PHRASES_PATH = os.path.join(BUNDLE_DIR, "phrases-simplified.txt")
BUILTIN_INDEX_PATH = os.path.join(BUNDLE_DIR, "stroke_index.json")

# 用户缓存目录（可写）
CACHE_DIR = os.path.join(USER_DATA_DIR, ".cache")
RAW_CACHE_PATH = os.path.join(CACHE_DIR, "sequence-characters.txt")
INDEX_PATH = os.path.join(CACHE_DIR, "stroke_index.json")
RANKING_CACHE_PATH = os.path.join(CACHE_DIR, "ranking-simplified.txt")
PHRASES_CACHE_PATH = os.path.join(CACHE_DIR, "phrases-simplified.txt")

# 笔画数字 -> 中文名
STROKE_NAMES = {
    "1": "横",
    "2": "竖",
    "3": "撇",
    "4": "捺",
    "5": "折",
}


class StrokeData:
    """笔画数据索引"""

    def __init__(self) -> None:
        # 笔画序列 -> 汉字列表
        self.index: Dict[str, List[str]] = {}
        # 完整笔画序列 -> 汉字列表（精确匹配）
        self.full: Dict[str, List[str]] = {}
        # 字 -> 字频排名（数字越小越常用）
        self.ranking: Dict[str, int] = {}
        # 首字 -> 词组列表（联想词组）
        self.phrases_by_head: Dict[str, List[str]] = {}
        self.loaded = False

    # ---------- 加载 ----------

    def ensure_loaded(self) -> None:
        """首次调用时加载；优先使用内置索引，没有则用内置原始文件构建，再不行下载"""
        if self.loaded:
            return

        os.makedirs(CACHE_DIR, exist_ok=True)

        # 1. 优先用用户缓存目录里的索引（之前构建过）
        index_to_use = None
        if os.path.exists(INDEX_PATH):
            index_to_use = INDEX_PATH
        elif os.path.exists(BUILTIN_INDEX_PATH):
            # 2. 用程序目录下的内置索引（打包时一起放进去）
            index_to_use = BUILTIN_INDEX_PATH

        if index_to_use is not None:
            with open(index_to_use, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.full = {k: list(v) for k, v in payload.get("full", {}).items()}
            self.index = {k: list(v) for k, v in payload.get("index", {}).items()}
        else:
            # 3. 没有索引文件，从原始数据构建
            self._build_index_from_raw()

        # 加载字频排名
        self.ranking = self._load_ranking()
        # 用字频排名重新排序候选字
        self._apply_ranking_to_candidates()
        # 加载词组
        self.phrases_by_head = self._load_phrases()
        self.loaded = True

    def _build_index_from_raw(self) -> None:
        """从原始文本构建索引，优先用内置文件，不行则下载"""
        raw = None
        source = None

        if os.path.exists(BUILTIN_SEQ_PATH):
            with open(BUILTIN_SEQ_PATH, "r", encoding="utf-8") as f:
                raw = f.read()
            source = f"内置: {BUILTIN_SEQ_PATH}"
        elif os.path.exists(RAW_CACHE_PATH):
            with open(RAW_CACHE_PATH, "r", encoding="utf-8") as f:
                raw = f.read()
            source = f"缓存: {RAW_CACHE_PATH}"
        else:
            # 下载
            print(f"[stroke_data] 首次运行，正在下载 Conway Stroke Data ...")
            try:
                req = urllib.request.Request(
                    DATA_URL,
                    headers={"User-Agent": "stroke-input-pc/1.0"},
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    raw = resp.read().decode("utf-8")
                os.makedirs(CACHE_DIR, exist_ok=True)
                with open(RAW_CACHE_PATH, "w", encoding="utf-8") as f:
                    f.write(raw)
                source = f"下载: {DATA_URL}"
            except Exception as e:
                print(f"[stroke_data] 下载失败: {e}")
                print("[stroke_data] 请检查网络或手动放入 sequence-characters.txt")
                sys.exit(1)

        print(f"[stroke_data] 数据源: {source}")
        self._build_index(raw)

    def _build_index(self, raw: str) -> None:
        """从原始文本构建两个索引：
        - full:  精确笔画序列 -> 汉字列表
        - index: 前缀笔画序列 -> 汉字列表（用于边输入边提示）
        每行格式：<数字序列>\t<连续汉字字符串>
        """
        full: Dict[str, List[str]] = {}
        prefix: Dict[str, List[str]] = {}

        for line in raw.splitlines():
            # 不要 strip() 掉 Tab 之间的内容，只去行尾换行
            line = line.rstrip("\r\n")
            if not line or line.lstrip().startswith("#"):
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            seq, chars_field = parts
            seq = seq.strip()
            # 第二列是连续汉字字符串，直接拆成单字
            chars: List[str] = list(chars_field)
            if not chars:
                continue

            full.setdefault(seq, []).extend(chars)

            # 同时为每个前缀建立索引
            for i in range(1, len(seq) + 1):
                prefix.setdefault(seq[:i], []).extend(chars)

        # 去重保序
        for seq in full:
            full[seq] = list(dict.fromkeys(full[seq]))
        for seq in prefix:
            prefix[seq] = list(dict.fromkeys(prefix[seq]))

        # 保存到用户缓存目录（可写）
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump({"full": full, "index": prefix}, f, ensure_ascii=False)
        print(f"[stroke_data] 索引构建完成：full={len(full)} 条，prefix={len(prefix)} 条")
        print(f"[stroke_data] 索引已缓存到: {INDEX_PATH}")

    def _load_ranking(self) -> Dict[str, int]:
        """
        加载字频排名文件。优先顺序：用户缓存 > 程序内置 > 下载
        返回 字 -> 排名（数字越小越常用）
        """
        path_to_use = None
        if os.path.exists(RANKING_CACHE_PATH):
            path_to_use = RANKING_CACHE_PATH
        elif os.path.exists(BUILTIN_RANKING_PATH):
            path_to_use = BUILTIN_RANKING_PATH
        else:
            # 下载
            print(f"[stroke_data] 未找到 ranking 文件，尝试下载 ...")
            try:
                req = urllib.request.Request(
                    RANKING_URL,
                    headers={"User-Agent": "stroke-input-pc/1.0"},
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    raw = resp.read().decode("utf-8")
                os.makedirs(CACHE_DIR, exist_ok=True)
                with open(RANKING_CACHE_PATH, "w", encoding="utf-8") as f:
                    f.write(raw)
                path_to_use = RANKING_CACHE_PATH
                print(f"[stroke_data] ranking 下载成功")
            except Exception as e:
                print(f"[stroke_data] ranking 下载失败: {e}（候选字将按 Unicode 顺序显示）")
                return {}

        ranking: Dict[str, int] = {}
        if path_to_use is None:
            return ranking
        # 解析：跳过 # 注释行，对其他行的每个字按出现顺序赋排名
        with open(path_to_use, "r", encoding="utf-8") as f:
            content = f.read()
        rank = 0
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for ch in line:
                # 第一次出现的位置决定排名（注释中说"If a character appears more than once, the ranking from its earliest appearance will prevail"）
                if ch not in ranking:
                    ranking[ch] = rank
                    rank += 1
        print(f"[stroke_data] 字频排名加载完成：共 {len(ranking)} 字")
        return ranking

    def _apply_ranking_to_candidates(self) -> None:
        """
        用字频排名重新排序 self.full 和 self.index 里的汉字列表：
        - 排名小的（更常用）排前面
        - 没有排名的字（ranking 里没有）放在最后，保留原相对顺序
        - 稳定排序：同分按原顺序
        """
        if not self.ranking:
            return
        BIG = 10_000_000  # 没在表中的字的默认排名
        for seq, chars in self.full.items():
            self.full[seq] = sorted(chars, key=lambda c: self.ranking.get(c, BIG))
        for seq, chars in self.index.items():
            self.index[seq] = sorted(chars, key=lambda c: self.ranking.get(c, BIG))

    def _load_phrases(self) -> Dict[str, List[str]]:
        """
        加载词组文件，构建"首字 -> [词组列表]"索引。
        优先顺序：用户缓存 > 程序内置 > 下载
        """
        path = None
        if os.path.exists(PHRASES_CACHE_PATH):
            path = PHRASES_CACHE_PATH
        elif os.path.exists(BUILTIN_PHRASES_PATH):
            path = BUILTIN_PHRASES_PATH
        else:
            print(f"[stroke_data] 词组文件未找到，尝试下载 ...")
            try:
                req = urllib.request.Request(
                    PHRASES_URL,
                    headers={"User-Agent": "stroke-input-pc/1.0"},
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    raw = resp.read().decode("utf-8")
                os.makedirs(CACHE_DIR, exist_ok=True)
                with open(PHRASES_CACHE_PATH, "w", encoding="utf-8") as f:
                    f.write(raw)
                path = PHRASES_CACHE_PATH
                print(f"[stroke_data] 词组下载成功")
            except Exception as e:
                print(f"[stroke_data] 词组下载失败: {e}（联想词组功能不可用）")
                return {}

        phrases_by_head: Dict[str, List[str]] = {}
        if path is None:
            return phrases_by_head
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 跳过 HTML 标签如 <phrases> </phrases>
            if line.startswith("<") and line.endswith(">"):
                continue
            if len(line) < 2:
                continue  # 单字不算词组
            head = line[0]
            phrases_by_head.setdefault(head, []).append(line)

        # 每个首字下：按 (词组长度, 字典序) 排序
        for head, plist in phrases_by_head.items():
            plist.sort(key=lambda p: (len(p), p))

        total = sum(len(v) for v in phrases_by_head.values())
        print(f"[stroke_data] 词组索引构建完成：{len(phrases_by_head)} 首字，{total} 个词组")
        return phrases_by_head

    # ---------- 查询 ----------

    def lookup(self, sequence: str) -> List[str]:
        """按完整笔画序列精确查询；若找不到则返回空"""
        self.ensure_loaded()
        return list(self.full.get(sequence, []))

    def lookup_prefix(self, sequence: str) -> List[str]:
        """按前缀查询（边输入边显示候选）"""
        self.ensure_loaded()
        if not sequence:
            return []
        return list(self.index.get(sequence, []))

    def lookup_phrases(self, head_char: str) -> List[str]:
        """查询以 head_char 开头的词组"""
        self.ensure_loaded()
        return list(self.phrases_by_head.get(head_char, []))


# 单例
_data_singleton: StrokeData | None = None


def get_data() -> StrokeData:
    global _data_singleton
    if _data_singleton is None:
        _data_singleton = StrokeData()
        _data_singleton.ensure_loaded()
    return _data_singleton


if __name__ == "__main__":
    # 命令行直接运行：仅下载并构建索引，不启动输入法
    d = StrokeData()
    d.ensure_loaded()
    print(f"full entries: {len(d.full)}")
    print(f"prefix entries: {len(d.index)}")
    # 简单自测：1=横 3=撇 4=捺 -> "大"
    print(f"笔画序列 '134' (横-撇-捺) -> {d.lookup('134')[:10]}")
    print(f"前缀 '13' (横-撇) -> {d.lookup_prefix('13')[:10]}")
