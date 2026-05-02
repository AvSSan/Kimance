import json
import os
import uuid

from config import TEMPLATES_FILE


class TemplatesStorage:
    def __init__(self, filename=TEMPLATES_FILE):
        self.filename = filename
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.filename):
            self._save_data([])

    def _load_data(self) -> list:
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_data(self, data: list):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def get_all(self):
        return self._load_data()

    def get(self, template_id: str):
        return next((t for t in self._load_data() if t["id"] == template_id), None)

    def add_template(self, name: str, comment: str, type_: str, category: str):
        data = self._load_data()
        template_id = str(uuid.uuid4())[:8]
        data.append(
            {
                "id": template_id,
                "name": name.strip(),
                "comment": comment.strip(),
                "type": type_,
                "category": category,
            }
        )
        self._save_data(data)
        return template_id

    def remove_template(self, template_id: str):
        data = self._load_data()
        original_length = len(data)
        data = [t for t in data if t["id"] != template_id]
        if len(data) < original_length:
            self._save_data(data)
            return True
        return False


templates_storage = TemplatesStorage()
