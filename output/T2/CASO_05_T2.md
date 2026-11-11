# CASO_05 - Resiliencia ante fallas de un proveedor externo de pagos

## Estado
Aceptado (Propuesto y validado mediante asistencia híbrida SWEBOK v4.0 + evaluación de trade-offs)

## Contexto y Problema
El servicio de cobros de la organización depende críticamente de una pasarela de pagos externa para procesar las transacciones financieras. Este proveedor externo presenta un comportamiento inestable caracterizado por latencias variables de red y caídas breves e impredecibles. 

Bajo la implementación actual, el mecanismo de reintentos síncronos ingenuos genera dos fallas operativas graves:
1. **Agotamiento de Recursos (Thread Pool Exhaustion):** Las peticiones colgadas esperando respuesta de la pasarela bloquean los hilos del servidor de aplicaciones, degradando y eventualmente colapsando el servicio completo de cobros ante picos de latencia externa.
2. **Duplicación de Cargos (Double-Charging):** Al reintentar peticiones que sufrieron un tiempo de espera excedido (*socket timeout*) en la capa de transporte, pero que sí fueron procesadas exitosamente por la pasarela, se generan cobros duplicados a los usuarios finales.

El problema arquitectónico consiste en diseñar una estrategia de integración resiliente que aísle al sistema de las fallas del proveedor, garantice la semántica de cobro único sin enmascarar fallas definitivas, cumpla con la restricción de un tiempo máximo de respuesta global de **8 segundos** por operación, y mantenga un registro inalterable de auditoría sin degradar la base de datos operacional transaccional.

## Drivers de Decisión (ASRs)
*   **ASR-01: Tolerancia a Fallos (Disponibilidad y Resiliencia):** Aísla la latencia y las caídas del proveedor externo, evitando el agotamiento del grupo de hilos (*Thread Pool Exhaustion*) y previniendo fallas en cascada en el servicio de cobros (`[SWEBOK-02-07]`).
*   **ASR-02: Integridad de Transacciones (Consistencia e Idempotencia):** Garantiza la semántica de procesamiento *exactly-once* a nivel de negocio. Se debe prevenir bajo cualquier circunstancia de falla de red o reintento el cobro duplicado a los clientes.
*   **ASR-03: Recuperación Controlada y Auditabilidad (Auditabilidad y Confiabilidad):** Propaga las fallas definitivas de forma determinista y registra de manera inmutable y persistente todas las operaciones fallidas, incompletas o en estado incierto para análisis forense y financiero (`[SWEBOK-02-09]`).
*   **R-01: Límite de Tiempo de Espera (Timeout Estricto):** La ventana máxima de respuesta síncrona global no puede superar los **8 segundos**.
*   **R-02: Capacidad de Idempotencia del Proveedor:** Obligación de generar, registrar y transmitir claves de idempotencia (*Idempotency Keys*) unívocas hacia la pasarela externa previa a la invocación de red.
*   **R-03: Auditoría Obligatoria de Fallas:** Todas las operaciones fallidas o inconclusas deben quedar registradas en un plano de auditoría dedicado, sin impactar el rendimiento I/O del almacenamiento primario.

## Opciones Consideradas

### Opción 1: Arquitectura Síncrona Resiliente con Circuit Breaker En-Línea y Reintentos Acotados
- **Descripción:** Implementación de invocación síncrona directa a la pasarela protegida mediante un patrón *Circuit Breaker* (ej. Resilience4j) y un reintento síncrono acotado. Asigna un timeout estricto de 3.5s por llamada, permitiendo máximo 1 reintento dentro del margen de 8s. Escribe las fallas síncronamente en la BD primario.
- **Ventajas:** Simplicidad arquitectónica y operativa. Protege los hilos del servicio ante caídas masivas del proveedor mediante el corte rápido (*Fail-Fast*) cuando el circuito se abre.
- **Desventajas:** Vulnerable a inconsistencias y cobros duplicados en caso de *socket timeouts* intermitentes. La escritura síncrona de logs de auditoría contamina y degrada la base de datos operacional transaccional bajo condiciones de estrés.
- **Riesgos:** Alta probabilidad de generar un falso negativo (asumir que la transacción falló cuando fue procesada tarde por la pasarela) derivando en reintentos síncronos peligrosos.

