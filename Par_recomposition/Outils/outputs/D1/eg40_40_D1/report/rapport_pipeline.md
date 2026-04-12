# Rapport pipeline - eg40_40_D1

Généré le: 2026-04-11T10:30:58+02:00

## Résumé global

- Cas execution: 3
- Cas normalize: 3
- Paires compare: 3
- Timeouts: 0

## Ressources par algorithme

- RAM = RSS maximum observé pendant l'exécution.
- Disque = taille récursive maximale du répertoire de travail du dataset surveillé.
- I/O = volumes lus/écrits observés via /proc pendant l'exécution.

| Algo | Cas | RAM max | Disque max | I/O lecture max | I/O écriture max |
| --- | --- | --- | --- | --- | --- |
| claude_lattice2 | 1 | 29.37 MiB | 18.52 MiB | 0 B | 3.70 MiB |
| fca4j | 1 | 259.65 MiB | 6.78 MiB | 0 B | 96.00 KiB |
| gpt53_lattice | 1 | 25.29 MiB | 22.69 MiB | 16.00 KiB | 57.87 MiB |

## Étape execution

| Dataset | Algo | Status | Elapsed(s) | RAM max | Disque max | I/O lecture | I/O écriture | Timeout | DOT copié |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eg40_40 | fca4j | OK | 0.658 | 259.65 MiB | 6.78 MiB | 0 B | 96.00 KiB | no | yes |
| eg40_40 | claude_lattice2 | OK | 9.48 | 29.37 MiB | 18.52 MiB | 0 B | 3.70 MiB | no | yes |
| eg40_40 | gpt53_lattice | OK | 187.736 | 25.29 MiB | 22.69 MiB | 16.00 KiB | 57.87 MiB | no | yes |

## Étape normalize

| Dataset | Algo | Status | Message | DOT normalisé |
| --- | --- | --- | --- | --- |
| eg40_40 | fca4j | OK | converted to full | yes |
| eg40_40 | claude_lattice2 | OK | converted to full | yes |
| eg40_40 | gpt53_lattice | OK | converted to full | yes |

## Étape compare

| Dataset | Pair | Status | Equivalent |
| --- | --- | --- | --- |
| eg40_40 | claude_lattice2 vs fca4j | OK | true |
| eg40_40 | claude_lattice2 vs gpt53_lattice | OK | true |
| eg40_40 | fca4j vs gpt53_lattice | OK | true |

## Matrice d'équivalence

- eg40_40
  - claude_lattice2__vs__fca4j: True
  - claude_lattice2__vs__gpt53_lattice: True
  - fca4j__vs__gpt53_lattice: True

