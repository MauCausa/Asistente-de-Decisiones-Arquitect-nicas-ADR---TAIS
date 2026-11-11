# ADR-10: Adopción de una estrategia de Observabilidad Unificada en Kubernetes

## Estado
Aceptado

## Contexto
La plataforma actual consta de veinte microservicios ejecutados en Kubernetes y desarrollados en múltiples lenguajes de programación. Actualmente enfrentamos fallas intermitentes difíciles de rastrear debido a:
* **Heterogeneidad:** Cada equipo utiliza formatos de logs distintos.
* **Desconexión:** Las métricas no se correlacionan con las trazas distribuidas.
* **Tiempos de diagnóstico elevados:** El equipo de operaciones carece de una visión unificada extremo a extremo.
* **Restricciones presupuestarias:** No es financieramente viable almacenar el 100% de las trazas de manera indefinida.

## Decisión
Se decide implementar una **plataforma de observabilidad unificada basada en estándares abiertos (OpenTelemetry)** y un stack centralizado de backend, estructurado de la siguiente manera:

1. **Estandarización de Telemetría con OpenTelemetry (OTel):**
   * Se adoptará el SDK y las APIs de OpenTelemetry de forma obligatoria en todos los servicios, independientemente del lenguaje de programación.
   * Se estandarizará el formato de logs estructurados (JSON) y la inyección automática de contextos de traza (*traceparent*) en los encabezados HTTP/gRPC.

2. **Arquitectura de Recolección con OpenTelemetry Collector:**
   * Se desplegará un `OTel Collector` en modo *DaemonSet* por nodo para la recolección local y un despliegue en modo *Deployment* para el procesamiento y filtrado centralizado antes de enviar los datos al almacenamiento.

3. **Control de Costos y Volumen (Muestreo y Retención):**
   * **Trazas:** Se implementará **muestreo basado en cabecera (*Head-based sampling*)** en los clientes y **muestreo basado en cola (*Tail-based sampling*)** en el colector central. Esto último permitirá retener el 100% de las trazas que contengan errores o latencias anómalas, descartando un porcentaje configurable de las trazas exitosas y de rutina.
   * **Métricas y Logs:** Se establecerán políticas estrictas de retención en el almacenamiento (ej. 30 días para métricas, 7 días para logs de depuración y 14 días para logs de producción).

4. **Stack de Backend:**
   * **Métricas y Trazas:** Se utilizará **Grafana Tempo** para almacenamiento de trazas y **Prometheus / Thanos** para métricas, garantizando una correlación nativa mediante *exemplars*.
   * **Visualización:** **Grafana** será la única interfaz de usuario para dashboards, correlación de logs-métricas-trazas y exploración.

## Consecuencias

### Positivas
* **Diagnóstico rápido:** Operaciones tendrá visibilidad extremo a extremo de las peticiones que fluyen a través de los 20 servicios.
* **Correlación nativa:** Capacidad de saltar desde una métrica anómala a un log específico y a su traza distribuida correspondiente en un solo clic desde Grafana.
* **Independencia de lenguaje:** OpenTelemetry provee soporte maduro para todos los lenguajes utilizados en la organización.
* **Control de costos:** El muestreo inteligente (*tail-based sampling*) y las políticas de retención protegen el presupuesto al evitar el almacenamiento masivo de datos redundantes.

### Negativas / Desafíos
* **Esfuerzo de adopción:** Los equipos de desarrollo deberán refactorizar sus aplicaciones para integrar los SDKs de OpenTelemetry y adaptar el formato de sus logs.
* **Curva de aprendizaje:** Operaciones y desarrollo deben capacitarse en el uso avanzado de Grafana Tempo, Prometheus y los conceptos de OpenTelemetry.
* **Costo computacional:** El despliegue de los colectores de OTel y el procesamiento de *tail-based sampling* consumirán recursos adicionales (CPU/Memoria) en el clúster de Kubernetes.