### Opción 2: Arquitectura Desacoplada Basada en Eventos con Outbox Pattern y Reconciliación Asíncrona
- **Descripción:** Modelo completamente asíncrono y orientado a eventos. La recepción del cobro persiste la transacción como `QUEUED` mediante el patrón *Transactional Outbox* y responde de inmediato un HTTP `202 Accepted` al cliente. Un proceso *Worker* asíncrono procesa la orden, invoca a la pasarela y envía fallas a una *Dead Letter Queue* (DLQ) para auditoría inmutable.
- **Ventajas:** Inmunidad total al agotamiento de hilos HTTP (respuestas en <100ms). Aislamiento completo de la latencia del proveedor y desacoplamiento nativo de la auditoría via DLQ.
- **Desventajas:** Rompe la semántica de la API cambiando de un modelo síncrono a un contrato asíncrono basado en *polling* o *webhooks*. Añade una alta complejidad de infraestructura (Event Broker, CDC, Workers).
- **Riesgos:** Condiciones de carrera si el cliente intenta cancelar o reintentar el pago por otro canal mientras el evento sigue encolado en el Broker.

### Opción 3: Arquitectura Híbrida "Dual-Phase" (Síncrona Acotada con Patrón Saga/Reconciliador y Plano de Auditoría Desacoplado)
- **Descripción:** Estrategia en dos fases. **Fase 1 (Síncrona Acotada):** Generación y persistencia de la *Idempotency Key* ($IK$) localmente; invocación síncrona con *Timeout* estricto de 3.5s y máximo 1 reintento rápido (solo ante errores de red no ambiguos). Si la llamada expira sin confirmación a los ~6s, el servicio **no reintenta a ciegas**, pasa el estado local a `UNCERTAIN_RECONCILE` y retorna un estado determinista `PENDING_CONFIRMATION` antes de los 8s (R-01). **Fase 2 (Asíncrona):** Un *Worker de Reconciliación* consulta asíncronamente el estado real en la pasarela usando la $IK$. Las fallas se publican de forma asíncrona hacia un almacén de auditoría inmutable (`append-only`).
- **Ventajas:** Garantiza estrictamente el límite de 8s (R-01) y protege los hilos. Elimina el riesgo de cobro duplicado (ASR-02) al evitar reintentos síncronos ante respuestas ambiguas. Desacopla la auditoría evitando degradar la BD operacional (R-03).
- **Desventajas:** Requiere soportar y gestionar el estado transaccional intermedio `UNCERTAIN_RECONCILE` en el dominio de negocio.
- **Riesgos:** Dependencia de la disponibilidad de un endpoint de consulta de estado por $IK$ en la pasarela del proveedor.

## Decisión y Justificación (Rationale)
Se selecciona la **Opción 3: Arquitectura Híbrida "Dual-Phase"**.

### Justificación por ASR y Restricción:
1. **Atención a ASR-01 (Tolerancia a Fallos) y Restricción R-01 ( Timeout <= 8s):**
   La Opción 3 establece un presupuesto de tiempo férreo en la Fase Síncrona: $3.5\text{s (intento 1)} + 0.5\text{s (backoff/jitter)} + 3.5\text{s (intento 2)} = 7.5\text{s}$ máximo absoluto. Se implementa un envoltura de resiliencia (`Resilience Wrapper`) con aislamiento de hilos (*Bulkhead/Semaphore*). Al cortar la ejecución a los 7.5s y liberar el hilo HTTP, se erradica por completo la amenaza de *Thread Pool Exhaustion* recomendada en `[SWEBOK-02-07]`.
