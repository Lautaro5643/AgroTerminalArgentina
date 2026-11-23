# Fuentes de datos: diagnóstico inicial

Fecha: 2026-11-22. Investigación por búsqueda web y lectura de documentación
pública. **No se hizo ninguna llamada real a las APIs ni se creó ninguna
cuenta.** Todo lo marcado como "no confirmado" debe verificarse antes de
construir sobre eso.

Leyenda: **[Leído]** figura en documentación consultada. **[No confirmado]**
no se encontró evidencia o hay contradicciones.

## Resumen

| Fuente | Qué da | Acceso | Estado |
|---|---|---|---|
| BCR - API GIX | Pizarra (precios de cámara) y cotización BNA | Formulario + api_key/secret | La más concreta para empezar |
| A3 / Matba Rofex - API Índices MtR | Índices (I.SOJA, I.MAIZ, I.TRIGO, etc.), REST y WebSocket | Gratuita, privada, permiso por email | Sirve para índices, **no** para futuros por contrato |
| A3 / Matba Rofex - futuros por contrato (settlements históricos) | Necesario para curvas y spreads | **[No confirmado]** | Pendiente: hay que confirmar con A3 |
| Primary / pyRofex | Precios, puntas y trades históricos de instrumentos | Cuenta REMARKET (demo gratis) o LIVE (contactar a MPI) | Útil para vivo; histórico de ajustes no confirmado |
| USDA FAS - PSD / OpenData | Balances oferta y demanda mundiales | API key gratuita | Buena para fundamentales |
| USDA NASS - Quick Stats | Estadísticas agrícolas de EE.UU. | Pública | Es solo EE.UU., no Argentina |
| CBOT / CME | Futuros de referencia | **[No confirmado]** | Probablemente de pago; requiere decisión y autorización tuya |

## 1. Bolsa de Comercio de Rosario - API GIX

- **Qué es [Leído]:** API con precios de cámara (pizarra) de trigo, maíz,
  sorgo, girasol y soja, y cotizaciones de divisas y billetes del BNA.
- **Acceso [Leído]:** se solicita por formulario (api.bcr.com.ar/form). Con
  `api_key` y `secret` se genera un Bearer Token en `/Login`; el token vale
  24 horas. Hay ambiente de prueba (UAT) y productivo. Los permisos se
  otorgan por consulta.
- **Endpoints [Leído]:**
  - `/PreciosCamara`: parámetros `idGrano` (Trigo 1, Maíz 2, Sorgo 3,
    Girasol 20, Soja 21), `fechaConcertacionDesde` y `fechaConcertacionHasta`.
  - `/Cotizacion`: tipos de cambio del BNA.
- **Límites [Leído]:** el rango de fechas no puede superar 7 días; la
  paginación es de 10 registros por página.
- **Formato [Leído]:** JSON con bloques `status`, `metadata` y `data`.
- **Costo y condiciones de uso [No confirmado]:** el manual no los menciona.
  Consultar a la BCR (protocolo: protocologix@bcr.com).
- **Implicancia:** cargar historia es posible pero lento (ventanas de 7 días,
  10 por página). El importador debe manejar paginación, expiración del token
  y reintentos.

## 2. A3 Mercados / Matba Rofex

A3 Mercados es la entidad que integra a Matba Rofex.

### 2.1 API Índices MtR
- **Qué es [Leído]:** índices de Matba Rofex (I.SOJA, I.MAIZ, I.TRIGO,
  I.AGTKSOYA, I.AGTKCORA, I.AGTKWHEA, I.DOLAREXPO, I.CCL, I.RFX20, entre
  otros). REST (histórico y actual) y WebSocket (tiempo real).
- **Acceso [Leído]:** "privada y sin costo". Hay que registrar usuario y
  contraseña y pedir permisos por email a investigacion@matbarofex.com.ar.
  Token vía `POST https://api.matbarofex.com.ar/v2/token/` (access 24 h,
  refresh 7 días). Límite: 10 requests por segundo por IP.
- **Limitación importante [Leído]:** el documento no describe datos de
  futuros por contrato ni de settlement. Son series de índices.
- **Condiciones de uso [No confirmado]:** no hay licencia formal en el
  documento; remite a un manual de buenas prácticas.

### 2.2 Futuros por contrato y settlements históricos
- **[No confirmado].** La búsqueda no encontró una descarga pública de precios
  de ajuste históricos por contrato. Es el dato que necesitan las curvas y los
  calendar spreads, así que es la pregunta más importante para hacerle a A3.
- Pedir por escrito: qué productos de datos históricos existen, formato,
  costo y licencia (incluida la redistribución a terceros).

### 2.3 Primary / pyRofex
- **Qué es [Leído]:** librería Python (licencia MIT) para las APIs REST y
  WebSocket de ROFEX. Datos de mercado (último precio, puntas), historial de
  operaciones entre dos fechas, listado de instrumentos.
- **Acceso [Leído]:** REMARKET (demo) con cuenta gratuita; LIVE contactando a
  mpi@primary.com.ar. Para operar en producción se necesitan credenciales de
  un agente.
- **Advertencia [Leído]:** las cuentas REMARKET son un ambiente demo; sus
  datos no deben tratarse como mercado real.
- **Alcance del proyecto:** esta terminal no envía órdenes. Solo lectura.

## 3. USDA

### 3.1 FAS - PSD y OpenData
- **Qué es [Leído]:** producción, oferta y distribución de commodities
  agrícolas mundiales (incluye Argentina). Licencia declarada CC BY 4.0
  (según catálogo de data.gov).
- **Acceso [Leído en catálogo de terceros]:** base
  `https://apps.fas.usda.gov/OpenData`, JSON, header `API_KEY`, registro
  gratuito de autoservicio. Los endpoints exactos están en el Swagger oficial
  (no consultado).
- **Contradicción [No confirmado]:** una página dice `apiKey` y otra
  "bearer token". Verificar en el Swagger.
- **Límites de uso [No confirmado].**

### 3.2 NASS - Quick Stats
- **Qué es [Leído]:** estadísticas agrícolas de **EE.UU.** (superficie,
  producción). No cubre Argentina. Licencia CC0 en el catálogo.
- **API key y límites [No confirmado]** en lo consultado.

## 4. CBOT / CME
- **[No confirmado]** en esta investigación. Hallazgo previo (documento viejo
  del proyecto, no reverificado): los precios históricos por contrato serían
  de pago vía CME DataMine. Comprar datos requiere tu autorización explícita.

## Preguntas abiertas para resolver (de menor a mayor esfuerzo)

1. Pedir acceso a API GIX (formulario BCR) y preguntar costo y condiciones.
2. Pedir permisos de API Índices MtR a investigacion@matbarofex.com.ar.
3. Registrarse para la API key gratuita de USDA FAS.
4. Consultar a A3 por settlements históricos por contrato (formato, costo,
   licencia, redistribución).
5. Decidir la fuente de CBOT/CME y presupuesto, si lo hubiera.
6. Consultar licencias de redistribución: si la terminal se ofrece como
   servicio a terceros, los términos de cada proveedor pueden cambiar lo que
   está permitido. Conviene consultarlo con un abogado antes de comercializar.
