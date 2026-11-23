"""Tests del cliente GIX con respuestas SIMULADAS.

La estructura de las respuestas copia la del manual de la BCR, pero todos los
valores son DATOS DE PRUEBA inventados. Nada de esto es información de mercado
ni confirma el comportamiento real de la API (login, método HTTP y nombre del
header son supuestos; ver el encabezado de app/ingestion/bcr_gix.py).
"""

from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.ingestion.bcr_gix import (
    LOGIN_PATH,
    PRECIOS_CAMARA_PATH,
    GixAuthError,
    GixClient,
    GixError,
    date_windows,
    import_precios_camara,
)
from app.models import ImportBatch, RawRecord

TOKEN = "Bearer token-de-prueba-1"


def _item(n: int, grano: int = 21) -> dict:
    return {
        "iD_Pizarra": 1000 + n,
        "fecha_Operacion_Pizarra": "2026-01-05T03:00:00",
        "iD_Cotizacion": 5000 + n,
        "precio_Cotizacion": 100000 + n,
        "esEstimado_Cotizacion": False,
        "iD_Grano": grano,
        "nombre_Grano": "Grano de prueba",
    }


def _envelope(data: list, page: int = 1, total_pages: int = 1) -> dict:
    return {
        "status": {"code": 200, "message": "Ok", "details": ""},
        "metadata": {
            "totalRecords": len(data),
            "pageSize": 10,
            "currentPage": page,
            "totalPages": total_pages,
            "nextPageLink": None,
            "prevPageLink": None,
        },
        "data": data,
    }


def _login_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"data": {"token": TOKEN}})


def _cliente(handler) -> GixClient:
    return GixClient(
        "https://gix.example.test",
        "api-key-de-prueba",
        "secreto-de-prueba",
        transport=httpx.MockTransport(handler),
    )


# ---------- ventanas de fechas (puras) ----------


def test_ventanas_cubren_el_rango_sin_huecos_ni_solapes():
    desde, hasta = date(2026, 1, 1), date(2026, 1, 20)

    ventanas = list(date_windows(desde, hasta))

    assert ventanas[0][0] == desde
    assert ventanas[-1][1] == hasta
    for (_, fin), (inicio_sig, _) in zip(ventanas, ventanas[1:]):
        assert inicio_sig == fin + timedelta(days=1)
    for inicio, fin in ventanas:
        assert (fin - inicio).days <= 6  # 7 días corridos inclusive


def test_ventana_de_un_solo_dia():
    assert list(date_windows(date(2026, 1, 1), date(2026, 1, 1))) == [
        (date(2026, 1, 1), date(2026, 1, 1))
    ]


def test_ventanas_rechazan_rango_invertido():
    with pytest.raises(ValueError):
        list(date_windows(date(2026, 1, 2), date(2026, 1, 1)))


# ---------- cliente ----------


def test_login_guarda_el_token_y_lo_envia_en_las_consultas():
    vistos = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == LOGIN_PATH:
            vistos.append(
                (
                    "login",
                    request.method,
                    request.headers.get("api_key"),
                    request.headers.get("secret"),
                    request.content,
                )
            )
            return _login_ok(request)
        vistos.append(("datos", request.headers.get("Authorization")))
        return httpx.Response(200, json=_envelope([_item(1)]))

    with _cliente(handler) as cliente:
        items = list(cliente.precios_camara(21, date(2026, 1, 5), date(2026, 1, 5)))

    assert items == [_item(1)]
    # Según el Swagger: POST con api_key y secret como HEADERS (sin cuerpo).
    assert vistos[0] == (
        "login",
        "POST",
        "api-key-de-prueba",
        "secreto-de-prueba",
        b"",
    )
    assert vistos[1] == ("datos", TOKEN)


def test_respeta_el_prefijo_gix_de_la_url_base_real_de_pruebas():
    # URL real del ambiente de pruebas, vista en el Swagger de la BCR.
    rutas = []

    def handler(request: httpx.Request) -> httpx.Response:
        rutas.append((request.method, str(request.url).split("?")[0]))
        if request.url.path.endswith("/Login"):
            return _login_ok(request)
        return httpx.Response(200, json=_envelope([]))

    cliente = GixClient(
        "https://apiuat.bcr.com.ar/gix",
        "k",
        "s",
        transport=httpx.MockTransport(handler),
    )
    with cliente:
        list(cliente.precios_camara(21, date(2026, 1, 5), date(2026, 1, 5)))

    assert rutas == [
        ("POST", "https://apiuat.bcr.com.ar/gix/v1.0/Login"),
        ("GET", "https://apiuat.bcr.com.ar/gix/v1.0/PreciosCamara"),
    ]


