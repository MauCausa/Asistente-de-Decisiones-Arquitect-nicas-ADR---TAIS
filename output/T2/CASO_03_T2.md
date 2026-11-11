# CASO_03 - Autenticacion centralizada para APIs de una plataforma universitaria

## Estado
Aceptado (Propuesto y validado mediante asistencia híbrida SWEBOK v4.0 + evaluación de trade-offs)

## Contexto y Problema
La universidad cuenta con una plataforma distribuida que integra servicios clave como matrículas, biblioteca, pagos y aula virtual a través de APIs independientes. Actualmente, cada uno de estos sistemas mantiene sus propios mecanismos de autenticación, almacenes de credenciales y esquemas de gestión de sesiones. Esta fragmentación genera una experiencia de usuario inconsistente para estudiantes, docentes y personal administrativo, quienes deben autenticarse repetidamente en las distintas herramientas. Asimismo, introduce severos riesgos de seguridad debido a la dispersión de credenciales, políticas de contraseñas heterogéneas y la dificultad para revocar accesos de forma centralizada.

El reto arquitectónico consiste en diseñar e implementar un mecanismo de autenticación centralizado que proporcione Inicio de Sesión Único (SSO) en canales web y móviles, integre un control de acceso basado en roles (RBAC) administrado de forma unificada y permita la convivencia temporal con sistemas heredados que carecen de soporte nativo para estándares modernos de autenticación basada en tokens, evitando refactorizaciones masivas e interrupciones operativas.

## Drivers de Decisión (ASRs)
*   **Seguridad (ASR-01):** Centralizar la autenticación, la emisión de aserciones de identidad y el control de acceso basado en roles (RBAC), eliminando la gestión de credenciales dispersa en las APIs independientes y protegiendo los servicios mediante tokens de corta duración [SWEBOK-02-05].
*   **Interoperabilidad (ASR-02):** Estandarizar las interfaces de comunicación entre los clientes heterogéneos (móvil y web) y los servicios del ecosistema universitario mediante contratos de autorización universales [SWEBOK-02-02, SWEBOK-02-05].
*   **Experiencia de Inicio de Sesión Único - SSO (ASR-03):** Garantizar la propagación fluida y transparente de la sesión a través de los múltiples dominios y aplicaciones académicas sin requerir re-autenticaciones manuales.
*   **Restricción - Convivencia Temporal con Sistemas Heredados:** La solución debe permitir la integración de aplicaciones antiguas (ej. biblioteca, aula virtual) que no procesan tokens JWT de forma nativa, sin obligar a su refactorización inmediata.
*   **Restricción - Soporte Multicanal (Acceso Web y Móvil):** Soporte nativo para flujos de autenticación en navegadores web y aplicaciones móviles nativas bajo esquemas de seguridad robustos.
*   **Restricción - Administración Centralizada de Roles Institucionales:** Desacoplamiento de la gestión de identidades y roles (estudiante, docente, personal administrativo) de la lógica de negocio de cada API, unificándolos en un único directorio institucional.

## Opciones Consideradas

### Opción 1: Arquitectura Basada en API Gateway Descentralizado con Envoltura Adapter / Strangler Fig para el Legado
- **Descripción:** Implementación de un API Gateway en el borde (Edge Gateway) integrado con un Proveedor de Identidad Centralizado (IdP) basado en OpenID Connect (OIDC) y OAuth 2.0 (con flujo Authorization Code + PKCE). El API Gateway asume la responsabilidad de descargado de seguridad (*offloading*) [SWEBOK-02-05], validando la firma criptográfica (JWKS) de los tokens de acceso (JWT) para las APIs modernas. Para los sistemas heredados, se despliegan adaptadores de traducción de cabeceras (*Adapters / Strangler Fig*) que convierten las aserciones JWT en cookies de sesión o cabeceras legacy.
- **Ventajas:**
  * Maximiza la seguridad aislando la red interna tras el Gateway y centralizando el *offloading* de credenciales [SWEBOK-02-05].
  * Resuelve la convivencia con el legado sin modificar el código fuente de los sistemas antiguos.
  * Proporciona un punto único para auditoría, limitación de tasa (*rate limiting*) y validación de roles centralizada.
- **Desventajas:**
  * Introduce un punto único de fallo (SPOF) y latencia adicional en el borde que debe ser gestionado mediante alta disponibilidad.
  * Requiere desarrollar y mantener adaptadores específicos para los sistemas heredados.
- **Riesgos:** Riesgo de "eternización" de los adaptadores si no se planifica la migración definitiva del legado; riesgo de desincronización de revocaciones entre el token JWT y las sesiones locales convertidas por los adaptadores.

### Opción 2: Autenticación Federada Basada en Tokens Puros en Cada Servicio (Decentralized Resource Server Architecture)
- **Descripción:** Las aplicaciones clientes (web y móvil) obtienen tokens JWT directamente desde el IdP Central. Cada API actúa como un Servidor de Recursos (*Resource Server*) independiente, validando el token localmente mediante SDKs/librerías embebidas en su código fuente. Esta opción requiere modificar el código de todos los sistemas heredados para incorporar módulos de inspección de cabeceras `Authorization: Bearer`.
- **Ventajas:**
  * Elimina cuellos de botella de enrutamiento central al no depender de un Gateway para la validación del tráfico.
  * Sigue estándares puros OIDC/OAuth 2.0 de extremo a extremo [SWEBOK-02-02].
- **Desventajas:**
  * Requiere refactorizar obligatoriamente el código fuente de los sistemas heredados, violando la restricción de convivencia temporal.
  * Eleva la carga cognitiva y duplica la lógica de validación de seguridad en múltiples lenguajes y frameworks.
