# Benchmark des algorithmes

## Objectif
Ce document sert de base pour mesurer le temps d'execution des algorithmes selon la taille du CSV en entree.

## Tableau principal (temps d'execution)
Unite des données : ms

la ❌ indique que l'aglo n'a pas fini en un temps données (pour l'instant 6h)

le ⚠️ indique que l'algo c'est fini (souvent trop vite) mais le résultats est faux

pour l'instant tout a était fait en c++

| Test (ordonnée) | Chatgpt5.3Codex | ClaudeSonnet4.6 | Gemini_2.5_Pro | gemini_3.1 | qwen |
|---|---|---|---|---|---|
| eg9_9.csv | 10 | 10 | ⚠️ | 0,427 | ⚠️ |
| eg20_20.csv | 57 | 46 | ⚠️ | 168 | ⚠️ |
| eg30_30.csv | 1 117 | 1 364 | ⚠️ | 6589 | ⚠️ |
| eg40_40.csv | 52 844 | 39 022 | ⚠️ | 212 435 | ⚠️ |
| eg50_50.csv | 1 356 553 | 712 440 | ⚠️ | 4 371 881 | ⚠️ |
| eg80_80.csv | ❌ | ❌ | ⚠️ | ❌ | ⚠️ |
| eg150_150.csv | ❌ | ❌ | ⚠️ | ❌ | ⚠️ |


## Information importante
- Tous les tests ont était faite sur la même machine.
- qwen a eu ces prompts en français, il faudra tout reafaire en anglais
- pour simplifier le tableau ont a pris la moyenne des temps


## Tableau des temps de fca4j 
| Test (ordonnée) | max | min 
|---|---|---|
| 9*9 | 83 max | 57 min 
| 20*20 | 168 max | 148 min 
| 30*30 | 487 max | 411 min 
| 40*40 | 1303 max | 1223 min 
| 50*50 | 6389 max | 5399 min 
| balance-scale_binarized | 47 max | 28 min 
| breast-cancer_binarized | 41 max | 31 min 
| car_binarized | 38 max | 31 min
| chess_binarized | 40 max | 30 min 
| cmc_binarized | 48 max | 33 min
| connect-4_binarized | 33 max | 25 min
| lymphography_binarized | 42 max | 28 min 
| monks-1_binarized | 54 max | 28 min 
| mushroom_binarized | 597 max | 505 min 
| nursery_binarized | 33 max | 29 min 
| plant-binarized | 31 max | 26 min 


## Tableau pour le rapport


| nom_csv | Chatgpt5.3Codex temps(s) | Chatgpt5.3Codex RAM_max(MB) | Chatgpt5.3Codex disque_sortie(MB) | Equivalent a fca4j | ClaudeSonnet4.6 temps(s) | ClaudeSonnet4.6 RAM_max(MB) | ClaudeSonnet4.6 disque_sortie(MB)| Equivalent a fca4j | Gemini_3.1 temps(s) | Gemini_3.1 RAM_max(MB) | Gemini_3.1 disque_sortie(MB)| Equivalent a fca4j | Qwen_en temps(s) | Qwen_en RAM_max(MB) | Qwen_en disque_sortie(MB) | Equivalent a fca4j | Temps fca4j (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| balance-scale_binarized.csv | ERROR | N/A | 0 | non | 0:00.31 | 5 | 0 | oui| 0:00.00 | 4 | 0 | oui| 0:00.00 | 4 | 0 | non | 0:00.04 | 
| breast-cancer_binarized.csv | ERROR | N/A | 0 |non | 0:09.90 | 18 | 1 | oui| 0:00.00 | 4 | 0 | oui| 0:00.00 | 4 | 0  | non | 0:00.04 | 
| car_binarized.csv | ERROR | N/A | 0 |non | 0:04.32 | 15 | 1 | oui| 0:00.01 | 4 | 0 | oui| 0:00.00 | 4 | 0  | non | 0:00.03 |
| chess_binarized.csv | ERROR | N/A | 0 | non | TimeOut | N/A | 0 | non| 0:00.04 | 5 | 0 | oui| 0:00.01 | 5 | 1  | non | 0:00.04 | 
| cmc_binarized.csv | ERROR | N/A | 0 |non | 3:15.14 | 207 | 6 | oui| 0:00.01 | 5 | 0 | oui| 0:00.00 | 4 | 0  | non | 0:00.04 |
| connect-4_binarized.csv | ERROR | N/A | 0 |non | TimeOut | N/A | 0 | non| 0:07.73 | 82 | 17 | oui| 0:00.17 | 45 | 34 | non | 0:00.03 |
| lymphography_binarized.csv | ERROR | N/A | 0 |non | 3:27.71 | 339 | 9 | oui| 0:00.00 | 4 | 0 | oui| 0:00.00 | 4 | 0  | non | 0:00.04 |
| monks-1_binarized.csv | ERROR | N/A | 0 |non | 0:00.48 | 7 | 1 | oui| 0:00.00 | 4 | 0 | oui| 0:00.00 | 4 | 0  | non | 0:00.04 | 
| mushrooms_binarized.csv | ERROR | N/A | 0 |non | 0:04.42 | 4 | 0 | oui| 0:00.16 | 5 | 0 | oui| 0:00.05 | 4 | 0  | non | 0:00.55 | 
| nursery_binarized.csv | ERROR | N/A | 0 |non | 9:53.76 | 1798 | 22 | oui| 0:00.32 | 8 | 1 | oui| 0:00.03 | 7 | 1  | non | 0:00.03 | 
| plants_binarized.csv | ERROR | N/A | 0 |non | TimeOut | N/A | 0 | non | 0:02.39 | 30 | 5 | oui| 0:00.07 | 19 | 11 | non | 0:00.03 | 
| eg9_9.csv | 0:00.00 | 3 | 0 | oui | 0:00.00 | 4 | 0 | oui| 0:00.00 | 4 | 0 | oui| 0:00.00 | 4 | 0 | non | 0:00.07 | 
| eg20_20.csv | 0:00.03 | 4 | 0 |oui | 0:00.05 | 4 | 0 | oui| 0:00.13 | 4 | 0 | oui| 0:00.09 | 4 | 0  | non | 0:00.16 | 
| eg30_30.csv | 0:01.16 | 5 | 1 |oui | 0:01.79 | 7 | 1 | oui| 0:07.88 | 5 | 1 | oui| 0:03.38 | 6 | 1  | non | 0:00.45 | 
| eg40_40.csv | 0:48.02 | 12 | 3 |oui | 0:40.72 | 55 | 3 | oui| 4:32.85 | 10 | 3 | oui| 1:24.59 | 18 | 4  | non | 0:01.26 |
| eg50_50.csv | TimeOut | N/A | 0 | oui |13:18.97 | 898 | 15 | oui| TimeOut | N/A | 0 | non | 25:44.04 | 72 | 20 | non | 0:05.89 |



