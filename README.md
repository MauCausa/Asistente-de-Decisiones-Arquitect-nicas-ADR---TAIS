# 🏛️ Asistente de Decisiones Arquitectónicas (ADR) Asistido por IA

**Universidad Nacional de San Agustín de Arequipa (UNSA)**  
**Facultad de Ingeniería de Producción y Servicios — Escuela Profesional de Ingeniería de Sistemas**  
**Curso:** Tópicos Avanzados en Ingeniería de Software (2026)  
**Docente:** Ing. Robert Edison Arisaca Mamani  

## Equipo de Investigación
- **Integrante 1:** Misael Josias Marron Lope *(Marco Teórico, Estado del Arte, Problemas/Objetivos y Edición General)*
- **Integrante 2:** Andre David Delgado Allpan *(Diseño Experimental, Operacionalización de Variables, Cronograma y Dataset de Casos)*
- **Integrante 3:** Mauricio Elias Congona Manrique *(Arquitectura del Prototipo, Stack Tecnológico, Orquestación IA/RAG y Ejecución Experimental)*
- **Integrante 4:** Javier Coronado Peña *(Evaluación Cuantitativa/Cualitativa, Análisis Estadístico, Resultados y Conclusiones)*

---

## 1. Descripción del Proyecto (Hito 2)

Este repositorio contiene el prototipo funcional y el pipeline de validación experimental de un **Asistente Híbrido de Decisiones Arquitectónicas (ADR)** basado en Modelos de Lenguaje Grandes (**Google Gemini API**) y Recuperación Aumentada por Generación (**RAG con ChromaDB y `all-MiniLM-L6-v2`**) fundamentado en el **Capítulo 02 (*Software Architecture*) del SWEBOK v4.0** y la plantilla formal **MADR (Markdown Architectural Decision Records)**.

### Diseño Experimental Pareado
Se comparan dos tratamientos sobre **12 escenarios reales de decisiones arquitectónicas** (`24 corridas` en total):
- **Tratamiento 1 (`T1` — Línea Base Zero-Shot Estándar):** Envío directo del problema arquitectónico al modelo de lenguaje solicitando un ADR sin estructura guiada ni recuperación de contexto.
- **Tratamiento 2 (`T2` — Propuesta: Asistente ADR Híbrido con Secuencia de Prompts + RAG):**
  1. **Etapa 1 (Análisis de ASRs y Recuperación RAG):** Identifica los *Architecturally Significant Requirements* (ASRs) y recupera tácticas/patrones del Capítulo 02 del SWEBOK v4.0 desde `ChromaDB`.
  2. **Etapa 2 (Exploración de Alternativas y "Abogado del Diablo"):** Obliga a proponer mínimo 3 alternativas viables y evalúa críticamente riesgos, deuda técnica potencial y concesiones (*trade-offs*).
  3. **Etapa 3 (Síntesis y Formateo MADR):** Consolida el documento bajo las 7 secciones obligatorias del estándar MADR.

---

## 2. Estructura del Repositorio

```text
├── anexos/
│   ├── Plantilla_MADR.md                # Plantilla formal MADR de 7 secciones obligatorias
│   └── Protocolo_Experimental.md        # Protocolo y controles experimentales
├── dataset/
│   └── escenarios_adr.json              # Dataset de 12 escenarios reales con ADR de referencia
├── knowledge_base/
│   └── swebok_cap02_corpus.json         # Corpus congelado del Capítulo 02 del SWEBOK v4.0 + MADR
├── src/
│   ├── __init__.py
│   ├── rag_engine.py                    # Indexación y búsqueda vectorial en ChromaDB (all-MiniLM-L6-v2)
│   ├── adr_assistant.py                 # Implementación de T1 (Zero-Shot) y T2 (Secuencia 3 Prompts + RAG)
│   └── app.py                           # Interfaz web interactiva en Streamlit
├── output/
│   ├── T1/                              # 12 ADRs generados con Tratamiento 1 (Zero-Shot)
│   ├── T2/                              # 12 ADRs generados con Tratamiento 2 (Propuesto)
│   └── ciego/                           # 24 ADRs codificados a ciegas (ADR_001 a ADR_024)
├── results/
│   ├── metricas_ejecucion.csv           # Latencia (TG), modelo, temperatura y metadatos de ejecución
│   ├── evaluacion_completa.csv          # CE, SS, C1-C6, CRA, alternativas y trade-offs de los 24 ADRs
│   ├── tabla_resultados_globales.csv    # Media, DE y resultados de Wilcoxon pareado (T1 vs T2)
│   └── figures/                         # Gráficos estadísticos (Barras agrupadas, Radar y Boxplots)
├── documento/                           # Entregables documentales del Hito 2 (.docx y .md)
├── experiment_runner.py                 # Script automatizado de las 24 corridas experimentales
├── test_estadistico.py                  # Evaluación cuantitativa, rúbrica y prueba de Wilcoxon
├── Diseno_Experimental_Hito2.xlsx       # Libro maestro de diseño experimental y evaluación ciega
└── requirements.txt                     # Dependencias reproducibles de Python 3.11+
```

---

## 3. Ejecución y Reproducibilidad

### 3.1 Instalación de dependencias
```bash
pip install -r requirements.txt
```

### 3.2 Configuración de variables de entorno
Crear un archivo `.env` en la raíz con la clave de Google AI Studio:
```env
GEMINI_API_KEY=tu_clave_aqui
GEMINI_MODEL=gemini-3.8-flash
```

### 3.3 Ejecutar las 24 corridas experimentales
```bash
python experiment_runner.py
```

### 3.4 Ejecutar la evaluación cuantitativa y pruebas estadísticas (Wilcoxon)
```bash
python test_estadistico.py
```

### 3.5 Iniciar la interfaz web interactiva (Streamlit)
```bash
streamlit run src/app.py
```
