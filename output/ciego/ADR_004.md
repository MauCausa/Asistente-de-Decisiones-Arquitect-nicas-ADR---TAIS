# CASO_02 - Aislamiento de datos en una plataforma SaaS multiempresa

## Estado
Aceptado

## Contexto y Problema
El proyecto consiste en el desarrollo de una plataforma de gestión comercial bajo el modelo Software as a Service (SaaS). El sistema iniciará operaciones prestando servicio a 80 empresas clientes (*tenants*), con una proyección de crecimiento escalable para alcanzar hasta 600 empresas en el mediano plazo. Los usuarios finales de estas empresas gestionan datos financieros altamente sensibles, por lo que el sistema debe garantizar la confidencialidad absoluta e impedir estrictamente cualquier fuga o visibilidad cruzada de información entre competidores o arrendatarios.

El problema arquitectónico principal radica en diseñar un modelo de persistencia y tenencia múltiple (*multi-tenancy*) que resuelva la tensión entre el aislamiento de datos estricto, la mantenibilidad a largo plazo de la base de datos y la eficiencia operacional. Esta decisión está fuertemente condicionada por tres restricciones innegociables:
1. El uso exclusivo de **PostgreSQL** como motor de base de datos relacional.
2. Un equipo de ingeniería reducido compuesto por solo **cuatro (4) desarrolladores**, lo que limita la capacidad operativa para gestionar infraestructuras complejas.
3. Un **presupuesto de infraestructura limitado**, que impide el sobreaprovisionamiento de recursos o el despliegue de múltiples nodos dedicados por cliente.

## Drivers de Decisión (ASRs)
*   **ASR-1: Aislamiento de Datos (Seguridad y Confidencialidad):** Garantizar de forma estricta que ningún arrendatario pueda acceder, visualizar o modificar información de otro arrendatario bajo ningún escenario (consultas erróneas, fallos en la capa de aplicación o accesos concurrentes), dado el carácter financiero y sensible de la información `[SWEBOK-02-04]`.
*   **ASR-2: Mantenibilidad del Esquema (Evolucionabilidad):** Asegurar que las migraciones DDL (*Data Definition Language*) y las actualizaciones del modelo de datos se puedan ejecutar de forma uniforme, rápida y segura tanto para los 80 clientes iniciales como para los 600 proyectados, minimizando la sobrecarga operativa y el riesgo de deslineamiento de esquemas (*schema drift*) `[SWEBOK-02-04]`.
*   **ASR-3: Eficiencia de Costos (Operatividad Económica):** Maximizar la densidad de *tenants* por unidad de infraestructura consumida (CPU, RAM, I/O), manteniendo los costos de operación reducidos y casi constantes a medida que el número de empresas escala `[SWEBOK-02-04]`.
*   **Restricción Técnica - Motor de BD:** Uso obligatorio del motor relacional PostgreSQL.
*   **Restricción Organizacional - Capacidad del Equipo:** Equipo pequeño de 4 desarrolladores, lo que prohíbe soluciones que requieran alta sobrecarga de mantenimiento u orquestación DevOps manual.
*   **Restricción Financiera - Presupuesto Limitado:** Infraestructura con presupuesto acotado, descartando soluciones de aislamiento físico por cliente.

## Opciones Consideradas

### Opción 1: Base de Datos y Esquema Compartidos con PostgreSQL Row-Level Security (RLS)
- **Descripción:** Todos los arrendatarios comparten la misma instancia de PostgreSQL, la misma base de datos y el mismo esquema lógico (`public`). Cada tabla del dominio transaccional incluye obligatoriamente una columna `tenant_id`. El aislamiento se delega al motor mediante la activación nativa de **Row-Level Security (RLS)** (`ALTER TABLE x ENABLE ROW LEVEL SECURITY`). Las solicitudes HTTP fijan el contexto de la sesión mediante `SET LOCAL app.current_tenant_id = 'uuid'`, y las políticas de RLS aplican un filtrado transparente en el motor (`USING (tenant_id = current_setting('app.current_tenant_id')::uuid)`).
- **Ventajas:** 
  * Máxima mantenibilidad del esquema (ASR-2): las migraciones DDL se ejecutan una sola vez para toda la plataforma.
  * Máxima eficiencia de costos (ASR-3): densidad óptima de *tenants* sin desperdicio de RAM o CPU.
  * Totalmente compatible con la capacidad del equipo de 4 desarrolladores y el presupuesto acotado.
