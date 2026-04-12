#!/bin/bash
# Koe Seed -- 全自動化
# 人間がやること: ハードウェアを物理的に触るだけ

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "Koe Seed 全自動化実行"
echo ""

# 1. デモ動画生成
echo "[1/4] デモ動画生成..."
bash scripts/generate-demo.sh
echo ""

# 2. SNS投稿（ブラウザを開く）
echo "[2/4] SNS投稿..."
bash scripts/post-sns.sh "Koe Seed -- 28mmのワイヤレスオーディオレシーバー。電源入れるだけで1km先の音楽が届く。WiFiなし、アプリなし、設定なし。先着100名 8,800円。 https://koe.live"
echo ""

# 3. サイト+決済テスト
echo "[3/4] E2Eテスト..."
if [ -f tests/test_api.sh ]; then
    bash tests/test_api.sh 2>&1 | tail -5
else
    echo "  tests/test_api.sh が見つかりません -- スキップ"
fi
echo ""

# 4. 監視ループ起動
echo "[4/4] 監視ループ..."
if [ -f run.sh ]; then
    echo "  run.sh が見つかりました"
    echo "  注文が入ったらメール+Telegramで通知します"
    echo "  起動: nohup bash run.sh > /tmp/koe-loop.log 2>&1 &"
else
    echo "  run.sh が見つかりません -- スキップ"
fi

echo ""
echo "========================================"
echo "  自動化完了"
echo "========================================"
echo ""
echo "  人間がやること（これだけ）:"
echo "  ─────────────────────────"
echo "  1. DigiKeyでDK購入（1回だけ）"
echo "  2. 届いたDKをUSBで繋いでflash"
echo "  3. 箱に入れて発送"
echo "  ─────────────────────────"
echo "  それ以外は全部自動。"
