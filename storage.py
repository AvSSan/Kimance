import json
import os
from config import CATEGORIES_FILE, DEFAULT_EXPENSE_CATEGORIES, DEFAULT_INCOME_CATEGORIES

class Storage:
    def __init__(self, filename=CATEGORIES_FILE):
        self.filename = filename
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.filename):
            data = {
                "income": DEFAULT_INCOME_CATEGORIES.copy(),
                "expense": DEFAULT_EXPENSE_CATEGORIES.copy()
            }
            self._save_data(data)

    def _load_data(self) -> dict:
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"income": DEFAULT_INCOME_CATEGORIES.copy(), "expense": DEFAULT_EXPENSE_CATEGORIES.copy()}

    def _save_data(self, data: dict):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def get_categories(self, type_: str) -> list[str]:
        """type_ can be 'income' or 'expense'"""
        data = self._load_data()
        return data.get(type_, [])

    def add_category(self, type_: str, category: str) -> bool:
        """Returns True if added, False if already exists."""
        data = self._load_data()
        categories = data.get(type_, [])
        
        # Check ignoring case and stripped spaces
        cat_lower = category.strip().lower()
        if any(c.lower().strip() == cat_lower for c in categories):
            return False
            
        data[type_].append(category.strip())
        self._save_data(data)
        return True

    def remove_category(self, type_: str, category: str) -> bool:
        """Returns True if removed, False if not found or it's the last one."""
        data = self._load_data()
        categories = data.get(type_, [])
        
        if len(categories) <= 1:
            return False # Cannot remove the last category
            
        if category in categories:
            data[type_].remove(category)
            self._save_data(data)
            return True
        return False

# Initialize a global instance
storage = Storage()
