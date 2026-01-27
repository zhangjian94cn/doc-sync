#!/usr/bin/env python3
import sys
import os

# Add src to path so doc_sync package can be found if not installed
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

try:
    from doc_sync.cli import main
except ImportError:
    # Fallback if src layout is not used or installed
    try:
        from doc_sync.cli import main
    except ImportError:
        print("Error: Could not import doc_sync.cli. Make sure 'src' directory is in PYTHONPATH.")
        sys.exit(1)

if __name__ == "__main__":
    main()
