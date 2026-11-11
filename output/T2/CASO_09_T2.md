# CASO_09 - Consistencia entre pedidos e inventario en microservicios

## Estado
Aceptado

## Contexto y Problema
El sistema actual de comercio electrónico ha migrado a una arquitectura de microservicios donde los dominios de "Pedidos" e "Inventario" operan con bases de datos independientes para garantizar autonomía y escalabilidad. Sin embargo, ha surgido un problema crítico de integridad de datos: al no existir transacciones atómicas entre servicios, una caída del sistema o un error de red después de confirmar un pedido puede impedir la reserva de stock correspondiente. Esto genera estados inconsistentes donde el cliente cree haber realizado una compra que el almacén no reconoce. El negocio prohíbe el uso de transacciones distribuidas (2PC) por su impacto en la latencia y disponibilidad, pero exige que cualquier fallo sea trazable y que las acciones compensatorias (como cancelaciones de pedidos por falta de stock) sean visibles y automáticas.

## Drivers de Decisión (ASRs)
*   **ASR-01: Consistencia eventual confiable:** Garantizar que, a pesar de la separación de bases de datos, el estado final entre el pedido y el inventario sea coherente a través de mecanismos de compensación.
*   **ASR-02: Trazabilidad de transacciones:** Capacidad de reconstruir la línea de tiempo de cada transacción distribuida para auditoría y soporte técnico [SWEBOK-02-09].
*   **ASR-03: Recuperación ante fallos parciales:** Resiliencia para retomar procesos interrumpidos sin pérdida de datos ni duplicidad de acciones.
*   **Restricción R-01 (Database-per-Service):** No se permite el acceso directo a bases de datos ajenas ni integridad referencial compartida.
*   **Restricción R-02 (No 2PC):** Se prohíben protocolos de bloqueo de dos fases para evitar cuellos de botella.
*   **Restricción R-03 (At-least-once delivery):** El diseño debe tolerar la recepción de mensajes duplicados mediante mecanismos de idempotencia.

## Opciones Consideradas

### Opción 1: Saga Coreografiada con Transactional Outbox
- **Descripción:** Cada servicio publica eventos (ej. `PedidoCreado`) y otros servicios reaccionan a ellos de forma autónoma. Se usa una tabla "Outbox" en cada servicio para asegurar que el evento se guarde atómicamente con el cambio de estado local.
- **Ventajas:** Máximo desacoplamiento; no hay un punto central de fallo lógico; fácil de añadir nuevos interesados en los eventos.
- **Desventajas:** Difícil de rastrear el flujo completo del negocio; riesgo de dependencias cíclicas; la lógica de compensación está dispersa en múltiples servicios.
- **Riesgos:** "Spaghetti de eventos" donde es complejo entender por qué falló una transacción sin herramientas de trazado distribuido costosas.

### Opción 2: Saga Orquestada con Transactional Outbox (Seleccionada)
- **Descripción:** Un componente centralizador (Orquestador de Sagas) dentro del servicio de Pedidos gestiona el flujo de trabajo, enviando comandos a Inventario y recibiendo respuestas. Utiliza el patrón Transactional Outbox para la mensajería y una tabla de estado para la persistencia de la Saga.
- **Ventajas:** Centraliza la lógica de negocio y compensación; facilita la trazabilidad (ASR-02); permite gestionar estados complejos de forma clara.
- **Desventajas:** Introduce un acoplamiento lógico entre el orquestador y los servicios participantes; el orquestador puede convertirse en un cuello de botella si no se escala correctamente.
- **Riesgos:** Punto único de fallo lógico si el orquestador tiene un bug en la máquina de estados.

### Opción 3: Event Sourcing con Proyecciones
- **Descripción:** En lugar de estados, se almacena una secuencia inmutable de eventos. El inventario es una "proyección" calculada a partir de estos eventos.
- **Ventajas:** Trazabilidad absoluta y nativa; capacidad de "viajar en el tiempo" para auditorías forenses.
- **Desventajas:** Curva de aprendizaje muy alta; complejidad técnica extrema para manejar versiones de eventos; posible latencia en la consistencia de las proyecciones.
- **Riesgos:** El "overselling" (vender sin stock) aumenta debido al retraso (lag) inherente en la actualización de las vistas de lectura.

## Decisión y Justificación (Rationale)
Se ha seleccionado la **Opción 2: Saga Orquestada con Transactional Outbox**.

La decisión se fundamenta en los siguientes puntos alineados con **SWEBOK v4.0 (Cap. 02)**:
1.  **Control de Flujo y Visibilidad (ASR-02):** A diferencia de la coreografía, la orquestación permite que el estado de la transacción distribuida resida en un solo lugar. Esto facilita cumplir con el requerimiento de negocio de "compensaciones visibles", ya que el orquestador puede registrar explícitamente el paso de `RESERVANDO_STOCK` a `COMPENSANDO_PEDIDO`.
2.  **Garantía de Entrega y Atomicidad (ASR-01/ASR-03):** El uso del patrón **Transactional Outbox** asegura que el mensaje de comando nunca se pierda si la base de datos local del pedido confirma la transacción. Esto resuelve el problema de caídas post-confirmación.
3.  **Manejo de la Restricción R-03 (Idempotencia):** El orquestador asigna un `SagaID` único. El servicio de Inventario implementará un **Consumidor Idempotente** [SWEBOK-02-11] que verificará este ID antes de procesar, mitigando el riesgo de entregas duplicadas.
4.  **Simplicidad Operativa vs. Event Sourcing:** Se descarta la Opción 3 por su excesiva carga cognitiva, considerando que la Saga Orquestada resuelve los ASRs con un modelo de programación más tradicional y mantenible.

## Consecuencias

### Positivas
- **Consistencia Garantizada:** Se asegura que el inventario y el pedido lleguen a un estado coherente mediante transacciones compensatorias automáticas.
- **Auditoría Centralizada:** Es sencillo consultar el estado de cualquier pedido y entender en qué fase de la transacción distribuida se encuentra.
- **Resiliencia:** El sistema puede recuperarse de fallos parciales reintentando comandos pendientes desde el estado guardado por el orquestador.

### Negativas
- **Acoplamiento Funcional:** El servicio de Pedidos (u Orquestador) debe conocer la interfaz de comandos del servicio de Inventario.
- **Sobrecarga de Almacenamiento:** Se requiere espacio adicional para las tablas de `Outbox` y el log de estados de la Saga.

### Trade-offs y Riesgos Residuales
- **Trade-off Disponibilidad vs. Consistencia:** Se acepta la consistencia eventual (AP en Teorema CAP). Durante breves periodos, el stock podría no reflejar la realidad mientras la Saga termina su ejecución.
- **Riesgo de Latencia:** El proceso asíncrono es más lento que una transacción local. **Mitigación:** Implementar notificaciones push (WebSockets) al usuario final para informar cuando el proceso de reserva haya concluido.
- **Riesgo de "Zombies" en Outbox:** Si el relay de mensajes falla, los eventos se acumulan. **Mitigación:** Implementar monitoreo de profundidad de colas y alertas sobre el tamaño de la tabla Outbox.