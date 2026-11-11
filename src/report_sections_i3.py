"""
Módulo generador de las secciones detalladas del Integrante 3 (Mauricio Elias Congona Manrique):
- Sección 6.1: Herramientas y Stack Tecnológico (explicación profunda por capas e inventario del corpus SWEBOK v4.0).
- Sección 6.2: Diseño Arquitectónico del Prototipo, Contratos de Datos y Pipeline Secuencial en 3 Etapas + RAG.
- Sección 6.3: Implementación del Prototipo, Prompts Congelados, Trazabilidad de las 24 Corridas y Capturas.
- Anexo del Repositorio GitHub.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import pandas as pd

from src.adr_assistant import (
    SYSTEM_PROMPT_T1_ZERO_SHOT,
    SYSTEM_PROMPT_T2_STAGE1_ASR,
    SYSTEM_PROMPT_T2_STAGE2_DEVILS_ADVOCATE,
    SYSTEM_PROMPT_T2_STAGE3_MADR_SYNTHESIS,
)


def build_i3_markdown(
    modelo_usado: str,
    corpus_list: list[dict[str, Any]],
    metrics_df: pd.DataFrame,
    df_to_md_fn: Any,
) -> str:
    corpus_rows = []
    for item in corpus_list:
        corpus_rows.append(
            {
                "ID Fragmento": f"`{item['id_fragmento']}`",
                "Sección SWEBOK v4.0": item["seccion_swebok"],
                "Tema / Patrón Arquitectónico": item["tema"],
                "Palabras Clave": ", ".join(item.get("palabras_clave", [])[:4]),
            }
        )
    corpus_df = pd.DataFrame(corpus_rows)

    runs_table_df = metrics_df[
        [
            "orden_ejecucion",
            "codigo_ciego",
            "id_caso",
            "tratamiento",
            "modelo",
            "temperatura",
            "tiempo_segundos",
            "longitud_caracteres",
            "fragmentos_rag_ids",
            "estado",
        ]
    ].copy()
    runs_table_df.columns = [
        "Orden",
        "Código Ciego",
        "Caso",
        "Trat.",
        "Modelo",
        "Temp.",
        "TG (s)",
        "Caracteres",
        "Fragmentos SWEBOK Recuperados (RAG)",
        "Estado",
    ]

    return rf"""## 6. Conducción del Experimento y Arquitectura del Prototipo (Integrante 3: Mauricio Elias Congona Manrique)

### 6.1 Herramientas y Stack Tecnológico

El desarrollo del prototipo de **Asistente de Decisiones Arquitectónicas (ADR) asistido por IA** y su plataforma de ejecución experimental se diseñó bajo los principios de **modularidad, determinismo técnico, trazabilidad de fuentes y reproducibilidad empírica**. Cada herramienta del stack tecnológico fue seleccionada para resolver las limitaciones identificadas en la revisión sistemática de literatura del Hito 1 (particularmente la genericidad de respuestas en modo *zero-shot*, la omisión de restricciones contextuales y la propensión a alucinaciones en la justificación de *trade-offs* reportadas en los estudios E03, E04, E06 y E08).

#### 6.1.1 Capa de Inferencia Generativa y Control Estocástico (Google AI Studio / API Gemini)
Para la generación de texto técnico se empleó la interfaz RESTful oficial `v1beta` (`models/{{model}}:generateContent`) de **Google AI Studio** utilizando la familia de modelos **Google Gemini Flash (`{modelo_usado}` / `gemini-3.5-flash`)**. Desde una perspectiva técnica, los modelos de lenguaje autorregresivos calculan la distribución de probabilidad del siguiente token $w_t$ aplicando la función *softmax* escalada por un hiperparámetro de temperatura $T$:

$$P(w_t \mid w_{{<t}}) = \frac{{\exp(z_t / T)}}{{\sum_{{j \in V}} \exp(z_j / T)}}$$

Donde $z_t$ representa el *logit* asignado al token $t$ dentro del vocabulario $V$. En la configuración por defecto de asistentes conversacionales ($T \in [0.7, 1.0]$), la distribución se aplana, incrementando la diversidad léxica pero introduciendo varianza estocástica y riesgo de afirmaciones infundadas. Por ello, en cumplimiento estricto de las variables de control del protocolo experimental, se fijó **`temperature = 0.2`** y **`maxOutputTokens = 4096`** de manera idéntica tanto en el Tratamiento 1 (`T1: Zero-Shot`) como en el Tratamiento 2 (`T2: Secuencia de Prompts + RAG`). Adicionalmente, en los modelos con razonamiento interno de la serie Gemini 3 se estandarizó `"thinkingConfig": {{"thinkingBudget": 0}}`, asegurando que la totalidad del presupuesto de 4096 tokens de salida se destine íntegramente a la estructuración explícita del documento ADR sin truncamientos prematuros.

