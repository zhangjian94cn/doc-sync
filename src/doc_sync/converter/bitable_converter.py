"""
Bitable Data Converter Module

Provides bidirectional conversion between local data formats (CSV, JSON, Markdown tables)
and Feishu Bitable records.

Usage:
    from doc_sync.converter.bitable_converter import BitableConverter
    
    fields, records = BitableConverter.csv_to_records("data.csv")
    BitableConverter.records_to_csv(records, fields, "output.csv")
"""

import csv
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from doc_sync.logger import logger


# Bitable field type constants (mirror from feishu/bitable.py)
FIELD_TYPE_TEXT = 1
FIELD_TYPE_NUMBER = 2
FIELD_TYPE_SELECT = 3
FIELD_TYPE_MULTI_SELECT = 4
FIELD_TYPE_DATE = 5
FIELD_TYPE_CHECKBOX = 7
FIELD_TYPE_URL = 15


class BitableConverter:
    """Converter between local data formats and Bitable record format.
    
    All methods are static for easy use without instantiation.
    """

    # =========================================================================
    # Local → Records
    # =========================================================================

    @staticmethod
    def csv_to_records(csv_path: str, encoding: str = "utf-8") -> Tuple[List[Dict], List[Dict]]:
        """Convert a CSV file to Bitable fields and records.
        
        Args:
            csv_path: Path to the CSV file
            encoding: File encoding (default: utf-8)
            
        Returns:
            Tuple of (fields, records):
                fields: List of {"field_name": str, "type": int}
                records: List of {"fields": {field_name: value}}
        """
        if not os.path.exists(csv_path):
            logger.error(f"CSV 文件不存在: {csv_path}")
            return [], []
        
        with open(csv_path, "r", encoding=encoding, newline="") as f:
            # Detect delimiter
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel
            
            reader = csv.DictReader(f, dialect=dialect)
            if not reader.fieldnames:
                logger.error("CSV 文件没有表头")
                return [], []
            
            # Collect all rows first for type inference
            rows = list(reader)
        
        # Build field definitions with type inference
        fields = []
        for name in reader.fieldnames:
            values = [row.get(name, "") for row in rows]
            field_type = BitableConverter.infer_field_type(values)
            fields.append({
                "field_name": name,
                "type": field_type,
            })
        
        # Build records with type-aware value conversion
        records = []
        for row in rows:
            field_values = {}
            for field_def in fields:
                name = field_def["field_name"]
                raw_val = row.get(name, "")
                field_values[name] = BitableConverter._convert_value(
                    raw_val, field_def["type"]
                )
            records.append({"fields": field_values})
        
        logger.info(f"CSV 转换完成: {len(fields)} 个字段, {len(records)} 条记录")
        return fields, records

    @staticmethod
    def json_to_records(json_path: str) -> Tuple[List[Dict], List[Dict]]:
        """Convert a JSON file to Bitable fields and records.
        
        Supports two JSON formats:
        1. Array of objects: [{"name": "A", "age": 1}, ...]
        2. Object with "fields" and "records" keys (pre-formatted)
        
        Args:
            json_path: Path to the JSON file
            
        Returns:
            Tuple of (fields, records)
        """
        if not os.path.exists(json_path):
            logger.error(f"JSON 文件不存在: {json_path}")
            return [], []
        
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            # Pre-formatted: {"fields": [...], "records": [...]}
            if "fields" in data and "records" in data:
                return data["fields"], data["records"]
            # Single object → wrap in list
            data = [data]
        
        if not isinstance(data, list) or len(data) == 0:
            logger.error("JSON 格式不支持: 需要对象数组或 {fields, records} 格式")
            return [], []
        
        # Array of objects
        all_keys = []
        seen = set()
        for obj in data:
            if isinstance(obj, dict):
                for k in obj.keys():
                    if k not in seen:
                        all_keys.append(k)
                        seen.add(k)
        
        fields = []
        for key in all_keys:
            values = [str(obj.get(key, "")) for obj in data if isinstance(obj, dict)]
            field_type = BitableConverter.infer_field_type(values)
            fields.append({"field_name": key, "type": field_type})
        
        records = []
        for obj in data:
            if isinstance(obj, dict):
                field_values = {}
                for field_def in fields:
                    name = field_def["field_name"]
                    raw_val = obj.get(name, "")
                    if isinstance(raw_val, (int, float)):
                        field_values[name] = raw_val
                    elif isinstance(raw_val, bool):
                        field_values[name] = raw_val
                    else:
                        field_values[name] = BitableConverter._convert_value(
                            str(raw_val), field_def["type"]
                        )
                records.append({"fields": field_values})
        
        logger.info(f"JSON 转换完成: {len(fields)} 个字段, {len(records)} 条记录")
        return fields, records

    @staticmethod
    def markdown_table_to_records(md_content: str) -> Tuple[List[Dict], List[Dict]]:
        """Parse a Markdown table string into Bitable fields and records.
        
        Args:
            md_content: Markdown content containing a table
            
        Returns:
            Tuple of (fields, records)
        """
        lines = md_content.strip().split("\n")
        
        # Find table lines (lines containing |)
        table_lines = [l for l in lines if "|" in l]
        if len(table_lines) < 3:
            logger.error("未找到有效的 Markdown 表格 (至少需要表头+分隔+1行数据)")
            return [], []
        
        # Parse header
        header_line = table_lines[0]
        headers = [h.strip() for h in header_line.split("|")]
        headers = [h for h in headers if h]
        
        # Skip separator line (contains ---)
        separator_idx = 1
        if not re.match(r"^\|?\s*[-:]+", table_lines[separator_idx]):
            logger.error("Markdown 表格缺少分隔行")
            return [], []
        
        # Parse data rows
        data_rows = []
        for line in table_lines[separator_idx + 1:]:
            cells = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c or cells.index(c) not in (0, len(cells)-1)]
            # Remove empty strings from split edges
            if cells and cells[0] == "":
                cells = cells[1:]
            if cells and cells[-1] == "":
                cells = cells[:-1]
            if cells:
                data_rows.append(cells)
        
        if not data_rows:
            logger.warning("Markdown 表格没有数据行")
            return [{"field_name": h, "type": FIELD_TYPE_TEXT} for h in headers], []
        
        # Infer field types
        fields = []
        for i, header in enumerate(headers):
            values = [row[i] if i < len(row) else "" for row in data_rows]
            field_type = BitableConverter.infer_field_type(values)
            fields.append({"field_name": header, "type": field_type})
        
        # Build records
        records = []
        for row in data_rows:
            field_values = {}
            for i, field_def in enumerate(fields):
                val = row[i] if i < len(row) else ""
                field_values[field_def["field_name"]] = BitableConverter._convert_value(
                    val, field_def["type"]
                )
            records.append({"fields": field_values})
        
        logger.info(f"Markdown 表格转换完成: {len(fields)} 个字段, {len(records)} 条记录")
        return fields, records

    # =========================================================================
    # Records → Local
    # =========================================================================

    @staticmethod
    def records_to_csv(records: List[Dict], fields: List[Dict],
                       output_path: str, encoding: str = "utf-8") -> bool:
        """Export Bitable records to a CSV file.
        
        Args:
            records: List of {"fields": {field_name: value}} or {"record_id": str, "fields": {...}}
            fields: List of {"field_name": str, ...}
            output_path: Output CSV file path
            encoding: File encoding (default: utf-8)
            
        Returns:
            True if successful
        """
        try:
            field_names = [f["field_name"] for f in fields]
            
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            
            with open(output_path, "w", encoding=encoding, newline="") as f:
                writer = csv.DictWriter(f, fieldnames=field_names)
                writer.writeheader()
                
                for record in records:
                    row_fields = record.get("fields", record)
                    row = {}
                    for name in field_names:
                        val = row_fields.get(name, "")
                        # Handle complex Bitable field values
                        row[name] = BitableConverter._flatten_value(val)
                    writer.writerow(row)
            
            logger.info(f"CSV 导出完成: {output_path} ({len(records)} 条记录)")
            return True
        except Exception as e:
            logger.error(f"CSV 导出失败: {e}")
            return False

    @staticmethod
    def records_to_json(records: List[Dict], fields: List[Dict],
                        output_path: str) -> bool:
        """Export Bitable records to a JSON file.
        
        Args:
            records: List of record dicts
            fields: List of field definition dicts
            output_path: Output JSON file path
            
        Returns:
            True if successful
        """
        try:
            field_names = [f["field_name"] for f in fields]
            
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            
            output_data = []
            for record in records:
                row_fields = record.get("fields", record)
                row = {}
                for name in field_names:
                    val = row_fields.get(name, "")
                    row[name] = BitableConverter._flatten_value(val)
                output_data.append(row)
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"JSON 导出完成: {output_path} ({len(records)} 条记录)")
            return True
        except Exception as e:
            logger.error(f"JSON 导出失败: {e}")
            return False

    # =========================================================================
    # Utility Methods
    # =========================================================================

    @staticmethod
    def infer_field_type(values: List[str]) -> int:
        """Infer the Bitable field type from sample values.
        
        Args:
            values: List of string values to analyze
            
        Returns:
            Bitable field type constant
        """
        if not values:
            return FIELD_TYPE_TEXT
        
        # Filter out empty values
        non_empty = [v for v in values if v and str(v).strip()]
        if not non_empty:
            return FIELD_TYPE_TEXT
        
        # Check if all values are boolean-like
        bool_patterns = {"true", "false", "yes", "no", "是", "否", "1", "0", "✓", "✗", "☑", "☐"}
        if all(str(v).strip().lower() in bool_patterns for v in non_empty):
            return FIELD_TYPE_CHECKBOX
        
        # Check if all values are numbers
        num_count = 0
        for v in non_empty:
            try:
                float(str(v).replace(",", "").replace("￥", "").replace("$", "").strip())
                num_count += 1
            except ValueError:
                pass
        if num_count == len(non_empty):
            return FIELD_TYPE_NUMBER
        
        # Check if all values look like URLs
        url_pattern = re.compile(r'^https?://', re.IGNORECASE)
        if all(url_pattern.match(str(v).strip()) for v in non_empty):
            return FIELD_TYPE_URL
        
        # Check if all values look like dates
        date_patterns = [
            r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}',  # 2024-01-01 or 2024/01/01
            r'^\d{1,2}[-/]\d{1,2}[-/]\d{4}',    # 01-01-2024
        ]
        is_date = True
        for v in non_empty:
            if not any(re.match(p, str(v).strip()) for p in date_patterns):
                is_date = False
                break
        if is_date:
            return FIELD_TYPE_DATE
        
        # Default to text
        return FIELD_TYPE_TEXT

    @staticmethod
    def _convert_value(raw_val: str, field_type: int) -> Any:
        """Convert a raw string value to the appropriate type for Bitable.
        
        Args:
            raw_val: Raw string value
            field_type: Target Bitable field type
            
        Returns:
            Converted value
        """
        if raw_val is None or raw_val == "":
            return raw_val
        
        raw_str = str(raw_val).strip()
        
        if field_type == FIELD_TYPE_NUMBER:
            try:
                cleaned = raw_str.replace(",", "").replace("￥", "").replace("$", "")
                if "." in cleaned:
                    return float(cleaned)
                return int(cleaned)
            except ValueError:
                return raw_str
        
        elif field_type == FIELD_TYPE_CHECKBOX:
            return raw_str.lower() in {"true", "yes", "是", "1", "✓", "☑"}
        
        elif field_type == FIELD_TYPE_URL:
            return {"link": raw_str, "text": raw_str}
        
        elif field_type == FIELD_TYPE_DATE:
            # Bitable expects timestamps in milliseconds
            from datetime import datetime
            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"]:
                try:
                    dt = datetime.strptime(raw_str, fmt)
                    return int(dt.timestamp() * 1000)
                except ValueError:
                    continue
            return raw_str
        
        # Text and others: return as-is
        return raw_str

    @staticmethod
    def _flatten_value(val: Any) -> str:
        """Flatten a Bitable field value to a string for CSV/JSON export.
        
        Handles complex types like person, attachment, multi-select, etc.
        
        Args:
            val: Bitable field value (may be str, int, float, list, dict)
            
        Returns:
            String representation
        """
        if val is None:
            return ""
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, bool):
            return "true" if val else "false"
        if isinstance(val, str):
            return val
        if isinstance(val, list):
            # Multi-select or person list
            parts = []
            for item in val:
                if isinstance(item, dict):
                    parts.append(item.get("text", item.get("name", str(item))))
                else:
                    parts.append(str(item))
            return ", ".join(parts)
        if isinstance(val, dict):
            # URL type: {"link": ..., "text": ...}
            if "link" in val:
                return val.get("link", "")
            if "text" in val:
                return val.get("text", "")
            return json.dumps(val, ensure_ascii=False)
        return str(val)

    @staticmethod
    def detect_format(file_path: str) -> Optional[str]:
        """Detect the format of a data file.
        
        Args:
            file_path: Path to the data file
            
        Returns:
            Format string: 'csv', 'json', 'markdown', or None
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".csv", ".tsv"):
            return "csv"
        elif ext in (".json", ".jsonl"):
            return "json"
        elif ext in (".md", ".markdown"):
            return "markdown"
        return None
