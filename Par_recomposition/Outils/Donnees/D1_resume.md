# Résumé - Compilation D1

Analyser l'ensemble de la compilation D1 en distinguant clairement: 
1. la validité des sorties (équivalence), 
2. la performance (temps), 
3. les ressources (RAM, disque, I/O)

Toutes les conclusions faites ne sont valables que sur les datasets testés ici, les algorithmes ont été écrits en Python avec GitHub Copilot ce qui pourrait avantager certains LLM.

## Périmètre et indicateurs
- Source analysée: `Outils/Donnees/D1.md`.
- Nombre de datasets: 16.
- Algorithmes comparés: `fca4j`, `claude_lattice2.py`, `gpt53_lattice.py`.
- Indicateurs utilisés: statut d'exécution, équivalence des treillis, temps d'exécution, RAM maximale, occupation disque, volumes d'I/O.
- Chaque algorithme a été lancé une seule fois sur chacun des datasets.
- Système d'exploitation: Linux (EXT4).
- Matériel :
  - **CPU** : Intel Core i5-13600H (13e génération, 12 cores, 16 threads, 4.8 GHz max).
  - **RAM** : 16 GiB DDR5 SODIMM 5600 MHz.
  - **Disque** : NVMe Samsung PM9B1 512 GB (476 GiB utilisable).
  - **GPU** : NVIDIA (discrète) + Intel Iris Xe (intégrée).
  - **Machine** : Dell Precision 3581 (notebook). 

## Résultats principaux

### 1) Validite et robustesse
- `fca4j`: 16/16 exécutions réussies; normalisation réussie sur tous les jeux.
- `claude_lattice2`: 16/16 exécutions réussies; normalisation réussie sur tous les jeux.
- `gpt53_lattice`: 6/16 exécutions réussies (échec sur 10 jeux, majoritairement `MISSING_RAW_DOT`), il réussit sur les datasets générés mais pas sur les datasets réels.
- Équivalence des treillis:
  - Pour tous les jeux où la comparaison est possible, `claude_lattice2` est équivalent à `fca4j`.
  - Sur les jeux `eg9_9` à `eg50_50`, les 3 algorithmes sont équivalents (comparaisons complètes OK).
  - Cas notable: `mushrooms_binarized`, exécution de `gpt53_lattice` OK mais normalisation échouée (`CONVERSION_FAILED`), soit la conversion a échoué soit l'algorithme a créé un DOT dans un format inattendu.

### 2) Performance temporelle
- Jeux petits à moyens (ex. `balance-scale_binarized`, `car_binarized`, `chess_binarized`):
  - `claude_lattice2` est généralement plus rapide que `fca4j`.
- Jeux plus structurés (`eg30_30` et au-delà):
  - `fca4j` devient nettement dominant en temps.
  - Exemples:
    - `eg40_40`: `fca4j` 0.658 s vs `claude_lattice2` 9.48 s vs `gpt53_lattice` 187.736 s.
    - `eg50_50`: `fca4j` 3.075 s vs `claude_lattice2` 175.97 s vs `gpt53_lattice` 3515.269 s.
- Lecture globale: `fca4j` présente la meilleure scalabilité temporelle quand la taille/complexité augmente.

### 3) Empreinte mémoire et disque
- RAM maximale:
  - `fca4j` est le plus coûteux en mémoire (jusqu'à 822.12 MiB sur `eg50_50`).
  - `claude_lattice2` et `gpt53_lattice` restent nettement plus bas en RAM sur les grands jeux.
- Disque/I-O:
  - `gpt53_lattice` et `claude_lattice2` montrent des écritures plus élevées par rapport à celles de `fca4j`, ce qui était attendu, même si la manière de vérifier l'I/O ici n'est pas encore fiable (sera modifiée plus tard)
  - `claude_lattice2` écrit davantage que `fca4j` sur plusieurs grands jeux, mais reste très inférieur à `gpt53_lattice` dans les cas extrêmes.

## Interprétation
- Le couple `fca4j`/`claude_lattice2` est fonctionnellement fiable (sorties équivalentes quand comparées).
- Le choix algorithmique dépend d'un compromis:
  - `fca4j`: meilleure performance temps à grande échelle, au prix d'une RAM plus élevée.
  - `claude_lattice2`: très bonne robustesse, RAM plus modérée, mais dégradation temporelle nette sur gros jeux.
  - `gpt53_lattice`: faible robustesse globale sur ce benchmark (taux d'échec élevé), et comportement de scalabilité défavorable sur grands jeux malgré une RAM contenue.

## Conclusion opérationnelle
Pour un usage production sur jeux de taille variable, `fca4j` apparaît comme la référence de performance robuste, sous réserve d'une capacité mémoire suffisante. `claude_lattice2` constitue une alternative fiable sur petits/moyens jeux ou en contexte contraint en RAM. `gpt53_lattice` nécessite une stabilisation dans la génération DOT et maîtrise des I/O avant usage compétitif.

## Points à améliorer pour le prochain benchmark

### Méthodologie expérimentale
- **Répétitions** : Conduire au minimum 3–5 répétitions par test pour mesurer variabilité et stabilité.
- **Statistiques** : Rapporter médiane, écart-type, et intervalles de confiance (95%).

### Reproductibilité et traçabilité
- **Versions logicielles** : Documenter les versions exactes (JVM pour fca4j, Python, dépendances pip, versions LLM/API si applicable).
- **Configuration** : Expliciter paramètres algorithmiques (recherche en profondeur/largeur, heuristiques, seuils) et stratégie de réglage (fixes vs optimisés).

### Validité des mesures
- **Fiabilisation I/O** : Préciser méthode d'instrumentation I/O (strace, cgroups, /proc), valider cohérence avec occupation disque observée.
- **Temps CPU vs wall-clock** : Rapporter les deux ; documenter si mono/multi-thread et nombre de threads utilisés.
- **Timeout gestion** : Expliciter seuils timeout, éventuels cas limite (eg : pourquoi gpt53 échoue sur réels ?).

### Validité de la comparaison de treillis
- **Critère d'équivalence** : Définir formellement (isomorphisme structurel, ordre des nœuds, canonical form générée).
- **Algorithme de comparaison** : Décrire la méthode exacte (graphe-isomorphe library, normalization DOT).
- **Cas ambigus** : Expliciter traitement des cas CONVERSION_FAILED (mushrooms) : rejet vs ajustement.

### Documentations des données
- **Métadonnées dataset** : Pour chaque jeu, documenter : source, taille (nombre d'objets×attributs), densité, type (réel vs synthétique), contexte applicatif.
- **Réal vs synthétique** : Justifier partition datasets réels/générés et impact attendu sur performance.
- **Format binarisé** : Expliquer prétraitements (seuillage, discrétisation) si applicable.

### Menaces à la validité
- **Biais d'implémentation** : Reconnaître que fca4j (Java optimisé) vs LLM (Python) crée inégalité de base ; explorer trade-off si possible.
- **Biais de sélection dataset** : Justifier choix des 16 jeux (représentation, taille, complexité inhérente).
- **Validité externe** : Clarifier si résultats généralisent à domaines au-delà des datasets testés.

### Présentation et exploitabilité
- **Scalabilité visuelle** : Ajouter graphiques (temps/RAM vs taille dataset) plutôt que tables seules.
- **Détails statistiques** : Fournir tableaux étendus avec min/max/stddev pour chaque métrique.
- **Artefacts** : Partager scripts lancement, configurations, rapports bruts pour transparence totale.
