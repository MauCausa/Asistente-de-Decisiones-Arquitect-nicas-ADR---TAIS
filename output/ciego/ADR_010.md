# ADR-005: Estrategia de Resiliencia, Idempotencia y Tolerancia a Fallos ante Proveedor Externo de Pagos

* **Estado:** Aceptado
* **Fecha:** 2023-10-25
* **Autores:** Equipo de Arquitectura de Software
* **Contexto del problema:** CASO_05 - Resiliencia ante fallas de un proveedor externo de pagos

---

## 1. Contexto y Problema

El servicio de cobros del sistema depende de una pasarela de pagos externa que experimenta degradación aleatoria de desempeño, expresada en latencias variables y caídas breves del servicio. 

La implementación actual realiza reintentos no coordinados ni idempotentes. Esto ha ocasionado dos problemas críticos:
1. **Cobros duplicados:** Al reintentar una solicitud cuya respuesta se perdió por *timeout*, la pasarela procesa el cobro nuevamente.
2. **Agotamiento de recursos (Thread Starvation):** Las peticiones bloqueadas esperando a la pasarela consumen los hilos de ejecución del servicio, degradando la disponibilidad global de la aplicación.

Se requiere diseñar una solución que garantice la resiliencia del sistema, proteja la integridad transaccional (evitando duplicidades), limite el tiempo de bloqueo de recursos y permita una recuperación controlada auditando cada fallo.

---

## 2. Drivers de Decisión (Atributos de Calidad y Requisitos)

* **Tolerancia a fallos:** El sistema debe resistir la indisponibilidad temporal del proveedor externo sin colapsar la arquitectura interna.
* **Integridad de transacciones:** Garantía estricta de *At-Most-Once* en los cobros; bajo ninguna circunstancia se debe cobrar dos veces al cliente por una misma transacción.
* **Recuperación controlada:** El sistema debe ser capaz de reanudar el tráfico hacia la pasarela de forma paulatina una vez restablecido el servicio.

---

## 3. Restricciones Téchnicas y de Negocio

* **Idempotencia nativa:** La API de la pasarela externa soporta el uso de claves de idempotencia (*Idempotency Keys*).
* **SLA de Latencia Maxima:** El tiempo máximo de espera (*Timeout*) permitido por operación es de **8 segundos**.
* **Auditoría obligatoria:** Todas las operaciones fallidas, tiempos de espera agotados o rechazos deben ser registrados de forma inmutable para reconciliación posterior.

---

## 4. Opciones Consideradas

* **Opción 1: Reintentos simples síncronos con incremento de Timeout.** Mantener la arquitectura actual pero aumentando el *timeout*. (Descartado: empeora el agotamiento de hilos).
* **Opción 2: Patrón Circuit Breaker + Claves de Idempotencia + Reintentos Asíncronos con Backoff Exponencial.** Implementar un interruptor de circuito para aislar la pasarela degradada, usar claves de idempotencia derivadas de la transacción y procesar los cobros de forma asíncrona mediante colas de mensajes en caso de fallos temporales.
* **Opción 3: Despliegue de Pasarela de Respaldo (Multi-vendor Routing).** Derivar el tráfico a un segundo proveedor de pagos cuando el primario falle. (Descartado por restricciones del negocio respecto a contratos vigentes).

---

## 5. Decisión Arquitectónica

Se decide adoptar la **Opción 2**. La arquitectura integrará una solución multicapa basada en:

1. **Gestión de la Idempotencia:**
   * Cada solicitud de cobro generará un `transaction_id` único en la base de datos local antes de llamar a la pasarela.
   * Este ID se enviará en la cabecera `Idempotency-Key` requerida por el proveedor externo.

2. **Control de Tiempo de Espera (Timeout):**
   * Se establece un **Timeout estricto de 7 segundos** a nivel de cliente HTTP (dentro del límite máximo permitido de 8 segundos) para evitar el acoplamiento de hilos.

