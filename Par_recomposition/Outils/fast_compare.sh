#!/usr/bin/env bash
# fast_compare.sh
#
# But:
#   Orchestrateur idempotent pour générer/compléter des treillis (.dot) puis comparer
#   le treillis complet FCA4J et le treillis complet LLM (généré par un algorithme Python).
#
# Usage:
#   ./Outils/fast_compare.sh [--fca4j-jar /path/to/fca4j-cli.jar] <CSV_INPUT> <ALGO_PY>
#
# Arguments:
#   CSV_INPUT : Nom.csv ou chemin vers Nom.csv (sert à déduire NAME=Nom)
#   ALGO_PY   : chemin vers le script Python de l'algorithme (ex: GPT-5.1/lattice.py)
#
# Options:
#   --fca4j-jar <path> : chemin vers fca4j-cli-*.jar (sinon FCA4J_JAR ou défaut existant)
#   -h, --help         : aide
#
# Prérequis:
#   - bash, java, python3
#   - Structure projet: racine contenant les dossiers "FCA4J" et "Outils"
#   - Scripts: Outils/compare_lattices.py et Outils/induced_to_full_dot.py
#
# Codes de sortie:
#   0  : treillis équivalents (compare_lattices.py)
#   1  : treillis différents (compare_lattices.py)
#   >=2: erreur d'usage/validation/dépendances/fichiers manquants/exécution

set -Eeuo pipefail
IFS=$'\n\t'

# -------- logging / errors --------

ts() { date +'%Y-%m-%d %H:%M:%S'; }

log_info() { printf '%s [INFO] %s\n' "$(ts)" "$*"; }
log_warn() { printf '%s [WARN] %s\n' "$(ts)" "$*" >&2; }
log_err()  { printf '%s [ERROR] %s\n' "$(ts)" "$*" >&2; }

die() {
  local msg=$1
  local code=${2:-2}
  log_err "$msg"
  exit "$code"
}

on_err() {
  local exit_code=$?
  local line_no=${1:-"?"}
  # BASH_COMMAND can be empty in some contexts.
  local cmd=${BASH_COMMAND:-"(commande inconnue)"}
  log_err "Échec (code ${exit_code}) à la ligne ${line_no}: ${cmd}"
  exit 3
}
trap 'on_err $LINENO' ERR

# -------- small helpers --------

usage() {
  cat <<'EOF'
Usage:
  fast_compare.sh [--fca4j-jar /path/to/fca4j-cli.jar] <CSV_INPUT> <ALGO_PY>

Description:
  - Vérifie/génère le treillis complet FCA4J (si absent).
  - Vérifie/génère le treillis induit LLM via l'algorithme Python (si absent).
  - Convertit le treillis induit en treillis complet LLM (si absent).
  - Compare les deux treillis complets et propage le code de sortie (0/1).

Entrées:
  CSV_INPUT : Nom.csv ou chemin vers Nom.csv
  ALGO_PY   : chemin vers le script Python de l'algorithme

Options:
  --fca4j-jar <path> : chemin vers le jar FCA4J (sinon FCA4J_JAR)
  -h, --help         : afficher cette aide

Exemples:
  ./Outils/fast_compare.sh eg20_20.csv GPT-5.1/lattice.py
  ./Outils/fast_compare.sh --fca4j-jar FCA4J/fca4j-cli-0.4.4.jar /tmp/eg20_20.csv GPT-5.1/lattice.py
EOF
}

need_cmd() {
  local cmd=$1
  command -v "$cmd" >/dev/null 2>&1 || die "Commande requise introuvable: '$cmd'. Installe-la puis réessaie." 2
}

# Avoid non-portable dependencies; attempt realpath then readlink -f.
abs_path() {
  local p=$1
  if command -v realpath >/dev/null 2>&1; then
    realpath "$p"
  elif command -v readlink >/dev/null 2>&1; then
    readlink -f "$p"
  else
    # Best-effort: resolve via pwd; may be relative.
    (cd -- "$(dirname -- "$p")" && printf '%s/%s\n' "$(pwd -P)" "$(basename -- "$p")")
  fi
}

