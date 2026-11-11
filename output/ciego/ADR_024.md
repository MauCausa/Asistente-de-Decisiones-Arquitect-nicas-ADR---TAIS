# CASO_12 - Gestion segura de secretos para aplicaciones y CI CD

## Estado
Aceptado

## Contexto y Problema
En el estado actual de la arquitectura, múltiples equipos de desarrollo almacenan claves de API, contraseñas y otros datos sensibles directamente en archivos de configuración estáticos y mediante variables manuales asignadas en los servidores de despliegue. Esta práctica ha provocado incidentes graves de seguridad, incluyendo la filtración accidental de secretos en los historiales de los repositorios de código. Asimismo, no existe un mecanismo centralizado ni automatizado para la rotación de credenciales. El problema principal radica en la alta exposición de datos sensibles y el riesgo inminente de comprometer la infraestructura, con el desafío adicional de corregir estas deficiencias sin bloquear, ralentizar o interrumpir los ciclos de despliegue automatizado de los equipos. El alcance abarca todas las aplicaciones desplegadas en contenedores y los pipelines de integración y entrega continua (CI/CD) alojados en GitHub Actions, bajo un estricto principio de menor privilegio.

## Drivers de Decisión (ASRs)
- **Confidencialidad (Prioridad Alta - Crítica):** Eliminación absoluta de credenciales en texto plano (en repositorios, archivos de configuración y variables manuales) mediante cifrado en reposo y en tránsito, e inyección dinámica en memoria o variables efímeras en tiempo de ejecución.
- **Rotación y Revocación (Prioridad Alta):** Capacidad de actualizar tokens, API keys y contraseñas de manera automatizada y periódica para minimizar la ventana de exposición ante incidentes, sin requerir paradas de servicio ni intervención manual.
- **Automatización de Despliegues (Prioridad Media-Alta):** Integración fluida en los pipelines de CI/CD mediante identidades efímeras, garantizando que la seguridad no degrade la velocidad de entrega del software.
- **Restricción 1 - Pipelines en GitHub Actions:** Uso obligatorio del ecosistema de GitHub Actions, requiriendo autenticación basada en identidad federada (OIDC) en lugar de secretos de larga duración estáticos.
- **Restricción 2 - Aplicaciones en Contenedores:** Inyección de secretos condicionada al entorno de ejecución de contenedores mediante identidades de carga de trabajo (*Workload Identity*), asegurando que residan estrictamente en la memoria efímera.
- **Restricción 3 - Mínimo Privilegio:** Restricción estricta de permisos de lectura y escritura para que cada aplicación o pipeline acceda exclusivamente a las credenciales indispensables para su funcionamiento, respaldado por auditoría centralizada.

## Opciones Consideradas
### Opción 1: Enfoque "Cloud-Native Managed" (Secret Manager + OIDC)
- **Descripción:** Delega la gestión de secretos a un servicio nativo del proveedor de nube (AWS Secrets Manager, Azure Key Vault o GCP Secret Manager). Se establece confianza federada mediante OpenID Connect (OIDC) entre GitHub Actions y la nube. Los contenedores utilizan *Workload Identity* para autenticarse, inyectando los secretos como variables efímeras o mediante llamadas seguras vía SDK en tiempo de ejecución.
- **Ventajas:** Eliminación total de secretos estáticos en repositorios; soporte nativo para rotación automática mediante funciones sin servidor; excelente integración con GitHub Actions vía OIDC; bajo costo inicial con modelo de pago por uso.
- **Desventajas:** Alta dependencia de las APIs específicas del proveedor de nube (Vendor Lock-in); costos de API escalables si las aplicaciones realizan consultas excesivas sin caché local.
- **Riesgos:** Riesgo de proliferación desordenada de secretos (*Secret Sprawl*) ante la falta de una nomenclatura estandarizada; deuda técnica potencial si las aplicaciones se acoplan fuertemente al SDK del proveedor en lugar de usar abstracciones.

### Opción 2: Enfoque "Platform-Agnostic Centralized" (HashiCorp Vault)
- **Descripción:** Despliegue y gestión de un clúster centralizado de HashiCorp Vault. GitHub Actions se autentica mediante `vault-action` usando tokens JWT/OIDC. Los contenedores emplean un *Vault Agent Sidecar* para inyectar secretos en volúmenes compartidos cifrados o archivos de configuración dinámicos.
- **Ventajas:** Generación de secretos dinámicos bajo demanda con expiración corta (ej. credenciales de base de datos efímeras); sistema de auditoría detallado y granular a nivel de acceso.
- **Desventajas:** Extrema complejidad operativa debido a la necesidad de gestionar alta disponibilidad, copias de seguridad y el proceso de desbloqueo (*unsealing*) del clúster; curva de aprendizaje elevada en HCL y políticas de Vault.
- **Riesgos:** El clúster de Vault se convierte en un Punto Único de Fallo (SPOF) crítico; si el servicio cae, se bloquean inmediatamente todos los despliegues y el arranque de las aplicaciones. Deuda operativa constante por gestión de parches e infraestructura propia.

