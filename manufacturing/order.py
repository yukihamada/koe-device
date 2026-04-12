#!/usr/bin/env python3
"""
Koe Device — ワンコマンド発注スクリプト
========================================
PCBWay API で見積もり → 確認 → 発注まで自動化。
PCB + SMT + 3Dプリント + Box Build を一括発注。

使い方:
  # 見積もりだけ（安全）
  python3 manufacturing/order.py --quote

  # 見積もり → 確認 → 発注
  python3 manufacturing/order.py --order

  # ステータス確認
  python3 manufacturing/order.py --status ORDER_NO

環境変数:
  PCBWAY_API_KEY  — PCBWay Partner APIキー
                    未設定の場合はブラウザで手動発注URLを開く

セットアップ（初回のみ）:
  1. sales@pcbway.com に API access 申請
  2. export PCBWAY_API_KEY="your-key"
"""

import base64
import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parent.parent
MFG = ROOT / "manufacturing"

# ════════════════════════════════════════════════════════════════
# 製品定義 — ここを変えるだけで別製品も発注可能
# ════════════════════════════════════════════════════════════════

PRODUCTS = {
    "coin-lite-v2": {
        "name": "Koe COIN Lite v2 (nRF5340 Auracast)",
        "gerber_zip": MFG / "gerbers" / "koe-coin-lite-v2" / "koe-coin-lite-v2-gerbers.zip",
        "bom_csv": MFG / "turnkey" / "coin-lite" / "BOM.csv",
        "cpl_csv": MFG / "turnkey" / "coin-lite" / "CPL.csv",
        "enclosure_stl": ROOT / "hardware" / "cases" / "coin-lite-case.stl",
        "pcb": {
            "BoardType": "Single PCB",
            "DesignInPanel": 1,
            "Length": 28.0,
            "Width": 28.0,
            "Qty": 10,
            "Layers": 2,
            "Material": "FR-4",
            "FR4Tg": "TG150",
            "Thickness": 1.0,
            "MinTrackSpacing": "5/5mil",
            "MinHoleSize": 0.3,
            "SolderMask": "Green",
            "Silkscreen": "White",
            "SilkSides": 1,
            "Goldfingers": "No",
            "SurfaceFinish": "ENIG",
            "ViaProcess": "Tenting vias",
            "FinishedCopper": "1 oz Cu",
            "RemoveProductNo": "No",
            "ImpedanceControl": "No",
            "HalogenFree": "No",
        },
        "assembly": {
            "type": "Turnkey",
            "side": "Top",
            "unique_parts": 21,
            "smd_parts": 21,
            "bga_qfp": 2,
            "through_hole": 0,
            "box_build": True,
            "firmware_loading": True,
            "special_notes": (
                "BOX BUILD ASSEMBLY - FULLY ASSEMBLED UNITS REQUIRED\n"
                "SoC: Nordic nRF5340 + nRF21540 (BLE 5.4 Auracast receiver)\n"
                "Per-unit: PCB+SMT, plug JST battery+speaker, 3D print case (SLA Black), "
                "assemble into case, flash FW via SWD (nrfjprog), test LED+BLE+audio, "
                "package in anti-static bag.\n"
                "CRITICAL: nRF5340 QFN-94 7x7mm 0.4mm pitch — needs X-ray/AOI."
            ),
        },
        "enclosure_3d": {
            "material": "SLA 8001 Resin",
            "color": "Black",
            "qty": 10,
            "est_cost_each": 2.20,
        },
        "manual_parts": [
            {"name": "LiPo 301020 300mAh JST-PH", "qty": 12, "est_each": 2.00},
            {"name": "Speaker 1510 8ohm JST-PH", "qty": 12, "est_each": 1.00},
        ],
    },
    "pro-v2": {
        "name": "Koe Pro v2 (nRF5340 + DW3000 UWB)",
        "gerber_zip": MFG / "gerbers" / "koe-pro-v2-production" / "koe-pro-v2-gerbers.zip",
        "bom_csv": MFG / "turnkey" / "pro-v2" / "BOM.csv" if (MFG / "turnkey" / "pro-v2" / "BOM.csv").exists() else None,
        "cpl_csv": MFG / "turnkey" / "pro-v2" / "CPL.csv" if (MFG / "turnkey" / "pro-v2" / "CPL.csv").exists() else None,
        "enclosure_stl": ROOT / "hardware" / "cases" / "pro-v2-case.stl",
        "pcb": {
            "BoardType": "Single PCB",
            "DesignInPanel": 1,
            "Length": 45.0,
            "Width": 30.0,
            "Qty": 5,
            "Layers": 4,
            "Material": "FR-4",
            "FR4Tg": "TG150",
            "Thickness": 1.6,
            "MinTrackSpacing": "5/5mil",
            "MinHoleSize": 0.3,
            "SolderMask": "Green",
            "Silkscreen": "White",
            "SilkSides": 2,
            "Goldfingers": "No",
            "SurfaceFinish": "ENIG",
            "ViaProcess": "Tenting vias",
            "FinishedCopper": "1 oz Cu",
            "RemoveProductNo": "No",
            "ImpedanceControl": "No",
            "HalogenFree": "No",
        },
        "assembly": {
            "type": "Turnkey",
            "side": "Top",
            "unique_parts": 33,
            "smd_parts": 33,
            "bga_qfp": 3,
            "through_hole": 0,
            "box_build": True,
            "firmware_loading": True,
            "special_notes": "BOX BUILD. nRF5340+DW3000+nPM1300. Flash via SWD.",
        },
        "enclosure_3d": {
            "material": "SLA 8001 Resin",
            "color": "Black",
            "qty": 5,
            "est_cost_each": 3.00,
        },
        "manual_parts": [
            {"name": "LiPo 802535 800mAh JST-PH", "qty": 7, "est_each": 3.00},
            {"name": "Speaker 20mm 8ohm JST-PH", "qty": 7, "est_each": 1.50},
        ],
    },
}

