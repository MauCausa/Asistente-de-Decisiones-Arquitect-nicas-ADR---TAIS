"""
Generador automatizado de entregables documentales extendidos para el Hito 2:
- Secciones 6.1, 6.2, 6.3 y Anexo de Repositorio GitHub (Integrante 3: Mauricio Elias Congona Manrique)
- Secciones 7.1, 7.2, 7.3, 7.4, Sección 8 (Conclusiones) y Anexo de Evaluación Estadística (Integrante 4: Javier Coronado Peña)
Genera tanto archivos Markdown (.md) como documentos Word (.docx) de alta profundidad técnica y académica.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
import pandas as pd

from src.report_sections_i3 import add_i3_to_word, build_i3_markdown
from src.report_sections_i4 import add_i4_to_word, build_i4_markdown

PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = PROJECT_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
DOC_DIR = PROJECT_ROOT / "documento"
OUT_T1_DIR = PROJECT_ROOT / "output" / "T1"
OUT_T2_DIR = PROJECT_ROOT / "output" / "T2"
CORPUS_PATH = PROJECT_ROOT / "knowledge_base" / "swebok_cap02_corpus.json"


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
                r.font.size = Pt(9.0)

    for row_vals in rows:
        row_cells = table.add_row().cells
        for idx, val in enumerate(row_vals):
            row_cells[idx].text = str(val)
            for p in row_cells[idx].paragraphs:
                for r in p.runs:
                    r.font.size = Pt(8.5)
    doc.add_paragraph()


def generate_all_documents() -> None:
    DOC_DIR.mkdir(parents=True, exist_ok=True)

    summary_df = pd.read_csv(RESULTS_DIR / "tabla_resultados_globales.csv")
    eval_df = pd.read_csv(RESULTS_DIR / "evaluacion_completa.csv")
    metrics_df = pd.read_csv(RESULTS_DIR / "metricas_ejecucion.csv")
    corpus_list = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

    by_metric = {row["Metrica"]: row for _, row in summary_df.iterrows()}
    modelo_usado = str(metrics_df["modelo"].iloc[0]) if not metrics_df.empty else "gemini-3.5-flash"

    caso01_t1 = (OUT_T1_DIR / "CASO_01_T1.md").read_text(encoding="utf-8")
    caso01_t2 = (OUT_T2_DIR / "CASO_01_T2.md").read_text(encoding="utf-8")

    header_md = (
        "# Entregable Hito 2 — Secciones 6, 7, 8 y Anexos (Versión Extendida y Detallada)\n\n"
        "**Universidad Nacional de San Agustín de Arequipa (UNSA)**  \n"
        "**Facultad de Ingeniería de Producción y Servicios — Escuela Profesional de Ingeniería de Sistemas**  \n"
        "**Curso:** Tópicos Avanzados en Ingeniería de Software — 2026  \n"
        "**Docente:** Ing. Robert Edison Arisaca Mamani  \n"
        "**Responsables:**\n"
        "- **Integrante 3:** Mauricio Elias Congona Manrique *(Sección 6: Arquitectura del Prototipo, Stack Tecnológico, Orquestación IA/RAG, Ejecución Experimental y Anexo de Repositorio en GitHub)*\n"
        "- **Integrante 4:** Javier Coronado Peña *(Sección 7: Evaluación Cuantitativa/Cualitativa, Fundamentación Matemática de Tests Estadísticos y Amenazas a la Validez; Sección 8: Conclusiones y Trabajos Futuros; Anexo de Evaluación Ciega)*\n\n"
        "---\n\n"
    )

    md_i3 = build_i3_markdown(modelo_usado, corpus_list, metrics_df, _df_to_markdown)
    md_i4 = build_i4_markdown(
        by_metric,
        eval_df,
        modelo_usado,
        caso01_t1,
        caso01_t2,
        _extract_snippet,
        _df_to_markdown,
    )

    md_path = DOC_DIR / "Aporte_Integrantes_3_y_4_Hito2.md"
    md_path.write_text(header_md + md_i3 + "\n" + md_i4, encoding="utf-8")

    # Generar documento Word (.docx)
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_t = title_p.add_run(
        "Universidad Nacional de San Agustín de Arequipa\n"
        "Escuela Profesional de Ingeniería de Sistemas\n"
        "Hito 2: Diseño, Implementación y Evaluación Experimental de un Asistente de "
        "Decisiones Arquitectónicas (ADR) Basado en Inteligencia Artificial\n"
        "Aporte Técnico Extendido — Integrantes 3 y 4 (Secciones 6, 7, 8 y Anexos)"
    )
    run_t.bold = True
    run_t.font.size = Pt(14)
    run_t.font.color.rgb = RGBColor(24, 58, 108)

    meta_p = doc.add_paragraph()
    meta_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta_p.add_run(
        "Curso: Tópicos Avanzados en Ingeniería de Software — UNSA 2026\n"
        "Docente: Ing. Robert Edison Arisaca Mamani\n"
        "Integrante 3: Mauricio Elias Congona Manrique (Arquitectura, Stack, RAG y Ejecución Experimental)\n"
        "Integrante 4: Javier Coronado Peña (Evaluación, Pruebas Estadísticas de Wilcoxon/t-Student, Resultados y Conclusiones)"
    ).italic = True

    add_i3_to_word(
        doc,
        modelo_usado,
        corpus_list,
        metrics_df,
        FIGURES_DIR,
        _add_formatted_table,
        Pt,
        Inches,
        WD_ALIGN_PARAGRAPH,
    )
    add_i4_to_word(
        doc,
        by_metric,
        eval_df,
        modelo_usado,
        caso01_t1,
        caso01_t2,
        FIGURES_DIR,
        _extract_snippet,
        _add_formatted_table,
        Inches,
        WD_ALIGN_PARAGRAPH,
    )

    docx_path = DOC_DIR / "Aporte_Integrantes_3_y_4_Hito2.docx"
    doc.save(docx_path)
    print(f"Documentos extendidos generados exitosamente:\n - {md_path}\n - {docx_path}")


if __name__ == "__main__":
    generate_all_documents()
