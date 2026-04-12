#!/bin/bash
# Generate a product demo video from existing images
# No physical device needed -- uses AI-generated product shots
# Ken Burns (zoom+pan) effect with crossfades

cd "$(dirname "$0")/.."
OUT="docs/demo-video.mp4"

echo "=== Koe Seed デモ動画生成 ==="

IMG1="docs/images/B1-palm-dark.png"
IMG2="docs/images/seed-wristband.jpg"
IMG3="docs/images/seed-festival.jpg"
IMG4="docs/images/seed-hero.jpg"
IMG5="docs/images/C3-festival-aerial.png"
IMG6="docs/images/seed-lineup.jpg"

# Verify images exist
MISSING=0
for img in "$IMG1" "$IMG2" "$IMG3" "$IMG4" "$IMG5" "$IMG6"; do
    if [ ! -f "$img" ]; then
        echo "  WARNING: $img not found"
        MISSING=$((MISSING + 1))
    fi
done
if [ "$MISSING" -gt 3 ]; then
    echo "Error: Not enough images in docs/images/"
    exit 1
fi

echo "  使用画像: $((6 - MISSING))枚"
echo "  動画長: 25秒"
echo "  生成中..."

# Write filter to temp file (avoids shell quoting issues)
# No drawtext -- homebrew ffmpeg may not have freetype support
FILTER_FILE=$(mktemp /tmp/koe-filter-XXXX.txt)
cat > "$FILTER_FILE" << 'EOF'
[0:v]scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:color=black,zoompan=z='min(zoom+0.001,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=125:s=1080x1080:fps=25[v0];
[1:v]scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:color=black,zoompan=z='min(zoom+0.001,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=125:s=1080x1080:fps=25[v1];
[2:v]scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:color=black,zoompan=z='min(zoom+0.001,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=125:s=1080x1080:fps=25[v2];
[3:v]scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:color=black,zoompan=z='min(zoom+0.001,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=125:s=1080x1080:fps=25[v3];
[4:v]scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:color=black,zoompan=z='min(zoom+0.001,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=125:s=1080x1080:fps=25[v4];
[5:v]scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:color=black,zoompan=z='min(zoom+0.001,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=125:s=1080x1080:fps=25[v5];
[v0][v1]xfade=transition=fade:duration=1:offset=4[t1];
[t1][v2]xfade=transition=fade:duration=1:offset=8[t2];
[t2][v3]xfade=transition=fade:duration=1:offset=12[t3];
[t3][v4]xfade=transition=fade:duration=1:offset=16[t4];
[t4][v5]xfade=transition=fade:duration=1:offset=20[out]
EOF

ffmpeg -y \
    -loop 1 -t 5 -i "$IMG1" \
    -loop 1 -t 5 -i "$IMG2" \
    -loop 1 -t 5 -i "$IMG3" \
    -loop 1 -t 5 -i "$IMG4" \
    -loop 1 -t 5 -i "$IMG5" \
    -loop 1 -t 5 -i "$IMG6" \
    -filter_complex_script "$FILTER_FILE" \
    -map "[out]" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 25 \
    -t 25 "$OUT" 2>&1 | tail -3

rm -f "$FILTER_FILE"

if [ -f "$OUT" ]; then
    SIZE=$(du -h "$OUT" | cut -f1)
    echo "  デモ動画生成完了: $OUT ($SIZE)"
    echo "  -> SNS投稿: bash scripts/post-sns.sh"
else
    echo "  動画生成失敗"
    echo "  テキスト付きで生成するには: brew install ffmpeg --with-freetype"
fi
