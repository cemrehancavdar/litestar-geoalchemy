import nox
from nox import options

options.default_venv_backend = "uv"


PYTHON_VERSIONS = [
    "3.10",
    "3.11"
]

LITESTAR_VERSIONS = ["2.0", "2.1", "2.2", "2.3", "2.4", "2.5", "latest"]
GEOALCHEMY_VERSIONS = ["0.16", "0.17", "0.18", "latest"]
SHAPELY_VERSIONS = ["2.0.0", "2.1.0", "2.1.2", "latest"]


def install_dep(session, pkg, version):
    """Install exact version or latest."""
    if version == "latest":
        spec = pkg
    else:
        spec = f"{pkg}=={version}"
    session.install(spec)


@nox.session(python=PYTHON_VERSIONS)
@nox.parametrize("ls_ver", LITESTAR_VERSIONS)
@nox.parametrize("ga_ver", GEOALCHEMY_VERSIONS)
@nox.parametrize("shp_ver", SHAPELY_VERSIONS)
def discover_baseline(session, ls_ver, ga_ver, shp_ver):
    """
    Try progressively older dependency versions until the package breaks.
    The first version where tests PASS becomes the baseline.
    """

    session.log(f"Testing: Python={session.python}, Litestar={ls_ver}, GeoAlchemy2={ga_ver}, Shapely={shp_ver}")

    try:
        install_dep(session, "litestar", ls_ver)
        install_dep(session, "geoalchemy2", ga_ver)
        install_dep(session, "shapely", shp_ver)
        session.install(".")
        session.install("pytest")
    except Exception:
        session.error("Failed to install combination.")

    try:
        session.run("pytest", "-q")
    except Exception:
        session.error("Tests failed for this combination.")
