#!/bin/bash

# Script pour exécuter un fichier C++ compilé sur tous les CSV d'un dossier
# et mesurer les performances (temps, RAM, disque)
#
# Usage: ./run_benchmark.sh <path_to_executable> <path_to_csv_folder>

set -euo pipefail

# Vérifier les arguments
if [ $# -ne 2 ]; then
    echo "Usage: $0 <path_to_executable> <path_to_csv_folder>"
    echo "Example: $0 ./lattice ./Test/RealData/balance-scale_binarized"
    exit 1
fi

EXECUTABLE="$1"
CSV_FOLDER="$2"
TIMEOUT_SECONDS=3600  # 1 heure

get_output_size_mb() {
    local file_path="$1"
    local bytes
    if [ -f "$file_path" ]; then
        bytes=$(stat -c%s "$file_path" 2>/dev/null || echo 0)
        echo $(( (bytes + 524287) / 1048576 ))
    else
        echo 0
    fi
}

get_elapsed_time() {
    local stats_path="$1"
    grep "Elapsed (wall clock) time" "$stats_path" 2>/dev/null | awk -F": " '{print $2}' | head -n1
}

get_max_rss_mb() {
    local stats_path="$1"
    local rss_kb
    rss_kb=$(grep "Maximum resident set size" "$stats_path" 2>/dev/null | awk -F": " '{print $2}' | head -n1 || true)
    if [ -n "${rss_kb:-}" ]; then
        echo $(( (rss_kb + 512) / 1024 ))
    else
        echo "N/A"
    fi
}

run_with_measure() {
    local stats_path="$1"
    local log_path="$2"
    shift 2
    timeout "$TIMEOUT_SECONDS" /usr/bin/time -v -o "$stats_path" "$@" >"$log_path" 2>&1
    return $?
}

looks_like_csv_delimiter_issue() {
    local log_path="$1"
    grep -Eiq "empty context read|malformed CSV row" "$log_path"
}

csv_needs_semicolon() {
    local csv_path="$1"
    local first_line
    first_line=$(head -n1 "$csv_path" 2>/dev/null || true)
    if echo "$first_line" | grep -q "," && ! echo "$first_line" | grep -q ";"; then
        return 0
    fi
    return 1
}

# Vérifier que l'exécutable existe et est exécutable
if [ ! -x "$EXECUTABLE" ]; then
    echo "Erreur: '$EXECUTABLE' n'existe pas ou n'est pas exécutable"
    exit 1
fi

# Vérifier que le dossier existe
if [ ! -d "$CSV_FOLDER" ]; then
    echo "Erreur: le dossier '$CSV_FOLDER' n'existe pas"
    exit 1
fi

# Extraire le chemin jusqu'à l'exécutable (sans "llm" et en remplaçant / par _)
EXEC_FULL_PATH=$(realpath "$EXECUTABLE")
# Enlever "llm/" du début s'il existe
EXEC_RELATIVE=$(echo "$EXEC_FULL_PATH" | sed "s|.*/llm/||")
# Remplacer les "/" par "_"
BENCHMARK_NAME=$(echo "$EXEC_RELATIVE" | sed 's|/|_|g')
BENCHMARK_FILE="benchmark_${BENCHMARK_NAME}.txt"

# Detecter l'interface de l'executable: 1 argument (input) ou 2 arguments (input output)
USAGE_LOG=$(mktemp "/tmp/benchmark_usage_XXXX.log")
timeout 5 "$EXECUTABLE" >"$USAGE_LOG" 2>&1 || true
if grep -q "<input.csv> <output.dot>" "$USAGE_LOG"; then
    EXEC_MODE="two_args"
elif grep -q "<input.csv>" "$USAGE_LOG"; then
    EXEC_MODE="one_arg"
else
    EXEC_MODE="auto"
fi
rm -f "$USAGE_LOG"

# Créer/initialiser le fichier benchmark
cat > "$BENCHMARK_FILE" << 'EOF'
================================================================================
RAPPORT DE BENCHMARK
================================================================================
Format: nom_csv | temps(s) | RAM_max(MB) | disque_sortie(MB) | statut | timestamp

EOF

echo "=== Démarrage du benchmark ==="
echo "Exécutable: $EXECUTABLE"
echo "Dossier CSV: $CSV_FOLDER"
echo "Fichier benchmark: $BENCHMARK_FILE"
echo "Timeout: ${TIMEOUT_SECONDS}s (1h)"
echo "Mode executable detecte: $EXEC_MODE"
echo ""

# Compteurs
total_tests=0
completed_tests=0
timeout_tests=0
failed_tests=0

# Trouver tous les fichiers CSV dans le dossier (récursivement)
while IFS= read -r csv_file; do
    total_tests=$((total_tests + 1))
    csv_basename=$(basename "$csv_file")
    csv_dir=$(dirname "$csv_file")
    output_file="${csv_dir}/${csv_basename%.csv}.dot"
    
    echo "════════════════════════════════════════"
    echo "Test $total_tests: $csv_basename"
    echo "════════════════════════════════════════"
    
    # Creer des fichiers temporaires pour stats et logs d'execution
    stats_file=$(mktemp "/tmp/benchmark_stats_XXXX.txt")
    exec_log=$(mktemp "/tmp/benchmark_exec_XXXX.log")
    start_time=$(date +%s)
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    rm -f "$output_file"

    run_status="ERROR"
    run_elapsed=""
    run_rss_mb="N/A"
    temp_csv=""
    temp_dot=""
    exit_code=1
    
    # Premier essai selon le mode detecte
    if [ "$EXEC_MODE" = "two_args" ]; then
        if run_with_measure "$stats_file" "$exec_log" "$EXECUTABLE" "$csv_file" "$output_file"; then
            run_status="SUCCESS"
            exit_code=0
        else
            exit_code=$?
        fi
    elif [ "$EXEC_MODE" = "one_arg" ]; then
        if run_with_measure "$stats_file" "$exec_log" "$EXECUTABLE" "$csv_file"; then
            run_status="SUCCESS"
            exit_code=0
        else
            exit_code=$?
        fi
    else
        if run_with_measure "$stats_file" "$exec_log" "$EXECUTABLE" "$csv_file" "$output_file"; then
            run_status="SUCCESS"
            exit_code=0
        else
            exit_code=$?
            if grep -q "Usage: .*<input.csv>" "$exec_log"; then
                if run_with_measure "$stats_file" "$exec_log" "$EXECUTABLE" "$csv_file"; then
                    run_status="SUCCESS"
                    exit_code=0
                else
                    exit_code=$?
                fi
            fi
        fi
    fi

    # Fallback: conversion comma->semicolon si erreur de parsing CSV
    if [ "$run_status" != "SUCCESS" ] && [ "$exit_code" -ne 124 ] && looks_like_csv_delimiter_issue "$exec_log" && csv_needs_semicolon "$csv_file"; then
        temp_csv=$(mktemp "/tmp/benchmark_csv_XXXX.csv")
        sed 's/,/;/g' "$csv_file" > "$temp_csv"

        if [ "$EXEC_MODE" = "two_args" ]; then
            if run_with_measure "$stats_file" "$exec_log" "$EXECUTABLE" "$temp_csv" "$output_file"; then
                run_status="SUCCESS"
                exit_code=0
            else
                exit_code=$?
            fi
        else
            if run_with_measure "$stats_file" "$exec_log" "$EXECUTABLE" "$temp_csv"; then
                temp_dot="${temp_csv%.csv}.dot"
                if [ -f "$temp_dot" ]; then
                    mv -f "$temp_dot" "$output_file"
                fi
                run_status="SUCCESS"
                exit_code=0
            else
                exit_code=$?
            fi
        fi
    fi

    if [ "$run_status" = "SUCCESS" ]; then
        
        # Exécution réussie
        status="SUCCESS"
        completed_tests=$((completed_tests + 1))
        
        # Récupérer les informations du fichier time
        elapsed_time=$(get_elapsed_time "$stats_file")
        if [ -z "${elapsed_time:-}" ]; then
            elapsed_time="N/A"
        fi
        max_rss_mb=$(get_max_rss_mb "$stats_file")
        
        # Calculer la taille du fichier de sortie en MB
        output_size_mb=$(get_output_size_mb "$output_file")
        
        echo "✓ Succès"
        echo "  Temps: ${elapsed_time}"
        echo "  RAM max: ${max_rss_mb} MB"
        echo "  Sortie: ${output_size_mb} MB"
        
        # Ajouter au fichier benchmark
        echo "$csv_basename | $elapsed_time | ${max_rss_mb} | ${output_size_mb} | $status | $timestamp" >> "$BENCHMARK_FILE"
        
    elif [ "$exit_code" -eq 124 ]; then
        # Timeout
        status="TIMEOUT (>${TIMEOUT_SECONDS}s)"
        timeout_tests=$((timeout_tests + 1))
        
        end_time=$(date +%s)
        actual_time=$((end_time - start_time))
        
        echo "⏱ TIMEOUT atteint après ${actual_time}s"
        
        # Essayer de récupérer les stats partielles
        max_rss_mb=$(get_max_rss_mb "$stats_file")
        
        # Taille de sortie si fichier créé
        output_size_mb=$(get_output_size_mb "$output_file")
        
        echo "  RAM max: ${max_rss_mb} MB"
        echo "  Sortie: ${output_size_mb} MB"
        
        # Ajouter au fichier benchmark
        echo "$csv_basename | >${TIMEOUT_SECONDS}s | ${max_rss_mb} | ${output_size_mb} | $status | $timestamp" >> "$BENCHMARK_FILE"
        
    else
        # Erreur d'exécution
        status="ERROR"
        failed_tests=$((failed_tests + 1))
        
        echo "✗ Erreur lors de l'exécution"
        
        # Taille de sortie si fichier créé
        output_size_mb=$(get_output_size_mb "$output_file")
        
        # Ajouter au fichier benchmark
        echo "$csv_basename | ERROR | N/A | ${output_size_mb} | $status | $timestamp" >> "$BENCHMARK_FILE"
    fi
    
    # Nettoyer
    rm -f "$stats_file" "$exec_log"
    if [ -n "$temp_csv" ] && [ -f "$temp_csv" ]; then
        rm -f "$temp_csv"
    fi
    if [ -n "$temp_dot" ] && [ -f "$temp_dot" ]; then
        rm -f "$temp_dot"
    fi
    echo ""
    
done < <(find "$CSV_FOLDER" -type f -name "*.csv" | sort)

# Résumé final
echo "════════════════════════════════════════"
echo "RÉSUMÉ DES TESTS"
echo "════════════════════════════════════════"
echo "Total de tests: $total_tests"
echo "Réussis: $completed_tests"
echo "Timeouts: $timeout_tests"
echo "Erreurs: $failed_tests"
echo ""
echo "Détails complets disponibles dans: $BENCHMARK_FILE"

# Ajouter le résumé au fichier benchmark
{
    echo ""
    echo "================================================================================"
    echo "RÉSUMÉ FINAL"
    echo "================================================================================"
    echo "Date de fin: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Total de tests: $total_tests"
    echo "Réussis: $completed_tests"
    echo "Timeouts: $timeout_tests"
    echo "Erreurs: $failed_tests"
} >> "$BENCHMARK_FILE"

exit 0
