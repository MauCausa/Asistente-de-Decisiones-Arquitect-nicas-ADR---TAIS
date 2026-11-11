# CASO_06 - Estrategia de modularización para un producto con equipo pequeño

## Estado
Aceptado

## Contexto y Problema
Una empresa está iniciando el desarrollo de un sistema de reservas con un equipo reducido de seis desarrolladores y un plazo estricto de cuatro meses para el lanzamiento. El sistema enfrenta la incertidumbre de un crecimiento futuro, pero con la certeza de que las reglas de negocio (políticas de cancelación, tarifas dinámicas, disponibilidad) cambiarán frecuentemente. El volumen inicial de transacciones será moderado, lo que no justifica una infraestructura de alta escala inmediata. El problema arquitectónico radica en elegir una estructura que permita la entrega rápida sin crear un "Monolito de Espagueti" que impida la evolución, pero evitando la complejidad operativa de los microservicios, dado que la capacidad DevOps es limitada.

## Drivers de Decisión (ASRs)
*   **Velocidad de Entrega (Time-to-Market):** Necesidad de producir un sistema funcional en 120 días.
*   **Mantenibilidad (Modificabilidad):** Capacidad de alterar reglas comerciales frecuentes con un impacto mínimo en otros componentes.
*   **Evolución Gradual:** La arquitectura debe permitir la transición hacia sistemas distribuidos si la demanda crece, sin requerir una reescritura total.
*   **Restricción de Equipo:** Un solo equipo de 6 personas (Ley de Conway), lo que favorece la comunicación directa y una base de código compartida.
*   **Restricción de Infraestructura:** Capacidad DevOps limitada que impide gestionar múltiples unidades de despliegue y orquestación compleja.

## Opciones Consideradas

### Opción 1: Monolito Modular (Seleccionada)
- **Descripción:** Organización del código en una única unidad de despliegue, pero dividida internamente en módulos lógicos estrictos basados en *Bounded Contexts*. Cada módulo encapsula su propia lógica y datos, comunicándose a través de interfaces/APIs internas.
- **Ventajas:** Despliegue simplificado (un solo artefacto), transacciones ACID directas, y facilidad de refactorización mediante herramientas del IDE.
- **Desventajas:** Requiere disciplina estricta para no romper los límites de los módulos; un fallo crítico en un módulo puede derribar toda la aplicación.
- **Riesgos:** Riesgo de erosión arquitectónica si no se automatizan las pruebas de dependencia entre módulos.

### Opción 2: Microservicios desde el inicio
- **Descripción:** Descomposición física del sistema en servicios independientes (Reservas, Pagos, Usuarios) con bases de datos propias y comunicación vía red (REST/gRPC).
- **Ventajas:** Aislamiento total de fallos y escalabilidad independiente por componente.
- **Desventajas:** Alta sobrecarga operativa (latencia, serialización, gestión de múltiples pipelines) y complejidad en la consistencia de datos (Sagas).
- **Riesgos:** Incumplimiento del plazo de 4 meses debido a la "parálisis por infraestructura" y sobrecarga cognitiva del equipo.

### Opción 3: Arquitectura de Micro-Kernel (Plug-ins)
- **Descripción:** Un núcleo central que gestiona el flujo de reservas y un sistema de complementos para las reglas de negocio variables.
- **Ventajas:** Excelente para gestionar la variabilidad de reglas comerciales sin modificar el código base.
- **Desventajas:** Diseño inicial del "Core" muy complejo y propenso a volverse un cuello de botella si las reglas requieren cambios en la estructura de datos base.
- **Riesgos:** Rigidez si el núcleo no anticipa correctamente los puntos de extensión necesarios.

## Decisión y Justificación (Rationale)
Se ha seleccionado la **Opción 1: Monolito Modular**. 

La decisión se fundamenta en los principios del **SWEBOK v4.0 (Capítulo 02)** sobre la gestión de la complejidad y los atributos de calidad:
1.  **Alineación con la Capacidad del Equipo (Ley de Conway):** Con 6 desarrolladores, la coordinación en un solo repositorio y unidad de despliegue es más eficiente que gestionar la comunicación inter-servicio de los microservicios.
2.  **Optimización del Time-to-Market:** Al eliminar la necesidad de una malla de servicios (Service Mesh), trazabilidad distribuida y gestión de consistencia eventual, el equipo puede dedicar el 100% del tiempo a la lógica de negocio, cumpliendo el plazo de 4 meses.
3.  **Táctica de Diseño (Encapsulamiento):** Se aplicará la táctica de *Bounded Contexts* para asegurar que las reglas comerciales estén aisladas. Esto garantiza la **Mantenibilidad** sin el costo de la red.
4.  **Preparación para el Futuro (Evolución Gradual):** Al mantener esquemas de base de datos separados lógicamente por módulo, se facilita una futura migración a microservicios (extracción de módulos) si el volumen operativo lo requiere, minimizando la deuda técnica arquitectónica.

**Supuesto asumido:** Se asume que el equipo utilizará herramientas de análisis estático (como ArchUnit o similares) para validar que no existan dependencias prohibidas entre módulos durante el desarrollo.

## Consecuencias

### Positivas
- Reducción drástica de la complejidad de despliegue y monitoreo.
- Facilidad para realizar pruebas de integración de extremo a extremo en un solo entorno.
- Consistencia de datos garantizada mediante transacciones locales.

### Negativas
- El sistema debe reiniciarse por completo para desplegar cualquier cambio menor en un módulo.
- Existe el riesgo de que el acoplamiento aumente si no se supervisan las revisiones de código.

### Trade-offs y Riesgos Residuales
- **Trade-off (Simplicidad vs. Aislamiento):** Se sacrifica el aislamiento físico de fallos (propio de microservicios) en favor de la simplicidad operativa necesaria para cumplir el plazo. 
- **Riesgo Residual:** La "Gran Bola de Lodo". Si el equipo ignora los límites modulares por la presión del tiempo, el sistema será difícil de mantener. 
- **Mitigación:** Implementación de pruebas de arquitectura automatizadas en el pipeline de CI/CD que fallen si un módulo accede directamente a la base de datos o lógica interna de otro módulo sin pasar por la interfaz autorizada.