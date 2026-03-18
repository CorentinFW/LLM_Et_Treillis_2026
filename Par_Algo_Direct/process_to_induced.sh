#!/bin/bash

# Script pour appliquer induced_to_full_dot.py sur tous les fichiers DOT de Synthetics
# Exclut les dossiers déjà traités: 9*9, 20*20, 29*31, 30*300, 150*150, 1726*20

SYNTHETICS_DIR="Synthetics"
SCRIPT="outils/induced_to_full_dot.py"

# Dossiers à ignorer
IGNORE_DIRS=("9*9" "20*20" "29*31" "30*300" "150*150" "1726*20")

# Fonction pour vérifier si un dossier doit être ignoré
should_ignore() {
    local dir="$1"
    for ignore in "${IGNORE_DIRS[@]}"; do
        if [[ "$dir" == *"$ignore"* ]]; then
            return 0  # true (ignorer)
        fi
    done
    return 1  # false (ne pas ignorer)
}

count=0
success=0

# Parcourir tous les sous-dossiers de Synthetics
for subdir in "$SYNTHETICS_DIR"/*; do
    if [ ! -d "$subdir" ]; then
        continue
    fi
    
    subdir_name=$(basename "$subdir")
    
    # Vérifier si le dossier doit être ignoré
    if should_ignore "$subdir_name"; then
        echo "⊘ Ignoré : $subdir_name"
        continue
    fi
    
    # Chercher le fichier CSV pour déterminer le nom de base
    csv_file=$(ls "$subdir"/eg*.csv 2>/dev/null | head -1)
    if [ -z "$csv_file" ]; then
        echo "✗ Pas de fichier CSV trouvé dans $subdir"
        continue
    fi
    
    # Extraire le nom de base
    csv_basename=$(basename "$csv_file" .csv)
    
    # Fichiers d'entrée et sortie
    input_dot="$subdir/${csv_basename}.dot"
    output_dot="$subdir/${csv_basename}_induit.dot"
    
    # Vérifier que le fichier DOT d'entrée existe
    if [ ! -f "$input_dot" ]; then
        echo "✗ Fichier DOT non trouvé : $input_dot"
        continue
    fi
    
    # Vérifier si le fichier de sortie existe déjà
    if [ -f "$output_dot" ]; then
        echo "⊘ Déjà existant : $output_dot"
        continue
    fi
    
    echo "Traitement : $input_dot"
    
    # Exécuter le script Python
    python3 "$SCRIPT" "$input_dot" "$output_dot"
    
    if [ $? -eq 0 ]; then
        echo "  ✓ Généré : $output_dot"
        ((success++))
    else
        echo "  ✗ Erreur lors du traitement de $input_dot"
    fi
    
    ((count++))
done

echo ""
echo "Résumé : $success/$count fichiers traités avec succès"
