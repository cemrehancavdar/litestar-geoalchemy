"""Tests for litestar-geoalchemy pydantic module.

Tests:
- pydantic-geojson model validation (PointModel, PolygonModel, etc.)
- wkb_to_geojson / geojson_to_wkb conversion utilities
- Geo* Annotated types (GeoPoint, GeoPolygon, etc.) in Pydantic models
"""

import pytest
from geoalchemy2 import WKBElement
from geoalchemy2.shape import from_shape
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic_geojson import (
    GeometryCollectionModel,
    LineStringModel,
    MultiLineStringModel,
    MultiPointModel,
    MultiPolygonModel,
    PointModel,
    PolygonModel,
)
from shapely import LineString as ShapelyLineString
from shapely import MultiLineString as ShapelyMultiLineString
from shapely import MultiPoint as ShapelyMultiPoint
from shapely import MultiPolygon as ShapelyMultiPolygon
from shapely import Point as ShapelyPoint
from shapely import Polygon as ShapelyPolygon

from litestar_geoalchemy.pydantic import (
    GeoGeometryCollection,
    GeoLineString,
    GeoMultiLineString,
    GeoMultiPoint,
    GeoMultiPolygon,
    GeoPoint,
    GeoPolygon,
    geojson_to_wkb,
    wkb_to_geojson,
)

# =============================================================================
# GeoJSON test data
# =============================================================================

POINT_GEOJSON = {"type": "Point", "coordinates": [12.34, 56.78]}
LINESTRING_GEOJSON = {"type": "LineString", "coordinates": [[0, 0], [1, 1], [2, 0]]}
POLYGON_GEOJSON = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
MULTIPOINT_GEOJSON = {"type": "MultiPoint", "coordinates": [[0, 0], [1, 1]]}
MULTILINESTRING_GEOJSON = {"type": "MultiLineString", "coordinates": [[[0, 0], [1, 1]], [[2, 2], [3, 3]]]}
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

DEFAULT_SRID = 4326


# =============================================================================
# pydantic-geojson model validation tests
# =============================================================================


class TestPointModel:
    def test_valid_point(self):
        p = PointModel(**POINT_GEOJSON)
        assert p.type == "Point"
        assert p.coordinates[0] == 12.34
        assert p.coordinates[1] == 56.78

    def test_point_type_required(self):
        with pytest.raises(ValidationError):
            PointModel(coordinates=[1.0, 2.0])

    def test_point_rejects_wrong_type(self):
        with pytest.raises(ValidationError):
            PointModel(type="Polygon", coordinates=[1.0, 2.0])

    def test_point_requires_coordinates(self):
        with pytest.raises(ValidationError):
            PointModel(type="Point")

    def test_point_model_dump(self):
        p = PointModel(**POINT_GEOJSON)
        dumped = p.model_dump()
        assert dumped["type"] == "Point"
        assert dumped["coordinates"][0] == 12.34
        assert dumped["coordinates"][1] == 56.78

    def test_point_json_schema(self):
        schema = PointModel.model_json_schema()
        assert "coordinates" in schema["properties"]

    def test_point_has_bbox_field(self):
        p = PointModel(**POINT_GEOJSON)
        assert "bbox" in PointModel.model_fields
        assert p.bbox is None


class TestLineStringModel:
    def test_valid_linestring(self):
        ls = LineStringModel(**LINESTRING_GEOJSON)
        assert ls.type == "LineString"
        assert len(ls.coordinates) == 3

    def test_linestring_rejects_wrong_type(self):
        with pytest.raises(ValidationError):
            LineStringModel(type="Point", coordinates=[[0, 0], [1, 1]])


class TestPolygonModel:
    def test_valid_polygon(self):
        p = PolygonModel(**POLYGON_GEOJSON)
        assert p.type == "Polygon"
        assert len(p.coordinates) == 1
        assert len(p.coordinates[0]) == 5

    def test_polygon_rejects_wrong_type(self):
        with pytest.raises(ValidationError):
            PolygonModel(type="Point", coordinates=[[[0, 0], [1, 0], [1, 1], [0, 0]]])


