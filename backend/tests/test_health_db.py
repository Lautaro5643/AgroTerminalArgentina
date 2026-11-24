from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_db
from app.main import app


class SesionQueFunciona:
    def execute(self, *args, **kwargs):
        return None


class SesionQueFalla:
    def execute(self, *args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("conexion rechazada"))


def _cliente_con_sesion(sesion):
    app.dependency_overrides[get_db] = lambda: sesion
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_health_db_ok_cuando_la_base_responde():
    response = _cliente_con_sesion(SesionQueFunciona()).get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_db_503_cuando_la_base_falla():
    response = _cliente_con_sesion(SesionQueFalla()).get("/health/db")

    assert response.status_code == 503
    assert response.json() == {"detail": "Base de datos no disponible"}
    # No se filtra el detalle interno del error.
    assert "conexion rechazada" not in response.text