API_BASE = "https://api-partner.pcbway.com"
SHIPPING = {"Country": "Japan", "CountryCode": "JP", "City": "Tokyo"}


# ════════════════════════════════════════════════════════════════
# API helpers
# ════════════════════════════════════════════════════════════════

def api_call(endpoint, data, api_key):
    url = f"{API_BASE}/api/{endpoint}"
    body = json.dumps(data).encode("utf-8")
    req = Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("api-key", api_key)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        print(f"  API Error {e.code}: {error_body}")
        return None


def validate_product(product):
    """発注前に全ファイルの存在と整合性をチェック"""
    errors = []
    p = PRODUCTS[product]

    # ファイル存在チェック
    for key in ["gerber_zip", "enclosure_stl"]:
        path = p.get(key)
        if path and not path.exists():
            errors.append(f"  MISSING: {key} → {path}")

    for key in ["bom_csv", "cpl_csv"]:
        path = p.get(key)
        if path and not path.exists():
            errors.append(f"  MISSING: {key} → {path}")

    # Gerber ZIP中身チェック
    gerber = p["gerber_zip"]
    if gerber.exists():
        import zipfile
        with zipfile.ZipFile(gerber) as z:
            names = z.namelist()
            required = ["F_Cu", "B_Cu", "F_Mask", "Edge_Cuts", ".drl"]
            for req in required:
                if not any(req in n for n in names):
                    errors.append(f"  Gerber ZIP missing: {req}")

    # STL検証
    stl = p["enclosure_stl"]
    if stl.exists():
        import struct
        with open(stl, "rb") as f:
            f.read(80)
            n = struct.unpack("<I", f.read(4))[0]
            expected = 80 + 4 + n * 50
            actual = stl.stat().st_size
            if expected != actual:
                errors.append(f"  STL corrupt: expected {expected}B, got {actual}B")

    return errors