class TestMultiPointModel:
    def test_valid_multipoint(self):
        mp = MultiPointModel(**MULTIPOINT_GEOJSON)
        assert mp.type == "MultiPoint"
        assert len(mp.coordinates) == 2


class TestMultiLineStringModel:
    def test_valid_multilinestring(self):
        mls = MultiLineStringModel(**MULTILINESTRING_GEOJSON)
        assert mls.type == "MultiLineString"
        assert len(mls.coordinates) == 2


class TestMultiPolygonModel:
    def test_valid_multipolygon(self):
        mp = MultiPolygonModel(**MULTIPOLYGON_GEOJSON)
        assert mp.type == "MultiPolygon"
        assert len(mp.coordinates) == 2


class TestGeometryCollectionModel:
    def test_valid_geometrycollection(self):
        gc = GeometryCollectionModel(**GEOMETRYCOLLECTION_GEOJSON)
        assert gc.type == "GeometryCollection"
        assert len(gc.geometries) == 2


# =============================================================================
# wkb_to_geojson conversion tests
# =============================================================================


class TestWkbToGeojson:
    def test_point(self):
        wkb = from_shape(ShapelyPoint(2.35, 48.86), srid=DEFAULT_SRID)
        result = wkb_to_geojson(wkb)
        assert result["type"] == "Point"
        assert result["coordinates"] == (2.35, 48.86)

    def test_linestring(self):
        wkb = from_shape(ShapelyLineString([(0, 0), (1, 1), (2, 0)]), srid=DEFAULT_SRID)
        result = wkb_to_geojson(wkb)
        assert result["type"] == "LineString"
        assert len(result["coordinates"]) == 3

    def test_polygon(self):
        wkb = from_shape(ShapelyPolygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]), srid=DEFAULT_SRID)
        result = wkb_to_geojson(wkb)
        assert result["type"] == "Polygon"

    def test_multipoint(self):
        wkb = from_shape(ShapelyMultiPoint([(0, 0), (1, 1)]), srid=DEFAULT_SRID)
        result = wkb_to_geojson(wkb)
        assert result["type"] == "MultiPoint"
        assert len(result["coordinates"]) == 2

    def test_multilinestring(self):
        wkb = from_shape(ShapelyMultiLineString([[(0, 0), (1, 1)], [(2, 2), (3, 3)]]), srid=DEFAULT_SRID)
        result = wkb_to_geojson(wkb)
        assert result["type"] == "MultiLineString"
        assert len(result["coordinates"]) == 2

    def test_multipolygon(self):
        poly1 = ShapelyPolygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        poly2 = ShapelyPolygon([(2, 2), (3, 2), (3, 3), (2, 3), (2, 2)])
        wkb = from_shape(ShapelyMultiPolygon([poly1, poly2]), srid=DEFAULT_SRID)
        result = wkb_to_geojson(wkb)
        assert result["type"] == "MultiPolygon"
        assert len(result["coordinates"]) == 2

    def test_result_is_valid_for_pydantic(self):
        """wkb_to_geojson output should be accepted by pydantic-geojson models."""
        wkb = from_shape(ShapelyPoint(2.35, 48.86), srid=DEFAULT_SRID)
        result = wkb_to_geojson(wkb)
        p = PointModel(**result)
        assert p.type == "Point"
        assert p.coordinates[0] == 2.35

    def test_rejects_non_wkb(self):
        with pytest.raises(TypeError):
            wkb_to_geojson({"type": "Point", "coordinates": [1, 2]})  # type: ignore[arg-type]

    def test_rejects_string(self):
        with pytest.raises(TypeError):
            wkb_to_geojson("not a geometry")  # type: ignore[arg-type]


# =============================================================================
# geojson_to_wkb conversion tests
# =============================================================================