#### 6.1.2 Capa de Base de Conocimiento Vectorial y Recuperación Semántica (RAG)
Para fundamentar las decisiones en ingeniería de software formal y evitar que el modelo dependa únicamente de su memoria paramétrica, se implementó un motor de **Recuperación Aumentada por Generación (RAG)** compuesto por:
1. **Modelo de Embeddings Densos (`sentence-transformers/all-MiniLM-L6-v2`, `v5.5.1`):** Red neuronal bi-encoder basada en una arquitectura Transformer de 6 capas que proyecta fragmentos de texto en un espacio vectorial continuo de dimensión $d = 384$ ($\mathbb{{R}}^{{384}}$). Los vectores generados son normalizados mediante norma euclidiana $L_2$ ($\hat{{\mathbf{{u}}}} = \mathbf{{u}} / \|\mathbf{{u}}\|_2$), de modo que el producto interno equivale exactamente a la similitud del coseno:
   $$\text{{sim}}_{{\cos}}(\mathbf{{q}}, \mathbf{{d}}_i) = \frac{{\mathbf{{q}} \cdot \mathbf{{d}}_i}}{{\|\mathbf{{q}}\|_2 \|\mathbf{{d}}_i\|_2}} = \hat{{\mathbf{{q}}}}^\top \hat{{\mathbf{{d}}}}_i \in [-1, 1]$$
2. **Motor de Base de Datos Vectorial (`ChromaDB v1.5.9`):** Configurado en modo persistente local (`chromadb.PersistentClient`) sobre el directorio `chroma_db/`, utilizando un índice **HNSW (*Hierarchical Navigable Small World*)** parametrizado en el espacio de distancia coseno (`hnsw:space = "cosine"`, donde $d_{{\cos}} = 1 - \text{{sim}}_{{\cos}}$).
3. **Corpus Curado y Congelado del SWEBOK v4.0 Cap. 02 (`knowledge_base/swebok_cap02_corpus.json`):** Se construyó e indexó un corpus inmutable de **14 fragmentos técnicos de alta densidad conceptual (`SWEBOK-02-01` a `SWEBOK-02-14`)** alineados al **Capítulo 02 (*Software Architecture*) de la Guía SWEBOK v4.0** y al estándar **MADR**. Cada fragmento encapsula la definición formal de los *Architecturally Significant Requirements* (ASRs), los estilos arquitectónicos, las tácticas de atributos de calidad y al menos tres patrones contrastantes con sus respectivos *trade-offs*.

**Tabla 6.1. Inventario completo de los 14 fragmentos del SWEBOK v4.0 Cap. 02 indexados en ChromaDB**

{df_to_md_fn(corpus_df)}

#### 6.1.3 Capa de Backend, Orquestación Secuencial e Instrumentación de Latencia
El núcleo lógico fue desarrollado en **Python `3.13.3`** aplicando separación de responsabilidades:
- **Medición de latencia con reloj monótono (`time.perf_counter()`):** A diferencia de `time.time()`, que puede sufrir ajustes por sincronización NTP del sistema operativo, `time.perf_counter()` utiliza el contador de rendimiento de hardware de mayor resolución disponible en Windows, permitiendo medir la variable dependiente **Tiempo de Generación (`TG`)** con precisión de diezmilésimas de segundo.
- **Tolerancia a fallos de red y control de cuota (*Rate-Limiting*):** El cliente HTTP implementa reintentos automáticos con *exponential backoff* ante códigos transitorios (`HTTP 429, 500, 502, 503, 504`), espaciado preventivo entre corridas y rotación transparente dentro de la misma subfamilia Gemini Flash cuando se alcanza el límite diario de peticiones de la capa gratuita (*Free Tier* de Google AI Studio), garantizando cero pérdida de datos durante la ejecución por lotes.

#### 6.1.4 Capa de Interfaz Interactiva y Reproducibilidad
- **Interfaz Web (`Streamlit v1.61.1` en `src/app.py`):** Implementa caché de recursos en memoria (`@st.cache_resource`) para mantener pre-cargados el modelo `all-MiniLM-L6-v2` y la conexión a `ChromaDB`, ofreciendo al arquitecto una experiencia interactiva sin latencia de inicialización.
- **Suite Científica (`SciPy v1.17.1`, `Pandas v3.0.3`, `Matplotlib v3.11.0`, `python-docx v1.2.0`):** Automatiza desde la verificación estructural de secciones MADR hasta el cálculo de pruebas no paramétricas y la exportación de reportes académicos.

