# Registro de Decisión Arquitectónica (ADR)

## Título: ADR-003: Implementación de un Servidor de Identidad Centralizado basado en OAuth 2.0 / OpenID Connect (OIDC) para la Plataforma Universitaria

* **Estado:** Aprobado
* **Fecha:** 2023-10-25
* **Autores:** Equipo de Arquitectura de Software
* **Contexto:** CASO_03 - Autenticación centralizada para APIs de una plataforma universitaria

---

## 1. Contexto y Problema

Actualmente, la plataforma universitaria cuenta con diversos sistemas independientes (Matrículas, Biblioteca, Pagos y Aula Virtual) que exponen sus propias APIs y gestionan sus credenciales/sesiones de forma aislada. 

Esta fragmentación genera los siguientes problemas:
* **Mala experiencia de usuario (UX):** Los estudiantes, docentes y personal administrativo deben autenticarse múltiples veces al navegar entre los diferentes servicios.
* **Riesgos de seguridad:** Duplicidad de credenciales, falta de visibilidad sobre la gestión de sesiones, políticas de contraseñas inconsistentes y una superficie de ataque ampliada.
* **Administración descentralizada:** Dificultad para revocar accesos o gestionar roles institucionales de forma uniforme.

Se requiere diseñar un esquema de autenticación y autorización unificado que resuelva estos problemas garantizando soporte para aplicaciones web y móviles, respetando la gobernanza de roles institucionales y permitiendo la convivencia temporal con sistemas heredados.

---

## 2. Drivers de Decisión (Atributos de Calidad y Requisitos)

* **Seguridad:** Protección de credenciales, emisión de tokens firmados y revocables, y cumplimiento de estándares de la industria.
* **Interoperabilidad:** Capacidad de integrar múltiples clientes (Web, Móvil) y APIs heterogéneas desarrolladas en distintas tecnologías.
* **Experiencia de usuario (SSO):** Proporcionar un flujo de Inicio de Sesión Único (Single Sign-On) transparente e integrado.
* **Gestión de Roles Centralizada:** Administración de permisos y roles institucionales (estudiante, docente, administrativo) en un único punto de verdad.

---

## 3. Restricciones Tecnológicas y de Negocio

* **Acceso Multicanal:** Debe dar soporte nativo a clientes de tipo Single Page Application (SPA), aplicaciones web tradicionales y aplicaciones móviles (iOS/Android).
* **Convivencia con Sistemas Heredados (Legacy):** La solución debe permitir una migración gradual sin exigir la reescritura inmediata de los sistemas antiguos.

---

## 4. Opciones Evaluadas

### Opción 1: Implementar un Proveedor de Identidad (IdP) Centralizado con OAuth 2.0 + OpenID Connect (OIDC) *(Opción Elegida)*
Desplegar un Servidor de Identidad centralizado (ej. Keycloak, Auth0 o Azure AD B2C) implementando el protocolo OIDC sobre OAuth 2.0. El IdP gestiona el almacenamiento/sincronización de usuarios (conectado a LDAP/Active Directory universitario), autentica centralizadamente y emite *Tokens de Acceso* (JWT) a las APIs backend.

* **Pros:**
  * Estándar de la industria para SSO, seguro y ampliamente probado.
  * Soporta todos los tipos de cliente (Web, Móvil) mediante flujos específicos como *Authorization Code Flow with PKCE*.
  * Desacopla la lógica de autenticación de las APIs del negocio.
  * Facilita la integración con sistemas heredados mediante *API Gateways* o adaptadores/proxies.
* **Contras:**
  * Introduce un punto único de fallo (SPOF) que requiere alta disponibilidad.
  * Curva de aprendizaje inicial para los equipos de desarrollo.

### Opción 2: Sistema Propio de Autenticación Basado en Tokens Propietarios / Base de Datos Compartida
Crear un microservicio a medida que gestione las credenciales en una base de datos centralizada y emita tokens JWT customizados para todas las APIs.