def estimate_cost(product):
    """コスト概算"""
    p = PRODUCTS[product]
    pcb_qty = p["pcb"]["Qty"]
    asm = p["assembly"]
    enc = p["enclosure_3d"]
    manual = p["manual_parts"]

    pcb_cost = pcb_qty * 2.0  # ~$2/board
    smt_cost = 30 + pcb_qty * 5  # setup + per-board
    parts_cost = pcb_qty * 8  # avg $8/board components
    enc_cost = enc["qty"] * enc["est_cost_each"]
    manual_cost = sum(m["qty"] * m["est_each"] for m in manual)
    box_build = pcb_qty * 3.5
    fw_flash = pcb_qty * 2.5
    shipping = 20

    total = pcb_cost + smt_cost + parts_cost + enc_cost + manual_cost + box_build + fw_flash + shipping
    return {
        "pcb": pcb_cost, "smt": smt_cost, "parts": parts_cost,
        "enclosure": enc_cost, "manual": manual_cost,
        "box_build": box_build, "fw_flash": fw_flash,
        "shipping": shipping, "total": total,
        "per_unit": total / pcb_qty,
    }


# ════════════════════════════════════════════════════════════════
# Main commands
# ════════════════════════════════════════════════════════════════

def cmd_quote(product, api_key=None):
    p = PRODUCTS[product]
    print(f"{'=' * 60}")
    print(f"  {p['name']}")
    print(f"  PCB: {p['pcb']['Length']}x{p['pcb']['Width']}mm, {p['pcb']['Layers']}層, x{p['pcb']['Qty']}")
    print(f"  Assembly: {p['assembly']['type']}, {p['assembly']['unique_parts']}部品")
    print(f"{'=' * 60}")

    # バリデーション
    errors = validate_product(product)
    if errors:
        print("\n  VALIDATION ERRORS:")
        for e in errors:
            print(f"    {e}")
        return None

    print("\n  Validation: ALL OK")

    # コスト概算
    cost = estimate_cost(product)
    print(f"\n  コスト概算:")
    print(f"    PCB製造:      ${cost['pcb']:.0f}")
    print(f"    SMT実装:      ${cost['smt']:.0f}")
    print(f"    部品代:       ${cost['parts']:.0f}")
    print(f"    筐体3D:       ${cost['enclosure']:.0f}")
    print(f"    手配部品:     ${cost['manual']:.0f}")
    print(f"    Box Build:    ${cost['box_build']:.0f}")
    print(f"    FW書込:       ${cost['fw_flash']:.0f}")
    print(f"    送料(DHL):    ${cost['shipping']:.0f}")
    print(f"    {'─' * 25}")
    print(f"    合計:         ${cost['total']:.0f}")
    print(f"    1台あたり:    ${cost['per_unit']:.0f}")

    # API見積もり
    if api_key:
        print(f"\n  PCBWay API 見積もり中...")
        quote_data = {**p["pcb"], **SHIPPING}
        result = api_call("Pcb/PcbQuotation", quote_data, api_key)
        if result and result.get("Status") == "ok":
            for price in result.get("priceList", [])[:3]:
                days = price.get("BuildText", "?")
                amt = price.get("Price", 0)
                print(f"    {days}: ${amt:.2f}")
        return result
    else:
        print(f"\n  (API未設定 — 概算のみ)")
        return cost


def cmd_order(product, api_key):
    p = PRODUCTS[product]
    quote = cmd_quote(product, api_key)
    if not quote:
        return

    print(f"\n  発注しますか？ (yes/no): ", end="")
    if input().strip().lower() != "yes":
        print("  キャンセル")
        return

    gerber = p["gerber_zip"]
    with open(gerber, "rb") as f:
        zip_b64 = base64.b64encode(f.read()).decode("ascii")

    order_data = {
        **p["pcb"], **SHIPPING,
        "PcbFileName": gerber.name,
        "DataZipFile": zip_b64,
    }

    print(f"\n  発注中...")
    result = api_call("Pcb/PlaceOrder", order_data, api_key)
    if result and result.get("Status") == "ok":
        order_no = result.get("OrderNo", "?")
        print(f"\n  {'=' * 40}")
        print(f"  発注完了! 注文番号: {order_no}")
        print(f"  {'=' * 40}")
        print(f"\n  次のステップ:")
        print(f"  1. PCBWayからメールが届く")
        print(f"  2. BOM/CPL/STL/FWをメール添付で返信")
        print(f"  3. Box Buildの詳細を確認")
        print(f"  4. 支払い → 製造開始")
    else:
        print(f"  発注失敗")


