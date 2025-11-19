from geoalchemy2 import Geometry
from litestar._openapi.schema_generation import SchemaCreator
from litestar.openapi.spec import OpenAPIType, Schema
from litestar.plugins import OpenAPISchemaPlugin
from litestar.typing import FieldDefinition

from .types import (
    LineString,
    Point,
    Polygon,
)

coordinate = Schema(
    type=OpenAPIType.ARRAY,
    description="Coordinates.",
    items=Schema(type=OpenAPIType.NUMBER),
    min_length=2,
    max_length=3,
)
point = Schema(
    type=OpenAPIType.ARRAY,
    description="Coordinates.",
    min_length=1,
    max_length=1,
    items=coordinate,
)

line_string = Schema(
    type=OpenAPIType.ARRAY,
    description="Coordinates.",
    min_length=2,
    items=coordinate,
)
polygon_part = Schema(
    type=OpenAPIType.ARRAY,
    description="Coordinates.",
    min_length=4,
    items=coordinate,
)
polygon = Schema(
    type=OpenAPIType.ARRAY,
    description="Coordinates.",
    min_length=1,
    items=polygon_part,
)
multipoint = Schema(
    type=OpenAPIType.ARRAY,
    description="Coordinates.",
    min_length=1,
    items=point,
)
multilinestring = Schema(
    type=OpenAPIType.ARRAY,
    description="Coordinates.",
    min_length=1,
    items=line_string,
)

multipolygon = Schema(
    type=OpenAPIType.ARRAY,
    description="Coordinates.",
    min_length=1,
    items=polygon,
)

point_schema = Schema(
    type=OpenAPIType.OBJECT,
    properties={
        "type": Schema(
            type=OpenAPIType.STRING,
            default="Point",
            description="Geometry Type.",
        ),
        "coordinates": point,
    },
)

line_string_schema = Schema(
    type=OpenAPIType.OBJECT,
    properties={
        "type": Schema(
            type=OpenAPIType.STRING,
            default="LineString",
            description="Geometry Type.",
        ),
        "coordinates": line_string,
    },
)

polygon_schema = Schema(
    type=OpenAPIType.OBJECT,
    properties={
        "type": Schema(
            type=OpenAPIType.STRING,
            default="Polygon",
            description="Geometry Type.",
        ),
        "coordinates": polygon,
    },
)


class GeoalchemySchemaPlugin(OpenAPISchemaPlugin):
    @staticmethod
    def is_plugin_supported_type(value) -> bool:  # noqa: ANN001
        return value in (Geometry, Point, LineString, Polygon)

    def to_openapi_schema(
        self,
        field_definition: FieldDefinition,
        schema_creator: SchemaCreator,  # noqa: ARG002
    ) -> Schema:
        if field_definition.annotation == Geometry:
            return Schema(one_of=[point_schema, line_string_schema, polygon_schema])

        if field_definition.annotation == Point:
            return point_schema

        if field_definition.annotation == LineString:
            return line_string_schema

        if field_definition.annotation == Polygon:
            return polygon_schema

        msg = f"Unsupported type {field_definition.annotation}"
        raise ValueError(msg)
