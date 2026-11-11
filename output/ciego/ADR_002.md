# Registro de Decisión Arquitectónica (ADR)

## ADR-001: Adopción de Arquitectura Orientada a Eventos mediante Broker de Mensajería para Procesamiento de Pedidos

* **Estatus:** Aprobado
* **Fecha:** 2023-10-25
* **Autores:** Equipo de Arquitectura de Software
* **Contexto Técnico:** CASO_01 - Plataforma de Comercio Electrónico

---

### 1. Contexto y Planteamiento del Problema

La plataforma de comercio electrónico experimenta picos de carga de hasta 2,500 pedidos por minuto durante campañas de ventas. Actualmente, el **Servicio de Pedidos** utiliza un patrón de comunicación sincrónica (ej. REST/HTTP) invocando de manera directa a los servicios de **Inventario**, **Pagos** y **Notificaciones**.

Esta arquitectura acoplada genera los siguientes problemas críticos:
* **Fallas Cascada:** Si uno de los servicios secundarios (ej. Notificaciones o Pagos) experimenta latencia o indisponibilidad, la transacción completa del pedido se bloquea o falla.
* **Cuello de Botella en Escalabilidad:** El procesamiento sincrónico agota los recursos del servidor durante los picos de tráfico.
* **Falta de Trazabilidad:** No existe un registro inmutable centralizado de los eventos ocurridos para auditoría o reintentos en caso de fallas.

**Objetivo:** Rediseñar la comunicación entre servicios para garantizar alta disponibilidad, escalabilidad y tolerancia a fallas, asegurando la no pérdida de información bajo ninguna circunstancia.

---

### 2. Drivers de Decisión (Atributos de Calidad y Requisitos)

* **Escalabilidad ante picos de carga:** Capacidad de absorber 2,500+ pedidos/minuto sin degradar la recepción de órdenes.
* **Desacoplamiento temporal:** El Servicio de Pedidos debe confirmar la recepción al usuario sin depender de la disponibilidad inmediata de los servicios de Pagos, Inventario o Notificaciones.
* **Trazabilidad y reprocesamiento de eventos:** Registro histórico e inmutable de los estados del pedido para auditorías y replay de eventos.
* **Cero Pérdida de Datos (Durable Execution):** Garantía estricta de no perder ningún pedido confirmado.

---

### 3. Restricciones Térmicas y Operativas

* **Despliegue:** Todo componente de la solución debe ser containerizable y ejecutable en un entorno de **Docker / Kubernetes**.
* **Curva de Aprendizaje:** El equipo de desarrollo cuenta con **experiencia básica en mensajería**.
* **Garantía de Entrega:** Se requiere al menos persistencia en disco y acuse de recibo (*acknowledgment*) para evitar la pérdida de pedidos.

---

### 4. Opciones Evaluadas

#### Opción 1: Apache Kafka
* **Pros:** Excelente para *event streaming*, replay de eventos masivos, alto rendimiento.
* **Contras:** Alta complejidad de administración y configuración (Zookeeper/KRaft, particionamiento), curva de aprendizaje empinada para un equipo con experiencia básica.

#### Opción 2: RabbitMQ (Solución Seleccionada)
* **Pros:** Broker de mensajería maduro, fácil despliegue en Docker, amplio soporte para patrones de enrutamiento (*Exchanges*), soporte nativo para persistencia de mensajes y colas durables, curva de aprendizaje suave.
* **Contras:** Recompilar/reprocesar eventos históricos (Event Replay) requiere una estrategia adicional basada en persistencia en base de datos (ej. Patrón *Transactional Outbox* o almacenamiento de logs).

#### Opción 3: Base de Datos como Cola (ej. PostgreSQL + SKIP LOCKED)
* **Pros:** No añade nuevos componentes de infraestructura.
* **Contras:** Mala escalabilidad ante 2,500 req/min, alto impacto en la I/O de la base de datos principal, acoplamiento en la capa de datos.

---

### 5. Decisión Tomada

