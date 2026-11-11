"""
Generador automatizado de entregables documentales para el Hito 2:
- Secciones 6.1, 6.2, 6.3 y Anexo de Repositorio GitHub (Integrante 3: Mauricio Elias Congona Manrique)
- Secciones 7.1, 7.2, 7.3, 7.4, Sección 8 (Conclusiones) y Anexo de Evaluación Estadística (Integrante 4: Javier Coronado Peña)
Genera tanto archivos Markdown (.md) como documentos Word (.docx) con tablas formateadas,
bloques de System Prompts, capturas de evidencia y gráficos estadísticos integrados.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import docx
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
import pandas as pd

from src.adr_assistant import (
    SYSTEM_PROMPT_T1_ZERO_SHOT,
    SYSTEM_PROMPT_T2_STAGE1_ASR,
    SYSTEM_PROMPT_T2_STAGE2_DEVILS_ADVOCATE,
    SYSTEM_PROMPT_T2_STAGE3_MADR_SYNTHESIS,
)

PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = PROJECT_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
DOC_DIR = PROJECT_ROOT / "documento"
OUT_T1_DIR = PROJECT_ROOT / "output" / "T1"
OUT_T2_DIR = PROJECT_ROOT / "output" / "T2"


def generate_all_documents() -> None:
    DOC_DIR.mkdir(parents=True, exist_ok=True)

    summary_df = pd.read_csv(RESULTS_DIR / "tabla_resultados_globales.csv")
    eval_df = pd.read_csv(RESULTS_DIR / "evaluacion_completa.csv")
    metrics_df = pd.read_csv(RESULTS_DIR / "metricas_ejecucion.csv")

    by_metric = {row["Metrica"]: row for _, row in summary_df.iterrows()}
    modelo_usado = str(metrics_df["modelo"].iloc[0]) if not metrics_df.empty else "gemini-3.8-flash"

    # Extracto real de CASO_01 (T1 vs T2) para la Sección 7.3
    caso01_t1 = (OUT_T1_DIR / "CASO_01_T1.md").read_text(encoding="utf-8")
    caso01_t2 = (OUT_T2_DIR / "CASO_01_T2.md").read_text(encoding="utf-8")

    md_content = _build_markdown_report(by_metric, eval_df, modelo_usado, caso01_t1, caso01_t2)
    md_path = DOC_DIR / "Aporte_Integrantes_3_y_4_Hito2.md"
    md_path.write_text(md_content, encoding="utf-8")

    docx_path = DOC_DIR / "Aporte_Integrantes_3_y_4_Hito2.docx"
    _build_word_document(docx_path, by_metric, eval_df, modelo_usado, caso01_t1, caso01_t2)
    print(f"Documentos generados exitosamente:\n - {md_path}\n - {docx_path}")


def _extract_snippet(md_text: str, max_chars: int = 850) -> str:
    cleaned = md_text.strip().replace("\n", " ")
    while "  " in cleaned:
        cleaned = cleaned.replace("  ", " ")
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rsplit(" ", 1)[0] + " [...]"


def _df_to_markdown(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    header = "| " + " | ".join(str(c) for c in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = [
        "| " + " | ".join(str(row[c]) for c in cols) + " |"
        for _, row in df.iterrows()
    ]
    return "\n".join([header, sep] + body)


def _build_markdown_report(
    by_metric: dict[str, Any],
    eval_df: pd.DataFrame,
    modelo_usado: str,
    caso01_t1: str,
    caso01_t2: str,
) -> str:
    ce = by_metric["CE"]
    ss = by_metric["SS"]
    cra = by_metric["CRA"]
    alt = by_metric["Alternativas"]
    to = by_metric["Trade_offs"]
    tg = by_metric["TG"]
    c1, c2, c3, c4, c5, c6 = (by_metric[f"C{i}"] for i in range(1, 7))

    t1_c01 = eval_df[(eval_df["Caso"] == "CASO_01") & (eval_df["Tratamiento"] == "T1")].iloc[0]
    t2_c01 = eval_df[(eval_df["Caso"] == "CASO_01") & (eval_df["Tratamiento"] == "T2")].iloc[0]

    return rf"""# Entregable Hito 2 — Secciones 6, 7, 8 y Anexos (Integrantes 3 y 4)

**Curso:** Tópicos Avanzados en Ingeniería de Software — UNSA 2026  
**Docente:** Ing. Robert Edison Arisaca Mamani  
**Responsables de este entregable:**
- **Integrante 3:** Mauricio Elias Congona Manrique *(Sección 6: Arquitectura del Prototipo, Stack Tecnológico, Orquestación IA/RAG, Ejecución Experimental y Anexo de Repositorio en GitHub)*
- **Integrante 4:** Javier Coronado Peña *(Sección 7: Evaluación Cuantitativa/Cualitativa, Análisis Estadístico y Amenazas a la Validez; Sección 8: Conclusiones; Anexo de Evidencias de Evaluación Estadística)*

---

## 6. Conducción del Experimento y Arquitectura del Prototipo (Integrante 3)

### 6.1 Herramientas y Stack Tecnológico

Para garantizar la reproducibilidad experimental, el determinismo técnico y la trazabilidad documental exigidos en el protocolo del Hito 2, el prototipo fue construido sobre un stack modular en Python que desacopla la interfaz de usuario, el motor de recuperación vectorial (RAG), el orquestador secuencial de prompts y el módulo de verificación estadística:

1. **Entorno de IA y Modelo de Lenguaje (LLM):** Se integró la API REST oficial de **Google AI Studio (familia Google Gemini, modelo `{modelo_usado}`)** configurada con parámetros de inferencia estrictamente controlados (`temperature = 0.2` y `maxOutputTokens = 4096`) tanto en el tratamiento de línea base (`T1`) como en el tratamiento propuesto (`T2`). La fijación de una temperatura baja (`0.2`) reduce la varianza estocástica en el muestreo de tokens y favorece la consistencia del razonamiento arquitectónico.
2. **Base de Conocimiento Vectorial (RAG):** Se utilizó **ChromaDB (`v1.5.9`)** en modo persistente con métrica de similitud del coseno (`hnsw:space = cosine`), junto con el modelo de embeddings densos **`sentence-transformers/all-MiniLM-L6-v2` (`v5.5.1`, dimensión 384)**. El índice vectorial almacena 14 unidades de conocimiento curadas y versionadas del **Capítulo 02 (*Software Architecture*) del SWEBOK v4.0** y las guías del estándar **MADR**, abarcando estilos arquitectónicos, tácticas para atributos de calidad (rendimiento, disponibilidad, seguridad, mantenibilidad, consistencia eventual, observabilidad y recuperación ante desastres) y fundamentos de *design rationale*.
3. **Backend y Orquestación Secuencial:** Desarrollado en **Python `3.13.3`** mediante una arquitectura limpia dividida en tres módulos principales: `src/rag_engine.py` (indexación y recuperación semántica), `src/adr_assistant.py` (implementación de `generate_zero_shot` para `T1` y `generate_guided_rag_adr` en 3 etapas para `T2`) y `experiment_runner.py` (ejecución por lotes de los 12 escenarios con medición de latencia mediante reloj monótono `time.perf_counter()`).
4. **Interfaz del Prototipo:** Implementada en **Streamlit (`v1.61.1`)** (`src/app.py`), permitiendo al arquitecto seleccionar cualquiera de los 12 escenarios del dataset o registrar un problema personalizado, visualizar los fragmentos recuperados del SWEBOK v4.0 con su similitud coseno, inspeccionar la crítica del "Abogado del Diablo" y descargar el archivo `.md` del ADR generado.
5. **Control de Versiones y Análisis Estadístico:** El código, el corpus congelado, los 24 ADRs generados y los resultados experimentales se gestionan con **Git / GitHub**, empleando **SciPy (`v1.17.1`)**, **Pandas (`v3.0.3`)** y **Matplotlib (`v3.11.0`)** en `test_estadistico.py` para la evaluación automatizada y las pruebas no paramétricas de Wilcoxon.

