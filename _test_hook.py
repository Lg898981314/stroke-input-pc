"""测试键盘钩子：按小键盘 7，看看输出什么"""
import time
from keyboard_hook import KeyboardHook

def on_key(evt):
    print(f"[KEY] type={evt['type']}, vk={hex(evt['vk'])}, value={evt.get('value')}")
    sys.stdout.flush()
    return False  # 先不拦截

import sys
hook = KeyboardHook(on_key)
hook.start()
print("钩子已启动，8 秒后自动停止。请现在按一下小键盘 7 试试...")
sys.stdout.flush()
time.sleep(8)
hook.stop()
print("已停止")
