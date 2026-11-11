Aquí tienes el Registro de Decisión Arquitectónica (ADR) para el caso planteado, siguiendo el estándar de la industria.

# Registro de Decisión Arquitectónica (ADR)

## Título
ADR 06: Adopción de Monolito Modular como Estrategia de Modularización Inicial

## Estatus
Aceptado

## Contexto
La empresa está iniciando el desarrollo de un sistema de reservas. El escenario presenta las siguientes características clave:
- **Equipo:** Un solo equipo pequeño de 6 desarrolladores.
- **Plazo:** Restringido (4 meses para el lanzamiento inicial).
- **Carga:** Volumen inicial moderado, pero con alta incertidumbre sobre el crecimiento futuro.
- **Negocio:** Se esperan cambios frecuentes en las reglas comerciales.
- **Limitaciones:** Capacidad de DevOps limitada y necesidad de alta velocidad de entrega.

El equipo evaluó la posibilidad de utilizar una arquitectura de microservicios para facilitar la escalabilidad futura. Sin embargo, la sobrecarga operativa de gestionar múltiples despliegues, redes y consistencia de datos distribuida podría comprometer el plazo de entrega.

## Decisión
Hemos decidido adoptar una arquitectura de **Monolito Modular (Modular Monolith)** en lugar de microservicios para el lanzamiento inicial.

Esta estrategia implica:
1.  **Separación Lógica:** El código se organizará en módulos claramente definidos (ej. Reservas, Pagos, Usuarios, Notificaciones) con interfaces internas estrictas.
2.  **Base de Datos Única:** Se utilizará una sola base de datos, pero con esquemas o prefijos de tablas separados por módulo para evitar el acoplamiento a nivel de datos.
3.  **Despliegue Único:** Todo el sistema se desplegará como una única unidad de ejecución (un solo artefacto).
4.  **Comunicación In-Process:** Los módulos se comunicarán mediante llamadas a funciones o eventos internos, evitando la latencia de red y la complejidad de protocolos como gRPC o REST internos.

## Atributos de Calidad Atendidos
*   **Velocidad de Entrega:** Al reducir la complejidad de infraestructura y DevOps, el equipo puede centrarse al 100% en la lógica de negocio para cumplir con los 4 meses.
*   **Mantenibilidad:** La separación modular permite que los cambios frecuentes en las reglas de negocio se localicen en módulos específicos sin afectar al resto del sistema.
*   **Evolución Gradual:** Al mantener fronteras claras entre módulos, el sistema está preparado para ser refactorizado hacia microservicios en el futuro si el volumen de carga o el tamaño del equipo lo justifican.

## Consecuencias

### Positivas
*   **Simplicidad de Desarrollo:** Un solo repositorio y un flujo de CI/CD simplificado.
*   **Facilidad de Refactorización:** Es más sencillo mover código entre módulos dentro de un monolito que entre servicios distribuidos.
*   **Consistencia de Datos:** Se pueden utilizar transacciones ACID locales, eliminando la necesidad de implementar patrones complejos como Saga.
*   **Bajo Costo Operativo:** Menor necesidad de monitoreo distribuido y orquestación compleja (Kubernetes, Service Mesh, etc.).

### Negativas / Riesgos
*   **Disciplina de Equipo:** Requiere rigor para evitar que los desarrolladores "salten" las interfaces de los módulos y creen acoplamiento fuerte (código espagueti).
*   **Escalabilidad Monolítica:** No se pueden escalar módulos de forma independiente; se debe escalar toda la aplicación.
*   **Punto Único de Falla:** Un error crítico en un módulo puede afectar la disponibilidad de todo el sistema.

## Alternativas Consideradas
*   **Microservicios:** Descartado debido a la "tasa de impuestos" (overhead) de infraestructura y la limitada capacidad DevOps. El riesgo de no cumplir el plazo de 4 meses era muy alto.
*   **Monolito Tradicional (Big Ball of Mud):** Descartado porque dificultaría la mantenibilidad y la evolución futura hacia una arquitectura distribuida.

## Notas de Implementación
*   Se utilizarán herramientas de análisis estático (como ArchUnit para Java o herramientas similares según el lenguaje) para asegurar que las dependencias entre módulos respeten las reglas de arquitectura definidas.
*   Cada módulo debe ser dueño de su propia lógica y datos, prohibiendo los *JOINs* entre tablas de diferentes módulos.