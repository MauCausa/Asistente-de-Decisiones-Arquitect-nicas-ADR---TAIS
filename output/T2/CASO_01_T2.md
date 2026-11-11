# CASO_01 - Comunicacion asincrona para pedidos de comercio electronico

## Estado
Aceptado (Propuesto y validado mediante asistencia híbrida SWEBOK v4.0 + evaluación de trade-offs)

## Contexto y Problema
La plataforma de comercio electrónico debe operar de forma confiable durante campañas de alto tráfico, procesando picos de hasta 2,500 pedidos por minuto (~42+ TPS promedio con ráfagas concurrentes superiores). En la arquitectura actual, el Servicio de Pedidos realiza invocaciones síncronas directas hacia los servicios de Inventario, Pagos y Notificaciones. Este acoplamiento síncrono causa un efecto en cascada (*cascading failure*): la falla parcial o la alta latencia en cualquiera de los servicios downstream (especialmente pasarelas de pago o notificaciones) bloquea el hilo de ejecución de Pedidos, provocando el agotamiento de recursos (*thread pool exhaustion*) y la caída total de la operación comercial.

El problema técnico exige migrar hacia un paradigma de comunicación asíncrona que desacople temporalmente los componentes y nivele la carga de trabajo. Además, el negocio requiere la capacidad estricta de auditar inmutablemente cada evento y reprocesar el historial (*event replay*) en caso de fallas operativas o conciliaciones. Esta solución debe implementarse bajo restricciones claras: empaquetamiento y orquestación exclusiva en contenedores Docker (R-01), adaptación al nivel de habilidad de un equipo con experiencia básica en mensajería (R-02), y la garantía absoluta de no perder ningún pedido verificado o confirmado (R-03).

## Drivers de Decisión (ASRs)
- **ASR-01: Escalabilidad ante picos de carga (Performance & Scalability):** Absorber ráfagas de hasta 2,500 pedidos/minuto sin degradación de rendimiento ni agotamiento de recursos, amortiguando el tráfico (*load leveling*) antes de impactar a los consumidores downstream.
- **ASR-02: Desacoplamiento temporal (Availability & Modularity):** Permitir que el Servicio de Pedidos confirme la recepción del pedido e ingrese la solicitud sin depender de la disponibilidad síncrona o la latencia de los servicios de Inventario, Pagos y Notificaciones.
- **ASR-03: Trazabilidad y reprocesamiento de eventos (Auditability & Reliability):** Mantener un registro inmutable de eventos que permita la lectura por múltiples consumidores independientes y el re-procesamiento (*replay*) histórico desde cualquier punto del tiempo.
- **R-01: Despliegue en contenedores Docker (Constraint):** La infraestructura debe ser liviana, portable y configurable declarativamente en contenedores Docker sin dependencias propietarias de nubes específicas.
- **R-02: Equipo con experiencia básica en mensajería (Constraint):** Diseños con baja sobrecarga cognitiva y operacional, evitando modelos de administración de clústeres complejos que incrementen el riesgo de fallas por mala configuración.
- **R-03: No se permite perder pedidos confirmados (Constraint):** Garantizar la persistencia duradera del pedido y del evento (*at-least-once delivery*) antes de responder al cliente final.

## Opciones Consideradas

### Opción 1: Broker de Mensajería Tradicional AMQP (RabbitMQ) + Store de Auditoría Adicional (Outbox / Database Sync)
- **Descripción:** El servicio de pedidos guarda el pedido localmente y publica el evento `pedido.creado` en un *Topic Exchange* de RabbitMQ con colas duraderas para Inventario, Pagos y Notificaciones. Para cumplir con el *Event Replay* y la auditoría, se desarrolla un servicio adicional (`Audit-Worker`) que consume los mensajes y los persiste de manera inmutable en una base de datos secundaria (PostgreSQL/MongoDB).
- **Ventajas:** 
  - Excelente amortiguación de picos de carga (ASR-01) y desacoplamiento temporal completo (ASR-02).
  - La curva de aprendizaje de RabbitMQ es baja, ideal para el nivel del equipo (R-02), y su contenedor Docker es liviano (R-01).