2. **Atención a ASR-02 (Integridad) y Restricción R-02 (Idempotencia):**
   Antes de emitir cualquier paquete a la red, se persiste localmente la $IK$ única (R-02). Si ocurre un *Socket Timeout* o falla indeterminada en el segundo intento, la Opción 3 **prohíbe reintentar a ciegas**. En su lugar, transiciona el registro a `UNCERTAIN_RECONCILE` y transfiere la responsabilidad al *Worker de Reconciliación*. Este worker consulta a la pasarela utilizando la $IK$ previa a ejecutar cualquier acción correctiva, garantizando la semántica *exactly-once* y previniendo de forma absoluta el cobro duplicado.
3. **Atención a ASR-03 (Auditabilidad) y Restricción R-03 (Auditoría de Fallas):**
   Para no impactar el rendimiento I/O de la base de datos operacional transaccional, las fallas definitivas o transiciones a estados inciertos emiten eventos asíncronos no bloqueantes (`Append-Only Event Stream`) hacia un almacén de auditoría inmutable dedicado (ej. Elasticsearch/S3 Append-Only Log) cumpliendo de manera estricta con R-03 y las tácticas de separación de planos de `[SWEBOK-02-09]`.

### Supuestos Asumidos:
*   Se asume que la pasarela de pagos externa soporta la consulta de estado de transacciones (*Query/Status API*) utilizando la misma *Idempotency Key* o ID de referencia enviado en la solicitud original.
*   Se asume que los clientes consumidores del API de cobros pueden interpretar una respuesta HTTP determinista de estado pendiente (`202 Accepted` o `200 OK` con payload `status: PENDING_CONFIRMATION`) en aquellos casos donde el proveedor presente latencia extrema.

## Consecuencias

### Positivas
*   **Aislamiento de Recursos Garantizado:** Eliminación del riesgo de colapso del servicio por agotamiento de hilos (*Thread Pool Exhaustion*).
*   **Cero Cobros Duplicados:** La combinación de persistencia previa de $IK$, corte de tiempo estricto y reconciliación asíncrona elimina la causa raíz de la duplicación de cargos.
*   **Cumplimiento Estricto de Tiempos:** El cliente siempre recibe una respuesta determinista en menos de 8 segundos (7.5s en el peor escenario síncrono).
*   **Desacoplamiento de Auditoría:** La BD primario queda libre de la carga de I/O contenciosa generada por los registros de auditoría de fallas.

### Negativas
*   **Complejidad en el Modelo de Dominio:** Obliga a introducir y gestionar los estados transaccionales `UNCERTAIN_RECONCILE` y `PENDING_CONFIRMATION`.
*   **Componente Adicional:** Requiere construir, desplegar y monitorear el *Worker de Reconciliación* asíncrono y el bus de eventos de auditoría.

### Trade-offs y Riesgos Residuales

*   **Trade-off (Consistencia Inmediata vs. Resiliencia y Latencia):** Se sacrifica la confirmación síncrona inmediata en el 100% de los casos a cambio de garantizar la integridad del dinero y la disponibilidad del sistema. Cuando la pasarela está degradada, la confirmación final se pospone para ser resuelta de forma asíncrona (Consistencia Eventual).
*   **Riesgo Residual 1:** *Inaccesibilidad del Endpoint de Reconciliación de la Pasarela.* Si la pasarela sufre una caída total y no responde tampoco a las consultas del *Worker de Reconciliación*.
    *   *Mitigación:* El *Worker* aplicará reintentos con *Exponential Backoff* prolongado (horas) y, en caso de falla persistente tras 24 horas, marcará el registro para reconciliación manual mediante el archivo de liquidación diario (*Settlement File*).
*   **Riesgo Residual 2:** *Latencia en la Notificación Final al Cliente.* El cliente final puede quedar en incertidumbre breve sobre el estado de su pago si la reconciliación tarda minutos.
    *   *Mitigación:* Exposición de un endpoint de consulta de estado de pago (*Polling Endpoint*) para el cliente y emisión de notificaciones tipo *Webhook* / *Push* tan pronto como el *Worker de Reconciliación* resuelva el estado de la transacción.