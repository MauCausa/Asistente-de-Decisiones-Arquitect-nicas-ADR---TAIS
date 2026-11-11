# ADR 002: Estrategia de Aislamiento de Datos en Base de Datos PostgreSQL para Plataforma SaaS Multiempresa

* **Estado:** Aceptado  
* **Fecha:** 24 de mayo de 2024  
* **Autores:** Equipo de Arquitectura de Software  
* **Caso:** CASO_02 - Aislamiento de datos en una plataforma SaaS multiempresa  

---

## 1. Contexto y Problema

Estamos construyendo un sistema SaaS de gestión comercial que atenderá inicialmente a 80 empresas cliente (tenants), con una proyección de crecimiento de hasta 600 empresas a mediano plazo. Los clientes manejan información financiera altamente sensible y exigen garantías estrictas de que sus datos estén completamente aislados de los demás arrendatarios.

El desafío arquitectónico consiste en seleccionar un patrón de tenencia de datos en PostgreSQL que cumpla con las siguientes condiciones y restricciones:

* **Atributos de Calidad Prioritarios:** Aislamiento de datos (seguridad), Mantenibilidad del esquema (facilidad de evolución/despliegues) y Eficiencia de costos (optimización de recursos infraestructurales).
* **Restricciones del Proyecto:** 
  * Motor de base de datos obligatorio: **PostgreSQL**.
  * Tamaño del equipo: **4 desarrolladores** (capacidad operativa reducida para mantenimiento de infraestructura).
  * **Presupuesto limitado** para infraestructura cloud.

## 2. Opciones Consideradas

Evaluamos tres modelos principales de diseño de base de datos multi-tenant sobre PostgreSQL:

1. **Opción 1: Base de datos independiente por Tenant (Silo / Isolated Database)**
   * *Descripción:* Cada empresa tiene su propia instancia o base de datos PostgreSQL física/lógica separada.
2. **Opción 2: Esquema PostgreSQL por Tenant (Multi-Schema / Separate Schemas)**
   * *Descripción:* Una única base de datos donde cada cliente tiene un `schema` de PostgreSQL dedicado (`tenant_a.orders`, `tenant_b.orders`).
3. **Opción 3: Base de datos compartida con discriminador de Tenant y Row-Level Security (RLS) (Pooled / Shared Schema + RLS)**
   * *Descripción:* Todos los tenants comparten las mismas tablas y esquemas (`public.orders`). Se añade una columna `tenant_id` en cada tabla y se aplica *Row-Level Security* (RLS) nativo de PostgreSQL para forzar el aislamiento a nivel de motor.

## 3. Decisión

Decidimos adoptar la **Opción 3: Base de datos compartida con discriminador de Tenant y Row-Level Security (RLS)** como estrategia principal para el aislamiento de datos.

### Razón de la elección
La Opción 3 ofrece el equilibrio perfecto entre las restricciones financieras y operativas del proyecto, sin sacrificar la seguridad:
* **Costos e Infraestructura:** Permite iniciar con un clúster pequeño de PostgreSQL (ej. AWS RDS o GCP Cloud SQL) y escalar vertical o horizontalmente según la carga real, maximizando la densidad de usuarios y minimizando el desperdicio de recursos (ideal para presupuesto limitado).
* **Mantenibilidad:** Ejecutar migraciones de esquema (ej. con Flyway o Liquibase) requiere alterar una sola instancia/esquema. Esto es crítico para un equipo de solo 4 desarrolladores que no pueden asumir la sobrecarga operativa de ejecutar y monitorear migraciones en 80 (y luego 600) bases de datos o esquemas independientes.
* **Aislamiento Robusto vía RLS:** PostgreSQL implementa Row-Level Security directamente en el motor de datos. Al definir políticas RLS vinculadas a la variable de sesión de la conexión (`SET LOCAL app.current_tenant_id = '...'`), se garantiza que, incluso si un desarrollador olvida un filtro `WHERE tenant_id = ...` en el código de la aplicación, el motor de la base de datos no retornará información de otros clientes.