def test_cotizacion_usa_get_con_page_y_recorre_las_paginas():
    consultas = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == LOGIN_PATH:
            return _login_ok(request)
        consultas.append((request.method, request.url.path, dict(request.url.params)))
        page = int(request.url.params["page"])
        return httpx.Response(
            200, json=_envelope([{"fila_de_prueba": page}], page, 2)
        )

    with _cliente(handler) as cliente:
        items = list(cliente.cotizacion())

    assert items == [{"fila_de_prueba": 1}, {"fila_de_prueba": 2}]
    assert consultas == [
        ("GET", "/v1.0/Cotizacion", {"page": "1"}),
        ("GET", "/v1.0/Cotizacion", {"page": "2"}),
    ]


def test_base_url_no_expone_credenciales():
    with _cliente(_login_ok) as cliente:
        assert cliente.base_url == "https://gix.example.test"


def test_recorre_todas_las_paginas_en_orden():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == LOGIN_PATH:
            return _login_ok(request)
        page = int(request.url.params["page"])
        paginas = {1: [_item(1), _item(2)], 2: [_item(3), _item(4)], 3: [_item(5)]}
        return httpx.Response(200, json=_envelope(paginas[page], page, 3))

    with _cliente(handler) as cliente:
        items = list(cliente.precios_camara(21, date(2026, 1, 5), date(2026, 1, 5)))

    assert [i["iD_Pizarra"] for i in items] == [1001, 1002, 1003, 1004, 1005]


def test_envia_los_parametros_documentados_y_parte_el_rango():
    consultas = []
    rutas = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == LOGIN_PATH:
            return _login_ok(request)
        rutas.append((request.method, request.url.path))
        consultas.append(dict(request.url.params))
        return httpx.Response(200, json=_envelope([]))

    with _cliente(handler) as cliente:
        list(cliente.precios_camara(21, date(2026, 1, 1), date(2026, 1, 15)))

    assert set(rutas) == {("GET", "/v1.0/PreciosCamara")}
    assert len(consultas) == 3  # 15 días -> 7 + 7 + 1
    assert all(c["idGrano"] == "21" for c in consultas)
    assert consultas[0]["fechaConcertacionDesde"] == "2026-01-01"
    assert consultas[0]["fechaConcertacionHasta"] == "2026-01-07"
    assert consultas[-1]["fechaConcertacionHasta"] == "2026-01-15"