### Opción 3: Enfoque "GitOps-Centric" (SOPS + Age/KMS)
- **Descripción:** Almacenamiento de secretos cifrados directamente en el repositorio Git utilizando Mozilla SOPS. La clave de descifrado maestra reside en un KMS de nube, la cual es utilizada por GitHub Actions exclusivamente durante la fase de despliegue para generar secretos estándar de Kubernetes o archivos de configuración.
- **Ventajas:** Alineación perfecta con flujos de trabajo basados en GitOps; simplicidad al no requerir infraestructura compleja en tiempo de ejecución ni consultas constantes a gestores externos.
- **Desventajas:** Mecanismo de rotación deficiente e ineficiente, requiriendo commits manuales en el repositorio; incapacidad de ofrecer credenciales verdaderamente dinámicas por sesión.
- **Riesgos:** Riesgo de "Fatiga de Cifrado" donde los desarrolladores cometan errores y suban archivos sin cifrar; falta de trazabilidad en tiempo real sobre qué aplicación leyó qué secreto.

## Decisión y Justificación (Rationale)
Se selecciona formalmente la **Opción 1: Enfoque "Cloud-Native Managed" (Secret Manager + OIDC)** como la arquitectura estándar para la gestión segura de secretos en aplicaciones y pipelines de CI/CD.

Esta decisión se fundamenta en la aplicación directa de tácticas del SWEBOK v4.0 (Capítulo 02: Software Design), específicamente el uso de un **Servicio Centralizado de Gestión de Secretos integrado mediante Autenticación Federada (OIDC)** y políticas de **Mínimo Privilegio**. 

*   **Justificación frente a ASRs y Restricciones:**
    *   **Confidencialidad:** Al utilizar Secret Manager junto con OIDC y *Workload Identity*, se eliminan por completo los secretos estáticos en texto plano en GitHub Actions y en los contenedores. Los datos viajan cifrados y se cargan efímeramente en la memoria del contenedor, cumpliendo con el estándar SWEBOK-02-14.
    *   **Rotación y Revocación:** Se aprovechan las capacidades nativas de rotación automática del proveedor de nube (mediante funciones serverless asociadas), reduciendo la ventana de exposición sin intervención manual.
    *   **Automatización de Despliegues y GitHub Actions:** La autenticación federada OIDC permite a GitHub Actions negociar tokens temporales de forma transparente, evitando almacenar credenciales de larga duración en los ajustes del repositorio y garantizando que los despliegues no sufran bloqueos operativos.
    *   **Contenedores y Mínimo Privilegio:** Mediante *Workload Identity* y roles IAM granulares, se asegura que cada contenedor o pipeline acceda únicamente a los secretos estrictamente necesarios para su operación.
*   **Justificación de Supuestos y Descarte de Otras Opciones:** Se asume que la organización opera sobre una infraestructura en la nube compatible con un proveedor principal, lo que justifica el uso de su gestor nativo. Se descarta la Opción 2 (Vault) debido a la sobrecarga operativa y al riesgo de convertir la infraestructura de secretos en un SPOF frente a la restricción de mantener despliegues fluidos. Se descarta la Opción 3 (GitOps/SOPS) porque no soporta rotación automática nativa y mantiene el riesgo de exposición en el repositorio ante errores humanos.

## Consecuencias
### Positivas
- Eliminación absoluta de credenciales estáticas y en texto plano en los repositorios de código y archivos de configuración locales.
- Integración fluida y segura de los pipelines de GitHub Actions mediante autenticación federada (OIDC), preservando la velocidad de entrega continua.
- Reducción drástica de la superficie de ataque gracias a la inyección de secretos directamente en memoria y al uso de políticas de mínimo privilegio.
- Capacidad de rotación automatizada de credenciales sin la necesidad de intervenciones manuales propensas a errores.

### Negativas
- Dependencia tecnológica directa del proveedor de nube seleccionado (Vendor Lock-in).
- Costos operativos variables asociados al consumo de llamadas API del servicio de gestión de secretos si las aplicaciones no implementan mecanismos adecuados de caché local.

### Trade-offs y Riesgos Residuales
- **Trade-off (Seguridad vs. Acoplamiento):** Se acepta un mayor acoplamiento a las APIs y modelos de identidad del proveedor de nube a cambio de eliminar por completo la carga de mantener infraestructura propia de secretos (como un clúster de Vault).
- **Riesgo Residual (Latencia y Fallas de Red en Runtime):** Depender de un servicio en la nube para recuperar secretos al iniciar contenedores puede introducir latencia o fallas si el servicio experimenta interrupciones.
  - *Acción de Mitigación:* Implementar estrategias de caché local de corta duración en las aplicaciones y reintentos robustos (*exponential backoff*) durante el arranque de los contenedores.
- **Riesgo Residual (Secret Sprawl):** Crecimiento desordenado de secretos en el gestor central.
  - *Acción de Mitigación:* Establecer una convención de nomenclatura estricta y gobernanza automatizada mediante políticas de infraestructura como código (IaC) para la creación y etiquetado de secretos.