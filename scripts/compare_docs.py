#!/usr/bin/env python3
"""
Document Comparison & Verification Tool

同步后验证本地 Markdown 与飞书云文档是否一致。

使用方式:
    # 单文件对比
    python scripts/compare_docs.py <local_file> <doc_token>
    
    # 批量验证（从配置文件读取）
    python scripts/compare_docs.py --config sync_config.json
    
    # 显示详细差异
    python scripts/compare_docs.py <local_file> <doc_token> --diff
    
    # JSON 格式输出（便于自动化）
    python scripts/compare_docs.py <local_file> <doc_token> --json
"""

import sys
import os
import json
import argparse
import difflib
from typing import Optional, List, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.feishu_client import FeishuClient
from src.converter import MarkdownToFeishu, FeishuToMarkdown
from src.config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_USER_ACCESS_TOKEN
from src.logger import logger


# ANSI colors
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def get_block_summary(block: dict) -> str:
    """Get a summary string for a block."""
    bt = block.get('block_type')
    
    type_names = {
        1: 'PAGE', 2: 'TEXT', 3: 'H1', 4: 'H2', 5: 'H3', 6: 'H4',
        7: 'H5', 8: 'H6', 9: 'H7', 10: 'H8', 11: 'H9',
        12: 'BULLET', 13: 'ORDERED', 14: 'CODE', 15: 'QUOTE',
        17: 'TODO', 22: 'DIVIDER', 27: 'IMAGE', 31: 'TABLE'
    }
    type_name = type_names.get(bt, f'TYPE_{bt}')
    
    # Get content for text-like blocks
    content = ""
    field_mapping = {
        2: 'text', 3: 'heading1', 4: 'heading2', 5: 'heading3',
        6: 'heading4', 7: 'heading5', 8: 'heading6', 9: 'heading7',
        10: 'heading8', 11: 'heading9', 12: 'bullet', 13: 'ordered',
        14: 'code', 15: 'quote', 17: 'todo'
    }
    
    field = field_mapping.get(bt)
    if field and field in block:
        elements = block[field].get('elements', [])
        for el in elements:
            if 'text_run' in el:
                content += el['text_run'].get('content', '')
    
    # Determine if it's a blank line
    if bt == 2 and (not content.strip() or content == '\n'):
        return "[BLANK]"
    
    # Truncate content
    content = content.replace('\n', '\\n')[:30]
    if content:
        return f"{type_name}: {content}"
    return type_name


class DictObj:
    """Helper to convert dict to object with attribute access."""
    def __init__(self, d):
        self._d = d
    
    def __getattr__(self, name):
        if name not in self._d:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        val = self._d[name]
        if isinstance(val, dict):
            return DictObj(val)
        if isinstance(val, list):
            return [DictObj(x) if isinstance(x, dict) else x for x in val]
        return val


def normalize_markdown(content: str) -> List[str]:
    """Normalize markdown content for comparison.
    
    - Strip trailing whitespace from each line
    - Normalize multiple consecutive blank lines to single blank line
    - Strip leading/trailing blank lines
    """
    lines = content.split('\n')
    # Strip trailing whitespace
    lines = [line.rstrip() for line in lines]
    
    # Normalize consecutive blank lines
    normalized = []
    prev_blank = False
    for line in lines:
        is_blank = not line.strip()
        if is_blank:
            if not prev_blank:
                normalized.append('')
            prev_blank = True
        else:
            normalized.append(line)
            prev_blank = False
    
    # Strip leading/trailing blank lines
    while normalized and not normalized[0].strip():
        normalized.pop(0)
    while normalized and not normalized[-1].strip():
        normalized.pop()
    
    return normalized


