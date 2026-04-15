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