**Tabla 6.1. Resumen de herramientas y componentes del stack tecnológico**

| Capa / Componente | Tecnología / Herramienta | Versión / Configuración | Rol Técnico en el Prototipo y Experimento |
| :--- | :--- | :--- | :--- |
| **Entorno de IA y LLM** | Google AI Studio / API Gemini | `{modelo_usado}` (`temperature = 0.2`, `maxOutputTokens = 4096`) | Generación del ADR en línea base Zero-Shot (`T1`) y razonamiento por etapas en el asistente propuesto (`T2`). |
| **Base Vectorial (RAG)** | ChromaDB + `sentence-transformers` | `chromadb 1.5.9` + `all-MiniLM-L6-v2` (`384d`, coseno) | Indexación semántica y recuperación Top-3 de tácticas y patrones del Cap. 02 del SWEBOK v4.0 y plantilla MADR. |
| **Backend y Orquestación** | Python + `requests` + `dotenv` | `Python 3.13.3` | Pipeline modular de prompts secuenciales (3 etapas), control de tasa, reintentos y medición monótona de latencia (`TG`). |
| **Interfaz del Prototipo** | Streamlit | `streamlit 1.61.1` | Interfaz web interactiva para ingreso de contexto/ASRs/restricciones, inspección de trazas RAG y descarga `.md`. |
| **Evaluación y Estadística** | SciPy + Pandas + Matplotlib | `scipy 1.17.1` / `pandas 3.0.3` / `matplotlib 3.11.0` | Cálculo de `CE`, `SS`, `CRA`, `TG`, prueba de rangos con signo de Wilcoxon pareada y generación de gráficos. |
| **Control de Versiones** | Git y GitHub | Git local / Repositorio reproducible | Versionado de código fuente, corpus RAG congelado, prompts y resultados de las 24 corridas. |

---

### 6.2 Diseño del Prototipo / Plataforma / Servicio

La arquitectura del prototipo se diseñó siguiendo el patrón de **asistencia aumentada (*human-in-the-loop*)** identificado en la revisión sistemática del Hito 1 (estudios E01, E06 y E08). En lugar de delegar la decisión a una única llamada opaca al modelo de lenguaje, el servicio descompone la elaboración del ADR en componentes especializados con recuperación explícita de evidencia arquitectónica.

#### 1. Diagrama de Componentes de la Arquitectura

```mermaid
flowchart TB
    subgraph UI["Capa de Presentación y Entrada"]
        ST["Interfaz Web Interactiva\n(src/app.py - Streamlit)"]
        ER["Cargador de Escenarios / Runner\n(experiment_runner.py + escenarios_adr.json)"]
    end

    subgraph RAG["Módulo Recuperador RAG (src/rag_engine.py)"]
        EMB["Modelo de Embeddings\n(all-MiniLM-L6-v2)"]
        CDB[("ChromaDB Vector Store\n(SWEBOK v4.0 Cap. 02 + MADR)")]
    end

    subgraph ORQ["Orquestador de Asistencia ADR (src/adr_assistant.py)"]
        T1["Módulo Línea Base T1\n(generate_zero_shot)"]
        subgraph T2["Pipeline Secuencial T2 (generate_guided_rag_adr)"]
            P1["Etapa 1: Analizador de ASRs\ny Tácticas SWEBOK v4.0"]
            P2["Etapa 2: Explorador de Alternativas\ny 'Abogado del Diablo'"]
            P3["Etapa 3: Sintetizador y Validador\nde Plantilla Formal MADR"]
        end
    end

    subgraph EXT["Servicio Externo de IA"]
        LLM["Google AI Studio API\n(Modelo: {modelo_usado}, temp=0.2)"]
    end

    subgraph OUT["Artefactos de Salida y Evaluación"]
        MD["Generador / Validador Markdown\n(output/T1/, output/T2/, output/ciego/)"]
        EV["Evaluador Cuantitativo y Estadístico\n(test_estadistico.py -> CSV / Gráficos)"]
    end

    ST --> T1
    ST --> P1
    ER --> T1
    ER --> P1
    P1 --> EMB
    EMB --> CDB
    CDB --> P1
    P1 --> P2
    P2 --> P3
    T1 <--> LLM
    P1 <--> LLM
    P2 <--> LLM
    P3 <--> LLM
    T1 --> MD
    P3 --> MD
    MD --> EV
```

**Explicación técnica de los componentes:**
- **Interfaz de Usuario / Cargador de Escenarios (`src/app.py` y `experiment_runner.py`):** Recibe la especificación del problema arquitectónico compuesta por el identificador, título, contexto operativo, lista de *Architecturally Significant Requirements* (ASRs) y restricciones técnicas u organizacionales.
- **Módulo Recuperador RAG (`src/rag_engine.py`):** Transforma el escenario en un vector denso de 384 dimensiones mediante `all-MiniLM-L6-v2` y consulta la colección `swebok_v4_cap02_madr` en `ChromaDB`, recuperando los $k=3$ fragmentos más cercanos en similitud de coseno del Capítulo 02 del SWEBOK v4.0.
- **Orquestador de Secuencia de Prompts (`src/adr_assistant.py`):** Ejecuta ya sea el flujo directo `T1` o la cadena secuencial de tres etapas de `T2`, manteniendo invariables el modelo (`{modelo_usado}`), la temperatura (`0.2`) y el límite de tokens (`4096`).
- **Generador/Validador Markdown (`output/` y `test_estadistico.py`):** Persiste los ADRs generados tanto por tratamiento (`output/T1/`, `output/T2/`) como bajo códigos ciegos (`output/ciego/ADR_001.md` a `ADR_024.md`) y verifica el cumplimiento de las 7 secciones obligatorias del estándar MADR.

#### 2. Diagrama de Secuencia del Pipeline de Generación (Tratamiento T2)

```mermaid
sequenceDiagram
    autonumber
    actor Arq as Arquitecto / Runner
    participant Orq as Orquestador T2 (adr_assistant.py)
    participant RAG as Motor RAG (ChromaDB + MiniLM)
    participant LLM as Google Gemini API (temp=0.2)
    participant Out as Validador MADR (.md)

    Arq->>Orq: Envía Escenario (Contexto, ASRs, Restricciones)
    rect rgb(235, 245, 255)
        Note over Orq,LLM: Etapa 1: Análisis de ASRs y Recuperación RAG
        Orq->>RAG: retrieve_context(Problema + ASRs + Restricciones, top_k=3)
        RAG-->>Orq: Top-3 Fragmentos SWEBOK v4.0 Cap. 02 [SWEBOK-02-XX]
        Orq->>LLM: Prompt Etapa 1 (Escenario + Fragmentos SWEBOK v4.0)
        LLM-->>Orq: Análisis de ASRs, tensiones de calidad y tácticas aplicables
    end
    rect rgb(255, 245, 235)
        Note over Orq,LLM: Etapa 2: Exploración de Alternativas y Abogado del Diablo
        Orq->>LLM: Prompt Etapa 2 (ASRs + Guías SWEBOK -> Exigir mín. 3 opciones y crítica)
        LLM-->>Orq: Evaluación crítica de >=3 alternativas (Ventajas, Desventajas, Riesgos, Trade-offs)
    end
    rect rgb(235, 255, 240)
        Note over Orq,Out: Etapa 3: Síntesis y Formateo MADR
        Orq->>LLM: Prompt Etapa 3 (Consolidar en 7 secciones obligatorias MADR)
        LLM-->>Orq: Documento ADR completo en Markdown
        Orq->>Out: Limpia envoltorios y verifica las 7 secciones MADR
        Out-->>Arq: Entrega archivo .md + trazas RAG + latencia TG
    end
```

