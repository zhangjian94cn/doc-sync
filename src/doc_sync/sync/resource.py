"""
Resource Index Module
Provides efficient resource lookup by caching file locations.
"""

import os
from typing import Dict, Optional, Set
from doc_sync.logger import logger


class ResourceIndex:
    """
    Caches resource file locations for efficient lookup.
    
    Instead of recursively scanning the vault for each resource reference,
    this class builds an index once and provides O(1) lookups.
    """
    
    def __init__(self, vault_root: str, extensions: Optional[Set[str]] = None):
        """
        Initialize and build the resource index.
        
        Args:
            vault_root: Root directory of the Obsidian vault
            extensions: Optional set of file extensions to index (e.g., {'png', 'jpg'}).
                       If None, indexes all files.
        """
        self.vault_root = os.path.abspath(vault_root)
        self.extensions = extensions
        self._index: Dict[str, str] = {}
        self._build_index()
    
    def _should_index(self, filename: str) -> bool:
        """Check if a file should be indexed based on extension."""
        if self.extensions is None:
            return True
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        return ext in self.extensions
    
    def _build_index(self) -> None:
        """Build the filename -> path index."""
        indexed_count = 0
        
        for dirpath, dirnames, filenames in os.walk(self.vault_root):
            # Skip hidden directories and common non-asset directories
            dirnames[:] = [d for d in dirnames if not d.startswith('.') and d not in {'node_modules', '__pycache__', 'venv'}]
            
            for filename in filenames:
                if not self._should_index(filename):
                    continue
                    
                # Only index the first occurrence (mimics Obsidian's "shortest path" behavior)
                if filename not in self._index:
                    self._index[filename] = os.path.join(dirpath, filename)
                    indexed_count += 1
        
        logger.debug(f"资源索引构建完成: {indexed_count} 个文件")
    
    def find(self, path: str) -> Optional[str]:
        """
        Find the full path of a resource.
        
        Args:
            path: Resource reference (can be filename only or relative path)
            
        Returns:
            Full absolute path if found, None otherwise
        """
        # Try exact path first (if it's an absolute path)
        if os.path.isabs(path) and os.path.exists(path):
            return path
        
        # Try relative to vault root
        relative_path = os.path.join(self.vault_root, path)
        if os.path.exists(relative_path):
            return relative_path
        
        # Look up by filename in index
        filename = os.path.basename(path)
        result = self._index.get(filename)
        if result:
            return result
        
        # Fallback: Try with .md suffix for Obsidian Excalidraw plugin
        # The plugin stores files as .excalidraw.md but links as .excalidraw
        if filename.endswith('.excalidraw'):
            md_filename = filename + '.md'
            result = self._index.get(md_filename)
            if result:
                return result
        
        return None
    
    def refresh(self) -> None:
        """Rebuild the index (call after adding/removing files)."""
        self._index.clear()
        self._build_index()
    
    def __len__(self) -> int:
        """Return the number of indexed files."""
        return len(self._index)
    
    def __contains__(self, filename: str) -> bool:
        """Check if a filename is in the index."""
        return filename in self._index
