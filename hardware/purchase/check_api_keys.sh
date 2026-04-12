#!/bin/bash
# Koe API Key Checker — 月曜昼+夜に実行
# crontab: 13 12 30 3 * /Users/yuki/workspace/koe-device/hardware/purchase/check_api_keys.sh
# crontab: 17 20 30 3 * /Users/yuki/workspace/koe-device/hardware/purchase/check_api_keys.sh

cd /Users/yuki/workspace/koe-device

# Check for replies
RESULTS=$(gog gmail search "from:jlcpcb.com OR from:pcbway.com OR from:anson" 2>&1)
JLCPCB_REPLY=$(echo "$RESULTS" | grep -i "api" | grep -v "SENT" | head -1)
PCBWAY_REPLY=$(echo "$RESULTS" | grep -i "pcbway\|anson" | grep -v "SENT" | head -1)

MSG="[Koe API Check $(date '+%H:%M')]
"

if [ -n "$JLCPCB_REPLY" ]; then
    MSG="${MSG}JLCPCB: 返信あり! ${JLCPCB_REPLY}
"
else
    MSG="${MSG}JLCPCB: まだ返信なし
"
fi

if [ -n "$PCBWAY_REPLY" ]; then
    MSG="${MSG}PCBWay: 返信あり! ${PCBWAY_REPLY}
"
else
    MSG="${MSG}PCBWay: まだ返信なし
"
fi

# Also check order status
ORDER_STATUS=$(gog gmail search "from:jlcpcb subject:order" 2>&1 | head -3)
MSG="${MSG}
注文状況:
${ORDER_STATUS}

APIキーが届いたら claude で:
claude 'APIキーが届いた。全自動パイプラインを構築して'"

# Send to Telegram
curl -s -X POST "https://api.telegram.org/bot$(cat ~/.claude/telegram_token 2>/dev/null || echo 'TOKEN')/sendMessage" \
  -d chat_id="1136442501" \
  -d text="$MSG" > /dev/null 2>&1

# Fallback: use MCP telegram if available
echo "$MSG"
