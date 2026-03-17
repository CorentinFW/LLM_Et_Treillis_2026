from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import DefaultDict, Iterable


NODE_ID_PATTERN = r'"(?:\\.|[^"])+"|[A-Za-z0-9_:.]+'
HEADER_PATTERN = re.compile(
    r'^\s*(?P<label_node_id>[^\s]+)\s*\((?P<ie>I:\s*\d+\s*,\s*E:\s*\d+)\)\s*(?P<rest>.*)$',
    flags=re.S,
)


@dataclass(frozen=True)
class NodeSignature:
    """Logical identity of a concept node, independent from its local DOT id."""

    ie_part: str
    attributes: tuple[str, ...]
    objects: tuple[str, ...]

    def canonical(self) -> str:
        return f"{self.ie_part}|{','.join(self.attributes)}|{','.join(self.objects)}"


@dataclass(frozen=True)
class NodeRecord:
    local_id: str
    raw_label: str
    signature: NodeSignature


@dataclass(frozen=True)
class DotGraph:
    path: str
    nodes_by_id: dict[str, NodeRecord]
    edges: set[tuple[str, str]]


@dataclass(frozen=True)
class ComparisonReport:
    equivalent: bool
    ambiguous: bool
    assumptions: list[str]
    node_count_file1: int
    node_count_file2: int
    edge_count_file1: int
    edge_count_file2: int
    correspondence_rows: list[dict[str, str]]
    only_in_file1: list[str]
    only_in_file2: list[str]
    ambiguous_in_file1: dict[str, list[str]]
    ambiguous_in_file2: dict[str, list[str]]
    normalized_edges_file1: list[str]
    normalized_edges_file2: list[str]
    edges_only_in_file1: list[str]
    edges_only_in_file2: list[str]


def split_dot_statements(text: str) -> list[str]:
    """Split DOT content on semicolons while preserving quoted/attribute blocks."""
    statements: list[str] = []
    buffer: list[str] = []
    in_quote = False
    escaped = False
    bracket_depth = 0

    for char in text:
        buffer.append(char)

        if in_quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_quote = False
            continue

        if char == '"':
            in_quote = True
        elif char == '[':
            bracket_depth += 1
        elif char == ']':
            bracket_depth = max(0, bracket_depth - 1)
        elif char == ';' and bracket_depth == 0:
            statement = ''.join(buffer[:-1]).strip()
            if statement:
                statements.append(statement)
            buffer = []

    tail = ''.join(buffer).strip()
    if tail:
        statements.append(tail)

    return statements


def normalize_dot_identifier(identifier: str) -> str:
    identifier = identifier.strip()
    if identifier.startswith('"') and identifier.endswith('"'):
        identifier = identifier[1:-1]
        identifier = identifier.replace(r'\"', '"')
    return identifier


def extract_label_attribute(attribute_block: str) -> str | None:
    quoted_match = re.search(r'label\s*=\s*"((?:\\.|[^"])*)"', attribute_block, flags=re.S)
    if quoted_match:
        return quoted_match.group(1)

    unquoted_match = re.search(r'label\s*=\s*([^,\]]+)', attribute_block, flags=re.S)
    if unquoted_match:
        return unquoted_match.group(1).strip()

    return None


def decode_graphviz_escapes(value: str) -> str:
    """Normalize common Graphviz line break encodings to real newlines."""
    normalized = value.replace('\r\n', '\n').replace('\r', '\n')
    normalized = re.sub(r'\\+n', '\n', normalized)
    normalized = re.sub(r'\\+l', '\n', normalized)
    return normalized


def split_non_empty_items(section: str) -> list[str]:
    items = [item.strip() for item in re.split(r'[\n|]+', section) if item.strip()]
    # Deduplicate while preserving the first semantic occurrence.
    return list(dict.fromkeys(items))


def parse_node_signature(label: str) -> NodeSignature:
    """Build a canonical signature from a Graphviz record label."""
    normalized_label = decode_graphviz_escapes(label).strip()
    if normalized_label.startswith('{') and normalized_label.endswith('}'):
        normalized_label = normalized_label[1:-1]
    normalized_label = normalized_label.strip()

    header_match = HEADER_PATTERN.match(normalized_label)
    if not header_match:
        raise ValueError(f"Impossible d'analyser l'en-tête du label: {label!r}")

    ie_part = f"({header_match.group('ie')})"
    rest = header_match.group('rest').strip()

    # The record payload is structurally '{id (I: x, E: y)|attrs|objects}'.
    # The leading local id inside the label is ignored for logical comparison.
    if rest.startswith('|'):
        rest = rest[1:]

    if '|' in rest:
        attributes_block, objects_block = rest.split('|', 1)
    else:
        attributes_block, objects_block = rest, ''

    attributes = tuple(sorted(split_non_empty_items(attributes_block)))
    objects = tuple(sorted(split_non_empty_items(objects_block)))

    counts_match = re.match(r'^\(I:\s*(\d+)\s*,\s*E:\s*(\d+)\)$', ie_part)
    if counts_match is None:
        raise ValueError(f"Partie (I, E) invalide: {ie_part}")

    attribute_count = int(counts_match.group(1))
    object_count = int(counts_match.group(2))

    if len(attributes) != attribute_count:
        raise ValueError(
            "Nombre d'attributs incohérent pour le label "
            f"{label!r}: attendu {attribute_count}, obtenu {len(attributes)}"
        )

    if len(objects) != object_count:
        raise ValueError(
            "Nombre d'objets incohérent pour le label "
            f"{label!r}: attendu {object_count}, obtenu {len(objects)}"
        )

    return NodeSignature(ie_part=ie_part, attributes=attributes, objects=objects)


