#!/usr/bin/env bash
set -euo pipefail

shopt -s nullglob
count=0
for f in csv/*.csv; do
  echo "[import] $f"
  python run_import.py "$f"
  count=$((count+1))
done

if [[ $count -eq 0 ]]; then
  echo "No CSV files found in csv/"
else
  echo "Imported $count file(s)."
fi

