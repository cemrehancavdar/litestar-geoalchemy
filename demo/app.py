# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "litestar-geoalchemy",
#     "advanced-alchemy>=1.8.2",
#     "asyncpg>=0.29.0",
#     "testcontainers[postgres]>=4.0.0",
#     "uvicorn>=0.30.0",
# ]
# ///
"""Demo app for litestar-geoalchemy plugin.

Uses SQLAlchemyDTO - no manual dataclasses needed!
Run with: uv run demo/app.py
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from advanced_alchemy.extensions.litestar import SQLAlchemyDTO, SQLAlchemyDTOConfig
from geoalchemy2.shape import from_shape
from litestar import Litestar, get, post
from litestar.datastructures import State
from litestar.exceptions import NotFoundException
from shapely import MultiPolygon as ShapelyMultiPolygon
from shapely import Point as ShapelyPoint
from shapely import Polygon as ShapelyPolygon
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from demo.models import Base, City as CityModel, Park as ParkModel, Region as RegionModel
from litestar_geoalchemy import GeoAlchemyPlugin
from litestar_geoalchemy.types import Point

# =============================================================================
# DTOs - SQLAlchemyDTO handles serialization automatically
# =============================================================================


class CityReadDTO(SQLAlchemyDTO[CityModel]):
    config = SQLAlchemyDTOConfig()


class CityWriteDTO(SQLAlchemyDTO[CityModel]):
    config = SQLAlchemyDTOConfig(exclude={"id"})


class ParkReadDTO(SQLAlchemyDTO[ParkModel]):
    config = SQLAlchemyDTOConfig()


class RegionReadDTO(SQLAlchemyDTO[RegionModel]):
    config = SQLAlchemyDTOConfig()


# =============================================================================
# Database setup
# =============================================================================

sessionmaker = async_sessionmaker(expire_on_commit=False)


async def provide_session(state: State) -> AsyncGenerator[AsyncSession, None]:
    async with sessionmaker(bind=state.engine) as session:
        yield session


async def seed_data(session: AsyncSession) -> None:
    if await session.scalar(select(func.count()).select_from(CityModel)) == 0:
        session.add(CityModel(name="Paris", location=from_shape(ShapelyPoint(2.35, 48.86), srid=4326)))
        session.add(CityModel(name="New York", location=from_shape(ShapelyPoint(-74.0, 40.71), srid=4326)))

    if await session.scalar(select(func.count()).select_from(ParkModel)) == 0:
        coords = [(-73.97, 40.76), (-73.95, 40.80), (-73.96, 40.80), (-73.98, 40.77), (-73.97, 40.76)]
        session.add(ParkModel(name="Central Park", boundary=from_shape(ShapelyPolygon(coords), srid=4326)))

    if await session.scalar(select(func.count()).select_from(RegionModel)) == 0:
        poly1 = ShapelyPolygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        poly2 = ShapelyPolygon([(2, 2), (3, 2), (3, 3), (2, 3), (2, 2)])
        session.add(RegionModel(name="Test Region", area=from_shape(ShapelyMultiPolygon([poly1, poly2]), srid=4326)))

    await session.commit()


@asynccontextmanager
async def db_lifespan(app: Litestar) -> AsyncGenerator[None, None]:
    container = PostgresContainer(image="postgis/postgis:16-3.4", username="test", password="test", dbname="test")
    container.start()

    sync_url = container.get_connection_url()
    async_url = sync_url.replace("psycopg2", "asyncpg").replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(async_url, echo=False)

    app.state.engine = engine
    app.state.container = container

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with sessionmaker(bind=engine) as session:
        await seed_data(session)

    print(f"\nPostGIS: {async_url}\n")  # noqa: T201

    try:
        yield
    finally:
        await engine.dispose()
        container.stop()


# =============================================================================
# Routes - Return models directly, DTOs handle serialization!
# =============================================================================


@get("/cities", operation_id="list_cities", return_dto=CityReadDTO)
async def list_cities(session: AsyncSession) -> list[CityModel]:
    result = await session.execute(select(CityModel))
    return list(result.scalars())


@get("/cities/{city_id:int}", operation_id="get_city", return_dto=CityReadDTO)
async def get_city(city_id: int, session: AsyncSession) -> CityModel:
    city = await session.get(CityModel, city_id)
    if not city:
        raise NotFoundException(f"City {city_id} not found")
    return city


@post("/cities", operation_id="create_city", dto=CityWriteDTO, return_dto=CityReadDTO)
async def create_city(data: CityModel, session: AsyncSession) -> CityModel:
    session.add(data)
    await session.commit()
    await session.refresh(data)
    return data


@get("/parks", operation_id="list_parks", return_dto=ParkReadDTO)
async def list_parks(session: AsyncSession) -> list[ParkModel]:
    result = await session.execute(select(ParkModel))
    return list(result.scalars())


@get("/parks/{park_id:int}", operation_id="get_park", return_dto=ParkReadDTO)
async def get_park(park_id: int, session: AsyncSession) -> ParkModel:
    park = await session.get(ParkModel, park_id)
    if not park:
        raise NotFoundException(f"Park {park_id} not found")
    return park


@get("/regions", operation_id="list_regions", return_dto=RegionReadDTO)
async def list_regions(session: AsyncSession) -> list[RegionModel]:
    result = await session.execute(select(RegionModel))
    return list(result.scalars())


# =============================================================================
# Direct geometry test routes
# =============================================================================


@dataclass
class PointInput:
    """For testing direct geometry input without model."""

    location: Point


@post("/test/point", operation_id="test_point_echo")
async def test_point_echo(data: PointInput) -> PointInput:
    return data


# =============================================================================
# App
# =============================================================================

app = Litestar(
    route_handlers=[
        list_cities,
        get_city,
        create_city,
        list_parks,
        get_park,
        list_regions,
        test_point_echo,
    ],
    dependencies={"session": provide_session},
    plugins=[GeoAlchemyPlugin()],
    lifespan=[db_lifespan],
    debug=True,
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)