- **Desventajas:** 
  - Las colas AMQP destruyen el mensaje tras la confirmación de lectura (`ACK`), careciendo de soporte nativo para *replay* (ASR-03).
  - Duplica la infraestructura necesaria (Broker AMQP + Base de datos de auditoría) y exige desarrollar herramientas manuales para la re-ingestión de eventos.
- **Riesgos:** 
  - Riesgo de inconsistencia o retrasos entre las colas de trabajo y la base de datos de auditoría si el `Audit-Worker` sufre fallas.
  - Riesgo de errores humanos al ejecutar scripts ad-hoc para republicar mensajes antiguos.

### Opción 2: Event-Streaming con Log Particionado Distribución Nativa (Apache Kafka)
- **Descripción:** Arquitectura basada completamente en *Event-Streaming* donde el Servicio de Pedidos publica en tópicos de Apache Kafka retenidos en disco. Los servicios downstream leen mediante *Consumer Groups* independientes gestionando sus propios *offsets*.
- **Ventajas:** 
  - Soporte nativo, robusto y de alto rendimiento para auditoría e *Event Replay* basado en la manipulación de *offsets* (ASR-03).
  - Capacidad de procesamiento masivo que supera con facilidad los requerimientos de picos de carga (ASR-01).
- **Desventajas:** 
  - Alta sobrecarga operativa y de memoria RAM dentro de contenedores Docker (R-01).
  - Exige conceptos avanzados (gestión de particiones, *rebalancing*, configuración de quórums KRaft/Zookeeper, políticas de *flush*) que sobrepasan la experiencia básica del equipo (R-02).
- **Riesgos:** 
  - Elevada probabilidad de pérdida de datos (violando R-03) o duplicidad masiva en producción por errores de configuración en el cliente/servidor Kafka.

### Opción 3: Event-Streaming Ligero Nativo (Redpanda o NATS JetStream) con Patrón Transactional Outbox
- **Descripción:** Utilización de un motor de *Event-Streaming* de binario único (como Redpanda o NATS JetStream) compatible con la abstracción de log persistente. Se implementa el patrón *Transactional Outbox* en el Servicio de Pedidos: el pedido y su evento representativo se escriben en la base de datos local en una única transacción ACID. Un proceso de retransmisión lee la tabla Outbox y publica el evento en el motor de streaming, donde queda retenido para lectura por *offsets* e inmutabilidad de auditoría.
- **Ventajas:** 
  - Cumplimiento nativo de *Event Replay* e inmutabilidad (ASR-03) sin requerir bases de datos secundarias para auditoría.
  - Consumo mínimo de recursos en contenedores Docker (~100MB RAM, binario único sin JVM) (R-01).
  - Garantía transaccional absoluta contra la pérdida de pedidos (R-03) combinando la transacción ACID con el motor de streaming duradero.
  - Abstracción operacional simplificada que reduce la fricción en equipos con experiencia básica (R-02).
- **Desventajas:** 
  - Requiere que el equipo aprenda la semántica básica de *offsets* y *Consumer Groups* en lugar de la destrucción tradicional de colas AMQP.
  - El patrón Outbox requiere mantenimiento preventivo de purga en la tabla de la base de datos operacional.
- **Riesgos:** 
  - Riesgo de duplicación de eventos durante reintentos de red, requiriendo que los consumidores apliquen controles de idempotencia.

## Decisión y Justificación (Rationale)
Se selecciona la **Opción 3: Event-Streaming Ligero Nativo (Redpanda/NATS JetStream) con Patrón Transactional Outbox**.

### Fundamentación Técnica y Trazabilidad de ASRs/Restricciones:
1. **Resolución del dilema ASR-03 vs. R-02/R-01:**  
   La Opción 1 (RabbitMQ) requiere crear y operar un sistema paralelo complejo de auditoría para compensar su incapacidad nativa de re-procesar eventos. La Opción 2 (Kafka) resuelve ASR-03 nativamente, pero incumple las restricciones R-01 y R-02 por su alta exigencia de recursos y complejidad de gestión. La Opción 3 provee la capacidad de log inmutable append-only y *replay* por *offsets* **[SWEBOK-02-03]** requerida por el **ASR-03**, manteniendo la simplicidad operativa de un único contenedor liviano que encaja perfectamente en Docker **(R-01)** y en el perfil técnico del equipo **(R-02)**.

