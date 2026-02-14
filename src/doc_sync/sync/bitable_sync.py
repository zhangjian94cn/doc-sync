"""
Bitable Sync Manager Module

Provides synchronization between local data files (CSV/JSON/Markdown tables)
and Feishu Bitable (多维表格).

Supports:
- Local → Cloud: Upload local data to Bitable
- Cloud → Local: Download Bitable data to local file
- Incremental sync: Match records by key_field, only update changed records
- Full overwrite: Clear cloud data and re-upload all records
"""

import os
import time
from typing import Any, Dict, List, Optional, Tuple

from doc_sync.feishu_client import FeishuClient
from doc_sync.converter.bitable_converter import BitableConverter
from doc_sync.logger import logger
from doc_sync.feishu.bitable import FIELD_TYPE_TEXT


class BitableSyncResult:
    """Result of a Bitable sync operation."""
    
    def __init__(self):
        self.success: bool = False
        self.records_created: int = 0
        self.records_updated: int = 0
        self.records_deleted: int = 0
        self.fields_created: int = 0
        self.table_id: Optional[str] = None
        self.error: Optional[str] = None
    
    def __str__(self):
        if not self.success:
            return f"❌ 同步失败: {self.error}"
        parts = []
        if self.fields_created:
            parts.append(f"新增 {self.fields_created} 个字段")
        if self.records_created:
            parts.append(f"新增 {self.records_created} 条记录")
        if self.records_updated:
            parts.append(f"更新 {self.records_updated} 条记录")
        if self.records_deleted:
            parts.append(f"删除 {self.records_deleted} 条记录")
        if not parts:
            parts.append("无变更")
        return f"✅ 同步成功: {', '.join(parts)}"


