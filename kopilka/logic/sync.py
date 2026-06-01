"""Sync with pCloud and conflict detection."""

import os
from pathlib import Path
from datetime import datetime


class SyncManager:
    """Handle pCloud sync and conflict detection."""
    
    @staticmethod
    def check_for_conflicts(file_path: str) -> bool:
        """Check if file has been modified on disk."""
        if not os.path.exists(file_path):
            return False
        
        # Check for conflict files created by pCloud
        parent = Path(file_path).parent
        filename = Path(file_path).stem
        ext = Path(file_path).suffix
        
        for item in parent.glob(f"{filename}*conflict*{ext}"):
            return True
        
        return False
    
    @staticmethod
    def get_file_mtime(file_path: str) -> float:
        """Get file modification time."""
        if not os.path.exists(file_path):
            return 0
        
        return os.path.getmtime(file_path)
    
    @staticmethod
    def update_metadata(budget, user: str):
        """Update budget metadata (last_modified, last_modified_by)."""
        budget.last_modified = datetime.now().isoformat()
        budget.last_modified_by = user
        return budget
    
    @staticmethod
    def handle_conflict(file_path: str, user: str):
        """
        Handle conflict by showing user options.
        
        Returns: "keep_local", "reload_disk", or "merge"
        """
        # TODO: Show GTK dialog with options
        return "keep_local"
