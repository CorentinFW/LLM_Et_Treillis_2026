# Rapport pipeline - car_binarized_D1

Généré le: 2026-04-11T12:56:33+02:00

## Résumé global

- Cas execution: 3
- Cas normalize: 3
- Paires compare: 1
- Timeouts: 0

## Ressources par algorithme

- RAM = RSS maximum observé pendant l'exécution.
- Disque = taille récursive maximale du répertoire de travail du dataset surveillé.
- I/O = volumes lus/écrits observés via /proc pendant l'exécution.

| Algo | Cas | RAM max | Disque max | I/O lecture max | I/O écriture max |
| --- | --- | --- | --- | --- | --- |
| claude_lattice2 | 1 | 8.20 MiB | 238.50 KiB | 0 B | 0 B |
| fca4j | 1 | 37.13 MiB | 238.50 KiB | 0 B | 32.00 KiB |
| gpt53_lattice | 1 | 10.30 MiB | 158.48 KiB | 0 B | 0 B |

## Étape execution

| Dataset | Algo | Status | Elapsed(s) | RAM max | Disque max | I/O lecture | I/O écriture | Timeout | DOT copié |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| car_binarized | fca4j | OK | 0.126 | 37.13 MiB | 238.50 KiB | 0 B | 32.00 KiB | no | yes |
| car_binarized | claude_lattice2 | OK | 0.074 | 8.20 MiB | 238.50 KiB | 0 B | 0 B | no | yes |
| car_binarized | gpt53_lattice | FAILED | 0.081 | 10.30 MiB | 158.48 KiB | 0 B | 0 B | no | no |

## Étape normalize

| Dataset | Algo | Status | Message | DOT normalisé |
| --- | --- | --- | --- | --- |
| car_binarized | fca4j | OK | converted to full | yes |
| car_binarized | claude_lattice2 | OK | converted to full | yes |
| car_binarized | gpt53_lattice | MISSING_RAW_DOT | raw DOT not available from execution stage | no |

## Étape compare

| Dataset | Pair | Status | Equivalent |
| --- | --- | --- | --- |
| car_binarized | claude_lattice2 vs fca4j | OK | true |

## Matrice d'équivalence

- car_binarized
  - claude_lattice2__vs__fca4j: True

