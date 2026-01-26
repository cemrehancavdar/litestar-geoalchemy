"""GeoAlchemy2 + Litestar plugin.

Handles GeoJSON <-> WKBElement conversion for Litestar routes.

Supports:
- Raw geometry: {"type": "Point", "coordinates": [lon, lat]}
- Feature: {"type": "Feature", "geometry": {...}, "properties": {...}}
- FeatureCollection: {"type": "FeatureCollection", "features": [...]}

SRID defaults to 4326 (WGS84) per GeoJSON spec.
"""

from functools import partial
from typing import Any

from geoalchemy2.shape import to_shape
from geoalchemy2.types import WKBElement  # pyright: ignore[reportPrivateImportUsage]
from litestar.config.app import AppConfig
from litestar.plugins import InitPluginProtocol
from shapely.geometry import mapping, shape
from shapely.wkb import dumps

from litestar_geoalchemy.openapi import GeoalchemySchemaPlugin
from litestar_geoalchemy.types import (
    AnyGeometry,
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

# GeoJSON uses WGS84 (EPSG:4326) by default
DEFAULT_SRID = 4326

# Valid GeoJSON geometry types
GEOJSON_TYPES = frozenset(
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

# Map our type classes to expected GeoJSON type strings
TYPE_TO_GEOJSON: dict[type, str] = {
    Point: "Point",
    LineString: "LineString",
    Polygon: "Polygon",
    MultiPoint: "MultiPoint",
    MultiLineString: "MultiLineString",
    MultiPolygon: "MultiPolygon",
    GeometryCollection: "GeometryCollection",
    AnyGeometry: "*",  # Accepts any geometry type
}


class GeoJSONError(ValueError):
    """Base exception for GeoJSON parsing errors."""


class GeoJSONTypeError(GeoJSONError):
    """Raised when geometry type doesn't match expected type."""

    def __init__(self, expected: str, received: str) -> None:
        self.expected = expected
        self.received = received
        super().__init__(f"Expected {expected} geometry, got {received}")


class GeoJSONValidationError(GeoJSONError):
    """Raised when GeoJSON structure is invalid."""


def _geojson_encoder(geom: WKBElement) -> dict[str, Any]:
    """Encode WKBElement to GeoJSON dict."""
    return mapping(to_shape(geom))


type_encoders = {
    WKBElement: _geojson_encoder,
}


def _validate_geometry_structure(geojson_type: str, value: dict[str, Any]) -> None:
    """Validate raw geometry has required fields."""
    if geojson_type == "GeometryCollection":
        if "geometries" not in value:
            msg = "GeometryCollection missing required 'geometries' field"
            raise GeoJSONValidationError(msg)
    elif "coordinates" not in value:
        msg = f"{geojson_type} missing required 'coordinates' field"
        raise GeoJSONValidationError(msg)


def _validate_geojson_structure(value: dict[str, Any]) -> None:
    """Validate basic GeoJSON structure.

    Raises:
        GeoJSONValidationError: If structure is invalid
    """
    if not isinstance(value, dict):
        msg = f"GeoJSON must be a dict, got {type(value).__name__}"
        raise GeoJSONValidationError(msg)

    geojson_type = value.get("type")
    if geojson_type is None:
        msg = "GeoJSON missing required 'type' field"
        raise GeoJSONValidationError(msg)

    if geojson_type in GEOJSON_TYPES:
        _validate_geometry_structure(geojson_type, value)
    elif geojson_type == "Feature" and "geometry" not in value:
        msg = "Feature missing required 'geometry' field"
        raise GeoJSONValidationError(msg)
    elif geojson_type == "FeatureCollection" and "features" not in value:
        msg = "FeatureCollection missing required 'features' field"
        raise GeoJSONValidationError(msg)
    elif geojson_type not in (*GEOJSON_TYPES, "Feature", "FeatureCollection"):
        msg = f"Unknown GeoJSON type: {geojson_type}"
        raise GeoJSONValidationError(msg)


def _extract_geometry(value: dict[str, Any]) -> dict[str, Any]:
    """Extract geometry from GeoJSON input.

    Handles:
    - Raw geometry: returns as-is
    - Feature: extracts geometry field
    - FeatureCollection: extracts geometry from first feature

    Raises:
        GeoJSONValidationError: If structure is invalid
    """
    _validate_geojson_structure(value)

    geojson_type = value.get("type")

    if geojson_type == "Feature":
        geometry = value.get("geometry")
        if geometry is None:
            msg = "Feature.geometry is null"
            raise GeoJSONValidationError(msg)
        return _extract_geometry(geometry)  # Recurse to validate geometry

    if geojson_type == "FeatureCollection":
        features = value.get("features", [])
        if not features:
            msg = "FeatureCollection.features is empty"
            raise GeoJSONValidationError(msg)
        if len(features) > 1:
            msg = f"FeatureCollection has {len(features)} features; expected 1 for single geometry field"
            raise GeoJSONValidationError(msg)
        return _extract_geometry(features[0])  # Recurse to handle Feature

    # Raw geometry (Point, Polygon, etc.)
    return value


def _validate_geometry_type(target_type: type[WKBElement], geojson_type: str) -> None:
    """Validate that GeoJSON type matches expected type.

    Raises:
        GeoJSONTypeError: If types don't match
    """
    expected = TYPE_TO_GEOJSON.get(target_type)

    # AnyGeometry accepts any type
    if expected == "*":
        return

    # Base WKBElement accepts any type
    if target_type is WKBElement:
        return

    if expected is None:
        # Unknown target type - allow any (for custom subclasses)
        return

    if geojson_type != expected:
        raise GeoJSONTypeError(expected=expected, received=geojson_type)


def geometry_decoder(
    target_type: type[WKBElement],
    value: dict[str, Any] | WKBElement,
    srid: int = DEFAULT_SRID,
) -> WKBElement:
    """Decode GeoJSON to WKBElement.

    Args:
        target_type: The WKBElement subclass (Point, Polygon, etc.)
        value: GeoJSON dict or already-decoded WKBElement
        srid: Spatial reference ID (default: 4326 for WGS84)

    Returns:
        WKBElement instance

    Raises:
        GeoJSONValidationError: If GeoJSON structure is invalid
        GeoJSONTypeError: If geometry type doesn't match target_type
    """
    # If already decoded, return as-is
    if isinstance(value, WKBElement):
        return value

    # Extract geometry from Feature/FeatureCollection if needed
    geometry_dict = _extract_geometry(value)

    # Validate geometry type matches target type
    geojson_type = geometry_dict.get("type")
    if geojson_type is None:
        msg = "Geometry missing 'type' field"
        raise GeoJSONValidationError(msg)
    _validate_geometry_type(target_type, geojson_type)

    # Convert to WKBElement with SRID
    try:
        shapely_geom = shape(geometry_dict)
    except Exception as e:
        msg = f"Invalid {geojson_type} coordinates: {e}"
        raise GeoJSONValidationError(msg) from e

    return target_type(dumps(shapely_geom), srid=srid)  # type: ignore[call-arg]


def _isclass(cl: type[Any]) -> bool:
    """Check if cl is a class (can be used with issubclass)."""
    try:
        return issubclass(cl, cl)
    except TypeError:
        return False


def _geometry_predicate(target_type: type[Any]) -> bool:
    """Check if target_type is a WKBElement subclass."""
    if not _isclass(target_type):
        return False
    return issubclass(target_type, WKBElement)


class GeoAlchemyPlugin(InitPluginProtocol):
    """Litestar plugin for GeoAlchemy2 geometry types.

    Args:
        srid: Default SRID for decoded geometries (default: 4326 for WGS84)

    Example:
        ```python
        from litestar import Litestar
        from litestar_geoalchemy import GeoAlchemyPlugin

        app = Litestar(
            plugins=[GeoAlchemyPlugin(srid=4326)]
        )
        ```
    """

    def __init__(self, srid: int = DEFAULT_SRID) -> None:
        self.srid = srid

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        # Add type encoders
        _type_encoders = app_config.type_encoders or {}
        _type_encoders.update(type_encoders)  # type: ignore[attr-defined]
        app_config.type_encoders = _type_encoders

        # Create decoder with configured SRID
        decoder_with_srid = partial(geometry_decoder, srid=self.srid)

        # Add type decoders
        existing_decoders = list(app_config.type_decoders or [])
        decoder_tuple = (_geometry_predicate, decoder_with_srid)
        if decoder_tuple not in existing_decoders:
            existing_decoders.append(decoder_tuple)
        app_config.type_decoders = existing_decoders

        # Add OpenAPI schema plugin
        app_config.plugins.append(GeoalchemySchemaPlugin())
        return app_config
