"""Parsing of the RUMO HTML catalogue, against captured real pages."""

import pytest

from app.etl.parsers import parse_lines, parse_sublines


def test_parse_lines_extracts_code_and_name(fixture_text):
    lines = parse_lines(fixture_text("rumo_home.html"))

    # 12 <option> elements in the fixture, one of which is the placeholder.
    assert len(lines) == 11
    first = lines[0]
    assert first.codigo_linha == "001"
    assert first.nome == "PONTE DOS CARVALHOS / PRAZERES (BARRA DE JANGADA)"
    assert first.nome_completo.startswith("001 - ")


def test_parse_lines_skips_the_placeholder_option(fixture_text):
    lines = parse_lines(fixture_text("rumo_home.html"))
    assert all(line.codigo_linha for line in lines)
    assert not any("Selecione" in line.nome for line in lines)


def test_parse_lines_raises_when_the_select_is_missing():
    with pytest.raises(ValueError, match="sel_linha"):
        parse_lines("<html><body>nada aqui</body></html>")


def test_parse_sublines_multi_variant_line(fixture_text):
    """Line 011 has four route variants — the case a single-subline
    assumption would silently get wrong."""
    sublines = parse_sublines(fixture_text("rumo_linha_011.html"))

    assert [s.id for s in sublines] == [705, 706, 1120, 1473]
    assert [s.label for s in sublines] == ["PRI", "LO1", "SHP", "LO2"]
    assert sublines[0].descricao == "Principal"
    assert sublines[1].descricao == "Atende Loreto II no sentido 1"


def test_parse_sublines_single_variant_line(fixture_text):
    sublines = parse_sublines(fixture_text("rumo_linha_115.html"))

    assert len(sublines) == 1
    assert sublines[0].id == 292
    assert sublines[0].label == "PRI"


def test_parse_sublines_collapses_whitespace(fixture_text):
    sublines = parse_sublines(fixture_text("rumo_linha_191.html"))
    descricoes = [s.descricao for s in sublines]

    assert "Atende à Maracaípe" in descricoes
    assert all("  " not in d and "\n" not in d for d in descricoes)


def test_parse_sublines_returns_empty_without_the_select():
    assert parse_sublines("<html><body>sem select</body></html>") == []
