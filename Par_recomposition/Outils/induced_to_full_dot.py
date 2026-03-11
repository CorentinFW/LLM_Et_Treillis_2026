#!/usr/bin/env python3
"""Convert a reduced/induced DOT lattice into a complete DOT lattice.

The input format targeted here is the FCA/Graphviz style used in this workspace:
- one directed graph representing a concept lattice;
- concept nodes encoded with Graphviz record labels;
- the middle record field stores reduced intent labels;
- the last record field stores reduced extent labels.

The script reconstructs the full intent and full extent of each concept and writes
an equivalent DOT file in which the labels no longer rely on induction.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


class DotFormatError(ValueError):
    """Raised when the DOT file does not match the expected lattice format."""


DOT_ID_PATTERN = r'"(?:\\.|[^"])*"|[^\s\[\]{};=,]+'
HEADER_COUNTS_PATTERN = re.compile(
    r'^\s*(?P<display_id>.*?)\s*\(\s*I\s*:\s*(?P<intent>\d+)\s*,\s*E\s*:\s*(?P<extent>\d+)\s*\)\s*$'
)
DIGRAPH_PATTERN = re.compile(r'^\s*digraph\s+(?P<name>[^\s{]+)\s*\{?', flags=re.M)
RANKDIR_PATTERN = re.compile(r'^\s*rankdir\s*=\s*(?P<value>[^;\s]+)\s*;?\s*$', flags=re.M)


@dataclass(slots=True)
class ParsedHeader:
    raw_text: str
    display_id: str | None
    intent_count: int | None
    extent_count: int | None


@dataclass(slots=True)
class Node:
    node_id: str
    raw_node_id: str
    attrs_order: list[str] = field(default_factory=list)
    attrs: dict[str, str] = field(default_factory=dict)
    header: ParsedHeader | None = None
    reduced_intent: list[str] = field(default_factory=list)
    reduced_extent: list[str] = field(default_factory=list)
    full_intent: set[str] = field(default_factory=set)
    full_extent: set[str] = field(default_factory=set)


@dataclass(slots=True)
class DotGraph:
    name: str = 'G'
    rankdir: str | None = None
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)


def normalize_dot_identifier(identifier: str) -> str:
    identifier = identifier.strip()
    if identifier.startswith('"') and identifier.endswith('"'):
        identifier = identifier[1:-1]
        identifier = identifier.replace(r'\"', '"')
    return identifier


def split_top_level(text: str, separator: str, *, keep_empty: bool = False) -> list[str]:
    """Split a DOT fragment on a separator outside double quotes."""
    parts: list[str] = []
    current: list[str] = []
    in_quote = False
    escaped = False

    for char in text:
        if in_quote:
            current.append(char)
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_quote = False
            continue

        if char == '"':
            in_quote = True
            current.append(char)
            continue

        if char == separator:
            part = ''.join(current).strip()
            if part or keep_empty:
                parts.append(part)
            current = []
        else:
            current.append(char)

    tail = ''.join(current).strip()
    if tail or keep_empty:
        parts.append(tail)
    return parts


def parse_attributes(attribute_block: str) -> tuple[dict[str, str], list[str]]:
    """Parse key=value attributes from the content of a [...] block."""
    attrs: dict[str, str] = {}
    order: list[str] = []

    if not attribute_block.strip():
        return attrs, order

    for part in split_top_level(attribute_block, ','):
        if '=' in part:
            key, value = part.split('=', 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
                value = value[1:-1]
                value = value.replace(r'\"', '"')
            attrs[key] = value
            order.append(key)
        else:
            key = part.strip()
            attrs[key] = ''
            order.append(key)

    return attrs, order


def split_non_empty_label_items(part: str) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for raw_item in part.split(r'\n'):
        item = raw_item.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        items.append(item)
    return items


def parse_record_label(label: str) -> tuple[ParsedHeader, list[str], list[str]]:
    """Parse a record label of the form {header|intent-part|extent-part}."""
    text = label.strip()
    if text.startswith('{') and text.endswith('}'):
        text = text[1:-1]

    parts = split_top_level(text, '|', keep_empty=True)
    if len(parts) != 3:
        raise DotFormatError(
            'Le label Graphviz doit contenir exactement 3 champs de record: '
            f'{label!r}'
        )

    raw_header, intent_part, extent_part = parts
    header_match = HEADER_COUNTS_PATTERN.match(raw_header.strip())
    if header_match:
        parsed_header = ParsedHeader(
            raw_text=raw_header.strip(),
            display_id=header_match.group('display_id').strip() or None,
            intent_count=int(header_match.group('intent')),
            extent_count=int(header_match.group('extent')),
        )
    else:
        parsed_header = ParsedHeader(
            raw_text=raw_header.strip(),
            display_id=raw_header.strip() or None,
            intent_count=None,
            extent_count=None,
        )

    return (
        parsed_header,
        split_non_empty_label_items(intent_part),
        split_non_empty_label_items(extent_part),
    )


def parse_dot_file(path: Path) -> DotGraph:
    """Extract graph metadata, nodes and edges from a DOT file."""
    text = path.read_text(encoding='utf-8')
    graph = DotGraph()

    digraph_match = DIGRAPH_PATTERN.search(text)
    if digraph_match:
        graph.name = normalize_dot_identifier(digraph_match.group('name'))

    rankdir_match = RANKDIR_PATTERN.search(text)
    if rankdir_match:
        graph.rankdir = rankdir_match.group('value').strip()

    node_pattern = re.compile(
        rf'^\s*(?P<node_id>{DOT_ID_PATTERN})\s*\[(?P<attrs>.*)\]\s*;?\s*$',
        flags=re.M,
    )
    edge_pattern = re.compile(
        rf'^\s*(?P<src>{DOT_ID_PATTERN})\s*->\s*(?P<dst>{DOT_ID_PATTERN})'
        rf'\s*(?:\[(?P<attrs>[^\]]*)\])?\s*;?\s*$',
        flags=re.M,
    )

    for match in node_pattern.finditer(text):
        raw_node_id = match.group('node_id').strip()
        node_id = normalize_dot_identifier(raw_node_id)
        if node_id in graph.nodes:
            raise DotFormatError(f'Nœud dupliqué: {node_id!r}')

        attrs, order = parse_attributes(match.group('attrs'))
        label = attrs.pop('label', None)
        order = [key for key in order if key != 'label']

        header: ParsedHeader | None = None
        reduced_intent: list[str] = []
        reduced_extent: list[str] = []
        if label is not None:
            header, reduced_intent, reduced_extent = parse_record_label(label)

        graph.nodes[node_id] = Node(
            node_id=node_id,
            raw_node_id=raw_node_id,
            attrs_order=order,
            attrs=attrs,
            header=header,
            reduced_intent=reduced_intent,
            reduced_extent=reduced_extent,
        )

    for match in edge_pattern.finditer(text):
        src = normalize_dot_identifier(match.group('src'))
        dst = normalize_dot_identifier(match.group('dst'))
        graph.edges.append((src, dst))

    if not graph.nodes:
        raise DotFormatError(f'Aucun nœud de concept détecté dans {path}')

    return graph


def build_adjacency(graph: DotGraph) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    succ: dict[str, list[str]] = {node_id: [] for node_id in graph.nodes}
    pred: dict[str, list[str]] = {node_id: [] for node_id in graph.nodes}

    for src, dst in graph.edges:
        if src not in graph.nodes or dst not in graph.nodes:
            raise DotFormatError(f'Arête invalide {src!r} -> {dst!r}: nœud inconnu')
        succ[src].append(dst)
        pred[dst].append(src)

    return succ, pred


def topological_sort(nodes: Iterable[str], succ: dict[str, list[str]]) -> list[str]:
    indegree = {node_id: 0 for node_id in nodes}
    for children in succ.values():
        for child in children:
            indegree[child] += 1

    queue = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    order: list[str] = []

    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        for child in sorted(succ[node_id]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    if len(order) != len(indegree):
        raise DotFormatError('Le graphe contient un cycle: ce n\'est pas un treillis orienté acyclique.')

    return order


def infer_edge_orientation(graph: DotGraph) -> str:
    """Infer whether edges go from specific concepts to general ones or the reverse."""
    forward_score = 0
    backward_score = 0

    for src, dst in graph.edges:
        src_header = graph.nodes[src].header
        dst_header = graph.nodes[dst].header
        if src_header is None or dst_header is None:
            continue
        if src_header.intent_count is None or src_header.extent_count is None:
            continue
        if dst_header.intent_count is None or dst_header.extent_count is None:
            continue

        if src_header.intent_count >= dst_header.intent_count and src_header.extent_count <= dst_header.extent_count:
            forward_score += 1
        if src_header.intent_count <= dst_header.intent_count and src_header.extent_count >= dst_header.extent_count:
            backward_score += 1

    if forward_score == backward_score:
        return 'specific_to_general'
    if forward_score > backward_score:
        return 'specific_to_general'
    return 'general_to_specific'


def reconstruct_full_labels(graph: DotGraph, orientation: str) -> None:
    succ, pred = build_adjacency(graph)
    topo_order = topological_sort(graph.nodes.keys(), succ)

    if orientation == 'specific_to_general':
        intent_sources = succ
        intent_order = reversed(topo_order)
        extent_sources = pred
        extent_order = topo_order
    elif orientation == 'general_to_specific':
        intent_sources = pred
        intent_order = topo_order
        extent_sources = succ
        extent_order = reversed(topo_order)
    else:
        raise DotFormatError(f'Orientation inconnue: {orientation}')

    for node_id in intent_order:
        node = graph.nodes[node_id]
        full_intent = set(node.reduced_intent)
        for neighbor in intent_sources[node_id]:
            full_intent.update(graph.nodes[neighbor].full_intent)
        node.full_intent = full_intent

    for node_id in extent_order:
        node = graph.nodes[node_id]
        full_extent = set(node.reduced_extent)
        for neighbor in extent_sources[node_id]:
            full_extent.update(graph.nodes[neighbor].full_extent)
        node.full_extent = full_extent


def validate_graph(graph: DotGraph, orientation: str) -> None:
    succ, pred = build_adjacency(graph)
    _ = topological_sort(graph.nodes.keys(), succ)

    for node in graph.nodes.values():
        if node.header and node.header.display_id is not None:
            display_id = normalize_dot_identifier(node.header.display_id)
            if display_id and display_id != node.node_id:
                raise DotFormatError(
                    f'Identifiant incohérent pour le nœud {node.node_id!r}: '
                    f'label={node.header.display_id!r}'
                )

        if node.header and node.header.intent_count is not None:
            if node.header.intent_count != len(node.full_intent):
                raise DotFormatError(
                    f'Cardinalité d\'intention incohérente pour le nœud {node.node_id!r}: '
                    f'entête={node.header.intent_count}, reconstruit={len(node.full_intent)}'
                )

        if node.header and node.header.extent_count is not None:
            if node.header.extent_count != len(node.full_extent):
                raise DotFormatError(
                    f'Cardinalité d\'extension incohérente pour le nœud {node.node_id!r}: '
                    f'entête={node.header.extent_count}, reconstruit={len(node.full_extent)}'
                )

    for src, dst in graph.edges:
        source = graph.nodes[src]
        target = graph.nodes[dst]
        if orientation == 'specific_to_general':
            if not target.full_intent.issubset(source.full_intent):
                raise DotFormatError(f'Monotonie des intentions violée sur {src!r} -> {dst!r}')
            if not source.full_extent.issubset(target.full_extent):
                raise DotFormatError(f'Monotonie des extensions violée sur {src!r} -> {dst!r}')
        else:
            if not source.full_intent.issubset(target.full_intent):
                raise DotFormatError(f'Monotonie des intentions violée sur {src!r} -> {dst!r}')
            if not target.full_extent.issubset(source.full_extent):
                raise DotFormatError(f'Monotonie des extensions violée sur {src!r} -> {dst!r}')

    tops = [node_id for node_id, parents in pred.items() if not parents]
    bottoms = [node_id for node_id, children in succ.items() if not children]
    if len(tops) != 1 or len(bottoms) != 1:
        raise DotFormatError(
            'Le graphe reconstruit n\'a pas un unique sommet et un unique fond: '
            f'sommets={tops}, fonds={bottoms}'
        )


def escape_record_text(value: str) -> str:
    escaped = value.replace('\\', r'\\')
    escaped = escaped.replace('"', r'\"')
    for special in ('{', '}', '|', '<', '>'):
        escaped = escaped.replace(special, '\\' + special)
    return escaped


def sort_items(items: Iterable[str]) -> list[str]:
    return sorted(set(items), key=lambda item: item.casefold())


def build_full_label(node: Node) -> str:
    intent_items = sort_items(node.full_intent)
    extent_items = sort_items(node.full_extent)
    header = f'{node.node_id} (I: {len(intent_items)}, E: {len(extent_items)})'
    intent_text = r'\n'.join(escape_record_text(item) for item in intent_items)
    extent_text = r'\n'.join(escape_record_text(item) for item in extent_items)
    return f'{{{header}|{intent_text}|{extent_text}}}'


def format_attribute(key: str, value: str) -> str:
    if value == '':
        return key
    escaped = value.replace('\\', r'\\').replace('"', r'\"')
    return f'{key}="{escaped}"'


def node_sort_key(node_id: str) -> tuple[int, int | str]:
    try:
        return (0, int(node_id))
    except ValueError:
        return (1, node_id)


def write_dot_file(graph: DotGraph, output_path: Path) -> None:
    lines: list[str] = []
    lines.append(f'digraph {graph.name} {{')
    if graph.rankdir is not None:
        lines.append(f'\trankdir={graph.rankdir};')

    for node_id in sorted(graph.nodes, key=node_sort_key):
        node = graph.nodes[node_id]
        attributes = [format_attribute(key, node.attrs[key]) for key in node.attrs_order]
        attributes.append(format_attribute('label', build_full_label(node)))
        lines.append(f'\t{node.raw_node_id} [{",".join(attributes)}];')

    for src, dst in graph.edges:
        source = graph.nodes[src].raw_node_id
        target = graph.nodes[dst].raw_node_id
        lines.append(f'\t{source} -> {target}')

    lines.append('}')
    output_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def convert_dot_file(input_path: Path, output_path: Path) -> str:
    graph = parse_dot_file(input_path)
    orientation = infer_edge_orientation(graph)
    reconstruct_full_labels(graph, orientation)
    validate_graph(graph, orientation)
    write_dot_file(graph, output_path)
    return orientation


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Transforme un treillis DOT induit en treillis DOT complet.'
    )
    parser.add_argument('input_dot', type=Path, help='Chemin du fichier DOT induit')
    parser.add_argument('output_dot', type=Path, help='Chemin du fichier DOT complet à générer')
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    try:
        orientation = convert_dot_file(args.input_dot, args.output_dot)
    except (OSError, DotFormatError) as error:
        print(f'Erreur: {error}', file=sys.stderr)
        return 1

    print(
        f'Conversion réussie: {args.input_dot} -> {args.output_dot} '
        f'(orientation détectée: {orientation})'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
