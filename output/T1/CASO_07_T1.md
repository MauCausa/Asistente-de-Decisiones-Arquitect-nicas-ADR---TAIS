Este es el Registro de Decisión Arquitectónica (ADR) para la implementación de un sistema de auditoría inmutable en la aplicación clínica.

# ADR 007: Implementación de Registro de Auditoría Inmutable y Centralizado

## Estado
Propuesto

## Contexto
La aplicación clínica actual almacena los registros de acceso y modificación de historias médicas en la misma base de datos operacional que los datos clínicos. Esta configuración presenta los siguientes problemas:
1. **Falta de Integridad:** Los administradores del sistema tienen permisos para modificar o eliminar registros de auditoría.
2. **Riesgo de Cumplimiento:** No se garantiza la inmutabilidad requerida por las normativas de salud.
3. **Rendimiento:** Las búsquedas históricas de auditoría compiten por recursos con las transacciones clínicas diarias.
4. **Retención:** No existe un mecanismo eficiente para asegurar la retención mínima de cinco años sin degradar el rendimiento de la base de datos principal.

## Decisión
Se ha decidido desacoplar el registro de auditoría de la base de datos operacional y migrar a una arquitectura de **Almacenamiento de Logs Inmutable** utilizando una combinación de **Event Sourcing** (para la captura) y un **WORM (Write Once, Read Many) Storage**.

### Detalles de la implementación:
1.  **Desacoplamiento:** Los eventos de auditoría se enviarán de forma asíncrona a un servicio de auditoría independiente mediante un bus de mensajes.
2.  **Inmutabilidad:** Se utilizará un servicio de almacenamiento que soporte políticas de bloqueo de objetos (Object Lock) o una base de datos de solo lectura (Append-only) como Ledger Database (ej. AWS QLDB o Azure Confidential Ledger).
3.  **Estructura del Evento:** Los registros contendrán metadatos (ID de usuario, ID de paciente, timestamp, tipo de acción, IP) pero **no incluirán datos clínicos sensibles** (diagnósticos, notas médicas) para cumplir con el principio de minimización de datos.
4.  **Segregación de Funciones:** El acceso a estos registros estará restringido exclusivamente al equipo de auditoría mediante políticas de IAM (Identity and Access Management) estrictas, eliminando el acceso a los administradores de la aplicación.
5.  **Indexación:** Se implementará un motor de búsqueda (ej. Elasticsearch o índices en la base de datos de auditoría) optimizado por los campos: `PacienteID`, `UsuarioID` y `Fecha`.

## Atributos de Calidad

*   **Integridad de Auditoría:** Al usar almacenamiento WORM o Ledger, ninguna entidad (incluidos administradores) puede alterar los registros una vez escritos.
*   **Confidencialidad:** El acceso está restringido por roles específicos y los datos clínicos innecesarios se omiten del log.
*   **Trazabilidad:** Se garantiza una línea de tiempo completa y verificable de todas las interacciones con las historias médicas.

## Consecuencias

### Positivas:
*   Cumplimiento total con los requisitos de auditoría y retención legal de cinco años.
*   Mejora el rendimiento de la base de datos operacional al reducir su tamaño y carga de consultas.
*   Prueba de manipulación (Tamper-proof) verificable mediante firmas criptográficas.

### Negativas/Riesgos:
*   **Complejidad técnica:** Requiere la implementación de una infraestructura adicional y manejo de consistencia eventual.
*   **Costo:** El almacenamiento a largo plazo y las bases de datos especializadas (Ledger) pueden incrementar los costos operativos.
*   **Latencia:** Existe un pequeño desfase (milisegundos) entre la acción clínica y la disponibilidad del log para búsqueda debido a la asincronía.

## Restricciones y Retención
*   **Retención:** Se configurará una política de ciclo de vida de datos para el archivado automático después de 5 años y eliminación definitiva tras cumplir el periodo legal.
*   **Privacidad:** Se aplicará enmascaramiento de datos en la interfaz de consulta de auditoría para asegurar que solo el personal autorizado vea los identificadores completos.

## Consultas de Auditoría
El sistema permitirá las siguientes dimensiones de búsqueda de forma eficiente:
*   `Filtrar por PacienteID`: Para ver quién accedió a una historia específica.
*   `Filtrar por UsuarioID`: Para auditar el comportamiento de un profesional de salud.
*   `Rango de Fechas`: Para auditorías periódicas obligatorias.