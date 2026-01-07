#!/bin/bash
# 自动设置环境变量并启动 DocSync GUI

# 确保使用 miniconda 的 python
export PATH=/opt/miniconda3/bin:$PATH

echo "正在启动 DocSync..."
cd electron-app
npm start
