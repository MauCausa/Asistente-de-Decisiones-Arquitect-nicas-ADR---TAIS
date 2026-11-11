# Registro de Decisión Arquitectónica (ADR)

## Título: Implementación de Cache Distribuida en Capas mediante Redis Administrado para el Catálogo de Productos de Alta Demanda

* **Estado:** Aprobado
* **Fecha:** 2023-10-24
* **Decisores:** Arquitecto de Software Principal, Líder Técnico de Backend, Ingeniero de Infraestructura / DevOps
* **Categoría:** Arquitectura de Datos / Rendimiento y Escalabilidad

---

## 1. Contexto y Problema

El catálogo de productos de la plataforma de comercio electrónico experimenta una carga asimétrica de tráfico, con una tasa de **12,000 lecturas por minuto (~200 RPS)** y un volumen bajo de escrituras (**menos de 200 actualizaciones por minuto**). 

Durante eventos promocionales, el tráfico de lectura se incrementa exponencialmente, provocando saturación de CPU en la base de datos relacional primaria. Esto resulta en tiempos de respuesta degradados que superan los **2 segundos**, afectando negativamente la experiencia del usuario y las tasas de conversión.

### Requisitos y Atributos de Calidad
* **Rendimiento de Lectura:** El tiempo de respuesta de extremo a extremo para las consultas del catálogo debe ser inferior a **300 ms** (p95).
* **Escalabilidad:** Capacidad para absorber picos de tráfico de lectura sin impactar el rendimiento de la base de datos subyacente.
* **Consistencia Controlada:** 
  * Los **precios** deben ser consistentes e integrales; no pueden permanecer obsoletos por más de **2 minutos (120 segundos)**.
  * Las **descripciones y atributos estáticos** admiten una consistencia eventualmente mayor (tolerancia a mayor latencia de actualización).

### Restricciones
* Debe utilizarse **Redis como servicio administrado** (AWS ElastiCache / Azure Cache for Redis / GCP Memorystore), el cual ya está disponible en la infraestructura de la empresa.
* Minimizar la reescritura masiva de la capa de datos existente.

---

## 2. Opciones Consideradas

### Opción 1: Escalado Vertical y Horizontal de la Base de Datos Relacional (Read Replicas)
Aumentar la capacidad del nodo principal de la base de datos e incorporar múltiples réplicas de lectura para distribuir la carga de las 12,000 lecturas/minuto.

* **Pros:**
  * No introduce componentes nuevos a la arquitectura.
  * Mantiene una semántica relacional directa.
* **Contras:**
  * Costo financiero elevado por cómputo y almacenamiento en la base de datos.
  * No resuelve completamente el tiempo de latencia a sub-300 ms bajo picos extremos de tráfico.
  * La replicación de base de datos aun puede sufrir de *lag* durante alta carga.

### Opción 2: Cache Distribuida usando Redis con Estrategia *Look-Aside* y TTLs Diferenciados por Atributo (Opción Seleccionada)
Implementar una capa de almacenamiento en caché en memoria intermedia entre los microservicios/APIs y la base de datos relacional usando el servicio administrado de Redis. 

* **Pros:**
  * Tiempos de respuesta en latencia de milisegundos (< 10 ms en capa de caché).
  * Reduce drásticamente la carga de CPU de la base de datos (offloading > 90%).
  * Permite definir políticas de expiración (TTL) y modelos de invalidación específicos según la naturaleza del dato (Precio vs. Descripción).
* **Contras:**
  * Incrementa la complejidad operativa al gestionar la consistencia eventual y la invalidación de caché.
  * Introduce un punto adicional de falla que debe ser mitigado con alta disponibilidad en Redis.

### Opción 3: Cache en Memoria Local dentro de la Aplicación (*In-Memory Local Cache*)
Utilizar librerías de caché en memoria dentro del propio proceso de las instancias de la aplicación (ej. Guava, Caffeine).

* **Pros:**
  * Latencia ultra baja (sin salto de red).