**Tabla 6.2. Resumen general del stack tecnológico y su justificación experimental**

| Capa Arquitectónica | Herramienta / Librería | Versión / Parámetros | Justificación Técnica y Experimental |
| :--- | :--- | :--- | :--- |
| **Inferencia LLM** | Google AI Studio REST API | `{modelo_usado}` (`temp = 0.2`, `maxTokens = 4096`) | Garantiza determinismo técnico y condiciones de control idénticas entre `T1` y `T2`. |
| **Motor Vectorial RAG** | ChromaDB (HNSW Cosine) | `chromadb 1.5.9` (`swebok_v4_cap02_madr`) | Recuperación semántica determinista en milisegundos de guías del SWEBOK v4.0 Cap. 02. |
| **Modelo de Embeddings** | Sentence-Transformers | `all-MiniLM-L6-v2` (`v5.5.1`, dim `384`) | Mismo espacio vectorial para recuperación RAG y para evaluar la Similitud Semántica (`SS`). |
| **Backend y Orquestación** | Python + `requests` + `dotenv` | `Python 3.13.3` | Ejecución modular de las 3 etapas de `T2`, manejo seguro de `.env` y reloj monótono `TG`. |
| **Interfaz de Usuario** | Streamlit | `streamlit 1.61.1` (`src/app.py`) | Demostración funcional *human-in-the-loop* con visualización de trazas RAG y descarga `.md`. |
| **Análisis Estadístico** | SciPy + NumPy + Pandas | `scipy 1.17.1` / `pandas 3.0.3` | Ejecución exacta de pruebas pareadas (`scipy.stats.wilcoxon` y `scipy.stats.ttest_rel`). |
| **Control de Versiones** | Git / GitHub | Git local (`rama main`) | Congelamiento auditable del corpus, prompts, scripts y los 24 ADRs generados. |

---

### 6.2 Diseño Arquitectónico del Prototipo / Plataforma / Servicio

La arquitectura del sistema propuesto se concibió para superar el defecto estructural del enfoque *Zero-Shot* (`T1`): cuando un LLM recibe un escenario arquitectónico en un único paso sin recuperación de contexto ni estructura de razonamiento intermedia, tiende a sufrir de **convergencia prematura** (elige la tecnología más popular en su corpus de pre-entrenamiento sin contrastarla contra las restricciones del equipo) y **complacencia acrítica** (describe ventajas genéricas omitiendo riesgos operacionales y deuda técnica).

Para corregir este comportamiento, el **Tratamiento 2 (`T2`)** implementa una arquitectura de **Pipeline Cognitivo Secuencial de 3 Etapas Aumentado por RAG**, donde cada etapa opera con un *System Prompt* especializado y un contrato de entrada/salida explícito.

#### 6.2.1 Diagrama de Componentes de la Arquitectura

