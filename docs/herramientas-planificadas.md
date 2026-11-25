# Herramientas planificadas: la lectura diaria de una mesa

Fecha: 2026-11-24. Origen: pedido del usuario. Este documento registra qué
quiere ver una mesa de granos y en qué estado está cada fuente. **No es una
promesa de que los datos existan**: cada fuente se verifica antes de usarse.

**Leyenda de estado:** **[Verificado]** se leyó documentación oficial en este
proyecto. **[Hipótesis]** es una fuente candidata que se conoce pero no se
verificó. **[Sin investigar]** todavía no se buscó. **[Existe, sin verificar]** (2026-11-24)
una búsqueda mostró que la publicación existe, pero no se leyó su contenido, formato
ni condiciones de uso.

## Idea central

Una mesa mira cada dato **contra su historia de esta fecha**. Eso se traduce en
tres piezas reutilizables, independientes de las fuentes. Cada fuente que se
conecte después alimenta estas piezas.

1. **Comparador estacional.** Para cualquier serie, compara el valor actual con
   el de la misma fecha en campañas o años anteriores: percentil, promedio,
   mínimo y máximo de las anteriores, y desvío.
2. **Relaciones.** Calcula primero la relación y la compara después: soja sobre
   maíz, un mes contra otro, físico contra futuro, Rosario contra Brasil.
3. **Calculadora de pase y guardado.** Lee el pase contra el costo de guardar
   (embolsar, financiar con warrant, costos fijos) y devuelve el neto.

Reglas que se mantienen: unidades explícitas en todo cálculo, nada se
interpola en silencio (un dato faltante se ve como faltante), y cada valor
conserva su fuente y su fecha.

## Bloques de la mesa

| Bloque | Qué mira | Fuente candidata | Estado |
|---|---|---|---|
| Físico | Pizarra de Rosario | API GIX de la BCR | [Verificado] estructura; falta acceso |
| Físico | FOB | Publicaciones oficiales de Agricultura (MAGyP) | [Existe, sin verificar] la serie; no se pudo abrir la página |
| Físico | Lo que pagan exportación e industria | Sin identificar | [Sin investigar] |
| Físico | Crush (margen de molienda) | Soja, aceite y harina | Aceite de soja en A3 [Verificado]; harina [Sin investigar] |
| Físico | Rosario contra Brasil | Precios de Brasil | [Sin investigar] |
| Comercialización | Compras por campaña contra el año anterior | Informe de compras de SIOGRANOS (PDF) | [Existe, sin verificar] PDF con porcentajes campaña contra campaña; sin precios por tonelada ni datos estructurados |
| Puerto y río | Camiones, buques a la carga, Paraná contra aguas bajas | Notas de la BCR sobre camiones; planillas mensuales .xls de alturas del río (IDESF) | [Existe, sin verificar] río: .xls mensual 2009 a ene-2024, sin API, productor y estaciones sin nombrar; camiones y buques sin fuente estructurada |
| Mundo | Fondos en Chicago | Reporte COT de la CFTC | [Existe, sin verificar] API y descargas CSV/XML; falta confirmar categoría de fondos (managed money), año de inicio y condiciones |
| Mundo | Ventas de EE.UU. | USDA FAS, dataset ESR | [Verificado] existe; falta API key |
| Mundo | Stock sobre uso y cosechas de afuera | USDA FAS, dataset PSD | [Verificado] existe; falta API key |
| Cosecha y clima | Avance de siembra en Argentina | Estimaciones semanales en PDF (MAGyP) | [Existe, sin verificar] solo PDF; sin datos estructurados confirmados |
| Cosecha y clima | Avance de siembra en EE.UU. | USDA NASS | [Hipótesis] sin verificar en esta pasada |
| Insumos | Toneladas de grano por urea, fosfato, potasio y gasoil | Monitores insumo-producto (publicaciones) | [Existe, sin verificar] sin datos ni precios confirmados |
| Futuros | Curvas, spreads, WTI y oro | A3 vía pyRofex | Contratos [Verificado]; falta cuenta |

## Requisito crítico: profundidad histórica

Comparar contra "esta fecha de años anteriores" exige **varios años de historia
de cada serie**. Una fuente que solo entrega el dato actual no sirve para esto.
Al evaluar cada fuente hay que confirmar desde qué fecha hay datos y cuánto
cuesta cargarlos. Ejemplo conocido: la API GIX limita cada consulta a 7 días y
10 registros por página, por lo que cargar años de pizarra son muchas llamadas.

## Definiciones que hay que confirmar con el usuario

- **Campaña:** cuándo empieza y termina para cada cultivo. No se asume.
- **"Esta fecha":** misma fecha calendario o mismo día de campaña. Hay que
  decidir el tratamiento de años bisiestos y de series semanales.

## Calculadora de pase contra costo de embolsar

El pase se lee contra el costo de guardar. El usuario carga su costo como % anual
y la herramienta devuelve el neto. Las fórmulas, con todas las convenciones
como parámetros y no escondidas:

- `pase` = precio del vencimiento lejano − precio del cercano. Mismo producto,
  misma unidad y **mismo tipo de precio** (ajuste con ajuste).
- `pase %` = pase ÷ precio cercano.
- `días` = días entre los dos vencimientos.
- `pase anualizado` = pase % × 365 ÷ días (simple, base 365; configurable).
- `neto anual` = pase anualizado − costo de embolsar (% anual, dato del usuario).
- `neto en USD/t` = pase − costo × precio cercano × días ÷ 365.

Se puede sumar en el mismo cálculo el costo financiero de un warrant (tasa, días
y costos fijos que carga el usuario). El material oficial leído **no informa
porcentaje financiado, tasa, comisiones ni plazos típicos**, así que no hay
valores por defecto. Si hay monedas distintas, el tipo de cambio es un dato
explícito. La herramienta muestra números; no recomienda operar.

## Acopios

Pedido: precio y cantidad, costos y una calculadora. **No se identificó ninguna
fuente de datos de acopios.** Hasta entonces el diseño parte de carga manual,
guardando para cada dato su origen y su fecha. Pregunta abierta: qué datos de
acopios se consultan hoy y de dónde salen.

## Orden propuesto

1. Comparador estacional y relaciones (no dependen de fuentes externas; se
   prueban con datos de prueba marcados como tales).
2. Calculadora de pase y guardado.
3. Libro de posiciones.
4. Conectar fuentes a medida que lleguen los accesos, empezando por las ya
   verificadas, y verificar las no investigadas una por una.
