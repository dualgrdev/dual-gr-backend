# app/services/ai_service.py
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from openai import OpenAI


def _get_client() -> OpenAI:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY não configurada no ambiente.")
    return OpenAI(api_key=api_key)


def _build_prompt(extracted_text: str, doc_type: str) -> str:
    # doc_type: "pedido_exame" | "receita"
    doc_label = "PEDIDO DE EXAME" if doc_type == "pedido_exame" else "RECEITA"

    return f"""
Você é uma enfermeira virtual da Dual GR.
IMPORTANTE: Você só pode analisar documentos do tipo {doc_label}.
Se o conteúdo não for claramente {doc_label}, responda com JSON indicando recusa.

Regras:
- Não dê diagnóstico definitivo.
- Não faça interpretações de outros documentos (boletos, contratos, RG/CPF, laudos diversos etc.).
- Se houver sinais de urgência/emergência, oriente procurar atendimento imediato.
- Use linguagem PT-BR simples e direta.
- Responda em JSON estrito com os campos definidos.

TEXTO EXTRAÍDO DO PDF:
\"\"\"{extracted_text[:25000]}\"\"\"

Retorne JSON com este schema:
{{
  "tipo_documento": "{doc_type}",
  "resumo": "string",
  "pontos_atencao": ["string", ...],
  "orientacoes": ["string", ...],
  "quando_procurar_urgencia": ["string", ...],
  "perguntas_para_medico": ["string", ...],
  "recusa": false,
  "motivo_recusa": null
}}
Se você identificar que NÃO é {doc_label}, retorne:
{{
  "tipo_documento": "indefinido",
  "resumo": "",
  "pontos_atencao": [],
  "orientacoes": [],
  "quando_procurar_urgencia": [],
  "perguntas_para_medico": [],
  "recusa": true,
  "motivo_recusa": "Explique por que não parece ser pedido de exame/receita"
}}
""".strip()


def analyze_exam_or_rx_text(extracted_text: str, doc_type: str, model: Optional[str] = None) -> Dict[str, Any]:
    client = _get_client()
    used_model = (model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()

    prompt = _build_prompt(extracted_text, doc_type)

    resp = client.responses.create(
        model=used_model,
        input=prompt,
        temperature=0.2,
    )

    content = (resp.output_text or "").strip()
    if not content:
        return {
            "tipo_documento": doc_type,
            "resumo": "Não foi possível gerar análise (resposta vazia).",
            "pontos_atencao": [],
            "orientacoes": [],
            "quando_procurar_urgencia": [],
            "perguntas_para_medico": [],
            "recusa": False,
            "motivo_recusa": None,
        }

    import json
    try:
        return json.loads(content)
    except Exception:
        # fallback seguro
        return {
            "tipo_documento": doc_type,
            "resumo": content[:2000],
            "pontos_atencao": [],
            "orientacoes": [],
            "quando_procurar_urgencia": [],
            "perguntas_para_medico": [],
            "recusa": False,
            "motivo_recusa": None,
            "_raw": content,
        }
