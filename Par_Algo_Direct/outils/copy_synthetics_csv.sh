#!/bin/bash

# Script pour copier les fichiers CSV de Synthetics dans un dossier cible
# Condition : uniquement les dossiers qui possèdent un fichier .dot induit
# Utilisation : ./copy_synthetics_csv.sh <dossier_cible>

if [ $# -ne 1 ]; then
    echo "Utilisation : $0 <dossier_cible>"
    echo "  <dossier_cible> : dossier où copier les fichiers CSV"
    exit 1
fi

TARGET_DIR="$1"
SYNTHETICS_DIR="Synthetics"

# Vérifier que le dossier cible existe
if [ ! -d "$TARGET_DIR" ]; then
    echo "Erreur : le dossier cible '$TARGET_DIR' n'existe pas"
    exit 1
fi

count=0
success=0

# Parcourir tous les sous-dossiers de Synthetics
for subdir in "$SYNTHETICS_DIR"/*; do
    if [ ! -d "$subdir" ]; then
        continue
    fi
    
    subdir_name=$(basename "$subdir")
    
    # Chercher un fichier .dot avec le suffixe _induit
    induit_dot=$(ls "$subdir"/*_induit.dot 2>/dev/null | head -1)
    
    if [ -z "$induit_dot" ]; then
        continue
    fi
    
    # Chercher le fichier CSV correspondant
    csv_file=$(ls "$subdir"/eg*.csv 2>/dev/null | head -1)
    
    if [ -z "$csv_file" ]; then
        echo "✗ Pas de fichier CSV trouvé dans $subdir (malgré la présence de $induit_dot)"
        continue
    fi
    
    csv_basename=$(basename "$csv_file")
    
    # Créer le dossier XX*YY dans le dossier cible s'il n'existe pas
    target_subdir="$TARGET_DIR/$subdir_name"
    if [ ! -d "$target_subdir" ]; then
        mkdir -p "$target_subdir"
    fi
    
    target_file="$target_subdir/$csv_basename"
    
    echo "Copie : $csv_file"
    
    # Copier le fichier CSV dans le dossier cible/XX*YY/
    cp "$csv_file" "$target_file"
    
    if [ $? -eq 0 ]; then
        echo "  ✓ Copié dans : $target_file"
        ((success++))
    else
        echo "  ✗ Erreur lors de la copie de $csv_file"
    fi
    
    ((count++))
done

echo ""
echo "Résumé : $success/$count fichiers CSV copiés avec succès"