def compare_documents(
    local_path: str, 
    doc_token: str, 
    show_diff: bool = False,
    output_json: bool = False,
    verbose: bool = True
) -> Dict[str, Any]:
    """Compare a local Markdown file with its cloud Feishu document.
    
    Args:
        local_path: Path to the local Markdown file
        doc_token: Feishu document token
        show_diff: Show detailed line-by-line diff
        output_json: Return JSON-compatible result
        verbose: Print detailed comparison
        
    Returns:
        dict with comparison results
    """
    # Create client
    client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, "")
    if FEISHU_USER_ACCESS_TOKEN:
        client.user_access_token = FEISHU_USER_ACCESS_TOKEN
    
    # Read local file
    if not os.path.exists(local_path):
        error = f"Local file not found: {local_path}"
        if output_json:
            return {"success": False, "error": error}
        print(f"❌ {error}")
        return None
        
    with open(local_path, 'r', encoding='utf-8') as f:
        local_content = f.read()
    
    # Convert local to blocks for structure comparison
    converter_to_feishu = MarkdownToFeishu()
    local_blocks = converter_to_feishu.parse(local_content)
    
    # Get cloud blocks
    cloud_blocks = client.get_block_children(doc_token, doc_token)
    
    if not cloud_blocks:
        error = "Failed to get cloud document blocks"
        if output_json:
            return {"success": False, "error": error}
        print(f"❌ {error}")
        return None
    
    # Convert cloud blocks to Markdown for content comparison
    converter_to_md = FeishuToMarkdown()
    # Convert dicts to objects for the converter
    cloud_blocks_objs = [DictObj(b) for b in cloud_blocks]
    cloud_content = converter_to_md.convert(cloud_blocks_objs)
    
    # Normalize both for fair comparison
    local_lines = normalize_markdown(local_content)
    cloud_lines = normalize_markdown(cloud_content)
    
    # Count blank lines in blocks
    local_blank_count = sum(1 for b in local_blocks if get_block_summary(b) == "[BLANK]")
    cloud_blank_count = sum(1 for b in cloud_blocks if get_block_summary(b) == "[BLANK]")
    
    # Compute diff
    diff = list(difflib.unified_diff(
        local_lines, cloud_lines,
        fromfile='Local', tofile='Cloud',
        lineterm=''
    ))
    
    # Check if content matches
    content_match = local_lines == cloud_lines
    block_count_match = len(local_blocks) == len(cloud_blocks)
    
    result = {
        'success': True,
        'local_path': local_path,
        'doc_token': doc_token,
        'local_block_count': len(local_blocks),
        'cloud_block_count': len(cloud_blocks),
        'local_blank_lines': local_blank_count,
        'cloud_blank_lines': cloud_blank_count,
        'local_line_count': len(local_lines),
        'cloud_line_count': len(cloud_lines),
        'block_count_match': block_count_match,
        'content_match': content_match,
        'diff_lines': len([d for d in diff if d.startswith('+') or d.startswith('-')]) - 2 if diff else 0
    }
    
    if output_json:
        return result
    
    if verbose:
        filename = os.path.basename(local_path)
        print()
        print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}")
        print(f"📄 {Colors.CYAN}{filename}{Colors.RESET}")
        print(f"☁️  {doc_token}")
        print(f"{'=' * 60}")
        
        print(f"\n{Colors.BOLD}📊 结构对比:{Colors.RESET}")
        print(f"   本地 blocks: {len(local_blocks):>4} (空行: {local_blank_count})")
        print(f"   云端 blocks: {len(cloud_blocks):>4} (空行: {cloud_blank_count})")
        
        if block_count_match:
            print(f"   {Colors.GREEN}✓ Block 数量一致{Colors.RESET}")
        else:
            diff_count = abs(len(local_blocks) - len(cloud_blocks))
            print(f"   {Colors.YELLOW}⚠ Block 数量差异: {diff_count}{Colors.RESET}")
        
        print(f"\n{Colors.BOLD}📝 内容对比:{Colors.RESET}")
        print(f"   本地行数: {len(local_lines):>4}")
        print(f"   云端行数: {len(cloud_lines):>4}")
        
        if content_match:
            print(f"   {Colors.GREEN}✓ 内容完全一致!{Colors.RESET}")
        else:
            print(f"   {Colors.RED}✗ 内容存在差异 ({result['diff_lines']} 行){Colors.RESET}")
            
            if show_diff and diff:
                print(f"\n{Colors.BOLD}📋 详细差异:{Colors.RESET}")
                print("-" * 60)
                for line in diff[:50]:  # Limit to 50 lines
                    if line.startswith('+++') or line.startswith('---'):
                        print(f"{Colors.BOLD}{line}{Colors.RESET}")
                    elif line.startswith('+'):
                        print(f"{Colors.GREEN}{line}{Colors.RESET}")
                    elif line.startswith('-'):
                        print(f"{Colors.RED}{line}{Colors.RESET}")
                    elif line.startswith('@@'):
                        print(f"{Colors.CYAN}{line}{Colors.RESET}")
                    else:
                        print(line)
                if len(diff) > 50:
                    print(f"... 还有 {len(diff) - 50} 行差异")
        
        # Block structure comparison (first 15)
        if not block_count_match or not content_match:
            print(f"\n{Colors.BOLD}🔍 Block 结构对比 (前 15 个):{Colors.RESET}")
            print(f"{'#':<3} {'本地':<28} {'云端':<28}")
            print("-" * 60)
            
            max_blocks = max(len(local_blocks), len(cloud_blocks))
            for i in range(min(max_blocks, 15)):
                local_sum = get_block_summary(local_blocks[i]) if i < len(local_blocks) else "(缺失)"
                cloud_sum = get_block_summary(cloud_blocks[i]) if i < len(cloud_blocks) else "(缺失)"
                
                if local_sum == cloud_sum:
                    marker = f"{Colors.GREEN}✓{Colors.RESET}"
                else:
                    marker = f"{Colors.RED}✗{Colors.RESET}"
                print(f"{i:<3} {local_sum:<28} {cloud_sum:<28} {marker}")
            
            if max_blocks > 15:
                print(f"... 还有 {max_blocks - 15} 个 blocks")
        
        print()
    
    return result


