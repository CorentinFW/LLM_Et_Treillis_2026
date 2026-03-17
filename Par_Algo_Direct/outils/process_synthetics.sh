#!/bin/bash

# Ce script traite tous les fichiers CSV de Synthetics
# Il génère les fichiers .dot avec FCA4J et les convertit en PDF

# Répertoires
SYNTHETICS_DIR="../Synthetics"
FCA4J_DIR="../FCA4J"
JAR_FILE="$FCA4J_DIR/fca4j-cli-0.4.4.jar"

# Vérification que FCA4J est présent
if [ ! -f "$JAR_FILE" ]; then
    echo "Erreur : $JAR_FILE non trouvé"
    exit 1
fi

# Compteur
count=0

# Parcourir tous les sous-dossiers de Synthetics (triés numériquement du petit au grand)
while IFS= read -r subdir; do
    if [ ! -d "$subdir" ]; then
        continue
    fi
    
    # Parcourir tous les CSV dans le sous-dossier
    for csv_file in "$subdir"/*.csv; do
        if [ ! -f "$csv_file" ]; then
            continue
        fi
        
        # Extraire le nom de base (sans extension)
        csv_basename=$(basename "$csv_file" .csv)
        subdir_name=$(basename "$subdir")
        
        # Noms des fichiers de sortie (dans le même répertoire que le CSV)
        dot_file="$subdir/${csv_basename}.dot"
        
        echo "Traitement : $csv_file"
        
        # Générer le fichier DOT avec FCA4J
        java -jar "$JAR_FILE" LATTICE "$csv_file" -i CSV -s SEMICOLON -g "$dot_file"
        
        if [ $? -eq 0 ]; then
            echo "  ✓ DOT généré : $dot_file"
            ((count++))
        else
            echo "  ✗ Erreur lors de la génération DOT pour $csv_file"
        fi
    done
done < <(find "$SYNTHETICS_DIR" -maxdepth 1 -type d ! -path "$SYNTHETICS_DIR" | sort -V)

echo ""
echo "Traitement terminé : $count fichiers traités avec succès"
