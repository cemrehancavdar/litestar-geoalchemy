"""Database models for demo app.

Separate file for Alembic to import without app dependencies.
"""

from geoalchemy2 import Geometry
from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from litestar_geoalchemy.types import MultiPolygon, Point, Polygon


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
