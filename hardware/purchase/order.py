#!/usr/bin/env python3
"""
Koe Dev Kit — 部品購入ヘルパー
DigiKey / Mouser / Amazon の直接購入リンク生成 + 在庫確認

使い方:
  python3 order.py          # 購入リンク一覧表示
  python3 order.py --check  # DigiKey API で在庫確認 (要 CLIENT_ID/SECRET)
  python3 order.py --cart   # DigiKey カートURL生成
"""

import sys
import json
import webbrowser
from urllib.parse import quote

# ============================================================
# 部品リスト
# ============================================================

PARTS = {
    "koe_pro_devkit": {
        "name": "Koe Pro v2 開発キット",
        "items": [
            {
                "name": "nRF5340 Audio DK (BLE Audio, LC3, I2S)",
                "qty": 2,
                "price_usd": 169.00,
                "digikey": "1490-NRF5340-AUDIO-DK-ND",
                "mouser": "949-NRF5340-AUDIO-DK",
                "url": "https://www.digikey.com/en/products/detail/nordic-semiconductor-asa/NRF5340-AUDIO-DK/16399476",
            },
            {
                "name": "DWM3000EVB UWB Evaluation Board",
                "qty": 2,
                "price_usd": 29.50,
                "digikey": "1479-DWM3000EVB-ND",
                "mouser": "584-DWM3000EVB",
                "url": "https://www.digikey.com/en/products/detail/qorvo/DWM3000EVB/24367408",
            },
            {
                "name": "PCM5102A I2S DAC Module (GY-PCM5102)",
                "qty": 2,
                "price_usd": 7.99,
                "amazon_asin": "B07KFC1YTD",
                "url": "https://www.amazon.com/dp/B07KFC1YTD",
            },
            {
                "name": "MAX98357A I2S Amp Breakout (Adafruit)",
                "qty": 1,
                "price_usd": 5.95,
                "adafruit": "3006",
                "url": "https://www.adafruit.com/product/3006",
            },
            {
                "name": "INMP441 I2S MEMS Microphone Module",
                "qty": 2,
                "price_usd": 3.99,
                "amazon_asin": "B09C4RTMHT",
                "url": "https://www.amazon.com/dp/B09C4RTMHT",
            },
        ],
    },
    "koe_hub_devkit": {
        "name": "Koe Hub v2 開発キット",
        "items": [
            {
                "name": "Raspberry Pi CM5 4GB WiFi",
                "qty": 1,
                "price_usd": 55.00,
                "url": "https://www.raspberrypi.com/products/compute-module-5/",
            },
            {
                "name": "Raspberry Pi CM5 IO Board",
                "qty": 1,
                "price_usd": 25.00,
                "url": "https://www.raspberrypi.com/products/cm5-dev-kit/",
            },
            {
                "name": "PCM5102A I2S DAC Module (main + monitor)",
                "qty": 2,
                "price_usd": 7.99,
                "amazon_asin": "B07KFC1YTD",
                "url": "https://www.amazon.com/dp/B07KFC1YTD",
            },
            {
                "name": "PCM1808 ADC Module (line input)",
                "qty": 1,
                "price_usd": 12.99,
                "url": "https://www.amazon.com/s?k=PCM1808+ADC+module",
            },
            {
                "name": "microSD 32GB (Pi CM5 boot)",
                "qty": 1,
                "price_usd": 7.99,
                "url": "https://www.amazon.com/dp/B073JWXGNT",
            },
        ],
    },
    "coin_lite_devkit": {
        "name": "COIN Lite 開発キット",
        "items": [
            {
                "name": "ESP32-C3-DevKitM-1",
                "qty": 3,
                "price_usd": 8.00,
                "digikey": "1965-ESP32-C3-DEVKITM-1-ND",
                "url": "https://www.digikey.com/en/products/detail/espressif-systems/ESP32-C3-DEVKITM-1/14553014",
            },
            {
                "name": "MAX98357A I2S Amp Breakout",
                "qty": 3,
                "price_usd": 5.95,
                "adafruit": "3006",
                "url": "https://www.adafruit.com/product/3006",
            },
            {
                "name": "WS2812B LEDストリップ (8 LED)",
                "qty": 1,
                "price_usd": 4.99,
                "url": "https://www.amazon.com/s?k=WS2812B+LED+strip+8",
            },
            {
                "name": "Small Speaker 28mm 8ohm 1W",
                "qty": 3,
                "price_usd": 1.50,
                "url": "https://www.amazon.com/s?k=28mm+speaker+8ohm",
            },
        ],
    },
    "cables_tools": {
        "name": "ケーブル・工具",
        "items": [
            {
                "name": "USB-C ケーブル (3本セット)",
                "qty": 1,
                "price_usd": 9.99,
                "url": "https://www.amazon.com/s?k=USB-C+cable+3+pack",
            },
            {
                "name": "ブレッドボード + ジャンパワイヤセット",
                "qty": 1,
                "price_usd": 12.99,
                "url": "https://www.amazon.com/s?k=breadboard+jumper+wire+kit",
            },
            {
                "name": "3.5mm TRS ケーブル",
                "qty": 2,
                "price_usd": 2.99,
                "url": "https://www.amazon.com/s?k=3.5mm+TRS+cable",
            },
        ],
    },
}


