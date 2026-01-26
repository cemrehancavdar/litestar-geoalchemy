# Litestar GeoAlchemy2 Plugin

A Litestar plugin for seamless GeoJSON serialization with GeoAlchemy2/PostGIS.

## Features

- **Automatic serialization**: WKBElement to GeoJSON on response
- **Automatic deserialization**: GeoJSON to WKBElement on request
- **Works with SQLAlchemyDTO**: Return models directly, no manual mapping
- **All geometry types**: Point, LineString, Polygon, Multi*, GeometryCollection
- **Feature support**: Accepts raw geometry, Feature, or FeatureCollection input
- **Type validation**: Point field rejects Polygon input with clear errors
- **Configurable SRID**: Default 4326 (WGS84), customizable per-app
- **OpenAPI schemas**: Full GeoJSON spec in Swagger UI

## Installation

```bash
pip install litestar-geoalchemy advanced-alchemy
# or
uv add litestar-geoalchemy advanced-alchemy
```

## Quick Start

```python
from advanced_alchemy.extensions.litestar import SQLAlchemyDTO, SQLAlchemyDTOConfig
from geoalchemy2 import Geometry
from litestar import Litestar, get, post
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from litestar_geoalchemy import GeoAlchemyPlugin, Point


# Model
class Base(DeclarativeBase):
    pass


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    location: Mapped[Point] = mapped_column(Geometry("POINT"))  # type: ignore[assignment]


# DTOs
class CityReadDTO(SQLAlchemyDTO[City]):
    config = SQLAlchemyDTOConfig()


class CityWriteDTO(SQLAlchemyDTO[City]):
    config = SQLAlchemyDTOConfig(exclude={"id"})


# Routes - return models directly!
@get("/cities/{city_id:int}", return_dto=CityReadDTO)
async def get_city(city_id: int, session: AsyncSession) -> City:
    return await session.get(City, city_id)


@post("/cities", dto=CityWriteDTO, return_dto=CityReadDTO)
async def create_city(data: City, session: AsyncSession) -> City:
    session.add(data)
    await session.commit()
    return data


# App
app = Litestar(
    route_handlers=[get_city, create_city],
    plugins=[GeoAlchemyPlugin()],
)
```

## Response

```json
{
    "id": 1,
    "name": "Paris",
    "location": {
        "type": "Point",
        "coordinates": [2.35, 48.86]
    }
}
```

## Input Formats

The plugin accepts three GeoJSON input formats:

```python
# 1. Raw geometry
{"type": "Point", "coordinates": [2.35, 48.86]}

# 2. Feature (geometry extracted automatically)
{
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [2.35, 48.86]},
    "properties": {"name": "Paris"}
}

# 3. FeatureCollection (single feature)
{
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [2.35, 48.86]},
        "properties": {}
    }]
}
```

## Geometry Types

```python
from litestar_geoalchemy import (
    Point,
    LineString,
    Polygon,
    MultiPoint,
    MultiLineString,
    MultiPolygon,
    GeometryCollection,
    AnyGeometry,  # Accepts any geometry type
)
```

## Configuration

### Custom SRID

Default is 4326 (WGS84). For Web Mercator or other projections:

```python
app = Litestar(
    plugins=[GeoAlchemyPlugin(srid=3857)],
)
```

## Error Handling

The plugin provides clear, specific error messages:

```python
from litestar_geoalchemy import GeoJSONError, GeoJSONTypeError, GeoJSONValidationError
```

| Error | Message |
|-------|---------|
| Type mismatch | `Expected Point geometry, got Polygon` |
| Missing coordinates | `Point missing required 'coordinates' field` |
| Missing type | `GeoJSON missing required 'type' field` |
| Unknown type | `Unknown GeoJSON type: InvalidType` |

## Requirements

- Python 3.11+
- Litestar 2.x
- GeoAlchemy2
- Shapely
- PostGIS database (for production)

## Demo

Run the demo app with PostGIS testcontainer (PEP 723 compatible):

```bash
git clone https://github.com/cemrehancavdar/litestar-geoalchemy
cd litestar-geoalchemy
uv run demo/app.py
```

Open http://localhost:8001/schema/swagger

## License

MIT
