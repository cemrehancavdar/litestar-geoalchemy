"""Litestar plugin for GeoAlchemy2 geometry types.

Provides automatic GeoJSON <-> WKBElement serialization for Litestar routes.
"""

from litestar_geoalchemy.plugin import (
    DEFAULT_SRID,
    GeoAlchemyPlugin,
    GeoJSONError,
    GeoJSONTypeError,
    GeoJSONValidationError,
)
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

__all__ = [
    "DEFAULT_SRID",
    "AnyGeometry",
    "GeoAlchemyPlugin",
    "GeoJSONError",
    "GeoJSONTypeError",
    "GeoJSONValidationError",
    "GeometryCollection",
    "LineString",
    "MultiLineString",
    "MultiPoint",
    "MultiPolygon",
    "Point",
    "Polygon",
]
