#!/usr/bin/env python3
"""
Koe Pro v2 — PCBWay API で基板を自動発注
使い方:
  1. PCBWay パートナーAPIキーを取得: anson@pcbway.com にメール
  2. 環境変数設定:
     export PCBWAY_API_KEY="your-api-key"
  3. 実行:
     python3 order_pcb.py --quote     # 見積もりのみ
     python3 order_pcb.py --order     # 見積もり + 発注
"""

import base64
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

API_BASE = "https://api-partner.pcbway.com"
GERBER_ZIP = Path(__file__).parent.parent / "manufacturing" / "gerbers" / "koe-pro-v2-production" / "koe-pro-v2-gerbers.zip"

# ── Koe Pro v2 基板スペック ──────────────────────────────────

PCB_SPEC = {
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
    "SolderMask": "Black",
    "Silkscreen": "White",
    "SilkSides": 2,
    "Goldfingers": "No",
    "SurfaceFinish": "HASL with lead free",
    "ViaProcess": "Tenting vias",
    "FinishedCopper": "1 oz Cu",
    "RemoveProductNo": "No",
    "ImpedanceControl": "No",
    "HalogenFree": "No",
}

SHIPPING = {
    "Country": "Japan",
    "CountryCode": "JP",
    "City": "Tokyo",
}


def api_call(endpoint, data, api_key):
    """PCBWay API を呼ぶ"""
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
        print(f"API Error {e.code}: {error_body}")
        sys.exit(1)


def get_quote(api_key):
    """見積もり取得"""
    print("=" * 60)
    print("  Koe Pro v2 — PCBWay 見積もり")
    print("=" * 60)
    print(f"  基板: {PCB_SPEC['Length']}x{PCB_SPEC['Width']}mm, {PCB_SPEC['Layers']}層")
    print(f"  数量: {PCB_SPEC['Qty']}枚")
    print(f"  表面: {PCB_SPEC['SolderMask']}, {PCB_SPEC['SurfaceFinish']}")
    print(f"  配送先: {SHIPPING['City']}, {SHIPPING['Country']}")
    print()

    quote_data = {**PCB_SPEC, **SHIPPING}
    result = api_call("Pcb/PcbQuotation", quote_data, api_key)

    if result.get("Status") != "ok":
        print(f"エラー: {result.get('ErrorText', 'Unknown error')}")
        return None

    print("  製造オプション:")
    print(f"  {'納期':>12} {'価格':>10} {'タイプ'}")
    print(f"  {'─' * 40}")

    prices = result.get("priceList", [])
    for p in prices:
        days = p.get("BuildText", f"{p.get('BuildDays', '?')}日")
        price = p.get("Price", 0)
        ptype = "Express" if p.get("Express") else "Standard" if p.get("Standard") else ""
        marker = " ←" if p.get("Standard") else ""
        print(f"  {days:>12} ${price:>8.2f}  {ptype}{marker}")

    ship = result.get("Shipping", {})
    if ship:
        print(f"\n  送料: ${ship.get('ShipCost', 0):.2f} ({ship.get('ShipDays', '?')})")
        print(f"  重量: {ship.get('Weight', 0):.1f}g")

    # 最安オプションを返す
    standard = [p for p in prices if p.get("Standard")]
    best = standard[0] if standard else prices[0] if prices else None
    if best:
        total = best["Price"] + ship.get("ShipCost", 0)
        print(f"\n  合計 (Standard): ${total:.2f}")

    return best


def place_order(api_key, build_days):
    """発注"""
    if not GERBER_ZIP.exists():
        print(f"Gerber ZIP が見つかりません: {GERBER_ZIP}")
        print("先に generate_gerbers.py を実行してください")
        sys.exit(1)

    # Gerber ZIP を Base64 エンコード
    with open(GERBER_ZIP, "rb") as f:
        zip_b64 = base64.b64encode(f.read()).decode("ascii")

    print(f"\n  Gerber: {GERBER_ZIP.name} ({GERBER_ZIP.stat().st_size:,} bytes)")
    print(f"  Base64: {len(zip_b64):,} chars")

    order_data = {
        **PCB_SPEC,
        **SHIPPING,
        "BuildDays": build_days,
        "PcbFileName": "koe-pro-v2-gerbers.zip",
        "DataZipFile": zip_b64,
    }

    print("\n  発注中...")
    result = api_call("Pcb/PlaceOrder", order_data, api_key)

    if result.get("Status") != "ok":
        print(f"  エラー: {result.get('ErrorText', 'Unknown error')}")
        return

    order_no = result.get("OrderNo", "?")
    price = result.get("Price", 0)
    delivery = result.get("DeliveryDate", "?")

    print(f"\n  {'=' * 40}")
    print(f"  発注完了!")
    print(f"  注文番号: {order_no}")
    print(f"  価格: ${price:.2f}")
    print(f"  納品予定: {delivery}")
    print(f"  {'=' * 40}")
    print(f"\n  確認: https://www.pcbway.com/setinvite.aspx")

    return order_no


def check_status(api_key, order_no):
    """製造ステータス確認"""
    result = api_call("Pcb/QueryOrderProcess", {"orderNo": order_no}, api_key)
    if result.get("Status") == "ok":
        print(f"  注文 {order_no}: {json.dumps(result, indent=2, ensure_ascii=False)}")
    else:
        print(f"  エラー: {result.get('ErrorText')}")


def main():
    api_key = os.environ.get("PCBWAY_API_KEY", "")

    if not api_key:
        print("=" * 60)
        print("  PCBWay API キーが未設定です")
        print("=" * 60)
        print()
        print("  セットアップ手順:")
        print("  1. anson@pcbway.com にメール:")
        print('     件名: "API Access Request - Koe Device"')
        print("     内容: PCBWay Partner API access を申請")
        print()
        print("  2. APIキーを受け取ったら:")
        print('     export PCBWAY_API_KEY="your-api-key"')
        print("     python3 order_pcb.py --quote")
        print()
        print("  3. またはJLCPCB手動発注:")
        print(f"     Gerber: {GERBER_ZIP}")
        print("     → https://cart.jlcpcb.com/quote にアップロード")
        print()

        # APIキーなしでもスペック確認は表示
        print("  ── 基板スペック (確認用) ──")
        for k, v in PCB_SPEC.items():
            print(f"    {k}: {v}")
        return

    if "--quote" in sys.argv or "--order" in sys.argv:
        best = get_quote(api_key)
        if not best:
            return

        if "--order" in sys.argv:
            build_days = best.get("BuildDays", 7)
            print(f"\n  {build_days}日納期で発注します。")
            confirm = input("  続行? (yes/no): ").strip().lower()
            if confirm == "yes":
                place_order(api_key, build_days)
            else:
                print("  キャンセルしました")

    elif "--status" in sys.argv:
        order_no = sys.argv[sys.argv.index("--status") + 1] if len(sys.argv) > sys.argv.index("--status") + 1 else None
        if order_no:
            check_status(api_key, order_no)
        else:
            print("使い方: python3 order_pcb.py --status ORDER_NO")

    else:
        print("使い方:")
        print("  python3 order_pcb.py --quote    # 見積もり")
        print("  python3 order_pcb.py --order    # 発注")
        print("  python3 order_pcb.py --status ORDER_NO  # ステータス確認")


if __name__ == "__main__":
    main()