class BitableSyncManager:
    """Manages synchronization between local data files and Feishu Bitable.
    
    Supports bidirectional sync with incremental or full overwrite modes.
    """
    
    def __init__(self, client: FeishuClient, app_token: str,
                 table_id: str = None, table_name: str = None,
                 key_field: str = None, overwrite: bool = False):
        """Initialize the Bitable sync manager.
        
        Args:
            client: Authenticated FeishuClient instance
            app_token: Bitable app token
            table_id: Target table ID (None to auto-create)
            table_name: Table name (used when auto-creating)
            key_field: Field name used as unique key for incremental sync
            overwrite: If True, full overwrite mode; if False, incremental sync
        """
        self.client = client
        self.app_token = app_token
        self.table_id = table_id
        self.table_name = table_name
        self.key_field = key_field
        self.overwrite = overwrite
    
    # =========================================================================
    # Push: Local → Cloud
    # =========================================================================
    
    def push(self, source_path: str) -> BitableSyncResult:
        """Push local data to Feishu Bitable.
        
        Args:
            source_path: Path to local data file (CSV/JSON/MD)
            
        Returns:
            BitableSyncResult with operation details
        """
        result = BitableSyncResult()
        
        # 1. Parse local data
        fields, records = self._load_local_data(source_path)
        if not fields:
            result.error = f"无法解析数据文件: {source_path}"
            return result
        
        logger.info(f"📄 本地数据: {len(fields)} 个字段, {len(records)} 条记录")
        
        # 2. Ensure table exists
        table_is_new = False
        if not self.table_id:
            table_name = self.table_name or os.path.splitext(os.path.basename(source_path))[0]
            self.table_id, table_is_new = self._ensure_table(table_name, fields)
            if not self.table_id:
                result.error = "创建数据表失败"
                return result
        
        result.table_id = self.table_id
        
        # 3. Sync fields (skip if table was just created with fields)
        if not table_is_new:
            new_fields = self._sync_fields(fields)
            result.fields_created = new_fields
        
        # 4. Sync records
        if self.overwrite:
            result = self._push_overwrite(records, result)
        else:
            result = self._push_incremental(records, result)
        
        result.success = result.error is None
        return result
    
    def _push_overwrite(self, records: List[Dict], result: BitableSyncResult) -> BitableSyncResult:
        """Full overwrite: delete all existing records, then create all local records."""
        # Delete existing records
        existing = self.client.bitable_list_records(self.app_token, self.table_id)
        if existing:
            record_ids = [r["record_id"] for r in existing]
            logger.info(f"🗑️ 删除云端 {len(record_ids)} 条记录")
            if not self.client.bitable_batch_delete_records(
                self.app_token, self.table_id, record_ids
            ):
                result.error = "删除云端记录失败"
                return result
            result.records_deleted = len(record_ids)
        
        # Create all records
        if records:
            logger.info(f"⬆️ 上传 {len(records)} 条记录")
            created_ids = self.client.bitable_batch_create_records(
                self.app_token, self.table_id, records
            )
            result.records_created = len(created_ids)
            if len(created_ids) != len(records):
                result.error = f"部分记录创建失败: 预期 {len(records)}, 实际 {len(created_ids)}"
        
        return result
    
    def _push_incremental(self, local_records: List[Dict], result: BitableSyncResult) -> BitableSyncResult:
        """Incremental sync: match by key_field, create/update/delete as needed."""
        # Get existing cloud records
        cloud_records = self.client.bitable_list_records(self.app_token, self.table_id)
        
        if not self.key_field:
            # No key field: if cloud is empty, just create all; otherwise full overwrite
            if not cloud_records:
                if local_records:
                    created_ids = self.client.bitable_batch_create_records(
                        self.app_token, self.table_id, local_records
                    )
                    result.records_created = len(created_ids)
                return result
            else:
                logger.info("⚠️ 未指定 key_field，使用全量覆盖模式")
                return self._push_overwrite(local_records, result)
        
        # Build index of cloud records by key field value
        cloud_index: Dict[str, Dict] = {}
        for rec in cloud_records:
            key_val = rec["fields"].get(self.key_field)
            if key_val is not None:
                key_str = str(key_val)
                cloud_index[key_str] = rec
        
        # Build index of local records by key field value
        to_create: List[Dict] = []
        to_update: List[Dict] = []
        matched_keys = set()
        
        for local_rec in local_records:
            local_fields = local_rec.get("fields", local_rec)
            key_val = local_fields.get(self.key_field)
            if key_val is None:
                # No key value: always create
                to_create.append(local_rec)
                continue
            
            key_str = str(key_val)
            matched_keys.add(key_str)
            
            cloud_rec = cloud_index.get(key_str)
            if cloud_rec is None:
                # New record
                to_create.append(local_rec)
            else:
                # Check if fields changed
                if self._records_differ(local_fields, cloud_rec["fields"]):
                    to_update.append({
                        "record_id": cloud_rec["record_id"],
                        "fields": local_fields,
                    })
        
        # Find records to delete (in cloud but not in local)
        to_delete = [
            rec["record_id"] for key_str, rec in cloud_index.items()
            if key_str not in matched_keys
        ]
        
        # Execute operations
        if to_create:
            logger.info(f"⬆️ 新增 {len(to_create)} 条记录")
            created_ids = self.client.bitable_batch_create_records(
                self.app_token, self.table_id, to_create
            )
            result.records_created = len(created_ids)
        
        if to_update:
            logger.info(f"🔄 更新 {len(to_update)} 条记录")
            self.client.bitable_batch_update_records(
                self.app_token, self.table_id, to_update
            )
            result.records_updated = len(to_update)
        
        if to_delete:
            logger.info(f"🗑️ 删除 {len(to_delete)} 条记录")
            self.client.bitable_batch_delete_records(
                self.app_token, self.table_id, to_delete
            )
            result.records_deleted = len(to_delete)
        
        return result
    
    # =========================================================================
    # Pull: Cloud → Local
    # =========================================================================
    
    def pull(self, output_path: str, output_format: str = None) -> BitableSyncResult:
        """Pull Bitable data to a local file.
        
        Args:
            output_path: Output file path
            output_format: 'csv' or 'json' (auto-detected from extension if None)
            
        Returns:
            BitableSyncResult with operation details
        """
        result = BitableSyncResult()
        
        if not self.table_id:
            result.error = "需要指定 table_id 才能拉取数据"
            return result
        
        # Detect format
        if not output_format:
            output_format = BitableConverter.detect_format(output_path) or "csv"
        
        # Get cloud data
        fields = self.client.bitable_list_fields(self.app_token, self.table_id)
        if not fields:
            result.error = "获取字段列表失败"
            return result
        
        records = self.client.bitable_list_records(self.app_token, self.table_id)
        logger.info(f"📥 云端数据: {len(fields)} 个字段, {len(records)} 条记录")
        
        # Export
        if output_format == "csv":
            success = BitableConverter.records_to_csv(records, fields, output_path)
        elif output_format == "json":
            success = BitableConverter.records_to_json(records, fields, output_path)
        else:
            result.error = f"不支持的输出格式: {output_format}"
            return result
        
        if success:
            result.success = True
            result.records_created = len(records)
            result.table_id = self.table_id
        else:
            result.error = f"导出到 {output_path} 失败"
        
        return result
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _load_local_data(self, source_path: str) -> Tuple[List[Dict], List[Dict]]:
        """Load data from a local file, auto-detecting format."""
        fmt = BitableConverter.detect_format(source_path)
        
        if fmt == "csv":
            return BitableConverter.csv_to_records(source_path)
        elif fmt == "json":
            return BitableConverter.json_to_records(source_path)
        elif fmt == "markdown":
            with open(source_path, "r", encoding="utf-8") as f:
                content = f.read()
            return BitableConverter.markdown_table_to_records(content)
        else:
            logger.error(f"不支持的文件格式: {source_path}")
            return [], []
    
    def _ensure_table(self, name: str, fields: List[Dict]) -> Tuple[Optional[str], bool]:
        """Ensure a table exists, creating it if needed.
        
        Args:
            name: Table name
            fields: Field definitions for new table
            
        Returns:
            Tuple of (Table ID or None, whether table was newly created)
        """
        # Check if table already exists by name
        existing_tables = self.client.bitable_list_tables(self.app_token)
        for t in existing_tables:
            if t["name"] == name:
                logger.info(f"📋 使用现有数据表: {name} ({t['table_id']})")
                return t["table_id"], False
        
        # Create new table with fields
        logger.info(f"📋 创建数据表: {name}")
        table_id = self.client.bitable_create_table(self.app_token, name, fields)
        return table_id, True
    
    def _sync_fields(self, local_fields: List[Dict]) -> int:
        """Ensure all local fields exist in the cloud table.
        
        Returns:
            Number of new fields created
        """
        cloud_fields = self.client.bitable_list_fields(self.app_token, self.table_id)
        cloud_field_names = {f["field_name"] for f in cloud_fields}
        
        created = 0
        for local_f in local_fields:
            if local_f["field_name"] not in cloud_field_names:
                field_id = self.client.bitable_create_field(
                    self.app_token, self.table_id,
                    local_f["field_name"], local_f.get("type", FIELD_TYPE_TEXT)
                )
                if field_id:
                    created += 1
        
        return created
    
    def _records_differ(self, local_fields: Dict, cloud_fields: Dict) -> bool:
        """Compare two records to check if they have different field values.
        
        Only compares fields present in local_fields.
        
        Args:
            local_fields: Local record fields dict
            cloud_fields: Cloud record fields dict
            
        Returns:
            True if any field values differ
        """
        for key, local_val in local_fields.items():
            cloud_val = cloud_fields.get(key)
            
            # Normalize values for comparison
            local_str = self._normalize_value(local_val)
            cloud_str = self._normalize_value(cloud_val)
            
            if local_str != cloud_str:
                return True
        
        return False
    
    @staticmethod
    def _normalize_value(val: Any) -> str:
        """Normalize a value to a string for comparison."""
        if val is None:
            return ""
        if isinstance(val, bool):
            return "true" if val else "false"
        if isinstance(val, (int, float)):
            # Normalize numbers: remove trailing zeros
            return str(val).rstrip("0").rstrip(".")
        if isinstance(val, list):
            parts = []
            for item in val:
                if isinstance(item, dict):
                    parts.append(str(item.get("text", item.get("name", str(item)))))
                else:
                    parts.append(str(item))
            return ",".join(sorted(parts))
        if isinstance(val, dict):
            if "link" in val:
                return val.get("link", "")
            if "text" in val:
                return val.get("text", "")
            return str(val)
        return str(val).strip()
