"""Static field-level lineage derived from the checked program."""

from dataclasses import dataclass

from .semantics import CheckedProgram, TypedExpression


@dataclass(frozen=True)
class LineageEdge:
    source: str
    target: str
    reason: str


@dataclass(frozen=True)
class LineageGraph:
    sources: tuple[str, ...]
    derived: tuple[str, ...]
    outputs: tuple[str, ...]
    edges: tuple[LineageEdge, ...]


def _references(expression: TypedExpression) -> set[str]:
    if expression.kind == "field":
        return {str(expression.value)}
    references: set[str] = set()
    if expression.left is not None:
        references.update(_references(expression.left))
    if expression.right is not None:
        references.update(_references(expression.right))
    return references


def build_lineage(checked: CheckedProgram) -> LineageGraph:
    edges: list[LineageEdge] = []
    derived_names = {item.symbol.name for item in checked.derivations}
    for derivation in checked.derivations:
        for source in sorted(_references(derivation.expression)):
            edges.append(LineageEdge(source, derivation.symbol.name, "derived expression"))
    for symbol in checked.selected:
        if symbol.name in derived_names:
            edges.append(LineageEdge(symbol.name, f"output.{symbol.name}", "selected derived field"))
        else:
            edges.append(LineageEdge(symbol.name, f"output.{symbol.name}", "selected source field"))
    for index, condition in enumerate(checked.conditions, 1):
        target = f"policy.{condition.kind}.{index}"
        for source in sorted(_references(condition.expression)):
            edges.append(LineageEdge(source, target, "validation or filtering dependency"))
    return LineageGraph(
        tuple(symbol.name for symbol in checked.symbols),
        tuple(item.symbol.name for item in checked.derivations),
        tuple(symbol.name for symbol in checked.selected),
        tuple(edges),
    )


def format_lineage(graph: LineageGraph) -> str:
    lines = ["VERIFLOW FIELD LINEAGE",
             "  sources: " + ", ".join(graph.sources),
             "  derived: " + (", ".join(graph.derived) or "none"),
             "  outputs: " + ", ".join(graph.outputs),
             "  edges:"]
    lines.extend(f"    {edge.source} -> {edge.target} ({edge.reason})" for edge in graph.edges)
    return "\n".join(lines)
