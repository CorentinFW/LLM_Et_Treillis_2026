#!/usr/bin/env bash
# fast_time.sh — Run a lattice algorithm on a dataset CSV and append logs.
#
# Usage:
#   ./fast_time.sh <path_vers_algo> <Nom_du_csv>
#
# Arguments (exactly 2):
#   <path_vers_algo>  Relative path (from repo root) to the algorithm to run
#                     (.jar for FCA4J, or .py for Python).
#   <Nom_du_csv>      Dataset name (directory name), e.g. eg20_20, balance-scale_binarized.
#
# Examples:
#   ./fast_time.sh FCA4J/fca4j-cli-0.4.4.jar balance-scale_binarized
#   ./fast_time.sh Claude_Opus-4.6/Python/lattice2.py eg9_9
#
# Output log (append mode):
#   TimeRecord/<Nom_du_csv>/<Parent>_result.txt
# where <Parent> is the first path component of <path_vers_algo>.

set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage:
  ./fast_time.sh <path_vers_algo> <Nom_du_csv>

Examples:
  ./fast_time.sh FCA4J/fca4j-cli-0.4.4.jar balance-scale_binarized
  ./fast_time.sh Claude_Opus-4.6/Python/lattice2.py eg9_9
USAGE
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

info() {
  echo "INFO: $*" >&2
}

require_cmd() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || die "Missing required command: $cmd"
}

on_err() {
  local exit_code=$?
  local line_no=${1:-?}
  # Keep this short and clear; detailed output is in the log file.
  echo "ERROR: failed at line ${line_no} (exit ${exit_code})" >&2
  exit "$exit_code"
}
trap 'on_err "$LINENO"' ERR

find_repo_root() {
  local script_path script_dir dir
  script_path="${BASH_SOURCE[0]}"
  script_dir="$(cd "$(dirname "$script_path")" && pwd -P)"

  dir="$script_dir"
  while :; do
    if [[ -d "$dir/Outils" && -d "$dir/TimeRecord" ]]; then
      echo "$dir"
      return 0
    fi

    if [[ "$dir" == "/" ]]; then
      break
    fi

    dir="$(dirname "$dir")"
  done

  return 1
}

detect_algo_kind() {
  local algo_rel="$1"
  local parent="$2"

  if [[ "$algo_rel" == *.jar || "$parent" == "FCA4J" ]]; then
    echo "fca4j"
    return 0
  fi
  if [[ "$algo_rel" == *.py ]]; then
    echo "python"
    return 0
  fi

  return 1
}

build_csv_path() {
  local kind="$1"
  local repo_root="$2"
  local parent="$3"
  local dataset="$4"

  local p1 p2
  if [[ "$kind" == "fca4j" ]]; then
    echo "FCA4J/${dataset}/${dataset}.csv"
    return 0
  fi

  # Python algorithms: try two layouts.
  p1="${parent}/Python/${dataset}/${dataset}.csv"
  if [[ -f "${repo_root}/${p1}" ]]; then
    echo "$p1"
    return 0
  fi

  p2="${parent}/${dataset}/${dataset}.csv"
  if [[ -f "${repo_root}/${p2}" ]]; then
    echo "$p2"
    return 0
  fi

  echo ""  # caller handles error messaging
  return 0
}

write_log_header() {
  local out_file="$1"
  local kind="$2"
  local algo_path="$3"
  local dataset="$4"
  local csv_path="$5"
  local dot_out="${6:-}"
  shift 6 || true
  local -a cmd=("$@")

  {
    echo "============================================================"
    echo "Date: $(date '+%Y-%m-%dT%H:%M:%S%z')"
    echo "Kind: ${kind}"
    echo "Algo: ${algo_path}"
    echo "Dataset: ${dataset}"
    echo "CSV: ${csv_path}"
    if [[ -n "$dot_out" ]]; then
      echo "DOT: ${dot_out}"
    fi
    printf 'Command:'
    printf ' %q' "${cmd[@]}"
    echo
    echo "------------------------------------------------------------"
  } >>"$out_file"
}

run_fca4j() {
  local repo_root="$1"
  local algo_rel="$2"
  local dataset="$3"
  local csv_rel="$4"
  local out_rel="$5"

  require_cmd java

  local dot_rel
  dot_rel="FCA4J/${dataset}/Lattice/${dataset}.dot"
  mkdir -p "$(dirname "$dot_rel")"

  local -a cmd=(
    java -jar "$algo_rel"
    LATTICE "$csv_rel"
    -i CSV
    -s SEMICOLON
    -g "$dot_rel"
  )

  info "Algo kind: FCA4J (.jar)"
  info "CSV_PATH: $csv_rel"
  info "DOT_OUT:  $dot_rel"
  info "LOG:      $out_rel"

  write_log_header "$out_rel" "fca4j" "$algo_rel" "$dataset" "$csv_rel" "$dot_rel" "${cmd[@]}"

  if ! "${cmd[@]}" >>"$out_rel" 2>&1; then
    die "FCA4J execution failed. See log: $out_rel"
  fi
}

