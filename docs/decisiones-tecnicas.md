# Registro de decisiones técnicas

Cada decisión indica qué se eligió, por qué y qué consecuencias tiene.
Fecha de inicio del registro: 2026-11-22 (Sprint 01).

## D-001. Backend: una sola aplicación FastAPI modular

- **Decisión:** una única aplicación FastAPI, organizada por módulos de
  dominio. Sin microservicios.
- **Motivo:** menor complejidad operativa mientras el producto se define.
  Se puede separar más adelante si hay una razón concreta.
- **Consecuencia:** las carpetas de módulos (`market_watch`, etc.) se crean
  cuando exista funcionalidad que las necesite, no antes.

## D-002. Base de datos: PostgreSQL 17 en Docker, puerto local 5433

- **Decisión:** PostgreSQL 17 (`postgres:17-alpine`) con volumen persistente,
  expuesto solo en `127.0.0.1:5433`.
- **Motivo:** puerto 5433 para evitar conflicto con una posible instalación
  local en 5432. Escuchar solo en localhost evita exponer la base a la red.
- **Consecuencia:** `docker compose down -v` borra los datos; no usarlo de
  forma rutinaria.

## D-003. Python 3.12 y dependencias fijadas

- **Decisión:** Python 3.12 dentro de `.venv`. Versiones exactas en
  `requirements.txt` (verificadas con `pip check`).
- **Motivo:** reproducibilidad. Solo se instala lo necesario para la
  infraestructura; pandas, numpy y librerías cuantitativas se agregan cuando
  una funcionalidad las requiera.
- **Pendiente:** el TestClient de Starlette muestra una advertencia de
  deprecación sobre `httpx` (sugiere `httpx2`). No afecta el funcionamiento;
  revisar al actualizar dependencias.

## D-004. Configuración por variables de entorno (`.env`)

- **Decisión:** la configuración se lee con `pydantic-settings` desde `.env`.
  `.env` está ignorado por Git; `.env.example` es la plantilla versionada.
- **Motivo:** no guardar credenciales en el código ni en el repositorio.
- **Consecuencia:** la URL de la base se arma con `URL.create`, de modo que
  caracteres especiales en la contraseña no rompen la conexión.

## D-005. Conexión a la base creada de forma perezosa

- **Decisión:** el engine y las sesiones de SQLAlchemy se crean la primera vez
  que se usan, no al importar el módulo.
- **Motivo:** los tests y herramientas que no usan la base no requieren `.env`.

## D-006. Migraciones con Alembic, sin URL en `alembic.ini`

- **Decisión:** Alembic administra el esquema. `env.py` obtiene la URL desde
  la configuración de la aplicación; `alembic.ini` no contiene credenciales.
- **Consecuencia:** los modelos nuevos deben importarse en `env.py` para que
  la autogeneración de migraciones los detecte.

## D-007. Dos endpoints de salud separados

- **Decisión:** `/health` confirma que la aplicación responde (sin tocar la
  base). `/health/db` confirma la conexión a PostgreSQL y responde 503 si
  falla, sin exponer el detalle del error.

## D-008. Flujo de ramas

- **Decisión:** el trabajo se integra en `dev`; `main` se mantiene estable.
- **Consecuencia:** los cambios pasan de `dev` a `main` cuando están
  verificados en el entorno local.

## D-009. Esquema de ingesta independiente de la fuente

- **Decisión:** tablas `data_source`, `import_batch`, `raw_record` e
  `import_error`. El registro original se guarda como JSONB sin modificar,
  con su hash SHA-256; la unicidad `(source_id, payload_hash)` evita
  duplicados. Los lotes registran parámetros, versión de normalización y
  contadores.
- **Motivo:** trazabilidad y preservación de originales (reglas de datos).
- **Pendiente deliberado:** las tablas de precios normalizados (pizarra,
  tipo de cambio, futuros) no se crean hasta ver una respuesta real de cada
  fuente. Supuestos a verificar entonces: unidad y moneda de cada precio,
  significado del indicador "estimado" de la BCR.
- **Verificación:** la migración se aplicó, revirtió y reaplicó sobre un
  PostgreSQL real de prueba; se comprobó que la base rechaza duplicados,
  estados inválidos y claves foráneas inexistentes.

## D-010. Importador genérico y tests con rollback

- **Decisión:** `app/ingestion/importer.py` expone `run_import(session,
  source_code, records)`. Guarda cada registro original en `raw_record`
  (JSONB sin modificar), deduplica por `(fuente, hash)` con
  `INSERT ... ON CONFLICT DO NOTHING`, registra registros inválidos en
  `import_error` y cierra el lote con estado `succeeded`, `partial` o
  `failed`.
