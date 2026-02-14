"""
Feishu Bitable (多维表格) Operations Module

Contains methods for Bitable/Base manipulation:
- App: get info
- Table: list, create
- Field: list, create, update, delete
- Record: list, batch create/update/delete, search
- View: list
"""

import time
import json as json_module
from typing import Any, Dict, List, Optional

import lark_oapi as lark
from lark_oapi.api.bitable.v1 import *

from doc_sync.logger import logger
from doc_sync.config import API_MAX_RETRIES, API_RETRY_BASE_DELAY


# Bitable field type constants
FIELD_TYPE_TEXT = 1          # 多行文本
FIELD_TYPE_NUMBER = 2       # 数字
FIELD_TYPE_SELECT = 3       # 单选
FIELD_TYPE_MULTI_SELECT = 4 # 多选
FIELD_TYPE_DATE = 5         # 日期
FIELD_TYPE_CHECKBOX = 7     # 复选框
FIELD_TYPE_PERSON = 11      # 人员
FIELD_TYPE_URL = 15         # 超链接
FIELD_TYPE_ATTACHMENT = 17  # 附件
FIELD_TYPE_FORMULA = 20     # 公式
FIELD_TYPE_AUTO_NUMBER = 1005  # 自动编号


class BitableOperationsMixin:
    """Mixin class providing Bitable (多维表格) operation methods for FeishuClient."""

    # =========================================================================
    # App Operations
    # =========================================================================

    def bitable_create_app(self, name: str, folder_token: str = None,
                           time_zone: str = "Asia/Shanghai") -> Optional[Dict[str, Any]]:
        """Create a new Bitable app.
        
        Args:
            name: App name
            folder_token: Optional folder token to create the app in
            time_zone: Time zone (default: Asia/Shanghai)
            
        Returns:
            Dict with app_token and other info, or None if failed
        """
        self._rate_limit()
        
        app_builder = ReqApp.builder().name(name).time_zone(time_zone)
        if folder_token:
            app_builder.folder_token(folder_token)
        
        request = CreateAppRequest.builder() \
            .request_body(app_builder.build()) \
            .build()
        
        response = self.client.bitable.v1.app.create(request, self._get_request_option())
        if response.success():
            app = response.data.app
            result = {
                "app_token": app.app_token,
                "name": app.name,
                "url": app.url if hasattr(app, 'url') else None,
            }
            logger.success(f"创建多维表格成功: {name} ({app.app_token})")
            return result
        logger.error(f"创建多维表格失败: {response.code} {response.msg}")
        return None

    def bitable_get_app_info(self, app_token: str) -> Optional[Dict[str, Any]]:
        """Get Bitable app info.
        
        Args:
            app_token: The Bitable app token
            
        Returns:
            App info dict or None if failed
        """
        self._rate_limit()
        request = GetAppRequest.builder().app_token(app_token).build()
        response = self.client.bitable.v1.app.get(request, self._get_request_option())
        if response.success():
            app = response.data.app
            return {
                "app_token": app.app_token,
                "name": app.name,
                "revision": app.revision,
                "is_advanced": app.is_advanced,
            }
        logger.error(f"获取多维表格信息失败: {response.code} {response.msg}")
        return None

    # =========================================================================
    # Table Operations
    # =========================================================================

    def bitable_list_tables(self, app_token: str) -> List[Dict[str, Any]]:
        """List all tables in a Bitable app.
        
        Args:
            app_token: The Bitable app token
            
        Returns:
            List of table info dicts
        """
        tables = []
        page_token = None
        
        while True:
            self._rate_limit()
            builder = ListAppTableRequest.builder().app_token(app_token).page_size(100)
            if page_token:
                builder.page_token(page_token)
            
            response = self.client.bitable.v1.app_table.list(builder.build(), self._get_request_option())
            if not response.success():
                logger.error(f"列出数据表失败: {response.code} {response.msg}")
                return tables
            
            if response.data and response.data.items:
                for t in response.data.items:
                    tables.append({
                        "table_id": t.table_id,
                        "name": t.name,
                        "revision": t.revision,
                    })
            
            page_token = response.data.page_token if response.data else None
            if not page_token:
                break
        
        return tables

    def bitable_create_table(self, app_token: str, name: str,
                             fields: List[Dict[str, Any]] = None) -> Optional[str]:
        """Create a new table in a Bitable app.
        
        Args:
            app_token: The Bitable app token
            name: Table name
            fields: Optional list of field definitions [{"field_name": str, "type": int}]
            
        Returns:
            Table ID if successful, None otherwise
        """
        self._rate_limit()
        
        # Build the table structure
        table_builder = ReqTable.builder().name(name)
        
        if fields:
            field_objs = []
            for f in fields:
                fb = AppTableCreateHeader.builder() \
                    .field_name(f["field_name"]) \
                    .type(f["type"])
                if "ui_type" in f:
                    fb.ui_type(f["ui_type"])
                if "property" in f:
                    fb.property(f["property"])
                field_objs.append(fb.build())
            table_builder.default_view_name("默认视图")
            table_builder.fields(field_objs)
        
        request = CreateAppTableRequest.builder() \
            .app_token(app_token) \
            .request_body(
                CreateAppTableRequestBody.builder()
                    .table(table_builder.build())
                    .build()
            ).build()
        
        response = self.client.bitable.v1.app_table.create(request, self._get_request_option())
        if response.success():
            table_id = response.data.table_id
            logger.success(f"创建数据表成功: {name} ({table_id})")
            return table_id
        logger.error(f"创建数据表失败: {response.code} {response.msg}")
        return None

    # =========================================================================
    # Field Operations
    # =========================================================================

    def bitable_list_fields(self, app_token: str, table_id: str) -> List[Dict[str, Any]]:
        """List all fields in a table using SDK native transport.
        
        Args:
            app_token: The Bitable app token
            table_id: Table ID
            
        Returns:
            List of field info dicts
        """
        fields = []
        page_token = None
        
        while True:
            self._rate_limit()
            
            req_builder = ListAppTableFieldRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .page_size(100)
            if page_token:
                req_builder.page_token(page_token)
            
            request = req_builder.build()
            response = self.client.bitable.v1.app_table_field.list(
                request, self._get_request_option()
            )
            
            if not response.success():
                logger.error(f"列出字段失败: {response.code} {response.msg}")
                return fields
            
            if response.data and response.data.items:
                for f in response.data.items:
                    fields.append({
                        "field_id": f.field_id,
                        "field_name": f.field_name,
                        "type": f.type,
                        "is_primary": getattr(f, 'is_primary', False),
                        "property": getattr(f, 'property', None),
                    })
            
            if response.data and response.data.has_more:
                page_token = response.data.page_token
            else:
                break
        
        return fields

    def bitable_create_field(self, app_token: str, table_id: str,
                             field_name: str, field_type: int = FIELD_TYPE_TEXT,
                             property: Dict = None) -> Optional[str]:
        """Create a new field in a table.
        
        Args:
            app_token: The Bitable app token
            table_id: Table ID
            field_name: Field name
            field_type: Field type (default: text)
            property: Optional field property config
            
        Returns:
            Field ID if successful, None otherwise
        """
        self._rate_limit()
        
        field_builder = AppTableField.builder() \
            .field_name(field_name) \
            .type(field_type)
        if property:
            field_builder.property(AppTableFieldProperty.builder().build())
        
        request = CreateAppTableFieldRequest.builder() \
            .app_token(app_token) \
            .table_id(table_id) \
            .request_body(field_builder.build()) \
            .build()
        
        response = self.client.bitable.v1.app_table_field.create(
            request, self._get_request_option()
        )
        if response.success():
            field_id = response.data.field.field_id
            logger.debug(f"创建字段成功: {field_name} ({field_id})")
            return field_id
        logger.error(f"创建字段失败: {response.code} {response.msg}")
        return None

    def bitable_delete_field(self, app_token: str, table_id: str,
                             field_id: str) -> bool:
        """Delete a field from a table.
        
        Args:
            app_token: The Bitable app token
            table_id: Table ID
            field_id: Field ID to delete
            
        Returns:
            True if successful
        """
        self._rate_limit()
        request = DeleteAppTableFieldRequest.builder() \
            .app_token(app_token) \
            .table_id(table_id) \
            .field_id(field_id) \
            .build()
        
        response = self.client.bitable.v1.app_table_field.delete(
            request, self._get_request_option()
        )
        if response.success():
            logger.debug(f"删除字段成功: {field_id}")
            return True
        logger.error(f"删除字段失败: {response.code} {response.msg}")
        return False

    # =========================================================================
    # Record Operations
    # =========================================================================

    def bitable_list_records(self, app_token: str, table_id: str,
                             page_size: int = 500,
                             filter_expr: str = None,
                             sort_expr: str = None,
                             field_names: List[str] = None) -> List[Dict[str, Any]]:
        """List all records in a table with automatic pagination.
        
        Uses SDK native transport.
        
        Args:
            app_token: The Bitable app token
            table_id: Table ID
            page_size: Page size (max 500)
            filter_expr: Optional filter expression
            sort_expr: Optional sort expression
            field_names: Optional list of field names to return
            
        Returns:
            List of record dicts with record_id and fields
        """
        records = []
        page_token = None
        retry_delay = API_RETRY_BASE_DELAY
        
        while True:
            self._rate_limit()
            
            req_builder = ListAppTableRecordRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .page_size(min(page_size, 500))
            if page_token:
                req_builder.page_token(page_token)
            if filter_expr:
                req_builder.filter(filter_expr)
            if sort_expr:
                req_builder.sort(sort_expr)
            if field_names:
                req_builder.field_names(json_module.dumps(field_names))
            
            request = req_builder.build()
            
            for attempt in range(API_MAX_RETRIES):
                response = self.client.bitable.v1.app_table_record.list(
                    request, self._get_request_option()
                )
                
                if response.success():
                    if response.data and response.data.items:
                        for r in response.data.items:
                            record_data = json_module.loads(lark.JSON.marshal(r))
                            records.append({
                                "record_id": record_data.get("record_id"),
                                "fields": record_data.get("fields", {}),
                            })
                    if response.data and response.data.has_more:
                        page_token = response.data.page_token
                    else:
                        page_token = None
                    break
                elif response.code == 99991400:  # Rate limit
                    if attempt < API_MAX_RETRIES - 1:
                        logger.warning(f"Rate limited, retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    logger.error(f"列出记录失败 (rate limited): {response.code} {response.msg}")
                    return records
                else:
                    logger.error(f"列出记录失败: {response.code} {response.msg}")
                    return records
            
            if not page_token:
                break
        
        return records

    def bitable_batch_create_records(self, app_token: str, table_id: str,
                                     records: List[Dict[str, Any]],
                                     batch_size: int = 500) -> List[str]:
        """Batch create records in a table.
        
        Args:
            app_token: The Bitable app token
            table_id: Table ID
            records: List of record field dicts ({"fields": {field_name: value}})
            batch_size: Batch size (max 1000, default 500)
            
        Returns:
            List of created record IDs
        """
        created_ids = []
        batch_size = min(batch_size, 1000)
        
        for i in range(0, len(records), batch_size):
            chunk = records[i:i + batch_size]
            
            record_objs = []
            for r in chunk:
                record_objs.append(
                    AppTableRecord.builder().fields(r.get("fields", r)).build()
                )
            
            self._rate_limit()
            request = BatchCreateAppTableRecordRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .request_body(
                    BatchCreateAppTableRecordRequestBody.builder()
                        .records(record_objs)
                        .build()
                ).build()
            
            retry_delay = API_RETRY_BASE_DELAY
            for attempt in range(API_MAX_RETRIES):
                response = self.client.bitable.v1.app_table_record.batch_create(
                    request, self._get_request_option()
                )
                
                if response.success():
                    if response.data and response.data.records:
                        for r in response.data.records:
                            created_ids.append(r.record_id)
                    logger.debug(f"批量创建 {len(chunk)} 条记录成功")
                    break
                elif response.code == 99991400:
                    if attempt < API_MAX_RETRIES - 1:
                        logger.warning(f"Rate limited, retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    logger.error(f"批量创建记录失败: {response.code} {response.msg}")
                else:
                    logger.error(f"批量创建记录失败: {response.code} {response.msg}")
                    break
            
            # Throttle between batches
            if i + batch_size < len(records):
                time.sleep(0.5)
        
        return created_ids

    def bitable_batch_update_records(self, app_token: str, table_id: str,
                                     records: List[Dict[str, Any]],
                                     batch_size: int = 500) -> bool:
        """Batch update records in a table.
        
        Args:
            app_token: The Bitable app token
            table_id: Table ID
            records: List of {"record_id": str, "fields": {field_name: value}}
            batch_size: Batch size (max 1000, default 500)
            
        Returns:
            True if all updates succeeded
        """
        success = True
        batch_size = min(batch_size, 1000)
        
        for i in range(0, len(records), batch_size):
            chunk = records[i:i + batch_size]
            
            record_objs = []
            for r in chunk:
                record_objs.append(
                    AppTableRecord.builder()
                        .record_id(r["record_id"])
                        .fields(r["fields"])
                        .build()
                )
            
            self._rate_limit()
            request = BatchUpdateAppTableRecordRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .request_body(
                    BatchUpdateAppTableRecordRequestBody.builder()
                        .records(record_objs)
                        .build()
                ).build()
            
            retry_delay = API_RETRY_BASE_DELAY
            for attempt in range(API_MAX_RETRIES):
                response = self.client.bitable.v1.app_table_record.batch_update(
                    request, self._get_request_option()
                )
                
                if response.success():
                    logger.debug(f"批量更新 {len(chunk)} 条记录成功")
                    break
                elif response.code == 99991400:
                    if attempt < API_MAX_RETRIES - 1:
                        logger.warning(f"Rate limited, retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    logger.error(f"批量更新记录失败: {response.code} {response.msg}")
                    success = False
                else:
                    logger.error(f"批量更新记录失败: {response.code} {response.msg}")
                    success = False
                    break
            
            if i + batch_size < len(records):
                time.sleep(0.5)
        
        return success

    def bitable_batch_delete_records(self, app_token: str, table_id: str,
                                     record_ids: List[str],
                                     batch_size: int = 500) -> bool:
        """Batch delete records from a table.
        
        Args:
            app_token: The Bitable app token
            table_id: Table ID
            record_ids: List of record IDs to delete
            batch_size: Batch size (max 1000, default 500)
            
        Returns:
            True if all deletes succeeded
        """
        success = True
        batch_size = min(batch_size, 1000)
        
        for i in range(0, len(record_ids), batch_size):
            chunk = record_ids[i:i + batch_size]
            
            self._rate_limit()
            request = BatchDeleteAppTableRecordRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .request_body(
                    BatchDeleteAppTableRecordRequestBody.builder()
                        .records(chunk)
                        .build()
                ).build()
            
            retry_delay = API_RETRY_BASE_DELAY
            for attempt in range(API_MAX_RETRIES):
                response = self.client.bitable.v1.app_table_record.batch_delete(
                    request, self._get_request_option()
                )
                
                if response.success():
                    logger.debug(f"批量删除 {len(chunk)} 条记录成功")
                    break
                elif response.code == 99991400:
                    if attempt < API_MAX_RETRIES - 1:
                        logger.warning(f"Rate limited, retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    logger.error(f"批量删除记录失败: {response.code} {response.msg}")
                    success = False
                else:
                    logger.error(f"批量删除记录失败: {response.code} {response.msg}")
                    success = False
                    break
            
            if i + batch_size < len(record_ids):
                time.sleep(0.5)
        
        return success

    def bitable_search_records(self, app_token: str, table_id: str,
                               filter_info: Dict = None,
                               sort: List[Dict] = None,
                               field_names: List[str] = None,
                               page_size: int = 500) -> List[Dict[str, Any]]:
        """Search records in a table with filter and sort.
        
        Args:
            app_token: The Bitable app token
            table_id: Table ID
            filter_info: Filter conditions
            sort: Sort conditions
            field_names: Fields to return
            page_size: Page size (max 500)
            
        Returns:
            List of matching record dicts
        """
        records = []
        page_token = None
        
        while True:
            self._rate_limit()
            body_builder = SearchAppTableRecordRequestBody.builder()
            if field_names:
                body_builder.field_names(field_names)
            if filter_info:
                body_builder.filter(filter_info)
            if sort:
                body_builder.sort(sort)
            
            req_builder = SearchAppTableRecordRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .page_size(min(page_size, 500)) \
                .request_body(body_builder.build())
            if page_token:
                req_builder.page_token(page_token)
            
            response = self.client.bitable.v1.app_table_record.search(
                req_builder.build(), self._get_request_option()
            )
            
            if response.success():
                if response.data and response.data.items:
                    for r in response.data.items:
                        records.append({
                            "record_id": r.record_id,
                            "fields": r.fields if r.fields else {},
                        })
                page_token = response.data.page_token if response.data else None
            else:
                logger.error(f"搜索记录失败: {response.code} {response.msg}")
                break
            
            if not page_token:
                break
        
        return records

    # =========================================================================
    # View Operations
    # =========================================================================

    def bitable_list_views(self, app_token: str, table_id: str) -> List[Dict[str, Any]]:
        """List all views of a table.
        
        Args:
            app_token: The Bitable app token
            table_id: Table ID
            
        Returns:
            List of view info dicts
        """
        views = []
        page_token = None
        
        while True:
            self._rate_limit()
            builder = ListAppTableViewRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .page_size(100)
            if page_token:
                builder.page_token(page_token)
            
            response = self.client.bitable.v1.app_table_view.list(
                builder.build(), self._get_request_option()
            )
            if not response.success():
                logger.error(f"列出视图失败: {response.code} {response.msg}")
                return views
            
            if response.data and response.data.items:
                for v in response.data.items:
                    views.append({
                        "view_id": v.view_id,
                        "view_name": v.view_name,
                        "view_type": v.view_type,
                    })
            
            page_token = response.data.page_token if response.data else None
            if not page_token:
                break
        
        return views
