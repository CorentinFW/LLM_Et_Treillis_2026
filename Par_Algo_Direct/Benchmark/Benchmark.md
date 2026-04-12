# Benchmark des algorithmes

## Objectif
Ce document sert de base pour mesurer le temps d'execution des algorithmes selon la taille du CSV en entree.

## Tableau principal (temps d'execution)
Unite conseillee: `ms` (ou `s`, mais rester coherent sur toute la feuille).

| Test (ordonnée) | Chatgpt5.3Codex | ClaudeSonnet4.6 | Gemini_2.5_Pro | gemini_3.1 | qwen | Notes |
|---|---|---|---|---|---|---|
| Animals11.csv |  |  |  |  |  |  |
| eg9_9.csv |  |  |  |  |  |  |
| eg20_20.csv |  |  |  |  |  |  |
| eg30_30.csv |  |  |  |  |  |  |
| eg40_40.csv |  |  |  |  |  |  |
| eg50_50.csv |  |  |  |  |  |  |
| eg80_80.csv |  |  |  |  |  |  |
| eg150_150.csv |  |  |  |  |  |  |
| Test supplementaire 1 |  |  |  |  |  |  |
| Test supplementaire 2 |  |  |  |  |  |  |
| Test supplementaire 3 |  |  |  |  |  |  |

## Variante (plusieurs essais)
Copier ce bloc si tu veux faire des moyennes (Ex: 3 a 10 executions par test).

| Test | LLM | Essai 1 | Essai 2 | Essai 3 | Moyenne | Ecart-type | Notes |
|---|---|---|---|---|---|---|---|
| eg20_20.csv |  |  |  |  |  |  |  |
| eg30_30.csv |  |  |  |  |  |  |  |
| eg40_40.csv |  |  |  |  |  |  |  |

## Rappels
- Garder la meme machine, meme configuration et meme version des executables pour comparer proprement.
- Mesurer au moins 3 fois chaque test pour lisser les variations.
- Noter tout changement de compilation, flags, ou format d'entree dans la colonne Notes.
