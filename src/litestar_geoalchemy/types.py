from typing import TypeVar

from geoalchemy2 import WKBElement

T = TypeVar("T", bound=WKBElement)


class Point(WKBElement):
    def __init__(self, *args, **kwargs):
        self.geometry_type = "POINT"
        super().__init__(*args, **kwargs)


class LineString(WKBElement):
    def __init__(self, *args, **kwargs):
        self.geometry_type = "LINESTRING"
        super().__init__(*args, **kwargs)


class Polygon(WKBElement):
    def __init__(self, *args, **kwargs):
        self.geometry_type = "POLYGON"
        super().__init__(*args, **kwargs)


class MultiPolygon(WKBElement):
    def __init__(self, *args, **kwargs):
        self.geometry_type = "MULTIPOLYGON"
        super().__init__(*args, **kwargs)


class MultiLineString(WKBElement):
    def __init__(self, *args, **kwargs):
        self.geometry_type = "MULTILINESTRING"
        super().__init__(*args, **kwargs)


class MultiPoint(WKBElement):
    def __init__(self, *args, **kwargs):
        self.geometry_type = "MULTIPOINT"
        super().__init__(*args, **kwargs)


class GeometryCollection(WKBElement):
    def __init__(self, *args, **kwargs):
        self.geometry_type = "GEOMETRYCOLLECTION"
        super().__init__(*args, **kwargs)


class AnyGeometry(WKBElement):
    def __init__(self, *args, **kwargs):
        self.geometry_type = "GEOMETRY"
        super().__init__(*args, **kwargs)


def from_wkb_element(cls: type[T], wkb_element: WKBElement) -> T:
    """Convert a generic WKBElement to the subclass instance."""
    return cls(bytes(wkb_element.data))  # ensures proper subclass instance
