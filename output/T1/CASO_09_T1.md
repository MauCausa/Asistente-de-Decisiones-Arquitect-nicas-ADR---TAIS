Este es el Registro de Decisión Arquitectónica (ADR) para abordar la consistencia entre los microservicios de pedidos e inventario.

# ADR 009: Implementación de Patrón Saga Basado en Coreografía para Consistencia Eventual

## Estado
Aceptado

## Contexto
El sistema actual utiliza microservicios independientes para la gestión de **Pedidos** (Orders) e **Inventario** (Inventory), cada uno con su propia base de datos. Actualmente, existe un riesgo de inconsistencia: si el servicio de pedidos confirma una orden pero el sistema falla antes de comunicarse con el inventario, el stock no se reserva, generando pedidos "fantasma" sin productos disponibles.

### Restricciones y Requisitos
*   **No a 2PC:** Las transacciones distribuidas (Two-Phase Commit) están descartadas por su falta de escalabilidad y acoplamiento.
*   **Consistencia Eventual:** El negocio acepta que el inventario no se actualice instantáneamente, siempre que el sistema se autorregule.
*   **Atropellamiento de Mensajes:** La infraestructura de mensajería puede entregar mensajes duplicados (at-least-once delivery).
*   **Trazabilidad:** Es imperativo saber en qué estado se encuentra una transacción en todo momento.

## Decisión
Implementaremos el **Patrón Saga basado en Coreografía** junto con el patrón **Transactional Outbox**.

### Detalles de la solución:
1.  **Saga de Coreografía:** Los servicios se comunicarán mediante eventos asíncronos. No habrá un orquestador central; cada servicio sabe qué evento escuchar y qué acción tomar (incluyendo compensaciones).
2.  **Patrón Transactional Outbox:** Para garantizar que el mensaje se envíe solo si la base de datos local se actualiza, cada servicio escribirá el evento en una tabla `Outbox` dentro de su propia transacción local. Un proceso independiente (Relay) leerá esta tabla y publicará el mensaje en el Broker (RabbitMQ/Kafka).
3.  **Idempotencia:** Dado que los mensajes pueden duplicarse, el servicio de Inventario y el de Pedidos implementarán manejadores de eventos idempotentes (verificando si el ID de la transacción ya fue procesado).
4.  **Lógica de Compensación:**
    *   Si el Inventario falla al reservar (ej. no hay stock), emitirá un evento `StockReservationFailed`.
    *   El servicio de Pedidos escuchará este evento y ejecutará una transacción compensatoria para marcar el pedido como `CANCELADO_POR_FALTA_DE_STOCK`.

## Consecuencias

### Positivas
*   **Desacoplamiento:** Los servicios no dependen de la disponibilidad inmediata del otro para procesar su parte.
*   **Escalabilidad:** Al no bloquear recursos con transacciones distribuidas, el rendimiento es superior.
*   **Resiliencia:** Si el servicio de inventario está caído, el mensaje permanecerá en la cola hasta que se recupere, garantizando que el stock se procese eventualmente.

### Negativas / Riesgos
*   **Complejidad de Depuración:** Rastrear una transacción a través de múltiples servicios y colas es más difícil. Se requiere el uso de **Correlation IDs**.
*   **Lecturas Sucias:** Un usuario podría ver su pedido como "Creado" mientras la saga aún está intentando reservar el stock (consistencia eventual).
*   **Complejidad de Implementación:** Requiere lógica adicional para manejar la tabla Outbox y la idempotencia en los consumidores.

## Atributos de Calidad Satisfechos
*   **Consistencia Eventual Confiable:** Garantizada por el patrón Outbox y el reintento de mensajes.
*   **Trazabilidad:** Lograda mediante el registro de estados de la Saga y Correlation IDs en los eventos.
*   **Recuperación ante fallos:** Las transacciones compensatorias aseguran que el sistema regrese a un estado consistente si un paso falla.