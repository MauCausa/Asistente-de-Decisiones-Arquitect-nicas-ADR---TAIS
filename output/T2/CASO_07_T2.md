# CASO_07 - Registro de auditoria inmutable para una aplicacion clinica

## Estado
Aceptado

## Contexto y Problema
La aplicación clínica actual gestiona datos de salud altamente sensibles donde la integridad de las historias médicas es crítica. El sistema de auditoría vigente almacena los registros de acceso y modificación en la misma base de datos operacional. Esta configuración presenta una vulnerabilidad crítica: los administradores de la base de datos o de la aplicación poseen privilegios que les permitirían alterar o eliminar evidencias de accesos no autorizados o malas praxis. 

El problema arquitectónico radica en la falta de segregación de funciones y la ausencia de mecanismos de inmutabilidad. Se requiere una solución que garantice que ningún actor (interno o externo) pueda modificar los registros, que soporte una retención de al menos cinco años y que permita búsquedas forenses eficientes por paciente, usuario y fecha, todo esto sin comprometer la confidencialidad de los datos clínicos.

## Drivers de Decisión (ASRs)
*   **ASR-01: Integridad de Auditoría (Crítico):** Garantizar la inmutabilidad de los registros (WORM - Write Once, Read Many) para evitar manipulaciones.
*   **ASR-02: Confidencialidad (Alto):** Restringir el acceso a los logs exclusivamente al equipo de auditoría y asegurar que no se filtren datos clínicos innecesarios (Minimización).
*   **ASR-03: Trazabilidad (Medio-Alto):** Capacidad de realizar búsquedas granulares y reconstruir eventos históricos de forma eficiente.
*   **Restricción de Retención:** Almacenamiento obligatorio por un periodo mínimo de 5 años.
*   **Restricción de Segregación:** Los administradores de TI/App no deben tener control sobre la persistencia de la auditoría.

## Opciones Consideradas

### Opción 1: Almacenamiento de Objetos con Bloqueo (WORM Cloud-Native)
- **Descripción:** Extracción de logs mediante el patrón *Transactional Outbox* hacia un bucket de almacenamiento de objetos (S3/Blob Storage) con política de "Object Lock" en modo cumplimiento (Compliance Mode).
- **Ventajas:** Máxima protección contra borrado físico incluso para usuarios raíz; bajo costo de retención a largo plazo (capas Archive).
- **Desventajas:** Las búsquedas requieren herramientas adicionales de consulta sobre archivos (ej. SQL sobre archivos planos), lo que aumenta la latencia de respuesta inicial.
- **Riesgos:** Complejidad en la gestión de esquemas de datos a lo largo de los 5 años (evolución del formato de log).

### Opción 2: Ledger Database Centralizada (SQL Ledger)
- **Descripción:** Uso de una base de datos especializada en libros mayores que utiliza encadenamiento criptográfico interno para validar la integridad de cada transacción.
- **Ventajas:** Facilidad de consulta mediante SQL estándar y pruebas matemáticas de integridad integradas en el motor.
- **Desventajas:** Alto costo por transacción y dependencia total de un proveedor específico (Vendor Lock-in).
- **Riesgos:** Escalabilidad financiera impredecible si el volumen de eventos clínicos crece exponencialmente.

### Opción 3: Sidecar de Auditoría con Hashing Chain Local
- **Descripción:** Implementación de una base de datos relacional dedicada donde cada registro contiene el hash del anterior, gestionado por la lógica de la aplicación.
- **Ventajas:** No requiere infraestructura nueva compleja y es altamente personalizable.
- **Desventajas:** No previene el borrado físico de la base de datos por parte de un administrador con privilegios de sistema; solo detecta la alteración pero no la impide.
- **Riesgos:** "Falsa sensación de seguridad" ante ataques de borrado total de tablas.

## Decisión y Justificación (Rationale)
Se ha seleccionado la **Opción 1: Almacenamiento de Objetos con Bloqueo (WORM Cloud-Native)**, complementada con el patrón **Transactional Outbox**.

**Justificación técnica basada en SWEBOK v4.0:**
1.  **Integridad (ASR-01):** Se aplica la táctica de *Immutable Audit Logs* [SWEBOK-02-09]. Al usar **Object Lock**, se garantiza la inmutabilidad a nivel de hardware/infraestructura, superando la protección lógica de las opciones 2 y 3.
2.  **Consistencia (Patrón Outbox):** Para evitar la pérdida de logs durante fallos de red, se implementa una tabla *Outbox* en la DB clínica. Esto asegura que el registro clínico y el evento de auditoría se confirmen atómicamente antes de ser exportados.
3.  **Segregación y Confidencialidad (ASR-02):** El almacenamiento de objetos permite políticas de IAM (Identity and Access Management) totalmente aisladas de la aplicación, cumpliendo con la restricción de acceso exclusivo al equipo de auditoría.
4.  **Eficiencia de Costos y Retención:** El almacenamiento de objetos es la única opción que permite mover datos a capas de "archivo frío" automáticamente después de un periodo, cumpliendo la restricción de 5 años con el menor TCO (Total Cost of Ownership).
5.  **Trazabilidad (ASR-03):** Se utilizará un motor de consultas serverless (como Amazon Athena o Azure Synapse) para indexar los archivos Parquet resultantes, permitiendo búsquedas por paciente y fecha sin mantener una base de datos costosa encendida 24/7.

## Consecuencias

### Positivas
- Cumplimiento normativo estricto de inmutabilidad (imposibilidad física de borrado antes de 5 años).
- Reducción de la carga en la base de datos operacional al externalizar los logs.
- Alta durabilidad de los datos (99.999999999% típica de proveedores cloud).

### Negativas
- Mayor complejidad en el despliegue inicial (configuración de pipelines de datos y políticas de bloqueo).
- Las consultas de auditoría no son instantáneas (latencia de segundos/minutos dependiendo del volumen).

### Trade-offs y Riesgos Residuales
- **Trade-off Rendimiento vs. Integridad:** Se acepta una ligera latencia adicional en las transacciones clínicas debido al patrón *Outbox* para garantizar que ningún evento se pierda.
- **Riesgo Residual (Evolución de Esquema):** Si el formato de los logs cambia en el año 3, las consultas sobre logs del año 1 podrían fallar. 
- **Mitigación:** Se implementará un registro de esquemas (Schema Registry) y se utilizará el formato **Apache Parquet** para asegurar la compatibilidad hacia atrás y la eficiencia en las búsquedas.