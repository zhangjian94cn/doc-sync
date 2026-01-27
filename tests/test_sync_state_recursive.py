
import os
import json
import tempfile
import shutil
import pytest
from doc_sync.sync.state import SyncState

@pytest.fixture
def temp_vault():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

def test_remove_directory_recursive(temp_vault):
    """Test recursive removal of state records for a directory."""
    state = SyncState(temp_vault)
    
    # Setup initial state with a hierarchy
    # root/
    #   folder1/
    #     file1.md (token1)
    #     subfolder/
    #       file2.md (token2)
    #   file3.md (token3)
    
    folder1 = os.path.join(temp_vault, "folder1")
    file1 = os.path.join(folder1, "file1.md")
    subfolder = os.path.join(folder1, "subfolder")
    file2 = os.path.join(subfolder, "file2.md")
    file3 = os.path.join(temp_vault, "file3.md")
    
    # Mock file existence (SyncState checks mtime)
    os.makedirs(subfolder, exist_ok=True)
    with open(file1, 'w') as f: f.write("test")
    with open(file2, 'w') as f: f.write("test")
    with open(file3, 'w') as f: f.write("test")
    
    # Update state
    state.update(folder1, "token_folder1", type="folder")
    state.update(file1, "token1")
    state.update(subfolder, "token_subfolder", type="folder")
    state.update(file2, "token2")
    state.update(file3, "token3")
    
    # Verify initial state
    assert state.get_by_token("token1") is not None
    assert state.get_by_token("token2") is not None
    assert state.get_by_token("token3") is not None
    assert state.get_by_token("token_folder1") is not None
    
    # Action: Remove folder1 recursively
    state.remove_directory(folder1)
    
    # Verify removal
    # Should be gone
    assert state.get_by_token("token_folder1") is None
    assert state.get_by_token("token1") is None
    assert state.get_by_token("token_subfolder") is None
    assert state.get_by_token("token2") is None
    
    # Should remain
    assert state.get_by_token("token3") is not None
    
    # Verify token_map cleanup
    assert "token1" not in state.token_map
    assert "token2" not in state.token_map
    assert "token3" in state.token_map

def test_remove_directory_exact_match_only(temp_vault):
    """Test that removing 'folder' does not remove 'folder_sibling'."""
    state = SyncState(temp_vault)
    
    folder = os.path.join(temp_vault, "folder")
    folder_sibling = os.path.join(temp_vault, "folder_sibling")
    
    os.makedirs(folder, exist_ok=True)
    os.makedirs(folder_sibling, exist_ok=True)
    
    state.update(folder, "token_folder", type="folder")
    state.update(folder_sibling, "token_sibling", type="folder")
    
    # Action: Remove 'folder'
    state.remove_directory(folder)
    
    # Verify
    assert state.get_by_token("token_folder") is None
    assert state.get_by_token("token_sibling") is not None