* **Pros:**
  * Control total sobre el código y la lógica de negocio.
  * Sin dependencia de soluciones/proveedores externos.
* **Contras:**
  * **Alto riesgo de seguridad:** Reinventar mecanismos de seguridad suele introducir vulnerabilidades (gestión de sesiones, revocación, etc.).
  * Alto costo de mantenimiento y desarrollo continuo.
  * Dificultad para integrar aplicaciones móviles de forma segura y estandarizada.

### Opción 3: Federación de Identidades Únicamente a Nivel de Base de Datos (Sincronización LDAP/DB)
Mantener la arquitectura de autenticación actual en cada API, pero sincronizar periódicamente las credenciales y roles desde un LDAP/Active Directory central a las bases de datos de cada aplicación.

* **Pros:**
  * Mínimo cambio en el código existente de cada aplicación.
* **Contras:**
  * **No ofrece SSO real:** El usuario sigue teniendo que ingresar sus credenciales en cada sistema.
  * La latencia en la sincronización puede generar inconsistencias en los datos de los usuarios.
  * No resuelve la seguridad en la capa de transmisión ni la gestión unificada de sesiones.

---

## 5. Decisión Arquitectónica

Se decide adoptar la **Opción 1: Implementar un Proveedor de Identidad Centralizado basado en OAuth 2.0 y OpenID Connect (OIDC)**.

### Detalles de la Implementación:
1. **Flujo de Autenticación:** Se utilizará el flujo **Authorization Code Flow con PKCE** (*Proof Key for Code Exchange*) para aplicaciones web SPA y aplicaciones móviles, garantizando la máxima seguridad.
2. **Formato de Tokens:** Se emitirán tokens **JSON Web Tokens (JWT)** firmados asimétricamente (RS256) que contendrán las demandas (*claims*) del usuario y sus roles institucionales.
3. **Gestión de Roles:** Los roles institucionales (estudiante, docente, administrativo) se gestionarán centralizadamente en el IdP/Directory Services y se incluirán dentro de los JWTs para que las APIs realicen la autorización (RBAC).
4. **Estrategia para Sistemas Heredados:** Para habilitar la convivencia temporal, se dispondrá de un **API Gateway** en la red universitaria. El Gateway validará el JWT centralizado y traducirá la identidad (mediante cabeceras HTTP o la inyección de una cookie legacy) para consumir las APIs de los sistemas antiguos que aún no soporten JWT de forma nativa.

---

## 6. Consecuencias y Mitigaciones

### Consecuencias Positivas:
* **UX Unificada:** Experiencia SSO fluida; el usuario se autentica una sola vez para acceder a Matrículas, Biblioteca, Pagos y Aula Virtual.
* **Seguridad Robusta:** Centralización de políticas de seguridad (MFA, políticas de contraseñas, auditoría) y eliminación del manejo directo de credenciales por parte de las APIs.
* **Escalabilidad e Interoperabilidad:** Nuevos módulos, servicios web o apps móviles podrán integrarse fácilmente adoptando el estándar OIDC.

### Consecuencias Negativas y Riesgos:
* **Punto Único de Fallo:** Si el IdP cae, ningún usuario podrá autenticarse en la plataforma.
  * *Mitigación:* Desplegar el IdP en un clúster de alta disponibilidad (HA) con réplicas de base de datos y balanceo de carga.
* **Complejidad en la Transición Legacy:**
  * *Mitigación:* Uso del patrón *Strangler Fig* respaldado por el API Gateway para migrar las APIs heredadas gradualmente a la validación nativa de JWT.
* **Gestión de Revocación de JWT:** Los JWTs son apátridas (*stateless*), lo que dificulta la invalidación inmediata antes de su expiración.
  * *Mitigación:* Configurar un tiempo de vida corto para los *Access Tokens* (ej. 5 a 15 minutos) y utilizar *Refresh Tokens* para la renovación transparente.