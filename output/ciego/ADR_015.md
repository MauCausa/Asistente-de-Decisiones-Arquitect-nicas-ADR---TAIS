Este es el Registro de Decisión Arquitectónica (ADR) para la implementación de una solución de distribución de archivos multimedia en la plataforma educativa.

# ADR 08: Distribución de Archivos Multimedia mediante Almacenamiento de Objetos y CDN

## Estado
Propuesto

## Contexto
La plataforma educativa enfrenta problemas de saturación de disco y latencia en la transferencia de archivos debido a que el almacenamiento se gestiona localmente en el servidor web. Los archivos (videos y materiales descargables) son pesados (hasta 4 GB), lo que degrada el rendimiento del servidor principal. Además, la audiencia es global, lo que requiere una estrategia para reducir la latencia según la ubicación geográfica, manteniendo la capacidad de restringir el acceso a contenido privado.

## Decisión
Implementaremos una arquitectura de distribución basada en dos componentes principales de nube pública:

1.  **Almacenamiento de Objetos (Object Storage):** Utilizar un servicio como AWS S3, Google Cloud Storage o Azure Blob Storage para desacoplar los archivos del servidor web.
2.  **Red de Entrega de Contenido (CDN):** Implementar una CDN (ej. CloudFront, Cloudflare o Akamai) frente al almacenamiento de objetos para el almacenamiento en caché geográfico.
3.  **URLs Firmadas (Signed URLs):** Para el contenido privado, el servidor de aplicaciones generará tokens de acceso temporal (URLs firmadas) que permitan al usuario descargar o visualizar el contenido directamente desde la CDN/Storage sin pasar por el servidor web.

## Atributos de Calidad

*   **Escalabilidad de almacenamiento:** El almacenamiento de objetos es virtualmente ilimitado, eliminando la saturación del disco local.
*   **Rendimiento global:** La CDN reduce la latencia al servir el contenido desde nodos cercanos al usuario final (Edge locations).
*   **Control de acceso:** Las URLs firmadas garantizan que solo los usuarios autenticados y autorizados accedan a cursos específicos por un tiempo limitado.
*   **Disponibilidad:** Se reduce la carga en el servidor web, permitiendo que este se dedique exclusivamente a la lógica de negocio.

## Restricciones
*   **Tamaño de archivos:** Los servicios de almacenamiento de objetos soportan archivos de hasta 5 TB, cubriendo ampliamente el requisito de 4 GB.
*   **Costo:** Se debe configurar una política de ciclo de vida de datos para mover archivos antiguos a niveles de almacenamiento más económicos si es necesario.
*   **Seguridad:** El bucket de almacenamiento debe configurarse como "Privado", permitiendo el acceso únicamente a través de la CDN o mediante identidades de acceso específicas.

## Consecuencias

### Positivas
*   Mejora drástica en la velocidad de carga de videos para usuarios internacionales.
*   Eliminación del riesgo de caída del servidor por falta de espacio en disco.
*   Reducción de costos de transferencia de datos (Egress) al utilizar la infraestructura optimizada de la CDN.

### Negativas / Riesgos
*   **Complejidad técnica:** Requiere la implementación de lógica en el backend para la generación de firmas y gestión de permisos.
*   **Costo variable:** El costo dependerá del volumen de datos transferidos y almacenados (Pay-as-you-go).
*   **Propagación:** Los cambios en archivos existentes podrían tardar unos minutos en reflejarse globalmente a menos que se realice una invalidación de caché.

## Notas adicionales
Se recomienda el uso de **Multipart Upload** para los archivos de 4 GB para asegurar la integridad de la subida y permitir la reanudación en caso de fallos de red.