"""HTML parsing for the RUMO portal.

RUMO renders its line catalogue server-side into two ``<select>`` elements:

* ``#sel_linha`` on the home page — every line in the network;
* ``#rutas-select`` on ``/rumo/?codigo-linha=<code>`` — that line's sublines.

Everything else in the pipeline comes from JSON endpoints.
"""

from dataclasses import dataclass

from selectolax.parser import HTMLParser


@dataclass(frozen=True)
class ParsedLine:
    codigo_linha: str
    nome: str
    nome_completo: str


@dataclass(frozen=True)
class ParsedSubline:
    id: int
    label: str | None
    descricao: str


def _split_line_label(text: str, codigo: str) -> tuple[str, str]:
    """Split ``"011 - PIEDADE / DERBY"`` into (nome, nome_completo)."""
    full = " ".join(text.split())
    nome = full
    prefix = f"{codigo} -"
    if full.startswith(prefix):
        nome = full[len(prefix):].strip()
    return nome or full, full


def parse_lines(html: str) -> list[ParsedLine]:
    """Extract every bus line from the RUMO home page."""
    tree = HTMLParser(html)
    select = tree.css_first("select#sel_linha")
    if select is None:
        raise ValueError("select#sel_linha not found — RUMO layout may have changed")

    lines: list[ParsedLine] = []
    for option in select.css("option"):
        codigo = (option.attributes.get("value") or "").strip()
        if not codigo:
            continue  # the "Selecione uma linha" placeholder
        nome, nome_completo = _split_line_label(option.text(), codigo)
        lines.append(ParsedLine(codigo_linha=codigo, nome=nome, nome_completo=nome_completo))
    return lines


def parse_sublines(html: str) -> list[ParsedSubline]:
    """Extract the sublines of a line-detail page.

    Returns an empty list when the line has no ``#rutas-select`` (some codes in
    ``#sel_linha`` render a page without an itinerary selector).
    """
    tree = HTMLParser(html)
    select = tree.css_first("select#rutas-select")
    if select is None:
        return []

    sublines: list[ParsedSubline] = []
    for option in select.css("option"):
        raw_value = (option.attributes.get("value") or "").strip()
        if not raw_value:
            continue
        try:
            subline_id = int(raw_value)
        except ValueError:
            continue
        label = (option.attributes.get("data-label") or "").strip() or None
        descricao = " ".join(option.text().split())
        sublines.append(
            ParsedSubline(id=subline_id, label=label, descricao=descricao)
        )
    return sublines
