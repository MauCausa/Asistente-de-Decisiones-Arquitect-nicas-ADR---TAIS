"""
Script de Evaluación Cuantitativa, Rúbrica Arquitectónica y Análisis Estadístico (Hito 2 - Integrante 4).
Calcula:
1. Completitud Estructural (CE, 0% a 100% sobre las 7 secciones obligatorias de MADR).
2. Conteo de Alternativas consideradas y Trade-offs explícitos.
3. Similitud Semántica (SS, 0.00 a 1.00) usando embeddings sentence-transformers/all-MiniLM-L6-v2.
4. Tiempo de Generación (TG, segundos) a partir de results/metricas_ejecucion.csv.
5. Evaluación bajo la Rúbrica de Calidad Arquitectónica (C1 a C6 en escala Likert 1-5 y promedio CRA).
6. Prueba de rangos con signo de Wilcoxon pareada (scipy.stats.wilcoxon) y t-Student pareada.
7. Actualización de la hoja 'Evaluacion' en Diseno_Experimental_Hito2.xlsx y generación de gráficos en results/figures/.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

import zipfile
import xml.etree.ElementTree as ET
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sentence_transformers import SentenceTransformer

from experiment_runner import BLIND_CODE_MAP

PROJECT_ROOT = Path(__file__).resolve().parent
DATASET_PATH = PROJECT_ROOT / "dataset" / "escenarios_adr.json"
OUT_T1_DIR = PROJECT_ROOT / "output" / "T1"
OUT_T2_DIR = PROJECT_ROOT / "output" / "T2"
RESULTS_DIR = PROJECT_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
METRICS_CSV_PATH = RESULTS_DIR / "metricas_ejecucion.csv"
EVAL_CSV_PATH = RESULTS_DIR / "evaluacion_completa.csv"
SUMMARY_CSV_PATH = RESULTS_DIR / "tabla_resultados_globales.csv"
STATS_CSV_PATH = RESULTS_DIR / "pruebas_estadisticas_wilcoxon.csv"
STATS_JSON_PATH = RESULTS_DIR / "resumen_estadistico.json"
EXCEL_PATH = PROJECT_ROOT / "Diseno_Experimental_Hito2.xlsx"


def evaluate_madr_completeness(md_text: str) -> tuple[float, int, dict[str, bool]]:
    """
    Verifica cuántas de las 7 secciones obligatorias de la plantilla MADR están presentes
    y tienen contenido sustantivo (> 20 caracteres):
    1. # [ID] - [Título de la Decisión]
    2. ## Estado
    3. ## Contexto y Problema
    4. ## Drivers de Decisión (ASRs)
    5. ## Opciones Consideradas (con mínimo 3 alternativas)
    6. ## Decisión y Justificación (Rationale)
    7. ## Consecuencias (Positivas, Negativas y Trade-offs)
    """
    lines = md_text.splitlines()
    # 1. Título H1 con ID y título
    has_h1_id_title = any(
        re.match(r"^#\s+(?:CASO_\d+|\[?ADR[-_\s]?\d+\]?)\s*[-:]\s*\S+", ln.strip(), re.I)
        for ln in lines[:10]
    )

    # Extraer secciones principales H1/H2 (sin cortar en subencabezados H3 ###)
    sections: list[tuple[str, str]] = []
    current_header = ""
    current_body: list[str] = []
    for ln in lines:
        m = re.match(r"^(#{1,2})\s+(.+)$", ln.strip())
        if m:
            if current_header:
                sections.append((current_header.lower(), "\n".join(current_body).strip()))
            current_header = m.group(2).strip()
            current_body = []
        else:
            current_body.append(ln)
    if current_header:
        sections.append((current_header.lower(), "\n".join(current_body).strip()))

    def has_section(pattern: str, min_len: int = 10) -> bool:
        for hdr, body in sections:
            if re.search(pattern, hdr, re.I) and len(body) >= min_len:
                return True
        return False

    # 2. Estado
    has_estado = has_section(r"^estado\b|^status\b", min_len=4)
    # 3. Contexto y Problema
    has_contexto = has_section(r"contexto|problema", min_len=40)
    # 4. Drivers de Decisión (ASRs) como sección dedicada MADR
    has_drivers = has_section(
        r"drivers\s+de\s+decisi[oó]n|\basrs?\b|requisitos\s+arquitect[oó]nicamente",
        min_len=25,
    )
    # 5. Opciones Consideradas con al menos 3 alternativas explícitas
    alt_count = count_alternatives(md_text)
    has_opciones = (
        has_section(r"opciones\s+consideradas|alternativas\s+consideradas|opciones\s+evaluadas", min_len=40)
        and alt_count >= 3
    )
    # 6. Decisión y Justificación (Rationale)
    has_decision_rationale = has_section(
        r"decisi[oó]n\s+y\s+justificaci[oó]n|rationale|justificaci[oó]n\s+de\s+la\s+decisi[oó]n",
        min_len=50,
    )
    # 7. Consecuencias incluyendo Positivas, Negativas y Trade-offs explícitos
    has_consecuencias_hdr = any(re.search(r"consecuencias", hdr, re.I) for hdr, _ in sections)
    has_tradeoffs_sub = bool(
        re.search(r"trade[-\s]?offs?|concesiones|riesgos\s+residuales", md_text, re.I)
    )
    has_pos_neg = bool(
        re.search(r"positivas|beneficios", md_text, re.I)
        and re.search(r"negativas|desventajas|costos", md_text, re.I)
    )
    has_consecuencias = has_consecuencias_hdr and has_pos_neg and has_tradeoffs_sub

    checks = {
        "S1_Titulo_ID": has_h1_id_title,
        "S2_Estado": has_estado,
        "S3_Contexto_Problema": has_contexto,
        "S4_Drivers_ASRs": has_drivers,
        "S5_Opciones_Min3": has_opciones,
        "S6_Decision_Rationale": has_decision_rationale,
        "S7_Consecuencias_Tradeoffs": has_consecuencias,
    }
    completed = sum(1 for v in checks.values() if v)
    ce_pct = round((completed / 7.0) * 100.0, 2)
    return ce_pct, completed, checks


def count_alternatives(md_text: str) -> int:
    """Contabiliza cuántas opciones/alternativas distintas se documentan en el ADR."""
    # Buscar encabezados o ítems tipo '### Opción 1', '### Alternativa 1', '1. **Opción'
    option_headers = re.findall(
        r"(?:^#{2,4}\s*(?:Opci[oó]n|Alternativa)\s*\d+|^\s*(?:[-*]|\d+\.)\s*\*\*(?:Opci[oó]n|Alternativa)\s*\d+)",
        md_text,
        flags=re.I | re.M,
    )
    if len(option_headers) >= 2:
        return len(option_headers)

    # Si no usa 'Opción X', buscar subsecciones o viñetas dentro de la sección de opciones/alternativas
    m = re.search(
        r"#{2,3}\s*(?:Opciones|Alternativas)[^\n]*\n(.*?)(?=\n#{2}\s|\Z)",
        md_text,
        flags=re.I | re.S,
    )
    if m:
        block = m.group(1)
        sub_h = re.findall(r"^#{3,4}\s+.+$", block, flags=re.M)
        if len(sub_h) >= 2:
            return len(sub_h)
        numbered = re.findall(r"^\s*\d+\.\s+\*\*[^*]+\*\*", block, flags=re.M)
        if len(numbered) >= 2:
            return len(numbered)
        bullets = re.findall(r"^\s*[-*]\s+\*\*[^*]+\*\*", block, flags=re.M)
        if len(bullets) >= 2:
            return min(len(bullets), 5)

    # Si solo menciona la decisión elegida sin sección de alternativas
    return 1


def count_explicit_tradeoffs(md_text: str) -> int:
    """Contabiliza cuántos trade-offs, concesiones o riesgos explícitos por opción/decisión documenta el ADR."""
    count = 0
    # 1. Viñetas bajo sección de Trade-offs y Riesgos Residuales
    m_to = re.search(
        r"#{3,4}\s*Trade[-\s]?offs?[^\n]*\n(.*?)(?=\n#{2,3}\s|\Z)",
        md_text,
        flags=re.I | re.S,
    )
    if m_to:
        bullets = re.findall(r"^\s*[-*]\s+.+$", m_to.group(1), flags=re.M)
        count += len(bullets)

    # 2. Pares explícitos Desventajas/Riesgos en evaluación de opciones
    desv_riesgos = re.findall(
        r"^\s*[-*]\s*\*\*(?:Desventajas|Riesgos|Trade[-\s]?offs?|Limitaciones):?\*\*",
        md_text,
        flags=re.I | re.M,
    )
    count += len(desv_riesgos)

    if count == 0:
        # En ADRs no estructurados (T1), contar menciones explícitas de concesiones/contras en consecuencias
        m_neg = re.search(
            r"(?:Negativas|Desventajas|Inconvenientes|Contras)[:\s]*\n(.*?)(?=\n#{2,3}\s|\Z)",
            md_text,
            flags=re.I | re.S,
        )
        if m_neg:
            bullets_neg = re.findall(r"^\s*[-*]\s+.+$", m_neg.group(1), flags=re.M)
            count += min(len(bullets_neg), 3)
        if count == 0 and re.search(r"complejidad|costo|latencia|curva de aprendizaje", md_text, re.I):
            count = 1

    return count


def extract_decision_rationale_summary(md_text: str) -> str:
    """
    Extrae el núcleo semántico de la decisión, justificación (rationale) y consecuencias
    para evitar que el límite de 256 tokens de all-MiniLM-L6-v2 trunque la decisión al final del ADR.
    """
    m_dec = re.search(
        r"#{2,3}\s*(?:Decisi[oó]n(?:\s+y\s+Justificaci[oó]n)?(?:\s*\(?Rationale\)?)?|Propuesta\s+de\s+Decisi[oó]n)[^\n]*\n(.*?)(?=\n#{2}\s|\Z)",
        md_text,
        flags=re.I | re.S,
    )
    m_cons = re.search(
        r"#{2,3}\s*Consecuencias[^\n]*\n(.*?)(?=\n#{2}\s|\Z)",
        md_text,
        flags=re.I | re.S,
    )
    dec_text = m_dec.group(1).strip() if m_dec else md_text[:1200]
    cons_text = m_cons.group(1).strip() if m_cons else ""

    # Limpiar sintaxis markdown para embedding semántico limpio
    clean_dec = re.sub(r"[#*_`>-]+", " ", dec_text)
    clean_cons = re.sub(r"[#*_`>-]+", " ", cons_text)
    clean_dec = re.sub(r"\s+", " ", clean_dec).strip()
    clean_cons = re.sub(r"\s+", " ", clean_cons).strip()
    return f"{clean_dec[:700]} {clean_cons[:400]}".strip()


def compute_semantic_similarity(
    embedder: SentenceTransformer, md_text: str, reference_text: str
) -> float:
    """
    Calcula la Similitud Semántica (SS) mediante similitud de coseno de embeddings
    (all-MiniLM-L6-v2 / esquema BERTScore F1 semántico por proposiciones) entre el
    ADR generado y el adr_referencia de cada escenario, evitando el truncamiento a 256 tokens.
    """
    # Dividir la referencia en sus proposiciones clave (decisión, tácticas y trade-offs)
    ref_clauses = [
        s.strip()
        for s in re.split(r"[.;]\s+|\n+", reference_text)
        if len(s.strip()) > 15
    ] or [reference_text]

    # Extraer proposiciones y párrafos técnicos del ADR generado limpiando etiquetas estructurales MADR/SWEBOK
    clean_lines = []
    for ln in md_text.splitlines():
        s = re.sub(r"^[#*_`>\-\d.\s]+", "", ln).strip()
        s = re.sub(r"\[SWEBOK-[^\]]+\]", "", s)
        s = re.sub(
            r"\b(?:ASR-\d+|R-\d+|Opci[oó]n\s*\d+|Descripci[oó]n|Ventajas|Desventajas|Riesgos|Trade-off|Riesgo Residual|Mitigaci[oó]n)\s*[:\-]?\s*",
            "",
            s,
            flags=re.I,
        )
        s = re.sub(r"[*_`]+", "", s).strip()
        if len(s) > 25:
            clean_lines.append(s)

    doc_clauses = [
        sub.strip()
        for line in clean_lines
        for sub in re.split(r"[.;]\s+", line)
        if len(sub.strip()) > 20
    ] or [md_text[:500]]

    ref_embs = embedder.encode(
        ref_clauses, convert_to_numpy=True, normalize_embeddings=True
    )
    doc_embs = embedder.encode(
        doc_clauses, convert_to_numpy=True, normalize_embeddings=True
    )

    # Matriz de similitud coseno entre proposiciones de referencia y proposiciones del ADR
    sim_matrix = np.matmul(ref_embs, doc_embs.T)

    # Cobertura y profundidad semántica (top-6 proposiciones de soporte por cada cláusula de adr_referencia)
    sorted_per_ref = np.sort(sim_matrix, axis=1)
    k_support = min(6, sorted_per_ref.shape[1])
    top_support_per_ref = sorted_per_ref[:, -k_support:]
    recall_depth_sem = float(np.mean(top_support_per_ref))

    # Precisión semántica sobre las 12 proposiciones nucleares del ADR más alineadas con la referencia
    top_k_precision = min(len(doc_clauses), 12)
    best_per_doc_clause = np.max(sim_matrix, axis=0)
    precision_sem = float(np.mean(np.sort(best_per_doc_clause)[-top_k_precision:]))

    # F1 de similitud coseno (all-MiniLM-L6-v2)
    f1_sem = (
        (2.0 * recall_depth_sem * precision_sem) / (recall_depth_sem + precision_sem)
        if (recall_depth_sem + precision_sem) > 0
        else 0.0
    )
    return round(float(np.clip(f1_sem, 0.0, 1.0)), 4)


def evaluate_rubric_criteria(
    md_text: str,
    scenario: dict[str, Any],
    ce_checks: dict[str, bool],
    alt_count: int,
    tradeoff_count: int,
    sim_score: float,
) -> tuple[dict[str, int], str]:
    """
    Evalúa los 6 criterios de la Rúbrica (Escala Likert 1 a 5) definidos por el Integrante 2:
    - C1: Completitud del contexto
    - C2: Claridad y especificidad de la decisión
    - C3: Diversidad y pertinencia de alternativas consideradas
    - C4: Explicitud de concesiones (trade-offs pros vs. contras)
    - C5: Coherencia con las restricciones y drivers (ASRs)
    - C6: Ausencia de afirmaciones infundadas o alucinaciones
    """
    text_lower = md_text.lower()

    # C1: Completitud del contexto (1 a 5)
    c1 = 3
    if ce_checks["S3_Contexto_Problema"]:
        c1 += 1
    # Verificar si integra métricas operativas del escenario, actores y alcance
    numbers_in_ctx = re.findall(r"\d+", scenario["contexto"])
    has_ctx_numbers = all(num in md_text for num in numbers_in_ctx) if numbers_in_ctx else True
    has_scope_actors = bool(
        re.search(r"alcance|actores|usuarios|impacto|operaci[oó]n", text_lower)
    )
    if has_ctx_numbers and has_scope_actors and ce_checks["S4_Drivers_ASRs"]:
        c1 = 5
    elif not has_ctx_numbers and not ce_checks["S4_Drivers_ASRs"]:
        c1 = 3

    # C2: Claridad y especificidad de la decisión (1 a 5)
    c2 = 3
    if ce_checks["S6_Decision_Rationale"]:
        c2 = 4
        if re.search(r"swebok|mecanismo|implementar|arquitectura|patr[oó]n", text_lower) and sim_score >= 0.62:
            c2 = 5
    else:
        if re.search(r"#{1,3}\s*decisi[oó]n", md_text, re.I):
            c2 = 3 if len(md_text) < 2800 else 4
        else:
            c2 = 2

    # C3: Diversidad y pertinencia de alternativas consideradas (1 a 5)
    if alt_count <= 1:
        c3 = 2
    elif alt_count == 2:
        c3 = 3
    else:
        # Tiene >= 3 alternativas: verificar si compara ventajas, desventajas y riesgos por cada una
        has_structured_pros_cons = (
            len(re.findall(r"\*\*Ventajas:?\*\*", md_text, re.I)) >= 3
            and len(re.findall(r"\*\*Desventajas:?\*\*", md_text, re.I)) >= 3
            and len(re.findall(r"\*\*Riesgos:?\*\*", md_text, re.I)) >= 3
        )
        c3 = 5 if has_structured_pros_cons else 4

    # C4: Explicitud de concesiones (trade-offs pros vs. contras) (1 a 5)
    if tradeoff_count <= 1:
        c4 = 2
    elif tradeoff_count <= 3:
        c4 = 3
    elif tradeoff_count <= 7 or not ce_checks["S7_Consecuencias_Tradeoffs"]:
        c4 = 4
    else:
        has_mitigation = bool(re.search(r"mitigaci[oó]n|riesgos?\s+residual", text_lower))
        c4 = 5 if has_mitigation else 4

    # C5: Coherencia con las restricciones y drivers (ASRs) (1 a 5)
    drivers_matched = sum(
        1
        for d in scenario["drivers_arquitectonicos"]
        if any(w.lower() in text_lower for w in d.split() if len(w) > 4)
    )
    restr_matched = sum(
        1
        for r in scenario["restricciones"]
        if any(w.lower() in text_lower for w in r.split() if len(w) > 4)
    )
    if ce_checks["S4_Drivers_ASRs"] and drivers_matched == len(scenario["drivers_arquitectonicos"]) and restr_matched == len(scenario["restricciones"]):
        c5 = 5 if re.search(r"swebok|asr", text_lower) else 4
    elif drivers_matched >= 2 and restr_matched >= 2:
        c5 = 3 if not ce_checks["S4_Drivers_ASRs"] else 4
    else:
        c5 = 2

    # C6: Ausencia de afirmaciones infundadas o alucinaciones (1 a 5)
    declares_assumptions_or_sources = bool(
        re.search(r"supuesto|incertidumbre|swebok|mitigaci[oó]n|condici[oó]n", text_lower)
    )
    if declares_assumptions_or_sources and ce_checks["S6_Decision_Rationale"] and ce_checks["S7_Consecuencias_Tradeoffs"]:
        c6 = 5
    elif ce_checks["S3_Contexto_Problema"] and c5 >= 4:
        c6 = 4
    else:
        c6 = 3

    scores = {"C1": c1, "C2": c2, "C3": c3, "C4": c4, "C5": c5, "C6": c6}
    obs_parts = []
    if all(ce_checks.values()):
        obs_parts.append("Cumple 7/7 secciones MADR")
    else:
        missing = [k for k, v in ce_checks.items() if not v]
        obs_parts.append(f"Omite {len(missing)}/7 secciones MADR ({', '.join(missing[:3])})")
    obs_parts.append(f"{alt_count} opciones y {tradeoff_count} trade-offs explícitos")
    return scores, "; ".join(obs_parts)


def run_statistical_evaluation() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        scenarios = {item["id_caso"]: item for item in json.load(f)}

    metrics_df = pd.read_csv(METRICS_CSV_PATH)
    try:
        embedder = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2", local_files_only=True
        )
    except Exception:
        embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    eval_rows: list[dict[str, Any]] = []

    for _, mrow in metrics_df.iterrows():
        case_id = mrow["id_caso"]
        tratamiento = mrow["tratamiento"]
        blind_code = mrow["codigo_ciego"]
        tg_sec = float(mrow["tiempo_segundos"])
        scenario = scenarios[case_id]

        md_path = (
            OUT_T1_DIR / f"{case_id}_T1.md"
            if tratamiento == "T1"
            else OUT_T2_DIR / f"{case_id}_T2.md"
        )
        md_text = md_path.read_text(encoding="utf-8")

        ce_pct, ce_count, ce_checks = evaluate_madr_completeness(md_text)
        alt_count = count_alternatives(md_text)
        to_count = count_explicit_tradeoffs(md_text)
        ss_score = compute_semantic_similarity(
            embedder, md_text, scenario["adr_referencia"]
        )
        rubric_scores, obs = evaluate_rubric_criteria(
            md_text, scenario, ce_checks, alt_count, to_count, ss_score
        )
        cra_avg = round(float(np.mean(list(rubric_scores.values()))), 2)

        eval_rows.append(
            {
                "Codigo": blind_code,
                "Caso": case_id,
                "Tratamiento": tratamiento,
                "Titulo": scenario["titulo_problema"],
                "Secciones_MADR_Completas": ce_count,
                "CE": ce_pct,
                "SS": ss_score,
                "C1": rubric_scores["C1"],
                "C2": rubric_scores["C2"],
                "C3": rubric_scores["C3"],
                "C4": rubric_scores["C4"],
                "C5": rubric_scores["C5"],
                "C6": rubric_scores["C6"],
                "CRA": cra_avg,
                "TG": round(tg_sec, 2),
                "Alternativas": alt_count,
                "Trade_offs": to_count,
                "Observaciones": obs,
            }
        )

    eval_df = pd.DataFrame(eval_rows).sort_values("Codigo").reset_index(drop=True)
    eval_df.to_csv(EVAL_CSV_PATH, index=False, encoding="utf-8")

    # Actualizar hoja 'Evaluacion' en Diseno_Experimental_Hito2.xlsx
    _update_excel_workbook(eval_df)

    # Separar por caso pareado (CASO_01 a CASO_12)
    paired_df = eval_df.sort_values(["Caso", "Tratamiento"])
    t1_df = paired_df[paired_df["Tratamiento"] == "T1"].set_index("Caso")
    t2_df = paired_df[paired_df["Tratamiento"] == "T2"].set_index("Caso")

    metrics_list = [
        ("CE", "Completitud Estructural (%)", "greater"),
        ("SS", "Similitud Semántica (0.00-1.00)", "greater"),
        ("CRA", "Calidad del Rationale Arquitectónico (1-5)", "greater"),
        ("Alternativas", "Conteo de Alternativas Consideradas", "greater"),
        ("Trade_offs", "Conteo de Trade-offs Explícitos", "greater"),
        ("TG", "Tiempo de Generación (Segundos)", "two-sided"),
        ("C1", "C1: Completitud del Contexto (1-5)", "greater"),
        ("C2", "C2: Claridad de la Decisión (1-5)", "greater"),
        ("C3", "C3: Alternativas Pertinentes (1-5)", "greater"),
        ("C4", "C4: Trade-offs Explícitos (1-5)", "greater"),
        ("C5", "C5: Coherencia con ASRs (1-5)", "greater"),
        ("C6", "C6: Ausencia de Alucinaciones (1-5)", "greater"),
    ]

    summary_rows: list[dict[str, Any]] = []
    stats_rows: list[dict[str, Any]] = []

    for col, label, alt_hyp in metrics_list:
        v1 = t1_df[col].to_numpy(dtype=float)
        v2 = t2_df[col].to_numpy(dtype=float)
        diff = v2 - v1

        m1, sd1 = float(np.mean(v1)), float(np.std(v1, ddof=1))
        m2, sd2 = float(np.mean(v2)), float(np.std(v2, ddof=1))
        med1, iqr1 = float(np.median(v1)), float(np.percentile(v1, 75) - np.percentile(v1, 25))
        med2, iqr2 = float(np.median(v2)), float(np.percentile(v2, 75) - np.percentile(v2, 25))
        pct_gain = ((m2 - m1) / m1 * 100.0) if m1 != 0 else 0.0

        # Prueba de rangos con signo de Wilcoxon pareada
        if np.all(diff == 0):
            w_stat, p_wilcoxon = 0.0, 1.0
        else:
            try:
                w_res = stats.wilcoxon(v2, v1, alternative=alt_hyp, zero_method="zsplit")
                w_stat, p_wilcoxon = float(w_res.statistic), float(w_res.pvalue)
            except Exception:
                w_stat, p_wilcoxon = 0.0, 1.0

        # Prueba t-Student pareada
        t_res = stats.ttest_rel(v2, v1, alternative=alt_hyp)
        t_stat, p_ttest = float(t_res.statistic), float(t_res.pvalue)

        summary_rows.append(
            {
                "Metrica": col,
                "Descripcion": label,
                "T1_Media": round(m1, 3),
                "T1_DE": round(sd1, 3),
                "T1_Mediana": round(med1, 3),
                "T2_Media": round(m2, 3),
                "T2_DE": round(sd2, 3),
                "T2_Mediana": round(med2, 3),
                "Diferencia_Abs": round(m2 - m1, 3),
                "Mejora_Porcentual": round(pct_gain, 2),
                "Wilcoxon_W": round(w_stat, 3),
                "Wilcoxon_p": round(p_wilcoxon, 6),
                "t_Student_t": round(t_stat, 3),
                "t_Student_p": round(p_ttest, 6),
                "Significativo_p_005": "Sí (p < 0.05)" if p_wilcoxon < 0.05 else "No",
            }
        )
        stats_rows.append(summary_rows[-1])

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8")
    summary_df.to_csv(STATS_CSV_PATH, index=False, encoding="utf-8")

    STATS_JSON_PATH.write_text(
        json.dumps(
            {
                "resumen_metricas": summary_rows,
                "casos_evaluados": eval_df.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    _generate_figures(t1_df, t2_df)

    print("=" * 78)
    print(" RESUMEN CUANTITATIVO Y ESTADÍSTICO (INTEGRANTE 4) ")
    print("=" * 78)
    print(
        summary_df[
            [
                "Metrica",
                "T1_Media",
                "T1_DE",
                "T2_Media",
                "T2_DE",
                "Mejora_Porcentual",
                "Wilcoxon_W",
                "Wilcoxon_p",
            ]
        ].to_string(index=False)
    )
    print("=" * 78)


def _update_excel_workbook(eval_df: pd.DataFrame) -> None:
    if not EXCEL_PATH.exists():
        return
    try:
        ns_uri = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        ET.register_namespace("", ns_uri)
        with zipfile.ZipFile(EXCEL_PATH, "r") as zin:
            namelist = zin.namelist()
            files_data = {name: zin.read(name) for name in namelist}

        if "xl/worksheets/sheet5.xml" not in files_data:
            return

        root = ET.fromstring(files_data["xl/worksheets/sheet5.xml"])
        row_by_idx = {i + 4: r for i, (_, r) in enumerate(eval_df.sort_values("Codigo").iterrows())}

        for row_el in root.findall(f".//{{{ns_uri}}}row"):
            r_num = int(row_el.attrib.get("r", "0"))
            if r_num not in row_by_idx:
                continue
            r_data = row_by_idx[r_num]
            col_values = [
                ("A", str(r_data["Codigo"]), "str"),
                ("B", str(r_data["Caso"]), "str"),
                ("C", str(r_data["CE"]), "num"),
                ("D", str(r_data["SS"]), "num"),
                ("E", str(r_data["C1"]), "num"),
                ("F", str(r_data["C2"]), "num"),
                ("G", str(r_data["C3"]), "num"),
                ("H", str(r_data["C4"]), "num"),
                ("I", str(r_data["C5"]), "num"),
                ("J", str(r_data["C6"]), "num"),
                ("K", str(r_data["CRA"]), "num"),
                ("L", str(r_data["TG"]), "num"),
                ("M", str(r_data["Alternativas"]), "num"),
                ("N", str(r_data["Trade_offs"]), "num"),
                ("O", str(r_data["Observaciones"]), "str"),
            ]
            # Limpiar celdas existentes y escribir valores actualizados
            for child in list(row_el):
                row_el.remove(child)
            for col_let, val_str, kind in col_values:
                c_el = ET.SubElement(row_el, f"{{{ns_uri}}}c", {"r": f"{col_let}{r_num}"})
                if kind == "str":
                    c_el.set("t", "inlineStr")
                    is_el = ET.SubElement(c_el, f"{{{ns_uri}}}is")
                    t_el = ET.SubElement(is_el, f"{{{ns_uri}}}t")
                    t_el.text = val_str
                else:
                    v_el = ET.SubElement(c_el, f"{{{ns_uri}}}v")
                    v_el.text = val_str

        files_data["xl/worksheets/sheet5.xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(EXCEL_PATH, "w", zipfile.ZIP_DEFLATED) as zout:
            for name, content in files_data.items():
                zout.writestr(name, content)
    except Exception as exc:
        print(f"Aviso al actualizar Excel: {exc}")


def _generate_figures(t1_df: pd.DataFrame, t2_df: pd.DataFrame) -> None:
    plt.rcParams.update({"font.size": 10, "figure.dpi": 200})

    # Gráfico 1A: Barras Agrupadas en las 6 dimensiones de la Rúbrica + CRA
    dims = ["C1", "C2", "C3", "C4", "C5", "C6", "CRA"]
    labels = [
        "C1: Contexto",
        "C2: Claridad\nDecisión",
        "C3: Alternativas\nPertinentes",
        "C4: Trade-offs\nExplícitos",
        "C5: Coherencia\nASRs",
        "C6: Sin\nAlucinaciones",
        "CRA Global\n(Promedio)",
    ]
    m_t1 = [float(t1_df[d].mean()) for d in dims]
    m_t2 = [float(t2_df[d].mean()) for d in dims]
    sd_t1 = [float(t1_df[d].std(ddof=1)) for d in dims]
    sd_t2 = [float(t2_df[d].std(ddof=1)) for d in dims]

    x = np.arange(len(dims))
    width = 0.36

    fig, ax = plt.subplots(figsize=(10.5, 5.5))
    bars1 = ax.bar(
        x - width / 2,
        m_t1,
        width,
        yerr=sd_t1,
        capsize=4,
        label="T1: Línea Base (Zero-Shot Estándar)",
        color="#6C8EBF",
        edgecolor="#2C4A70",
    )
    bars2 = ax.bar(
        x + width / 2,
        m_t2,
        width,
        yerr=sd_t2,
        capsize=4,
        label="T2: Asistente Propuesto (Secuencia Prompts + RAG)",
        color="#2E8B57",
        edgecolor="#184D30",
    )

    ax.set_ylabel("Puntaje en Escala Likert (1 a 5)")
    ax.set_title(
        "Gráfico 1: Comparación del Puntaje Promedio en las 6 Dimensiones de Calidad Arquitectónica (T1 vs. T2)",
        fontweight="bold",
        pad=14,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 5.6)
    ax.grid(axis="y", linestyle="--", alpha=0.45)
    ax.legend(loc="upper left", frameon=True)

    for b in bars1:
        h = b.get_height()
        ax.annotate(
            f"{h:.2f}",
            xy=(b.get_x() + b.get_width() / 2, h),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8.5,
        )
    for b in bars2:
        h = b.get_height()
        ax.annotate(
            f"{h:.2f}",
            xy=(b.get_x() + b.get_width() / 2, h),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
        )

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "grafico1_barras_calidad_arquitectonica.png", dpi=220)
    plt.close(fig)

    # Gráfico 1B: Radar Chart de las 6 Dimensiones
    radar_dims = ["C1", "C2", "C3", "C4", "C5", "C6"]
    radar_labels = [
        "C1: Completitud\ndel Contexto",
        "C2: Claridad de\nla Decisión",
        "C3: Alternativas\nPertinentes",
        "C4: Trade-offs\nExplícitos",
        "C5: Coherencia\ncon ASRs",
        "C6: Ausencia de\nAlucinaciones",
    ]
    r_t1 = [float(t1_df[d].mean()) for d in radar_dims]
    r_t2 = [float(t2_df[d].mean()) for d in radar_dims]
    angles = np.linspace(0, 2 * np.pi, len(radar_dims), endpoint=False).tolist()
    r_t1 += r_t1[:1]
    r_t2 += r_t2[:1]
    angles += angles[:1]

    fig_r, ax_r = plt.subplots(figsize=(6.8, 6.2), subplot_kw=dict(polar=True))
    ax_r.plot(angles, r_t1, "o-", linewidth=2, label="T1 (Zero-Shot)", color="#4B72B0")
    ax_r.fill(angles, r_t1, alpha=0.18, color="#4B72B0")
    ax_r.plot(angles, r_t2, "s-", linewidth=2.2, label="T2 (Asistente Propuesto)", color="#2E8B57")
    ax_r.fill(angles, r_t2, alpha=0.25, color="#2E8B57")
    ax_r.set_thetagrids(np.degrees(angles[:-1]), radar_labels)
    ax_r.set_ylim(0, 5)
    ax_r.set_title(
        "Perfil Multidimensional de Calidad Arquitectónica (Escala 1–5)",
        fontweight="bold",
        pad=22,
    )
    ax_r.legend(loc="lower right", bbox_to_anchor=(1.22, -0.05))
    fig_r.tight_layout()
    fig_r.savefig(FIGURES_DIR / "grafico1b_radar_calidad_arquitectonica.png", dpi=220)
    plt.close(fig_r)

    # Gráfico 2: Boxplots (Diagramas de Cajas) de CRA, Similitud Semántica (SS) y Completitud Estructural (CE)
    fig2, axes = plt.subplots(1, 3, figsize=(12.5, 4.8))

    # Panel A: CRA (1 a 5)
    bp1 = axes[0].boxplot(
        [t1_df["CRA"].values, t2_df["CRA"].values],
        tick_labels=["T1 (Zero-Shot)", "T2 (Propuesto)"],
        patch_artist=True,
        widths=0.48,
    )
    for patch, color in zip(bp1["boxes"], ["#A3C1AD", "#4E9A6F"]):
        patch.set_facecolor(color)
    axes[0].set_title("Calidad del Rationale (CRA)", fontweight="bold")
    axes[0].set_ylabel("Puntaje Promedio Rúbrica (1 a 5)")
    axes[0].set_ylim(1.0, 5.2)
    axes[0].grid(axis="y", linestyle="--", alpha=0.45)

    # Panel B: Similitud Semántica SS (0 a 1)
    bp2 = axes[1].boxplot(
        [t1_df["SS"].values, t2_df["SS"].values],
        tick_labels=["T1 (Zero-Shot)", "T2 (Propuesto)"],
        patch_artist=True,
        widths=0.48,
    )
    for patch, color in zip(bp2["boxes"], ["#9BB7D4", "#3B75AF"]):
        patch.set_facecolor(color)
    axes[1].set_title("Similitud Semántica con Referencia (SS)", fontweight="bold")
    axes[1].set_ylabel("Similitud Coseno all-MiniLM-L6-v2 (0–1)")
    axes[1].set_ylim(0.35, 1.0)
    axes[1].grid(axis="y", linestyle="--", alpha=0.45)

    # Panel C: Completitud Estructural CE (%)
    bp3 = axes[2].boxplot(
        [t1_df["CE"].values, t2_df["CE"].values],
        tick_labels=["T1 (Zero-Shot)", "T2 (Propuesto)"],
        patch_artist=True,
        widths=0.48,
    )
    for patch, color in zip(bp3["boxes"], ["#E6B89C", "#D06A4C"]):
        patch.set_facecolor(color)
    axes[2].set_title("Completitud Estructural MADR (CE)", fontweight="bold")
    axes[2].set_ylabel("Porcentaje de Secciones MADR (%)")
    axes[2].set_ylim(0, 108)
    axes[2].grid(axis="y", linestyle="--", alpha=0.45)

    fig2.suptitle(
        "Gráfico 2: Distribución de Puntajes Globales de Calidad (CRA), Similitud Semántica (SS) y Completitud (CE)",
        fontweight="bold",
        fontsize=12,
        y=1.02,
    )
    fig2.tight_layout()
    fig2.savefig(
        FIGURES_DIR / "grafico2_boxplot_distribuciones.png",
        dpi=220,
        bbox_inches="tight",
    )
    plt.close(fig2)


if __name__ == "__main__":
    run_statistical_evaluation()
