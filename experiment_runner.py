"""
Script automatizado de ejecución experimental (Hito 2 - Integrante 3).
Lee dataset/escenarios_adr.json (12 escenarios reales), ejecuta Tratamiento 1 (Zero-Shot)
y Tratamiento 2 (Asistente Híbrido con Secuencia de Prompts + RAG) para cada caso (24 corridas),
guarda los archivos Markdown en output/T1/, output/T2/ y output/ciego/ (ADR_001..ADR_024),
y exporta results/metricas_ejecucion.csv.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import time
from pathlib import Path
from typing import Any

from src.adr_assistant import (
    CONTROL_MAX_OUTPUT_TOKENS,
    CONTROL_TEMPERATURE,
    DEFAULT_MODEL_ID,
    GeminiADRClient,
    generate_guided_rag_adr,
    generate_zero_shot,
)
from src.rag_engine import SwebokRAGEngine

PROJECT_ROOT = Path(__file__).resolve().parent
DATASET_PATH = PROJECT_ROOT / "dataset" / "escenarios_adr.json"
OUT_T1_DIR = PROJECT_ROOT / "output" / "T1"
OUT_T2_DIR = PROJECT_ROOT / "output" / "T2"
OUT_BLIND_DIR = PROJECT_ROOT / "output" / "ciego"
RESULTS_DIR = PROJECT_ROOT / "results"
METRICS_CSV_PATH = RESULTS_DIR / "metricas_ejecucion.csv"
TRACES_JSON_PATH = RESULTS_DIR / "trazas_rag_y_etapas.json"

# Clave de tratamientos definida por el Integrante 2 en Diseno_Experimental_Hito2.xlsx
BLIND_CODE_MAP: dict[tuple[str, str], str] = {
    ("CASO_01", "T2"): "ADR_001",
    ("CASO_01", "T1"): "ADR_002",
    ("CASO_02", "T1"): "ADR_003",
    ("CASO_02", "T2"): "ADR_004",
    ("CASO_03", "T2"): "ADR_005",
    ("CASO_03", "T1"): "ADR_006",
    ("CASO_04", "T1"): "ADR_007",
    ("CASO_04", "T2"): "ADR_008",
    ("CASO_05", "T2"): "ADR_009",
    ("CASO_05", "T1"): "ADR_010",
    ("CASO_06", "T1"): "ADR_011",
    ("CASO_06", "T2"): "ADR_012",
    ("CASO_07", "T2"): "ADR_013",
    ("CASO_07", "T1"): "ADR_014",
    ("CASO_08", "T1"): "ADR_015",
    ("CASO_08", "T2"): "ADR_016",
    ("CASO_09", "T2"): "ADR_017",
    ("CASO_09", "T1"): "ADR_018",
    ("CASO_10", "T1"): "ADR_019",
    ("CASO_10", "T2"): "ADR_020",
    ("CASO_11", "T2"): "ADR_021",
    ("CASO_11", "T1"): "ADR_022",
    ("CASO_12", "T1"): "ADR_023",
    ("CASO_12", "T2"): "ADR_024",
}


def run_experiment(pause_between_calls_sec: float = 1.5) -> None:
    OUT_T1_DIR.mkdir(parents=True, exist_ok=True)
    OUT_T2_DIR.mkdir(parents=True, exist_ok=True)
    OUT_BLIND_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        scenarios: list[dict[str, Any]] = json.load(f)

    print("=" * 78)
    print(" EJECUCIÓN EXPERIMENTAL HITO 2 — ASISTENTE ADR ASISTIDO POR IA ")
    print("=" * 78)
    print(f"Modelo controlado     : {DEFAULT_MODEL_ID}")
    print(f"Temperatura controlada: {CONTROL_TEMPERATURE}")
    print(f"Max Output Tokens     : {CONTROL_MAX_OUTPUT_TOKENS}")
    print(f"Escenarios cargados   : {len(scenarios)} (24 corridas pareadas T1 y T2)")
    print("-" * 78)

    rag_engine = SwebokRAGEngine()
    print(
        f"[RAG] Colección ChromaDB '{rag_engine.collection.name}' lista con "
        f"{rag_engine.collection.count()} fragmentos del SWEBOK v4.0 Cap. 02."
    )

    client = GeminiADRClient(
        model_id=DEFAULT_MODEL_ID,
        temperature=CONTROL_TEMPERATURE,
        max_output_tokens=CONTROL_MAX_OUTPUT_TOKENS,
    )

    # Cargar trazas y métricas previas si existen para permitir reanudación limpia
    traces: dict[str, Any] = {}
    if TRACES_JSON_PATH.exists():
        try:
            traces = json.loads(TRACES_JSON_PATH.read_text(encoding="utf-8"))
        except Exception:
            traces = {}

    existing_rows: dict[tuple[str, str], dict[str, Any]] = {}
    if METRICS_CSV_PATH.exists():
        with open(METRICS_CSV_PATH, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("estado") == "OK":
                    existing_rows[(row["id_caso"], row["tratamiento"])] = row

    all_rows: list[dict[str, Any]] = []
    run_order = 0

    for scenario in scenarios:
        case_id = scenario["id_caso"]
        title = scenario["titulo_problema"]

        for tratamiento in ("T1", "T2"):
            run_order += 1
            blind_code = BLIND_CODE_MAP[(case_id, tratamiento)]
            out_file = (
                OUT_T1_DIR / f"{case_id}_T1.md"
                if tratamiento == "T1"
                else OUT_T2_DIR / f"{case_id}_T2.md"
            )
            blind_file = OUT_BLIND_DIR / f"{blind_code}.md"

            if (
                (case_id, tratamiento) in existing_rows
                and out_file.exists()
                and out_file.stat().st_size > 200
            ):
                prev = existing_rows[(case_id, tratamiento)]
                prev["orden_ejecucion"] = run_order
                all_rows.append(prev)
                if not blind_file.exists():
                    blind_file.write_text(out_file.read_text(encoding="utf-8"), encoding="utf-8")
                print(
                    f"[{run_order:02d}/24] {case_id} | {tratamiento} ({blind_code}) -> "
                    f"Ya completado previamente (TG={prev['tiempo_segundos']}s)"
                )
                continue

            print(
                f"[{run_order:02d}/24] Ejecutando {case_id} ({title[:42]}...) | "
                f"Tratamiento: {tratamiento} -> {blind_code} ...",
                flush=True,
            )
            timestamp_iso = dt.datetime.now().isoformat(timespec="seconds")

            try:
                if tratamiento == "T1":
                    res = generate_zero_shot(scenario, client=client)
                else:
                    res = generate_guided_rag_adr(
                        scenario, rag_engine=rag_engine, client=client, top_k_rag=3
                    )

                md_text = res["adr_markdown"]
                out_file.write_text(md_text, encoding="utf-8")
                blind_file.write_text(md_text, encoding="utf-8")

                frag_ids = ";".join(
                    f["id_fragmento"] for f in res.get("fragmentos_rag", [])
                )
                row_data = {
                    "orden_ejecucion": run_order,
                    "codigo_ciego": blind_code,
                    "id_caso": case_id,
                    "titulo_problema": title,
                    "tratamiento": tratamiento,
                    "modelo": res["modelo"],
                    "temperatura": res["temperatura"],
                    "max_tokens": CONTROL_MAX_OUTPUT_TOKENS,
                    "fecha_hora_iso": timestamp_iso,
                    "tiempo_segundos": res["tiempo_segundos"],
                    "longitud_caracteres": len(md_text),
                    "fragmentos_rag_ids": frag_ids,
                    "estado": "OK",
                    "error": "",
                }
                all_rows.append(row_data)

                traces[f"{case_id}_{tratamiento}"] = {
                    "codigo_ciego": blind_code,
                    "id_caso": case_id,
                    "tratamiento": tratamiento,
                    "tiempo_segundos": res["tiempo_segundos"],
                    "fragmentos_rag": res.get("fragmentos_rag", []),
                    "etapas_intermedias": res.get("etapas_intermedias", {}),
                }
                TRACES_JSON_PATH.write_text(
                    json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                _save_metrics_csv(all_rows)

                print(
                    f"         OK en {res['tiempo_segundos']:.2f}s | "
                    f"Chars: {len(md_text)} | RAG: [{frag_ids or 'Ninguno'}]",
                    flush=True,
                )
                time.sleep(pause_between_calls_sec)

            except Exception as exc:
                print(f"         ERROR en {case_id} ({tratamiento}): {exc}", flush=True)
                row_data = {
                    "orden_ejecucion": run_order,
                    "codigo_ciego": blind_code,
                    "id_caso": case_id,
                    "titulo_problema": title,
                    "tratamiento": tratamiento,
                    "modelo": DEFAULT_MODEL_ID,
                    "temperatura": CONTROL_TEMPERATURE,
                    "max_tokens": CONTROL_MAX_OUTPUT_TOKENS,
                    "fecha_hora_iso": timestamp_iso,
                    "tiempo_segundos": 0.0,
                    "longitud_caracteres": 0,
                    "fragmentos_rag_ids": "",
                    "estado": "ERROR",
                    "error": str(exc),
                }
                all_rows.append(row_data)
                _save_metrics_csv(all_rows)

    print("=" * 78)
    ok_count = sum(1 for r in all_rows if r["estado"] == "OK")
    print(f" EJECUCIÓN FINALIZADA: {ok_count}/24 corridas exitosas.")
    print(f" - Archivos T1   : {OUT_T1_DIR}")
    print(f" - Archivos T2   : {OUT_T2_DIR}")
    print(f" - Archivos ciego: {OUT_BLIND_DIR}")
    print(f" - Métricas CSV  : {METRICS_CSV_PATH}")
    print("=" * 78)


def _save_metrics_csv(rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "orden_ejecucion",
        "codigo_ciego",
        "id_caso",
        "titulo_problema",
        "tratamiento",
        "modelo",
        "temperatura",
        "max_tokens",
        "fecha_hora_iso",
        "tiempo_segundos",
        "longitud_caracteres",
        "fragmentos_rag_ids",
        "estado",
        "error",
    ]
    with open(METRICS_CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    run_experiment()
