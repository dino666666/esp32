import network
import time
from machine import Pin

# 板载 LED（GPIO2）
LED_PIN = 2
led = Pin(LED_PIN, Pin.OUT)
led.value(0)  # 初始熄灭（根据你的板子，可能需要 0 或 1）

SSID = "3SE"
PASSWORD = "11111112"

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    # 重置接口
    wlan.active(False)
    time.sleep(0.5)
    wlan.active(True)
    time.sleep(0.5)
    wlan.disconnect()
    time.sleep(0.2)

    print("正在扫描 WiFi...")
    try:
        nets = wlan.scan()
    except Exception as e:
        print("扫描失败:", e)
        nets = []

    target_bssid = None
    for net in nets:
        net_ssid = net[0].decode() if net[0] else ""
        channel = net[2]
        rssi = net[3]
        print(f"  {net_ssid:20s} 信道:{channel:2} 信号:{rssi}dBm")
        if net_ssid == SSID and channel in range(1, 14):
            target_bssid = net[1]
            print(f"找到目标 2.4G 网络，BSSID: {target_bssid.hex()}")
            break

    if target_bssid:
        print(f"尝试使用 BSSID 连接 {SSID}...")
        wlan.connect(SSID, PASSWORD, bssid=target_bssid)
    else:
        print(f"未找到 2.4G 的 {SSID}，尝试常规连接...")
        wlan.connect(SSID, PASSWORD)

    timeout = 20
    while timeout > 0:
        if wlan.isconnected():
            print(f"\nWiFi 连接成功！IP: {wlan.ifconfig()[0]}")
            return True
        time.sleep(1)
        print(".", end="")
        timeout -= 1
    print("\nWiFi 连接失败")
    return False

if connect_wifi():
    print("网络就绪，即将启动 main.py")
    # 连接成功：LED 闪烁 3 次
    for _ in range(3):
        led.value(1)
        time.sleep(0.2)
        led.value(0)
        time.sleep(0.2)
    # 注意：不在这里导入 main，让 MicroPython 自动执行 main.py
else:
    print("请检查 WiFi 配置或路由器 2.4G 是否开启")
    # 连接失败：LED 慢闪报警
    while True:
        led.value(1)
        time.sleep(0.5)
        led.value(0)
        time.sleep(0.5)