def parse_dot_graph(path: Path) -> DotGraph:
    """Read a DOT lattice file and extract node records and edges."""
    text = path.read_text(encoding='utf-8')
    nodes_by_id: dict[str, NodeRecord] = {}
    edges: set[tuple[str, str]] = set()

    node_pattern = re.compile(rf'^\s*(?P<node_id>{NODE_ID_PATTERN})\s*\[(?P<attrs>.*)\]\s*$', flags=re.S)
    edge_pattern = re.compile(
        rf'^\s*(?P<src>{NODE_ID_PATTERN})\s*->\s*(?P<dst>{NODE_ID_PATTERN})\s*(?:\[(?P<attrs>[^\]]*)\])?\s*;?\s*$',
        flags=re.M,
    )

    for edge_match in edge_pattern.finditer(text):
        source = normalize_dot_identifier(edge_match.group('src'))
        target = normalize_dot_identifier(edge_match.group('dst'))
        edges.add((source, target))

    for statement in split_dot_statements(text):
        stripped = statement.strip()
        if not stripped or stripped.startswith('digraph') or stripped in {'{', '}'}:
            continue

        node_match = node_pattern.match(stripped)
        if not node_match:
            continue

        node_id = normalize_dot_identifier(node_match.group('node_id'))
        label = extract_label_attribute(node_match.group('attrs'))
        if label is None or '(I:' not in label:
            continue

        signature = parse_node_signature(label)
        nodes_by_id[node_id] = NodeRecord(local_id=node_id, raw_label=label, signature=signature)

    return DotGraph(path=str(path), nodes_by_id=nodes_by_id, edges=edges)


def group_ids_by_signature(graph: DotGraph) -> dict[str, list[str]]:
    grouped: DefaultDict[str, list[str]] = defaultdict(list)
    for node_id, node in graph.nodes_by_id.items():
        grouped[node.signature.canonical()].append(node_id)

    for node_ids in grouped.values():
        node_ids.sort()

    return dict(grouped)


def extract_ambiguous_signatures(grouped: dict[str, list[str]]) -> dict[str, list[str]]:
    return {signature: ids for signature, ids in grouped.items() if len(ids) > 1}