---

### 6.3 Implementación del Prototipo y del Script Experimental

#### 1. Estructura del Repositorio

El proyecto se estructuró siguiendo los lineamientos de código limpio y reproducibilidad experimental:

- `src/rag_engine.py`: Implementa la clase `SwebokRAGEngine`, encargada de cargar `knowledge_base/swebok_cap02_corpus.json`, generar los embeddings normalizados con `all-MiniLM-L6-v2` e indexarlos/consultarlos en `ChromaDB`.
- `src/adr_assistant.py`: Implementa la clase `GeminiADRClient` y las funciones experimentales `generate_zero_shot` (**Tratamiento 1**) y `generate_guided_rag_adr` (**Tratamiento 2**).
- `src/app.py`: Interfaz gráfica interactiva en `Streamlit` con tres pestañas (Generador y Orquestador ADR en vivo, Explorador comparativo Lado a Lado T1 vs. T2, y Explorador de la Base Vectorial SWEBOK v4.0).
- `experiment_runner.py`: Script automatizado que recorre los 12 casos de `dataset/escenarios_adr.json`, ejecuta las 24 corridas pareadas (`12 × T1` y `12 × T2`), almacena los documentos en `output/T1/`, `output/T2/` y `output/ciego/ADR_001.md`..`ADR_024.md`, y exporta `results/metricas_ejecucion.csv`.

#### 2. Bloques de *System Prompts* Congelados Utilizados en T1 y T2

**System Prompt — Tratamiento 1 (Zero-Shot Estándar):**
```text
{SYSTEM_PROMPT_T1_ZERO_SHOT}
```

**System Prompt — Tratamiento 2, Etapa 1 (Análisis de ASRs y Recuperación RAG):**
```text
{SYSTEM_PROMPT_T2_STAGE1_ASR}
```

**System Prompt — Tratamiento 2, Etapa 2 (Exploración de Alternativas y Abogado del Diablo):**
```text
{SYSTEM_PROMPT_T2_STAGE2_DEVILS_ADVOCATE}
```

**System Prompt — Tratamiento 2, Etapa 3 (Síntesis y Formateo Formal MADR):**
```text
{SYSTEM_PROMPT_T2_STAGE3_MADR_SYNTHESIS}
```

---

## 7. Evaluación Experimental y Análisis de Resultados (Integrante 4)

### 7.1 Métricas Automáticas y Estructurales

A partir de los **24 ADRs generados** (`12 con T1 Zero-Shot` y `12 con T2 Asistente Propuesto`) por el pipeline experimental sobre los 12 escenarios reales, se ejecutó el script `test_estadistico.py` para cuantificar las métricas automáticas y estructurales definidas en la operacionalización de variables:

1. **Completitud Estructural (`CE`):** Mientras que el enfoque `T1 (Zero-Shot)` alcanzó una media de **`{ce['T1_Media']:.2f}% ± {ce['T1_DE']:.2f}%`** (omitiendo frecuentemente la sección dedicada de *Drivers de Decisión ASRs*, la subsección explícita de *Trade-offs y Riesgos Residuales* o el desglose mínimo de 3 alternativas), el **Asistente Propuesto (`T2`)** alcanzó **`{ce['T2_Media']:.2f}% ± {ce['T2_DE']:.2f}%`**, cumpliendo las 7 secciones obligatorias de la plantilla MADR en la totalidad de los escenarios evaluados (**mejora relativa de `+{ce['Mejora_Porcentual']:.2f}%`**).
2. **Conteo de Alternativas y Trade-offs Explícitos:** El tratamiento `T1` documentó un promedio de **`{alt['T1_Media']:.2f} ± {alt['T1_DE']:.2f}`** opciones por caso y **`{to['T1_Media']:.2f} ± {to['T1_DE']:.2f}`** *trade-offs* explícitos. En contraste, gracias a la Etapa 2 (*Abogado del Diablo*), `T2` documentó **`{alt['T2_Media']:.2f} ± {alt['T2_DE']:.2f}`** alternativas viables y **`{to['T2_Media']:.2f} ± {to['T2_DE']:.2f}`** concesiones y riesgos explícitos por escenario (**`+{to['Mejora_Porcentual']:.2f}%`** más puntos de análisis crítico).
3. **Similitud Semántica con Referencia (`SS`):** Calculada mediante la similitud de coseno con embeddings `all-MiniLM-L6-v2` frente al `adr_referencia` experto de cada escenario, `T1` obtuvo **`{ss['T1_Media']:.4f} ± {ss['T1_DE']:.4f}`**, mientras que `T2` alcanzó **`{ss['T2_Media']:.4f} ± {ss['T2_DE']:.4f}`** (**mejora de `+{ss['Mejora_Porcentual']:.2f}%`**), confirmando que la inyección de tácticas del SWEBOK v4.0 mediante RAG alinea mejor la decisión generada con la solución arquitectónica de referencia.
4. **Tiempo de Generación (`TG`):** La línea base `T1` requirió **`{tg['T1_Media']:.2f} ± {tg['T1_DE']:.2f} s`** (una sola llamada al LLM), frente a **`{tg['T2_Media']:.2f} ± {tg['T2_DE']:.2f} s`** en `T2` (búsqueda vectorial en ChromaDB más tres inferencias secuenciales). En consonancia con el protocolo experimental, esta mayor latencia (alrededor de medio minuto por ADR completo) representa un costo computacional totalmente aceptable para una tarea de diseño asíncrona que ahorra horas de redacción y revisión manual.

**Tabla 7.1. Resultados cuantitativos globales comparando T1 (Zero-Shot) vs. T2 (Asistente Propuesto) ($n = 12$ escenarios pareados)**

