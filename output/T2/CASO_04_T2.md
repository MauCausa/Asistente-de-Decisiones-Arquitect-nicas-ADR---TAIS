# CASO_04 - Cache distribuida para un catalogo de productos de alta demanda

## Estado
Aceptado (Propuesto y validado mediante asistencia híbrida SWEBOK v4.0 + evaluación de trade-offs)

## Contexto y Problema
El sistema de catálogo de productos de la tienda electrónica enfrenta una carga operativa de alta asimetría, caracterizada por aproximadamente 12,000 lecturas por minuto (~200 RPS) frente a menos de 200 actualizaciones por minuto (~3.33 WPS). Durante eventos de promociones masivas, el tráfico de lectura se incrementa exponencialmente, saturando la capacidad de procesamiento (CPU) de la base de datos relacional principal. Esta saturación degrada gravemente la experiencia del usuario, registrando tiempos de respuesta end-to-end superiores a 2,000 ms.

El problema arquitectónico radica en el acoplamiento directo del flujo masivo de lectura a la capa de persistencia relacional en disco, la cual no está optimizada para servir alta concurrencia de consultas repetitivas de solo lectura. Se requiere introducir una capa de caché distribuida que desacople las lecturas de la base de datos, garantizando tiempos de respuesta ultrarrápidos y protegiendo el almacenamiento primario. 

Dentro de las restricciones operativas e infraestructura impuestas, se cuenta con **Redis como Servicio Administrado**, se exige un tiempo objetivo de respuesta menor a 300 ms (SLA) y se impone un límite estricto de obsolescencia de datos: los precios modificados deben verse reflejados en un máximo de dos minutos (120 segundos), mientras que la información descriptiva soporta una consistencia eventual más relajada.

## Drivers de Decisión (ASRs)
- **ASR-01: Rendimiento de Lectura (Latencia y Throughput):** Garantizar un tiempo de respuesta end-to-end de la API de catálogo menor a 300 ms (p99) bajo una carga nominal de 12,000 RPM y picos de tráfico durante eventos promocionales.
- **ASR-02: Escalabilidad de la Capa de Lectura:** Capacidad de absorber incrementos en el volumen de consultas sin saturar el consumo de CPU ni agotar el *pool* de conexiones de la base de datos relacional subyacente.
- **ASR-03: Consistencia Controlada y Divergente por Dominio (Bounded Eventual Consistency):** Garantizar que las actualizaciones de precios no permanezcan obsoletas en la caché por más de 2 minutos (120 segundos), admitiendo ventanas de inconsistencia eventual más amplias para atributos no críticos como descripciones e imágenes.
- **Restricción 01 (Infraestructura):** Uso obligatorio de Redis Administrado como motor de almacenamiento en memoria para la capa de caché.
- **Restricción 02 (Límite de Obsolescencia Comercial):** Cero tolerancia a precios obsoletos más allá de los 120 segundos tras su modificación en el sistema de origen.

## Opciones Consideradas

### Opción 1: Cache-Aside Pasivo con TTLs Asimétricos y Jitter
- **Descripción:** La aplicación consulta a Redis Administrado antes de acudir a la BD. En caso de *Cache Miss*, lee de la base de datos y almacena el resultado en Redis. Se guarda el objeto del producto dividiendo los atributos en claves independientes: el precio se almacena con un TTL corto de 90 segundos más un *jitter* aleatorio de $\pm 15$ segundos (rango 75-105 segundos), y la descripción con un TTL largo de 24 horas. Las escrituras modifican únicamente la BD relacional y no emiten ningún evento de invalidación a la caché, confiando el refresco de datos $100\%$ a la expiración pasiva por TTL.
- **Ventajas:**
  - Desacoplamiento total entre los servicios de escritura y la capa de caché.
  - Implementación simple que no requiere infraestructura de mensajería ni lógica de eventos.
  - Alta latencia de lectura ($< 15\text{ ms}$) al servir la gran mayoría de peticiones desde memoria.
- **Desventajas:**
  - Los cambios de precios tardan sistemáticamente hasta 105 segundos en reflejarse, operando al borde de la restricción de 2 minutos.
  - Genera múltiples llamadas I/O (*MGET* o varias consultas) a Redis si las entidades se fragmentan para manejar TTLs independientes.
  - Riesgo residual de *Cache Stampede* si expira el TTL de un producto altamente demandado durante una promoción.