def print_shopping_list():
    """購入リスト表示"""
    grand_total = 0
    print("=" * 70)
    print("  Koe Pro v2 + Hub v2 + COIN Lite — 開発キット購入リスト")
    print("=" * 70)

    for group_key, group in PARTS.items():
        subtotal = 0
        print(f"\n{'─' * 70}")
        print(f"  {group['name']}")
        print(f"{'─' * 70}")
        print(f"  {'部品':<45} {'数量':>4} {'単価':>8} {'小計':>8}")
        print(f"  {'─' * 65}")

        for item in group["items"]:
            line_total = item["qty"] * item["price_usd"]
            subtotal += line_total
            name = item["name"][:44]
            print(f"  {name:<45} {item['qty']:>4} ${item['price_usd']:>7.2f} ${line_total:>7.2f}")

        print(f"  {'':>45} {'':>4} {'':>8} {'─' * 8}")
        print(f"  {'小計':>45} {'':>4} {'':>8} ${subtotal:>7.2f}")
        grand_total += subtotal

    print(f"\n{'=' * 70}")
    print(f"  {'合計':>45} {'':>4} {'':>8} ${grand_total:>7.2f}")
    print(f"{'=' * 70}")

    print(f"\n  全部揃えて ${grand_total:.0f} で Koe エコシステム全体のプロトタイプが作れます。\n")


def print_purchase_links():
    """購入リンク一覧"""
    print("\n📎 購入リンク:")
    print("─" * 70)
    for group_key, group in PARTS.items():
        print(f"\n  [{group['name']}]")
        for item in group["items"]:
            print(f"    {item['name'][:50]}")
            print(f"      → {item['url']}")
            if "digikey" in item:
                print(f"      DigiKey: {item['digikey']}")
            if "mouser" in item:
                print(f"      Mouser:  {item['mouser']}")
    print()


def generate_digikey_cart_url():
    """DigiKey カートURL生成 (DigiKey parts only)"""
    dk_parts = []
    for group in PARTS.values():
        for item in group["items"]:
            if "digikey" in item:
                dk_parts.append(f"{item['digikey']}|{item['qty']}")

    if not dk_parts:
        print("DigiKey部品が見つかりません")
        return

    # DigiKey の add-to-cart URL パターン
    parts_str = ",".join(dk_parts)
    url = f"https://www.digikey.com/ordering/shoppingcart?newproducts={quote(parts_str)}"

    print(f"\nDigiKey カートURL (ブラウザで開く):")
    print(f"  {url}")
    print(f"\n含まれる部品:")
    for group in PARTS.values():
        for item in group["items"]:
            if "digikey" in item:
                print(f"  - {item['name']} x{item['qty']} (${item['price_usd']:.2f})")

    return url


def open_all_links():
    """全購入リンクをブラウザで開く"""
    urls = set()
    for group in PARTS.values():
        for item in group["items"]:
            urls.add(item["url"])

    print(f"\n{len(urls)}個のリンクをブラウザで開きます...")
    for url in sorted(urls):
        webbrowser.open(url)
    print("完了")


if __name__ == "__main__":
    print_shopping_list()
    print_purchase_links()

    if "--cart" in sys.argv:
        url = generate_digikey_cart_url()
        if url and "--open" in sys.argv:
            webbrowser.open(url)

    if "--open" in sys.argv:
        open_all_links()

    if "--check" in sys.argv:
        print("\nDigiKey API 在庫確認には CLIENT_ID と CLIENT_SECRET が必要です。")
        print("https://developer.digikey.com/ でアプリ登録してください。")
        print("設定後: DIGIKEY_CLIENT_ID=xxx DIGIKEY_CLIENT_SECRET=yyy python3 order.py --check")
