"""Pydantic GeoJSON types and WKBElement conversion utilities.

Provides two layers:

1. **Geo* Annotated types** (GeoPoint, GeoPolygon, etc.) — Pydantic field types that
   accept GeoJSON input, store WKBElement internally, and serialize back to GeoJSON.
   Use these in Pydantic models for seamless GeoJSON <-> WKBElement conversion.

2. **Utility functions** (wkb_to_geojson, geojson_to_wkb) — For manual conversion
   when needed outside of Pydantic models.

Usage:
    from pydantic import BaseModel, ConfigDict
    from litestar_geoalchemy.pydantic import GeoPoint

    class CityCreateModel(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)
        name: str
        location: GeoPoint

    # Input: GeoJSON dict -> stored as WKBElement
    geojson = {"type": "Point", "coordinates": [2.35, 48.86]}
    city = CityCreateModel.model_validate({"name": "Paris", "location": geojson})
    assert isinstance(city.location, WKBElement)

    # model_dump() -> WKBElement (for SQLAlchemy)
    raw = city.model_dump()
    # model_dump(mode="json") -> GeoJSON dict (for HTTP responses)
    raw_json = city.model_dump(mode="json")

Requires: pip install litestar-geoalchemy[pydantic]
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any

try:
    from pydantic import BaseModel  # noqa: F401 - verify pydantic is installed
except ImportError as e:
    msg = "pydantic is required. Install it with: pip install litestar-geoalchemy[pydantic]"
    raise ImportError(msg) from e

from geoalchemy2 import WKBElement
from geoalchemy2.shape import from_shape, to_shape
from pydantic import BeforeValidator, SerializerFunctionWrapHandler, WrapSerializer
from pydantic_geojson import (
    FeatureCollectionModel,
    FeatureModel,
    GeometryCollectionModel,
    LineStringModel,
    MultiLineStringModel,
    MultiPointModel,
    MultiPolygonModel,
    PointModel,
    PolygonModel,
)
from shapely.geometry import mapping, shape

if TYPE_CHECKING:
    from pydantic_core.core_schema import SerializationInfo

__all__ = [
    "AnyGeometryModel",
    "FeatureCollectionModel",
    "FeatureModel",
    "GeoGeometryCollection",
    "GeoLineString",
    "GeoMultiLineString",
    "GeoMultiPoint",
    "GeoMultiPolygon",
    "GeoPoint",
    "GeoPolygon",
    "GeometryCollectionModel",
    "LineStringModel",
    "MultiLineStringModel",
    "MultiPointModel",
    "MultiPolygonModel",
    "PointModel",
    "PolygonModel",
    "geojson_to_wkb",
    "wkb_to_geojson",
]

# GeoJSON uses WGS84 (EPSG:4326) by default
DEFAULT_SRID = 4326

# Valid GeoJSON geometry type strings
GEOJSON_GEOMETRY_TYPES = frozenset(
    {
        "Point",
        "LineString",
        "Polygon",
        "MultiPoint",
        "MultiLineString",
        "MultiPolygon",
        "GeometryCollection",
    }
)

# =============================================================================
# Union of all pydantic-geojson models for generic geometry fields
# =============================================================================

AnyGeometryModel = (
    PointModel
    | LineStringModel
    | PolygonModel
    | MultiPointModel
    | MultiLineStringModel
    | MultiPolygonModel
    | GeometryCollectionModel
)

# =============================================================================
# Internal helpers: coordinate cleaning for pydantic-geojson compatibility
# =============================================================================


def _strip_none_coordinates(coords: Any) -> Any:  # noqa: ANN401
    """Recursively strip None values from coordinate arrays.

    pydantic-geojson models add None altitude (e.g., (2.35, 48.86, None)).
    shapely.shape() cannot handle None in coordinates.
    """
    if isinstance(coords, list | tuple):
        if coords and not isinstance(coords[0], list | tuple):
            return [c for c in coords if c is not None]
        return [_strip_none_coordinates(c) for c in coords]
    return coords


def _clean_geojson_for_shapely(value: dict[str, Any]) -> dict[str, Any]:
    """Clean a GeoJSON dict for shapely consumption.

    Strips None altitude values and bbox fields that shapely cannot process.
    """
    cleaned: dict[str, Any] = {"type": value["type"]}

    if "coordinates" in value:
        cleaned["coordinates"] = _strip_none_coordinates(value["coordinates"])
    elif "geometries" in value:
        cleaned["geometries"] = [_clean_geojson_for_shapely(g) for g in value["geometries"]]

    return cleaned


# =============================================================================
# Utility functions: manual WKBElement <-> GeoJSON conversion
# =============================================================================


def wkb_to_geojson(value: WKBElement) -> dict[str, Any]:
    """Convert a WKBElement to a GeoJSON dict.

    Args:
        value: A GeoAlchemy2 WKBElement instance.

    Returns:
        GeoJSON dict with 'type' and 'coordinates' keys.
    """
    return dict(mapping(to_shape(value)))


def geojson_to_wkb(value: dict[str, Any], srid: int = DEFAULT_SRID) -> WKBElement:
    """Convert a GeoJSON dict to a WKBElement.

    Handles pydantic-geojson model_dump() output which may contain None altitude
    values and bbox fields that shapely cannot process.

    Args:
        value: A GeoJSON dict with 'type' and 'coordinates' keys.
        srid: Spatial reference ID (default: 4326 / WGS84).

    Returns:
        A GeoAlchemy2 WKBElement suitable for SQLAlchemy column assignment.
    """
    return from_shape(shape(_clean_geojson_for_shapely(value)), srid=srid)


# =============================================================================
# Pydantic validators/serializers for Geo* Annotated types
# =============================================================================


def _validate_geojson_type(value: dict[str, Any], expected_type: str) -> None:
    """Validate that a GeoJSON dict has the expected geometry type."""
    geojson_type = value.get("type")
    if geojson_type is None:
        msg = "GeoJSON missing required 'type' field"
        raise ValueError(msg)
    if geojson_type != expected_type:
        msg = f"Expected {expected_type} geometry, got {geojson_type}"
        raise ValueError(msg)


def _make_geojson_validator(expected_type: str | None = None):  # noqa: ANN202
    """Create a BeforeValidator function for a specific geometry type.

    Args:
        expected_type: The expected GeoJSON type string (e.g., "Point").
            If None, accepts any geometry type.
    """

    def _validator(value: Any) -> WKBElement:  # noqa: ANN401
        if isinstance(value, WKBElement):
            return value
        if not isinstance(value, dict):
            msg = f"Expected GeoJSON dict or WKBElement, got {type(value).__name__}"
            raise ValueError(msg)  # noqa: TRY004 - ValueError needed for pydantic ValidationError wrapping
        if expected_type is not None:
            _validate_geojson_type(value, expected_type)
        elif value.get("type") not in GEOJSON_GEOMETRY_TYPES:
            msg = f"Unknown GeoJSON type: {value.get('type')}"
            raise ValueError(msg)
        return geojson_to_wkb(value)

    return _validator


def _wkb_serializer(
    value: WKBElement,
    _handler: SerializerFunctionWrapHandler,
    info: "SerializationInfo",
) -> dict[str, Any] | WKBElement:
    """Serialize WKBElement based on pydantic serialization mode.

    - mode="python" (default model_dump): returns WKBElement as-is for SQLAlchemy
    - mode="json" (model_dump_json or model_dump(mode="json")): returns GeoJSON dict
    """
    if info.mode == "json":
        return wkb_to_geojson(value)
    return value


# =============================================================================
# Geo* Annotated types: GeoJSON <-> WKBElement Pydantic field types
#
# Use these in Pydantic models. They accept GeoJSON dicts as input, store
# WKBElement internally, and serialize back to GeoJSON for JSON output.
#
# Models using these types MUST set: model_config = ConfigDict(arbitrary_types_allowed=True)
# =============================================================================


@dataclass(frozen=True)
class GeoJSONMeta:
    """Metadata marker for Geo* Annotated types.

    Stored in the Annotated args so OpenAPI schema generation can identify
    the geometry type without inspecting validator closures.
    """

    geojson_type: str


_WRAP = WrapSerializer(_wkb_serializer)

GeoPoint = Annotated[WKBElement, GeoJSONMeta("Point"), BeforeValidator(_make_geojson_validator("Point")), _WRAP]
GeoLineString = Annotated[
    WKBElement, GeoJSONMeta("LineString"), BeforeValidator(_make_geojson_validator("LineString")), _WRAP
]
GeoPolygon = Annotated[WKBElement, GeoJSONMeta("Polygon"), BeforeValidator(_make_geojson_validator("Polygon")), _WRAP]
GeoMultiPoint = Annotated[
    WKBElement, GeoJSONMeta("MultiPoint"), BeforeValidator(_make_geojson_validator("MultiPoint")), _WRAP
]
GeoMultiLineString = Annotated[
    WKBElement,
    GeoJSONMeta("MultiLineString"),
    BeforeValidator(_make_geojson_validator("MultiLineString")),
    _WRAP,
]
GeoMultiPolygon = Annotated[
    WKBElement, GeoJSONMeta("MultiPolygon"), BeforeValidator(_make_geojson_validator("MultiPolygon")), _WRAP
]
GeoGeometryCollection = Annotated[
    WKBElement,
    GeoJSONMeta("GeometryCollection"),
    BeforeValidator(_make_geojson_validator("GeometryCollection")),
    _WRAP,
]
