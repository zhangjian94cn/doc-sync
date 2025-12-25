#!/bin/bash
# 一键生成多平台图标
# 需要安装：npm i -g svg2img imagemagick

set -e

SRC=icon.svg
DST_DIR=.

# 生成 512x512 PNG
svg2img $SRC $DST_DIR/icon-512.png -w 512 -h 512

# macOS .icns
mkdir -p icon.iconset
for size in 16 32 64 128 256 512; do
  svg2img $SRC icon.iconset/icon_${size}x${size}.png -w $size -h $size
done
iconutil -c icns icon.iconset -o $DST_DIR/icon.icns
rm -rf icon.iconset

# Windows .ico
convert $DST_DIR/icon-512.png -resize 256x256 $DST_DIR/icon-256.png
convert $DST_DIR/icon-256.png $DST_DIR/icon-512.png -resize 128x128 $DST_DIR/icon-128.png \
  $DST_DIR/icon-64.png $DST_DIR/icon-32.png $DST_DIR/icon-16.png $DST_DIR/icon.ico

# Linux PNG (AppImage)
cp $DST_DIR/icon-512.png $DST_DIR/icon.png

echo "✅ 图标生成完成：icon.icns | icon.ico | icon.png"