- **Riesgos:**
  - Picos repentinos de CPU en la BD relacional si múltiples peticiones concurrentes experimentan un *Cache Miss* simultáneo al vencer el TTL del precio de un producto estrella.

### Opción 2: Cache-Aside Activo con Invalidación Basada en Eventos y TTL de Resguardo (Seleccionada)
- **Descripción:** La lectura sigue el patrón *Cache-Aside* leyendo un documento JSON consolidado por producto desde Redis. Al momento de ejecutarse una actualización ($<200\text{ WPM}$), el servicio de escritura modifica la BD relacional y publica inmediatamente una señal de invalidación/actualización hacia Redis (vía Redis Pub/Sub o llamada directa del servicio) para eliminar o sobrescribir la clave afectada. Como mecanismo de defensa en profundidad, la clave se guarda con un TTL pasivo de resguardo de 120 segundos para el objeto consolidado (o con expiración acotada para el bloque de precio).
- **Ventajas:**
  - **Consistencia casi en tiempo real:** La obsolescencia del precio se reduce a milisegundos tras la confirmación de la escritura en la BD, superando holgadamente la restricción de 2 minutos.
  - **Lectura optimizada:** Permite recuperar la información completa del producto en una sola operación `GET` de Redis con latencias $< 10\text{ ms}$.
  - **Eficiencia de recursos:** Mantiene un excelente balance entre rendimiento de lectura y protección de la base de datos.
- **Desventajas:**
  - Requiere lógica adicional en los servicios de escritura para coordinar la invalidación en Redis.
  - Mayor acoplamiento operacional entre la capa de actualización y la disponibilidad de Redis.
- **Riesgos:**
  - Si la señal de invalidación activa falla (ej. caída momentánea de red o pérdida de mensaje Pub/Sub), el sistema depende exclusivamente del TTL de resguardo, permitiendo una ventana de obsolescencia de hasta 2 minutos (la cual sigue estando dentro del límite permitido).

### Opción 3: Read-Through / Write-Through Híbrido con Redis Hash y Locking Distribuido
- **Descripción:** Se implementa una capa de abstracción donde la aplicación interactúa únicamente con la caché. Las lecturas (*Read-Through*) y escrituras (*Write-Through*) son gestionadas por un middleware que sincroniza síncronamente Redis (usando estructuras `HASH`) y la BD. Para evitar que la expiración de la caché golpee la BD, la regeneración del dato ante un *miss* requiere la adquisición de un bloqueo distribuido en Redis (utilizando `SETNX` o *Redlock*), forzando a que solo un hilo consulte la BD mientras los demás esperan.
- **Ventajas:**
  - Elimina por completo la posibilidad de un *Cache Stampede* sobre la base de datos.
  - Permite la modificación granular de campos específicos (`HSET product:id price value`) sin reescribir toda la entidad.
- **Desventajas:**
  - Incrementa la latencia en el flujo de escritura ($<200\text{ WPM}$) debido al acoplamiento síncrono BD + Redis.
  - Agrega una alta complejidad de implementación y sobrecarga operacional para un volumen de escrituras tan bajo.
  - Riesgo de cuellos de botella e incremento de latencia de lectura si el hilo que sostiene el *lock* tarda en responder.
- **Riesgos:**
  - Sobrediseño (*Over-engineering*) severo. Riesgo de bloqueos colgados (*deadlocks*) o agotamiento de hilos por fallos en la liberación de candados distribuidos.

## Decisión y Justificación (Rationale)
Se selecciona la **Opción 2: Cache-Aside Activo con Invalidación Basada en Eventos y TTL de Resguardo**.

