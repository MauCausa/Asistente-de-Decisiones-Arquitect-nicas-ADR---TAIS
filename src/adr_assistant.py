"""
Implementación del Asistente de Decisiones Arquitectónicas (ADR) asistido por IA.
Incluye:
- Tratamiento 1 (T1): Generación Zero-Shot estándar (generate_zero_shot).
- Tratamiento 2 (T2): Pipeline Híbrido de 3 Etapas de Prompts + RAG (generate_guided_rag_adr).
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import dotenv
import requests

from src.rag_engine import SwebokRAGEngine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
dotenv.load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_MODEL_ID = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
FALLBACK_MODELS = [
    "gemini-3-flash-preview",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
]
CONTROL_TEMPERATURE = 0.2
CONTROL_MAX_OUTPUT_TOKENS = 4096

# ==============================================================================
# BLOQUES DE SYSTEM PROMPTS CONGELADOS (PROTOCOLO EXPERIMENTAL HITO 2)
# ==============================================================================

SYSTEM_PROMPT_T1_ZERO_SHOT = (
    "Eres un asistente de software. Redacta un Registro de Decisión Arquitectónica (ADR) "
    "en español y en formato Markdown para responder al problema descrito por el usuario."
)

SYSTEM_PROMPT_T2_STAGE1_ASR = (
    "Eres un Arquitecto de Software Senior especialista en el SWEBOK v4.0 (Capítulo 02: "
    "Software Architecture). Tu objetivo en esta Etapa 1 es analizar rigurosamente el "
    "escenario arquitectónico, extraer y priorizar los Requisitos Arquitectónicamente "
    "Significativos (ASRs), vincular las restricciones técnicas y organizacionales con "
    "las tácticas y patrones del SWEBOK v4.0 recuperados mediante RAG, e identificar "
    "las tensiones entre atributos de calidad."
)

SYSTEM_PROMPT_T2_STAGE2_DEVILS_ADVOCATE = (
    "Eres un Evaluador Crítico de Arquitectura ('Abogado del Diablo') fundamentado en el "
    "SWEBOK v4.0. Tu misión en esta Etapa 2 es explorar el espacio de diseño proponiendo "
    "al menos TRES (3) alternativas arquitectónicas técnicamente viables y contrastantes "
    "para el escenario. Para cada alternativa debes detallar: (a) Descripción técnica, "
    "(b) Ventajas frente a los ASRs, (c) Desventajas y costos ocultos, y (d) Riesgos "
    "técnicos y deuda arquitectónica potencial. Finalmente, compara las concesiones "
    "(trade-offs) explícitas entre las opciones y selecciona la alternativa óptima que "
    "respete estrictamente todas las restricciones del equipo e infraestructura, sin "
    "inventar capacidades no sustentadas."
)

SYSTEM_PROMPT_T2_STAGE3_MADR_SYNTHESIS = (
    "Eres un Documentador Experto en Registros de Decisiones Arquitectónicas bajo el "
    "estándar MADR (Markdown Architectural Decision Records) y el SWEBOK v4.0. Tu tarea "
    "en esta Etapa 3 es consolidar el análisis de ASRs (Etapa 1) y la evaluación crítica "
    "de alternativas y trade-offs (Etapa 2) en un documento ADR formal, exhaustivo, "
    "preciso y libre de alucinaciones. Debes incluir OBLIGATORIAMENTE y con exactitud "
    "las 7 secciones de la plantilla MADR:\n"
    "1. # [ID] - [Título de la Decisión]\n"
    "2. ## Estado\n"
    "3. ## Contexto y Problema\n"
    "4. ## Drivers de Decisión (ASRs)\n"
    "5. ## Opciones Consideradas (con subsecciones ### Opción 1, ### Opción 2, ### Opción 3 "
    "detallando Descripción, Ventajas, Desventajas y Riesgos)\n"
    "6. ## Decisión y Justificación (Rationale) (trazando cada ASR, restricción y guía SWEBOK v4.0)\n"
    "7. ## Consecuencias (con subsecciones ### Positivas, ### Negativas y ### Trade-offs y Riesgos Residuales)"
)


class GeminiADRClient:
    """Cliente controlado para la API de Google AI Studio (Gemini) con parámetros experimentales fijos."""

    def __init__(
        self,
        api_key: str | None = None,
        model_id: str = DEFAULT_MODEL_ID,
        temperature: float = CONTROL_TEMPERATURE,
        max_output_tokens: int = CONTROL_MAX_OUTPUT_TOKENS,
    ) -> None:
        self.api_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or dotenv.dotenv_values(PROJECT_ROOT / ".env").get("GEMINI_API_KEY")
        )
        if not self.api_key:
            raise ValueError(
                "No se encontró GEMINI_API_KEY en el entorno ni en el archivo .env."
            )
        self.model_id = model_id.replace("models/", "")
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.base_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_id}:generateContent"
        )

    def generate(
        self,
        user_prompt: str,
        system_prompt: str,
        max_retries: int = 3,
    ) -> str:
        """Invoca generateContent con control de temperatura 0.2 y rotación dentro de la familia Gemini Flash ante límites de cuota gratuita (HTTP 429)."""
        models_to_try = [self.model_id] + [
            m for m in FALLBACK_MODELS if m != self.model_id
        ]
        last_error: Exception | None = None

        for candidate_model in models_to_try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{candidate_model}:generateContent?key={self.api_key.strip()}"
            )
            use_thinking_cfg = "lite" not in candidate_model
            for attempt in range(1, max_retries + 1):
                gen_cfg: dict[str, Any] = {
                    "temperature": self.temperature,
                    "maxOutputTokens": self.max_output_tokens,
                }
                if use_thinking_cfg:
                    gen_cfg["thinkingConfig"] = {"thinkingBudget": 0}

                payload = {
                    "system_instruction": {"parts": [{"text": system_prompt}]},
                    "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                    "generationConfig": gen_cfg,
                }
                try:
                    response = requests.post(url, json=payload, timeout=75)
                    if response.status_code == 200:
                        data = response.json()
                        candidates = data.get("candidates", [])
                        if not candidates:
                            raise RuntimeError(f"Respuesta sin candidates: {data}")
                        parts = candidates[0].get("content", {}).get("parts", [])
                        text = "".join(part.get("text", "") for part in parts).strip()
                        return text
                    if response.status_code == 400 and use_thinking_cfg:
                        use_thinking_cfg = False
                        continue
                    if response.status_code == 429:
                        last_error = RuntimeError(
                            f"HTTP 429 ({candidate_model}): {response.text[:240]}"
                        )
                        # Cambiar al siguiente modelo Flash disponible en la familia Gemini
                        break
                    if response.status_code in (500, 502, 503, 504):
                        time.sleep(3 * attempt)
                        continue
                    raise RuntimeError(
                        f"Error API Gemini HTTP {response.status_code}: {response.text[:300]}"
                    )
                except requests.RequestException as exc:
                    last_error = exc
                    time.sleep(2 * attempt)

        raise RuntimeError(f"Fallo tras agotar reintentos: {last_error}")


def generate_zero_shot(
    scenario: dict[str, Any],
    client: GeminiADRClient | None = None,
) -> dict[str, Any]:
    """
    Tratamiento 1 (T1 - Línea Base Zero-Shot Estándar):
    Envía el problema arquitectónico directamente al modelo pidiendo un ADR
    sin estructura guiada MADR ni recuperación de contexto RAG.
    """
    llm = client or GeminiADRClient()
    drivers_str = ", ".join(scenario.get("drivers_arquitectonicos", []))
    restricciones_str = ", ".join(scenario.get("restricciones", []))

    user_prompt = (
        f"Caso: {scenario['id_caso']} - {scenario['titulo_problema']}\n"
        f"Contexto del problema: {scenario['contexto']}\n"
        f"Atributos y requisitos: {drivers_str}\n"
        f"Restricciones: {restricciones_str}\n\n"
        "Genera un documento ADR en español para este problema arquitectónico."
    )

    t0 = time.perf_counter()
    markdown_text = llm.generate(
        user_prompt=user_prompt,
        system_prompt=SYSTEM_PROMPT_T1_ZERO_SHOT,
    )
    elapsed = round(time.perf_counter() - t0, 4)

    return {
        "id_caso": scenario["id_caso"],
        "tratamiento": "T1",
        "modelo": llm.model_id,
        "temperatura": llm.temperature,
        "tiempo_segundos": elapsed,
        "adr_markdown": markdown_text,
        "fragmentos_rag": [],
        "etapas_intermedias": {},
    }


def generate_guided_rag_adr(
    scenario: dict[str, Any],
    rag_engine: SwebokRAGEngine,
    client: GeminiADRClient | None = None,
    top_k_rag: int = 3,
) -> dict[str, Any]:
    """
    Tratamiento 2 (T2 - Asistente ADR Híbrido con Secuencia de Prompts + RAG):
    - Etapa 1: Análisis de ASRs y Recuperación RAG desde ChromaDB (SWEBOK v4.0 Cap. 02).
    - Etapa 2: Exploración de Alternativas (mín. 3) y Abogado del Diablo (riesgos y trade-offs).
    - Etapa 3: Síntesis y Formateo bajo plantilla formal MADR (7 secciones obligatorias).
    """
    llm = client or GeminiADRClient()
    t0 = time.perf_counter()

    # 1. Recuperación Vectorial en ChromaDB (SWEBOK v4.0 Cap. 02)
    query_text = rag_engine.build_Scenario_query(scenario)
    recovered_fragments = rag_engine.retrieve_context(query_text, top_k=top_k_rag)
    rag_context_block = rag_engine.format_fragments_for_prompt(recovered_fragments)

    drivers_bullets = "\n".join(
        f"- {d}" for d in scenario.get("drivers_arquitectonicos", [])
    )
    restricciones_bullets = "\n".join(
        f"- {r}" for r in scenario.get("restricciones", [])
    )

    # 2. Etapa 1: Análisis de ASRs y Tácticas del SWEBOK v4.0
    stage1_prompt = (
        f"### ESCENARIO ARQUITECTÓNICO\n"
        f"- ID: {scenario['id_caso']}\n"
        f"- Título: {scenario['titulo_problema']}\n"
        f"- Contexto: {scenario['contexto']}\n"
        f"- Drivers de Decisión (ASRs):\n{drivers_bullets}\n"
        f"- Restricciones:\n{restricciones_bullets}\n\n"
        f"### CONOCIMIENTO RECUPERADO DEL SWEBOK v4.0 (CAPÍTULO 02) Y MADR\n"
        f"{rag_context_block}\n\n"
        "### TAREA DE LA ETAPA 1\n"
        "1. Analiza cada Driver Arquitectónico (ASR) y su impacto técnico en el sistema.\n"
        "2. Identifica qué restricciones operativas, de presupuesto o de equipo limitan el diseño.\n"
        "3. Extrae las tácticas, estilos y patrones aplicables de los fragmentos SWEBOK v4.0 recuperados "
        "(citando sus códigos como [SWEBOK-02-XX]).\n"
        "Sé conciso, estructurado y riguroso."
    )
    stage1_output = llm.generate(
        user_prompt=stage1_prompt,
        system_prompt=SYSTEM_PROMPT_T2_STAGE1_ASR,
    )

    # 3. Etapa 2: Exploración de Alternativas y Abogado del Diablo
    stage2_prompt = (
        f"### ESCENARIO ARQUITECTÓNICO\n"
        f"- ID: {scenario['id_caso']} - {scenario['titulo_problema']}\n"
        f"- Contexto: {scenario['contexto']}\n"
        f"- Drivers (ASRs):\n{drivers_bullets}\n"
        f"- Restricciones:\n{restricciones_bullets}\n\n"
        f"### RESULTADO DE LA ETAPA 1 (ANÁLISIS DE ASRs Y GUÍAS SWEBOK v4.0)\n"
        f"{stage1_output}\n\n"
        "### TAREA DE LA ETAPA 2 (EXPLORACIÓN DE ALTERNATIVAS Y ABOGADO DEL DIABLO)\n"
        "Formula al menos TRES (3) opciones arquitectónicas distintas y realistas (Opción 1, Opción 2, Opción 3).\n"
        "Actúa como 'Abogado del Diablo' evaluando críticamente cada opción con:\n"
        "- Descripción técnica concreta.\n"
        "- Ventajas respecto a los ASRs.\n"
        "- Desventajas y costos operativos/cognitivos.\n"
        "- Riesgos técnicos y deuda técnica potencial si se adopta.\n"
        "Luego, explicita las concesiones (trade-offs) entre las 3 opciones y determina cuál es la "
        "decisión arquitectónica óptima que cumple todos los drivers sin violar ninguna restricción."
    )
    stage2_output = llm.generate(
        user_prompt=stage2_prompt,
        system_prompt=SYSTEM_PROMPT_T2_STAGE2_DEVILS_ADVOCATE,
    )

    # 4. Etapa 3: Síntesis y Formateo Estricto bajo Plantilla MADR (7 secciones)
    stage3_prompt = (
        f"### DATOS DEL CASO\n"
        f"- ID: {scenario['id_caso']}\n"
        f"- Título del Problema: {scenario['titulo_problema']}\n"
        f"- Contexto Original: {scenario['contexto']}\n"
        f"- Drivers (ASRs):\n{drivers_bullets}\n"
        f"- Restricciones:\n{restricciones_bullets}\n\n"
        f"### ANÁLISIS DE ASRs Y SWEBOK v4.0 (ETAPA 1)\n{stage1_output}\n\n"
        f"### EVALUACIÓN CRÍTICA DE ALTERNATIVAS Y TRADE-OFFS (ETAPA 2)\n{stage2_output}\n\n"
        "### TAREA DE LA ETAPA 3 (SÍNTESIS FORMAL MADR)\n"
        "Genera únicamente el documento ADR final en Markdown siguiendo EXACTAMENTE esta estructura "
        "de 7 secciones obligatorias (sin bloques ```markdown envolventes):\n\n"
        f"# {scenario['id_caso']} - {scenario['titulo_problema']}\n\n"
        "## Estado\n"
        "Aceptado (Propuesto y validado mediante asistencia híbrida SWEBOK v4.0 + evaluación de trade-offs)\n\n"
        "## Contexto y Problema\n"
        "(Describe con precisión el sistema, volumen operativo, problema arquitectónico actual, actores afectados, "
        "alcance y restricciones técnicas/organizacionales del escenario).\n\n"
        "## Drivers de Decisión (ASRs)\n"
        "(Lista y explica cada uno de los drivers arquitectónicos y restricciones clave del caso).\n\n"
        "## Opciones Consideradas\n"
        "### Opción 1: [Nombre de la Opción 1]\n"
        "- **Descripción:** ...\n"
        "- **Ventajas:** ...\n"
        "- **Desventajas:** ...\n"
        "- **Riesgos:** ...\n\n"
        "### Opción 2: [Nombre de la Opción 2]\n"
        "- **Descripción:** ...\n"
        "- **Ventajas:** ...\n"
        "- **Desventajas:** ...\n"
        "- **Riesgos:** ...\n\n"
        "### Opción 3: [Nombre de la Opción 3]\n"
        "- **Descripción:** ...\n"
        "- **Ventajas:** ...\n"
        "- **Desventajas:** ...\n"
        "- **Riesgos:** ...\n\n"
        "## Decisión y Justificación (Rationale)\n"
        "(Enuncia de forma inequívoca y específica la opción seleccionada, detallando sus componentes, "
        "mecanismos técnicos y tácticas del SWEBOK v4.0 Cap. 02 aplicadas. Justifica paso a paso por qué "
        "supera a las demás opciones frente a cada ASR y cómo respeta todas las restricciones del equipo e "
        "infraestructura. Declara explícitamente los supuestos asumidos para evitar afirmaciones infundadas).\n\n"
        "## Consecuencias\n"
        "### Positivas\n"
        "- ...\n\n"
        "### Negativas\n"
        "- ...\n\n"
        "### Trade-offs y Riesgos Residuales\n"
        "- (Detalla las concesiones aceptadas pros vs. contras, los riesgos residuales y sus acciones concretas de mitigación)."
    )
    final_markdown = llm.generate(
        user_prompt=stage3_prompt,
        system_prompt=SYSTEM_PROMPT_T2_STAGE3_MADR_SYNTHESIS,
    )

    # Limpiar posible bloque de código envolvente si el LLM lo agregó
    if final_markdown.startswith("```markdown"):
        final_markdown = final_markdown[len("```markdown") :].strip()
    elif final_markdown.startswith("```"):
        final_markdown = final_markdown[3:].strip()
    if final_markdown.endswith("```"):
        final_markdown = final_markdown[:-3].strip()

    elapsed = round(time.perf_counter() - t0, 4)

    return {
        "id_caso": scenario["id_caso"],
        "tratamiento": "T2",
        "modelo": llm.model_id,
        "temperatura": llm.temperature,
        "tiempo_segundos": elapsed,
        "adr_markdown": final_markdown,
        "fragmentos_rag": recovered_fragments,
        "etapas_intermedias": {
            "etapa_1_asr_rag": stage1_output,
            "etapa_2_abogado_diablo": stage2_output,
        },
    }