class TestGeojsonToWkb:
    def test_point_roundtrip(self):
        """GeoJSON -> WKBElement -> GeoJSON should preserve geometry."""
        wkb = geojson_to_wkb(POINT_GEOJSON)
        result = wkb_to_geojson(wkb)
        assert result["type"] == "Point"
        assert result["coordinates"][0] == pytest.approx(12.34)
        assert result["coordinates"][1] == pytest.approx(56.78)

    def test_polygon_roundtrip(self):
        wkb = geojson_to_wkb(POLYGON_GEOJSON)
        result = wkb_to_geojson(wkb)
        assert result["type"] == "Polygon"
        assert len(result["coordinates"][0]) == 5

    def test_linestring_roundtrip(self):
        wkb = geojson_to_wkb(LINESTRING_GEOJSON)
        result = wkb_to_geojson(wkb)
        assert result["type"] == "LineString"
        assert len(result["coordinates"]) == 3

    def test_multipoint_roundtrip(self):
        wkb = geojson_to_wkb(MULTIPOINT_GEOJSON)
        result = wkb_to_geojson(wkb)
        assert result["type"] == "MultiPoint"
        assert len(result["coordinates"]) == 2

    def test_multipolygon_roundtrip(self):
        wkb = geojson_to_wkb(MULTIPOLYGON_GEOJSON)
        result = wkb_to_geojson(wkb)
        assert result["type"] == "MultiPolygon"
        assert len(result["coordinates"]) == 2

    def test_custom_srid(self):
        """geojson_to_wkb should accept custom SRID."""
        wkb = geojson_to_wkb(POINT_GEOJSON, srid=3857)
        assert wkb.srid == 3857

    def test_default_srid_is_4326(self):
        wkb = geojson_to_wkb(POINT_GEOJSON)
        assert wkb.srid == DEFAULT_SRID

    def test_returns_wkb_element(self):
        wkb = geojson_to_wkb(POINT_GEOJSON)
        assert isinstance(wkb, WKBElement)

    def test_pydantic_model_dump_roundtrip(self):
        """PointModel.model_dump() dict (with None altitude) should be convertible to WKBElement."""
        model = PointModel(**POINT_GEOJSON)
        dumped = model.model_dump()
        wkb = geojson_to_wkb(dumped)
        result = wkb_to_geojson(wkb)
        assert result["type"] == "Point"
        assert result["coordinates"][0] == pytest.approx(12.34)


# =============================================================================
# Geo* Annotated type tests
# =============================================================================


class _PointModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    location: GeoPoint


class _PolygonModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    boundary: GeoPolygon


class _MultiPolygonModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    area: GeoMultiPolygon


class _LineStringModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    path: GeoLineString


class _MultiPointModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    points: GeoMultiPoint


class _MultiLineStringModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    paths: GeoMultiLineString


class _GeometryCollectionModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    geom: GeoGeometryCollection