Se decide implementar una **Arquitectura Orientada a Eventos (EDA)** utilizando **RabbitMQ** desplegado en contenedores **Docker**, complementado con el patrón **Transactional Outbox** y **Dead Letter Exchanges (DLX)**.

#### Arquitectura de la Solución:

1. **Patrón Transactional Outbox (Servicio de Pedidos):**
   * Cuando entra un pedido, el Servicio de Pedidos guarda el pedido y el evento `PedidoCreado` en su propia base de datos relacional dentro de la misma transacción local ACID.
   * Un proceso en segundo plano (ej. Debezium o un poller ligero) lee la tabla *Outbox* y publica el evento en RabbitMQ. Esto garantiza que ningún pedido confirmado se pierda aunque el broker no esté disponible en el milisegundo exacto.

2. **Topología en RabbitMQ:**
   * **Exchange:** `pedidos.topic` (Tipo Topic).
   * **Colas Durables:**
     * `cola.inventario` (Suscrita a `pedido.creado`)
     * `cola.pagos` (Suscrita a `pedido.creado`)
     * `cola.notificaciones` (Suscrita a `pedido.procesado`, `pedido.fallido`, etc.)
   * **Persistencia:** Todos los mensajes se publican con `delivery_mode = 2` (persistente) y las colas se declaran como `durable = true`.

3. **Manejo de Fallas y Reprocesamiento:**
   * **DLX (Dead Letter Exchange):** Si un consumidor (ej. Pagos) falla al procesar un mensaje tras $N$ reintentos, el mensaje se redirige automáticamente a una cola `cola.pedidos.dlq` para su posterior inspección y reprocesamiento manual o automático.
   * **Almacenamiento de Auditoría:** Un servicio *Auditor/Logger* consume todos los eventos del bus y los persiste en una base de datos documental (ej. MongoDB o PostgreSQL) para consulta histórica y trazabilidad.

---

### 6. Conseguencias de la Decisión

#### Impacto Positivo (Beneficios)
* **Alta Disponibilidad:** Si el servicio de Notificaciones cae, el usuario sigue comprando. Los mensajes se acumulan en la cola y se procesan cuando el servicio se recupere.
* **Escalabilidad:** Se puede escalar horizontalmente el número de instancias de los consumidores (ej. más contenedores del Servicio de Pagos) durante las campañas.
* **Tolerancia a la Curva de Aprendizaje:** RabbitMQ posee una interfaz de administración sencilla y SDKs muy amigables para el equipo.
* **Cero Pérdida de Datos:** La combinación de mensajes persistentes en RabbitMQ, confirmación del consumidor (*Publisher Confirms* / *Manual ACKs*) y el patrón *Transactional Outbox* asegura que la información no se pierda.

#### Impacto Negativo y Mitigaciones (Riesgos)
* **Consistencia Eventual:** El usuario no sabrá de inmediato si el pago falló en la misma respuesta HTTP.
  * *Mitigación:* Implementar comunicación asíncrona hacia el cliente (WebSockets, Server-Sent Events o notificaciones Push/Email).
* **Reprocesamiento complejo vs Kafka:** RabbitMQ elimina el mensaje de la cola una vez consumido con éxito, dificultando el "replay" desde la cola.
  * *Mitigación:* Se almacena el registro histórico de los eventos en la base de datos a través del servicio de auditoría y la tabla *Outbox*.

---

### 7. Cumplimiento de Restricciones y Atributos

| Requisito / Restricción | Solución Aplicada |
| :--- | :--- |
| **2,500 pedidos/min** | Desacoplamiento asíncrono; el servicio de pedidos responde en milisegundos tras persistir el evento. |
| **No perder pedidos** | Patrón Outbox + Persistencia de mensajes en disco (RabbitMQ) + ACKs manuales. |
| **Despliegue Docker** | Imagen oficial de `rabbitmq:3-management-alpine` containerizada. |
| **Experiencia básica** | RabbitMQ requiere menor esfuerzo operacional que clústeres de streaming complejos. |
| **Trazabilidad** | Eventos versionados, consumo por servicio de auditoría y manejo de colas DLQ. |