find_project_root() {
  local start_dir=$1
  local cur=$start_dir
  local i
  for i in {1..8}; do
    if [[ -d "$cur/FCA4J" && -d "$cur/Outils" ]]; then
      printf '%s\n' "$cur"
      return 0
    fi
    local parent
    parent=$(cd -- "$cur/.." && pwd -P)
    [[ "$parent" == "$cur" ]] && break
    cur=$parent
  done
  return 1
}

is_csv_name() {
  [[ "$1" == *.csv ]]
}

strip_csv_ext() {
  local base
  base=$(basename -- "$1")
  printf '%s\n' "${base%.csv}"
}

resolve_algo_layout() {
  # Determine which layout to use for the algorithm dataset folder.
  # Returns 0 and prints chosen base_dir if it exists, else prints empty and returns 1.
  # Order: simple then double.
  local algo_dir=$1
  local name=$2

  local simple_dir="$algo_dir/$name"
  local double_dir="$algo_dir/$name/$name"

  if [[ -d "$simple_dir" ]]; then
    printf '%s\n' "$simple_dir"
    return 0
  fi
  if [[ -d "$double_dir" ]]; then
    printf '%s\n' "$double_dir"
    return 0
  fi
  return 1
}

resolve_first_existing_file() {
  # Usage: resolve_first_existing_file <label> <path1> <path2>
  # Prints path if found; else dies listing paths tested.
  local label=$1
  local p1=$2
  local p2=$3

  if [[ -f "$p1" ]]; then
    printf '%s\n' "$p1"
    return 0
  fi
  if [[ -f "$p2" ]]; then
    printf '%s\n' "$p2"
    return 0
  fi

  die "$label introuvable. Chemins testés:\n  - $p1\n  - $p2" 2
}

find_induced_dot() {
  # Find the induced DOT for a given dataset base directory.
  # Preference order:
  #   1) <base>/Lattice/<NAME>_LLM.dot
  #   2) first match (sorted) of <base>/Lattice/<NAME>_LLM*.dot
  # Prints the chosen file path if found, else prints nothing and returns 1.
  local base_dir=$1
  local name=$2

  local exact="$base_dir/Lattice/${name}_LLM.dot"
  if [[ -f "$exact" ]]; then
    printf '%s\n' "$exact"
    return 0
  fi

  local lattice_dir="$base_dir/Lattice"
  [[ -d "$lattice_dir" ]] || return 1

  # Use find (portable) instead of globbing; keep deterministic by sorting.
  local matches
  matches=$(find "$lattice_dir" -maxdepth 1 -type f -name "${name}_LLM*.dot" -print 2>/dev/null | LC_ALL=C sort) || true
  if [[ -n "$matches" ]]; then
    printf '%s\n' "$(printf '%s\n' "$matches" | head -n 1)"
    return 0
  fi

  return 1
}

# -------- args parsing --------

FCA4J_JAR_CLI=""
CSV_INPUT=""
ALGO_PY=""
END_OF_OPTS=0

while [[ $# -gt 0 ]]; do
  if [[ $END_OF_OPTS -eq 1 ]]; then
    if [[ -z "$CSV_INPUT" ]]; then
      CSV_INPUT=$1
    elif [[ -z "$ALGO_PY" ]]; then
      ALGO_PY=$1
    else
      die "Trop d'arguments. Utilise -h pour l'aide." 2
    fi
    shift
    continue
  fi

  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --fca4j-jar)
      [[ $# -ge 2 ]] || die "Option --fca4j-jar attend un chemin." 2
      FCA4J_JAR_CLI=$2
      shift 2
      ;;
    --)
      END_OF_OPTS=1
      shift
      ;;
    -* )
      die "Option inconnue: $1 (utilise -h pour l'aide)." 2
      ;;
    *)
      # Positional args
      if [[ -z "$CSV_INPUT" ]]; then
        CSV_INPUT=$1
      elif [[ -z "$ALGO_PY" ]]; then
        ALGO_PY=$1
      else
        die "Trop d'arguments. Utilise -h pour l'aide." 2
      fi
      shift
      ;;
  esac

done

if [[ -z "$CSV_INPUT" || -z "$ALGO_PY" ]]; then
  usage >&2
  die "Arguments manquants: <CSV_INPUT> et <ALGO_PY> sont requis." 2
fi

