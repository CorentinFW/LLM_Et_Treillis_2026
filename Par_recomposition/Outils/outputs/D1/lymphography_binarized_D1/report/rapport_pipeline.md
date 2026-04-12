# Rapport pipeline - lymphography_binarized_D1

Généré le: 2026-04-11T12:58:41+02:00

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
| claude_lattice2 | 1 | 7.07 MiB | 38.14 KiB | 0 B | 0 B |
| fca4j | 1 | 36.11 MiB | 38.14 KiB | 8.00 KiB | 32.00 KiB |
| gpt53_lattice | 1 | 8.53 MiB | 19.21 KiB | 0 B | 0 B |

## Étape execution

| Dataset | Algo | Status | Elapsed(s) | RAM max | Disque max | I/O lecture | I/O écriture | Timeout | DOT copié |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lymphography_binarized | fca4j | OK | 0.131 | 36.11 MiB | 38.14 KiB | 8.00 KiB | 32.00 KiB | no | yes |
| lymphography_binarized | claude_lattice2 | OK | 0.074 | 7.07 MiB | 38.14 KiB | 0 B | 0 B | no | yes |
| lymphography_binarized | gpt53_lattice | FAILED | 0.076 | 8.53 MiB | 19.21 KiB | 0 B | 0 B | no | no |

## Étape normalize

| Dataset | Algo | Status | Message | DOT normalisé |
| --- | --- | --- | --- | --- |
| lymphography_binarized | fca4j | OK | converted to full | yes |
| lymphography_binarized | claude_lattice2 | OK | converted to full | yes |
| lymphography_binarized | gpt53_lattice | MISSING_RAW_DOT | raw DOT not available from execution stage | no |

## Étape compare

| Dataset | Pair | Status | Equivalent |
| --- | --- | --- | --- |
| lymphography_binarized | claude_lattice2 vs fca4j | OK | true |

## Matrice d'équivalence

- lymphography_binarized
  - claude_lattice2__vs__fca4j: True

