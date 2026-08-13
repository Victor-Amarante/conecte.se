"""Coordinate conversion and normalisation of RUMO payloads.

The reference point comes from RUMO's own data: the stop with nodo 19223
(Terminal de Ponte dos Carvalhos) is at UTM 25S (281302.98, 9088652.47), which
must land on the Cabo de Santo Agostinho coast.
"""

import pytest

from app.etl.transform import (
    RMR_BBOX,
    enrich_stops_from_itinerary,
    is_within_rmr,
    looks_like_terminal,
    to_wkt_linestring,
    to_wkt_point,
    transform_shape,
    transform_stops,
    transform_subline_stops,
    utm_to_wgs84,
)


class TestCoordinateConversion:
    def test_known_point_converts_to_recife_metro_area(self):
        lat, lon = utm_to_wgs84(281302.97866523557, 9088652.471504372)

        assert lat == pytest.approx(-8.239764, abs=1e-5)
        assert lon == pytest.approx(-34.985355, abs=1e-5)

    def test_inventory_reference_point(self):
        """First row of json_mapa_paradas, verified against RUMO's own map."""
        lat, lon = utm_to_wgs84(292036.273506116, 9105626.468489692)

        assert lat == pytest.approx(-8.086781, abs=1e-5)
        assert lon == pytest.approx(-34.887233, abs=1e-5)

    def test_conversion_is_ordered_easting_then_northing(self):
        """always_xy=True: swapping the arguments must not silently work."""
        lat, lon = utm_to_wgs84(9088652.47, 281302.98)
        assert not is_within_rmr(lat, lon)

    def test_bbox_rejects_points_outside_the_region(self):
        assert is_within_rmr(-8.05, -34.95)
        assert not is_within_rmr(-23.55, -46.63)  # São Paulo
        assert not is_within_rmr(0.0, 0.0)

    def test_bbox_covers_the_whole_observed_network(self):
        min_lat, max_lat, min_lon, max_lon = RMR_BBOX
        # Extremes measured across all 7136 stops in the live inventory.
        assert min_lat < -8.5621 and max_lat > -7.7333
        assert min_lon < -35.2008 and max_lon > -34.8209


class TestTransformStops:
    def test_converts_every_row_of_the_sample(self, fixture_json):
        stops, dropped = transform_stops(fixture_json("json_mapa_paradas.json"))

        assert dropped == 0
        assert stops
        assert all(is_within_rmr(s.latitude, s.longitude) for s in stops)

    def test_marks_terminals_from_class_and_name(self, fixture_json):
        stops, _ = transform_stops(fixture_json("json_mapa_paradas.json"))

        for stop in stops:
            assert stop.is_terminal == looks_like_terminal(stop.clase, stop.codigo)


class TestTerminalDetection:
    @pytest.mark.parametrize(
        "nome",
        [
            "TI Abreu e Lima (PCR) - Embarque 07 - 190908",
            "TP Cais de Sta. Rita - Embarque 01 - 180931",
            "Terminal de Ponte dos Carvalhos - 190223",
            "Estação Abolição IDA - 080198",
        ],
    )
    def test_terminal_names_are_recognised_whatever_the_class(self, nome):
        assert looks_like_terminal(2, nome)

    def test_bare_numeric_codes_are_ordinary_stops(self):
        """Class 4 is 94% terminals; the numeric name settles the rest."""
        assert not looks_like_terminal(4, "130142")

    def test_terminal_class_without_a_name_still_counts(self):
        assert looks_like_terminal(26, None)

    def test_ordinary_class_and_ordinary_name(self):
        assert not looks_like_terminal(2, "010001")

    def test_drops_rows_with_unusable_coordinates(self):
        stops, dropped = transform_stops(
            [
                {"id": 1, "nodo": 1, "nombre": "A", "clase": 2, "posX": None, "posY": 1},
                {"id": 2, "nodo": 2, "nombre": "B", "clase": 2, "posX": 0, "posY": 0},
            ]
        )

        assert stops == []
        assert dropped == 2

    def test_falls_back_to_the_nodo_when_the_code_is_missing(self):
        stops, _ = transform_stops(
            [
                {
                    "id": 9,
                    "nodo": 4242,
                    "nombre": "",
                    "clase": 2,
                    "posX": 292036.27,
                    "posY": 9105626.47,
                }
            ]
        )

        assert stops[0].codigo == "4242"