def load_config(config_path: str) -> list:
    """Load sync tasks from configuration file."""
    if not os.path.exists(config_path):
        return []
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data.get("tasks", [])
            elif isinstance(data, list):
                return data
            return []
    except (json.JSONDecodeError, IOError) as e:
        print(f"❌ 读取配置文件失败: {e}")
        return []


def batch_compare(config_path: str, show_diff: bool = False, output_json: bool = False) -> List[Dict]:
    """Compare all tasks from config file."""
    tasks = load_config(config_path)
    if not tasks:
        print(f"❌ 未找到任务配置: {config_path}")
        return []
    
    results = []
    success_count = 0
    fail_count = 0
    
    if not output_json:
        print(f"\n🔄 正在批量验证 {len(tasks)} 个任务...")
    
    for task in tasks:
        if not task.get("enabled", True):
            continue
            
        local_path = task.get("local")
        cloud_token = task.get("cloud")
        
        if not local_path or not cloud_token:
            continue
        
        # Handle folder tasks - skip for now (could expand later)
        if os.path.isdir(local_path):
            if not output_json:
                print(f"\n⏭️  跳过文件夹: {local_path} (暂不支持文件夹对比)")
            continue
        
        result = compare_documents(
            local_path, cloud_token,
            show_diff=show_diff,
            output_json=output_json,
            verbose=not output_json
        )
        
        if result:
            results.append(result)
            if result.get('content_match'):
                success_count += 1
            else:
                fail_count += 1
    
    if not output_json:
        print("\n" + "=" * 60)
        print(f"{Colors.BOLD}📊 批量验证汇总{Colors.RESET}")
        print("=" * 60)
        print(f"   总任务数: {len(results)}")
        print(f"   {Colors.GREEN}✓ 一致: {success_count}{Colors.RESET}")
        if fail_count > 0:
            print(f"   {Colors.RED}✗ 差异: {fail_count}{Colors.RESET}")
        print()
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description='对比本地 Markdown 与飞书云文档的一致性',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单文件对比
  %(prog)s /path/to/note.md Fu6bdHpmNoQo1nxwT0zcfxbhnPe
  
  # 显示详细差异
  %(prog)s /path/to/note.md Fu6bdHpmNoQo1nxwT0zcfxbhnPe --diff
  
  # 批量验证（从配置读取）
  %(prog)s --config sync_config.json
  
  # JSON 格式输出
  %(prog)s /path/to/note.md Fu6bdHpmNoQo1nxwT0zcfxbhnPe --json
        """
    )
    
    parser.add_argument('local_file', nargs='?', help='本地 Markdown 文件路径')
    parser.add_argument('doc_token', nargs='?', help='飞书文档 Token')
    parser.add_argument('--config', '-c', help='从配置文件批量验证')
    parser.add_argument('--diff', '-d', action='store_true', help='显示详细行级别差异')
    parser.add_argument('--json', '-j', action='store_true', dest='output_json', help='JSON 格式输出')
    parser.add_argument('--quiet', '-q', action='store_true', help='静默模式，只显示摘要')
    
    args = parser.parse_args()
    
    # Batch mode
    if args.config:
        results = batch_compare(args.config, show_diff=args.diff, output_json=args.output_json)
        if args.output_json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        
        # Exit code: 1 if any mismatch
        if any(not r.get('content_match') for r in results):
            sys.exit(1)
        return
    
    # Single file mode
    if not args.local_file or not args.doc_token:
        parser.print_help()
        print("\n❌ 请提供本地文件路径和云端文档 Token，或使用 --config 批量验证")
        sys.exit(1)
    
    result = compare_documents(
        args.local_file, 
        args.doc_token, 
        show_diff=args.diff,
        output_json=args.output_json,
        verbose=not args.quiet and not args.output_json
    )
    
    if args.output_json and result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    if result and not result.get('content_match'):
        sys.exit(1)


if __name__ == '__main__':
    main()
