# Protocolo experimental del Hito 2

## Diseno

El experimento aplica un diseno pareado. Cada uno de los 12 escenarios se procesa con los dos tratamientos, lo que produce 24 ADR. La unidad experimental es el escenario arquitectonico.

- T1: prompt zero shot directo, sin recuperacion de contexto ni secuencia guiada.
- T2: secuencia estructurada de prompts con recuperacion RAG y salida MADR.

## Controles obligatorios

- Mismo identificador y version del modelo en T1 y T2.
- Temperatura 0.2 en ambos tratamientos.
- Mismo limite maximo de tokens.
- Mismo escenario de entrada y mismo orden de ejecucion registrado.
- Prompts congelados antes de iniciar las corridas.
- Corpus RAG congelado y versionado para todas las corridas T2.
- Registro de fecha, hora, latencia, estado y errores de cada ejecucion.

## Metricas

- CE = secciones MADR completas y no vacias / 7 x 100.
- SS = similitud coseno entre el ADR generado y el ADR de referencia usando all MiniLM L6 v2.
- CRA = promedio de los seis criterios de la rubrica, cada uno entre 1 y 5.
- TG = segundos transcurridos desde el envio hasta la recepcion completa del ADR.
- Metricas secundarias: numero de alternativas y numero de trade offs explicitos.

## Hipotesis

- H0: T2 no mejora la completitud estructural, la similitud semantica ni la calidad del rationale respecto de T1.
- H1: T2 mejora la completitud estructural, la similitud semantica y la calidad del rationale respecto de T1.

La latencia se analiza como costo del tratamiento y no como evidencia automatica de superioridad. Las comparaciones se realizan por escenario con una prueba de Wilcoxon pareada. No se redactan conclusiones hasta ejecutar las corridas reales.

## Evaluacion sin sesgo

Los ADR deben entregarse al evaluador con codigos anonimos que no revelen el tratamiento. Se recomienda que dos integrantes califiquen la rubrica de forma independiente y resuelvan sus diferencias antes del analisis final.

