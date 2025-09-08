from app.csv_import import import_csv
import sys

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_import.py path/to/contacts.csv")
        raise SystemExit(1)
    import_csv(sys.argv[1])
    print("Import complete.")
