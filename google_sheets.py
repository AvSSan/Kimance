import asyncio
import gspread
from google.oauth2.service_account import Credentials
import logging
import datetime

from config import GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_FILE, GOOGLE_WORKSHEET_TITLE

logger = logging.getLogger(__name__)

# Define the scope we need
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

class GoogleSheetsClient:
    def __init__(self):
        self.client = None
        self.spreadsheet = None
        self.worksheet = None
        
    def _authenticate(self):
        if not self.client:
            try:
                credentials = Credentials.from_service_account_file(
                    GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
                )
                self.client = gspread.authorize(credentials)
            except Exception as e:
                logger.error(f"Error authenticating to Google Sheets: {e}")
                raise
                
    def _init_worksheet(self):
        self._authenticate()
        if not self.spreadsheet:
            try:
                self.spreadsheet = self.client.open_by_key(GOOGLE_SHEET_ID)
            except Exception as e:
                logger.error(f"Error opening spreadsheet by key {GOOGLE_SHEET_ID}: {e}")
                raise

        # Try to open worksheet, if not exists, create it
        try:
            self.worksheet = self.spreadsheet.worksheet(GOOGLE_WORKSHEET_TITLE)
        except gspread.exceptions.WorksheetNotFound:
            logger.info(f"Worksheet '{GOOGLE_WORKSHEET_TITLE}' not found. Creating...")
            self.worksheet = self.spreadsheet.add_worksheet(title=GOOGLE_WORKSHEET_TITLE, rows="1000", cols="20")
            
        # Ensure headers exist
        headers = self.worksheet.row_values(1)
        expected_headers = ["Дата", "Время", "Тип", "Сумма", "Категория", "Комментарий"]
        if not headers or headers[:5] != expected_headers[:5]:
            logger.info("Headers not found or incorrect. Adding headers...")
            self.worksheet.insert_row(expected_headers, index=1)
            # Format header row to be bold (optional, can be done if needed)

    def _append_row(self, data: list):
        if not self.worksheet:
            self._init_worksheet()
        self.worksheet.append_row(data)

    async def init(self):
        """Asynchronously initialize connection and worksheet headers"""
        try:
            await asyncio.to_thread(self._init_worksheet)
            logger.info("Google Sheets initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets: {e}")
            
    async def add_record(self, record_type: str, amount: float, category: str, comment: str = ""):
        """
        Asynchronously appends a row to the worksheet.
        record_type: "Доход" or "Расход"
        amount: the sum
        category: category string
        comment: optional comment string
        """
        now = datetime.datetime.now()
        date_str = now.strftime("%d.%m.%Y")
        time_str = now.strftime("%H:%M")
        
        row_data = [date_str, time_str, record_type, amount, category, comment]
        
        try:
            await asyncio.to_thread(self._append_row, row_data)
            return True, row_data
        except Exception as e:
            logger.error(f"Failed to append row to Google Sheets: {e}")
            return False, []

    def _calculate_balance(self):
        if not self.worksheet:
            self._init_worksheet()
        
        records = self.worksheet.get_all_records()
        balance = 0.0
        for row in records:
            # "Сумма", "Тип" expected
            try:
                amt = float(str(row.get("Сумма", 0)).replace(',', '.'))
            except (ValueError, TypeError):
                amt = 0.0
                
            op_type = str(row.get("Тип", "")).strip()
            if op_type == "Доход":
                balance += amt
            elif op_type == "Расход":
                balance -= amt
                
        return balance

    async def get_balance(self):
        try:
            return await asyncio.to_thread(self._calculate_balance)
        except Exception as e:
            logger.error(f"Failed to calculate balance: {e}")
            return None

    def _delete_specific_row(self, row_data: list):
        if not self.worksheet:
            self._init_worksheet()
            
        records = self.worksheet.get_all_values()
        for i in range(len(records) - 1, 0, -1):
            row = records[i]
            # Match at least time, type, amount, category. row_data: [date, time, type, amount, cat, comment]
            if len(row) >= 5 and row[1] == row_data[1] and row[2] == row_data[2] and row[4] == row_data[4]:
                self.worksheet.delete_rows(i + 1)
                return True
        return False

    async def delete_record(self, row_data: list):
        try:
            return await asyncio.to_thread(self._delete_specific_row, row_data)
        except Exception as e:
            logger.error(f"Failed to delete record: {e}")
            return False

# Global instance
gs_client = GoogleSheetsClient()