run_python() {
  local repo_root="$1"
  local algo_rel="$2"
  local dataset="$3"
  local csv_rel="$4"
  local out_rel="$5"

  require_cmd python3

  local wrapper
  wrapper="Outils/run_with_cpu_time.py"
  [[ -f "${repo_root}/${wrapper}" ]] || die "Wrapper not found: $wrapper"

  local -a cmd=(
    python3 "$wrapper" "$algo_rel" "$csv_rel"
  )

  info "Algo kind: Python (.py)"
  info "CSV_PATH: $csv_rel"
  info "LOG:      $out_rel"

  write_log_header "$out_rel" "python" "$algo_rel" "$dataset" "$csv_rel" "" "${cmd[@]}"

  if ! "${cmd[@]}" >>"$out_rel" 2>&1; then
    die "Python execution failed. See log: $out_rel"
  fi
}

main() {
  if [[ $# -ne 2 ]]; then
    usage
    die "Expected exactly 2 arguments, got $#"
  fi

  local algo_rel dataset
  algo_rel="$1"
  dataset="$2"

  # Basic normalization (keep paths relative to repo root).
  algo_rel="${algo_rel#./}"

  [[ -n "$algo_rel" ]] || die "<path_vers_algo> must be non-empty"
  [[ -n "$dataset" ]] || die "<Nom_du_csv> must be non-empty"

  # Safety: ensure repo-relative paths (avoid escaping the repo).
  if [[ "$algo_rel" == /* ]]; then
    die "<path_vers_algo> must be a relative path from repo root (got absolute path)"
  fi
  if [[ "$algo_rel" == *".."* ]]; then
    die "<path_vers_algo> must not contain '..'"
  fi

  # Dataset name should be a simple directory name.
  if [[ "$dataset" == */* || "$dataset" == *".."* ]]; then
    die "<Nom_du_csv> must be a simple dataset name without '/' or '..'"
  fi
  if [[ ! "$dataset" =~ ^[A-Za-z0-9._-]+$ ]]; then
    die "<Nom_du_csv> contains invalid characters (allowed: A-Z a-z 0-9 . _ -)"
  fi

  local repo_root
  if ! repo_root="$(find_repo_root)"; then
    die "Cannot locate repo root (expected directories 'Outils/' and 'TimeRecord/'). Run from inside the repo or fix the repository structure."
  fi

  local parent
  parent="${algo_rel%%/*}"
  [[ -n "$parent" ]] || die "Cannot parse parent directory from <path_vers_algo>: $algo_rel"

  local algo_abs
  algo_abs="${repo_root}/${algo_rel}"
  [[ -f "$algo_abs" ]] || die "Algorithm file not found: $algo_rel"

  local kind
  if ! kind="$(detect_algo_kind "$algo_rel" "$parent")"; then
    die "Unsupported algorithm type. Expected .jar (FCA4J) or .py (Python). Got: $algo_rel"
  fi

  local csv_rel
  csv_rel="$(build_csv_path "$kind" "$repo_root" "$parent" "$dataset")"
  if [[ -z "$csv_rel" ]]; then
    die "CSV not found for dataset '${dataset}'. Tried: '${parent}/Python/${dataset}/${dataset}.csv' and '${parent}/${dataset}/${dataset}.csv'"
  fi
  [[ -f "${repo_root}/${csv_rel}" ]] || die "CSV file not found: $csv_rel"

  local out_dir_rel out_file_rel
  out_dir_rel="TimeRecord/${dataset}"
  out_file_rel="${out_dir_rel}/${parent}_result.txt"
  info "PARENT:    $parent"

  # Execute from repo root so all paths remain relative.
  cd "$repo_root"

  mkdir -p "$out_dir_rel"

  case "$kind" in
    fca4j)
      run_fca4j "$repo_root" "$algo_rel" "$dataset" "$csv_rel" "$out_file_rel"
      ;;
    python)
      run_python "$repo_root" "$algo_rel" "$dataset" "$csv_rel" "$out_file_rel"
      ;;
    *)
      die "Internal error: unknown kind '$kind'"
      ;;
  esac
}

main "$@"
