"""Sync with pCloud and conflict detection."""

import json
import os
from pathlib import Path
from datetime import datetime


class SyncManager:
    """Handle pCloud conflict detection and external-modification checks."""

    @staticmethod
    def conflict_files(file_path: str) -> list[Path]:
        """Return any pCloud conflict copies in the same directory."""
        if not os.path.exists(file_path):
            return []
        parent = Path(file_path).parent
        stem = Path(file_path).stem
        ext = Path(file_path).suffix
        # pCloud names conflicts: "budget (Alice's conflicted copy 2026-06-01).json"
        return (
            list(parent.glob(f"{stem}*conflict*{ext}"))
            + list(parent.glob(f"{stem}*(* conflicted*){ext}"))
        )

    @staticmethod
    def get_file_mtime(file_path: str) -> float:
        if not os.path.exists(file_path):
            return 0.0
        return os.path.getmtime(file_path)

    @staticmethod
    def is_externally_modified(file_path: str, known_mtime: float) -> bool:
        """True if the file on disk is newer than when we last loaded it."""
        current = SyncManager.get_file_mtime(file_path)
        return current > known_mtime + 1.0   # 1 s tolerance for same-save

    @staticmethod
    def peek_metadata(file_path: str) -> dict:
        """Read just the metadata block without fully deserialising the budget."""
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            meta = data.get("metadata", {})
            return {
                "last_modified": meta.get("last_modified", ""),
                "last_modified_by": meta.get("last_modified_by", "your partner"),
            }
        except Exception:
            return {"last_modified": "", "last_modified_by": "your partner"}

    @staticmethod
    def friendly_time(iso_str: str) -> str:
        """Convert ISO timestamp to a short human-readable string."""
        try:
            dt = datetime.fromisoformat(iso_str)
            delta = datetime.now() - dt
            mins = int(delta.total_seconds() / 60)
            if mins < 1:
                return "just now"
            if mins < 60:
                return f"{mins} min ago"
            hours = mins // 60
            if hours < 24:
                return f"{hours} h ago"
            return dt.strftime("%b %-d")
        except Exception:
            return ""

    @staticmethod
    def update_metadata(budget, user: str):
        """Stamp last_modified / last_modified_by before saving."""
        budget.last_modified = datetime.now().isoformat()
        budget.last_modified_by = user
        return budget
