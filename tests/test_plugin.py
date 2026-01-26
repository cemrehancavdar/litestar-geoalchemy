"""Tests for litestar-geoalchemy plugin."""

from dataclasses import dataclass

import geoalchemy2.shape
import pytest
import shapely
from litestar import Litestar, get, post
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST
from litestar.testing import TestClient

from litestar_geoalchemy import (
    GeoAlchemyPlugin,
    GeoJSONTypeError,
    GeoJSONValidationError,
    Point,
    Polygon,
)
from litestar_geoalchemy.plugin import geometry_decoder
from litestar_geoalchemy.types import (
    AnyGeometry,
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    from_wkb_element,
)

# =============================================================================
# Test fixtures and helpers
# =============================================================================


POINT_GEOJSON = {"type": "Point", "coordinates": [12.34, 56.78]}
POLYGON_GEOJSON = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
}
LINESTRING_GEOJSON = {"type": "LineString", "coordinates": [[0, 0], [1, 1], [2, 0]]}
MULTIPOINT_GEOJSON = {"type": "MultiPoint", "coordinates": [[0, 0], [1, 1]]}
MULTILINESTRING_GEOJSON = {
    "type": "MultiLineString",
    "coordinates": [[[0, 0], [1, 1]], [[2, 2], [3, 3]]],
}
MULTIPOLYGON_GEOJSON = {
    "type": "MultiPolygon",
    "coordinates": [
        [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        [[[2, 2], [3, 2], [3, 3], [2, 3], [2, 2]]],
    ],
}
GEOMETRYCOLLECTION_GEOJSON = {
    "type": "GeometryCollection",
    "geometries": [POINT_GEOJSON, LINESTRING_GEOJSON],
}


def create_app(*handlers) -> Litestar:
    return Litestar(route_handlers=list(handlers), plugins=[GeoAlchemyPlugin()], debug=True)


def create_app_with_srid(srid: int, *handlers) -> Litestar:
    return Litestar(route_handlers=list(handlers), plugins=[GeoAlchemyPlugin(srid=srid)], debug=True)


# =============================================================================
# Basic serialization tests
# =============================================================================


class TestPointSerialization:
    def test_get_point(self):
        @get("/point", sync_to_thread=True)
        def handler() -> Point:
            shape = shapely.from_geojson('{"type": "Point", "coordinates": [12.34, 56.78]}')
            geometry = geoalchemy2.shape.from_shape(shape)
            return from_wkb_element(Point, geometry)

        with TestClient(create_app(handler)) as client:
            response = client.get("/point")
            assert response.status_code == HTTP_200_OK
            data = response.json()
            assert data["type"] == "Point"
            assert data["coordinates"] == [12.34, 56.78]

    def test_post_point(self):
        @post("/point", sync_to_thread=True)
        def handler(data: Point) -> Point:
            return data

        with TestClient(create_app(handler)) as client:
            response = client.post("/point", json=POINT_GEOJSON)
            assert response.status_code == HTTP_201_CREATED
            data = response.json()
            assert data["type"] == "Point"
            assert len(data["coordinates"]) == 2


class TestPolygonSerialization:
    def test_post_polygon(self):
        @post("/polygon", sync_to_thread=True)
        def handler(data: Polygon) -> Polygon:
            return data

        with TestClient(create_app(handler)) as client:
            response = client.post("/polygon", json=POLYGON_GEOJSON)
            assert response.status_code == HTTP_201_CREATED
            data = response.json()
            assert data["type"] == "Polygon"
            assert len(data["coordinates"]) == 1
            assert len(data["coordinates"][0]) == 5


class TestAllGeometryTypes:
    @pytest.mark.parametrize(
        ("geometry_type", "geojson"),
        [
            (Point, POINT_GEOJSON),
            (LineString, LINESTRING_GEOJSON),
            (Polygon, POLYGON_GEOJSON),
            (MultiPoint, MULTIPOINT_GEOJSON),
            (MultiLineString, MULTILINESTRING_GEOJSON),
            (MultiPolygon, MULTIPOLYGON_GEOJSON),
            (GeometryCollection, GEOMETRYCOLLECTION_GEOJSON),
        ],
    )
    def test_geometry_roundtrip(self, geometry_type: type, geojson: dict):
        @post("/geom", sync_to_thread=True)
        def handler(data: geometry_type) -> geometry_type:  # type: ignore[valid-type]
            return data

        with TestClient(create_app(handler)) as client:
            response = client.post("/geom", json=geojson)
            assert response.status_code == HTTP_201_CREATED
            data = response.json()
            assert data["type"] == geojson["type"]


# =============================================================================
# Feature/FeatureCollection input tests
# =============================================================================


class TestFeatureInput:
    def test_feature_extracts_geometry(self):
        @post("/point", sync_to_thread=True)
        def handler(data: Point) -> Point:
            return data

        feature = {
            "type": "Feature",
            "geometry": POINT_GEOJSON,
            "properties": {"name": "test"},
        }

        with TestClient(create_app(handler)) as client:
            response = client.post("/point", json=feature)
            assert response.status_code == HTTP_201_CREATED
            data = response.json()
            assert data["type"] == "Point"
            assert data["coordinates"] == [12.34, 56.78]

    def test_feature_collection_single_feature(self):
        @post("/point", sync_to_thread=True)
        def handler(data: Point) -> Point:
            return data

        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": POINT_GEOJSON,
                    "properties": {},
                }
            ],
        }

        with TestClient(create_app(handler)) as client:
            response = client.post("/point", json=fc)
            assert response.status_code == HTTP_201_CREATED
            data = response.json()
            assert data["type"] == "Point"