## 4. Evaluacion de Opciones y Trade-offs

| Criterio | Opción 1: Base de datos por Tenant | Opción 2: Esquema por Tenant | Opción 3: Tabla Compartida + RLS (Elegida) |
| :--- | :--- | :--- | :--- |
| **Aislamiento de Datos** | **Excelente** (Físico/Lógico total) | **Alto** (Aislamiento de namespace) | **Alto** (Lógico garantizado por RLS a nivel de motor) |
| **Eficiencia de Costos** | **Muy Baja** (Alto consumo idle por instancia) | **Media** (Límites de conexión y memoria por esquema) | **Excelente** (Uso óptimo de CPU/RAM compartida) |
| **Mantenibilidad del Esquema** | **Muy Compleja** (600 migraciones independientes) | **Compleja** (600 esquemas que actualizar en cada release) | **Sencilla** (1 sola migración global de BD) |
| **Sobrecarga para el Equipo (4 devs)** | **Inviable** | **Alta** | **Baja / Manejable** |

### Por qué se descartaron las otras opciones:

* **Descarte de Opción 1 (BD por Tenant):** Aunque ofrece el aislamiento más estricto, el costo de mantener 80 a 600 bases de datos activas excede el presupuesto. Adicionalmente, la sobrecarga operativa para el equipo de 4 desarrolladores al desplegar actualizaciones de esquema en 600 bases de datos sería insostenible.
* **Descarte de Opción 2 (Esquema por Tenant):** Aunque parece un punto medio, PostgreSQL no escala eficientemente cuando el número de esquemas y tablas crece exponencialmente (600 tenants * 50 tablas = 30,000 tablas en el catálogo de PostgreSQL). Esto degrada el rendimiento de la memoria cache (`shared_buffers`), complica herramientas de respaldo y sigue requiriendo ejecutar scripts DDL 600 veces por cada despliegue.

## 5. Consecuencias y Mitigaciones

### Positivas
* **Bajo costo operativo y de infraestructura:** Maximiza el rendimiento del hardware invertido.
* **Facilidad de despliegue:** Las migraciones de software se aplican una sola vez por entorno (Desarrollo, Staging, Producción).
* **Seguridad declarativa:** Las políticas RLS centralizan la lógica de aislamiento fuera de la capa de aplicación.

### Negativas / Riesgos
* **Efecto "Vecino Ruidoso" (Noisy Neighbor):** Un tenant con un volumen masivo de transacciones o consultas complejas podría impactar el rendimiento de los demás.
* **Riesgo de error de configuración en RLS:** Si RLS no se habilita explícitamente en una nueva tabla (`ALTER TABLE tbl ENABLE ROW LEVEL SECURITY`), los datos podrían quedar expuestos.
* **Dificultad para copias de seguridad/restauraciones individuales:** Restaurar los datos de un único cliente a un punto específico en el tiempo es más complejo que en un modelo de base de datos dedicada.

### Plan de Mitigación
1. **Prevención de Vecino Ruidoso:** Implementar límites de tasa (*rate limiting*) en la capa de API Gateway por `tenant_id` y aislamiento de consultas pesadas mediante réplicas de lectura si es necesario.
2. **Automatización de RLS:** Integrar pruebas automatizadas en el pipeline de CI/CD que verifiquen que **todas** las tablas creadas tengan habilitado RLS y posean sus correspondientes políticas activas antes de pasar a producción.
3. **Restauración y Exportación de Datos:** Implementar scripts automatizados de exportación/importación a nivel de aplicación (JSON/CSV sanitizado) para atender solicitudes específicas de extracción o respaldo por cliente.
4. **Patrón de Conexión Seguro:** Utilizar un *Connection Pooler* (como PgBouncer) configurado para asegurar que la variable `app.current_tenant_id` se limpie o reasigne correctamente en cada transacción o conexión devuelta al pool.