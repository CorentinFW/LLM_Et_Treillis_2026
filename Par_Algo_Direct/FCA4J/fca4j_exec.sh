#!/bin/bash

# Vérification de l'argument
if [ -z "$1" ]; then
    echo "Usage: $0 <nom_de_dossier>"
    exit 1
fi

NOM="${1%/}"

# Vérification de l'existence du dossier
if [ ! -d "$NOM" ]; then
    echo "Erreur : Aucun dossier de ce nom n'a été trouvé"
    exit 1
fi

# Création du sous-dossier Lattice si nécessaire
if [ ! -d "$NOM/Lattice" ]; then
    mkdir -p "$NOM/Lattice"
fi

# Génération du treillis au format DOT
java -jar fca4j-cli-0.4.4.jar LATTICE "$NOM/$NOM.csv" -i CSV -s SEMICOLON -g "$NOM/Lattice/$NOM.dot"

# Conversion DOT vers PDF
dot -Tpdf "$NOM/Lattice/$NOM.dot" -o "$NOM/Lattice/$NOM.pdf"
