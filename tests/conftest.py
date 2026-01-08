"""
Pytest configuration and shared fixtures.
"""

import os
import sys
import tempfile
import shutil
from typing import Generator, Dict, Any

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def temp_vault() -> Generator[str, None, None]:
    """Create a temporary Obsidian vault for testing."""
    vault_dir = tempfile.mkdtemp(prefix="test_vault_")
    
    # Create .obsidian folder to make it a valid vault
    os.makedirs(os.path.join(vault_dir, ".obsidian"))
    
    # Create some test directories
    os.makedirs(os.path.join(vault_dir, "assets"))
    os.makedirs(os.path.join(vault_dir, "notes"))
    
    yield vault_dir
    
    # Cleanup
    shutil.rmtree(vault_dir, ignore_errors=True)


@pytest.fixture
def sample_markdown() -> str:
    """Provide sample markdown content for testing."""
    return """# Test Document

## Introduction

This is a **bold** and *italic* text with `inline code`.

### Features

- Item 1
- Item 2
  - Nested item
- Item 3

1. First
2. Second
3. Third

```python
def hello():
    print("Hello, World!")
```

![Test Image](test.png)
"""


@pytest.fixture
def sample_markdown_with_image(temp_vault: str) -> Dict[str, Any]:
    """Create markdown with actual image file."""
    # Create a dummy image file
    image_path = os.path.join(temp_vault, "assets", "test.png")
    with open(image_path, "wb") as f:
        # Write minimal PNG (1x1 pixel transparent)
        f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
                b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
                b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
                b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
    
    md_content = """# Document with Image

![Test Image](assets/test.png)

Some text after image.
"""
    
    md_path = os.path.join(temp_vault, "notes", "test.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    
    return {
        "vault": temp_vault,
        "md_path": md_path,
        "md_content": md_content,
        "image_path": image_path
    }