- **Desventajas:** 
  * Requiere un acoplamiento disciplinado con la capa de aplicación/ORM para inicializar el contexto de la transacción (`SET LOCAL`).
  * Riesgo potencial del efecto "vecino ruidoso" (*noisy neighbor*) en el uso de recursos de la base de datos.
- **Riesgos:** 
  * Omisión del filtrado si la aplicación conecta con un rol de superusuario de PostgreSQL (ej. `postgres` o roles con atributo `BYPASSRLS`).
  * Invalidation de planes de ejecución en el query planner de PostgreSQL al modificar políticas de RLS bajo alta concurrencia.

### Opción 2: Esquema Lógico Separado por Arrendatario (Schema-per-Tenant)
- **Descripción:** Se utiliza una única instancia y base de datos PostgreSQL, pero se aprovisiona un esquema de base de datos (*namespace*) independiente por cada empresa (ej. `tenant_empresa001`). Al autenticarse el cliente, la aplicación ajusta el parámetro de conexión `SET search_path TO tenant_empresa001, public`. El esquema `public` se reserva únicamente para tablas globales del sistema.
- **Ventajas:** 
  * Aislamiento lógico fuerte respaldado por los namespaces de PostgreSQL (ASR-1). Las consultas SQL no requieren la columna discriminadora `tenant_id`.
  * Permite realizar respaldos y restauraciones independientes por cliente (`pg_dump -n tenant_x`).
- **Desventajas:** 
  * Degradación severa de la mantenibilidad del esquema (ASR-2): al alcanzar 600 clientes, una migración DDL debe ejecutarse 600 veces en bucle, aumentando exponencialmente la probabilidad de fallos a mitad de despliegue.
  * Degradación del catálogo del motor PostgreSQL (`pg_class`): la creación de decenas de miles de tablas satura la memoria del catálogo, ralentizando la planificación de consultas y los tiempos de autocompletado.
- **Riesgos:** 
  * Alta sobrecarga cognitiva y operativa para el equipo de 4 desarrolladores al gestionar fallos en migraciones y herramientas de *connection pooling* (PgBouncer) con constantes cambios de `search_path`.

### Opción 3: Enfoque Híbrido (Agrupamiento por Micro-Instancias / Shards Lógicos)
- **Descripción:** Se dividen los *tenants* en grupos distribuidos sobre 2 o más instancias/bases de datos de PostgreSQL (ej. `db_pool_1`, `db_pool_2`). Un componente de enrutamiento (*Tenant Router*) en la capa de aplicación intercepta las peticiones y redirige el tráfico a la instancia correspondiente según la empresa. Dentro de cada instancia se aplica RLS o esquemas separados.
- **Ventajas:** 
  * Aislamiento del dominio de falla (*blast-radius*): la caída o degradación de una instancia no afecta a los clientes alojados en las demás.
  * Escalabilidad horizontal progresiva que permite mover clientes de alto volumen a instancias dedicadas.
- **Desventajas:** 
  * Violación directa de la restricción de presupuesto (ASR-3): multiplica los costos fijos de infraestructura (nodos, almacenamiento provisionado, duplicación de réplicas de lectura).
  * Alta complejidad en el desarrollo de la aplicación para manejar el enrutamiento y la consolidación de datos analíticos.
- **Riesgos:** 
  * Inviabilidad de gestión operacional por parte del equipo de 4 desarrolladores debido a la sobrecarga de pipelines CI/CD y despliegues coordinados en múltiples instancias.

## Decisión y Justificación (Rationale)
Se decide adoptar la **Opción 1: Base de Datos y Esquema Compartidos con PostgreSQL Row-Level Security (RLS)** `[SWEBOK-02-04]`.