* **Contras:**
  * Dificultad para mantener la consistencia entre múltiples instancias distribuidas del servicio.
  * Riesgo de agotar la memoria del Heap de la aplicación (*Out of Memory*).
  * Incumplimiento estricto de la restricción de 2 minutos para precios entre nodos no sincronizados.

---

## 3. Decisión

Se decide adoptar la **Opción 2: Cache Distribuida utilizando Redis Administrado con el patrón Cache-Aside (Look-Aside) y TTLs Diferenciados**.

### Detalle de la Solución Arquitectónica

1. **Patrón de Lectura (Cache-Aside):**
   * La aplicación consulta primero a Redis por la clave del producto (`product:{id}`).
   * **Hit de Caché:** Retorna el objeto formateado directamente al cliente.
   * **Miss de Caché:** Lee de la base de datos primaria, escribe el resultado en Redis con su correspondiente TTL, y retorna la respuesta.

2. **Estructura de Datos y Separación de Entidades:**
   Para cumplir con la restricción de actualización de precios sin comprometer la velocidad de las descripciones, se dividirá la entidad del producto en el caché en dos estructuras Hash o JSON en Redis:
   * `product:{id}:static` -> Contiene descripciones, categorías, imágenes.
   * `product:{id}:pricing` -> Contiene precio, moneda, descuentos.

3. **Estrategia de Consistencia y Expiración (TTL):**
   * **Precios (`product:{id}:pricing`):** TTL estricto de **90 segundos** (garantizando un margen seguro por debajo del límite de 2 minutos / 120 segundos). Adicionalmente, se implementará un evento de invalidación por bus de mensajes (Pub/Sub o CDC) cuando ocurra una actualización explícita desde el panel de administración.
   * **Descripciones y Atributos (`product:{id}:static`):** TTL largo de **24 horas**, complementado con invalidación basada en eventos tras cada actualización.

4. **Configuración de Redis Administrado:**
   * Despliegue en modo **Cluster/Multi-AZ** con auto-failover habilitado para garantizar alta disponibilidad.
   * Política de Maxmemory eviction: `allkeys-lru` (Least Recently Used).

---

## 4. Consecuencias

### Positivas
* **Rendimiento Excelente:** Reducción del tiempo de respuesta promedio de lectura de >2000 ms a **menos de 50 ms** para peticiones cacheadas, superando con holgura la restricción de < 300 ms.
* **Reducción de Carga en BD:** La CPU de la base de datos disminuye drásticamente (se estima un porcentaje de aciertos de caché / *Cache Hit Ratio* > 92%), permitiendo soportar promociones sin degradación.
* **Cumplimiento de SLA de Negocio:** El TTL de 90 segundos asegura matemáticamente que ningún precio obsoleto permanezca visible por más de dos minutos.

### Negativas / Riesgos y Mitigaciones
* **Riesgo de Stampede Effect / Thundering Herd:** Si una oferta masiva expira, miles de peticiones concurrentes podrían ir a la BD simultáneamente.
  * *Mitigación:* Implementación de **Mutex Locks / Soft Leases** en el cliente de caché para que solo una petición regenere el caché mientras las demás esperan o reciben un valor stale por unos milisegundos.
* **Consistencia Eventual:** Durante hasta 90 segundos, un cliente podría ver un precio no actualizado si falla la invalidación por eventos.
  * *Mitigación:* Se valida y re-confirma el precio directamente contra la BD única y exclusivamente en el paso crítico de "Agregar al carrito" y "Checkout".

---

## 5. Validación y Métricas

La efectividad de esta decisión se evaluará mediante los siguientes indicadores clave (KPIs):

* **Tiempo de Respuesta (p95 / p99):** Monitoreado vía APM; debe ser $< 300\text{ ms}$ globalmente y $< 20\text{ ms}$ en la capa de Redis.
* **Cache Hit Ratio:** Debe mantenerse en un valor $\ge 90\%$.
* **Uso de CPU en Base de Datos:** No debe superar el $40\%$ de utilización durante eventos de alta demanda.
* **Freshness de Precios:** Monitoreo sintético para verificar que las actualizaciones de precios se reflejen en la capa de lectura en un tiempo $T < 120\text{ segundos}$.