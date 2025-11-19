from typing import Any

from geoalchemy2.shape import to_shape
from geoalchemy2.types import WKBElement  # pyright: ignore[reportPrivateImportUsage]
from litestar.config.app import AppConfig
from litestar.plugins import InitPluginProtocol
from shapely.geometry import mapping, shape
from shapely.wkb import dumps

from litestar_geoalchemy.openapi import GeoalchemySchemaPlugin

"""GeoAlchemy2 + Litestar plugin.

Adds per-geometry encoders so Litestar can serialize concrete geometry
subclasses (Point, LineString, Polygon, Multi*, GeometryCollection) directly
without falling back to the base WKBElement encoder lookup. While the generic
WKBElement encoder would work, explicit entries improve clarity and allow
future specialization per geometry type if desired.
"""


def _geojson_encoder(geom: WKBElement) -> dict[str, Any]:  # GeoJSON dict
    return mapping(to_shape(geom))


type_encoders = {
    WKBElement: _geojson_encoder,
}


def geometry_decoder(target_type: WKBElement, value: dict[str, Any]) -> WKBElement:
    return target_type(dumps(shape(value)))  # type: ignore[call-arg]


def isclass(cl: type[Any]):
    try:
        return issubclass(cl, cl)
    except TypeError:
        return False


def geometry_predicate(target_type: type[Any]):
    if not isclass(target_type):
        return False
    return issubclass(target_type, WKBElement)


type_decoders = {
    (geometry_predicate, geometry_decoder),
}


class GeoAlchemyPlugin(InitPluginProtocol):
    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        _type_encoders = app_config.type_encoders or {}
        _type_encoders.update(type_encoders)  # type: ignore[attr-defined]
        app_config.type_encoders = _type_encoders

        existing_decoders = list(app_config.type_decoders or [])
        for decoder_tuple in type_decoders:
            if decoder_tuple not in existing_decoders:
                existing_decoders.append(decoder_tuple)
        app_config.type_decoders = existing_decoders

        app_config.plugins.append(GeoalchemySchemaPlugin())
        return app_config
