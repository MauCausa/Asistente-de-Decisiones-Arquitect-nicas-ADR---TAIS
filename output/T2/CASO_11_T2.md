# CASO_11 - Recuperacion regional para un sistema de tramites publicos

## Estado
Aceptado

## Contexto y Problema
El sistema de trámites públicos de la organización es una pieza crítica para la atención ciudadana. Actualmente, el sistema opera en una única región de nube, lo que representa un punto único de fallo ante desastres regionales. La organización requiere una estrategia de recuperación ante desastres (DR) que garantice la continuidad del servicio en una región secundaria. Sin embargo, existen limitaciones financieras estrictas que impiden la implementación de una arquitectura *Active-Active* (duplicidad total de recursos activos). El problema radica en diseñar una arquitectura que equilibre la rapidez de recuperación y la mínima pérdida de datos con un presupuesto operativo restringido.

## Drivers de Decisión (ASRs)
*   **ASR-01: Recuperación ante Desastres (Disponibilidad):** Capacidad de restaurar el servicio en una región geográfica distinta ante una caída total de la región principal.
*   **ASR-02: Integridad de Datos (Fiabilidad):** Garantizar que la información de los trámites sea consistente tras la recuperación, minimizando la pérdida de transacciones.
*   **ASR-03: Costo Operativo (Eficiencia):** Restricción presupuestaria que obliga a minimizar el gasto en infraestructura ociosa en la región de contingencia.
*   **Restricción de RTO (Recovery Time Objective):** El tiempo máximo de interrupción permitido es de 60 minutos.
*   **Restricción de RPO (Recovery Point Objective):** La pérdida máxima de datos permitida es de 15 minutos.

## Opciones Consideradas

### Opción 1: Modelo "Pilot Light" con Infraestructura como Código (IaC)
- **Descripción:** Se mantiene solo la base de datos replicándose asíncronamente en la región secundaria. El resto de la infraestructura (servidores, redes, balanceadores) solo existe como código (IaC) y se despliega únicamente cuando ocurre el desastre.
- **Ventajas:** Costo operativo mínimo, ya que no se paga por cómputo encendido en la región secundaria.
- **Desventajas:** El tiempo de despliegue y aprovisionamiento de recursos desde cero puede ser impredecible y lento.
- **Riesgos:** Riesgo elevado de incumplir el RTO de 60 minutos debido a posibles fallos en las APIs del proveedor de nube o falta de capacidad disponible en la región secundaria durante una crisis masiva.

### Opción 2: Modelo "Warm Standby" con Capacidad Reducida
- **Descripción:** Se mantiene una versión mínima y funcional de la infraestructura siempre activa en la región secundaria (ej. 10-20% de la flota de servidores). La base de datos está en replicación asíncrona. Ante un fallo, se escala horizontalmente la infraestructura existente.
- **Ventajas:** RTO muy bajo y predecible; los servicios ya están configurados y conectados. Cumple con el RPO mediante la replicación de datos.
- **Desventajas:** Incurre en un costo fijo mensual por el cómputo que permanece encendido 24/7.
- **Riesgos:** Riesgo de "Capacity Starvation" si el proveedor de nube no puede suministrar el escalado rápido necesario durante un desastre regional que afecte a múltiples clientes.

### Opción 3: Arquitectura Híbrida Serverless / Event-Driven
- **Descripción:** Uso de servicios sin servidor (FaaS) y buses de eventos replicados. Los componentes de cómputo no tienen costo mientras no se usen, pero están desplegados y listos para procesar peticiones.
- **Ventajas:** Costo óptimo (pago por uso) y recuperación casi instantánea.
- **Desventajas:** Requiere una reingeniería profunda de las aplicaciones de trámites para ser *stateless* e idempotentes.
- **Riesgos:** Alta complejidad de implementación y posibles limitaciones de tiempo de ejecución en trámites gubernamentales complejos.

## Decisión y Justificación (Rationale)
Se ha seleccionado la **Opción 2: Modelo "Warm Standby" con Capacidad Reducida**.

La justificación se basa en los siguientes puntos alineados con el **SWEBOK v4.0 (Capítulo 02)**:
1.  **Cumplimiento de Restricciones (RTO/RPO):** A diferencia de la Opción 1, el *Warm Standby* garantiza un RTO inferior a 60 minutos porque elimina el tiempo de aprovisionamiento inicial de red y configuración de servicios básicos [SWEBOK-02-13]. La replicación asíncrona de la base de datos satisface el RPO de 15 minutos (ASR-02).
2.  **Equilibrio Costo-Riesgo (ASR-03):** Aunque es más costosa que la Opción 1, es significativamente más económica que un modelo *Active-Active*. Se ajusta al presupuesto al mantener solo una "huella" mínima de cómputo, cumpliendo con la táctica de eficiencia de recursos.
3.  **Tácticas de Disponibilidad [SWEBOK-02-07]:** Se implementará el escalado automático (*Auto-scaling*) para pasar de la capacidad mínima a la operativa. Se asume el uso de **Idempotency Keys** en la capa de aplicación para asegurar que los trámites enviados durante la ventana de 15 min del RPO no generen duplicados tras el failover.
4.  **Supuestos:** Se asume que el sistema actual permite el escalado horizontal y que el proveedor de nube garantiza cuotas mínimas de reserva para el escalado en la región secundaria.

## Consecuencias

### Positivas
- **Resiliencia Probada:** El sistema puede estar operativo en menos de 60 minutos con una configuración validada y activa.
- **Simplicidad Operativa:** Los procesos de despliegue (CI/CD) pueden actualizar ambas regiones simultáneamente, reduciendo la deriva de configuración.
- **Integridad:** La base de datos "caliente" en modo lectura facilita auditorías de datos en tiempo real sin afectar la producción.

### Negativas
- **Gasto Fijo:** Existe un costo permanente por recursos que no procesan tráfico ciudadano en condiciones normales.
- **Mantenimiento Doble:** Obliga a gestionar parches y actualizaciones de seguridad en dos entornos activos (aunque uno sea reducido).

### Trade-offs y Riesgos Residuales
- **Trade-off Costo vs. Disponibilidad:** Se acepta pagar un excedente presupuestario mínimo (comparado con Pilot Light) para eliminar el riesgo de incumplimiento legal del RTO.
- **Riesgo Residual de Capacidad:** En un desastre que afecte a toda una zona geográfica, el escalado del 10% al 100% podría fallar si el proveedor de nube agota sus recursos. 
- **Mitigación:** Se programarán simulacros de desastre (*DR Drills*) trimestrales y se negociarán "Reserved Instances" o "Capacity Reservations" con el proveedor de nube para los componentes más críticos del sistema de trámites.