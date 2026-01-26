"""OpenAPI schema generation for GeoJSON geometry types.

Supports all GeoJSON types per RFC 7946:
- Geometry: Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon, GeometryCollection
- Feature: geometry + properties
- FeatureCollection: array of features
"""

from geoalchemy2 import Geometry
from litestar._openapi.schema_generation import SchemaCreator
from litestar.openapi.spec import OpenAPIType, Schema
from litestar.plugins import OpenAPISchemaPlugin
from litestar.typing import FieldDefinition

from .types import (
    AnyGeometry,
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

# =============================================================================
# Coordinate schemas
# =============================================================================

coordinate = Schema(
    type=OpenAPIType.ARRAY,
    description="A position: [longitude, latitude] or [longitude, latitude, altitude]",
    items=Schema(type=OpenAPIType.NUMBER),
    min_length=2,
    max_length=3,
)

# Point coordinates: [lon, lat] or [lon, lat, alt]
point_coordinates = coordinate

line_string_coordinates = Schema(
    type=OpenAPIType.ARRAY,
    description="Array of positions forming a line.",
    min_length=2,
    items=coordinate,
)

linear_ring = Schema(
    type=OpenAPIType.ARRAY,
    description="A closed ring (first and last position must match).",
    min_length=4,
    items=coordinate,
)

polygon_coordinates = Schema(
    type=OpenAPIType.ARRAY,
    description="Array of linear rings (first is exterior, rest are holes).",
    min_length=1,
    items=linear_ring,
)

multipoint_coordinates = Schema(
    type=OpenAPIType.ARRAY,
    description="Array of point positions.",
    min_length=1,
    items=point_coordinates,
)

multilinestring_coordinates = Schema(
    type=OpenAPIType.ARRAY,
    description="Array of line coordinate arrays.",
    min_length=1,
    items=line_string_coordinates,
)

multipolygon_coordinates = Schema(
    type=OpenAPIType.ARRAY,
    description="Array of polygon coordinate arrays.",
    min_length=1,
    items=polygon_coordinates,
)

# =============================================================================
# Geometry schemas
# =============================================================================

point_schema = Schema(
    type=OpenAPIType.OBJECT,
    required=["type", "coordinates"],
    properties={
        "type": Schema(type=OpenAPIType.STRING, const="Point", description="Geometry type."),
        "coordinates": point_coordinates,
    },
)

line_string_schema = Schema(
    type=OpenAPIType.OBJECT,
    required=["type", "coordinates"],
    properties={
        "type": Schema(type=OpenAPIType.STRING, const="LineString", description="Geometry type."),
        "coordinates": line_string_coordinates,
    },
)

polygon_schema = Schema(
    type=OpenAPIType.OBJECT,
    required=["type", "coordinates"],
    properties={
        "type": Schema(type=OpenAPIType.STRING, const="Polygon", description="Geometry type."),
        "coordinates": polygon_coordinates,
    },
)

multipoint_schema = Schema(
    type=OpenAPIType.OBJECT,
    required=["type", "coordinates"],
    properties={
        "type": Schema(type=OpenAPIType.STRING, const="MultiPoint", description="Geometry type."),
        "coordinates": multipoint_coordinates,
    },
)

multilinestring_schema = Schema(
    type=OpenAPIType.OBJECT,
    required=["type", "coordinates"],
    properties={
        "type": Schema(type=OpenAPIType.STRING, const="MultiLineString", description="Geometry type."),
        "coordinates": multilinestring_coordinates,
    },
)

multipolygon_schema = Schema(
    type=OpenAPIType.OBJECT,
    required=["type", "coordinates"],
    properties={
        "type": Schema(type=OpenAPIType.STRING, const="MultiPolygon", description="Geometry type."),
        "coordinates": multipolygon_coordinates,
    },
)

# All simple geometry schemas (used in oneOf)
all_geometry_schemas = [
    point_schema,
    line_string_schema,
    polygon_schema,
    multipoint_schema,
    multilinestring_schema,
    multipolygon_schema,
]

# GeometryCollection contains other geometries
geometry_collection_schema = Schema(
    type=OpenAPIType.OBJECT,
    required=["type", "geometries"],
    properties={
        "type": Schema(type=OpenAPIType.STRING, const="GeometryCollection", description="Geometry type."),
        "geometries": Schema(
            type=OpenAPIType.ARRAY,
            description="Array of geometry objects.",
            items=Schema(one_of=all_geometry_schemas),
        ),
    },
)

# Any geometry type
any_geometry_schema = Schema(one_of=[*all_geometry_schemas, geometry_collection_schema])

# =============================================================================
# Feature schemas (for input - decoder accepts these)
# =============================================================================

feature_schema = Schema(
    type=OpenAPIType.OBJECT,
    required=["type", "geometry"],
    description="A GeoJSON Feature wrapping a geometry with optional properties.",
    properties={
        "type": Schema(type=OpenAPIType.STRING, const="Feature", description="Must be 'Feature'."),
        "geometry": any_geometry_schema,
        "properties": Schema(
            type=OpenAPIType.OBJECT,
            description="Arbitrary properties associated with the geometry.",
            additional_properties=Schema(),  # Allow any properties
        ),
        "id": Schema(
            one_of=[Schema(type=OpenAPIType.STRING), Schema(type=OpenAPIType.INTEGER)],
            description="Optional feature identifier.",
        ),
    },
)

feature_collection_schema = Schema(
    type=OpenAPIType.OBJECT,
    required=["type", "features"],
    description="A GeoJSON FeatureCollection containing exactly one feature (for single geometry fields).",
    properties={
        "type": Schema(type=OpenAPIType.STRING, const="FeatureCollection", description="Must be 'FeatureCollection'."),
        "features": Schema(
            type=OpenAPIType.ARRAY,
            description="Array of Feature objects (must contain exactly 1 for single geometry fields).",
            items=feature_schema,
            min_length=1,
            max_length=1,
        ),
    },
)

# =============================================================================
# Type mappings
# =============================================================================

SUPPORTED_TYPES = (
    Geometry,
    AnyGeometry,
    Point,
    LineString,
    Polygon,
    MultiPoint,
    MultiLineString,
    MultiPolygon,
    GeometryCollection,
)

TYPE_TO_SCHEMA: dict[type, Schema] = {
    Point: point_schema,
    LineString: line_string_schema,
    Polygon: polygon_schema,
    MultiPoint: multipoint_schema,
    MultiLineString: multilinestring_schema,
    MultiPolygon: multipolygon_schema,
    GeometryCollection: geometry_collection_schema,
}


def _schema_with_feature_input(geometry_schema: Schema) -> Schema:
    """Create schema that accepts raw geometry, Feature, or FeatureCollection."""
    return Schema(
        one_of=[
            geometry_schema,
            feature_schema,
            feature_collection_schema,
        ],
        description="Accepts raw geometry, Feature, or FeatureCollection (with single feature).",
    )


# =============================================================================
# Plugin
# =============================================================================


class GeoalchemySchemaPlugin(OpenAPISchemaPlugin):
    @staticmethod
    def is_plugin_supported_type(value) -> bool:  # noqa: ANN001
        return value in SUPPORTED_TYPES

    def to_openapi_schema(
        self,
        field_definition: FieldDefinition,
        schema_creator: SchemaCreator,  # noqa: ARG002
    ) -> Schema:
        annotation = field_definition.annotation

        # Generic Geometry or AnyGeometry: accept any geometry type + Feature wrappers
        if annotation in (Geometry, AnyGeometry):
            return _schema_with_feature_input(any_geometry_schema)

        # Specific geometry type
        if annotation in TYPE_TO_SCHEMA:
            return _schema_with_feature_input(TYPE_TO_SCHEMA[annotation])

        msg = f"Unsupported type {annotation}"
        raise ValueError(msg)
