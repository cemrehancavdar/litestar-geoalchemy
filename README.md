# Litestar GeoAlchemy2 Plugin

> ⚠️ **Work In Progress** - This plugin is currently under development.

## Overview

A Litestar plugin for integrating GeoAlchemy2 with SQLAlchemy, providing seamless support for geographic and geometric data types in your Litestar applications.

## Features

- 🗺️ Geographic data type support via GeoAlchemy2
- 🔌 Easy integration with Litestar's SQLAlchemy plugin
- 🛠️ Automatic serialization/deserialization of geometric types
- 📦 Type-safe geometric operations (WIP)

## Installation

```bash
pip install litestar-geoalchemy
uv add litestar-geoalchemy
```

## Quick Start

```python
from litestar import Litestar
from litestar_geoalchemy import GeoAlchemyPlugin

app = Litestar(
    plugins=[GeoAlchemyPlugin()],
)
```

## Usage
WIP 

## Requirements

WIP

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
