import geoalchemy2.shape
import shapely
from litestar import Litestar, get, post
from litestar.testing import TestClient

from litestar_geoalchemy.plugin import GeoAlchemyPlugin
from litestar_geoalchemy.types import Point, from_wkb_element


@get("/geometry", sync_to_thread=True)
def get_geometry() -> Point:  # type: ignore[return-value]
    shape = shapely.from_geojson('{"type": "Point", "coordinates": [12.34, 56.78]}')
    geometry = geoalchemy2.shape.from_shape(shape)

    return from_wkb_element(Point, geometry)


@post("/geometry", sync_to_thread=True)
def post_geometry(data: Point) -> Point:
    return data


def create_app() -> Litestar:
    return Litestar(route_handlers=[get_geometry, post_geometry], plugins=[GeoAlchemyPlugin()], debug=True)


def test_get_geometry_serialization():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/geometry")
        if response.status_code != 200:
            msg = "Expected status 200"
            raise AssertionError(msg)
        data = response.json()
        if data["type"] != "Point":
            msg = "Expected type Point"
            raise AssertionError(msg)
        if not isinstance(data["coordinates"], list):
            msg = "Coordinates should be list"
            raise TypeError(msg)
        if len(data["coordinates"]) < 2:
            msg = "Insufficient coordinate length"
            raise AssertionError(msg)


def test_post_geometry_deserialization():
    app = create_app()
    with TestClient(app) as client:
        geojson_payload = {"type": "Point", "coordinates": [98.76, 54.32]}
        response = client.post("/geometry", json=geojson_payload)
        if response.status_code != 201:
            msg = "Expected status 201"
            raise AssertionError(msg)
        data = response.json()
        if data["type"] != "Point":
            msg = "Expected type Point"
            raise AssertionError(msg)
        if not isinstance(data["coordinates"], list):
            msg = "Coordinates should be list"
            raise TypeError(msg)
        if len(data["coordinates"]) < 2:
            msg = "Insufficient coordinate length"
            raise AssertionError(msg)
