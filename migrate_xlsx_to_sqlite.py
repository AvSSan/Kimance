import argparse

from database import records_db
from excel_utils import records_from_xlsx


def main():
    parser = argparse.ArgumentParser(description="Import finance records from xlsx into SQLite.")
    parser.add_argument("path", nargs="?", default="Kimance.xlsx")
    parser.add_argument("--sheet", default="Расходы")
    args = parser.parse_args()

    records_db.init()
    records = records_from_xlsx(args.path, args.sheet)
    inserted, skipped = records_db.import_records(records)

    print(f"Read records: {len(records)}")
    print(f"Inserted: {inserted}")
    print(f"Skipped duplicates: {skipped}")
    print(f"Database: {records_db.filename}")


if __name__ == "__main__":
    main()
