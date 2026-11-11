# CASO_10 - Observabilidad unificada en una plataforma Kubernetes

## Estado
Aceptado

## Contexto y Problema
La organización opera una plataforma distribuida en Kubernetes compuesta por 20 microservicios desarrollados en múltiples lenguajes de programación. Actualmente, el sistema registra fallas intermitentes en producción que no pueden ser rastreadas ni correlacionadas a través de las fronteras de los servicios. 

Cada equipo de desarrollo ha implementado su propio formato de registro de eventos (logs), y las métricas de infraestructura/aplicación existentes se encuentran totalmente disociadas de las trazas de ejecución. Esta fragmentación impide a las operaciones calcular la causa raíz de las anomalías, incrementando inaceptablemente el Tiempo Medio de Resolución (MTTR). 

El problema central radica en la imposibilidad de obtener visibilidad de extremo a extremo sin exceder las severas restricciones presupuestarias impuestas sobre la retención de datos de telemetría y el almacenamiento en disco, dentro de un entorno informático heterogéneo (políglota) ejecutándose en Kubernetes.

## Drivers de Decisión (ASRs)
*   **ASR-1: Observabilidad extremo a extremo:** Capacidad de rastrear solicitudes a través de los 20 microservicios políglotas en Kubernetes de forma unificada, enlazando métricas, logs y trazas distribuidas.
*   **ASR-2: Diagnóstico rápido:** Reducción del MTTR mediante la correlación contextual bidireccional directa entre métricas anómalas, logs de error y trazas distribuidas.
*   **ASR-3: Control de costos de telemetría:** Restricción estricta del volumen de almacenamiento e ingesta de datos, prohibiendo la persistencia incondicional del 100% de la telemetría generada.
*   **R-1: Entorno Políglota en Kubernetes:** Operación sobre 20 servicios desarrollados en múltiples lenguajes (ej. Java, Go, Python, Node.js), lo que descarta soluciones propietarias o librerías heterogéneas por lenguaje que incrementen la deuda técnica.
*   **R-2: Retención Completa Limitada por Presupuesto:** Imposibilidad financiera de almacenar el volumen total de trazas generadas por el tráfico normal de producción.
*   **R-3: Heterogeneidad Actual de Formatos:** Logs incoherentes y no estructurados entre equipos de desarrollo que impiden la agregación directa sin un proceso de estandarización.

## Opciones Consideradas

### Opción 1: Observabilidad basada en Infraestructura/Service Mesh (Istio / Envoy Proxy + Fluentbit + Jaeger)
- **Descripción:** Inserción de sidecars Envoy en cada pod mediante Istio Service Mesh para capturar tráfico de red L7, generar trazas automáticamente y recolectar logs de *stdout* a través de Fluentbit como DaemonSet, aplicando un muestreo de ingesta basado en origen (*Head-Based Sampling*) a un porcentaje fijo (ej. 5%).
- **Ventajas:** 
  - Cero modificación de código fuente para la generación de trazas de red (cumple R-1 sin acoplamiento a nivel de aplicación).
  - Proporciona instantáneamente un mapa de topología de red y métricas de latencia/error entre servicios.
- **Desventajas:** 
  - Invisibilidad de los procesos internos de la aplicación (excepciones no capturadas, consultas a bases de datos, lógica de negocio).
  - Elevada sobrecarga de recursos de infraestructura en el clúster (CPU y RAM consumidos por 20+ sidecars Envoy).
  - Alta complejidad operativa de mantenimiento de la plano de control del Mesh.
- **Riesgos:** 
  - El muestreo *Head-Based* descarta aleatoriamente datos en la entrada; si ocurre una falla en el tráfico no muestreado, se pierde la traza necesaria para el diagnóstico (violación de ASR-2 y ASR-3).

