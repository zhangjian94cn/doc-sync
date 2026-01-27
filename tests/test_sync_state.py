import os
import json
import pytest
from doc_sync.sync.state import SyncState

def test_sync_state_init(temp_vault):
    """Test SyncState initialization."""
    state = SyncState(temp_vault)
    assert state.root_path == os.path.abspath(temp_vault)
    assert state.data == {}
    assert state.token_map == {}
    
    # State file should not exist yet (only saves on update)
    # Actually, _load checks existence, but init doesn't force save unless update is called.
    # But wait, looking at code: __init__ calls _load. _load just reads.
    # So file is not created until save is called.
    assert not os.path.exists(state.state_path)

def test_sync_state_update_and_persistence(temp_vault):
    """Test updating state and persistence to disk."""
    state = SyncState(temp_vault)
    
    file_path = os.path.join(temp_vault, "notes", "test.md")
    token = "docx_token_123"
    
    # Create dummy file to allow getmtime to work (though SyncState handles non-existence with 0)
    with open(file_path, "w") as f:
        f.write("content")
        
    state.update(file_path, token)
    
    # Check in-memory
    assert state.get_by_token(token) is not None
    assert state.get_by_path(file_path) is not None
    assert state.get_by_path(file_path)["token"] == token
    
    # Check file on disk
    assert os.path.exists(state.state_path)
    with open(state.state_path, "r") as f:
        data = json.load(f)
        rel_path = "notes/test.md"
        assert rel_path in data
        assert data[rel_path]["token"] == token

    # Reload state
    new_state = SyncState(temp_vault)
    assert new_state.get_by_token(token) is not None
    assert new_state.get_by_path(file_path)["token"] == token

def test_sync_state_remove(temp_vault):
    """Test removing entries."""
    state = SyncState(temp_vault)
    path1 = os.path.join(temp_vault, "p1.md")
    token1 = "t1"
    path2 = os.path.join(temp_vault, "p2.md")
    token2 = "t2"
    
    state.update(path1, token1)
    state.update(path2, token2)
    
    # Remove by path
    state.remove(path1)
    assert state.get_by_path(path1) is None
    assert state.get_by_token(token1) is None
    # path2 should still be there
    assert state.get_by_path(path2) is not None
    
    # Remove by token
    state.remove_by_token(token2)
    assert state.get_by_path(path2) is None
    assert state.get_by_token(token2) is None

def test_sync_state_relative_paths(temp_vault):
    """Test that paths are stored relatively."""
    state = SyncState(temp_vault)
    abs_path = os.path.join(temp_vault, "folder", "doc.md")
    token = "token_abc"
    
    state.update(abs_path, token)
    
    with open(state.state_path, "r") as f:
        raw_data = json.load(f)
        
    # Key should be "folder/doc.md" (or with backslash on Windows, but os.path.relpath handles it)
    # We just check that absolute path is NOT in keys
    assert abs_path not in raw_data
    # Check for relative path end
    found = False
    for k in raw_data.keys():
        if k.endswith("doc.md"):
            found = True
            break
    assert found
