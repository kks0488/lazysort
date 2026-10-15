import json
import os
from datetime import datetime

HISTORY_FILE = "history.json"

def save_log(original: str, new: str, status: str = "success"):
    """
    Saves the renaming operation to a JSON log file.
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "original": original,
        "new": new,
        "status": status
    }
    
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        except json.JSONDecodeError:
            pass
            
    history.append(entry)
    
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def get_undo_operations(limit: int = 10) -> list[dict]:
    """
    Retrieves the last N operations for undo.
    """
    if not os.path.exists(HISTORY_FILE):
        return []
        
    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
            return history[-limit:]
    except json.JSONDecodeError:
        return []
