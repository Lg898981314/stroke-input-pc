"""
配置文件读写模块
- 从 config.json 读取配置
- 支持用户自定义笔画键映射、符号列表、界面设置
- 配置文件与 exe 同目录（或源码模式下与 main.py 同目录）
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List


def get_app_dir() -> str:
    """
    获取程序所在目录
    - 打包后 exe 所在目录
    - 开发模式下 main.py 所在目录
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_bundle_dir() -> str:
    """
    打包后资源/数据所在目录（PyInstaller 的 _MEIPASS，即 _internal 目录），
    源码模式下返回程序目录。
    """
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    if getattr(sys, "frozen", False):
        internal = os.path.join(os.path.dirname(sys.executable), "_internal")
        if os.path.isdir(internal):
            return internal
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_user_dir() -> str:
    """用户可写目录（APPDATA/StrokeInput）"""
    base = os.environ.get("APPDATA")
    if not base:
        base = os.path.expanduser("~")
    path = os.path.join(base, "StrokeInput")
    os.makedirs(path, exist_ok=True)
    return path


APP_DIR = get_app_dir()
BUNDLE_DIR = get_bundle_dir()
USER_DIR = get_user_dir()

# 配置文件：优先读用户目录（用户改过的），其次读 bundle 目录的内置配置
# 写入永远写到用户目录
BUILTIN_CONFIG_PATH = os.path.join(BUNDLE_DIR, "config.json")
USER_CONFIG_PATH = os.path.join(USER_DIR, "config.json")

# 默认配置（config.json 不存在时使用）
DEFAULT_CONFIG: Dict[str, Any] = {
    "keymap": {
        "7": "1",
        "8": "2",
        "9": "3",
        "4": "4",
        "5": "5",
    },
    "stroke_buttons": {
        "rows": [
            [
                {"label": "一", "stroke": "1", "type": "stroke"},
                {"label": "丨", "stroke": "2", "type": "stroke"},
                {"label": "丿", "stroke": "3", "type": "stroke"},
            ],
            [
                {"label": "丶", "stroke": "4", "type": "stroke"},
                {"label": "𠃍", "stroke": "5", "type": "stroke"},
                {"label": "通配", "type": "wildcard"},
            ],
            [
                {"label": "分词", "type": "action", "action": "segment"},
                {"label": "：", "type": "symbol"},
                {"label": "；", "type": "symbol"},
            ],
        ]
    },
    "symbols": {
        "left_col": ["，", "。", "？", "！"],
        "extra_symbols": {
            "rows": [
                ["、", "：", "；", '"', '"', """, """, "（"],
                ["）", "【", "】", "…", "—", "～", "·", "《"],
                ["》", "〈", "〉", "「", "」", "『", "』", "•"],
                ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧"],
                ["⑨", "⑩", "Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ"],
                ["Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ", "↑", "↓", "←", "→"],
                ["〓", "■", "◆", "●", "▲", "★", "☆", "◇"],
                ["%", "#", "@", "&", "*", "×", "÷", "±"],
                ["℃", "‰", "§", "№", "€", "￡", "￥", "＄"],
                ["〇", "壹", "贰", "叁", "肆", "伍", "陆", "柒"],
                ["捌", "玖", "拾", "佰", "仟", "万", "亿", "兆"],
            ]
        },
    },
    "ui": {
        "page_size": 9,
        "candidate_font_size": 20,
        "key_font_size": 26,
        "show_status_indicator": True,
        "window_on_top": True,
    },
}


class Config:
    """配置管理器（单例）"""

    def __init__(self) -> None:
        self.data: Dict[str, Any] = {}
        self._loaded = False

    def _get_read_path(self) -> str | None:
        """优先读用户配置，其次读程序目录的内置配置"""
        if os.path.exists(USER_CONFIG_PATH):
            return USER_CONFIG_PATH
        if os.path.exists(BUILTIN_CONFIG_PATH):
            return BUILTIN_CONFIG_PATH
        return None

    def load(self) -> None:
        """从文件加载；不存在则用默认值并写回用户目录"""
        read_path = self._get_read_path()
        if read_path:
            try:
                with open(read_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                print(f"[config] 已加载配置: {read_path}")
                self._loaded = True
                return
            except Exception as e:
                print(f"[config] 加载失败: {e}，使用默认配置")

        # 不存在或加载失败：用默认并保存到用户目录
        self.data = json.loads(json.dumps(DEFAULT_CONFIG))
        self._loaded = True
        self.save()

    def save(self) -> None:
        """保存到用户目录（可写）"""
        try:
            os.makedirs(USER_DIR, exist_ok=True)
            with open(USER_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            print(f"[config] 配置已保存: {USER_CONFIG_PATH}")
        except Exception as e:
            print(f"[config] 保存失败: {e}")

    # ---------- 快捷访问 ----------

    @property
    def keymap(self) -> Dict[str, str]:
        """物理按键 -> 笔画数字（过滤掉 _comment 等注释键）"""
        raw = self.data.get("keymap", DEFAULT_CONFIG["keymap"])
        return {k: v for k, v in raw.items() if not k.startswith("_")}

    @property
    def stroke_button_rows(self) -> List[List[dict]]:
        """笔画按钮行配置"""
        sb = self.data.get("stroke_buttons", {})
        return sb.get("rows", DEFAULT_CONFIG["stroke_buttons"]["rows"])

    @property
    def left_col_symbols(self) -> List[str]:
        """左列符号"""
        sym = self.data.get("symbols", {})
        return sym.get("left_col", DEFAULT_CONFIG["symbols"]["left_col"])

    @property
    def extra_symbol_rows(self) -> List[List[str]]:
        """更多符号（符面板）—— 旧格式兼容，返回第一页内容"""
        pages = self.symbol_pages
        if pages:
            return pages[0].get("rows", [])
        return []

    @property
    def symbol_pages(self) -> List[dict]:
        """符号面板分页：[{name, rows: [[...], ...]}, ...]"""
        sym = self.data.get("symbols", {})
        sp = sym.get("symbol_pages", {})
        pages = sp.get("pages", [])
        if pages:
            return pages
        # 兼容旧格式 extra_symbols
        extra = sym.get("extra_symbols", {})
        rows = extra.get("rows", DEFAULT_CONFIG["symbols"]["symbol_pages"]["pages"][0]["rows"])
        return [{"name": "符号", "rows": rows}]

    @property
    def ui(self) -> Dict[str, Any]:
        return self.data.get("ui", DEFAULT_CONFIG["ui"])

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


# 单例
_config_singleton: Config | None = None


def get_config() -> Config:
    global _config_singleton
    if _config_singleton is None:
        _config_singleton = Config()
        _config_singleton.load()
    return _config_singleton
