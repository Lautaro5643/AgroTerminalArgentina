# Especificaciones de contratos de soja

Consultado el 2026-11-23 en documentación pública. Es la base de
`backend/app/instruments/`. Ningún valor se cargó de memoria: cada uno viene
de la fuente indicada.

**Leyenda:** **[Confirmado]** figura en la fuente y, cuando se indica, en una
segunda. **[Una sola fuente]** figura en una sola fuente secundaria.
**[No confirmado]** no figura o no se pudo abrir la fuente.

## 1. CBOT / CME: Soybean futures (ZS)

| Dato | Valor | Estado |
|---|---|---|
| Tamaño | 5.000 bushels (≈136 t métricas según CME) | [Confirmado] CME y MarketsWiki |
| Cotización | Centavos de dólar por bushel | [Confirmado] |
| Fluctuación mínima | 1/4 de centavo por bushel (US$12,50 por contrato) | [Confirmado] |
| Meses | Ene (F), Mar (H), May (K), Jul (N), Ago (Q), Sep (U), Nov (X) | [Confirmado] |
| Último día de negociación | "El día hábil anterior al día 15 calendario del mes del contrato" | [Confirmado] CME y MarketsWiki |
| Liquidación | Entrega física | [Confirmado] (CME) |
| Código | ZS (Globex) | [Confirmado] |

Fuentes: `https://www.cmegroup.com/cn-t/markets/agriculture/oilseeds/soybean.contractSpecs.html`
(versión en chino de la página de CME) y
`https://www.marketswiki.com/wiki/Soybean_futures`. La página en inglés de CME
no devolvió las especificaciones al consultarla.

## 2. A3 Mercados (Matba Rofex): soja

Fuente: guía de negociación de productos agro de A3
(`https://matbarofex.com.ar/documentos/investigacion/guia-de-negociacion-productos-agro`)
y reglamento del contrato Soja Índice Mini
(`https://matbarofex.com.ar/documentos/legales/reglamento-soja-mini`).

| Contrato | Tamaño | Cotización | Liquidación | Último día de negociación |
|---|---|---|---|---|
| Soja en dólares | 100 t | USD/t | Entrega física | "La última rueda previa a las últimas cinco (5) ruedas del mes pactado para la entrega" |
| Soja Índice Mini | 10 t | USD/t | Diferencias en efectivo | "El último día hábil del mes anterior al mes del contrato" |
| Soja Chicago | 5 t | USD/t | Diferencias en efectivo | El día del vencimiento de las opciones sobre futuros de soja CBOT |

Detalles del Mini [Confirmado en el reglamento]: liquida contra "el precio de
ajuste del futuro de Soja en Dólares con entrega para el mismo mes"; cobros y
pagos en pesos al tipo de cambio de referencia del Mercado.

**Trampa de unidades:** un contrato CBOT equivale a ≈136 t; uno de A3 son 100,
10 o 5 t. Un contrato de A3 no es comparable "uno a uno" con uno de CBOT, y los
precios están en unidades distintas (centavos por bushel vs. USD por tonelada).
Por eso toda conversión pasa por `app/instruments/units.py`.

### Lo que NO está confirmado de A3

- **Vigencia.** La guía usa ejemplos de 2021-2022 (por ejemplo `SOJ.ROS/MAY22`).
  Confirmar con las circulares de A3 que las especificaciones siguen vigentes.
- **Meses listados.** La guía dice "todos los meses"; los efectivamente listados
  pueden ser menos.
- **Fluctuación mínima.** El reglamento del Mini dice que "será informada
  mediante Circular": no figura.
- **Precio de referencia de Soja Chicago.** No se verificó.
- **Formato exacto de los tickers.** Los ejemplos (`SOJ.ROS/MAY22`,
  `SOJ.MIN/MAY22`, `SOY.CME/ABR22`) permiten deducir un patrón, pero la guía no
  lo define. Por eso el código no genera tickers.
- **Contratos en pesos (30 t), maíz y trigo, girasol, sorgo, cebada, aceite:**
  no modelados todavía.

## 3. Conversiones de unidades

| Grano | Libras por bushel | Bushels por tonelada | Estado |
|---|---|---|---|
| Soja | 60 | 36,7437 | [Una sola fuente] |
| Trigo | 60 | 36,7437 | [Una sola fuente] |
| Maíz | 56 | 39,368 | [Una sola fuente] |

Fuente: tabla del U.S. Grains Council (`https://grains.org/?p=429`), que no cita
fuente primaria.

- **Verificación cruzada que sí se hizo:** con 1 libra = 0,45359237 kg (exacto
  por definición internacional), 60 lb/bushel reproduce 36,7437 bushels/t y
  56 lb/bushel reproduce 39,368. Además, CME informa que 5.000 bushels de soja
  son "aprox. 136 toneladas", coherente con 60 lb/bushel.
- **Lo que no se pudo hacer:** confirmar los pesos por bushel contra el manual
  del USDA (AH-697, *Weights, Measures, and Conversion Factors for Agricultural
  Commodities*). La página consultada no incluía el PDF.

## 4. Vencimientos: son estimaciones

`app/instruments/expiry.py` aplica las reglas de la sección 1 y 2 sobre un
calendario de días hábiles, pero **no incluye feriados** porque no se verificó
ningún calendario oficial. Solo conoce sábados y domingos; el llamador pasa los
feriados del mercado correspondiente. El resultado es una estimación basada en
la regla, no la fecha oficial, que publican A3 y CME. La regla de Soja Chicago
no se calcula.
