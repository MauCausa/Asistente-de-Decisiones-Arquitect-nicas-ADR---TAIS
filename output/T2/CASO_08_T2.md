# CASO_08 - Distribucion de archivos multimedia para una plataforma educativa

## Estado
Aceptado

## Contexto y Problema
La plataforma educativa actual enfrenta una crisis de escalabilidad y rendimiento debido a que el almacenamiento de videos y materiales descargables (de hasta 4 GB por archivo) se realiza de forma local en el servidor web. Esta arquitectura monolítica ha provocado saturación de disco, transferencias lentas para usuarios fuera de la región principal y una degradación general de la lógica de negocio al competir por recursos de E/S. El sistema requiere una solución que permita distribuir contenido pesado a nivel global, garantizando que los materiales privados solo sean accesibles por estudiantes autorizados mediante mecanismos temporales, eliminando la carga de transferencia del servidor de aplicaciones.

## Drivers de Decisión (ASRs)
*   **ASR-01: Escalabilidad de Almacenamiento:** Capacidad de almacenar volúmenes crecientes de datos sin depender de la capacidad física de un servidor individual.
*   **ASR-02: Rendimiento Global:** Minimización de la latencia y optimización del rendimiento de descarga para usuarios distribuidos en diversas regiones geográficas.
*   **ASR-03: Control de Acceso:** Garantía de que el contenido restringido solo sea accesible por usuarios con autorización vigente.
*   **Restricción 01:** Soporte para archivos de gran tamaño (hasta 4 GB).
*   **Restricción 02:** Despliegue obligatorio en infraestructura de nube pública.
*   **Restricción 03:** Autorización basada en acceso temporal.

## Opciones Consideradas

### Opción 1: Arquitectura Edge-Centric (Object Storage + CDN + Signed Cookies)
- **Descripción:** Almacenamiento en un servicio de objetos (S3/GCS) distribuido a través de una CDN. La autorización se gestiona mediante cookies firmadas emitidas por el backend, las cuales son validadas por los nodos de borde (Edge Nodes) de la CDN.
- **Ventajas:** Alta eficiencia de caché (múltiples usuarios autorizados comparten el mismo objeto en el borde), excelente rendimiento global y descarga total del tráfico del servidor web.
- **Desventajas:** Requiere configuración de dominios compartidos entre la aplicación y la CDN; mayor complejidad inicial en la gestión de políticas de seguridad de cookies.
- **Riesgos:** Posible "Session Hijacking" si no se implementan atributos de seguridad estrictos en las cookies.

### Opción 2: Arquitectura Direct-to-Storage (Object Storage + Presigned URLs)
- **Descripción:** El backend genera una URL firmada con una clave secreta y una expiración corta que apunta directamente al bucket de almacenamiento, saltándose la CDN para contenido privado.
- **Ventajas:** Implementación técnica sencilla y control de acceso granular por cada solicitud individual.
- **Desventajas:** Rendimiento geográfico pobre (latencia alta desde el origen), costos de egreso (egress) de datos más elevados desde el almacenamiento directo a internet.
- **Riesgos:** Las descargas de 4 GB pueden fallar si la URL expira antes de completar la transferencia, requiriendo lógica compleja de reintentos en el cliente.

### Opción 3: Arquitectura Hybrid Gateway (Storage Gateway + Proxies Regionales)
- **Descripción:** Despliegue de servidores proxy (Nginx/Varnish) en distintas regiones que actúan como caché intermedia frente al almacenamiento centralizado.
- **Ventajas:** Control total sobre la lógica de caché y potencial ahorro en costos de salida si el tráfico es altamente repetitivo.
- **Desventajas:** Alta carga operativa (IaaS); se traslada el problema de saturación de disco a los nuevos nodos proxy gestionados manualmente.
- **Riesgos:** Inconsistencia de datos entre regiones y fallos en la invalidación de caché manual.

## Decisión y Justificación (Rationale)
Se ha seleccionado la **Opción 1: Arquitectura Edge-Centric (Object Storage + CDN + Signed Cookies)**.

La decisión se fundamenta en los siguientes puntos alineados con el **SWEBOK v4.0 (Capítulo 02)**:
1.  **Separación de Responsabilidades [SWEBOK-02-10]:** El uso de **Object Storage** desacopla el almacenamiento de la lógica de cómputo, resolviendo el ASR-01 y eliminando la saturación de disco local.
2.  **Táctica de Rendimiento Geográfico:** La **CDN** es la única opción que satisface el ASR-02 para archivos de 4 GB, moviendo el contenido al borde de la red para reducir el TTFB (Time to First Byte).
3.  **Eficiencia de Caché vs. Seguridad:** A diferencia de las URLs firmadas (Opción 2), las **Signed Cookies** permiten que el contenido sea cacheable para diferentes usuarios autorizados en una misma región. Esto optimiza el ancho de banda y reduce costos, cumpliendo con el ASR-03 sin degradar el rendimiento.
4.  **Manejo de Archivos Grandes:** La combinación de CDN y Object Storage soporta nativamente **HTTP Range Requests**, permitiendo descargas pausables y reanudables de archivos de 4 GB, mitigando los riesgos de expiración de la Opción 2.
5.  **Supuestos:** Se asume que la plataforma educativa tiene control sobre el dominio principal para configurar subdominios que permitan el intercambio de cookies de forma segura.

## Consecuencias

### Positivas
*   **Escalabilidad Infinita:** El almacenamiento de objetos elimina los límites físicos de disco del servidor web.
*   **Experiencia de Usuario Superior:** Los videos cargan con baja latencia independientemente de la ubicación del estudiante.
*   **Reducción de Carga en Backend:** El servidor de aplicaciones solo procesa metadatos y firmas, no flujos de bytes pesados.

### Negativas
*   **Complejidad de Configuración:** Requiere gestionar la rotación de llaves de firma entre el backend y el proveedor de CDN.
*   **Dependencia del Proveedor (Vendor Lock-in):** La implementación de firmas de CDN suele ser específica de las APIs del proveedor de nube elegido.

### Trade-offs y Riesgos Residuales
*   **Costo vs. Rendimiento:** Se acepta un costo operativo por el servicio de CDN a cambio de una mejora drástica en el rendimiento global. Para mitigar costos excesivos, se deben configurar políticas de TTL (Time-to-Live) agresivas para contenidos que cambian con poca frecuencia.
*   **Riesgo de Seguridad en Cookies:** Existe el riesgo de que las cookies sean interceptadas. **Mitigación:** Implementación obligatoria de TLS 1.3, atributos `Secure`, `HttpOnly` y políticas de expiración de cookies de corta duración alineadas con la duración promedio de una sesión de estudio.