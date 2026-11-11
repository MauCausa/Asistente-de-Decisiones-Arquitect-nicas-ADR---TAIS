# ADR-011: Estrategia de Recuperación Ante Desastres (Warm Standby / Pilot Light) para el Sistema de Trámites Públicos

* **Estado:** Aprobado
* **Fecha:** 2023-10-25
* **Autores:** Equipo de Arquitectura de Software
* **Contexto del Negocio:** Sistema de Trámites Públicos

---

## 1. Contexto y Problema

El Sistema de Trámites Públicos es una plataforma crítica para la ciudadanía. En caso de un fallo catastrófico o caída masiva de la región principal de nube (Region A), el sistema debe garantizar la continuidad del negocio migrando su operación a una región secundaria (Region B).

Sin embargo, el presupuesto asignado prohíbe el despliegue de una arquitectura Activo-Activo (Active-Active) con capacidad duplicada al 100% en tiempo real. La organización ha definido un equilibrio entre disponibilidad, costo y tolerancia a pérdidas, formalizado mediante los siguientes objetivos de recuperación:
* **RTO (Recovery Time Objective):** Máximo 60 minutos.
* **RPO (Recovery Point Objective):** Máximo 15 minutos.

El desafío arquitectónico consiste en diseñar una estrategia de Recuperación ante Desastres (DR) multirregión que cumpla estrictamente con el RTO y RPO, preservando la integridad de los trámites y optimizando los costos operativos.

## 2. Opciones Consideradas

1. **Opción 1: Backup & Restore (Frío)**
   * Se realizan respaldos periódicos de bases de datos y archivos a almacenamiento en la región secundaria. No hay infraestructura de cómputo encendida.
   * *Pros:* La opción más económica.
   * *Contras:* El RTO supera fácilmente los 60 minutos (tiempo de aprovisionamiento, restauración de terabytes de datos y pruebas); riesgo de violar el RPO de 15 minutos.

2. **Opción 2: Warm Standby / Pilot Light (Cálido/Piloto) — *Seleccionada***
   * Se mantiene la capa de datos replicada de forma asíncrona y continua en la región secundaria. La capa de aplicación/cómputo se mantiene apagada o escalada al mínimo (piloto). Ante un desastre, un proceso automatizado/semiautomatizado escala la infraestructura en la región secundaria y redirige el tráfico.
   * *Pros:* Cumple con RPO < 15 min y RTO < 60 min. Ahorro significativo en costos de cómputo en comparación con Active-Active.
   * *Contras:* Requiere automatización sólida de Infraestructura como Código (IaC) y orquestación de *failover*.

3. **Opción 3: Active-Active (Caliente)**
   * Toda la infraestructura está duplicada y procesando tráfico simultáneamente en ambas regiones con replicación bidireccional de datos.
   * *Pros:* RTO y RPO cercanos a cero; sin interrupción del servicio.
   * *Contras:* Inviable financieramente por restricción presupuestaria. Alta complejidad en resolución de conflictos de datos.

## 3. Decisión

Se decide adoptar un patrón de **Recuperación ante Desastres basado en Warm Standby / Pilot Light** entre dos regiones del proveedor de nube.

### Detalles de la Implementación:

1. **Capa de Datos e Integridad (Garantía RPO < 15 min):**
   * Se configurará la base de datos principal (ej. PostgreSQL/MySQL gestionado) con **replicación asíncrona en tiempo real** hacia una instancia de lectura (*Read Replica*) en la región secundaria. El *lag* de replicación se monitoreará para asegurar que permanezca por debajo de los 5 minutos.
   * El almacenamiento de archivos/documentos adjuntos de trámites (ej. Object Storage) utilizará **replicación entre regiones (CRR)** habilitada con un SLA de transferencia por debajo de los 15 minutos.

2. **Capa de Cómputo y Aplicación (Garantía RTO < 60 min):**
   * La infraestructura de la región secundaria estará definida completamente mediante **Infraestructura como Código (IaC)** (ej. Terraform, CloudFormation).
   * Se mantendrá un clúster mínimo o imágenes/plantillas de servidores preconfiguradas. Se utilizarán pipelines de CI/CD para desplegar o escalar automáticamente los microservicios/aplicaciones en la región secundaria durante el evento de *failover*.

3. **Enrutamiento de Tráfico:**
   * Se utilizará un servicio de DNS global / Traffic Manager con comprobaciones de estado (*health checks*). El cambio de tráfico (*failover*) se ejecutará de forma semiautomática con confirmación humana para evitar falsos positivos (*split-brain*).

```
[ Región Principal (Activa) ]
  ├── Cómputo (100% Capacidad)
  └── BD Principal ──(Replicación Asíncrona < 5 min)──┐
                                                      │
[ Región Secundaria (Warm Standby) ]                  │
  ├── Cómputo (0% a 10% / Desplegable via IaC)        │
  └── BD Replica (Lectura) <──────────────────────────┘
```

## 4. Consecuencias

### Positivas:
* **Optimización de Costos Operativos:** Reduce drásticamente los costos de cómputo al no pagar por servidores/contenedores redundantes encendidos al 100% en la región secundaria.
* **Cumplimiento de SLA:** Se garantiza un RPO ≤ 15 minutos (mediante replicación continua de BD) y un RTO ≤ 60 minutos (tiempo suficiente para promover la BD a primaria y desplegar el cómputo vía IaC).
* **Integridad de Datos:** La replicación de base de datos a nivel de motor previene la corrupción o inconsistencia en los estados de los trámites.

### Negativas / Riesgos:
* **Breve Interrupción del Servicio:** La ciudadanía experimentará una ventana de indisponibilidad de hasta 60 minutos mientras se ejecuta el plan de recuperación.
* **Complejidad en Automatización:** Dependencia crítica en scripts de IaC, pruebas de despliegue automatizado y herramientas de orquestación.
* **Costo de Red:** Genera un costo recurrente por transferencia de datos salientes entre regiones (*Cross-Region Data Transfer*).

## 5. Mitigación de Riesgos y Validación

* **Simulacros de DR (Game Days):** Se realizarán pruebas de *failover* programadas de forma trimestral para validar que el tiempo de despliegue de IaC y promoción de la BD se mantenga dentro del límite de 60 minutos.
* **Monitoreo de Replicación:** Se establecerán alarmas críticas (Alertmanager/CloudWatch) si el retraso de replicación de la base de datos (*Replication Lag*) supera los 10 minutos.
* **Scripts de Promoción Probados:** Los procedimientos para promover la réplica de base de datos a instancia de escritura primaria estarán completamente automatizados y auditados.