# =============================================================================
# Type validation tests
# =============================================================================


class TestTypeValidation:
    def test_point_rejects_polygon(self):
        @post("/point", sync_to_thread=True)
        def handler(data: Point) -> Point:
            return data

        with TestClient(create_app(handler)) as client:
            response = client.post("/point", json=POLYGON_GEOJSON)
            assert response.status_code == HTTP_400_BAD_REQUEST
            assert "Expected Point geometry, got Polygon" in response.text

    def test_polygon_rejects_point(self):
        @post("/polygon", sync_to_thread=True)
        def handler(data: Polygon) -> Polygon:
            return data

        with TestClient(create_app(handler)) as client:
            response = client.post("/polygon", json=POINT_GEOJSON)
            assert response.status_code == HTTP_400_BAD_REQUEST
            assert "Expected Polygon geometry, got Point" in response.text

    def test_any_geometry_accepts_all(self):
        @post("/any", sync_to_thread=True)
        def handler(data: AnyGeometry) -> AnyGeometry:
            return data

        with TestClient(create_app(handler)) as client:
            # Should accept Point
            response = client.post("/any", json=POINT_GEOJSON)
            assert response.status_code == HTTP_201_CREATED

            # Should accept Polygon
            response = client.post("/any", json=POLYGON_GEOJSON)
            assert response.status_code == HTTP_201_CREATED


# =============================================================================
# Validation error tests
# =============================================================================