- **Riesgos:** Alto riesgo de discrepancias en la interpretación de los *claims* de roles entre servicios debido a implementaciones heterogéneas en los SDKs [SWEBOK-02-05].

### Opción 3: Malla de Identidad Basada en Reverse-Proxy In-Process / Sidecar (Identity-Aware Proxy / Gateway Per-Service)
- **Descripción:** Despliegue de un proxy inverso ligero (*sidecar* o *identity-aware proxy*) adyacente a cada instancia de API o sistema heredado. El proxy intercepta el tráfico entrante, gestiona el flujo de autenticación con el IdP Central, valida el JWT y pasa la petición a la API de negocio inyectando cabeceras sanitizadas.
- **Ventajas:**
  * Ofrece un modelo de seguridad de Aislamiento Total (Zero Trust) a nivel de servicio [SWEBOK-02-05].
  * Desacopla 100% la lógica de autenticación del código de las aplicaciones sin requerir modificaciones en el legado.
- **Desventajas:**
  * Alta complejidad operativa e infraestructural al multiplicar el número de componentes a orquestar y monitorear.
  * Incremento en el consumo de recursos computacionales (CPU/RAM) por cada instancia de servicio.
- **Riesgos:** Desalineación de configuraciones entre múltiples proxies independientes, lo que puede provocar brechas de seguridad por errores de despliegue manual.

## Decisión y Justificación (Rationale)
Se selecciona la **Opción 1: Arquitectura Basada en API Gateway Descentralizado con Envoltura Adapter / Strangler Fig para el Legado**.

### Justificación Técnica y Trazabilidad (SWEBOK v4.0):
1. **Atención a Restricciones y Descarte de Alternativas:**
   * La **Opción 2** queda totalmente descartada por violar la restricción de *Convivencia Temporal con Sistemas Heredados*, al exigir la reescritura de los módulos de autenticación en aplicaciones antiguas de biblioteca y aula virtual.
   * La **Opción 3** se descarta por introducir una complejidad operativa de orquestación de malla de infraestructura desproporcionada para el contexto universitario, incrementando innecesariamente el costo de mantenimiento.

2. **Aplicación de Tácticas Arquitectónicas (SWEBOK Cap. 02):**
   * **Proveedor de Identidad Centralizado (IdP):** Se establece Keycloak (o equivalente) como única fuente de verdad para identidades y roles institucionales (Estudiantes, Docentes, Administrativos), implementando **OIDC + OAuth 2.0 con PKCE**, lo que garantiza un SSO seguro tanto en navegadores web como en aplicaciones móviles nativas.
   * **API Gateway Offloading:** Se utiliza el API Gateway para interceptar las peticiones de los clientes, asumiendo la terminación TLS y la validación criptográfica de firmas de tokens JWT (vía JWKS) [SWEBOK-02-05]. Esto exonera a las APIs internas (Matrículas, Pagos) de la carga de validación y desacopla la seguridad de la lógica de negocio.
   * **Patrón Adapter / Strangler Fig:** Para atender la restricción del legado, el Gateway (o un adaptador dedicado en el borde) intercepta las peticiones dirigidas a sistemas antiguos, valida el JWT contra el IdP y traduce dicho contexto a cookies de sesión o cabeceras legacy. Esto permite una migración progresiva (*strangler pattern*) sin impacto en la experiencia del usuario final [SWEBOK-02-05].

3. **Supuestos Asumidos:**
   * Se asume que la universidad dispone o desplegará un directorio activo o LDAP central estructurado que servirá como repositorio subyacente para el IdP.
   * Se asume que el tráfico entre el API Gateway y las APIs internas se mantendrá dentro de una red privada virtual (VPC/DMZ) protegida.

## Consecuencias

### Positivas
- **Aislamiento y Centralización:** Eliminación completa del almacenamiento de credenciales en APIs de negocio independientes, reduciendo drásticamente la superficie de ataque [SWEBOK-02-05].
- **Experiencia de Usuario Unificada:** Logro de un Inicio de Sesión Único (SSO) transparente entre los canales móvil y web para todos los roles institucionales.
- **Cero Impacto al Legado:** Convivencia operativa inmediata con sistemas heredados sin necesidad de modificar su código fuente original.
- **Eficiencia en Desarrollo:** Las APIs de negocio modernas reciben peticiones previamente saneadas y autorizadas, simplificando su desarrollo.

### Negativas
- **SPOF en Infraestructura:** El clúster de API Gateway e IdP se convierten en un punto único de fallo crítico para el ecosistema universitario.
- **Sobrecarga de Red en el Borde:** Concentración del procesamiento de firmas criptográficas y traducción de tráfico en el borde.
- **Mantenimiento de Adaptadores:** Necesidad de mantener código de traducción temporal (*Adapters*) para cada sistema heredado integrado.

### Trade-offs y Riesgos Residuales
- **Trade-off Aceptado:** Se acepta la centralización de la seguridad en el borde (introduciendo un potencial cuello de botella) a cambio de no refactorizar los sistemas heredados y acelerar el tiempo de despliegue.
- **Riesgo Residual 1: Invalidación de Sesiones en Sistemas Heredados:** Existe el riesgo de que la revocación inmediata de un token en el IdP no invalide de forma síncrona la cookie traducida en el sistema heredado.
  * *Mitigación:* Configurar tiempos de vida (*TTL*) extremadamente cortos (ej. 5 a 15 minutos) en los adaptadores para las sesiones traducidas hacia el legado y forzar re-validaciones periódicas contra el IdP.
- **Riesgo Residual 2: Indisponibilidad del API Gateway / IdP:**
  * *Mitigación:* Desplegar el API Gateway y el IdP en un clúster con alta disponibilidad (HA), escalado automático horizontal y almacenamiento en caché distribuido para llaves públicas (JWKS).