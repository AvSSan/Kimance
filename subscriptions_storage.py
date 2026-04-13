import json
import os
import uuid

class SubscriptionsStorage:
    def __init__(self, filename="subscriptions.json"):
        self.filename = filename
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.filename):
            self._save_data([])

    def _load_data(self) -> list:
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_data(self, data: list):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def get_all(self):
        return self._load_data()

    def add_subscription(self, name: str, amount: float, category: str, type_: str, date_str: str):
        data = self._load_data()
        sub_id = str(uuid.uuid4())[:8]
        data.append({
            "id": sub_id,
            "name": name,
            "amount": amount,
            "category": category,
            "type": type_,
            "date": date_str # DD.MM.YYYY format expected
        })
        self._save_data(data)
        return sub_id

    def remove_subscription(self, sub_id: str):
        data = self._load_data()
        original_length = len(data)
        data = [s for s in data if s["id"] != sub_id]
        if len(data) < original_length:
            self._save_data(data)
            return True
        return False
        
    def update_subscription_date(self, sub_id: str, new_date_str: str):
        data = self._load_data()
        for s in data:
            if s["id"] == sub_id:
                s["date"] = new_date_str
                self._save_data(data)
                return True
        return False

# Global instance
sub_storage = SubscriptionsStorage()
