#!/usr/bin/env python3
"""飞书文档下载脚本 - 将飞书文档下载为本地 Markdown

此脚本将指定的飞书文档转换为 Markdown 格式并保存到本地。
支持下载图片到本地 assets 目录。

使用方式:
    python scripts/download_doc.py <document_id> [output_path]

示例:
    # 下载到当前目录
    python scripts/download_doc.py WBGOdnG5nolMv4xXnRRcffe5nDc
    
    # 下载到指定文件
    python scripts/download_doc.py WBGOdnG5nolMv4xXnRRcffe5nDc ./output/my_doc.md
"""

import os
import sys
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import FEISHU_APP_ID, FEISHU_APP_SECRET
from src.feishu_client import FeishuClient
from src.converter import FeishuToMarkdown
from src.logger import logger


def download_document(doc_id: str, output_path: str = None, download_images: bool = True):
    """Download a Feishu document to local Markdown.
    
    Args:
        doc_id: The document ID (from URL)
        output_path: Output Markdown file path
        download_images: Whether to download images locally
    """
    print(f"\n📄 正在下载文档: {doc_id}")
    
    # Initialize client
    client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET)
    
    # Get document info
    print("🔍 获取文档信息...")
    file_info = client.get_file_info(doc_id, obj_type="docx")
    if file_info:
        doc_name = file_info.name or doc_id
        print(f"   文档名称: {doc_name}")
    else:
        doc_name = doc_id
        print("   ⚠️ 无法获取文档信息")
    
    # Set output path
    if not output_path:
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in doc_name)
        output_path = f"{safe_name}.md"
    
    # Create output directory
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Assets directory
    assets_dir = os.path.join(output_dir or ".", "assets")
    if download_images and not os.path.exists(assets_dir):
        os.makedirs(assets_dir)
    
    # Get all blocks
    print("📥 获取文档内容...")
    blocks = client.list_document_blocks(doc_id)
    if not blocks:
        print("❌ 无法获取文档内容")
        return False
    
    # Filter out page block
    blocks = [b for b in blocks if b.block_type != 1]
    print(f"   共获取 {len(blocks)} 个块")
    
    # Image downloader callback
    downloaded_count = [0]  # Use list for mutable in closure
    
    def image_downloader(token: str) -> str:
        """Download image and return relative path."""
        if not download_images:
            return None
        
        save_path = os.path.join(assets_dir, f"{token}.png")
        if client.download_image(token, save_path):
            downloaded_count[0] += 1
            # Return relative path from markdown file
            rel_path = os.path.relpath(save_path, output_dir or ".")
            return rel_path
        return None
    
    # Convert to Markdown
    print("🔄 转换为 Markdown...")
    converter = FeishuToMarkdown(image_downloader=image_downloader)
    md_content = converter.convert(blocks)
    
    # Add metadata header
    header = f"---\n# Downloaded from Feishu\n# Document ID: {doc_id}\n# Original Title: {doc_name}\n---\n\n"
    md_content = header + md_content
    
    # Write to file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    
    print(f"\n✅ 下载完成!")
    print(f"   📄 文件: {output_path}")
    print(f"   📊 块数: {len(blocks)}")
    if downloaded_count[0] > 0:
        print(f"   🖼️  图片: {downloaded_count[0]} 个")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="下载飞书文档为 Markdown 文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s WBGOdnG5nolMv4xXnRRcffe5nDc
  %(prog)s WBGOdnG5nolMv4xXnRRcffe5nDc ./output/doc.md
  %(prog)s WBGOdnG5nolMv4xXnRRcffe5nDc --no-images
        """
    )
    
    parser.add_argument("doc_id", help="飞书文档 ID（从 URL 获取）")
    parser.add_argument("output", nargs="?", help="输出文件路径（可选）")
    parser.add_argument("--no-images", action="store_true", 
                        help="不下载图片到本地")
    
    args = parser.parse_args()
    
    # Check config
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("❌ 请配置环境变量 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
        return 1
    
    # Download
    success = download_document(
        args.doc_id, 
        args.output, 
        download_images=not args.no_images
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