2. **Garantía Transaccional de No Pérdida (R-03):**  
   Se adopta la táctica de diseño **[SWEBOK-02-09] Transactional Outbox**. El Servicio de Pedidos almacena en la misma transacción ACID de la base de datos relacional el registro del pedido y el evento `PedidoCreado`. Con esto se garantiza que ningún pedido confirmado quede huérfano de evento, incluso ante una falla imprevista del motor de mensajería o reinicio de contenedores.

3. **Desacoplamiento y Control de Picos (ASR-01, ASR-02):**  
   El motor de streaming absorbe las ráfagas de 2,500 pedidos/min mediante amortiguación en disco (*load leveling*). Los servicios de Inventario, Pagos y Notificaciones consumen de forma asíncrona mediante *Consumer Groups* independientes **[SWEBOK-02-03]**. Si el Servicio de Pagos falla o la pasarela externa se degrada, el Servicio de Pedidos sigue operando sin interrupción, cumpliendo con el desacoplamiento temporal de la **ASR-02**.

4. **Tácticas de Resiliencia en Consumidores:**  
   Para evitar fallas por latencias externas en el consumo (ej. Pasarela de Pagos), se aplican las tácticas **[SWEBOK-02-07] Circuit Breaker + Exponential Backoff**. Adicionalmente, ante la entrega con semántica *at-least-once*, los consumidores obligatoriamente aplican verificación de **Idempotency Key** para evitar cobros o reservas duplicadas.

### Supuestos Asumidos:
- La base de datos relacional del Servicio de Pedidos soporta transacciones ACID locales y tiene capacidad para almacenar temporalmente la tabla Outbox.
- Los volúmenes de almacenamiento en Docker están configurados con volumen persistente mapeado al *host* para evitar pérdida de logs del motor de streaming tras reinicios de contenedores.

## Consecuencias

### Positivas
- **Inmutabilidad y Re-procesamiento:** Capacidad nativa de reiniciar punteros de lectura (*offsets*) para auditar o re-procesar eventos pasados sin afectar la operación activa de otros microservicios.
- **Cero Pérdida de Datos:** La combinación del patrón *Transactional Outbox* con la retención persistente del broker garantiza que ningún pedido confirmado se pierda.
- **Eficiencia de Recursos:** El motor de streaming ligero se ejecuta en Docker con un footprint mínimo de memoria RAM y CPU, agilizando los entornos de desarrollo y producción.
- **Ailamiento de Fallas:** Las caídas de servicios downstream no bloquean la creación ni confirmación de nuevos pedidos en el sistema principal.

### Negativas
- **Complejidad de Mantenimiento del Outbox:** Se introduce la necesidad de un proceso de purga periódico (*cleanup job*) sobre la tabla Outbox en la base de datos de Pedidos para prevenir su crecimiento desmedido.
- **Gestión de Consistencia Eventual:** La confirmación del pedido hacia el usuario ocurre antes del procesamiento de pagos e inventario, requiriendo que la interfaz de usuario gestione estados asíncronos (ej. "Pedido en Procesamiento").

### Trade-offs y Riesgos Residuales
- **Concesión Aceptada (Mensajería at-least-once vs. Complejidad en Consumidores):**  
  *Trade-off:* Se acepta la posibilidad de recibir eventos duplicados en la capa de consumo a cambio de garantizar la entrega sin pérdida de mensajes y mantener una infraestructura simple.  
  *Riesgo Residual:* Riesgo de duplicidad en transacciones de pago o duplicación de reservas de inventario durante reintentos por fallas de red.  
  *Mitigación:* Se exige la implementación obligatoria de una tabla/cache de deduplicación basada en la clave primaria del evento (`pedido_id`) como filtro de **Idempotencia [SWEBOK-02-07]** en todos los servicios consumidores antes de ejecutar cualquier lógica de negocio.