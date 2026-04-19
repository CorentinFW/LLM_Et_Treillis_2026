#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT_DIR/llm/Chatgpt5.3Codex/C++/concept_lattice"

SEARCH_DIRS=(
  "$ROOT_DIR/llm/Chatgpt5.3Codex/C++/Test/RealData"
)

if [[ ! -x "$BIN" ]]; then
  echo "Erreur: executable introuvable ou non executable: $BIN" >&2
  exit 1
fi

mapfile -t CSV_FILES < <(find "${SEARCH_DIRS[@]}" -type f -name '*.csv' 2>/dev/null | sort -u)

if [[ ${#CSV_FILES[@]} -eq 0 ]]; then
  echo "Aucun CSV trouve dans Test/RealData."
  exit 0
fi

echo "CSV RealData detectes: ${#CSV_FILES[@]}"

ok_count=0
ko_count=0

for csv in "${CSV_FILES[@]}"; do
  dot="${csv%.csv}.dot"
  tmp_csv="$(mktemp)"
  echo "[RUN] $(realpath --relative-to="$ROOT_DIR" "$csv") -> $(realpath --relative-to="$ROOT_DIR" "$dot")"

  # Normalise le CSV au format attendu par concept_lattice: separateur ';' et
  # premiere cellule d'en-tete vide.
  if ! python3 - "$csv" "$tmp_csv" <<'PY'
import csv
import sys

src_path = sys.argv[1]
dst_path = sys.argv[2]

with open(src_path, "r", encoding="utf-8", newline="") as src:
    sample = src.read(8192)
    src.seek(0)
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.reader(src, delimiter=delimiter)
    rows = list(reader)

if not rows:
    raise SystemExit("CSV vide")

if not rows[0]:
    rows[0] = [""]

first_header = rows[0][0].lstrip("\ufeff").strip()
if first_header != "":
    rows[0][0] = ""

with open(dst_path, "w", encoding="utf-8", newline="") as dst:
    writer = csv.writer(dst, delimiter=";", lineterminator="\n")
    writer.writerows(rows)
PY
  then
    ko_count=$((ko_count + 1))
    echo "[ERR] Echec de normalisation CSV: $csv" >&2
    rm -f "$tmp_csv"
    continue
  fi

  if "$BIN" "$tmp_csv" "$dot"; then
    ok_count=$((ok_count + 1))
  else
    ko_count=$((ko_count + 1))
    echo "[ERR] Echec sur: $csv" >&2
  fi

  rm -f "$tmp_csv"
done

echo "Termine. OK=$ok_count, KO=$ko_count"

if [[ $ko_count -gt 0 ]]; then
  exit 2
fi
