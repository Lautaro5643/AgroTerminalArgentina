"""Cliente de la API GIX de la Bolsa de Comercio de Rosario.

Basado en el manual de usuario de la BCR (abril 2025). Entrega los registros
originales (los items de ``data``, sin modificar) para pasarlos a
``run_import``. No normaliza ni convierte nada.

=====================  SUPUESTOS NO CONFIRMADOS POR EL MANUAL  =====================
El manual NO indica lo siguiente. Se asumió lo más habitual y debe verificarse
contra el Swagger de la BCR (https://apiuat.bcr.com.ar/gix/index.html) o con
la primera respuesta real. Todo está concentrado en las constantes de abajo:

* LOGIN_METHOD / LOGIN_PATH / cómo se envían api_key y secret (se asume POST
  con cuerpo JSON {"api_key": ..., "secret": ...}).
* AUTH_HEADER: nombre del header del token (se asume "Authorization").
* Método HTTP de /PreciosCamara y /Cotizacion (se asume GET).
* URL base de cada ambiente: no figura; se configura en BCR_GIX_BASE_URL.

Sí figura en el manual (y se usa como tal): token en ``data.token`` (empieza
con "Bearer "), parámetros en query string, ``page`` para paginar, página de
10 registros, ``metadata.totalPages``, fechas YYYY-MM-DD y rango máximo de
7 días por consulta.

Discrepancia del manual: la tabla de ids dice Trigo=1, pero el ejemplo de
respuesta muestra ``iD_Grano: 8`` para Trigo. Por eso el cliente recibe el
``id_grano`` del llamador y no trae una tabla propia.
=====================================================================================
"""

from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.ingestion.importer import ImportResult, run_import
from app.models import DataSource

SOURCE_CODE = "bcr_gix"

# --- Supuestos (ver el encabezado del módulo) ---
LOGIN_METHOD = "POST"
LOGIN_PATH = "/Login"
AUTH_HEADER = "Authorization"
DATA_METHOD = "GET"
# ------------------------------------------------

PRECIOS_CAMARA_PATH = "/PreciosCamara"
COTIZACION_PATH = "/Cotizacion"

# El manual: "el rango de fechas no puede superar 7 días". Se usan ventanas de
# 7 días corridos inclusive, que es la interpretación más conservadora.
MAX_DAYS_PER_QUERY = 7
# Tope de seguridad contra paginación infinita por un error de la API.
MAX_PAGES = 10_000


class GixError(RuntimeError):
    """Error al consultar la API GIX."""


class GixAuthError(GixError):
    """No se pudo autenticar (credenciales inválidas o token rechazado)."""


def date_windows(
    desde: date, hasta: date, max_days: int = MAX_DAYS_PER_QUERY
) -> Iterator[tuple[date, date]]:
    """Parte [desde, hasta] en ventanas contiguas de hasta ``max_days`` días."""
    if desde > hasta:
        raise ValueError("'desde' no puede ser posterior a 'hasta'")
    inicio = desde
    while inicio <= hasta:
        fin = min(inicio + timedelta(days=max_days - 1), hasta)
        yield inicio, fin
        inicio = fin + timedelta(days=1)