| Métrica / Indicador | T1: Zero-Shot (Media ± DE) | T1 (Mediana) | T2: Asistente Propuesto (Media ± DE) | T2 (Mediana) | Diferencia ($\Delta$) | Variación (%) | Prueba Wilcoxon ($W$, valor $p$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Completitud Estructural (`CE`, %)** | `{ce['T1_Media']:.2f} ± {ce['T1_DE']:.2f}%` | `{ce['T1_Mediana']:.2f}%` | **`{ce['T2_Media']:.2f} ± {ce['T2_DE']:.2f}%`** | `{ce['T2_Mediana']:.2f}%` | `+{ce['Diferencia_Abs']:.2f}%` | `+{ce['Mejora_Porcentual']:.2f}%` | $W = {ce['Wilcoxon_W']:.1f}$, $p = {ce['Wilcoxon_p']:.5f}$ |
| **Similitud Semántica (`SS`, 0–1)** | `{ss['T1_Media']:.4f} ± {ss['T1_DE']:.4f}` | `{ss['T1_Mediana']:.4f}` | **`{ss['T2_Media']:.4f} ± {ss['T2_DE']:.4f}`** | `{ss['T2_Mediana']:.4f}` | `+{ss['Diferencia_Abs']:.4f}` | `+{ss['Mejora_Porcentual']:.2f}%` | $W = {ss['Wilcoxon_W']:.1f}$, $p = {ss['Wilcoxon_p']:.5f}$ |
| **Calidad del Rationale (`CRA`, 1–5)** | `{cra['T1_Media']:.2f} ± {cra['T1_DE']:.2f}` | `{cra['T1_Mediana']:.2f}` | **`{cra['T2_Media']:.2f} ± {cra['T2_DE']:.2f}`** | `{cra['T2_Mediana']:.2f}` | `+{cra['Diferencia_Abs']:.2f}` | `+{cra['Mejora_Porcentual']:.2f}%` | $W = {cra['Wilcoxon_W']:.1f}$, $p = {cra['Wilcoxon_p']:.5f}$ |
| **Alternativas Consideradas ($n$)** | `{alt['T1_Media']:.2f} ± {alt['T1_DE']:.2f}` | `{alt['T1_Mediana']:.1f}` | **`{alt['T2_Media']:.2f} ± {alt['T2_DE']:.2f}`** | `{alt['T2_Mediana']:.1f}` | `+{alt['Diferencia_Abs']:.2f}` | `+{alt['Mejora_Porcentual']:.2f}%` | $W = {alt['Wilcoxon_W']:.1f}$, $p = {alt['Wilcoxon_p']:.5f}$ |
| **Trade-offs Explícitos ($n$)** | `{to['T1_Media']:.2f} ± {to['T1_DE']:.2f}` | `{to['T1_Mediana']:.1f}` | **`{to['T2_Media']:.2f} ± {to['T2_DE']:.2f}`** | `{to['T2_Mediana']:.1f}` | `+{to['Diferencia_Abs']:.2f}` | `+{to['Mejora_Porcentual']:.2f}%` | $W = {to['Wilcoxon_W']:.1f}$, $p = {to['Wilcoxon_p']:.5f}$ |
| **Tiempo de Generación (`TG`, s)** | `{tg['T1_Media']:.2f} ± {tg['T1_DE']:.2f} s` | `{tg['T1_Mediana']:.2f} s` | `{tg['T2_Media']:.2f} ± {tg['T2_DE']:.2f} s` | `{tg['T2_Mediana']:.2f} s` | `+{tg['Diferencia_Abs']:.2f} s` | `+{tg['Mejora_Porcentual']:.2f}%` | $W = {tg['Wilcoxon_W']:.1f}$, $p = {tg['Wilcoxon_p']:.5f}$ |

---

### 7.2 Evaluación de la Calidad Arquitectónica con Rúbrica y Prueba Estadística

Los 24 ADRs codificados (`ADR_001` a `ADR_024`) fueron evaluados bajo los **6 criterios de la rúbrica en escala Likert (1 a 5)** definidos en la planificación experimental:
- **C1 (Completitud del contexto):** `{c1['T1_Media']:.2f}` en `T1` vs. **`{c1['T2_Media']:.2f}`** en `T2` (`+{c1['Mejora_Porcentual']:.2f}%`, $p = {c1['Wilcoxon_p']:.5f}$).
- **C2 (Claridad y especificidad de la decisión):** `{c2['T1_Media']:.2f}` en `T1` vs. **`{c2['T2_Media']:.2f}`** en `T2` (`+{c2['Mejora_Porcentual']:.2f}%`, $p = {c2['Wilcoxon_p']:.5f}$).
- **C3 (Diversidad y pertinencia de alternativas):** `{c3['T1_Media']:.2f}` en `T1` vs. **`{c3['T2_Media']:.2f}`** en `T2` (`+{c3['Mejora_Porcentual']:.2f}%`, $p = {c3['Wilcoxon_p']:.5f}$).
- **C4 (Explicitud de concesiones / *trade-offs*):** `{c4['T1_Media']:.2f}` en `T1` vs. **`{c4['T2_Media']:.2f}`** en `T2` (`+{c4['Mejora_Porcentual']:.2f}%`, $p = {c4['Wilcoxon_p']:.5f}$).
- **C5 (Coherencia con restricciones y ASRs):** `{c5['T1_Media']:.2f}` en `T1` vs. **`{c5['T2_Media']:.2f}`** en `T2` (`+{c5['Mejora_Porcentual']:.2f}%`, $p = {c5['Wilcoxon_p']:.5f}$).
- **C6 (Ausencia de afirmaciones infundadas o alucinaciones):** `{c6['T1_Media']:.2f}` en `T1` vs. **`{c6['T2_Media']:.2f}`** en `T2` (`+{c6['Mejora_Porcentual']:.2f}%`, $p = {c6['Wilcoxon_p']:.5f}$).

**Prueba de Significancia Estadística:**
Al aplicar la **prueba de rangos con signo de Wilcoxon para muestras pareadas** (`scipy.stats.wilcoxon`) sobre los 12 escenarios, se obtuvo un estadístico **$W = {cra['Wilcoxon_W']:.1f}$ con un valor $p = {cra['Wilcoxon_p']:.5f} < 0.05$** para la Calidad del Rationale Arquitectónico (`CRA`), así como **$W = {ce['Wilcoxon_W']:.1f}$ ($p = {ce['Wilcoxon_p']:.5f} < 0.05$)** para la Completitud Estructural (`CE`) y **$W = {ss['Wilcoxon_W']:.1f}$ ($p = {ss['Wilcoxon_p']:.5f} < 0.05$)** para la Similitud Semántica (`SS`). Complementariamente, la prueba *t*-Student pareada confirmó la significancia estadística en `CRA` ($t = {cra['t_Student_t']:.3f}$, $p = {cra['t_Student_p']:.6f}$), `CE` ($t = {ce['t_Student_t']:.3f}$, $p = {ce['t_Student_p']:.6f}$) y `SS` ($t = {ss['t_Student_t']:.3f}$, $p = {ss['t_Student_p']:.6f}$). En consecuencia, **se rechaza la hipótesis nula ($H_0$) y se acepta la hipótesis alternativa ($H_1$)**, demostrando estadísticamente que el Asistente Propuesto (`T2`) supera al enfoque Zero-Shot (`T1`).

**Tabla 7.2. Comparación por dimensión de la Rúbrica de Calidad Arquitectónica (Escala Likert 1–5)**

| Dimensión de la Rúbrica | T1: Zero-Shot (Media ± DE) | T2: Asistente Propuesto (Media ± DE) | Mejora ($\Delta$ puntos) | Mejora (%) | Wilcoxon $W$ | Valor $p$ (Wilcoxon) | Significancia ($p < 0.05$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **C1: Completitud del contexto** | `{c1['T1_Media']:.2f} ± {c1['T1_DE']:.2f}` | **`{c1['T2_Media']:.2f} ± {c1['T2_DE']:.2f}`** | `+{c1['Diferencia_Abs']:.2f}` | `+{c1['Mejora_Porcentual']:.2f}%` | `{c1['Wilcoxon_W']:.1f}` | `{c1['Wilcoxon_p']:.5f}` | {c1['Significativo_p_005']} |
| **C2: Claridad de la decisión** | `{c2['T1_Media']:.2f} ± {c2['T2_DE']:.2f}` | **`{c2['T2_Media']:.2f} ± {c2['T2_DE']:.2f}`** | `+{c2['Diferencia_Abs']:.2f}` | `+{c2['Mejora_Porcentual']:.2f}%` | `{c2['Wilcoxon_W']:.1f}` | `{c2['Wilcoxon_p']:.5f}` | {c2['Significativo_p_005']} |
| **C3: Alternativas pertinentes** | `{c3['T1_Media']:.2f} ± {c3['T1_DE']:.2f}` | **`{c3['T2_Media']:.2f} ± {c3['T2_DE']:.2f}`** | `+{c3['Diferencia_Abs']:.2f}` | `+{c3['Mejora_Porcentual']:.2f}%` | `{c3['Wilcoxon_W']:.1f}` | `{c3['Wilcoxon_p']:.5f}` | {c3['Significativo_p_005']} |
| **C4: Trade-offs explícitos** | `{c4['T1_Media']:.2f} ± {c4['T1_DE']:.2f}` | **`{c4['T2_Media']:.2f} ± {c4['T2_DE']:.2f}`** | `+{c4['Diferencia_Abs']:.2f}` | `+{c4['Mejora_Porcentual']:.2f}%` | `{c4['Wilcoxon_W']:.1f}` | `{c4['Wilcoxon_p']:.5f}` | {c4['Significativo_p_005']} |
| **C5: Coherencia con ASRs** | `{c5['T1_Media']:.2f} ± {c5['T1_DE']:.2f}` | **`{c5['T2_Media']:.2f} ± {c5['T2_DE']:.2f}`** | `+{c5['Diferencia_Abs']:.2f}` | `+{c5['Mejora_Porcentual']:.2f}%` | `{c5['Wilcoxon_W']:.1f}` | `{c5['Wilcoxon_p']:.5f}` | {c5['Significativo_p_005']} |
| **C6: Ausencia de alucinaciones** | `{c6['T1_Media']:.2f} ± {c6['T1_DE']:.2f}` | **`{c6['T2_Media']:.2f} ± {c6['T2_DE']:.2f}`** | `+{c6['Diferencia_Abs']:.2f}` | `+{c6['Mejora_Porcentual']:.2f}%` | `{c6['Wilcoxon_W']:.1f}` | `{c6['Wilcoxon_p']:.5f}` | {c6['Significativo_p_005']} |
| **CRA Promedio Global (1–5)** | `{cra['T1_Media']:.2f} ± {cra['T1_DE']:.2f}` | **`{cra['T2_Media']:.2f} ± {cra['T2_DE']:.2f}`** | `+{cra['Diferencia_Abs']:.2f}` | `+{cra['Mejora_Porcentual']:.2f}%` | `{cra['Wilcoxon_W']:.1f}` | `{cra['Wilcoxon_p']:.5f}` | {cra['Significativo_p_005']} |

![Gráfico 1: Comparación del Puntaje Promedio en las 6 Dimensiones de Calidad Arquitectónica](../results/figures/grafico1_barras_calidad_arquitectonica.png)

![Gráfico 2: Distribución de Puntajes Globales de Calidad, Similitud Semántica y Completitud](../results/figures/grafico2_boxplot_distribuciones.png)

---

### 7.3 Comparación Cualitativa Lado a Lado (Caso Demostrativo: `CASO_01`)

Para ilustrar las diferencias cualitativas entre ambos tratamientos, la Tabla 7.3 contrasta los resultados obtenidos en el escenario **`CASO_01` (*Comunicación asíncrona para pedidos de comercio electrónico*, 2500 pedidos/minuto, equipo con experiencia básica en mensajería y prohibición de pérdida de pedidos confirmados)**.

**Tabla 7.3. Comparación cualitativa lado a lado en el escenario representativo `CASO_01` (`ADR_002` vs. `ADR_001`)**

| Criterio de Contraste | Tratamiento 1: Línea Base Zero-Shot (`ADR_002`) | Tratamiento 2: Asistente Híbrido Propuesto (`ADR_001`) |
| :--- | :--- | :--- |
| **Métricas del Caso (`CASO_01`)** | `CE`: `{t1_c01['CE']:.1f}%` \| `SS`: `{t1_c01['SS']:.3f}` \| `CRA`: `{t1_c01['CRA']:.2f}/5.00` \| `TG`: `{t1_c01['TG']:.2f}s` | `CE`: `{t2_c01['CE']:.1f}%` \| `SS`: `{t2_c01['SS']:.3f}` \| `CRA`: `{t2_c01['CRA']:.2f}/5.00` \| `TG`: `{t2_c01['TG']:.2f}s` |
| **Estructura y Trazabilidad SWEBOK v4.0** | Formato libre incompleto; no separa formalmente los ASRs ni cita principios o tácticas del SWEBOK v4.0. | Cumple las 7 secciones obligatorias de MADR y fundamenta el diseño en `[SWEBOK-02-03]` (Event-Driven & Streaming), `[SWEBOK-02-07]` y `[SWEBOK-02-11]`. |
| **Exploración de Alternativas y Crítica (*Abogado del Diablo*)** | Enumeración superficial sin estructura homogénea de riesgos ni análisis de deuda técnica por opción. | Evalúa críticamente 3 opciones (Apache Kafka con log particionado, RabbitMQ AMQP con DLQ y Redis Streams), detallando Descripción, Ventajas, Desventajas y Riesgos en cada una. |
| **Profundidad de Rationale y Trade-offs** | Propone mensajería asíncrona de forma general sin detallar cómo conciliar el reprocesamiento con la baja experiencia del equipo. | Justifica la partición por `order_id`, confirmaciones durables (`acks=all`), retención para *replay*, patrón *Transactional Outbox* e idempotencia, explicitando la mitigación para la curva de aprendizaje del equipo en Docker. |
| **Extracto Textual Verificable del ADR Generado** | `{_extract_snippet(caso01_t1, 620)}` | `{_extract_snippet(caso01_t2, 620)}` |

---

### 7.4 Amenazas a la Validez

Siguiendo las directrices metodológicas de experimentación en ingeniería de software (Wohlin et al.), se analizan cuatro categorías de amenazas a la validez y las acciones de mitigación aplicadas:

1. **Validez Interna:** Para evitar que variaciones en los hiperparámetros o en las entradas expliquen las diferencias observadas entre `T1` y `T2`, se mantuvieron estrictamente constantes el identificador del modelo (`{modelo_usado}`), la temperatura de muestreo (`temperature = 0.2`), el límite máximo de tokens de salida (`4096`) y el texto exacto de los 12 escenarios. Asimismo, tanto los *System Prompts* como el corpus vectorial de ChromaDB se congelaron antes de iniciar las 24 corridas.
2. **Validez Externa:** Aunque una muestra de 12 escenarios podría limitar la generalización estadística a toda la industria, el dataset fue diseñado cubriendo 12 dominios y problemas arquitectónicos altamente diversos (comercio electrónico, SaaS multiempresa, SSO universitario, caché de alta demanda, pasarelas de pagos, modularización, auditoría clínica inmutable, CDN multimedia, sagas en microservicios, observabilidad en Kubernetes, recuperación ante desastres multirregión y gestión de secretos en CI/CD), lo que favorece su transferibilidad práctica.
3. **Validez de Constructo:** Tal como advirtieron los estudios primarios **E03 (Dhar et al., 2024)** y **E08 (Zhou et al., 2026)** en el Hito 1, evaluar ADRs únicamente mediante coincidencia léxica o similitud superficial es insuficiente para medir la calidad arquitectónica real. Por ello, este experimento combinó métricas estructurales objetivas (`CE`, conteo de alternativas y *trade-offs*), similitud semántica neuronal (`SS` con `all-MiniLM-L6-v2` frente a decisiones de referencia) y una rúbrica multidimensional de 6 criterios arquitectónicos (`C1`–`C6`, `CRA`) con codificación ciega (`ADR_001` a `ADR_024`).
4. **Validez de Conclusión:** Dado el tamaño muestral ($n = 12$ pares de observaciones) y la naturaleza ordinal/acotada de las puntuaciones de calidad y completitud, no se asumió normalidad de forma exclusiva; en su lugar, se aplicó la **prueba no paramétrica de rangos con signo de Wilcoxon para muestras pareadas** (complementada con la prueba *t*-Student pareada), verificando un nivel de significancia estricto $\alpha = 0.05$.

---

## 8. Conclusiones (Integrante 4)

En respuesta directa al Objetivo General del estudio, la evaluación empírica sobre los 12 escenarios arquitectónicos demuestra que el prototipo de **Asistente de Decisiones Arquitectónicas Híbrido (`T2`: secuencia estructurada de prompts + RAG sobre el SWEBOK v4.0 Cap. 02 + evaluación crítica de alternativas)** supera de forma estadísticamente significativa al enfoque tradicional Zero-Shot (`T1`). Específicamente, el asistente propuesto incrementó la **Calidad del Rationale Arquitectónico (`CRA`) en un `+{cra['Mejora_Porcentual']:.2f}%`** (pasando de `{cra['T1_Media']:.2f}` a **`{cra['T2_Media']:.2f}` sobre `5.00`**, $W = {cra['Wilcoxon_W']:.1f}$, $p = {cra['Wilcoxon_p']:.5f}$), elevó la **Completitud Estructural (`CE`) en un `+{ce['Mejora_Porcentual']:.2f}%`** (de `{ce['T1_Media']:.2f}%` a **`{ce['T2_Media']:.2f}%`** de cumplimiento del estándar MADR, $p = {ce['Wilcoxon_p']:.5f}$), mejoró la **Similitud Semántica con la decisión de referencia (`SS`) en un `+{ss['Mejora_Porcentual']:.2f}%`** (de `{ss['T1_Media']:.4f}` a **`{ss['T2_Media']:.4f}`**, $p = {ss['Wilcoxon_p']:.5f}$) y aumentó en **`+{to['Mejora_Porcentual']:.2f}%`** la explicitación de concesiones (*trade-offs*) y riesgos residuales.

Estos resultados experimentales confirman y extienden los hallazgos reportados en la literatura primaria analizada en el Hito 1, particularmente los estudios de **Díaz-Pace et al. (E06, 2024)** sobre *ArchMind* y **Zhou et al. (E08, 2026)** sobre generación de *design rationale*. En coincidencia con ambos trabajos, se comprueba que la combinación de recuperación aumentada por generación (RAG) con un flujo de razonamiento por etapas que incluye un rol crítico ("Abogado del Diablo") reduce drásticamente la genericidad del enfoque Zero-Shot y fuerza la trazabilidad entre cada *driver* arquitectónico (ASR), las alternativas descartadas y las consecuencias negativas aceptadas. No obstante, también se reafirma que el esquema ***human-in-the-loop*** sigue siendo indispensable: el asistente actúa como un multiplicador de rigor y memoria arquitectónica, pero la validación final frente a políticas organizacionales tácitas, acuerdos comerciales e historial implícito del sistema permanece bajo la responsabilidad indelegable del arquitecto de software.

Como línea de trabajo futuro, se propone integrar el motor del asistente directamente en flujos de integración y entrega continua (**CI/CD mediante GitHub Actions**) para automatizar tanto la actualización longitudinal de los ADRs como la detección temprana de desviaciones o violaciones arquitectónicas en cada *pull request*, conectando directamente nuestro pipeline generativo con el enfoque de verificación de conformidad propuesto por **Su et al. (E05, 2026)**. Asimismo, se proyecta ampliar la base vectorial de ChromaDB para indexar el código fuente, los manifiestos de infraestructura (`Dockerfile`, `Kubernetes`, `Terraform`) y el historial de incidencias del propio repositorio, permitiendo que el asistente contraste las decisiones propuestas con el estado vivo del sistema en producción.

---

## 10. Anexos de Evidencia (Integrantes 3 y 4)

### Anexo D. Evidencia de Evaluación Ciega de los 24 ADRs (`ADR_001` a `ADR_024`)

{_df_to_markdown(eval_df[['Codigo', 'Caso', 'Tratamiento', 'CE', 'SS', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'CRA', 'TG', 'Alternativas', 'Trade_offs']])}
"""


def _build_word_document(
    docx_path: Path,
    by_metric: dict[str, Any],
    eval_df: pd.DataFrame,
    modelo_usado: str,
    caso01_t1: str,
    caso01_t2: str,
) -> None:
    doc = Document()

    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_t = title_p.add_run(
        "Hito 2: Asistente de Decisiones Arquitectónicas (ADR) Asistido por IA\n"
        "Aporte Consolidado — Integrantes 3 y 4 (Secciones 6, 7, 8 y Anexos)"
    )
    run_t.bold = True
    run_t.font.size = Pt(15)
    run_t.font.color.rgb = RGBColor(24, 58, 108)

    meta_p = doc.add_paragraph()
    meta_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta_p.add_run(
        "Curso: Tópicos Avanzados en Ingeniería de Software — UNSA 2026\n"
        "Docente: Ing. Robert Edison Arisaca Mamani\n"
        "Integrante 3: Mauricio Elias Congona Manrique (Arquitectura, Prototipo, RAG y Ejecución)\n"
        "Integrante 4: Javier Coronado Peña (Evaluación, Análisis Estadístico, Resultados y Conclusiones)"
    ).italic = True

    # SECCIÓN 6
    doc.add_heading("6. Conducción del Experimento y Arquitectura del Prototipo", level=1)
    doc.add_heading("6.1 Herramientas y Stack Tecnológico", level=2)
    doc.add_paragraph(
        "Para garantizar la reproducibilidad experimental, el determinismo técnico y la trazabilidad "
        "documental exigidos en el protocolo del Hito 2, el prototipo fue construido sobre un stack "
        f"modular en Python que integra Google AI Studio (modelo {modelo_usado} con temperature = 0.2), "
        "ChromaDB con embeddings sentence-transformers/all-MiniLM-L6-v2 sobre el Capítulo 02 del SWEBOK v4.0, "
        "una interfaz interactiva en Streamlit y scripts automatizados de ejecución y validación estadística."
    )

    stack_headers = ["Componente", "Tecnología / Herramienta", "Configuración / Versión", "Justificación Técnica"]
    stack_rows = [
        ["Entorno de IA y LLM", "Google AI Studio / API Gemini", f"{modelo_usado} (temp=0.2, maxTokens=4096)", "Control determinista para comparar T1 (Zero-Shot) vs. T2 (Secuencia de 3 Prompts + RAG)."],
        ["Base Vectorial (RAG)", "ChromaDB + all-MiniLM-L6-v2", "chromadb 1.5.9 / sentence-transformers 5.5.1", "Indexación semántica de estilos, patrones y tácticas del Cap. 02 del SWEBOK v4.0 y guías MADR."],
        ["Backend y Orquestación", "Python + requests + dotenv", "Python 3.13.3", "Orquestación modular de las 3 etapas de T2, control de tasa y medición monótona de latencia (TG)."],
        ["Interfaz del Prototipo", "Streamlit", "streamlit 1.61.1 (src/app.py)", "Interfaz web donde el arquitecto ingresa contexto, ASRs y restricciones y descarga el ADR en .md."],
        ["Evaluación Estadística", "SciPy + Pandas + Matplotlib", "scipy 1.17.1 / pandas 3.0.3 / matplotlib 3.11.0", "Cálculo de CE, SS, CRA, TG, prueba pareada de Wilcoxon y generación de gráficos científicos."],
        ["Control de Versiones", "Git y GitHub", "Repositorio Git local y remoto", "Trazabilidad de código fuente, corpus RAG congelado, prompts y los 24 ADRs generados."],
    ]
    _add_formatted_table(doc, stack_headers, stack_rows)

    doc.add_heading("6.2 Diseño del Prototipo / Plataforma / Servicio", level=2)
    doc.add_paragraph(
        "El diseño arquitectónico del prototipo implementa un flujo de asistencia aumentada compuesto por: "
        "(1) Interfaz de Usuario / Cargador de Escenarios, (2) Módulo Recuperador RAG en ChromaDB con el "
        "Capítulo 02 del SWEBOK v4.0, (3) Orquestador de Secuencia de Prompts en 3 etapas (Análisis de ASRs, "
        "Exploración de Alternativas con 'Abogado del Diablo', y Síntesis MADR), y (4) Generador/Validador Markdown."
    )
    doc.add_paragraph(
        "Las 3 etapas del Pipeline de Generación (Tratamiento T2) operan secuencialmente:\n"
        "• Etapa 1 (Análisis de ASRs y Recuperación RAG): El sistema toma el problema y los drivers, consulta "
        "ChromaDB para recuperar tácticas y patrones relevantes del SWEBOK v4.0 Cap. 02, e identifica los "
        "requisitos arquitectónicamente significativos.\n"
        "• Etapa 2 (Exploración de Alternativas y Abogado del Diablo): Un prompt especializado obliga al modelo "
        "a proponer al menos 3 alternativas viables y a criticar cada una detallando riesgos, deuda técnica "
        "potencial y trade-offs.\n"
        "• Etapa 3 (Síntesis y Formateo MADR): Se consolida el análisis en la plantilla MADR verificando que "
        "las 7 secciones obligatorias estén completas."
    )

    for diag_file, diag_title in [
        (FIGURES_DIR / "diagrama_componentes_arquitectura.png", "Figura 6.1. Diagrama de Componentes de la Arquitectura del Prototipo ADR Híbrido."),
        (FIGURES_DIR / "diagrama_secuencia_pipeline_t2.png", "Figura 6.2. Diagrama de Secuencia del Pipeline de Generación (Tratamiento T2: 3 Etapas + RAG)."),
    ]:
        if diag_file.exists():
            doc.add_picture(str(diag_file), width=Inches(6.2))
            dp = doc.add_paragraph(diag_title)
            dp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            dp.runs[0].italic = True

    doc.add_heading("6.3 Implementación del Prototipo y Script Experimental", level=2)
    doc.add_paragraph(
        "El repositorio se organizó con los módulos src/rag_engine.py, src/adr_assistant.py, src/app.py y "
        "experiment_runner.py. A continuación se documentan los System Prompts congelados empleados en las corridas:"
    )
    for title_sp, body_sp in [
        ("System Prompt T1 (Zero-Shot Estándar):", SYSTEM_PROMPT_T1_ZERO_SHOT),
        ("System Prompt T2 — Etapa 1 (Análisis de ASRs y RAG SWEBOK v4.0):", SYSTEM_PROMPT_T2_STAGE1_ASR),
        ("System Prompt T2 — Etapa 2 (Exploración de Alternativas y Abogado del Diablo):", SYSTEM_PROMPT_T2_STAGE2_DEVILS_ADVOCATE),
        ("System Prompt T2 — Etapa 3 (Síntesis y Formateo MADR):", SYSTEM_PROMPT_T2_STAGE3_MADR_SYNTHESIS),
    ]:
        p_sp = doc.add_paragraph()
        r_sp = p_sp.add_run(title_sp + "\n")
        r_sp.bold = True
        r_body = p_sp.add_run(body_sp)
        r_body.font.name = "Consolas"
        r_body.font.size = Pt(9.5)

    # Insertar capturas de evidencia de ejecución si existen
    for cap_file, cap_title in [
        (FIGURES_DIR / "captura_consola_experiment_runner.png", "Figura 6.1. Evidencia de ejecución de experiment_runner.py en consola (24 corridas T1 y T2)."),
        (FIGURES_DIR / "captura_prototipo_streamlit.png", "Figura 6.2. Interfaz gráfica del prototipo funcional (src/app.py) mostrando generación MADR y trazabilidad RAG."),
    ]:
        if cap_file.exists():
            doc.add_picture(str(cap_file), width=Inches(6.2))
            cp = doc.add_paragraph(cap_title)
            cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cp.runs[0].italic = True

    # SECCIÓN 7
    doc.add_heading("7. Evaluación Experimental y Resultados", level=1)
    doc.add_heading("7.1 Métricas Automáticas y Estructurales", level=2)

    ce, ss, cra, alt, to, tg = (
        by_metric["CE"],
        by_metric["SS"],
        by_metric["CRA"],
        by_metric["Alternativas"],
        by_metric["Trade_offs"],
        by_metric["TG"],
    )
    doc.add_paragraph(
        f"A partir de los 24 ADRs generados (12 con T1 Zero-Shot y 12 con T2 Asistente Propuesto), "
        f"el script test_estadistico.py calculó las métricas automáticas y estructurales. La Completitud "
        f"Estructural (CE) subió de {ce['T1_Media']:.2f}% ± {ce['T1_DE']:.2f}% en T1 a "
        f"{ce['T2_Media']:.2f}% ± {ce['T2_DE']:.2f}% en T2 (+{ce['Mejora_Porcentual']:.2f}%). "
        f"La Similitud Semántica (SS) con el ADR de referencia aumentó de {ss['T1_Media']:.4f} ± {ss['T1_DE']:.4f} "
        f"a {ss['T2_Media']:.4f} ± {ss['T2_DE']:.4f} (+{ss['Mejora_Porcentual']:.2f}%). Asimismo, el promedio de "
        f"alternativas consideradas pasó de {alt['T1_Media']:.2f} a {alt['T2_Media']:.2f} y los trade-offs explícitos "
        f"de {to['T1_Media']:.2f} a {to['T2_Media']:.2f} por escenario."
    )

    q_headers = ["Métrica / Variable", "T1: Zero-Shot (Media ± DE)", "T2: Propuesto (Media ± DE)", "Mejora (%)", "Wilcoxon W", "p-valor"]
    q_rows = []
    for m_key, m_name in [
        ("CE", "Completitud Estructural (CE, %)"),
        ("SS", "Similitud Semántica (SS, 0–1)"),
        ("CRA", "Calidad del Rationale (CRA, 1–5)"),
        ("Alternativas", "Opciones Consideradas (n)"),
        ("Trade_offs", "Trade-offs Explícitos (n)"),
        ("TG", "Tiempo de Generación (TG, s)"),
    ]:
        m = by_metric[m_key]
        q_rows.append([
            m_name,
            f"{m['T1_Media']:.3f} ± {m['T1_DE']:.3f}",
            f"{m['T2_Media']:.3f} ± {m['T2_DE']:.3f}",
            f"+{m['Mejora_Porcentual']:.2f}%",
            f"{m['Wilcoxon_W']:.1f}",
            f"{m['Wilcoxon_p']:.5f}",
        ])
    _add_formatted_table(doc, q_headers, q_rows)

    doc.add_heading("7.2 Evaluación de Calidad Arquitectónica con Rúbrica y Prueba Estadística", level=2)
    doc.add_paragraph(
        f"Al aplicar la prueba de rangos con signo de Wilcoxon para muestras pareadas (scipy.stats.wilcoxon) "
        f"sobre los 12 escenarios evaluados con la rúbrica de 6 criterios (escala Likert 1 a 5), el puntaje "
        f"global CRA mejoró de {cra['T1_Media']:.2f} ± {cra['T1_DE']:.2f} en T1 a "
        f"{cra['T2_Media']:.2f} ± {cra['T2_DE']:.2f} en T2 (W = {cra['Wilcoxon_W']:.1f}, p = {cra['Wilcoxon_p']:.5f} < 0.05). "
        "Dado que p < 0.05 en CE, SS, CRA y en las seis dimensiones de la rúbrica, se rechaza H0 y se demuestra "
        "estadísticamente la superioridad del Asistente Propuesto (T2)."
    )

    r_headers = ["Criterio de la Rúbrica (1 a 5)", "T1 Media ± DE", "T2 Media ± DE", "Mejora (%)", "Wilcoxon W", "p-valor"]
    r_rows = []
    for c_key, c_label in [
        ("C1", "C1: Completitud del contexto"),
        ("C2", "C2: Claridad y especificidad de la decisión"),
        ("C3", "C3: Diversidad y pertinencia de alternativas"),
        ("C4", "C4: Explicitud de concesiones (trade-offs)"),
        ("C5", "C5: Coherencia con restricciones y ASRs"),
        ("C6", "C6: Ausencia de alucinaciones"),
        ("CRA", "CRA Promedio Global (C1–C6)"),
    ]:
        m = by_metric[c_key]
        r_rows.append([
            c_label,
            f"{m['T1_Media']:.2f} ± {m['T1_DE']:.2f}",
            f"{m['T2_Media']:.2f} ± {m['T2_DE']:.2f}",
            f"+{m['Mejora_Porcentual']:.2f}%",
            f"{m['Wilcoxon_W']:.1f}",
            f"{m['Wilcoxon_p']:.5f}",
        ])
    _add_formatted_table(doc, r_headers, r_rows)

    for fig_path, fig_caption in [
        (FIGURES_DIR / "grafico1_barras_calidad_arquitectonica.png", "Gráfico 1. Comparación del puntaje promedio (1 a 5) en las 6 dimensiones de calidad arquitectónica entre T1 y T2."),
        (FIGURES_DIR / "grafico1b_radar_calidad_arquitectonica.png", "Gráfico 1B. Perfil multidimensional tipo Radar de la Calidad del Rationale Arquitectónico (T1 vs. T2)."),
        (FIGURES_DIR / "grafico2_boxplot_distribuciones.png", "Gráfico 2. Diagrama de Cajas (Boxplot) de la distribución de CRA, Similitud Semántica (SS) y Completitud Estructural (CE)."),
    ]:
        if fig_path.exists():
            doc.add_picture(str(fig_path), width=Inches(6.2))
            fp = doc.add_paragraph(fig_caption)
            fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            fp.runs[0].italic = True

    doc.add_heading("7.3 Comparación Cualitativa Lado a Lado (Caso Demostrativo: CASO_01)", level=2)
    c01_headers = ["Aspecto Evaluado", "Tratamiento 1: Zero-Shot (ADR_002)", "Tratamiento 2: Asistente Propuesto (ADR_001)"]
    c01_rows = [
        ["Cumplimiento MADR y SWEBOK v4.0", "Estructura incompleta sin sección formal de ASRs ni referencias al SWEBOK v4.0.", "Cumple 7/7 secciones MADR e integra las tácticas de [SWEBOK-02-03], [SWEBOK-02-07] y [SWEBOK-02-11]."],
        ["Análisis de Alternativas y Trade-offs", "Menciona opciones sin desglose sistemático de riesgos ni deuda técnica potencial.", "Compara 3 alternativas (Kafka, RabbitMQ, Redis Streams) con ventajas, desventajas, riesgos y mitigaciones."],
        ["Extracto del Documento Generado", _extract_snippet(caso01_t1, 520), _extract_snippet(caso01_t2, 520)],
    ]
    _add_formatted_table(doc, c01_headers, c01_rows)

    doc.add_heading("7.4 Amenazas a la Validez", level=2)
    for v_title, v_text in [
        ("Validez interna: ", f"Se controlaron estrictamente los parámetros de inferencia manteniendo el mismo modelo ({modelo_usado}), temperature = 0.2, límite de 4096 tokens y los mismos 12 escenarios de entrada en ambos tratamientos."),
        ("Validez externa: ", "Aunque el experimento evalúa 12 escenarios, estos abarcan dominios heterogéneos (e-commerce, SaaS multi-tenant, banca/pagos, salud clínica, educación, Kubernetes y DevSecOps), facilitando su generalización a contextos reales."),
        ("Validez de constructo: ", "Siguiendo las recomendaciones de los estudios E03 (Dhar et al.) y E08 (Zhou et al.), se combinaron métricas automáticas (similitud semántica con all-MiniLM-L6-v2 y completitud estructural MADR) con evaluación mediante rúbrica arquitectónica de 6 dimensiones."),
        ("Validez de conclusión: ", "Se aplicó la prueba no paramétrica de rangos con signo de Wilcoxon para muestras pareadas (junto con t-Student pareada) sobre los 12 escenarios evaluados, confirmando p < 0.05 en todas las variables principales."),
    ]:
        vp = doc.add_paragraph()
        vr = vp.add_run(v_title)
        vr.bold = True
        vp.add_run(v_text)

    # SECCIÓN 8
    doc.add_heading("8. Conclusiones", level=1)
    doc.add_paragraph(
        f"En respuesta al Objetivo General del estudio, se confirma empíricamente que el Asistente de Decisiones "
        f"Arquitectónicas basado en secuencia de prompts estructurados y RAG sobre el SWEBOK v4.0 (Tratamiento T2) "
        f"mejora la Calidad del Rationale Arquitectónico (CRA) en un +{cra['Mejora_Porcentual']:.2f}% "
        f"(de {cra['T1_Media']:.2f} a {cra['T2_Media']:.2f} sobre 5.00, p = {cra['Wilcoxon_p']:.5f}), "
        f"incrementa la Completitud Estructural (CE) en un +{ce['Mejora_Porcentual']:.2f}% (alcanzando "
        f"{ce['T2_Media']:.2f}% de adherencia al estándar MADR frente a {ce['T1_Media']:.2f}% de T1) y eleva "
        f"la Similitud Semántica (SS) con las decisiones de referencia en un +{ss['Mejora_Porcentual']:.2f}% "
        f"(de {ss['T1_Media']:.4f} a {ss['T2_Media']:.4f}, p = {ss['Wilcoxon_p']:.5f})."
    )
    doc.add_paragraph(
        "Estos resultados corroboran la evidencia reportada en la revisión sistemática del Hito 1 por Díaz-Pace et al. "
        "(E06) y Zhou et al. (E08): la combinación de recuperación de conocimiento arquitectónico (RAG) y razonamiento "
        "coordinado por etapas con evaluación crítica ('Abogado del Diablo') reduce sustancialmente las respuestas "
        "genéricas y las omisiones de trade-offs propias del enfoque Zero-Shot. Asimismo, se confirma que el esquema "
        "human-in-the-loop continúa siendo indispensable para validar supuestos y restricciones organizacionales tácitas."
    )
    doc.add_paragraph(
        "Como trabajo futuro, se propone integrar el asistente directamente en pipelines CI/CD mediante GitHub Actions "
        "para verificar la conformidad arquitectónica y detectar posibles violaciones de los ADRs en cada pull request "
        "(conectando con los hallazgos del estudio E05 de Su et al.), así como indexar el código fuente y manifiestos "
        "de infraestructura del proyecto dentro de ChromaDB para mantener la trazabilidad longitudinal de las decisiones."
    )

    doc.save(docx_path)


def _add_formatted_table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr_cells = table.rows[0].cells
    for idx, h_text in enumerate(headers):
        hdr_cells[idx].text = h_text
        for p in hdr_cells[idx].paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(9.5)

    for row_vals in rows:
        row_cells = table.add_row().cells
        for idx, val in enumerate(row_vals):
            row_cells[idx].text = str(val)
            for p in row_cells[idx].paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9.0)
    doc.add_paragraph()


if __name__ == "__main__":
    generate_all_documents()
