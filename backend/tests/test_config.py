from app.core.config import Settings


def test_database_url_usa_los_valores_configurados():
    settings = Settings(
        postgres_db="db_prueba",
        postgres_user="usuario_prueba",
        postgres_password="clave_de_prueba",
        postgres_host="127.0.0.1",
        postgres_port=5433,
    )

    url = settings.database_url

    assert url.drivername == "postgresql+psycopg"
    assert url.host == "127.0.0.1"
    assert url.port == 5433
    assert url.database == "db_prueba"
    assert url.username == "usuario_prueba"


def test_database_url_soporta_caracteres_especiales_en_la_clave():
    settings = Settings(
        postgres_db="db",
        postgres_user="user",
        postgres_password="p@ss:w/ord#1",
        postgres_host="127.0.0.1",
    )

    url = settings.database_url

    # La clave se conserva intacta y no rompe el resto de la URL.
    assert url.password == "p@ss:w/ord#1"
    assert url.host == "127.0.0.1"
    assert "p@ss:w/ord#1" not in url.render_as_string(hide_password=True)