def test_si_el_token_vence_renueva_y_reintenta_una_vez():
    estado = {"logins": 0, "datos": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == LOGIN_PATH:
            estado["logins"] += 1
            return _login_ok(request)
        estado["datos"] += 1
        if estado["datos"] == 1:
            return httpx.Response(401)
        return httpx.Response(200, json=_envelope([_item(1)]))

    with _cliente(handler) as cliente:
        items = list(cliente.precios_camara(21, date(2026, 1, 5), date(2026, 1, 5)))

    assert items == [_item(1)]
    assert estado == {"logins": 2, "datos": 2}


def test_si_el_token_sigue_rechazado_falla_sin_reintentar_en_bucle():
    estado = {"datos": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == LOGIN_PATH:
            return _login_ok(request)
        estado["datos"] += 1
        return httpx.Response(401)

    with _cliente(handler) as cliente:
        with pytest.raises(GixAuthError):
            list(cliente.precios_camara(21, date(2026, 1, 5), date(2026, 1, 5)))

    assert estado["datos"] == 2


def test_login_rechazado_levanta_error_de_autenticacion():
    with _cliente(lambda r: httpx.Response(401)) as cliente:
        with pytest.raises(GixAuthError):
            list(cliente.precios_camara(21, date(2026, 1, 5), date(2026, 1, 5)))


def test_login_sin_token_en_la_respuesta():
    with _cliente(lambda r: httpx.Response(200, json={"data": {}})) as cliente:
        with pytest.raises(GixAuthError):
            cliente.login()


def test_error_del_servidor_informa_el_codigo_sin_filtrar_el_cuerpo():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == LOGIN_PATH:
            return _login_ok(request)
        return httpx.Response(500, text="detalle interno con TOKEN-SECRETO")

    with _cliente(handler) as cliente:
        with pytest.raises(GixError) as info:
            list(cliente.precios_camara(21, date(2026, 1, 5), date(2026, 1, 5)))

    assert "500" in str(info.value)
    assert "TOKEN-SECRETO" not in str(info.value)


def test_status_de_error_dentro_del_cuerpo_tambien_falla():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == LOGIN_PATH:
            return _login_ok(request)
        cuerpo = _envelope([])
        cuerpo["status"] = {"code": 400, "message": "Bad request", "details": ""}
        return httpx.Response(200, json=cuerpo)

    with _cliente(handler) as cliente:
        with pytest.raises(GixError):
            list(cliente.precios_camara(21, date(2026, 1, 5), date(2026, 1, 5)))


def test_respuesta_sin_lista_de_datos_falla():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == LOGIN_PATH:
            return _login_ok(request)
        return httpx.Response(200, json={"status": {"code": 200}, "data": None})

    with _cliente(handler) as cliente:
        with pytest.raises(GixError):
            list(cliente.precios_camara(21, date(2026, 1, 5), date(2026, 1, 5)))


def test_repr_no_muestra_credenciales_ni_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return _login_ok(request)

    with _cliente(handler) as cliente:
        cliente.login()
        texto = repr(cliente)

    assert "api-key-de-prueba" not in texto
    assert "secreto-de-prueba" not in texto
    assert "token-de-prueba" not in texto


def test_from_settings_exige_la_configuracion_completa():
    settings = Settings(
        postgres_db="db", postgres_user="u", postgres_password="p"
    )
    settings.bcr_gix_base_url = None  # independiente de lo que haya en .env
    settings.bcr_gix_api_key = None
    settings.bcr_gix_secret = None

    with pytest.raises(GixError):
        GixClient.from_settings(settings)


def test_from_settings_con_configuracion_completa():
    settings = Settings(
        postgres_db="db",
        postgres_user="u",
        postgres_password="p",
        bcr_gix_base_url="https://gix.example.test",
        bcr_gix_api_key="k",
        bcr_gix_secret="s",
    )

    with GixClient.from_settings(settings) as cliente:
        assert "gix.example.test" in repr(cliente)
        assert "k" not in repr(cliente).replace("gix.example.test", "")


# ---------- integración con el importador (contra PostgreSQL, con rollback) ----------


def _handler_con_datos(request: httpx.Request) -> httpx.Response:
    if request.url.path == LOGIN_PATH:
        return _login_ok(request)
    return httpx.Response(200, json=_envelope([_item(1), _item(2)]))


def test_importa_pizarra_como_registros_originales(db_session):
    with _cliente(_handler_con_datos) as cliente:
        r = import_precios_camara(
            db_session, cliente, 21, date(2026, 1, 5), date(2026, 1, 5)
        )

    assert (r.rows_loaded, r.rows_duplicate, r.errors) == (2, 0, 0)
    guardados = db_session.scalars(
        select(RawRecord).where(RawRecord.batch_id == r.batch_id)
    ).all()
    # Se guarda exactamente lo que devolvió la API, sin transformar.
    assert sorted(g.payload["iD_Pizarra"] for g in guardados) == [1001, 1002]
    assert guardados[0].payload["precio_Cotizacion"] in (100001, 100002)
    lote = db_session.get(ImportBatch, r.batch_id)
    assert lote.parameters["endpoint"] == PRECIOS_CAMARA_PATH
    # El lote registra el ambiente, para no mezclar pruebas con producción.
    assert lote.parameters["base_url"] == "https://gix.example.test"
    assert lote.parameters["idGrano"] == 21


def test_reimportar_la_misma_pizarra_no_duplica(db_session):
    with _cliente(_handler_con_datos) as cliente:
        r1 = import_precios_camara(
            db_session, cliente, 21, date(2026, 1, 5), date(2026, 1, 5)
        )
        r2 = import_precios_camara(
            db_session, cliente, 21, date(2026, 1, 5), date(2026, 1, 5)
        )

    assert (r2.rows_loaded, r2.rows_duplicate) == (0, 2)

    def filas_del_lote(batch_id):
        return db_session.scalar(
            select(func.count())
            .select_from(RawRecord)
            .where(RawRecord.batch_id == batch_id)
        )

    assert filas_del_lote(r1.batch_id) == 2
    assert filas_del_lote(r2.batch_id) == 0


def test_si_la_api_falla_a_mitad_se_conserva_lo_importado(db_session):
    estado = {"datos": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == LOGIN_PATH:
            return _login_ok(request)
        estado["datos"] += 1
        if estado["datos"] == 1:
            return httpx.Response(200, json=_envelope([_item(1)]))
        return httpx.Response(500)

    with _cliente(handler) as cliente:
        with pytest.raises(GixError):
            import_precios_camara(
                db_session, cliente, 21, date(2026, 1, 1), date(2026, 1, 15)
            )

    lote = db_session.scalar(select(ImportBatch).order_by(ImportBatch.id.desc()))
    assert lote.status == "partial"
    assert lote.rows_loaded == 1
