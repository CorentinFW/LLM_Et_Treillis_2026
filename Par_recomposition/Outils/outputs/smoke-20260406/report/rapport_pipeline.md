# Rapport pipeline - smoke-20260406

Généré le: 2026-04-06T11:59:58+02:00

## Résumé global

- Cas execution: 3
- Cas normalize: 3
- Paires compare: 3
- Timeouts: 0

## Étape execution

| Dataset | Algo | Status | Elapsed(s) | Timeout | DOT copié |
| --- | --- | --- | --- | --- | --- |
| eg9_9 | fca4j | OK | 0.132 | no | yes |
| eg9_9 | claude_lattice2 | OK | 0.043 | no | yes |
| eg9_9 | gpt53_lattice | OK | 0.06 | no | yes |

## Étape normalize

| Dataset | Algo | Status | Message | DOT normalisé |
| --- | --- | --- | --- | --- |
| eg9_9 | fca4j | OK | converted to full | yes |
| eg9_9 | claude_lattice2 | OK | converted to full | yes |
| eg9_9 | gpt53_lattice | OK | converted to full | yes |

## Étape compare

| Dataset | Pair | Status | Equivalent |
| --- | --- | --- | --- |
| eg9_9 | claude_lattice2 vs fca4j | OK | true |
| eg9_9 | claude_lattice2 vs gpt53_lattice | OK | true |
| eg9_9 | fca4j vs gpt53_lattice | OK | true |

## Matrice d'équivalence

- eg9_9
  - claude_lattice2__vs__fca4j: True
  - claude_lattice2__vs__gpt53_lattice: True
  - fca4j__vs__gpt53_lattice: True