is_csv_name "$CSV_INPUT" || die "CSV_INPUT doit se terminer par .csv (reçu: '$CSV_INPUT')." 2

NAME=$(strip_csv_ext "$CSV_INPUT")
[[ -n "$NAME" ]] || die "Impossible de déduire NAME depuis '$CSV_INPUT'." 2

# -------- environment validation --------

need_cmd java
need_cmd python3

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
PROJECT_ROOT=$(find_project_root "$SCRIPT_DIR") || die "Impossible de détecter la racine projet depuis '$SCRIPT_DIR'. Attendu: dossiers 'FCA4J' et 'Outils'." 2

FCA4J_DIR="$PROJECT_ROOT/FCA4J"
OUTILS_DIR="$PROJECT_ROOT/Outils"

COMPARE_PY="$OUTILS_DIR/compare_lattices.py"
INDUCED_TO_FULL_PY="$OUTILS_DIR/induced_to_full_dot.py"

[[ -f "$COMPARE_PY" ]] || die "Script requis introuvable: $COMPARE_PY" 2
[[ -f "$INDUCED_TO_FULL_PY" ]] || die "Script requis introuvable: $INDUCED_TO_FULL_PY" 2

ALGO_PY_ABS=$(abs_path "$ALGO_PY")
[[ -f "$ALGO_PY_ABS" ]] || die "ALGO_PY introuvable: '$ALGO_PY'" 2
ALGO_DIR=$(cd -- "$(dirname -- "$ALGO_PY_ABS")" && pwd -P)

# -------- resolve FCA4J jar --------

FCA4J_JAR_PATH=""
if [[ -n "$FCA4J_JAR_CLI" ]]; then
  FCA4J_JAR_PATH=$(abs_path "$FCA4J_JAR_CLI")
elif [[ -n "${FCA4J_JAR:-}" ]]; then
  FCA4J_JAR_PATH=$(abs_path "$FCA4J_JAR")
fi

if [[ -z "$FCA4J_JAR_PATH" ]]; then
  # Default candidates (only if they exist)
  if [[ -f "$FCA4J_DIR/fca4j-cli-0.4.4.jar" ]]; then
    FCA4J_JAR_PATH="$FCA4J_DIR/fca4j-cli-0.4.4.jar"
  elif [[ -f "$PROJECT_ROOT/fca4j-cli-0.4.4.jar" ]]; then
    FCA4J_JAR_PATH="$PROJECT_ROOT/fca4j-cli-0.4.4.jar"
  fi
fi

[[ -n "$FCA4J_JAR_PATH" ]] || die "Chemin du jar FCA4J non fourni. Fournis --fca4j-jar <path> ou exporte FCA4J_JAR. (Défaut tenté: fca4j-cli-0.4.4.jar si présent)" 2
[[ -f "$FCA4J_JAR_PATH" ]] || die "Jar FCA4J introuvable: '$FCA4J_JAR_PATH'. Indique le bon chemin via --fca4j-jar ou FCA4J_JAR." 2

# -------- Step 1: check FCA4J CSV exists --------

FCA4J_CSV="$FCA4J_DIR/$NAME/$NAME.csv"
[[ -f "$FCA4J_CSV" ]] || die "CSV FCA4J requis introuvable: $FCA4J_CSV\nAttendu: FCA4J/NAME/NAME.csv (NAME='$NAME').\nCorrige en plaçant le CSV au bon endroit." 2

# -------- Step 2: ensure FCA4J full DOT --------

FCA4J_FULL_DOT="$FCA4J_DIR/$NAME/Lattice/full/${NAME}_full.dot"
if [[ -f "$FCA4J_FULL_DOT" ]]; then
  log_info "Treillis complet FCA4J déjà présent (skip): $FCA4J_FULL_DOT"
else
  log_info "Génération du treillis complet FCA4J: $FCA4J_FULL_DOT"
  mkdir -p -- "$(dirname -- "$FCA4J_FULL_DOT")"
  java -jar "$FCA4J_JAR_PATH" LATTICE "$FCA4J_CSV" -i CSV -s SEMICOLON -g "$FCA4J_FULL_DOT" -d full
  [[ -f "$FCA4J_FULL_DOT" ]] || die "Génération FCA4J terminée mais DOT introuvable: $FCA4J_FULL_DOT" 4
