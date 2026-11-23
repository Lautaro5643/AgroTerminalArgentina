# AgroTerminalArgentina

*De los datos a las decisiones.*

Plataforma web que centraliza la información y las herramientas que necesita
un trader o una mesa de dinero agro: futuros, precios, forwards, mercado
físico, noticias, fundamentales, análisis cuantitativo y seguimiento de
posiciones.

## Estado

Desarrollo inicial, **Sprint 01: Project Foundation & Data Architecture**.
Hoy el repo contiene solo infraestructura (PostgreSQL en Docker, estructura
de carpetas, dependencias). No hay código de producto ni datos de mercado.

Regla del proyecto: nunca se presentan datos simulados como reales.

## Requisitos

- Windows + PowerShell
- Python 3.12
- Docker Desktop
- Git

## Puesta en marcha

Todos los comandos se ejecutan desde la raíz del proyecto.

### 1. Entorno virtual

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
```

`python --version` debe mostrar 3.12.x.

### 2. Dependencias

```powershell
python -m pip install -r requirements.txt
```

### 3. Configuración

```powershell
Copy-Item .env.example .env
```

Editá `.env` y reemplazá `POSTGRES_PASSWORD` por una contraseña propia.
El archivo `.env` está ignorado por Git: nunca se sube al repositorio.

### 4. Base de datos (PostgreSQL)

Iniciar:

```powershell
docker compose up -d
docker compose ps
```

El contenedor debe figurar como `healthy`. PostgreSQL queda disponible en
`127.0.0.1:5433`.

Detener (conserva los datos):

```powershell
docker compose stop
```

> No uses `docker compose down -v` salvo que quieras borrar la base:
> la opción `-v` elimina el volumen con todos los datos.

## Flujo de trabajo con Git

- `main`: rama estable.
- `dev`: rama de trabajo. Los cambios se prueban acá y luego pasan a `main`.

## Estructura

```text
backend/app/    código de la aplicación (api, core, db, models)
backend/tests/  tests
data/raw/       datos originales (no se versionan)
data/processed/ datos procesados (no se versionan)
docs/           documentación y decisiones técnicas
```

## Próximos pasos del Sprint 01

FastAPI con endpoint `/health`, conexión SQLAlchemy a PostgreSQL, Alembic,
tests iniciales y registro de decisiones técnicas.
