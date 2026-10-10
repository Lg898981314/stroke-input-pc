# 笔画输入法 (Stroke Input Method for PC)

一款运行在 Windows 上的**电脑端笔画输入法**，仿手机九宫格笔画输入法布局，支持虚拟键盘点击和物理小键盘输入。

## ✨ 功能特性

- **五笔画输入**：横(一)、竖(丨)、撇(丿)、捺(丶)、折(𠃍)，对应手机九宫格布局
- **双输入方式**：虚拟键盘鼠标点击 + 物理 NumPad 小键盘
- **智能候选**：基于 Conway Stroke Data，6 万+ 汉字，按字频排序
- **用户记忆**：常用字自动置顶，越用越顺手
- **多主题**：6 种配色主题（浅色 / 深色 / 蓝色 / 绿色 / 粉色 / 橙色）
- **符号面板**：14 类符号（常用/数字/数学/箭头/图形/单位/货币/希腊/拼音/平假/片假/俄文/表情/其他）
- **数字键盘**：一键切换数字键盘
- **表情直达**：一键打开表情面板
- **换行按钮**：虚拟键盘直接换行
- **系统托盘**：最小化到托盘，不占任务栏
- **全局热键**：`Ctrl + \`` 显示/隐藏键盘，`F2` 开关输入法
- **窗口置顶**：始终在最上层，不被其他窗口遮挡
- **不抢焦点**：点击键盘不会抢走输入框焦点

## 🖼️ 界面预览

### 主键盘
```
┌───────────────────────────────────┐
│ 笔画输入法 ● 已启用  🎨 ℹ — ✕    │
├───────────────────────────────────┤
│ 笔画：丿一                         │
│ ┌──┐┌──┐┌──┐┌──┐┌──┐             │
│ │我││和││手││看││生│             │  ← 5个候选字
│ └──┘└──┘└──┘└──┘└──┘             │
├────┬───────────────┬─────────────┤
│ 符 │  一   丨   丿  │  删除       │
│123 │               │             │
│ 😀 │  丶   𠃍  通配 │  重输       │
│ ， │               │             │
│ 。 │ 分词  ：  ；  │  换行 ↵     │
│ ？ │               │             │
│ ！ │               │  ◀          │
│    │               │  ▶          │
└────┴───────────────┴─────────────┘
```

## 📦 安装使用

### 方式一：安装包（推荐）

下载最新的 `笔画输入法-安装包.exe`，双击安装即可。

- 安装完成后自动启动
- 系统托盘显示蓝色"笔"图标
- 按 `Ctrl + \`` 呼出/隐藏虚拟键盘
- 按 `F2` 临时开启/关闭输入法

### 方式二：源码运行

```bash
# 克隆项目
git clone https://github.com/你的用户名/stroke-input-pc.git
cd stroke-input-pc

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

首次运行会自动下载笔画数据库（Conway Stroke Data）到本地缓存。

## ⌨️ 按键映射

### 物理键盘

| 按键 | 功能 |
|------|------|
| NumPad `7` | 横（一） |
| NumPad `8` | 竖（丨） |
| NumPad `9` | 撇（丿） |
| NumPad `4` | 捺（丶） |
| NumPad `5` | 折（𠃍） |
| 主键盘 `1-5` | 选择候选字 |
| `空格` / `Enter` | 上屏首候选 |
| `Backspace` | 删除最后一笔 / 删除文字 |
| `Esc` | 清空当前输入 |
| `-` / `=` | 上一页 / 下一页 |
| `F2` | 开关输入法 |
| `Ctrl + \`` | 显示/隐藏虚拟键盘 |

### 虚拟键盘

直接点击按钮即可，布局与物理键盘对应。

## 🎨 主题切换

点击标题栏的 🎨 按钮循环切换主题：

- 🌞 浅色（默认）
- 🌙 深色
- 🔵 蓝色
- 🟢 绿色
- 🌸 粉色
- 🍊 橙色

主题设置自动保存。

## ⚙️ 自定义配置

配置文件位于 `%APPDATA%\StrokeInput\config.json`，可自定义：

- **笔画键映射**：修改 `keymap` 调整 NumPad 到笔画的对应关系
- **笔画按钮**：修改 `stroke_buttons` 调整虚拟键盘上的笔画按钮布局
- **符号**：修改 `symbols` 自定义符号面板内容
- **界面**：修改 `ui` 调整候选字数、字号等
- **主题**：修改 `themes` 自定义主题配色

## 📁 项目结构

```
stroke_input_pc/
├── main.py                 # 主入口
├── stroke_data.py          # 笔画数据加载与查询
├── stroke_input_method.py  # 输入法状态机
├── virtual_keyboard.py     # 虚拟键盘 UI
├── candidate_window.py     # 浮动候选窗口
├── keyboard_hook.py        # 全局键盘钩子
├── input_sender.py         # 文字上屏（剪贴板+Ctrl+V）
├── user_memory.py          # 用户输入记忆
├── config.py               # 配置管理
├── config.json             # 默认配置
├── requirements.txt        # Python 依赖
├── app_icon.ico            # 程序图标
├── installer.iss           # Inno Setup 安装脚本
├── 笔画输入法.spec         # PyInstaller 打包配置
├── LICENSE                 # GPL v3 许可证
├── NOTICE                  # 第三方版权声明
└── README.md               # 本文件
```

## 🛠️ 打包成 exe

```bash
# 安装 PyInstaller
pip install pyinstaller

# 打包
pyinstaller 笔画输入法.spec

# 生成安装包（需安装 Inno Setup）
# 用 Inno Setup 编译器打开 installer.iss 编译
```

打包产物在 `dist/笔画输入法/` 目录下。

## 📊 数据来源

本软件使用 **Conway Stroke Data** 作为笔画数据库：

- 项目地址：https://github.com/stroke-input/stroke-input-data
- 许可证：
  - `sequence-characters.txt` — CC-BY-4.0
  - `ranking-simplified.txt` — CC0 / 公共领域
  - `phrases-simplified.txt` — CC0 / 公共领域

## ⚖️ 许可证

本软件采用 **GNU General Public License v3.0** 协议发布。

您可以自由复制、修改和分发本软件，但衍生作品也必须以相同协议发布。

本软件按"现状"提供，不提供任何明示或暗示的担保，包括但不限于适销性、特定用途适用性和非侵权性的担保。

## 🤝 致谢

- [Conway Stroke Data](https://github.com/stroke-input/stroke-input-data) — 笔画数据库
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) — GUI 框架
- [pynput](https://github.com/moses-palmer/pynput) — 键盘输入
- [pyperclip](https://github.com/asweigart/pyperclip) — 剪贴板操作