def cmd_browser(product):
    """APIキーなしでもブラウザで発注画面を開く"""
    p = PRODUCTS[product]

    # バリデーション
    errors = validate_product(product)
    if errors:
        print("  VALIDATION ERRORS:")
        for e in errors:
            print(f"    {e}")
        return

    cost = estimate_cost(product)
    print(f"  {p['name']}")
    print(f"  概算: ${cost['total']:.0f} (${cost['per_unit']:.0f}/台)")
    print(f"\n  ブラウザで以下を開きます:")
    print(f"  1. PCBWay 発注フォーム")
    print(f"  2. 添付ファイルのフォルダ")

    # ZIPのパス
    zip_path = MFG / "turnkey" / "coin-lite-v2-complete.zip"
    turnkey_dir = MFG / "turnkey" / "coin-lite"

    print(f"\n  発注ZIP: {zip_path}")
    print(f"  フォーム入力値は ORDER-NOW.md を参照")
    print(f"\n  開きますか？ (yes/no): ", end="")
    if input().strip().lower() != "yes":
        print("  キャンセル")
        return

    webbrowser.open("https://www.pcbway.com/QuickOrderOnline.aspx")
    subprocess.run(["open", str(turnkey_dir)])
    print(f"\n  PCBWayフォームとファイルフォルダを開きました。")
    print(f"  ORDER-NOW.md の手順に従ってフォーム入力してください。")


def cmd_status(order_no, api_key):
    result = api_call("Pcb/QueryOrderProcess", {"orderNo": order_no}, api_key)
    if result and result.get("Status") == "ok":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"  エラー: {result}")


def main():
    api_key = os.environ.get("PCBWAY_API_KEY", "")
    product = "coin-lite-v2"  # デフォルト

    # 引数パース
    args = sys.argv[1:]
    for a in args:
        if a in PRODUCTS:
            product = a

    if "--quote" in args:
        cmd_quote(product, api_key or None)
    elif "--order" in args:
        if not api_key:
            print("  PCBWAY_API_KEY が未設定です。")
            print("  ブラウザ発注に切り替えます。")
            cmd_browser(product)
        else:
            cmd_order(product, api_key)
    elif "--browser" in args:
        cmd_browser(product)
    elif "--status" in args:
        order_no = args[args.index("--status") + 1] if len(args) > args.index("--status") + 1 else None
        if order_no and api_key:
            cmd_status(order_no, api_key)
        else:
            print("  使い方: python3 order.py --status ORDER_NO")
            print("  PCBWAY_API_KEY が必要です")
    else:
        print("=" * 60)
        print("  Koe Device — ワンコマンド発注")
        print("=" * 60)
        print()
        print("  使い方:")
        print("    python3 manufacturing/order.py --quote           # 見積もり")
        print("    python3 manufacturing/order.py --order           # 発注")
        print("    python3 manufacturing/order.py --browser         # ブラウザで開く")
        print("    python3 manufacturing/order.py --status ORDER_NO # ステータス確認")
        print()
        print("  製品:")
        for k, v in PRODUCTS.items():
            print(f"    {k:20s} — {v['name']}")
        print()
        print("  環境変数:")
        print(f"    PCBWAY_API_KEY = {'設定済み' if api_key else '未設定（ブラウザ発注のみ）'}")
        print()

        # APIキーなくてもバリデーション+概算は出す
        for prod in PRODUCTS:
            print(f"\n  ── {PRODUCTS[prod]['name']} ──")
            errors = validate_product(prod)
            if errors:
                for e in errors:
                    print(f"    {e}")
            else:
                cost = estimate_cost(prod)
                print(f"    Validation: OK")
                print(f"    概算: ${cost['total']:.0f} ({PRODUCTS[prod]['pcb']['Qty']}台, ${cost['per_unit']:.0f}/台)")


if __name__ == "__main__":
    main()
