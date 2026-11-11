Este es el Registro de Decisión Arquitectónica (ADR) para la implementación de una gestión segura de secretos, diseñado para mitigar los riesgos de exposición y mejorar la operatividad del ciclo de vida de las credenciales.

---

# ADR 012: Gestión Segura de Secretos y Automatización de Ciclo de Vida

## Estado
Propuesto

## Contexto
Actualmente, los equipos de desarrollo almacenan información sensible (claves de API, contraseñas de bases de datos, certificados) de manera descentralizada y poco segura. Se han identificado las siguientes problemáticas:
*   **Exposición en código:** Secretos almacenados en archivos de configuración (`.env`, `.yaml`) que terminan en el historial de Git.
*   **Gestión Manual:** Las variables de entorno se configuran manualmente en los servidores, lo que induce a errores y falta de consistencia.
*   **Ausencia de Rotación:** No existe un mecanismo para cambiar credenciales periódicamente, aumentando el impacto en caso de una filtración.
*   **Falta de Auditoría:** No se sabe quién o qué servicio accedió a un secreto específico.

## Decisión
Adoptaremos **HashiCorp Vault** como la solución centralizada para la gestión de secretos, integrada con **GitHub Actions** para el CI/CD y utilizando **Sidecars/Init-containers** para las aplicaciones en contenedores.

### Detalles de la Implementación:

1.  **Almacenamiento Centralizado:** Todos los secretos se migrarán de los repositorios y servidores a HashiCorp Vault.
2.  **Autenticación mediante OIDC:** GitHub Actions utilizará OpenID Connect (OIDC) para autenticarse con Vault sin necesidad de almacenar un "token maestro" de larga duración en GitHub.
3.  **Inyección Dinámica:**
    *   Para aplicaciones en contenedores (Kubernetes/Docker), se utilizará el **Vault Agent** para inyectar secretos directamente en el sistema de archivos compartido o como variables de entorno en tiempo de ejecución, evitando que persistan en la imagen del contenedor.
4.  **Rotación Automática:** Se configurarán *Dynamic Secrets* para bases de datos y servicios compatibles, donde Vault genera credenciales temporales que expiran automáticamente.
5.  **Estructura de Políticas:** Se aplicará el principio de **mínimo privilegio**, creando políticas de Vault específicas por entorno (dev, staging, prod) y por microservicio.

## Atributos de Calidad

*   **Confidencialidad:** Los secretos están cifrados en reposo y en tránsito. Solo las identidades autorizadas (máquinas o humanos) pueden descifrarlos.
*   **Rotación y Revocación:** La capacidad de rotar credenciales dinámicas reduce la ventana de oportunidad para un atacante. La revocación es instantánea desde el panel central.
*   **Automatización de Despliegues:** La integración nativa con GitHub Actions permite que los pipelines obtengan credenciales "just-in-time", eliminando la configuración manual de secretos en la interfaz de GitHub.

## Restricciones
*   **GitHub Actions:** Se requiere configurar el "Trust Relationship" entre el proveedor de identidad de GitHub y Vault.
*   **Contenedores:** Las aplicaciones deben ser capaces de leer configuraciones desde archivos inyectados o variables de entorno dinámicas.
*   **Conectividad:** El clúster de Vault debe ser accesible desde los runners de GitHub Actions y desde los nodos donde residen los contenedores.

## Consecuencias

### Positivas:
*   **Eliminación de secretos en Git:** Se reduce drásticamente el riesgo de fugas de datos por historial de repositorio.
*   **Auditoría Completa:** Vault proporciona logs detallados de cada acceso a un secreto.
*   **Escalabilidad:** Un solo método para gestionar secretos en múltiples equipos y tecnologías.

### Negativas/Riesgos:
*   **Punto Único de Fallo:** Si Vault no está disponible, los despliegues y el arranque de aplicaciones pueden fallar. Se requiere una configuración de Alta Disponibilidad (HA).
*   **Curva de Aprendizaje:** Los equipos deben aprender a interactuar con la API/CLI de Vault y entender el flujo de autenticación OIDC.
*   **Esfuerzo de Migración:** Requiere un trabajo inicial para limpiar historiales de Git y mover variables manuales al nuevo sistema.

## Alternativas Consideradas
*   **GitHub Actions Secrets únicamente:** Descartado porque no ofrece rotación automática ni gestión de secretos para las aplicaciones en tiempo de ejecución (solo para el pipeline).
*   **AWS Secrets Manager / Azure Key Vault:** Considerados, pero se optó por HashiCorp Vault por su naturaleza agnóstica a la nube, permitiendo una estrategia multi-cloud o híbrida en el futuro.

---
**Fecha:** 24 de Mayo de 2024
**Autor:** Arquitectura de Software / Equipo de Seguridad de Plataforma