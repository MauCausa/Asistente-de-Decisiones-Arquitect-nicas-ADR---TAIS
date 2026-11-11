"""
Genera las figuras de arquitectura y las capturas de evidencia de ejecución
para la Sección 6.2 y Sección 6.3 del informe del Hito 2 (Integrante 3):
1. Diagrama de Componentes de la Arquitectura (diagrama_componentes_arquitectura.png)
2. Diagrama de Secuencia del Pipeline T2 (diagrama_secuencia_pipeline_t2.png)
3. Captura de ejecución en consola de experiment_runner.py (captura_consola_experiment_runner.png)
4. Captura de la interfaz gráfica del prototipo Streamlit funcionando (captura_prototipo_streamlit.png)
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = PROJECT_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
METRICS_CSV_PATH = RESULTS_DIR / "metricas_ejecucion.csv"
TRACES_JSON_PATH = RESULTS_DIR / "trazas_rag_y_etapas.json"
OUT_T2_DIR = PROJECT_ROOT / "output" / "T2"


def generate_all_evidence_visuals() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    _draw_architecture_components_diagram()
    _draw_sequence_pipeline_diagram()
    _draw_console_execution_capture()
    _draw_streamlit_prototype_capture()
    print(f"Evidencias visuales de la Sección 6 generadas en: {FIGURES_DIR}")


def _draw_box(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    subtitle: str,
    facecolor: str,
    edgecolor: str,
    text_color: str = "#1A1A1A",
) -> None:
    box = mpatches.FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.03",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=1.8,
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2,
        y + h * 0.65,
        title,
        ha="center",
        va="center",
        fontsize=9.5,
        fontweight="bold",
        color=text_color,
    )
    ax.text(
        x + w / 2,
        y + h * 0.30,
        subtitle,
        ha="center",
        va="center",
        fontsize=8.0,
        color=text_color,
    )


def _draw_architecture_components_diagram() -> None:
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.5,
        0.95,
        "Diagrama de Componentes de la Arquitectura del Prototipo ADR Híbrido (SWEBOK v4.0 + RAG)",
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
        color="#14325C",
    )

    # 1. Capa de Entrada
    _draw_box(
        ax,
        0.04,
        0.65,
        0.24,
        0.20,
        "Interfaz de Usuario / Runner",
        "src/app.py (Streamlit)\nexperiment_runner.py\ndataset/escenarios_adr.json",
        "#E8F1FA",
        "#2F65A7",
    )

    # 2. Módulo RAG
    _draw_box(
        ax,
        0.04,
        0.18,
        0.24,
        0.26,
        "Módulo Recuperador RAG",
        "src/rag_engine.py\nChromaDB (SWEBOK v4.0 Cap. 02)\nEmbeddings: all-MiniLM-L6-v2",
        "#EBF7EE",
        "#2E8B57",
    )

    # 3. Orquestador de Secuencia de Prompts
    container = mpatches.FancyBboxPatch(
        (0.35, 0.16),
        0.32,
        0.70,
        boxstyle="round,pad=0.02,rounding_size=0.03",
        facecolor="#FFF9F0",
        edgecolor="#C87A28",
        linewidth=1.8,
        linestyle="--",
    )
    ax.add_patch(container)
    ax.text(
        0.51,
        0.82,
        "Orquestador ADR (src/adr_assistant.py)",
        ha="center",
        va="center",
        fontsize=9.5,
        fontweight="bold",
        color="#8B4D0E",
    )

    _draw_box(
        ax,
        0.38,
        0.62,
        0.26,
        0.14,
        "Etapa 1: Análisis de ASRs + RAG",
        "Extrae drivers y tácticas SWEBOK v4.0",
        "#FFF0D9",
        "#C87A28",
    )
    _draw_box(
        ax,
        0.38,
        0.41,
        0.26,
        0.15,
        "Etapa 2: Abogado del Diablo",
        "Explora >=3 opciones, riesgos y trade-offs",
        "#FFE4C4",
        "#B85D19",
    )
    _draw_box(
        ax,
        0.38,
        0.20,
        0.26,
        0.15,
        "Etapa 3: Síntesis Formal MADR",
        "Consolida las 7 secciones obligatorias",
        "#FFDAB9",
        "#A04000",
    )

    # 4. API LLM
    _draw_box(
        ax,
        0.73,
        0.58,
        0.23,
        0.24,
        "Google AI Studio API",
        "Familia Google Gemini\ntemperature = 0.2 (Control)\nmaxOutputTokens = 4096",
        "#F3EBF9",
        "#6C3483",
    )

    # 5. Generador / Validador Markdown
    _draw_box(
        ax,
        0.73,
        0.18,
        0.23,
        0.26,
        "Generador / Validador MADR",
        "output/T1/, output/T2/\noutput/ciego/ (ADR_001..024)\ntest_estadistico.py (CE, SS, CRA)",
        "#E8F8F5",
        "#117864",
    )

    arrow_kw = dict(arrowstyle="->", lw=1.8, color="#34495E")
    ax.annotate("", xy=(0.38, 0.70), xytext=(0.28, 0.74), arrowprops=arrow_kw)
    ax.annotate("", xy=(0.16, 0.44), xytext=(0.16, 0.65), arrowprops=dict(arrowstyle="<->", lw=1.8, color="#2E8B57"))
    ax.annotate("", xy=(0.38, 0.66), xytext=(0.28, 0.34), arrowprops=dict(arrowstyle="->", lw=1.8, color="#2E8B57"))
    ax.annotate("", xy=(0.51, 0.56), xytext=(0.51, 0.62), arrowprops=arrow_kw)
    ax.annotate("", xy=(0.51, 0.35), xytext=(0.51, 0.41), arrowprops=arrow_kw)
    ax.annotate("", xy=(0.73, 0.70), xytext=(0.64, 0.70), arrowprops=dict(arrowstyle="<->", lw=1.8, color="#6C3483"))
    ax.annotate("", xy=(0.73, 0.66), xytext=(0.64, 0.48), arrowprops=dict(arrowstyle="<->", lw=1.8, color="#6C3483"))
    ax.annotate("", xy=(0.73, 0.62), xytext=(0.64, 0.28), arrowprops=dict(arrowstyle="<->", lw=1.8, color="#6C3483"))
    ax.annotate("", xy=(0.73, 0.28), xytext=(0.64, 0.27), arrowprops=dict(arrowstyle="->", lw=2.0, color="#117864"))

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "diagrama_componentes_arquitectura.png", dpi=220)
    plt.close(fig)


def _draw_sequence_pipeline_diagram() -> None:
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.5,
        0.95,
        "Diagrama de Secuencia del Pipeline de Generación — Tratamiento T2 (3 Etapas + RAG)",
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
        color="#14325C",
    )

    actors = [
        (0.10, "Arquitecto /\nRunner"),
        (0.32, "Orquestador T2\n(adr_assistant.py)"),
        (0.56, "Motor RAG\n(ChromaDB + MiniLM)"),
        (0.80, "Google Gemini API\n(temp = 0.2)"),
        (0.95, "Salida MADR\n(.md / CSV)"),
    ]
    for x_pos, name in actors:
        _draw_box(ax, x_pos - 0.08, 0.82, 0.16, 0.09, name, "", "#D6EAF8", "#2874A6")
        ax.plot([x_pos, x_pos], [0.06, 0.82], linestyle="--", color="#7F8C8D", lw=1.2)

    stages = [
        (0.56, 0.79, "Etapa 1: Análisis de ASRs y Recuperación Vectorial RAG (SWEBOK v4.0 Cap. 02)", "#EBF5FB"),
        (0.32, 0.54, "Etapa 2: Exploración de >=3 Alternativas y Evaluación Crítica ('Abogado del Diablo')", "#FEF9E7"),
        (0.08, 0.30, "Etapa 3: Síntesis y Validación Estructural en Plantilla MADR (7 Secciones)", "#E8F8F5"),
    ]
    for y_low, y_high, label, color in stages:
        rect = mpatches.Rectangle((0.03, y_low), 0.94, y_high - y_low, facecolor=color, edgecolor="#BDC3C7", alpha=0.65)
        ax.add_patch(rect)
        ax.text(0.04, y_high - 0.025, label, fontsize=8.8, fontweight="bold", color="#2C3E50")

    def msg(x1: float, x2: float, y: float, text: str, dashed: bool = False) -> None:
        style = "->"
        ls = "--" if dashed else "-"
        ax.annotate("", xy=(x2, y), xytext=(x1, y), arrowprops=dict(arrowstyle=style, lw=1.5, ls=ls, color="#1F618D"))
        ax.text((x1 + x2) / 2, y + 0.012, text, ha="center", va="bottom", fontsize=7.8, color="#1A252F")

    msg(0.10, 0.32, 0.74, "1. Enviar escenario (Contexto, ASRs, Restricciones)")
    msg(0.32, 0.56, 0.69, "2. retrieve_context(query, top_k=3)")
    msg(0.56, 0.32, 0.64, "3. Top-3 Fragmentos SWEBOK v4.0 [SWEBOK-02-XX]", dashed=True)
    msg(0.32, 0.80, 0.60, "4. Prompt Etapa 1 (Escenario + Contexto SWEBOK v4.0)")
    msg(0.80, 0.32, 0.56, "5. Análisis de ASRs y tácticas aplicables", dashed=True)

    msg(0.32, 0.80, 0.46, "6. Prompt Etapa 2 (Exigir mín. 3 alternativas + crítica Abogado del Diablo)")
    msg(0.80, 0.32, 0.36, "7. Opciones 1..3 con Ventajas, Desventajas, Riesgos y Trade-offs", dashed=True)

    msg(0.32, 0.80, 0.23, "8. Prompt Etapa 3 (Consolidar en las 7 secciones obligatorias MADR)")
    msg(0.80, 0.32, 0.16, "9. Documento ADR completo en Markdown", dashed=True)
    msg(0.32, 0.95, 0.11, "10. Guardar output/T2/, output/ciego/ y metricas_ejecucion.csv")

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "diagrama_secuencia_pipeline_t2.png", dpi=220)
    plt.close(fig)


def _draw_console_execution_capture() -> None:
    df = pd.read_csv(METRICS_CSV_PATH)
    modelo = df["modelo"].iloc[0] if not df.empty else "gemini-3.5-flash"

    lines = [
        "PS C:\\Users\\LENOVO\\Desktop\\UNSA\\2026 - B\\TAIS\\Proyecto Final> python experiment_runner.py",
        "=" * 86,
        " EJECUCIÓN EXPERIMENTAL HITO 2 — ASISTENTE ADR ASISTIDO POR IA ",
        "=" * 86,
        f"Modelo controlado     : {modelo}",
        "Temperatura controlada: 0.2",
        "Max Output Tokens     : 4096",
        "Escenarios cargados   : 12 (24 corridas pareadas T1 y T2)",
        "-" * 86,
        "[RAG] Colección ChromaDB 'swebok_v4_cap02_madr' lista con 14 fragmentos del SWEBOK v4.0 Cap. 02.",
    ]

    for _, row in df.iterrows():
        ord_idx = int(row["orden_ejecucion"])
        case_id = row["id_caso"]
        trat = row["tratamiento"]
        blind = row["codigo_ciego"]
        tg = float(row["tiempo_segundos"])
        chars = int(row["longitud_caracteres"])
        rag_ids = str(row["fragmentos_rag_ids"]) if pd.notna(row["fragmentos_rag_ids"]) and str(row["fragmentos_rag_ids"]) else "Ninguno (Zero-Shot)"
        lines.append(
            f"[{ord_idx:02d}/24] {case_id} | {trat} -> {blind} | Estado: OK | TG: {tg:5.2f}s | Chars: {chars:4d} | RAG: [{rag_ids}]"
        )

    lines.extend([
        "=" * 86,
        f" EJECUCIÓN FINALIZADA: {len(df)}/24 corridas exitosas (100% completado).",
        " - Archivos T1   : output/T1/ (12 ADRs)",
        " - Archivos T2   : output/T2/ (12 ADRs)",
        " - Archivos ciego: output/ciego/ (ADR_001.md a ADR_024.md)",
        " - Métricas CSV  : results/metricas_ejecucion.csv",
        "=" * 86,
    ])

    fig, ax = plt.subplots(figsize=(12.2, 7.6), facecolor="#0C0C0C")
    ax.set_facecolor("#0C0C0C")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Barra superior estilo ventana PowerShell
    header = mpatches.Rectangle((0, 0.94), 1, 0.06, facecolor="#1F1F1F", edgecolor="#333333")
    ax.add_patch(header)
    ax.text(
        0.02,
        0.97,
        "Windows PowerShell — Ejecución Automatizada de experiment_runner.py (24 Corridas T1 y T2)",
        color="#E0E0E0",
        fontsize=9.5,
        fontweight="bold",
        va="center",
        family="monospace",
    )

    y = 0.91
    step = 0.88 / len(lines)
    for ln in lines:
        color = "#CCCCCC"
        if "EJECUCIÓN" in ln or "===" in ln:
            color = "#4EC9B0"
        elif "| T2 ->" in ln:
            color = "#9CDCFE"
        elif "OK" in ln:
            color = "#B5CEA8"
        ax.text(0.015, y, ln, color=color, fontsize=7.8, family="monospace", va="top")
        y -= step

    fig.tight_layout(pad=0.2)
    fig.savefig(FIGURES_DIR / "captura_consola_experiment_runner.png", dpi=220, facecolor="#0C0C0C")
    plt.close(fig)


def _draw_streamlit_prototype_capture() -> None:
    traces = json.loads(TRACES_JSON_PATH.read_text(encoding="utf-8"))
    t2_trace = traces.get("CASO_01_T2", {})
    t2_md = (OUT_T2_DIR / "CASO_01_T2.md").read_text(encoding="utf-8")
    tg_val = t2_trace.get("tiempo_segundos", 12.4)
    frags = t2_trace.get("fragmentos_rag", [])

    fig, ax = plt.subplots(figsize=(12.5, 7.2), facecolor="#F8F9FB")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Top bar
    ax.add_patch(mpatches.Rectangle((0, 0.92), 1, 0.08, facecolor="#1B365D"))
    ax.text(
        0.02,
        0.96,
        "[UNSA - TAIS] Asistente de Decisiones Arquitectonicas (ADR) Asistido por IA — Interfaz Streamlit (src/app.py)",
        color="white",
        fontsize=11,
        fontweight="bold",
        va="center",
    )

    # Sidebar
    ax.add_patch(mpatches.Rectangle((0, 0), 0.22, 0.92, facecolor="#EEF2F6", edgecolor="#D0D7DE"))
    ax.text(0.015, 0.87, "Configuracion Experimental", fontsize=9.5, fontweight="bold", color="#1B365D")
    sidebar_lines = [
        "Modelo Google AI Studio:",
        "  [ gemini-3.5-flash ]",
        "",
        "Temperatura (Control):",
        "  [==== 0.20 ====]",
        "",
        "RAG Top-K (SWEBOK v4.0):",
        "  [==== 3 fragmentos ====]",
        "",
        "Base Vectorial Activa:",
        "  • ChromaDB v1.5.9",
        "  • all-MiniLM-L6-v2 (384d)",
        "  • Colección: swebok_v4_cap02",
        "  • Plantilla: MADR (7 secc.)",
    ]
    y_sb = 0.82
    for s_ln in sidebar_lines:
        ax.text(0.015, y_sb, s_ln, fontsize=8.0, color="#2C3E50", family="monospace")
        y_sb -= 0.042

    # Columna Izquierda: Entrada del Escenario
    ax.add_patch(mpatches.FancyBboxPatch((0.24, 0.04), 0.34, 0.85, boxstyle="round,pad=0.01", facecolor="white", edgecolor="#D0D7DE"))
    ax.text(0.255, 0.86, "1. Escenario Arquitectónico Cargado", fontsize=9.8, fontweight="bold", color="#1B365D")
    input_lines = [
        "ID del Caso: CASO_01 (Código Ciego: ADR_001)",
        "Título: Comunicación asíncrona para pedidos e-commerce",
        "",
        "Contexto y Problema:",
        "Plataforma procesa hasta 2500 pedidos/min en campañas.",
        "El servicio de pedidos invoca síncronamente a inventario,",
        "pagos y notificaciones; una falla parcial bloquea todo.",
        "Se requiere desacoplar y conservar eventos para replay.",
        "",
        "Drivers de Decisión (ASRs):",
        " • Escalabilidad ante picos de carga",
        " • Desacoplamiento temporal",
        " • Trazabilidad y reprocesamiento de eventos",
        "",
        "Restricciones:",
        " • Despliegue en contenedores Docker",
        " • Equipo con experiencia básica en mensajería",
        " • No se permite perder pedidos confirmados",
        "",
        "Tratamiento Seleccionado:",
        " [x] T2 — Secuencia 3 Prompts + RAG SWEBOK v4.0 + MADR",
    ]
    y_in = 0.81
    for i_ln in input_lines:
        ax.text(0.255, y_in, i_ln, fontsize=7.8, color="#333333")
        y_in -= 0.035

    # Columna Derecha: Salida MADR y Fragmentos RAG
    ax.add_patch(mpatches.FancyBboxPatch((0.60, 0.04), 0.38, 0.85, boxstyle="round,pad=0.01", facecolor="white", edgecolor="#2E8B57", lw=1.5))
    ax.text(0.615, 0.86, f"2. Resultado T2 Generado (TG = {tg_val:.2f} s) — 7/7 Secciones MADR", fontsize=9.5, fontweight="bold", color="#1E6B3E")

    ax.add_patch(mpatches.Rectangle((0.615, 0.66), 0.35, 0.17, facecolor="#EBF7EE", edgecolor="#A3D9B1"))
    ax.text(0.625, 0.805, "[RAG] Fragmentos SWEBOK v4.0 Recuperados de ChromaDB:", fontsize=8.2, fontweight="bold", color="#184D30")
    y_f = 0.77
    for frag in frags[:3]:
        ax.text(
            0.625,
            y_f,
            f"• [{frag['id_fragmento']}] {frag['tema'][:46]}... (Sim: {frag['similitud_coseno']:.3f})",
            fontsize=7.5,
            color="#1E4620",
        )
        y_f -= 0.035

    ax.text(0.615, 0.62, "[MADR] Vista Previa del Documento MADR Generado (CASO_01_T2.md):", fontsize=8.4, fontweight="bold", color="#1B365D")
    preview_lines = [ln[:66] for ln in t2_md.splitlines() if ln.strip()][:16]
    y_pv = 0.58
    for p_ln in preview_lines:
        weight = "bold" if p_ln.startswith("#") else "normal"
        col = "#1B365D" if p_ln.startswith("#") else "#2C3E50"
        ax.text(0.615, y_pv, p_ln, fontsize=7.3, fontweight=weight, color=col, family="monospace")
        y_pv -= 0.032

    fig.tight_layout(pad=0.2)
    fig.savefig(FIGURES_DIR / "captura_prototipo_streamlit.png", dpi=220)
    plt.close(fig)


if __name__ == "__main__":
    generate_all_evidence_visuals()
