# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "litestar-geoalchemy[pydantic]",
#     "advanced-alchemy>=1.8.2",
#     "asyncpg>=0.29.0",
#     "testcontainers[postgres]>=4.0.0",
#     "uvicorn>=0.30.0",
# ]
# ///
"""Demo: litestar-geoalchemy with Pydantic Geo* types.

Uses Geo* Annotated types (GeoPoint, GeoPolygon, etc.) with advanced-alchemy's
service/repository pattern. The Pydantic types handle GeoJSON <-> WKBElement
conversion seamlessly.

Run with: uv run python demo/pydantic_app.py
Swagger UI: http://127.0.0.1:8002/schema/swagger
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from geoalchemy2 import Geometry
from geoalchemy2.shape import from_shape
from litestar import Litestar, get, post
from litestar.datastructures import State
from litestar.di import Provide
from pydantic import BaseModel, ConfigDict
from shapely import MultiPolygon as ShapelyMultiPolygon
from shapely import Point as ShapelyPoint
from shapely import Polygon as ShapelyPolygon
from sqlalchemy import Integer, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from testcontainers.postgres import PostgresContainer

from litestar_geoalchemy import GeoAlchemyPlugin
from litestar_geoalchemy.pydantic import GeoMultiPolygon, GeoPoint, GeoPolygon
from litestar_geoalchemy.types import MultiPolygon, Point, Polygon

# =============================================================================
# Database Models
# =============================================================================


class Base(DeclarativeBase):
    pass


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[Point] = mapped_column(Geometry("POINT"), nullable=False)  # type: ignore[assignment]


class Park(Base):
    __tablename__ = "parks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    boundary: Mapped[Polygon] = mapped_column(Geometry("POLYGON"), nullable=False)  # type: ignore[assignment]


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    area: Mapped[MultiPolygon] = mapped_column(Geometry("MULTIPOLYGON"), nullable=False)  # type: ignore[assignment]


# =============================================================================
# Pydantic Models — Geo* types handle GeoJSON <-> WKBElement automatically
# =============================================================================


class CityReadModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    id: int
    name: str
    location: GeoPoint


class CityCreateModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str
    location: GeoPoint


class ParkReadModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    id: int
    name: str
    boundary: GeoPolygon


class RegionReadModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    id: int
    name: str
    area: GeoMultiPolygon


# =============================================================================
# Repositories + Services
# =============================================================================


class CityRepository(SQLAlchemyAsyncRepository[City]):
    model_type = City


class ParkRepository(SQLAlchemyAsyncRepository[Park]):
    model_type = Park


class RegionRepository(SQLAlchemyAsyncRepository[Region]):
    model_type = Region


class CityService(SQLAlchemyAsyncRepositoryService[City, CityRepository]):
    repository_type = CityRepository


class ParkService(SQLAlchemyAsyncRepositoryService[Park, ParkRepository]):
    repository_type = ParkRepository


class RegionService(SQLAlchemyAsyncRepositoryService[Region, RegionRepository]):
    repository_type = RegionRepository


# =============================================================================
# DI Providers
# =============================================================================


async def provide_db_session(state: State) -> AsyncGenerator[AsyncSession, None]:
    async with sessionmaker(bind=state.engine) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def provide_city_service(db_session: AsyncSession) -> AsyncGenerator[CityService, None]:
    async with CityService.new(session=db_session) as service:
        yield service


async def provide_park_service(db_session: AsyncSession) -> AsyncGenerator[ParkService, None]:
    async with ParkService.new(session=db_session) as service:
        yield service


async def provide_region_service(db_session: AsyncSession) -> AsyncGenerator[RegionService, None]:
    async with RegionService.new(session=db_session) as service:
        yield service


# =============================================================================
# Routes
# =============================================================================


@get("/cities", dependencies={"service": Provide(provide_city_service)})
async def list_cities(service: CityService) -> list[CityReadModel]:
    results = await service.list()
    return [CityReadModel.model_validate(city, from_attributes=True) for city in results]


@get("/cities/{city_id:int}", dependencies={"service": Provide(provide_city_service)})
async def get_city(city_id: int, service: CityService) -> CityReadModel:
    city = await service.get(city_id)
    return CityReadModel.model_validate(city, from_attributes=True)


@post("/cities", dependencies={"service": Provide(provide_city_service)})
async def create_city(data: CityCreateModel, service: CityService) -> CityReadModel:
    city = await service.create(data.model_dump())
    return CityReadModel.model_validate(city, from_attributes=True)


@get("/parks", dependencies={"service": Provide(provide_park_service)})
async def list_parks(service: ParkService) -> list[ParkReadModel]:
    results = await service.list()
    return [ParkReadModel.model_validate(park, from_attributes=True) for park in results]


@get("/regions", dependencies={"service": Provide(provide_region_service)})
async def list_regions(service: RegionService) -> list[RegionReadModel]:
    results = await service.list()
    return [RegionReadModel.model_validate(region, from_attributes=True) for region in results]


# =============================================================================
# Database lifecycle
# =============================================================================

sessionmaker = async_sessionmaker(expire_on_commit=False)


async def seed_data(session: AsyncSession) -> None:
    if await session.scalar(select(func.count()).select_from(City)) == 0:
        session.add(City(name="Paris", location=from_shape(ShapelyPoint(2.35, 48.86), srid=4326)))
        session.add(City(name="New York", location=from_shape(ShapelyPoint(-74.0, 40.71), srid=4326)))
        session.add(City(name="Tokyo", location=from_shape(ShapelyPoint(139.69, 35.68), srid=4326)))

    if await session.scalar(select(func.count()).select_from(Park)) == 0:
        coords = [(-73.97, 40.76), (-73.95, 40.80), (-73.96, 40.80), (-73.98, 40.77), (-73.97, 40.76)]
        session.add(Park(name="Central Park", boundary=from_shape(ShapelyPolygon(coords), srid=4326)))

    if await session.scalar(select(func.count()).select_from(Region)) == 0:
        poly1 = ShapelyPolygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        poly2 = ShapelyPolygon([(2, 2), (3, 2), (3, 3), (2, 3), (2, 2)])
        session.add(Region(name="Test Region", area=from_shape(ShapelyMultiPolygon([poly1, poly2]), srid=4326)))

    await session.commit()


@asynccontextmanager
async def db_lifespan(app: Litestar) -> AsyncGenerator[None, None]:
    container = PostgresContainer(image="postgis/postgis:16-3.4", username="test", password="test", dbname="test")
    container.start()

    sync_url = container.get_connection_url()
    async_url = sync_url.replace("psycopg2", "asyncpg").replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(async_url, echo=False)

    app.state.engine = engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with sessionmaker(bind=engine) as session:
        await seed_data(session)

    print(f"\nPostGIS: {async_url}")  # noqa: T201
    print("Swagger: http://127.0.0.1:8002/schema/swagger\n")  # noqa: T201

    try:
        yield
    finally:
        await engine.dispose()
        container.stop()


# =============================================================================
# App
# =============================================================================

app = Litestar(
    route_handlers=[list_cities, get_city, create_city, list_parks, list_regions],
    dependencies={"db_session": provide_db_session},
    plugins=[GeoAlchemyPlugin()],
    lifespan=[db_lifespan],
    debug=True,
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8002)