def build_correspondence_rows(
    grouped_file1: dict[str, list[str]],
    grouped_file2: dict[str, list[str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    common_signatures = sorted(set(grouped_file1) & set(grouped_file2))

    for index, signature in enumerate(common_signatures, start=1):
        ids_file1 = grouped_file1[signature]
        ids_file2 = grouped_file2[signature]
        if len(ids_file1) != 1 or len(ids_file2) != 1:
            continue
        rows.append({
            'Commun': f'C{index}',
            'fichier1': ids_file1[0],
            'fichier2': ids_file2[0],
            'signature': signature,
        })

    return rows


def build_common_id_maps(correspondence_rows: Iterable[dict[str, str]]) -> tuple[dict[str, str], dict[str, str]]:
    id_map_file1: dict[str, str] = {}
    id_map_file2: dict[str, str] = {}
    for row in correspondence_rows:
        common_id = row['Commun']
        id_map_file1[row['fichier1']] = common_id
        id_map_file2[row['fichier2']] = common_id
    return id_map_file1, id_map_file2


def normalize_edges(graph: DotGraph, id_map: dict[str, str]) -> set[tuple[str, str]]:
    normalized: set[tuple[str, str]] = set()
    for source, target in graph.edges:
        if source not in id_map or target not in id_map:
            missing = source if source not in id_map else target
            raise ValueError(
                f"L'arête {source!r} -> {target!r} du fichier {graph.path} référence un nœud non apparié: {missing!r}"
            )
        normalized.add((id_map[source], id_map[target]))
    return normalized


def compare_lattices(file1: Path, file2: Path) -> ComparisonReport:
    graph1 = parse_dot_graph(file1)
    graph2 = parse_dot_graph(file2)

    grouped_file1 = group_ids_by_signature(graph1)
    grouped_file2 = group_ids_by_signature(graph2)

    only_in_file1 = sorted(set(grouped_file1) - set(grouped_file2))
    only_in_file2 = sorted(set(grouped_file2) - set(grouped_file1))
    ambiguous_in_file1 = extract_ambiguous_signatures(grouped_file1)
    ambiguous_in_file2 = extract_ambiguous_signatures(grouped_file2)
    ambiguous = bool(ambiguous_in_file1 or ambiguous_in_file2)

    correspondence_rows = build_correspondence_rows(grouped_file1, grouped_file2)

    normalized_edges_file1: list[str] = []
    normalized_edges_file2: list[str] = []
    edges_only_in_file1: list[str] = []
    edges_only_in_file2: list[str] = []

    nodes_fully_match = not only_in_file1 and not only_in_file2 and not ambiguous

    if nodes_fully_match:
        id_map_file1, id_map_file2 = build_common_id_maps(correspondence_rows)
        edge_set_file1 = normalize_edges(graph1, id_map_file1)
        edge_set_file2 = normalize_edges(graph2, id_map_file2)

        normalized_edges_file1 = [f'{source} -> {target}' for source, target in sorted(edge_set_file1)]
        normalized_edges_file2 = [f'{source} -> {target}' for source, target in sorted(edge_set_file2)]
        edges_only_in_file1 = sorted(set(normalized_edges_file1) - set(normalized_edges_file2))
        edges_only_in_file2 = sorted(set(normalized_edges_file2) - set(normalized_edges_file1))

        equivalent = not edges_only_in_file1 and not edges_only_in_file2
    else:
        equivalent = False

    assumptions = [
        "Chaque nœud logique du treillis possède une signature canonique unique dans un fichier donné.",
        "Les labels de concepts suivent la structure Graphviz record '{id (I: x, E: y)|attributs|objets}'.",
        "Les différences de formatage (ordre des attributs/objets, sauts de ligne, espaces, \\n) ne changent pas le contenu logique.",
    ]

    return ComparisonReport(
        equivalent=equivalent,
        ambiguous=ambiguous,
        assumptions=assumptions,
        node_count_file1=len(graph1.nodes_by_id),
        node_count_file2=len(graph2.nodes_by_id),
        edge_count_file1=len(graph1.edges),
        edge_count_file2=len(graph2.edges),
        correspondence_rows=correspondence_rows,
        only_in_file1=only_in_file1,
        only_in_file2=only_in_file2,
        ambiguous_in_file1=ambiguous_in_file1,
        ambiguous_in_file2=ambiguous_in_file2,
        normalized_edges_file1=normalized_edges_file1,
        normalized_edges_file2=normalized_edges_file2,
        edges_only_in_file1=edges_only_in_file1,
        edges_only_in_file2=edges_only_in_file2,
    )


def print_human_report(report: ComparisonReport, file1: Path, file2: Path) -> None:
    verdict = 'Les deux treillis sont équivalents.' if report.equivalent else 'Les deux treillis sont différents.'
    print(verdict)
    print()
    print('Correspondance des nœuds:')
    if report.correspondence_rows:
        print('| Commun | fichier1 | fichier2 |')
        print('|--------|----------|----------|')
        for row in report.correspondence_rows:
            print(f"| {row['Commun']} | {row['fichier1']} | {row['fichier2']} |")
    else:
        print('(aucune correspondance exploitable)')

    print()
    print(f'Signatures présentes seulement dans {file1}:')
    print(report.only_in_file1 or ['aucune'])
    print(f'Signatures présentes seulement dans {file2}:')
    print(report.only_in_file2 or ['aucune'])

    print()
    print(f'Signatures ambiguës dans {file1}:')
    print(report.ambiguous_in_file1 or {'aucune': []})
    print(f'Signatures ambiguës dans {file2}:')
    print(report.ambiguous_in_file2 or {'aucune': []})

    print()
    print(f"Nombre d'arêtes normalisées dans fichier1 : {len(report.normalized_edges_file1)}")
    print(f"Nombre d'arêtes normalisées dans fichier2 : {len(report.normalized_edges_file2)}")
    print('Arêtes présentes seulement dans fichier1:')
    print(report.edges_only_in_file1 or ['aucune'])
    print('Arêtes présentes seulement dans fichier2:')
    print(report.edges_only_in_file2 or ['aucune'])


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            'Compare deux treillis Graphviz .dot à renumérotation des nœuds près, '
            'à partir de signatures canoniques de concepts.'
        )
    )
    parser.add_argument(
        'file1',
        help='Chemin du premier fichier .dot',
    )
    parser.add_argument(
        'file2',
        help='Chemin du second fichier .dot',
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Affiche le rapport complet au format JSON.',
    )
    parser.add_argument(
        '--simple',
        action='store_true',
        help="Affiche uniquement le verdict d'équivalence.",
    )
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    file1 = Path(args.file1)
    file2 = Path(args.file2)

    report = compare_lattices(file1, file2)

    if args.json and args.simple:
        parser.error('Les options --json et --simple sont mutuellement exclusives.')

    if args.simple:
        print('Les deux treillis sont équivalents.' if report.equivalent else 'Les deux treillis sont différents.')
    elif args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print_human_report(report, file1, file2)

    return 0 if report.equivalent else 1


if __name__ == '__main__':
    raise SystemExit(main())