class TestGeoPointType:
    def test_accepts_geojson_dict(self):
        m = _PointModel.model_validate({"location": POINT_GEOJSON})
        assert isinstance(m.location, WKBElement)

    def test_stores_wkb_element(self):
        m = _PointModel.model_validate({"location": POINT_GEOJSON})
        assert isinstance(m.location, WKBElement)
        assert m.location.srid == DEFAULT_SRID

    def test_model_dump_returns_wkb(self):
        """model_dump() (python mode) returns WKBElement for SQLAlchemy."""
        m = _PointModel.model_validate({"location": POINT_GEOJSON})
        dumped = m.model_dump()
        assert isinstance(dumped["location"], WKBElement)

    def test_model_dump_json_mode_returns_geojson(self):
        """model_dump(mode='json') returns GeoJSON dict for HTTP responses."""
        m = _PointModel.model_validate({"location": POINT_GEOJSON})
        dumped = m.model_dump(mode="json")
        assert isinstance(dumped["location"], dict)
        assert dumped["location"]["type"] == "Point"
        assert dumped["location"]["coordinates"][0] == pytest.approx(12.34)
        assert dumped["location"]["coordinates"][1] == pytest.approx(56.78)

    def test_accepts_existing_wkb(self):
        """GeoPoint should accept WKBElement as-is (idempotent)."""
        wkb = from_shape(ShapelyPoint(2.35, 48.86), srid=DEFAULT_SRID)
        m = _PointModel.model_validate({"location": wkb})
        assert m.location is wkb

    def test_rejects_wrong_geometry_type(self):
        with pytest.raises(ValidationError, match="Expected Point geometry, got Polygon"):
            _PointModel.model_validate({"location": POLYGON_GEOJSON})

    def test_rejects_non_dict(self):
        with pytest.raises(ValidationError, match="Expected GeoJSON dict or WKBElement"):
            _PointModel.model_validate({"location": "not a geometry"})

    def test_roundtrip_preserves_coordinates(self):
        """GeoJSON -> WKBElement -> GeoJSON roundtrip preserves data."""
        m = _PointModel.model_validate({"location": POINT_GEOJSON})
        dumped = m.model_dump(mode="json")
        m2 = _PointModel.model_validate({"location": dumped["location"]})
        dumped2 = m2.model_dump(mode="json")
        assert dumped["location"]["coordinates"] == dumped2["location"]["coordinates"]


class TestGeoPolygonType:
    def test_accepts_geojson_dict(self):
        m = _PolygonModel.model_validate({"boundary": POLYGON_GEOJSON})
        assert isinstance(m.boundary, WKBElement)

    def test_model_dump_json_mode(self):
        m = _PolygonModel.model_validate({"boundary": POLYGON_GEOJSON})
        dumped = m.model_dump(mode="json")
        assert dumped["boundary"]["type"] == "Polygon"
        assert len(dumped["boundary"]["coordinates"][0]) == 5

    def test_rejects_wrong_type(self):
        with pytest.raises(ValidationError, match="Expected Polygon geometry, got Point"):
            _PolygonModel.model_validate({"boundary": POINT_GEOJSON})


class TestGeoMultiPolygonType:
    def test_accepts_geojson_dict(self):
        m = _MultiPolygonModel.model_validate({"area": MULTIPOLYGON_GEOJSON})
        assert isinstance(m.area, WKBElement)

    def test_model_dump_json_mode(self):
        m = _MultiPolygonModel.model_validate({"area": MULTIPOLYGON_GEOJSON})
        dumped = m.model_dump(mode="json")
        assert dumped["area"]["type"] == "MultiPolygon"
        assert len(dumped["area"]["coordinates"]) == 2


class TestGeoLineStringType:
    def test_accepts_geojson_dict(self):
        m = _LineStringModel.model_validate({"path": LINESTRING_GEOJSON})
        assert isinstance(m.path, WKBElement)

    def test_model_dump_json_mode(self):
        m = _LineStringModel.model_validate({"path": LINESTRING_GEOJSON})
        dumped = m.model_dump(mode="json")
        assert dumped["path"]["type"] == "LineString"
        assert len(dumped["path"]["coordinates"]) == 3


class TestGeoMultiPointType:
    def test_accepts_geojson_dict(self):
        m = _MultiPointModel.model_validate({"points": MULTIPOINT_GEOJSON})
        assert isinstance(m.points, WKBElement)


class TestGeoMultiLineStringType:
    def test_accepts_geojson_dict(self):
        m = _MultiLineStringModel.model_validate({"paths": MULTILINESTRING_GEOJSON})
        assert isinstance(m.paths, WKBElement)


class TestGeoGeometryCollectionType:
    def test_accepts_geojson_dict(self):
        m = _GeometryCollectionModel.model_validate({"geom": GEOMETRYCOLLECTION_GEOJSON})
        assert isinstance(m.geom, WKBElement)

    def test_model_dump_json_mode(self):
        m = _GeometryCollectionModel.model_validate({"geom": GEOMETRYCOLLECTION_GEOJSON})
        dumped = m.model_dump(mode="json")
        assert dumped["geom"]["type"] == "GeometryCollection"
