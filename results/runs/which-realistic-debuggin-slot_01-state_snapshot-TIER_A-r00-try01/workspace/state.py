import json
from pathlib import Path
import os
import tempfile


class MigrationState:
    def __init__(self, marker_path: Path):
        self.marker_path = marker_path
        self.done_steps = set()
        self.load_state()

    def load_state(self):
        if self.marker_path.exists():
            try:
                with open(self.marker_path, "r") as f:
                    data = json.load(f)
                    self.done_steps = set(data.get("done", []))
            except json.JSONDecodeError:
                # If marker file is corrupted, treat as empty state
                # This allows migration to restart from scratch for the marker file
                self.done_steps = set()
        else:
            self.done_steps = set()

    def save_state(self):
        # Make save_state atomic to prevent corrupted marker files
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=self.marker_path.parent, encoding="utf-8") as tmp_f:
                json.dump({"done": list(self.done_steps)}, tmp_f, indent=2)
                tmp_f.flush()
                os.fsync(tmp_f.fileno())
            
            temp_file_path = Path(tmp_f.name)
            os.replace(temp_file_path, self.marker_path)
        finally:
            if temp_file_path and temp_file_path.exists():
                temp_file_path.unlink()

    def mark_done(self, step_name: str):
        self.done_steps.add(step_name)

    def is_done(self, step_name: str) -> bool:
        return step_name in self.done_steps