class TestEnrichStops:
    def test_itinerary_supplies_names_and_references(self, fixture_json):
        stops, _ = transform_stops(fixture_json("json_mapa_paradas.json"))
        by_nodo = {s.nodo: s for s in stops}
        assert by_nodo[19126].nome is None

        enrich_stops_from_itinerary(
            by_nodo, fixture_json("json_paradas_linha_1424.json")
        )

        assert by_nodo[19126].nome == "190126"
        assert by_nodo[19126].referencia == "EM FRENTE AO Nº749."

    def test_prefers_the_more_descriptive_name(self):
        from app.etl.transform import StopRecord

        stop = StopRecord(
            id=1, nodo=7, codigo="190223", nome="190223", referencia=None,
            clase=2, is_terminal=False, latitude=-8.0, longitude=-35.0,
        )
        by_nodo = {7: stop}

        enrich_stops_from_itinerary(
            by_nodo, [{"nodo": 7, "nombre": "Terminal de Ponte dos Carvalhos - 190223"}]
        )

        assert stop.nome == "Terminal de Ponte dos Carvalhos - 190223"

    def test_ignores_nodes_absent_from_the_inventory(self):
        by_nodo = {}
        enrich_stops_from_itinerary(by_nodo, [{"nodo": 999, "nombre": "X"}])
        assert by_nodo == {}


class TestTransformSublineStops:
    def test_builds_a_contiguous_sequence(self, fixture_json):
        itinerary = fixture_json("json_paradas_linha_1424.json")
        nodo_to_id = {row["nodo"]: row["nodo"] for row in itinerary}

        records, orphans = transform_subline_stops(1424, itinerary, nodo_to_id)

        assert orphans == 0
        assert [r.sequence for r in records] == list(range(len(records)))
        assert all(r.subline_id == 1424 for r in records)

    def test_counts_orphan_nodes_without_failing(self, fixture_json):
        itinerary = fixture_json("json_paradas_linha_1424.json")

        records, orphans = transform_subline_stops(1424, itinerary, {})

        assert records == []
        assert orphans == len(itinerary)

    def test_deduplicates_revisited_stops_on_circular_routes(self):
        itinerary = [
            {"nodo": 1, "orden": 1, "posicion": 0},
            {"nodo": 2, "orden": 1, "posicion": 10},
            {"nodo": 1, "orden": 2, "posicion": 20},
        ]

        records, _ = transform_subline_stops(1, itinerary, {1: 100, 2: 200})

        assert [r.stop_id for r in records] == [100, 200]


class TestTransformShape:
    def test_groups_points_into_ordered_segments(self, fixture_json):
        segments = transform_shape(1424, fixture_json("json_shape_1424.json"))

        assert segments
        assert all(len(s.points) >= 2 for s in segments)
        assert all(s.subline_id == 1424 for s in segments)
        assert segments == sorted(segments, key=lambda s: (s.ordem, s.idseccion or 0))

    def test_points_are_lon_lat_within_the_region(self, fixture_json):
        segments = transform_shape(1424, fixture_json("json_shape_1424.json"))

        for lon, lat in segments[0].points:
            assert is_within_rmr(lat, lon)

    def test_drops_segments_with_a_single_point(self):
        segments = transform_shape(
            1,
            [
                {
                    "idrota": 1, "idseccion": 1, "idRamal": 1,
                    "xlon": " 281302.97 ", "ylat": " 9088652.47 ",
                }
            ],
        )

        assert segments == []

    def test_handles_the_padded_string_coordinates_rumo_sends(self):
        rows = [
            {
                "idrota": 1, "idseccion": 1, "idRamal": 1,
                "ordemSeccionesRuta": 1,
                "xlon": "                281302.978670599870",
                "ylat": "               9088652.469821140200",
            },
            {
                "idrota": 1, "idseccion": 1, "idRamal": 1,
                "ordemSeccionesRuta": 1,
                "xlon": "                281295.635426372870",
                "ylat": "               9088657.327356739000",
            },
        ]

        segments = transform_shape(1, rows)

        assert len(segments) == 1
        assert len(segments[0].points) == 2


class TestWKT:
    def test_point_is_ewkt_in_lon_lat_order(self):
        assert to_wkt_point(-8.05, -34.95) == "SRID=4326;POINT(-34.95 -8.05)"

    def test_linestring_is_ewkt_in_lon_lat_order(self):
        wkt = to_wkt_linestring([(-34.95, -8.05), (-34.96, -8.06)])
        assert wkt == "SRID=4326;LINESTRING(-34.95 -8.05, -34.96 -8.06)"
