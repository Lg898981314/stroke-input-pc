"""
调试用：启动输入法并打印每一个键盘事件的详细信息
运行后用小键盘输入，把输出截图或复制给我
"""
import sys
import time
from keyboard_hook import KeyboardHook
from stroke_data import get_data
from stroke_input_method import StrokeInputMethod, get_key_to_stroke

print("=" * 50)
print("笔画输入法 - 按键调试模式")
print("=" * 50)
print("请用小键盘按 7 试试，看看输出...")
print("按 Ctrl+C 退出")
print()

# 加载数据
print("[加载] 加载笔画数据...")
get_data()
print("[加载] 完成")
print()

keymap = get_key_to_stroke()
print(f"[配置] 笔画映射: {keymap}")
print()

method = StrokeInputMethod(
    on_candidates_updated=lambda state: print(f"  [候选] {state.current_page()[:5]}"),
    on_commit=lambda text: print(f"  [上屏] {text}"),
    on_status_change=lambda enabled: print(f"  [状态] {'启用' if enabled else '关闭'}"),
)
method.enable(True)
print("[状态] 输入法已启用")
print()

count = [0]

def on_key(evt):
    count[0] += 1
    vk_hex = hex(evt.get('vk', 0))
    etype = evt['type']
    val = evt.get('value')
    
    # 先判断要不要拦截
    block = False
    if etype == "numpad_digit":
        value_str = str(val)
        if value_str in keymap:
            method.add_stroke(value_str)
            block = True
    
    print(f"[{count[0]:03d}] vk={vk_hex:>6}  type={etype:15s}  value={str(val):>5}  block={'YES' if block else 'no'}")
    sys.stdout.flush()
    return block

hook = KeyboardHook(on_key)
hook.start()
print("[钩子] 已启动，等待按键...\n")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n[退出] 正在停止...")
    hook.stop()
    print("[退出] 完成")
