# Rapport pipeline - eg20_20_D1

Généré le: 2026-04-11T10:25:06+02:00

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
| claude_lattice2 | 1 | 14.94 MiB | 386.06 KiB | 0 B | 116.00 KiB |
| fca4j | 1 | 54.71 MiB | 380.87 KiB | 116.00 KiB | 100.00 KiB |
| gpt53_lattice | 1 | 17.15 MiB | 799.58 KiB | 8.00 KiB | 520.00 KiB |

## Étape execution

| Dataset | Algo | Status | Elapsed(s) | RAM max | Disque max | I/O lecture | I/O écriture | Timeout | DOT copié |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eg20_20 | fca4j | OK | 0.213 | 54.71 MiB | 380.87 KiB | 116.00 KiB | 100.00 KiB | no | yes |
| eg20_20 | claude_lattice2 | OK | 0.129 | 14.94 MiB | 386.06 KiB | 0 B | 116.00 KiB | no | yes |
| eg20_20 | gpt53_lattice | OK | 0.304 | 17.15 MiB | 799.58 KiB | 8.00 KiB | 520.00 KiB | no | yes |

## Étape normalize

| Dataset | Algo | Status | Message | DOT normalisé |
| --- | --- | --- | --- | --- |
| eg20_20 | fca4j | OK | converted to full | yes |
| eg20_20 | claude_lattice2 | OK | converted to full | yes |
| eg20_20 | gpt53_lattice | OK | converted to full | yes |

## Étape compare

| Dataset | Pair | Status | Equivalent |
| --- | --- | --- | --- |
| eg20_20 | claude_lattice2 vs fca4j | OK | true |
| eg20_20 | claude_lattice2 vs gpt53_lattice | OK | true |
| eg20_20 | fca4j vs gpt53_lattice | OK | true |

## Matrice d'équivalence

- eg20_20
  - claude_lattice2__vs__fca4j: True
  - claude_lattice2__vs__gpt53_lattice: True
  - fca4j__vs__gpt53_lattice: True

