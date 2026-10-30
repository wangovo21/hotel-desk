r"""KL9007U 读写器 → 酒店录入系统 桥接进程。

硬件事实（来自 C:\Users\17857\Desktop\KL9007U开发包下载 的 C# 演示源码）：
  · 设备走 USB 虚拟串口（装完「USB 驱动」目录里的驱动后出现 COM 口）
  · 厂商 SDK 是 32 位原生 DLL（Basic.dll，导出 AutoOpenComPort / Inventory_G2 等），
    因此本脚本必须跑在 32 位 Python 上 —— run_bridge.bat 用的是旁边的 py32/，
    那是 python.org 官方 win32 嵌入式版，不用改你系统的 Python。

工作方式：
  1. 启动时从酒店系统拉「在住客人」列表，你选一张入住单作为刷卡目标；
  2. 之后持续盘存（Inventory_G2）：读写器感应到标签 → 拿到 EPC 卡号；
  3. 新卡号自动 POST 给酒店系统发卡（默认），--mode revoke 则改为退卡；
  4. 同一张卡在去抖窗口内只算一次，避免 UHF 连续读报刷出一堆卡。

不用桥接也能刷卡：系统网页里的发卡输入框本身支持键盘仿真的读写器，
或者直接手输卡号按回车 —— 三条路最终都走同一个发卡接口。
"""
from __future__ import annotations

import argparse
import ctypes
import json
import struct
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# SDK 签名（对照 Form1.cs 里 StaticClassReaderB.* 的调用方式）
# ---------------------------------------------------------------------------
EPC_BUF = ctypes.create_string_buffer(5000)


def load_sdk(dll_path: Path):
    if struct.calcsize("P") != 4:
        sys.exit("桥接脚本必须用 32 位 Python 运行（请用 run_bridge.bat）")
    dll = ctypes.WinDLL(str(dll_path))

    # int AutoOpenComPort(ref int Port, ref byte ComAdr, byte Baud, ref int ComIndex)
    dll.AutoOpenComPort.argtypes = [
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_byte),
        ctypes.c_byte,
        ctypes.POINTER(ctypes.c_int),
    ]
    # int OpenComPort(int Port, ref byte ComAdr, byte Baud, ref int ComIndex)
    dll.OpenComPort.argtypes = [
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_byte),
        ctypes.c_byte,
        ctypes.POINTER(ctypes.c_int),
    ]
    dll.CloseSpecComPort.argtypes = [ctypes.c_int]
    # int Inventory_G2(ref byte ComAdr, byte AdrTID, byte LenTID, byte TIDFlag,
    #                  byte[] EPC, ref int Totallen, ref int CardNum, int ComIndex)
    dll.Inventory_G2.argtypes = [
        ctypes.POINTER(ctypes.c_byte),
        ctypes.c_byte,
        ctypes.c_byte,
        ctypes.c_byte,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_int,
    ]
    return dll


def open_reader(dll, com_port: int | None) -> int:
    """打开读写器，返回句柄（<0 表示失败）。"""
    com_adr = ctypes.c_byte(0xFF)  # FF = 广播地址
    index = ctypes.c_int(-1)

    if com_port is None:
        port = ctypes.c_int(0)
        # 波特率代码 5 = 115200（demo 默认档）
        ret = dll.AutoOpenComPort(ctypes.byref(port), ctypes.byref(com_adr), 5, ctypes.byref(index))
    else:
        ret = dll.OpenComPort(
            com_port, ctypes.byref(com_adr), 5, ctypes.byref(index)
        )

    if ret != 0:
        hints = {
            0x30: "串口通讯错误：设备没接好，或被厂商演示程序占着",
            0x35: "串口已被其他程序打开",
            -1: "没有找到读写器：确认已插 USB、装好「USB 驱动」目录里的驱动",
        }.get(ret & 0xFF if ret > 0 else ret, f"错误码 {ret:#x}")
        sys.exit(f"打开读写器失败：{hints}")
    return index.value


def inventory_once(dll, handle: int, com_adr: ctypes.c_byte) -> list[str]:
    """盘存一次，返回本次读到的 EPC 卡号（大写十六进制串）。"""
    total = ctypes.c_int(0)
    card_num = ctypes.c_int(0)
    ret = dll.Inventory_G2(
        ctypes.byref(com_adr),
        0, 0, 0,  # 不读 TID
        EPC_BUF,
        ctypes.byref(total),
        ctypes.byref(card_num),
        handle,
    )
    # 0 成功；1/2/3 询查结束；0xFB 无标签 —— 都算"这一轮完了"
    if ret not in (0x00, 0x01, 0x02, 0x03, 0x04, 0xFB):
        return []
    if card_num.value == 0 or total.value == 0:
        return []

    buf = EPC_BUF.raw[: total.value]
    epcs: list[str] = []
    pos = 0
    for _ in range(card_num.value):
        epc_len = buf[pos]
        epc = buf[pos + 1 : pos + 1 + epc_len].hex().upper()
        pos += 1 + epc_len
        if epc:
            epcs.append(epc)
    return epcs


