#!/bin/bash

# Script auto_test.sh
# Compare les fichiers .dot de deux dossiers en les convertissant d'abord en format "full"
# Utilise induced_to_full_dot.py et compare_lattices.py

set -e

# Vérifier que deux paramètres sont fournis
if [[ $# -ne 2 ]]; then
    echo "Usage: $0 <dossier1> <dossier2>"
    echo ""
    echo "Description:"
    echo "  Compare les fichiers .dot de même nom dans deux dossiers."
    echo "  Chaque fichier est d'abord converti en format 'full' (complet) en utilisant induced_to_full_dot.py,"
    echo "  puis les versions complètes sont comparées avec compare_lattices.py."
    exit 1
fi

FOLDER1="$1"
FOLDER2="$2"

# Convertir les dossiers en chemins absolus
FOLDER1="$(cd "$FOLDER1" && pwd)"
FOLDER2="$(cd "$FOLDER2" && pwd)"

# Vérifier que les dossiers existent
if [[ ! -d "$FOLDER1" ]]; then
    echo "Erreur: le dossier '$FOLDER1' n'existe pas"
    exit 1
fi

if [[ ! -d "$FOLDER2" ]]; then
    echo "Erreur: le dossier '$FOLDER2' n'existe pas"
    exit 1
fi

# Obtenir le répertoire du script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Chemins des scripts Python
INDUCED_TO_FULL="$SCRIPT_DIR/induced_to_full_dot.py"
COMPARE_LATTICES="$SCRIPT_DIR/compare_lattices.py"

# Vérifier que les scripts Python existent
if [[ ! -f "$INDUCED_TO_FULL" ]]; then
    echo "Erreur: $INDUCED_TO_FULL n'existe pas"
    exit 1
fi

if [[ ! -f "$COMPARE_LATTICES" ]]; then
    echo "Erreur: $COMPARE_LATTICES n'existe pas"
    exit 1
fi

# Créer un dossier temporaire pour les fichiers "full"
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

echo "Dossier temporaire: $TEMP_DIR"
echo ""

# Compter les fichiers comparés
TOTAL_COMPARISONS=0
EQUIVALENT_COUNT=0

# Chercher tous les fichiers .dot de manière récursive dans les sous-dossiers
while IFS= read -r DOT_FILE1; do
    [[ -z "$DOT_FILE1" ]] && continue
    
    # Obtenir le chemin relatif par rapport au FOLDER1
    RELATIVE_PATH="${DOT_FILE1#$FOLDER1/}"
    
    # Construire le chemin correspondant dans FOLDER2
    DOT_FILE2="$FOLDER2/$RELATIVE_PATH"
    
    if [[ ! -f "$DOT_FILE2" ]]; then
        echo "⚠ Fichier non trouvé: $RELATIVE_PATH dans dossier2"
        continue
    fi
    
    # Obtenir le nom de base du fichier (sans extension)
    FILENAME_NO_EXT="${RELATIVE_PATH%.*}"
    # Remplacer les '/' par '_' pour créer un nom unique
    TEMP_NAME=$(echo "$FILENAME_NO_EXT" | sed 's/\//_/g')
    
    # Chemins pour les fichiers "full"
    FULL_FILE1="$TEMP_DIR/${TEMP_NAME}_full.dot"
    FULL_FILE2="$TEMP_DIR/${TEMP_NAME}_full_2.dot"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Traitement: $RELATIVE_PATH"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Convertir les fichiers en format "full"
    echo -n "  ► Conversion dossier 1... "
    if timeout 10 python3 "$INDUCED_TO_FULL" "$DOT_FILE1" "$FULL_FILE1" >/dev/null 2>&1; then
        echo "✓"
    else
        echo "✗ (timeout ou erreur)"
        continue
    fi
    
    echo -n "  ► Conversion dossier 2... "
    if timeout 10 python3 "$INDUCED_TO_FULL" "$DOT_FILE2" "$FULL_FILE2" >/dev/null 2>&1; then
        echo "✓"
    else
        echo "✗ (timeout ou erreur)"
        continue
    fi
    
    # Comparer les fichiers
    echo "  ► Comparaison des fichiers complets..."
    if python3 "$COMPARE_LATTICES" "$FULL_FILE1" "$FULL_FILE2" --simple >/dev/null 2>&1; then
        echo "    ✅ Les treillis sont équivalents"
        ((EQUIVALENT_COUNT++))
    else
        echo "    ❌ Les treillis sont différents"
    fi
    
    ((TOTAL_COMPARISONS++))
    echo ""
done < <(find "$FOLDER1" -name "*.dot" -type f | grep -v "_full\.dot" | grep -v "_induit\.dot")