```mermaid
flowchart TB
    subgraph UI["1. Capa de Presentación y Carga Experimental"]
        ST["Interfaz Web Interactiva\n(src/app.py - Streamlit)"]
        ER["Ejecutor de Lotes Experimentales\n(experiment_runner.py + escenarios_adr.json)"]
    end

    subgraph RAG["2. Subsistema Recuperador RAG (src/rag_engine.py)"]
        QB["Constructor de Consulta Semántica\n(build_Scenario_query)"]
        EMB["Bi-Encoder Embeddings\n(all-MiniLM-L6-v2, 384d, L2-norm)"]
        CDB[("ChromaDB Persistent Store\n14 Fragmentos SWEBOK v4.0 Cap. 02")]
    end

    subgraph ORQ["3. Subsistema Orquestador de Asistencia ADR (src/adr_assistant.py)"]
        T1["Ejecutor Línea Base T1\n(generate_zero_shot)"]
        subgraph T2["Pipeline Secuencial Guiado T2 (generate_guided_rag_adr)"]
            P1["Etapa 1: Analizador de ASRs\ny Mapeo Táctico SWEBOK v4.0"]
            P2["Etapa 2: Explorador de Alternativas\ny 'Abogado del Diablo' (Mín. 3 Opciones)"]
            P3["Etapa 3: Sintetizador Formal\ny Validador de Plantilla MADR (7 Secc.)"]
        end
    end

    subgraph EXT["4. Proveedor de Inferencia Controlada"]
        LLM["Google AI Studio API (Familia Gemini Flash)\ntemperature = 0.2 | maxOutputTokens = 4096"]
    end

    subgraph OUT["5. Subsistema de Persistencia, Cegado y Evaluación"]
        MD["Almacén de Artefactos Markdown\noutput/T1/, output/T2/ y output/ciego/ (ADR_001..024)"]
        EV["Motor de Evaluación y Estadística\n(test_estadistico.py -> CE, SS, CRA, TG, Wilcoxon)"]
    end

    ST --> T1
    ST --> P1
    ER --> T1
    ER --> P1
    P1 --> QB
    QB --> EMB
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

![Figura 6.1: Diagrama de Componentes de la Arquitectura del Prototipo ADR Híbrido](../results/figures/diagrama_componentes_arquitectura.png)

#### 6.2.2 Especificación Técnica de los Cinco Subsistemas

1. **Subsistema de Entrada y Carga Experimental (`src/app.py` y `experiment_runner.py`):**
   Recibe un objeto JSON estructurado con el contrato de datos definido por el Integrante 2: `id_caso`, `titulo_problema`, `contexto`, `drivers_arquitectonicos` (lista de 3 ASRs) y `restricciones` (lista de 3 limitaciones técnicas/organizacionales).
2. **Subsistema Recuperador Vectorial RAG (`src/rag_engine.py`):**
   - El método `build_Scenario_query(scenario)` concatena semánticamente el problema, el contexto, los ASRs y las restricciones en una consulta densa $q$.
   - El método `retrieve_context(query_text, top_k=3)` codifica $q$ con `all-MiniLM-L6-v2` y ejecuta una búsqueda $k$-NN ($k=3$) sobre el grafo HNSW de `ChromaDB`.
   - El método `format_fragments_for_prompt(fragments)` serializa los 3 fragmentos recuperados incluyendo su código normativo (`[SWEBOK-02-XX]`), su sección del SWEBOK v4.0, su puntaje de similitud coseno y su contenido técnico completo.
3. **Subsistema Orquestador de Secuencia de Prompts (`src/adr_assistant.py`):**
   Coordina la ejecución de los dos tratamientos experimentales bajo las mismas restricciones de inferencia:
   - **Flujo `T1 (generate_zero_shot)`:** Construye un único prompt directo con los datos del escenario y solicita la redacción de un ADR en Markdown sin proporcionar la plantilla MADR ni contexto externo.
   - **Flujo `T2 (generate_guided_rag_adr)`:** Ejecuta una cadena de pensamiento estructurada en **tres etapas secuenciales con transferencia acumulativa de estado**, detallada a continuación.
4. **Subsistema de Inferencia Controlada (`GeminiADRClient`):**
   Encapsula la comunicación HTTPS con `generativelanguage.googleapis.com`, inyectando las instrucciones de sistema (`system_instruction`) por separado del mensaje de usuario (`contents`) para evitar que el modelo confunda su rol metodológico con los datos del escenario.
5. **Subsistema de Persistencia, Codificación Ciega y Evaluación (`output/` y `test_estadistico.py`):**
   Almacena cada ADR tanto en su carpeta de tratamiento (`output/T1/CASO_XX_T1.md`, `output/T2/CASO_XX_T2.md`) como en la carpeta de evaluación ciega (`output/ciego/ADR_001.md` a `ADR_024.md`) siguiendo el mapeo aleatorio balanceado de la hoja `Clave_Tratamientos`.

#### 6.2.3 Diagrama de Secuencia y Mecánica Interna del Pipeline T2 (3 Etapas + RAG)

```mermaid
sequenceDiagram
    autonumber
    actor Arq as Arquitecto / Runner
    participant Orq as Orquestador T2 (adr_assistant.py)
    participant RAG as Motor RAG (ChromaDB + MiniLM)
    participant LLM as Google Gemini API (temp=0.2)
    participant Out as Validador MADR (.md / CSV)

    Arq->>Orq: Envía Escenario (ID, Título, Contexto, ASRs, Restricciones)
    rect rgb(235, 245, 255)
        Note over Orq,LLM: ETAPA 1: Análisis de ASRs, Restricciones y Recuperación RAG
        Orq->>RAG: build_Scenario_query() + retrieve_context(top_k=3)
        RAG-->>Orq: Top-3 Fragmentos SWEBOK v4.0 Cap. 02 [SWEBOK-02-XX] + Similitud Coseno
        Orq->>LLM: SystemPrompt_Etapa1 + (Escenario + Fragmentos SWEBOK v4.0)
        LLM-->>Orq: Salida Etapa 1 (Priorización de ASRs, tensiones de calidad y tácticas SWEBOK)
    end
    rect rgb(255, 245, 235)
        Note over Orq,LLM: ETAPA 2: Exploración Divergente y Evaluación Crítica ("Abogado del Diablo")
        Orq->>LLM: SystemPrompt_Etapa2 + (Escenario + Salida Etapa 1)
        LLM-->>Orq: Salida Etapa 2 (>=3 Opciones con Descripción, Ventajas, Desventajas, Riesgos y Trade-offs)
    end
    rect rgb(235, 255, 240)
        Note over Orq,Out: ETAPA 3: Síntesis Convergente y Formateo Estricto MADR (7 Secciones)
        Orq->>LLM: SystemPrompt_Etapa3 + (Escenario + Salida Etapa 1 + Salida Etapa 2)
        LLM-->>Orq: Documento ADR Final en Markdown (7 Secciones MADR + Trazabilidad SWEBOK)
        Orq->>Out: Sanitiza bloques Markdown, mide latencia TG y persiste archivos
        Out-->>Arq: Retorna ADR (.md), trazas de Etapas 1-2 y fragmentos RAG
    end
