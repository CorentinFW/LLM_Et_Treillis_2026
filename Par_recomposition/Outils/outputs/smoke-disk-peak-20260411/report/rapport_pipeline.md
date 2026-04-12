# Rapport pipeline - smoke-disk-peak-20260411

Généré le: 2026-04-11T14:10:38+02:00

## Résumé global

- Cas execution: 2
- Cas normalize: 2
- Paires compare: 1
- Timeouts: 0

## Ressources par algorithme

- RAM = RSS maximum observé pendant l'exécution.
- Disque = pic du surcroît d'espace occupé par les fichiers écrits pendant l'exécution (par rapport à l'état initial du dataset surveillé).
- I/O = volumes lus/écrits observés via /proc pendant l'exécution.

| Algo | Cas | RAM max | Disque max | I/O lecture max | I/O écriture max |
| --- | --- | --- | --- | --- | --- |
| claude_lattice2 | 1 | 7.34 MiB | 0 B | 0 B | 0 B |
| gpt53_lattice | 1 | 7.39 MiB | 0 B | 0 B | 0 B |

## Étape execution

| Dataset | Algo | Status | Elapsed(s) | RAM max | Disque max | I/O lecture | I/O écriture | Timeout | DOT copié |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eg9_9 | claude_lattice2 | OK | 0.065 | 7.34 MiB | 0 B | 0 B | 0 B | no | yes |
| eg9_9 | gpt53_lattice | OK | 0.065 | 7.39 MiB | 0 B | 0 B | 0 B | no | yes |

## Étape normalize

| Dataset | Algo | Status | Message | DOT normalisé |
| --- | --- | --- | --- | --- |
| eg9_9 | claude_lattice2 | OK | converted to full | yes |
| eg9_9 | gpt53_lattice | OK | converted to full | yes |

## Étape compare

| Dataset | Pair | Status | Equivalent |
| --- | --- | --- | --- |
| eg9_9 | claude_lattice2 vs gpt53_lattice | OK | true |

## Matrice d'équivalence

- eg9_9
  - claude_lattice2__vs__gpt53_lattice: True