### Opción 2: Pipeline Unificado con SDKs de OpenTelemetry + Tail-Based Sampling en OTel Collector Central
- **Descripción:** Implementación del estándar abierto OpenTelemetry mediante SDKs/Agentes en los 20 microservicios para inyectar `trace_id` y `span_id` en logs JSON unificados y emitir trazas via OTLP/gRPC. La recolección se realiza mediante un agente local (*OTel Collector DaemonSet*) y un clúster central (*OTel Collector Deployment*) que ejecuta filtrado posterior en memoria (*Tail-Based Sampling*).
- **Ventajas:** 
  - Cumplimiento total de ASR-1 y ASR-2 mediante correlación contextual nativa a nivel de código, red y runtime.
  - Optimización extrema de costos (ASR-3 y R-2) al retener el 100% de los errores y latencias críticas, filtrando el tráfico sano redundante.
  - Independencia de proveedores (*vendor-neutral*) respetando el carácter políglota (R-1).
- **Desventajas:** 
  - Requiere un esfuerzo inicial de refactorización por parte de los equipos de desarrollo para adoptar el formato de logging estructurado JSON y configurar SDKs.
  - Consumo de memoria RAM en el clúster central de recolectores para sostener el búfer de trazas en evaluación.
- **Riesgos:** 
  - Riesgo de desbordamiento de memoria (OOM) en los colectores centrales ante picos masivos e imprevistos de errores en producción si no se configuran salvaguardas.

### Opción 3: Observabilidad por Kernel mediante eBPF (Pixie / Cilium) + Agente de Logs Tradicional
- **Descripción:** Despliegue de programas eBPF en el Kernel de Linux de los nodos K8s para inspeccionar sockets de red y llamadas al sistema (*syscalls*) de forma no invasiva, combinado con un agente de logs (Vector/Fluentbit) para leer *stdout*.
- **Ventajas:** 
  - Cero impacto en el código fuente de los desarrolladores y mínima sobrecarga de CPU/RAM sobre los pods de la aplicación.
  - Despliegue e integración inmediatos en el clúster Kubernetes.
- **Desventajas:** 
  - Incapacidad para propagar el contexto de traza de forma determinista en procesamientos asíncronos (colas de mensajes como Kafka/RabbitMQ).
  - Imposibilidad de vincular directamente los logs estructurados del espacio de usuario con las trazas interceptadas a nivel de Kernel (no satisface ASR-2).
  - Imposibilidad de adjuntar metadatos del dominio de negocio a los tramos de ejecución (*spans*).
- **Riesgos:** 
  - Alta dependencia de versiones específicas del Kernel de Linux (>= 5.4) y necesidad de ejecutar contenedores con privilegios elevados (`CAP_SYS_ADMIN`), generando riesgos de seguridad en el clúster.

## Decisión y Justificación (Rationale)
Se selecciona la **Opción 2: Pipeline Unificado con SDKs de OpenTelemetry + Tail-Based Sampling en OTel Collector Central**.

### Justificación por ASRs y Tácticas SWEBOK v4.0 (Capítulo 2: Diseño de Software):

1. **Resolución del Conflicto Costo vs. Visibilidad (ASR-3 y R-2):**
   Se aplica la táctica de *Gestión de Recursos en Observabilidad* mediante el patrón **Tail-Based Sampling [SWEBOK-02-12]**. A diferencia del muestreo en origen (Opción 1), el OTel Collector Gateway retiene los tramos (*spans*) en búferes de memoria temporal hasta que la traza completa finaliza. Esto permite aplicar reglas deterministas:
   - Persistir el **100%** de las trazas que contengan códigos de estado de error (HTTP 5xx, excepciones no controladas).
   - Persistir el **100%** de las trazas cuyos tiempos de respuesta superen los umbrales degradados (P95/P99).
   - Persistir un porcentaje mínimo estocástico (ej. 1%) del tráfico exitoso para baselines estadísticos.
   Esta táctica garantiza que no se pague por almacenar millones de trazas triviales de tráfico sano, asegurando la permanencia de los datos críticos de diagnóstico bajo el presupuesto asignado.