### Justificación por Tácticas SWEBOK v4.0 y ASRs:
1.  **Alineación estricta con ASR-1 (Aislamiento de Datos):** La responsabilidad de garantizar el aislamiento de datos no se confía a la capa de aplicación (escritura manual de `WHERE tenant_id = x` en cada consulta), sino que se delega a las políticas nativas del motor de PostgreSQL (`Row-Level Security`). PostgreSQL intercepta cualquier operación `SELECT`, `INSERT`, `UPDATE` y `DELETE` a nivel de Kernel de BD, aplicando de manera transparente la restricción `USING (tenant_id = current_setting('app.current_tenant_id'))`. Esto asegura que, incluso si un programador olvida filtrar una consulta en el código, el motor jamás retornará ni modificará registros pertenecientes a otro *tenant*.
2.  **Optimización de ASR-2 (Mantenibilidad del Esquema):** Al haber una sola instancia con un único esquema de tablas, los cambios en el modelo de datos se realizan ejecutando un único script DDL en el pipeline de despliegue. Esto erradica el problema del *schema drift* y la necesidad de orquestar 600 migraciones individuales en bucle, respetando la capacidad operativa del equipo.
3.  **Cumplimiento de ASR-3 (Eficiencia de Costos) y Restricciones:** La Opción 1 ofrece la mayor densidad de *tenants* por megabyte de memoria RAM y CPU consumidos. Elimina la sobrecarga del catálogo `pg_class` presente en la Opción 2 y la duplicación de costos fijos de infraestructura de la Opción 3. Permite procesar la carga proyectada de 80 a 600 empresas en un clúster PostgreSQL de tamaño reducido, garantizando la viabilidad financiera dentro del presupuesto limitado.
4.  **Ajuste a la Capacidad del Equipo (4 Desarrolladores):** Esta opción minimiza la sobrecarga en DevOps e infraestructura. El equipo se concentra exclusivamente en implementar el middleware de sesión en la aplicación y mantener el conjunto unificado de migraciones DDL.

### Supuestos Asumidos:
*   Se asume que todas las peticiones entrantes pueden ser autenticadas y asociadas a un `tenant_id` antes de abrir o tomar una conexión del pool de base de datos.
*   Se asume que las consultas financieras típicas del sistema se benefician de índices compuestos que incluyen a `tenant_id` como primer elemento de la llave.

## Consecuencias

### Positivas
*   **Despliegues Ágiles e Identicos:** Las migraciones de modelos de datos se completan en una única transacción DDL para los 600 clientes.
*   **Costo de Infraestructura Mínimo:** Maximización del retorno de inversión y consumo eficiente del presupuesto limitado.
*   **Aislamiento Nativo por BD:** Menor superficie de ataque por omisiones defensivas en el código fuente de la aplicación.
*   **Simplicidad en Monitoreo y Copias de Seguridad:** Procesos de *backup* y mantenibilidad simplificados al operar sobre una sola base de datos lógica.

### Negativas
*   **Riesgo de "Vecino Ruidoso" (Noisy Neighbor):** Las consultas de análisis masivo o transacciones pesadas de un *tenant* específico pueden impactar el rendimiento global del motor de base de datos compartido.
*   **Mayor Rigor en Conexiones:** La capa de software está obligada a envolver cada interacción con la base de datos invocando explícitamente `SET LOCAL app.current_tenant_id` dentro de una transacción.
*   **Restauración Individual Compleja:** Restaurar los datos a un punto en el tiempo (*PITR*) para un solo cliente requiere extraer lógicamente sus filas desde un ambiente de respaldo a la instancia de producción, a diferencia de restaurar un archivo `.dump` completo.

### Trade-offs y Riesgos Residuales

*   **Trade-off (Aislamiento Físico vs. Costo Operativo):** Se sacrifica el aislamiento físico estricto (como instancias o esquemas independientes) en favor de una alta eficiencia de costos y mantenibilidad DDL simplificada, compensando el riesgo de aislamiento mediante las políticas RLS del motor de base de datos.

*   **Riesgo Residual 1: Bypassing de RLS por superusuarios o conexiones mal configuradas.**
    *   *Mitigación:* Se prohíbe terminantemente que la aplicación conecte a PostgreSQL con el usuario `postgres` o roles con el atributo `BYPASSRLS`. Se creará un rol de aplicación no privilegiado (ej. `app_user`) que estará sujeto obligatoriamente a las reglas de RLS.

*   **Riesgo Residual 2: Degradación de rendimiento por vecinos ruidosos.**
    *   *Mitigación:* Se configurarán parámetros de *statement_timeout* estrictos en PostgreSQL para abortar consultas desmedidas. Adicionalmente, se establecerá un control de tasa (*Rate Limiting*) en el API Gateway por `tenant_id`.

*   **Riesgo Residual 3: Errores en la asignación del contexto del tenant en transacciones reutilizadas.**
    *   *Mitigación:* Implementación de un Middleware/Interceptor centralizado en el framework de la aplicación que ejecute automáticamente `SET LOCAL app.current_tenant_id` al abrir cualquier transacción, complementado con pruebas de integración continuas en el pipeline de CI/CD que validen el retorno de `0 rows` al intentar acceder cross-tenant.