fi

# -------- Step 3: ensure induced LLM DOT --------

# Candidate layouts: simple then double.
ALGO_SIMPLE_BASE="$ALGO_DIR/$NAME"
ALGO_DOUBLE_BASE="$ALGO_DIR/$NAME/$NAME"

ALGO_BASE=""
INDUCED_DOT=""

if INDUCED_DOT=$(find_induced_dot "$ALGO_SIMPLE_BASE" "$NAME"); then
  ALGO_BASE="$ALGO_SIMPLE_BASE"
  log_info "Treillis induit LLM déjà présent (skip): $INDUCED_DOT"
elif INDUCED_DOT=$(find_induced_dot "$ALGO_DOUBLE_BASE" "$NAME"); then
  ALGO_BASE="$ALGO_DOUBLE_BASE"
  log_info "Treillis induit LLM déjà présent (skip): $INDUCED_DOT"
else
  log_info "Treillis induit LLM absent: exécution de l'algorithme Python."

  ALGO_CSV_SIMPLE="$ALGO_SIMPLE_BASE/$NAME.csv"
  ALGO_CSV_DOUBLE="$ALGO_DOUBLE_BASE/$NAME.csv"

  if [[ -f "$ALGO_CSV_SIMPLE" ]]; then
    ALGO_BASE="$ALGO_SIMPLE_BASE"
    ALGO_CSV="$ALGO_CSV_SIMPLE"
  elif [[ -f "$ALGO_CSV_DOUBLE" ]]; then
    ALGO_BASE="$ALGO_DOUBLE_BASE"
    ALGO_CSV="$ALGO_CSV_DOUBLE"
  else
    die "CSV côté algorithme introuvable. Chemins testés:\n  - $ALGO_CSV_SIMPLE\n  - $ALGO_CSV_DOUBLE\nNe copie pas automatiquement; place le CSV au bon endroit." 2
  fi

  log_info "Lancement: python3 $ALGO_PY_ABS $ALGO_CSV"
  python3 "$ALGO_PY_ABS" "$ALGO_CSV"

  if ! INDUCED_DOT=$(find_induced_dot "$ALGO_BASE" "$NAME"); then
    die "Algorithme exécuté mais treillis induit introuvable. Attendu (au choix):\n  - $ALGO_BASE/Lattice/${NAME}_LLM.dot\n  - $ALGO_BASE/Lattice/${NAME}_LLM*.dot" 4
  fi
fi

# -------- Step 4: ensure full LLM DOT --------

LLM_FULL_DOT=""

if [[ -z "$ALGO_BASE" ]]; then
  die "Impossible de déterminer le chemin du DOT complet LLM (base algo inconnue)." 3
fi

# Preserve induced-dot semantics: <something>.dot -> <something>_full.dot
induced_filename=$(basename -- "$INDUCED_DOT")
induced_stem=${induced_filename%.dot}
LLM_FULL_DOT="$ALGO_BASE/Lattice/full/${induced_stem}_full.dot"

if [[ -f "$LLM_FULL_DOT" ]]; then
  log_info "Treillis complet LLM déjà présent (skip): $LLM_FULL_DOT"
else
  log_info "Conversion induit -> complet LLM: $LLM_FULL_DOT"
  mkdir -p -- "$(dirname -- "$LLM_FULL_DOT")"
  python3 "$INDUCED_TO_FULL_PY" "$INDUCED_DOT" "$LLM_FULL_DOT"
  [[ -f "$LLM_FULL_DOT" ]] || die "Conversion terminée mais DOT complet LLM introuvable: $LLM_FULL_DOT" 4
fi

# -------- Step 5: compare --------

log_info "Comparaison des treillis: FCA4J vs LLM"
log_info "  FCA4J: $FCA4J_FULL_DOT"
log_info "  LLM  : $LLM_FULL_DOT"

set +e
python3 "$COMPARE_PY" "$FCA4J_FULL_DOT" "$LLM_FULL_DOT"
rc=$?
set -e

if [[ $rc -eq 0 || $rc -eq 1 ]]; then
  exit "$rc"
fi

die "compare_lattices.py a retourné un code inattendu ($rc). Vérifie les fichiers .dot et relance avec les mêmes arguments." 3
