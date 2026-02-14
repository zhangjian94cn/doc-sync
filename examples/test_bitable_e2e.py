#!/usr/bin/env python3
"""
Bitable E2E 端到端测试

演示完整的 Bitable 工作流：
1. 创建多维表格 (获取 app_token)
2. 上传本地 CSV 数据 (Push)
3. 验证云端数据 (Verify)
4. 下载到本地 (Pull)
5. 增量更新测试 (Incremental Update)

所有操作都通过 SDK 的原生 HTTP 传输完成。
"""

import os
import sys
import json
import csv
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from doc_sync.feishu_client import FeishuClient
from doc_sync.sync.bitable_sync import BitableSyncManager
from doc_sync.converter.bitable_converter import BitableConverter
from doc_sync.config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_USER_ACCESS_TOKEN
from doc_sync.logger import logger


def main():
    logger.header("Bitable 端到端测试", icon="🧪")
    
    client = FeishuClient(
        FEISHU_APP_ID, FEISHU_APP_SECRET,
        user_access_token=FEISHU_USER_ACCESS_TOKEN
    )
    
    csv_path = os.path.join(os.path.dirname(__file__), "sample_bitable_data.csv")
    if not os.path.exists(csv_path):
        logger.error(f"测试数据文件不存在: {csv_path}")
        return
    
    # =====================================================================
    # Step 1: 创建多维表格
    # =====================================================================
    logger.header("Step 1: 创建多维表格", icon="📋")
    app_info = client.bitable_create_app("DocSync 测试表格")
    if not app_info:
        logger.error("创建多维表格失败！请检查权限配置。")
        return
    
    app_token = app_info["app_token"]
    url = app_info.get("url", "")
    logger.success(f"多维表格已创建: {app_token}")
    if url:
        logger.info(f"链接: {url}")
    
    # =====================================================================
    # Step 2: 上传 CSV → 多维表格
    # =====================================================================
    logger.header("Step 2: 上传本地 CSV → 多维表格", icon="⬆️")
    manager = BitableSyncManager(
        client=client,
        app_token=app_token,
        table_name="项目管理",
        key_field="项目名称",
    )
    
    result = manager.push(csv_path)
    logger.info(str(result))
    
    if not result.success:
        logger.error("上传失败，终止测试")
        return
    
    table_id = result.table_id
    logger.success(f"数据表 ID: {table_id}")
    
    # =====================================================================
    # Step 3: 验证云端数据
    # =====================================================================
    logger.header("Step 3: 验证云端数据", icon="🔍")
    
    fields = client.bitable_list_fields(app_token, table_id)
    records = client.bitable_list_records(app_token, table_id)
    
    logger.info(f"字段数: {len(fields)}")
    for f in fields:
        logger.info(f"  📌 {f['field_name']} (type={f['type']}, id={f['field_id']})")
    
    logger.info(f"记录数: {len(records)}")
    for r in records:
        name = r["fields"].get("项目名称", "Unknown")
        budget = r["fields"].get("预算(万元)", "?")
        logger.info(f"  📄 {name} - 预算: {budget}万")
    
    assert len(fields) >= 9, f"期望至少 9 个字段, 实际 {len(fields)}"
    assert len(records) == 5, f"期望 5 条记录, 实际 {len(records)}"
    logger.success("Step 3 验证通过!")
    
    # =====================================================================
    # Step 4: 下载到本地 CSV
    # =====================================================================
    logger.header("Step 4: 下载云端数据 → 本地 CSV", icon="⬇️")
    
    output_csv = os.path.join(tempfile.gettempdir(), "bitable_downloaded.csv")
    pull_manager = BitableSyncManager(
        client=client,
        app_token=app_token,
        table_id=table_id,
    )
    
    pull_result = pull_manager.pull(output_csv)
    logger.info(str(pull_result))
    
    if pull_result.success:
        with open(output_csv, "r", encoding="utf-8") as f:
            logger.info(f"下载内容:\n{f.read()}")
        os.unlink(output_csv)
    
    # =====================================================================
    # Step 5: 增量更新测试
    # =====================================================================
    logger.header("Step 5: 增量更新测试", icon="🔄")
    
    updated_csv = os.path.join(tempfile.gettempdir(), "bitable_updated.csv")
    with open(csv_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # Modify "Alpha计划" budget from 50 to 80
    updated_lines = []
    for line in lines:
        if line.startswith("Alpha计划"):
            line = line.replace(",50,", ",80,")
        updated_lines.append(line)
    
    # Add a new record
    updated_lines.append("Zeta发布,孙八,45,未开始,2024-08-15,高,4,0,https://example.com/zeta\n")
    
    with open(updated_csv, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)
    
    incr_manager = BitableSyncManager(
        client=client,
        app_token=app_token,
        table_id=table_id,
        key_field="项目名称",
    )
    
    incr_result = incr_manager.push(updated_csv)
    logger.info(str(incr_result))
    os.unlink(updated_csv)
    
    # =====================================================================
    # 完成
    # =====================================================================
    logger.header("测试完成!", icon="🎉")
    logger.info(f"App Token: {app_token}")
    logger.info(f"Table ID: {table_id}")
    logger.info("请在飞书中查看多维表格确认数据正确性")
    if url:
        logger.info(f"飞书链接: {url}")


if __name__ == "__main__":
    main()
