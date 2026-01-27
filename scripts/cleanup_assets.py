#!/usr/bin/env python3
"""
DocSync Assets Cleanup Script (Safe Version)

This script scans a Feishu Drive folder for duplicate/orphan files,
ensuring files still referenced by documents are NOT deleted.

Process:
1. Scan all documents in sync folder to find referenced file tokens
2. List all files in Assets folder
3. Identify orphan files (not referenced by any document)
4. Among orphans, find duplicates by filename (same name = likely duplicates)
5. Delete orphan duplicates (keeping one copy each)
"""

import os
import sys
import json
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from doc_sync.feishu_client import FeishuClient
from doc_sync.config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_USER_ACCESS_TOKEN
from doc_sync.logger import logger
import lark_oapi as lark


def get_referenced_tokens_from_doc(client: FeishuClient, doc_token: str) -> set:
    """Extract all file/image tokens referenced in a document."""
    tokens = set()
    try:
        blocks = client.list_document_blocks(doc_token)
        for block in blocks:
            # Convert to dict for easier access
            try:
                block_dict = json.loads(lark.JSON.marshal(block))
            except:
                continue
            
            # Check for image blocks (type 27)
            if block_dict.get("block_type") == 27:
                img = block_dict.get("image", {})
                if img.get("token"):
                    tokens.add(img["token"])
            
            # Check for file blocks (type 23)
            elif block_dict.get("block_type") == 23:
                file_info = block_dict.get("file", {})
                if file_info.get("token"):
                    tokens.add(file_info["token"])
                    
    except Exception as e:
        logger.warning(f"无法读取文档 {doc_token}: {e}")
    
    return tokens


def scan_docs_for_references(client: FeishuClient, folder_token: str) -> set:
    """Recursively scan all documents in a folder to find referenced tokens."""
    all_tokens = set()
    
    files = client.list_folder_files(folder_token)
    for file in files:
        if file.type == "docx":
            logger.debug(f"扫描文档: {file.name}")
            tokens = get_referenced_tokens_from_doc(client, file.token)
            all_tokens.update(tokens)
        elif file.type == "folder":
            # Recursively scan subfolders
            sub_tokens = scan_docs_for_references(client, file.token)
            all_tokens.update(sub_tokens)
    
    return all_tokens


def cleanup_assets(assets_folder_token: str, docs_folder_token: str, dry_run: bool = True):
    """
    Clean up duplicate and orphan files in the assets folder.
    
    Args:
        assets_folder_token: Token of the Assets folder to clean
        docs_folder_token: Token of the documents folder (to check references)
        dry_run: If True, only report without deleting
    """
    logger.header("DocSync Assets 清理工具 (安全模式)", icon="🧹")
    
    client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, 
                          user_access_token=FEISHU_USER_ACCESS_TOKEN)
    
    # Step 1: Scan all documents to find referenced tokens
    logger.info("步骤 1/3: 扫描文档中正在使用的附件...", icon="📄")
    referenced_tokens = scan_docs_for_references(client, docs_folder_token)
    logger.success(f"发现 {len(referenced_tokens)} 个正在被引用的附件 Token")
    
    # Step 2: List all files in Assets folder
    logger.info("步骤 2/3: 列出 Assets 文件夹中的所有文件...", icon="📂")
    asset_files = client.list_folder_files(assets_folder_token)
    
    # Filter to actual files (not folders)
    files_only = [f for f in asset_files if f.type == "file"]
    logger.info(f"Assets 文件夹中共有 {len(files_only)} 个文件")
    
    # Step 3: Identify orphan files (not referenced)
    logger.info("步骤 3/3: 识别孤立文件和重复项...", icon="🔍")
    
    orphan_files = []
    referenced_files = []
    
    for f in files_only:
        if f.token in referenced_tokens:
            referenced_files.append(f)
        else:
            orphan_files.append(f)
    
    logger.info(f"  - 被引用的文件: {len(referenced_files)} 个 (将保留)")
    logger.warning(f"  - 孤立文件: {len(orphan_files)} 个 (可能为重复或无用)")
    
    if not orphan_files:
        logger.success("没有孤立文件需要清理！")
        return
    
    # Group orphan files by filename to find duplicates
    name_to_files = defaultdict(list)
    for f in orphan_files:
        name_to_files[f.name].append(f)
    
    # Find duplicates (same filename appearing multiple times)
    duplicate_groups = {name: files for name, files in name_to_files.items() if len(files) > 1}
    unique_orphans = {name: files[0] for name, files in name_to_files.items() if len(files) == 1}
    
    duplicate_count = sum(len(files) - 1 for files in duplicate_groups.values())
    
    logger.info(f"\n分析结果:")
    logger.info(f"  - 孤立且唯一的文件: {len(unique_orphans)} 个")
    logger.warning(f"  - 孤立且重复的文件: {duplicate_count} 个 (可删除)")
    
    if not duplicate_groups:
        logger.success("没有重复的孤立文件需要清理！")
        return
    
    # Report duplicates
    logger.info("\n重复文件详情:")
    for name, files in duplicate_groups.items():
        logger.info(f"  文件名: {name}")
        for i, f in enumerate(files):
            status = "保留" if i == 0 else "删除"
            logger.info(f"    [{status}] Token: {f.token}")
    
    if dry_run:
        logger.warning("\n[DRY RUN 模式] 未执行删除。使用 --execute 参数执行实际删除。")
        return
    
    # Execute deletion
    logger.header("开始删除重复的孤立文件...", icon="🗑️")
    deleted_count = 0
    failed_count = 0
    
    for name, files in duplicate_groups.items():
        for f in files[1:]:  # Keep first, delete rest
            if client.delete_file(f.token, file_type="file"):
                deleted_count += 1
                logger.success(f"已删除: {name} ({f.token})")
            else:
                failed_count += 1
                logger.error(f"删除失败: {name}")
    
    logger.success(f"\n清理完成！删除 {deleted_count} 个文件，失败 {failed_count} 个。")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="清理飞书云盘中的重复/孤立附件（安全模式：不删除被文档引用的文件）",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
示例:
  1. 预览模式 (推荐先运行):
     python cleanup_assets.py <assets_folder_token> <docs_folder_token>
  
  2. 执行删除:
     python cleanup_assets.py <assets_folder_token> <docs_folder_token> --execute
"""
    )
    parser.add_argument(
        "assets_token",
        help="Assets 文件夹的 Token (存放附件的文件夹)"
    )
    parser.add_argument(
        "docs_token",
        help="文档文件夹的 Token (同步的笔记文件夹，用于检查引用)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行实际删除操作 (默认只进行预览)"
    )
    
    args = parser.parse_args()
    
    cleanup_assets(args.assets_token, args.docs_token, dry_run=not args.execute)


if __name__ == "__main__":
    main()
