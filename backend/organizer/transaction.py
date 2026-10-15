import os
import shutil
import json
from datetime import datetime

class TransactionManager:
    def __init__(self, journal_path: str = "move_journal.json"):
        self.journal_path = journal_path
        self.operations = [] # List of {'src': str, 'dst': str, 'status': 'pending'|'done'}

    def add_move(self, src: str, dst: str):
        """Adds a move operation to the transaction."""
        self.operations.append({
            'src': src,
            'dst': dst,
            'timestamp': datetime.now().isoformat(),
            'status': 'pending'
        })

    def save_journal(self):
        """Saves current operations to disk."""
        with open(self.journal_path, 'w') as f:
            json.dump(self.operations, f, indent=2)

    def execute(self):
        """Executes all pending operations safely."""
        self.save_journal()
        
        completed_count = 0
        errors = []
        
        for op in self.operations:
            if op['status'] == 'done':
                continue
                
            src = op['src']
            dst = op['dst']
            
            try:
                # Ensure dst directory exists
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                
                # Handle collision
                if os.path.exists(dst):
                    base, ext = os.path.splitext(dst)
                    dst = f"{base}_copy{datetime.now().microsecond}{ext}"
                    op['dst'] = dst # Update journal with actual dst
                
                shutil.move(src, dst)
                op['status'] = 'done'
                completed_count += 1
                
            except Exception as e:
                print(f"Error moving {src} to {dst}: {e}")
                errors.append(str(e))
                # Stop on error? Or continue?
                # For batch processing, maybe continue but log error.
                op['status'] = 'error'
                op['error'] = str(e)
        
        self.save_journal()
        return completed_count, errors

    def rollback(self):
        """Reverses all 'done' operations in reverse order."""
        if not os.path.exists(self.journal_path):
            return 0
            
        with open(self.journal_path, 'r') as f:
            self.operations = json.load(f)
            
        # Reverse iterate
        rollback_count = 0
        for op in reversed(self.operations):
            if op.get('status') == 'done':
                src = op['src'] # Original location
                dst = op['dst'] # Current location
                
                try:
                    if os.path.exists(dst):
                        shutil.move(dst, src)
                        op['status'] = 'rolled_back'
                        rollback_count += 1
                except Exception as e:
                    print(f"Error rolling back {dst} to {src}: {e}")
                    
        self.save_journal()
        return rollback_count