- **Límite de responsabilidad:** no conoce ninguna fuente. Cada proveedor
  necesita un adaptador propio (conexión, paginación, partir la respuesta en
  registros) y un paso posterior de normalización a tablas de precios.
- **Errores de la fuente:** si la fuente falla a mitad de camino se conserva
  lo cargado, el lote queda `partial`/`failed` y la excepción se vuelve a
  lanzar. En el registro de errores se guarda solo el tipo de excepción, no
  su mensaje (podría contener URLs o credenciales).
- **Errores de base de datos:** se propagan; el lote queda en `running`
  (importación interrumpida).
- **Tests:** los que usan PostgreSQL corren dentro de una transacción que se
  deshace, por lo que no dejan datos; se saltean solos si la base no está
  disponible o faltan migraciones. Usan datos de prueba inventados.

## D-011. Cliente de la API GIX (BCR) con supuestos aislados

- **Decisión:** `app/ingestion/bcr_gix.py` usa `httpx`. Hace login, reutiliza
  el token, renueva una vez ante HTTP 401, parte los rangos en ventanas de 7
  días corridos, recorre todas las páginas y entrega los items de `data` sin
  modificar a `run_import`.
- **Verificado contra el Swagger de la BCR:** login por `POST /v1.0/Login`
  con `api_key` y `secret` en headers (un primer supuesto de cuerpo JSON
  resultó incorrecto y se corrigió) y `GET /v1.0/PreciosCamara`.
- **También verificado en el Swagger:** header `Authorization`,
  `GET /v1.0/Cotizacion` y URL base de pruebas
  `https://apiuat.bcr.com.ar/gix` (el prefijo `/gix` tiene test propio).
- **Todavía sin confirmar:** formato de fecha (se envía `YYYY-MM-DD`), URL
  base productiva y si los datos de UAT son reales. Cada lote guarda la
  `base_url` en `import_batch.parameters` para distinguir pruebas de
  producción y no mezclarlas.
- **Credenciales:** `BCR_GIX_BASE_URL`, `BCR_GIX_API_KEY` y `BCR_GIX_SECRET`
  en `.env` (opcionales). Se leen como `SecretStr`; el cliente no las muestra
  en `repr` ni en mensajes de error, y los errores informan solo el código
  HTTP, nunca el cuerpo.
- **Tests:** con respuestas simuladas (`httpx.MockTransport`) y valores
  inventados. Prueban el comportamiento del cliente, **no** que la API real
  responda así.
- **Tests de base de datos rápidos:** la conexión se prueba una sola vez con
  un tiempo máximo de 3 segundos; si falla, todos los tests de base se
  saltean. (Antes cada test reintentaba y la suite llegó a tardar 21 min con
  la base caída.)

## D-012. Maestro de instrumentos, unidades y vencimientos estimados

- **Decisión:** `app/instruments/` con tres módulos. `units.py` hace todas las
  conversiones con `Decimal` (rechaza `float`, `bool` y texto) y precios con
  unidad explícita (`Price`), de modo que convertir un precio en la unidad
  equivocada falla con `UnitMismatchError`. `contracts.py` describe cada
  contrato (CBOT ZS y tres de A3) citando su fuente y declarando lo no
  confirmado (`None` o `caveats`). `expiry.py` aplica las reglas de vencimiento.
- **Motivo:** el error más caro y menos visible es mezclar toneladas con
  bushels o dólares con centavos; un contrato CBOT (≈136 t) tampoco es
  comparable uno a uno con uno de A3 (100, 10 o 5 t).
- **Vencimientos:** son **estimaciones**, no fechas oficiales. No se incluyen
  feriados porque no se verificó ningún calendario oficial; el llamador los
  pasa. La regla de Soja Chicago se cita pero no se calcula.
- **Pendiente:** pesos por bushel confirmados en una sola fuente secundaria
  (falta el manual USDA AH-697); vigencia y meses listados de A3.
  Detalle y fuentes en `docs/especificaciones-contratos.md`.
- **Alcance:** solo soja. Sin rondeo implícito: quien llama decide los
  decimales.

## Reglas de datos vigentes (aplican a todo el desarrollo futuro)

1. Preservar los datos originales; la normalización no los reemplaza.
2. No mezclar settlement, último operado, bid y ask.
3. Sin conversiones implícitas de unidad o moneda; toda conversión se documenta.
4. Distinguir siempre datos reales, históricos, de prueba y simulados.
   Nunca presentar datos simulados como reales.
5. Verificar existencia, formato, acceso y licencia de cada fuente antes de
   integrarla.
