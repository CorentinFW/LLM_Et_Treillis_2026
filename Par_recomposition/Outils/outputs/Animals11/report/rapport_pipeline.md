# Rapport pipeline - Animals11

Généré le: 2026-04-11T12:54:05+02:00

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
| claude_lattice2 | 1 | 7.24 MiB | 41.20 KiB | 0 B | 0 B |
| fca4j | 1 | 35.18 MiB | 36.43 KiB | 0 B | 32.00 KiB |
| gpt53_lattice | 1 | 8.54 MiB | 70.83 KiB | 0 B | 0 B |

## Étape execution

| Dataset | Algo | Status | Elapsed(s) | RAM max | Disque max | I/O lecture | I/O écriture | Timeout | DOT copié |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Animals11 | fca4j | OK | 0.132 | 35.18 MiB | 36.43 KiB | 0 B | 32.00 KiB | no | yes |
| Animals11 | claude_lattice2 | OK | 0.069 | 7.24 MiB | 41.20 KiB | 0 B | 0 B | no | yes |
| Animals11 | gpt53_lattice | OK | 0.07 | 8.54 MiB | 70.83 KiB | 0 B | 0 B | no | yes |

## Étape normalize

| Dataset | Algo | Status | Message | DOT normalisé |
| --- | --- | --- | --- | --- |
| Animals11 | fca4j | OK | converted to full | yes |
| Animals11 | claude_lattice2 | OK | converted to full | yes |
| Animals11 | gpt53_lattice | CONVERSION_FAILED | Erreur: Cardinalité d'extension incohérente pour le nœud '1': entête=10, reconstruit=9 | no |

## Étape compare

| Dataset | Pair | Status | Equivalent |
| --- | --- | --- | --- |
| Animals11 | claude_lattice2 vs fca4j | OK | true |

## Matrice d'équivalence

- Animals11
  - claude_lattice2__vs__fca4j: True