### Justificación Técnica y Tácticas SWEBOK v4.0 Aplicadas:
1. **Atención al Rendimiento y Latencia (ASR-01):** Siguiendo los principios de *Distributed Caching* [SWEBOK-02-06], el patrón *Cache-Aside* permite responder el $98\%$ de las $12,000\text{ RPM}$ directamente desde la memoria RAM de Redis Administrado. Servir la entidad en un único valor consolidado en formato JSON reduce el tiempo de red a una sola operación I/O (`GET product:{id}`), logrando latencias de respuesta end-to-end de 10-20 ms, situándose muy por debajo del objetivo de $300\text{ ms}$.
2. **Escalabilidad y Protección de Persistencia (ASR-02):** La tasa de escrituras es extremadamente baja ($<200\text{ WPM} \approx 3.33\text{ WPS}$) en comparación con la lectura ($200\text{ RPS}$). Absorber el $100\%$ de la carga de lectura repetitiva mediante la caché descarga la CPU de la base de datos relacional a niveles mínimos, permitiendo que esta absorba holgadamente los picos de promociones sin degradación de recursos [SWEBOK-02-01].
3. **Cumplimiento Estricto de Consistencia Acotada (ASR-03 y Restricción 02):** La táctica de *Event-Driven Invalidation* genera una actualización/invalidación en Redis inmediatamente después de que un precio es actualizado en la BD relacional. Esto reduce la latencia de consistencia de los precios de **minutos a milisegundos**. 
4. **Mecanismo de Resiliencia y Defensa en Profundidad:** Al configurar un **TTL pasivo de resguardo de 120 segundos (2 minutos)** en Redis, se garantiza que, si el mecanismo de invalidación activa por eventos llega a fallar (por pérdida de conectividad o fallo del hilo ejecutor), la ventana de obsolescencia de los precios jamás superará el máximo de 2 minutos exigido por la restricción del negocio.

### Supuestos Asumidos:
- Se asume que el servicio que ejecuta la actualización del producto puede invocar una orden de invalidación/actualización en Redis dentro de la misma transacción de aplicación o mediante un patrón de publicación de eventos tras la confirmación de la BD (*commit*).
- Se asume que el tamaño de cada objeto de catálogo JSON es moderado ($<10\text{ KB}$), por lo que la transferencia y deserialización no representan un cuello de botella para la memoria de Redis ni para la red.

## Consecuencias

### Positivas
- **Latencia Ultrabaja:** Tiempos de respuesta de lectura en el rango de 5 ms a 20 ms (p99), superando holgadamente la meta de $<300\text{ ms}$.
- **Protección de la BD:** La base de datos relacional reduce el uso de CPU en más de un $90\%$ durante promociones, procesando casi exclusivamente escrituras y eventuales *Cache Misses*.
- **Frescura de Datos Críticos:** Los precios se reflejan en la interfaz de usuario de forma casi instantánea tras ser modificados en el sistema de origen.
- **Aprovechamiento Operativo:** Uso optimizado de **Redis Administrado**, eliminando mantenimiento infraestructural complejo.

### Negativas
- **Lógica Adicional en Escritura:** El código de dominio de la aplicación debe incorporar el manejo explícito de la invalidación de caché tras una escritura exitosa.
- **Riesgo Marginal de Consistencia Dual:** Si la base de datos confirma el *commit* pero Redis no está accesible para procesar la invalidación, existirá una inconsistencia temporal hasta que actúe el TTL de resguardo.

### Trade-offs y Riesgos Residuales
- **Trade-off Aceptado (Simplicidad vs. Garantía de Entrega de Eventos):** Se acepta el uso de un mecanismo de invalidación simple (llamada post-commit o Pub/Sub) en lugar de un complejo bus de eventos distribuido con entrega *exactly-once*. Se prioriza la simplicidad de la arquitectura aprovechando que la baja tasa de escrituras ($3.33\text{ WPS}$) reduce el riesgo de colisiones.
- **Riesgo Residual 1: Cache Stampede durante Promociones.**
  - *Descripción:* Expiración simultánea del TTL de resguardo para un producto estrella en pleno pico de ventas.
  - *Mitigación:* Se implementará un valor de **Jitter aleatorio ($\pm 10$ segundos)** en el TTL de resguardo de 120 segundos en Redis, previniendo que múltiples claves expiren sincronizadamente.
- **Riesgo Residual 2: Fallo de Conexión con Redis Administrado.**
  - *Descripción:* Caída temporal de la instancia de caché administrada.
  - *Mitigación:* Implementar un patrón *Circuit Breaker* y degradación elegante (*Graceful Degradation*) en el backend para degradar temporalmente a lecturas controladas en la BD relacional con límites de tasa (*Rate Limiting*), protegiendo la base de datos contra caídas en cascada.