3. **Patrón Circuit Breaker (Cortocircuito):**
   * Se implementará un *Circuit Breaker* alrededor del cliente del proveedor con tres estados:
     * **Cerrado:** Flujo normal.
     * **Abierto:** Si el 50% de las peticiones en una ventana de 10 segundos fallan o superan el timeout, el circuito se abre inmediatamente. Las peticiones subsiguientes fallan rápido (*Fail-Fast*) sin consumir hilos del sistema.
     * **Entreabierto (Half-Open):** Transcurridos 30 segundos, se permite un tráfico de prueba (10% de las peticiones) para evaluar la recuperación de la pasarela.

4. **Desacoplamiento y Reintentos Asíncronos (Outbox Pattern + DLQ):**
   * Si la pasarela falla por problemas de red o si el circuito está abierto, la transacción no se descarta. Se registra como `PENDIENTE_REINTENTO` en una tabla de auditoría local y se envía a una cola de procesamiento asíncrono.
   * Un worker reintentará la transacción respetando la clave de idempotencia original mediante **Backoff Exponencial con Jitter**.
   * Si tras $N$ intentos la falla persiste, el mensaje se envía a una *Dead Letter Queue* (DLQ) para auditoría e intervención manual.

---

## 6. Diagrama del Flujo de Ejecución

```
[ Cliente / Servicio ]
         │
         ▼
 1. Generar Transaction ID
    & Guardar Estado "INICIADO"
         │
         ▼
 2. Evaluar Circuit Breaker ────(Abierto)────► 3. Guardar en Cola para
         │                                       Procesamiento Asíncrono
     (Cerrado)                                           │
         │                                               ▼
         ▼                                     4. Registro de Auditoría
 5. Llamada a Pasarela                                   (Transacción Fallida/Pospuesta)
    - Timeout: 7s
    - Header: Idempotency-Key
         │
    ┌────┴────────────────────────┬────────────────────────┐
    │                             │                        │
(Éxito < 7s)               (Timeout / Error 5xx)     (Error 4xx - Rechazo definitivo)
    │                             │                        │
    ▼                             ▼                        ▼
Actualizar a               Registrar en Cola /       Actualizar a "RECHAZADO"
"COMPLETADO"               Activar Circuit Breaker   Auditado inmutablemente
```

---

## 7. Consecuencias y Impacto

### Positivas
* **Protección Financiera:** Cero riesgo de cobros duplicados gracias a la obligatoriedad del `Idempotency-Key`.
* **Resiliencia de Recursos:** Se evita el *Thread Starvation*. Si la pasarela cae, el *Circuit Breaker* responde en milisegundos (*Fail-Fast*).
* **Consistencia Eventual:** Las fallas transitorias se resuelven automáticamente en segundo plano sin impactar la experiencia del usuario de forma síncrona.
* **Trazabilidad Total:** Todo fallo queda auditado con su respectivo identificador, payload y causa raíz.

### Negativas / Mitigaciones
* **Complejidad Operativa:** Incrementa la complejidad al introducir componentes de mensajería asíncrona y Workers para el procesamiento diferido.
  * *Mitigación:* Uso de librerías maduras para el *Circuit Breaker* (ej. Resilience4j / Polly) y monitoreo centralizado con métricas Prometheus/Grafana.
* **Latencia en Diagnóstico:** Para operaciones diferidas, el cliente debe consultar el estado final mediante *polling* o recibir una notificación vía *Webhooks/WebSockets*.

---

## 8. Cumplimiento de Restricciones y Auditoría

| Criterio / Restricción | Implementación en la Decisión |
| :--- | :--- |
| **Claves de Idempotencia** | Generación estricta de `Idempotency-Key` por transacción única persistida previamente. |
| **Timeout Max. 8s** | Timeout HTTP configurado en 7 segundos para dejar margen de 1s de procesamiento interno. |
| **Auditoría de Fallas** | Patrón *Transactional Outbox* + DLQ. Todo estado de error genera un registro inmutable en base de datos conteniendo: `transaction_id`, `timestamp`, `error_code`, `http_status` y `payload_sent`. |