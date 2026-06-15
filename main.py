# main.py - 远程开机舵机版（带心跳监测和自动重连）
import uasyncio as a
import time
import network
from machine import Pin, PWM
from sinricpro import SinricPro
from sinricpro.devices.sinricpro_switch import SinricProSwitch

# ========== 用户配置 ==========
APP_KEY = "55a0dffb-93e4-4f88-9bc0-03be202cd8a7"
APP_SECRET = "e8aa83f1-0a2a-414d-a6e7-c3a640fcb2bb-3956c9c5-e776-4c99-b340-1de178b7e245"
DEVICE_ID = "6a2a5c58baa50bf9bf4c9836"

SERVO_PIN = 13
PRESS_DUTY = 35
RELEASE_DUTY = 25
PRESS_HOLD = 1          # 按下保持时间（秒）
COOLDOWN_SEC = 5        # 两次按压最小间隔（秒）

# 重连配置
HEARTBEAT_INTERVAL = 120   # 秒，检查连接状态的间隔
MAX_RECONNECT_ATTEMPTS = 5
# ===========================

# 初始化舵机
servo = PWM(Pin(SERVO_PIN))
servo.freq(50)
servo.duty(RELEASE_DUTY)

# LED 指示（与 boot.py 共用 GPIO2）
led = Pin(2, Pin.OUT)
led.value(0)

# 全局状态
sinricpro = None
is_connected = False
reconnect_attempts = 0

# ---------- 辅助函数 ----------
def blink_led(times=1, on_ms=200, off_ms=200):
    for _ in range(times):
        led.value(1)
        time.sleep_ms(on_ms)
        led.value(0)
        time.sleep_ms(off_ms)

# ---------- 舵机按压 ----------
async def press_power():
    global last_press_time
    now = time.time()
    if now - last_press_time < COOLDOWN_SEC:
        print(f"冷却中，忽略按压 (上次 {now - last_press_time:.0f}s 前)")
        return False
    print("--- 开始按压 ---")
    led.value(1)
    servo.duty(PRESS_DUTY)
    await a.sleep(0.2)
    await a.sleep(PRESS_HOLD)
    servo.duty(RELEASE_DUTY)
    await a.sleep(0.2)
    led.value(0)
    print("--- 按压完成 ---")
    last_press_time = now
    return True

last_press_time = 0

# ---------- SinricPro 回调 ----------
async def on_power_state(device_id: str, state: bool):
    print(f"收到设备 {device_id} 状态: {'ON' if state else 'OFF'}")
    if state:
        await press_power()
    return True

async def on_connected():
    global is_connected, reconnect_attempts
    is_connected = True
    reconnect_attempts = 0
    print("✅ SinricPro 已连接")
    blink_led(2, 100, 100)   # 快速闪烁两次

async def on_disconnected():
    global is_connected
    is_connected = False
    print("❌ SinricPro 断开连接")
    blink_led(3, 150, 150)   # 闪烁三次

# ---------- 创建/重建 SinricPro 连接 ----------
def create_sinricpro():
    global sinricpro
    if sinricpro:
        try:
            sinricpro.stop()
        except:
            pass
    sinricpro = SinricPro()
    sinricpro.on_connected(on_connected)
    sinricpro.on_disconnected(on_disconnected)
    switch = SinricProSwitch(DEVICE_ID)
    switch.on_power_state(on_power_state)
    sinricpro.add_device(switch)
    sinricpro.start(APP_KEY, APP_SECRET, enable_log=True)
    print("SinricPro 启动中...")

# ---------- WiFi 重连（如 boot.py 未做）----------
def check_wifi():
    wlan = network.WLAN(network.STA_IF)
    if wlan.isconnected():
        return True
    print("WiFi 断开，尝试重连...")
    wlan.active(False)
    time.sleep(0.5)
    wlan.active(True)
    wlan.connect("3SE", "11111112")
    timeout = 15
    while timeout > 0:
        if wlan.isconnected():
            print("WiFi 重连成功, IP:", wlan.ifconfig()[0])
            return True
        time.sleep(1)
        timeout -= 1
    print("WiFi 重连失败")
    return False

# ---------- 心跳监测任务（低频率主动检查）----------
async def heartbeat_monitor():
    global reconnect_attempts, sinricpro, is_connected
    while True:
        await a.sleep(HEARTBEAT_INTERVAL)

        # 1. 确保 WiFi 在线
        if not check_wifi():
            print("WiFi 不可用，跳过本次 SinricPro 重连")
            continue

        # 2. 如果 SinricPro 断开，则尝试重连
        if not is_connected:
            reconnect_attempts += 1
            print(f"🔄 尝试重连 SinricPro ({reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS})")
            if reconnect_attempts <= MAX_RECONNECT_ATTEMPTS:
                create_sinricpro()
            else:
                print("⚠️ 多次重连失败，等待下一周期")
                blink_led(10, 100, 100)   # 快闪报警
                reconnect_attempts = 0
        else:
            reconnect_attempts = 0

# ---------- 主函数 ----------
async def main():
    global sinricpro, is_connected
    print("系统启动，正在初始化 SinricPro...")
    create_sinricpro()
    # 启动心跳监测任务
    a.create_task(heartbeat_monitor())

    while True:
        # 关键：必须定期调用 handle() 以维持 WebSocket 心跳和接收消息
        if sinricpro and is_connected:
            try:
                sinricpro.handle()   # 根据你的 SinricPro 库，也可能是 loop()
            except Exception as e:
                print(f"handle() 错误: {e}")
                is_connected = False
        await a.sleep_ms(200)   # 200ms 轮询，足够轻量

# 运行主程序
try:
    a.run(main())
except KeyboardInterrupt:
    print("程序被用户中断")
finally:
    a.new_event_loop()
