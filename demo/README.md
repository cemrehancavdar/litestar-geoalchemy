# Demo App

Uses testcontainers PostGIS for real geometry column support.

## Models

```python
class City(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    location: Mapped[WKBElement] = mapped_column(Geometry("POINT", srid=4326))

class Park(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    boundary: Mapped[WKBElement] = mapped_column(Geometry("POLYGON", srid=4326))
```

## Run

```bash
# Requires Docker running
uv run litestar --app demo.app:app run --reload
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/cities` | List cities |
| GET | `/cities/{id}` | Get city |
| POST | `/cities` | Create city |
| DELETE | `/cities/{id}` | Delete city |
| GET | `/parks` | List parks |
| GET | `/parks/{id}` | Get park |
| POST | `/parks` | Create park |
| DELETE | `/parks/{id}` | Delete park |
| GET | `/test/point` | Return Point type |
| GET | `/test/polygon` | Return Polygon type |
| POST | `/test/point` | Echo Point |
| POST | `/test/polygon` | Echo Polygon |

## Key Finding

GeoAlchemy2 `Geometry` columns return `WKBElement` at runtime, NOT typed subclasses:

```python
city.location  # → WKBElement (not Point)
park.boundary  # → WKBElement (not Polygon)
```

The plugin's encoder handles this because it checks `isinstance(x, WKBElement)`.