class TestValidationErrors:
    def test_missing_type(self):
        @post("/point", sync_to_thread=True)
        def handler(data: Point) -> Point:
            return data

        with TestClient(create_app(handler)) as client:
            response = client.post("/point", json={"coordinates": [1, 2]})
            assert response.status_code == HTTP_400_BAD_REQUEST
            assert "missing required 'type' field" in response.text

    def test_missing_coordinates(self):
        @post("/point", sync_to_thread=True)
        def handler(data: Point) -> Point:
            return data

        with TestClient(create_app(handler)) as client:
            response = client.post("/point", json={"type": "Point"})
            assert response.status_code == HTTP_400_BAD_REQUEST
            assert "missing required 'coordinates' field" in response.text

    def test_unknown_type(self):
        @post("/point", sync_to_thread=True)
        def handler(data: Point) -> Point:
            return data

        with TestClient(create_app(handler)) as client:
            response = client.post("/point", json={"type": "Unknown", "coordinates": [1, 2]})
            assert response.status_code == HTTP_400_BAD_REQUEST
            assert "Unknown GeoJSON type" in response.text

    def test_empty_feature_collection(self):
        @post("/point", sync_to_thread=True)
        def handler(data: Point) -> Point:
            return data

        with TestClient(create_app(handler)) as client:
            response = client.post("/point", json={"type": "FeatureCollection", "features": []})
            assert response.status_code == HTTP_400_BAD_REQUEST
            assert "empty" in response.text.lower()

    def test_multiple_features_rejected(self):
        @post("/point", sync_to_thread=True)
        def handler(data: Point) -> Point:
            return data

        fc = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": POINT_GEOJSON, "properties": {}},
                {"type": "Feature", "geometry": POINT_GEOJSON, "properties": {}},
            ],
        }

        with TestClient(create_app(handler)) as client:
            response = client.post("/point", json=fc)
            assert response.status_code == HTTP_400_BAD_REQUEST
            assert "2 features" in response.text


# =============================================================================
# SRID configuration tests
# =============================================================================


class TestSRIDConfiguration:
    def test_default_srid_4326(self):
        result = geometry_decoder(Point, POINT_GEOJSON)
        assert result.srid == 4326

    def test_custom_srid(self):
        result = geometry_decoder(Point, POINT_GEOJSON, srid=3857)
        assert result.srid == 3857

    def test_plugin_srid_config(self):
        @post("/point", sync_to_thread=True)
        def handler(data: Point) -> Point:
            # Verify SRID is set correctly
            assert data.srid == 3857
            return data

        with TestClient(create_app_with_srid(3857, handler)) as client:
            response = client.post("/point", json=POINT_GEOJSON)
            assert response.status_code == HTTP_201_CREATED


# =============================================================================
# Nested dataclass tests
# =============================================================================


class TestNestedDataclass:
    def test_dataclass_with_geometry(self):
        @dataclass
        class Location:
            name: str
            point: Point

        @post("/location", sync_to_thread=True)
        def handler(data: Location) -> Location:
            return data

        payload = {"name": "Paris", "point": POINT_GEOJSON}

        with TestClient(create_app(handler)) as client:
            response = client.post("/location", json=payload)
            assert response.status_code == HTTP_201_CREATED
            data = response.json()
            assert data["name"] == "Paris"
            assert data["point"]["type"] == "Point"
            assert data["point"]["coordinates"] == [12.34, 56.78]

    def test_dataclass_with_feature_input(self):
        @dataclass
        class Location:
            name: str
            point: Point

        @post("/location", sync_to_thread=True)
        def handler(data: Location) -> Location:
            return data

        feature = {
            "type": "Feature",
            "geometry": POINT_GEOJSON,
            "properties": {},
        }
        payload = {"name": "Paris", "point": feature}

        with TestClient(create_app(handler)) as client:
            response = client.post("/location", json=payload)
            assert response.status_code == HTTP_201_CREATED
            data = response.json()
            assert data["point"]["type"] == "Point"


# =============================================================================
# Decoder unit tests
# =============================================================================


class TestDecoderUnit:
    def test_decoder_idempotent(self):
        """Decoder should return WKBElement as-is if already decoded."""
        first = geometry_decoder(Point, POINT_GEOJSON)
        second = geometry_decoder(Point, first)
        assert first is second

    def test_decoder_raises_type_error(self):
        with pytest.raises(GeoJSONTypeError) as exc_info:
            geometry_decoder(Point, POLYGON_GEOJSON)
        assert exc_info.value.expected == "Point"
        assert exc_info.value.received == "Polygon"

    def test_decoder_raises_validation_error(self):
        with pytest.raises(GeoJSONValidationError):
            geometry_decoder(Point, {"type": "Point"})  # missing coordinates
