"""
Interfaz Web Interactiva en Streamlit del Asistente de Decisiones Arquitectónicas (ADR)
asistido por IA (SWEBOK v4.0 Cap. 02 + ChromaDB RAG + MADR).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adr_assistant import (
    CONTROL_MAX_OUTPUT_TOKENS,
    CONTROL_TEMPERATURE,
    DEFAULT_MODEL_ID,
    GeminiADRClient,
    generate_guided_rag_adr,
    generate_zero_shot,
)
from src.rag_engine import SwebokRAGEngine


st.set_page_config(
    page_title="Asistente ADR Híbrido (SWEBOK v4.0 + RAG)",
    page_icon="🏛️",
    layout="wide",
)


@st.cache_resource
def get_rag_engine() -> SwebokRAGEngine:
    return SwebokRAGEngine()


@st.cache_data
def load_dataset() -> list[dict]:
    dataset_path = PROJECT_ROOT / "dataset" / "escenarios_adr.json"
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    st.title("🏛️ Asistente de Decisiones Arquitectónicas (ADR) Asistido por IA")
    st.caption(
        "UNSA — Tópicos Avanzados en Ingeniería de Software (Hito 2) | "
        "Fundamentado en SWEBOK v4.0 Cap. 02, ChromaDB RAG y Plantilla Formal MADR"
    )

    scenarios = load_dataset()
    scenario_map = {
        f"{item['id_caso']} — {item['titulo_problema']}": item for item in scenarios
    }

    with st.sidebar:
        st.header("⚙️ Configuración Experimental")
        model_id = st.selectbox(
            "Modelo Gemini (Google AI Studio)",
            options=[
                DEFAULT_MODEL_ID,
                "gemini-2.5-flash",
                "gemini-3.5-flash",
                "gemini-3.7-flash",
            ],
            index=0,
        )
        temperature = st.slider(
            "Temperatura (Variable de Control)",
            min_value=0.0,
            max_value=1.0,
            value=float(CONTROL_TEMPERATURE),
            step=0.05,
            help="Fijada en 0.2 según el protocolo experimental para favorecer determinismo técnico.",
        )
        top_k = st.slider(
            "Fragmentos SWEBOK v4.0 a recuperar (RAG Top-K)",
            min_value=1,
            max_value=5,
            value=3,
        )
        st.markdown("---")
        st.markdown(
            "**Stack Tecnológico:**\n"
            f"- **LLM:** `{model_id}` (`temp={temperature}`)\n"
            "- **Vector DB:** `ChromaDB 1.5.9`\n"
            "- **Embeddings:** `all-MiniLM-L6-v2`\n"
            "- **Estándar:** `MADR (7 secciones)`"
        )

    tab_gen, tab_comp, tab_kb = st.tabs(
        [
            "🚀 Generador y Orquestador ADR",
            "📊 Explorador de Corridas (T1 vs. T2)",
            "📚 Base Vectorial SWEBOK v4.0 (ChromaDB)",
        ]
    )

    with tab_gen:
        col_left, col_right = st.columns([1, 1])
        with col_left:
            st.subheader("1. Definición del Escenario Arquitectónico")
            modo_entrada = st.radio(
                "Fuente del escenario:",
                options=["Cargar del Dataset Experimental (12 Casos)", "Escenario Personalizado"],
                horizontal=True,
            )

            if modo_entrada == "Cargar del Dataset Experimental (12 Casos)":
                selected_label = st.selectbox(
                    "Seleccione un caso experimental:",
                    options=list(scenario_map.keys()),
                )
                base_case = scenario_map[selected_label]
            else:
                base_case = {
                    "id_caso": "CASO_CUSTOM",
                    "titulo_problema": "Selección de arquitectura de comunicación entre servicios",
                    "contexto": "Describa el sistema, volumen de usuarios y problema arquitectónico actual...",
                    "drivers_arquitectonicos": [
                        "Escalabilidad",
                        "Mantenibilidad",
                        "Tolerancia a fallos",
                    ],
                    "restricciones": [
                        "Equipo pequeño",
                        "Despliegue en contenedores Docker",
                    ],
                }

            id_caso = st.text_input("ID del Caso", value=base_case["id_caso"])
            titulo = st.text_input("Título del Problema", value=base_case["titulo_problema"])
            contexto = st.text_area("Contexto y Problema", value=base_case["contexto"], height=110)
            drivers_text = st.text_area(
                "Drivers Arquitectónicos (ASRs, uno por línea)",
                value="\n".join(base_case["drivers_arquitectonicos"]),
                height=90,
            )
            restricciones_text = st.text_area(
                "Restricciones Técnicas y Organizacionales (una por línea)",
                value="\n".join(base_case["restricciones"]),
                height=90,
            )

            tratamiento_sel = st.radio(
                "Tratamiento Experimental a Ejecutar:",
                options=[
                    "T2 — Propuesta (Secuencia de 3 Prompts + RAG SWEBOK v4.0 + Abogado del Diablo + MADR)",
                    "T1 — Línea Base (Zero-Shot Estándar directo)",
                ],
            )
            btn_ejecutar = st.button("✨ Generar Registro de Decisión Arquitectónica (ADR)", type="primary")

        with col_right:
            st.subheader("2. Resultado de la Generación y Trazabilidad")
            if btn_ejecutar:
                scenario_input = {
                    "id_caso": id_caso.strip(),
                    "titulo_problema": titulo.strip(),
                    "contexto": contexto.strip(),
                    "drivers_arquitectonicos": [
                        d.strip() for d in drivers_text.splitlines() if d.strip()
                    ],
                    "restricciones": [
                        r.strip() for r in restricciones_text.splitlines() if r.strip()
                    ],
                }
                client = GeminiADRClient(
                    model_id=model_id,
                    temperature=temperature,
                    max_output_tokens=CONTROL_MAX_OUTPUT_TOKENS,
                )
                if tratamiento_sel.startswith("T2"):
                    with st.spinner(
                        "Ejecutando Pipeline T2: Recuperando SWEBOK v4.0 en ChromaDB → Etapa 1 (ASRs) → Etapa 2 (Abogado del Diablo) → Etapa 3 (Síntesis MADR)..."
                    ):
                        rag = get_rag_engine()
                        res = generate_guided_rag_adr(
                            scenario_input, rag_engine=rag, client=client, top_k_rag=top_k
                        )
                else:
                    with st.spinner("Ejecutando Tratamiento T1 (Zero-Shot Estándar)..."):
                        res = generate_zero_shot(scenario_input, client=client)

                st.success(
                    f"✅ ADR generado exitosamente con **{res['tratamiento']}** "
                    f"| Modelo: `{res['modelo']}` | Tiempo (TG): **{res['tiempo_segundos']:.2f} s**"
                )

                if res["fragmentos_rag"]:
                    with st.expander("🔍 Fragmentos Recuperados de ChromaDB (SWEBOK v4.0 Cap. 02)", expanded=True):
                        for frag in res["fragmentos_rag"]:
                            st.markdown(
                                f"**`{frag['id_fragmento']}` — {frag['tema']}** "
                                f"*(Similitud Coseno: `{frag['similitud_coseno']:.3f}`)*\n\n"
                                f"> {frag['documento']}"
                            )

                if res["etapas_intermedias"]:
                    with st.expander("🧠 Razonamiento Intermedio: Etapa 1 (ASRs) y Etapa 2 (Abogado del Diablo)"):
                        st.markdown("#### Etapa 1: Análisis de ASRs y Tácticas SWEBOK v4.0")
                        st.markdown(res["etapas_intermedias"].get("etapa_1_asr_rag", ""))
                        st.markdown("---")
                        st.markdown("#### Etapa 2: Exploración de Alternativas y Abogado del Diablo")
                        st.markdown(res["etapas_intermedias"].get("etapa_2_abogado_diablo", ""))

                st.download_button(
                    label=f"📥 Descargar {id_caso}_{res['tratamiento']}.md",
                    data=res["adr_markdown"],
                    file_name=f"{id_caso}_{res['tratamiento']}.md",
                    mime="text/markdown",
                )
                st.markdown("### Vista Previa del Documento MADR")
                st.markdown(res["adr_markdown"])
            else:
                # Si ya existen resultados pre-generados en output/T2, mostrar el del caso seleccionado
                t2_file = PROJECT_ROOT / "output" / "T2" / f"{base_case['id_caso']}_T2.md"
                if t2_file.exists():
                    st.info(
                        f"Mostrando ADR pre-calculado en corrida experimental para **{base_case['id_caso']} (Tratamiento T2)**. "
                        "Presione el botón de la izquierda para ejecutar en vivo."
                    )
                    content_md = t2_file.read_text(encoding="utf-8")
                    st.download_button(
                        label=f"📥 Descargar {base_case['id_caso']}_T2.md",
                        data=content_md,
                        file_name=f"{base_case['id_caso']}_T2.md",
                        mime="text/markdown",
                    )
                    st.markdown(content_md)

    with tab_comp:
        st.subheader("Comparación Lado a Lado de Archivos Generados (T1 Zero-Shot vs. T2 Propuesto)")
        selected_comp = st.selectbox(
            "Seleccione el escenario para comparar sus salidas experimentales:",
            options=list(scenario_map.keys()),
            key="comp_selector",
        )
        case_id = scenario_map[selected_comp]["id_caso"]
        p_t1 = PROJECT_ROOT / "output" / "T1" / f"{case_id}_T1.md"
        p_t2 = PROJECT_ROOT / "output" / "T2" / f"{case_id}_T2.md"
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"#### 📄 Tratamiento 1 (Zero-Shot) — `{case_id}_T1.md`")
            if p_t1.exists():
                st.markdown(p_t1.read_text(encoding="utf-8"))
            else:
                st.warning("Aún no se ha ejecutado `experiment_runner.py` para este caso.")
        with c2:
            st.markdown(f"#### 🏛️ Tratamiento 2 (Propuesto RAG + MADR) — `{case_id}_T2.md`")
            if p_t2.exists():
                st.markdown(p_t2.read_text(encoding="utf-8"))
            else:
                st.warning("Aún no se ha ejecutado `experiment_runner.py` para este caso.")

    with tab_kb:
        st.subheader("Corpus Conocimiento Arquitectónico Indexado en ChromaDB (SWEBOK v4.0 Cap. 02)")
        rag = get_rag_engine()
        q_test = st.text_input(
            "Probar búsqueda vectorial en ChromaDB:",
            value="Desacoplamiento temporal y reprocesamiento de eventos ante picos de carga",
        )
        if q_test:
            frags = rag.retrieve_context(q_test, top_k=top_k)
            for f_item in frags:
                st.markdown(
                    f"**`{f_item['id_fragmento']}` | {f_item['seccion_swebok']} — {f_item['tema']}** "
                    f"(Similitud Coseno: `{f_item['similitud_coseno']:.4f}`)"
                )
                st.caption(f"Palabras clave: {f_item['palabras_clave']}")
                st.write(f_item["documento"])
                st.divider()


if __name__ == "__main__":
    main()
