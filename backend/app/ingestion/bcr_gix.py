"""Cliente de la API GIX de la Bolsa de Comercio de Rosario.

Basado en el manual de usuario de la BCR (abril 2025). Entrega los registros
originales (los items de ``data``, sin modificar) para pasarlos a
``run_import``. No normaliza ni convierte nada.

=============================  QUÉ ESTÁ CONFIRMADO  =============================
Confirmado en el Swagger de la BCR (capturas del usuario, 2026-11-23):
* ``POST /v1.0/Login`` recibe ``api_key`` y ``secret`` como HEADERS.
* ``GET /v1.0/PreciosCamara`` con ``idGrano``, ``fechaConcertacionDesde``,
  ``fechaConcertacionHasta`` y ``page`` en query string.

* El token va en el header ``Authorization`` (esquema "Bearer (apiKey)").
* ``GET /v1.0/Cotizacion`` con ``page`` como único parámetro.
* URL base de pruebas (UAT): ``https://apiuat.bcr.com.ar/gix``; la URL del
  login queda ``https://apiuat.bcr.com.ar/gix/v1.0/Login``.

Confirmado en el manual: token en ``data.token`` (empieza con "Bearer "),
``page`` para paginar, página de 10 registros, ``metadata.totalPages`` y
rango máximo de 7 días por consulta.

=========================  TODAVÍA NO CONFIRMADO  =========================
Se verifica con la primera respuesta real:
* Formato de fecha: el manual dice YYYY-MM-DD, el Swagger tipifica el
  parámetro como date-time. Se envía YYYY-MM-DD (el del manual).
* URL base productiva: se supone ``https://api.bcr.com.ar/gix`` por analogía
  con la de pruebas; no está confirmada.
* Si los datos del ambiente UAT son reales o de prueba. Por eso cada lote
  guarda en ``parameters`` la URL base de la que vino.

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

API_VERSION = "/v1.0"  # confirmado en el Swagger

LOGIN_METHOD = "POST"  # confirmado
LOGIN_PATH = f"{API_VERSION}/Login"  # confirmado
DATA_METHOD = "GET"  # confirmado
PRECIOS_CAMARA_PATH = f"{API_VERSION}/PreciosCamara"  # confirmado
COTIZACION_PATH = f"{API_VERSION}/Cotizacion"  # confirmado

AUTH_HEADER = "Authorization"  # confirmado

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

    @property
    def base_url(self) -> str:
        """URL base del ambiente al que apunta el cliente (sin credenciales)."""
        return str(self._http.base_url).rstrip("/")

    def __repr__(self) -> str:  # nunca mostrar credenciales ni token
        return f"GixClient(base_url={self._http.base_url!s})"

    # ------------------------------------------------------------------ auth

    def login(self) -> None:
        """Obtiene un token nuevo (vale 24 horas según el manual)."""
        response = self._http.request(
            LOGIN_METHOD,
            LOGIN_PATH,
            headers={"api_key": self._api_key, "secret": self._secret},
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
            "base_url": client.base_url,  # distingue pruebas (UAT) de producción
            "endpoint": PRECIOS_CAMARA_PATH,
            "idGrano": id_grano,
            "desde": desde.isoformat(),
            "hasta": hasta.isoformat(),
        },
    )