class GixClient:
    """Cliente HTTP de la API GIX. Usar como context manager o llamar a close()."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        secret: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._secret = secret
        self._token: str | None = None
        self._http = httpx.Client(
            base_url=base_url, timeout=timeout, transport=transport
        )

    @classmethod
    def from_settings(
        cls,
        settings: Settings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> "GixClient":
        settings = settings or get_settings()
        if not (
            settings.bcr_gix_base_url
            and settings.bcr_gix_api_key
            and settings.bcr_gix_secret
        ):
            raise GixError(
                "Faltan BCR_GIX_BASE_URL, BCR_GIX_API_KEY o BCR_GIX_SECRET en .env"
            )
        return cls(
            settings.bcr_gix_base_url,
            settings.bcr_gix_api_key.get_secret_value(),
            settings.bcr_gix_secret.get_secret_value(),
            transport=transport,
        )

    def __enter__(self) -> "GixClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def __repr__(self) -> str:  # nunca mostrar credenciales ni token
        return f"GixClient(base_url={self._http.base_url!s})"

    # ------------------------------------------------------------------ auth

    def login(self) -> None:
        """Obtiene un token nuevo (vale 24 horas según el manual)."""
        response = self._http.request(
            LOGIN_METHOD,
            LOGIN_PATH,
            json={"api_key": self._api_key, "secret": self._secret},
        )
        if response.status_code in (400, 401, 403):
            raise GixAuthError(f"Login rechazado (HTTP {response.status_code})")
        body = self._parse(response, "Login")
        token = (body.get("data") or {}).get("token")
        if not isinstance(token, str) or not token:
            raise GixAuthError("La respuesta de /Login no trae data.token")
        # El manual dice que el valor ya empieza con "Bearer ".
        self._token = token if token.startswith("Bearer ") else f"Bearer {token}"

    # --------------------------------------------------------------- requests

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """Consulta con reintento único si el token venció (HTTP 401)."""
        if self._token is None:
            self.login()
        for intento in (1, 2):
            response = self._http.request(
                DATA_METHOD,
                path,
                params=params,
                headers={AUTH_HEADER: self._token or ""},
            )
            if response.status_code == 401 and intento == 1:
                self.login()
                continue
            if response.status_code == 401:
                raise GixAuthError(f"{path}: token rechazado tras renovarlo")
            return self._parse(response, path)
        raise GixError("unreachable")  # pragma: no cover

    @staticmethod
    def _parse(response: httpx.Response, where: str) -> dict[str, Any]:
        # Solo se informa el código HTTP: el cuerpo podría contener datos
        # sensibles y nunca se registra el token.
        if response.status_code != 200:
            raise GixError(f"{where}: HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise GixError(f"{where}: la respuesta no es JSON") from exc
        if not isinstance(body, dict):
            raise GixError(f"{where}: formato de respuesta inesperado")
        status = body.get("status")
        if isinstance(status, dict) and status.get("code") not in (None, 200):
            raise GixError(f"{where}: la API informó status {status.get('code')}")
        return body

    def _paginate(self, path: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        page = 1
        while page <= MAX_PAGES:
            body = self._get(path, {**params, "page": page})
            data = body.get("data")
            if not isinstance(data, list):
                raise GixError(f"{path}: la respuesta no trae 'data' como lista")
            yield from data
            total_pages = (body.get("metadata") or {}).get("totalPages")
            if not isinstance(total_pages, int) or page >= total_pages:
                return
            page += 1
        raise GixError(f"{path}: demasiadas páginas (tope {MAX_PAGES})")

    # ------------------------------------------------------------- endpoints

    def precios_camara(
        self, id_grano: int, desde: date, hasta: date
    ) -> Iterator[dict[str, Any]]:
        """Precios de cámara (pizarra) de un grano en un rango de fechas.

        Parte el rango en ventanas de 7 días y recorre todas las páginas.
        Entrega los items originales de ``data``.
        """
        for inicio, fin in date_windows(desde, hasta):
            yield from self._paginate(
                PRECIOS_CAMARA_PATH,
                {
                    "idGrano": id_grano,
                    "fechaConcertacionDesde": inicio.isoformat(),
                    "fechaConcertacionHasta": fin.isoformat(),
                },
            )

    def cotizacion(self) -> Iterator[dict[str, Any]]:
        """Cotizaciones de divisas y billetes del BNA."""
        yield from self._paginate(COTIZACION_PATH, {})


# ------------------------------------------------------------ integración


def ensure_source(session: Session) -> DataSource:
    """Devuelve la fuente 'bcr_gix', creándola si no existe."""
    source = session.scalar(select(DataSource).where(DataSource.code == SOURCE_CODE))
    if source is None:
        source = DataSource(
            code=SOURCE_CODE,
            name="Bolsa de Comercio de Rosario - API GIX",
            license_notes=(
                "Costo y condiciones de uso NO confirmados por la BCR "
                "(el manual no los menciona). Consulta pendiente."
            ),
        )
        session.add(source)
        session.commit()
    return source


def import_precios_camara(
    session: Session,
    client: GixClient,
    id_grano: int,
    desde: date,
    hasta: date,
) -> ImportResult:
    """Importa la pizarra de un grano como registros originales en un lote."""
    ensure_source(session)
    return run_import(
        session,
        SOURCE_CODE,
        client.precios_camara(id_grano, desde, hasta),
        parameters={
            "endpoint": PRECIOS_CAMARA_PATH,
            "idGrano": id_grano,
            "desde": desde.isoformat(),
            "hasta": hasta.isoformat(),
        },
    )
