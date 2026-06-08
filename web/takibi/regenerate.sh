#!/usr/bin/env bash
# 焚き火 OSSクライアントの再生成: 本番の/takibiを取得し、同一オリジン相対パスを
# 絶対API(mcp.koe.live)へ書き換えて自己完結の静的クライアントにする。
set -euo pipefail
cd "$(dirname "$0")"
API="https://mcp.koe.live"
curl -fsS "$API/takibi" -o index.html
perl -0pi -e "s/const \\\$=id=>document\.getElementById\(id\);/const API='https:\/\/mcp.koe.live';const \\\$=id=>document.getElementById(id);/" index.html
perl -0pi -e "s/fetch\('\/api/fetch(API+'\/api/g" index.html
perl -0pi -e "s/new Audio\(d\.url\)/new Audio(API+d.url)/g" index.html
perl -0pi -e "s/if\('serviceWorker' in navigator\)\{navigator\.serviceWorker\.register\('\/takibi\/sw\.js',\{scope:'\/takibi'\}\)\.catch\(\(\)=>\{\}\)\}//" index.html
perl -0pi -e 's{href="/takibi/manifest.webmanifest"}{href="https://mcp.koe.live/takibi/manifest.webmanifest"}' index.html
echo "regenerated $(pwd)/index.html ($(wc -c < index.html) bytes)"