# ---------------------------------------------------------------------------
# 酒店系统 HTTP
# ---------------------------------------------------------------------------
def call_api(base: str, method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except Exception:
            return e.code, {}
    except urllib.error.URLError as e:
        raise SystemExit(f"连不上酒店系统（{base}）：{e.reason} —— 先把系统跑起来再启动桥接")


def pick_target_stay(base: str, stay_arg: str | None) -> dict:
    status, stays = call_api(base, "GET", "/api/stays/in-house")
    if status != 200 or not stays:
        sys.exit("当前没有在住客人，先办一单入住再启动桥接")

    if stay_arg:
        key = stay_arg.strip().upper()
        for s in stays:
            if key in (str(s["id"]), s["stay_no"].upper(), s["room_no"]):
                print(f"刷卡目标：{s['guest_name']} · {s['room_no']} · {s['stay_no']}")
                return s
        sys.exit(f"在住列表里找不到 {stay_arg}（可用：房号 / 单号 / 单据 id）")

    print("在住客人（输入房号或序号选择刷卡目标）：")
    for i, s in enumerate(stays, 1):
        print(f"  {i}. 房 {s['room_no']}  {s['guest_name']}  {s['stay_no']}  离店 {s['expected_checkout_date']}")
    while True:
        try:
            choice = input("选择> ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit("\n已取消")
        for i, s in enumerate(stays, 1):
            if choice in (str(i), s["room_no"], s["stay_no"].upper()):
                print(f"刷卡目标：{s['guest_name']} · {s['room_no']} · {s['stay_no']}")
                return s
        print("没匹配到，请重输")


def swipe(base: str, stay: dict, card_no: str, mode: str, operator: str) -> None:
    if mode == "revoke":
        _, cards = call_api(base, "GET", f"/api/stays/{stay['id']}/cards")
        match = [c for c in cards if c["card_no"] == card_no and c["status"] == "ACTIVE"]
        if not match:
            print(f"  ✗ 卡 {card_no} 不是这张单的在用卡，无法退")
            return
        status, out = call_api(
            base, "POST", f"/api/cards/{match[0]['id']}/revoke", {"operator": operator}
        )
        if status == 200:
            print(f"  ✓ 已退卡 {card_no}")
        else:
            print(f"  ✗ 退卡失败：{out.get('error', {}).get('message', status)}")
        return

    status, out = call_api(
        base,
        "POST",
        f"/api/stays/{stay['id']}/cards",
        {"card_no": card_no, "operator": operator, "remark": "读写器发卡"},
    )
    if status == 200:
        issued = next((c for c in out if c["card_no"] == card_no and c["status"] == "ACTIVE"), None)
        print(f"  ✓ 发卡成功 {card_no} → {stay['guest_name']} · 房 {stay['room_no']}")
        _ = issued
    else:
        err = out.get("error", {})
        if err.get("code") == "CARD_IN_USE":
            print(f"  · 卡 {card_no} 已绑在住单，不重复发（{err.get('message')}）")
        else:
            print(f"  ✗ 发卡失败：{err.get('message', status)}")


# ---------------------------------------------------------------------------
def main() -> int:
    sdk_default = Path(r"C:/Users/17857/Desktop/KL9007U开发包下载/Csharp chV2.1/UHFReader18demomain/bin/Debug/Basic.dll")

    parser = argparse.ArgumentParser(description="KL9007U 读写器桥接（刷卡自动发卡/退卡）")
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="酒店系统地址")
    parser.add_argument("--dll", default=str(sdk_default), help="Basic.dll 路径")
    parser.add_argument("--stay", help="刷卡目标：房号 / 入住单号 / 单据 id（不传则启动时选择）")
    parser.add_argument("--com", type=int, default=None, help="指定 COM 口号（默认自动搜索）")
    parser.add_argument("--mode", choices=["issue", "revoke"], default="issue", help="刷卡动作：发卡(默认)/退卡")
    parser.add_argument("--operator", default="读写器", help="留痕里的操作员名")
    parser.add_argument("--interval", type=float, default=0.4, help="盘存间隔秒")
    parser.add_argument("--debounce", type=float, default=5.0, help="同一张卡的去抖秒数")
    parser.add_argument("--selftest", action="store_true", help="只做自检（加载 DLL + 探测 API），不连设备")
    args = parser.parse_args()

    dll_path = Path(args.dll)
    if not dll_path.is_file():
        sys.exit(f"找不到 SDK：{dll_path}\n（把它随开发包一起放在本机，或用 --dll 指定路径）")

    print("== KL9007U 桥接自检 ==")
    try:
        dll = load_sdk(dll_path)
        print(f"✓ 32 位 Python 加载 {dll_path.name} 成功")
    except OSError as e:
        sys.exit(f"加载 SDK 失败：{e}")

    status, health = call_api(args.api, "GET", "/api/health")
    if status != 200:
        sys.exit(f"酒店系统异常：HTTP {status}")
    print(f"✓ 酒店系统在线：{health.get('hotel_name')}（schema v{health['db']['schema_version']}）")

    if args.selftest:
        print("自检通过。真机刷卡：run_bridge.bat（或 python bridge.py --stay <房号>）")
        return 0

    stay = pick_target_stay(args.api, args.stay)
    handle = open_reader(dll, args.com)
    com_adr = ctypes.c_byte(0xFF)
    mode_label = "发卡" if args.mode == "issue" else "退卡"
    print(f"✓ 读写器已连接（句柄 {handle}），模式：刷卡{mode_label}")
    print("  把卡放到读写器上即可；Ctrl+C 退出\n")

    recent: dict[str, float] = {}
    try:
        while True:
            for epc in inventory_once(dll, handle, com_adr):
                now = time.monotonic()
                if now - recent.get(epc, -1e9) < args.debounce:
                    continue
                recent[epc] = now
                stamp = time.strftime("%H:%M:%S")
                print(f"[{stamp}] 读到卡 {epc} → {mode_label}")
                try:
                    swipe(args.api, stay, epc, args.mode, args.operator)
                except SystemExit as e:
                    print(f"  ✗ {e}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n停止桥接")
    finally:
        dll.CloseSpecComPort(handle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
