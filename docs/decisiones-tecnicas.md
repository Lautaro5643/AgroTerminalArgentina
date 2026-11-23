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

## Reglas de datos vigentes (aplican a todo el desarrollo futuro)

1. Preservar los datos originales; la normalización no los reemplaza.
2. No mezclar settlement, último operado, bid y ask.
3. Sin conversiones implícitas de unidad o moneda; toda conversión se documenta.
4. Distinguir siempre datos reales, históricos, de prueba y simulados.
   Nunca presentar datos simulados como reales.
5. Verificar existencia, formato, acceso y licencia de cada fuente antes de
   integrarla.