```

![Figura 6.2: Diagrama de Secuencia del Pipeline de Generación — Tratamiento T2](../results/figures/diagrama_secuencia_pipeline_t2.png)

**Análisis técnico de las 3 etapas del Tratamiento T2:**
- **Etapa 1 — Análisis de ASRs y Anclaje en el SWEBOK v4.0:** Antes de proponer cualquier solución, el modelo actúa como un *Arquitecto de Software Senior* que cruza los 3 drivers de calidad del caso con las 3 restricciones operativas y extrae las tácticas aplicables de los 3 fragmentos recuperados de ChromaDB (citando sus identificadores `[SWEBOK-02-XX]`). Esto elimina la desconexión contextual observada en la literatura (estudio E04 y E06).
- **Etapa 2 — Exploración de Alternativas y Rol de "Abogado del Diablo":** Inspirado en los hallazgos sobre razonamiento multiagente y *Chain-of-Thought* de **Zhou et al. (E08, 2026)** y **Maranhão y Guerra (E01, 2024)**, esta etapa impone una restricción de exploración divergente seguida de crítica convergente: obliga al modelo a formular **mínimo 3 alternativas arquitectónicas viables y contrastantes** y a auditar cada una como un *Abogado del Diablo*, explicitando costos ocultos, sobrecarga cognitiva para el tamaño del equipo, riesgos de falla en producción y deuda técnica potencial.
- **Etapa 3 — Síntesis y Validación Estructural MADR:** Recibe como contexto acumulado el escenario original, el análisis de ASRs/SWEBOK de la Etapa 1 y la matriz crítica de alternativas de la Etapa 2, y sintetiza el documento definitivo cumpliendo rigurosamente las **7 secciones obligatorias del estándar MADR**, incluyendo una subsección dedicada a *Supuestos Asumidos* (para prevenir afirmaciones infundadas) y una subsección de *Trade-offs y Riesgos Residuales* con su respectiva estrategia de mitigación.

---

### 6.3 Implementación del Prototipo y del Script Experimental

#### 6.3.1 Organización Limpia de Módulos en el Repositorio
El repositorio Git fue estructurado con separación estricta entre datos de entrada (`dataset/`, `knowledge_base/`), código fuente (`src/`), scripts de automatización (`experiment_runner.py`, `test_estadistico.py`, `generate_evidence_screenshots.py`, `generate_deliverables.py`), artefactos generados (`output/T1/`, `output/T2/`, `output/ciego/`) y evidencias cuantitativas (`results/`).

#### 6.3.2 Bloques Íntegros de *System Prompts* Congelados

A continuación se documentan textualmente los cuatro *System Prompts* congelados en `src/adr_assistant.py` antes del inicio de las corridas experimentales:

**1. System Prompt utilizado en el Tratamiento 1 (`T1` — Línea Base Zero-Shot Estándar):**
```text
{SYSTEM_PROMPT_T1_ZERO_SHOT}
```

**2. System Prompt utilizado en el Tratamiento 2 — Etapa 1 (Análisis de ASRs y Recuperación RAG):**
```text
{SYSTEM_PROMPT_T2_STAGE1_ASR}
```

**3. System Prompt utilizado en el Tratamiento 2 — Etapa 2 (Exploración de Alternativas y Abogado del Diablo):**
```text
{SYSTEM_PROMPT_T2_STAGE2_DEVILS_ADVOCATE}
```

**4. System Prompt utilizado en el Tratamiento 2 — Etapa 3 (Síntesis y Formateo MADR):**
```text
{SYSTEM_PROMPT_T2_STAGE3_MADR_SYNTHESIS}
```

#### 6.3.3 Registro Completo de las 24 Ejecuciones Experimentales (`results/metricas_ejecucion.csv`)

El script `experiment_runner.py` ejecutó de manera automatizada los 12 escenarios del Integrante 2 bajo ambos tratamientos (`24 corridas` en total), registrando la marca temporal ISO-8601, el código ciego asignado, la latencia exacta en segundos (`TG`), la longitud en caracteres del ADR producido y los identificadores de los fragmentos del SWEBOK v4.0 recuperados desde ChromaDB en `T2`.

**Tabla 6.3. Bitácora verificable de las 24 corridas ejecutadas por `experiment_runner.py`**

{df_to_md_fn(runs_table_df)}

#### 6.3.4 Evidencias Visuales del Prototipo y de la Ejecución en Consola

Las Figuras 6.3 y 6.4 muestran la evidencia directa de la ejecución por lotes de `experiment_runner.py` en consola (completando las 24 corridas sin errores) y la interfaz web interactiva en `Streamlit` (`src/app.py`) visualizando la recuperación vectorial en ChromaDB y el documento MADR generado para `CASO_01`.

![Figura 6.3: Evidencia de ejecución automatizada de experiment_runner.py en consola (24 corridas T1 y T2)](../results/figures/captura_consola_experiment_runner.png)

![Figura 6.4: Interfaz gráfica del prototipo funcional en Streamlit (src/app.py) con trazabilidad RAG y vista previa MADR](../results/figures/captura_prototipo_streamlit.png)
"""


def add_i3_to_word(
    doc: Any,
    modelo_usado: str,
    corpus_list: list[dict[str, Any]],
    metrics_df: pd.DataFrame,
    figures_dir: Path,
    add_table_fn: Any,
    Pt: Any,
    Inches: Any,
    WD_ALIGN_PARAGRAPH: Any,
) -> None:
    doc.add_heading("6. Conducción del Experimento y Arquitectura del Prototipo (Integrante 3)", level=1)

    doc.add_heading("6.1 Herramientas y Stack Tecnológico", level=2)
    doc.add_paragraph(
        "El desarrollo del prototipo de Asistente de Decisiones Arquitectónicas (ADR) asistido por IA y su "
        "plataforma de ejecución experimental se diseñó bajo los principios de modularidad, determinismo técnico, "
        "trazabilidad de fuentes y reproducibilidad empírica. Cada componente del stack tecnológico fue seleccionado "
        "para mitigar las limitaciones identificadas en la revisión sistemática del Hito 1 (genericidad del enfoque "
        "zero-shot, desconexión respecto a las restricciones del proyecto y riesgo de alucinaciones en los trade-offs)."
    )

    doc.add_heading("6.1.1 Capa de Inferencia Generativa y Control Estocástico (Google AI Studio / API Gemini)", level=3)
    doc.add_paragraph(
        f"Se integró la API REST oficial v1beta de Google AI Studio empleando la familia de modelos Google Gemini Flash "
        f"({modelo_usado} / gemini-3.5-flash). En los modelos de lenguaje autorregresivos, la temperatura T escala los "
        "logits antes de aplicar la función softmax: P(w_t | w_<t) = exp(z_t / T) / sum_j exp(z_j / T). Con temperaturas "
        "altas (T >= 0.7), la distribución se aplana e introduce varianza estocástica y riesgo de alucinación. Por ello, "
        "como variable de control estricta del diseño experimental, se fijó temperature = 0.2 y maxOutputTokens = 4096 "
        "de manera idéntica en el Tratamiento 1 (T1: Zero-Shot) y en el Tratamiento 2 (T2: Secuencia de Prompts + RAG), "
        "además de configurar thinkingBudget = 0 para destinar el 100% de la ventana de salida a la redacción del ADR."
    )

    doc.add_heading("6.1.2 Base de Conocimiento Vectorial y Recuperación Semántica (RAG en ChromaDB)", level=3)
    doc.add_paragraph(
        "Para fundamentar las decisiones en el cuerpo de conocimiento de la ingeniería de software, se implementó un "
        "motor RAG sobre ChromaDB (v1.5.9) en modo persistente con índice HNSW (Hierarchical Navigable Small World) "
        "parametrizado con similitud del coseno (hnsw:space = cosine) y el modelo bi-encoder sentence-transformers/all-MiniLM-L6-v2 "
        "(v5.5.1, vectores densos de 384 dimensiones normalizados en L2). Se indexaron 14 fragmentos curados del Capítulo 02 "
        "(Software Architecture) del SWEBOK v4.0 y la guía MADR (SWEBOK-02-01 a SWEBOK-02-14)."
    )

    corpus_headers = ["ID Fragmento", "Sección SWEBOK v4.0", "Tema / Patrón Arquitectónico", "Palabras Clave"]
    corpus_rows = [
        [
            item["id_fragmento"],
            item["seccion_swebok"],
            item["tema"],
            ", ".join(item.get("palabras_clave", [])[:4]),
        ]
        for item in corpus_list
    ]
    add_table_fn(doc, corpus_headers, corpus_rows)

    doc.add_heading("6.1.3 Backend, Orquestación, Interfaz Streamlit y Reproducibilidad", level=3)
    doc.add_paragraph(
        "El backend se desarrolló en Python 3.13.3 dividiendo responsabilidades entre src/rag_engine.py (indexación y "
        "búsqueda vectorial), src/adr_assistant.py (implementación de T1 y del pipeline de 3 etapas de T2), src/app.py "
        "(interfaz web interactiva en Streamlit v1.61.1 con caché de recursos, inspección de fragmentos RAG y descarga .md) "
        "y experiment_runner.py (ejecución automatizada de las 24 corridas midiendo el Tiempo de Generación TG con el reloj "
        "monótono de hardware time.perf_counter())."
    )

    stack_headers = ["Capa Arquitectónica", "Tecnología / Herramienta", "Versión / Configuración", "Justificación Técnica y Experimental"]
    stack_rows = [
        ["Inferencia LLM", "Google AI Studio / API Gemini", f"{modelo_usado} (temp=0.2, maxTokens=4096)", "Control determinista idéntico para comparar T1 (Zero-Shot) frente a T2 (3 Etapas + RAG)."],
        ["Base Vectorial RAG", "ChromaDB (Índice HNSW Coseno)", "chromadb 1.5.9 (swebok_v4_cap02_madr)", "Recuperación Top-3 de estilos, patrones y tácticas del Cap. 02 del SWEBOK v4.0."],
        ["Modelo Embeddings", "Sentence-Transformers", "all-MiniLM-L6-v2 (v5.5.1, 384d, L2-norm)", "Representación semántica densa tanto para RAG como para medir Similitud Semántica (SS)."],
        ["Backend y Runner", "Python + requests + dotenv", "Python 3.13.3 + time.perf_counter()", "Orquestación secuencial, manejo seguro de credenciales (.env) y medición exacta de TG."],
        ["Interfaz Prototipo", "Streamlit", "streamlit 1.61.1 (src/app.py)", "Entorno interactivo human-in-the-loop para explorar escenarios, trazas RAG y exportar .md."],
        ["Suite Estadística", "SciPy + Pandas + Matplotlib", "scipy 1.17.1 / pandas 3.0.3 / matplotlib 3.11.0", "Cálculo automatizado de CE, SS, CRA, TG, prueba pareada de Wilcoxon y gráficos a 220 DPI."],
        ["Versionado", "Git y GitHub", "Git local (rama main)", "Trazabilidad completa de código, corpus congelado, prompts y los 24 ADRs generados."],
    ]
    add_table_fn(doc, stack_headers, stack_rows)

    doc.add_heading("6.2 Diseño Arquitectónico del Prototipo / Plataforma / Servicio", level=2)
    doc.add_paragraph(
        "Cuando un modelo de lenguaje opera en modo Zero-Shot (T1), sufre de convergencia prematura (selecciona la "
        "tecnología más frecuente en su pre-entrenamiento sin contrastarla con las limitaciones del equipo) y complacencia "
        "acrítica (omite costos ocultos y riesgos residuales). Para resolver este problema, el Tratamiento 2 (T2) implementa "
        "una arquitectura de Pipeline Cognitivo Secuencial en 3 Etapas Aumentado por RAG, desacoplada en cinco subsistemas:"
    )
    doc.add_paragraph(
        "1. Subsistema de Presentación y Carga Experimental (src/app.py y experiment_runner.py): Ingiere la definición "
        "del escenario (ID, título, contexto operativo, 3 ASRs y 3 restricciones).\n"
        "2. Subsistema Recuperador RAG (src/rag_engine.py): Construye una consulta semántica enriquecida, la vectoriza con "
        "all-MiniLM-L6-v2 y recupera de ChromaDB los k=3 fragmentos más cercanos del Capítulo 02 del SWEBOK v4.0.\n"
        "3. Subsistema Orquestador de Secuencia de Prompts (src/adr_assistant.py):\n"
        "   • Etapa 1 (Análisis de ASRs y Recuperación RAG): Extrae los requisitos arquitectónicamente significativos, "
        "identifica las tensiones entre atributos de calidad y vincula las restricciones con las tácticas del SWEBOK v4.0 [SWEBOK-02-XX].\n"
        "   • Etapa 2 (Exploración de Alternativas y 'Abogado del Diablo'): Fuerza el pensamiento divergente exigiendo al "
        "menos 3 alternativas técnicamente viables y audita críticamente cada una detallando ventajas, desventajas, riesgos "
        "operativos, deuda técnica potencial y concesiones (trade-offs).\n"
        "   • Etapa 3 (Síntesis y Validación Estructural MADR): Consolida el estado acumulado de las Etapas 1 y 2 dentro "
        "de las 7 secciones obligatorias de la plantilla formal MADR, declarando supuestos y mitigaciones de riesgos residuales.\n"
        "4. Subsistema de Inferencia Controlada (GeminiADRClient): Ejecuta las peticiones HTTPS separando system_instruction "
        "de contents bajo temperature = 0.2.\n"
        "5. Subsistema de Persistencia, Codificación Ciega y Evaluación (output/ y test_estadistico.py): Guarda los 24 ADRs "
        "en output/T1/, output/T2/ y output/ciego/ (ADR_001 a ADR_024)."
    )

    for diag_file, diag_title in [
        (figures_dir / "diagrama_componentes_arquitectura.png", "Figura 6.1. Diagrama de Componentes de la Arquitectura del Prototipo ADR Híbrido."),
        (figures_dir / "diagrama_secuencia_pipeline_t2.png", "Figura 6.2. Diagrama de Secuencia del Pipeline de Generación (Tratamiento T2: 3 Etapas + RAG)."),
    ]:
        if diag_file.exists():
            doc.add_picture(str(diag_file), width=Inches(6.2))
            dp = doc.add_paragraph(diag_title)
            dp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            dp.runs[0].italic = True

    doc.add_heading("6.3 Implementación del Prototipo y del Script Experimental", level=2)
    doc.add_paragraph(
        "A continuación se presentan los bloques íntegros de los System Prompts congelados en src/adr_assistant.py "
        "utilizados para ejecutar el Tratamiento 1 y las tres etapas secuenciales del Tratamiento 2:"
    )

    for title_sp, body_sp in [
        ("1. System Prompt — Tratamiento 1 (Zero-Shot Estándar):", SYSTEM_PROMPT_T1_ZERO_SHOT),
        ("2. System Prompt — Tratamiento 2, Etapa 1 (Análisis de ASRs y RAG SWEBOK v4.0):", SYSTEM_PROMPT_T2_STAGE1_ASR),
        ("3. System Prompt — Tratamiento 2, Etapa 2 (Exploración de Alternativas y Abogado del Diablo):", SYSTEM_PROMPT_T2_STAGE2_DEVILS_ADVOCATE),
        ("4. System Prompt — Tratamiento 2, Etapa 3 (Síntesis y Formateo MADR):", SYSTEM_PROMPT_T2_STAGE3_MADR_SYNTHESIS),
    ]:
        p_sp = doc.add_paragraph()
        r_sp = p_sp.add_run(title_sp + "\n")
        r_sp.bold = True
        r_body = p_sp.add_run(body_sp)
        r_body.font.name = "Consolas"
        r_body.font.size = Pt(9.0)

    doc.add_paragraph(
        "La Tabla 6.3 presenta la bitácora completa de las 24 corridas ejecutadas por experiment_runner.py, "
        "incluyendo el código ciego asignado, el tiempo de generación (TG), la extensión en caracteres y los "
        "fragmentos del SWEBOK v4.0 inyectados mediante RAG en cada escenario del Tratamiento 2:"
    )

    run_headers = ["Ord.", "Cód. Ciego", "Caso", "Trat.", "TG (s)", "Caract.", "Fragmentos SWEBOK v4.0 Recuperados (RAG)", "Estado"]
    run_rows = []
    for _, r in metrics_df.iterrows():
        rag_str = str(r["fragmentos_rag_ids"]) if pd.notna(r["fragmentos_rag_ids"]) and str(r["fragmentos_rag_ids"]) else "Ninguno (Zero-Shot)"
        run_rows.append([
            str(r["orden_ejecucion"]),
            str(r["codigo_ciego"]),
            str(r["id_caso"]),
            str(r["tratamiento"]),
            f"{float(r['tiempo_segundos']):.2f}",
            str(r["longitud_caracteres"]),
            rag_str,
            str(r["estado"]),
        ])
    add_table_fn(doc, run_headers, run_rows)

    for cap_file, cap_title in [
        (figures_dir / "captura_consola_experiment_runner.png", "Figura 6.3. Evidencia de ejecución automatizada de experiment_runner.py en consola (24/24 corridas exitosas)."),
        (figures_dir / "captura_prototipo_streamlit.png", "Figura 6.4. Interfaz gráfica del prototipo funcional en Streamlit (src/app.py) mostrando generación MADR y trazabilidad RAG."),
    ]:
        if cap_file.exists():
            doc.add_picture(str(cap_file), width=Inches(6.2))
            cp = doc.add_paragraph(cap_title)
            cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cp.runs[0].italic = True