2. **Diagnóstico Rápido por Correlación Contextual (ASR-2 y R-3):**
   La adopción de OpenTelemetry impone la estandarización del formato de log en JSON en los 20 microservicios, inyectando el estándar **W3C Trace Context** (`trace_id`, `span_id`) directamente en los metadatos del log. Aplicando la táctica de *Estandarización de Interfaces de Telemetría [SWEBOK-02-12]*, cualquier alerta lanzada por una métrica desalineada permite pivotar en tiempo real hacia la traza exacta y aislar los registros de log correspondientes en milisegundos, reduciendo drásticamente el MTTR.

3. **Arquitectura Multicapa Desacoplada (ASR-1, R-1 y SWEBOK-02-03):**
   Para amortiguar el impacto en el rendimiento de los 20 servicios políglotas, se implementa un patrón de procesamiento desacoplado en dos niveles (*Event-Driven Collection Pipeline*):
   - **Nivel 1 (DaemonSet por Nodo):** Los microservicios emiten telemetría mediante OTLP/gRPC sobre un *loopback* local al recolector del nodo, eliminando el acoplamiento y bloqueos I/O en la aplicación.
   - **Nivel 2 (Deployment Central Scalable):** Concentra la lógica pesada de evaluación de reglas de muestreo (*tail-based*), transformaciones y exportación hacia el backend de almacenamiento final.

### Supuestos Asumidos:
- Los equipos de desarrollo tienen la capacidad de incorporar las librerías/agentes de OpenTelemetry en sus respectivos pipelines de integración continua (CI/CD).
- Se dispone de nodos en Kubernetes con suficiente capacidad de memoria RAM dedicada para operar el grupo de colectores centrales encargados del *tail-based sampling*.

## Consecuencias

### Positivas
- **Garantía de Causa Raíz:** Se captura el 100% de los eventos anómalos o lentos de la plataforma sin importar en cuál de los 20 microservicios se hayan originado.
- **Reducción del MTTR:** Correlación bidireccional instantánea entre Logs, Métricas y Trazas mediante un identificador único global (`trace_id`).
- **Control Presupuestario Riguroso:** Eliminación del desperdicio de almacenamiento mediante el descarte inteligente en memoria de telemetría redundante antes de ser escrita en disco.
- **Portabilidad Futura:** Arquitectura basada completamente en el estándar graduado por la CNCF (OpenTelemetry), evitando el acoplamiento a tecnologías o proveedores propietarios.

### Negativas
- **Esfuerzo de Adopción Inicial:** Necesidad de refactorizar el middleware de logging de las aplicaciones para garantizar el formato JSON y la inyección del contexto W3C.
- **Consumo de Memoria Centralizada:** El clúster de OTel Collectors requiere un dimensionamiento de memoria RAM proporcional al volumen de trazas simultáneas en procesamiento.

### Trade-offs y Riesgos Residuales

*   **Trade-off (Esfuerzo de Desarrollo vs. Calidad de Diagnóstico):** Se sacrifica la inmediatez de una solución "cero código" (como eBPF o Mesh puro) a cambio de obtener correlación exacta intra-proceso y soporte para procesamientos asíncronos.
*   **Riesgo Residual 1: Desbordamiento de Memoria por Tormenta de Fallas (OOM-Killed en Collector Central).**
    *Mitigación:* Se configurará obligatoriamente el procesador `memory_limiter` en el OTel Collector Central con límites estrictos de uso de Heap, sumado a una política de descarte por *backpressure* y la reserva de espacio de búfer tipo *ballast* para prevenir la caída del pod ante picos inusuales de errores en la plataforma (*SWEBOK-02-03 Fault Tolerance*).
*   **Riesgo Residual 2: Latencia de Red por Propagación de Contexto.**
    *Mitigación:* Utilización del protocolo binario de alta eficiencia OTLP/gRPC para el transporte de telemetría entre los pods de aplicación y los colectores locales del nodo.