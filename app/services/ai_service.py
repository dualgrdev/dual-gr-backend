# app/services/ai_service.py
from __future__ import annotations

import os
import base64
from typing import Any, Dict, Optional

from openai import OpenAI


def _get_client() -> OpenAI:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY não configurada no ambiente.")
    return OpenAI(api_key=api_key)


def _doc_label(doc_type: str) -> str:
    dt = (doc_type or "").strip().lower()
    if dt in ("exame", "pedido_exame", "laudo", "resultado_exame"):
        return "EXAME"
    return "RECEITA"


def _build_prompt_text(extracted_text: str, doc_type: str) -> str:
    doc_label = _doc_label(doc_type)

    return f"""
Você é uma enfermeira virtual da Dual GR.

IMPORTANTE:
- Você só pode analisar documentos do tipo {doc_label} (Exames OU Receitas).
- Se o conteúdo NÃO for claramente {doc_label}, responda com JSON indicando recusa.

Regras:
- Não dê diagnóstico definitivo.
- Não analise boletos, contratos, RG/CPF, laudos não médicos, documentos pessoais etc.
- Se houver sinais de urgência/emergência, oriente procurar atendimento imediato.
- Use linguagem PT-BR simples e direta.
- Responda em JSON estrito com os campos definidos.

TEXTO EXTRAÍDO:
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

Se NÃO for {doc_label}, retorne:
{{
  "tipo_documento": "indefinido",
  "resumo": "",
  "pontos_atencao": [],
  "orientacoes": [],
  "quando_procurar_urgencia": [],
  "perguntas_para_medico": [],
  "recusa": true,
  "motivo_recusa": "Explique por que não parece ser exame/receita"
}}
""".strip()


def _build_prompt_image(doc_type: str) -> str:
    doc_label = _doc_label(doc_type)

    return f"""
Você é uma enfermeira virtual da Dual GR.

IMPORTANTE:
- Você só pode analisar IMAGENS que sejam {doc_label} (EXAME ou RECEITA).
- Se a imagem NÃO for claramente um {doc_label}, responda com JSON indicando recusa.

Regras:
- Não dê diagnóstico definitivo.
- Não analise boletos, contratos, RG/CPF, documentos pessoais.
- Se houver sinais de urgência/emergência, oriente procurar atendimento imediato.
- Use linguagem PT-BR simples e direta.
- Responda em JSON estrito com os campos definidos.

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

Se NÃO for {doc_label}, retorne:
{{
  "tipo_documento": "indefinido",
  "resumo": "",
  "pontos_atencao": [],
  "orientacoes": [],
  "quando_procurar_urgencia": [],
  "perguntas_para_medico": [],
  "recusa": true,
  "motivo_recusa": "Explique por que não parece ser exame/receita"
}}
""".strip()


def _parse_json_or_fallback(content: str, doc_type: str) -> Dict[str, Any]:
    content = (content or "").strip()
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
        obj = json.loads(content)
        if isinstance(obj, dict):
            return obj
        return {
            "tipo_documento": doc_type,
            "resumo": "Resposta em formato inesperado.",
            "pontos_atencao": [],
            "orientacoes": [],
            "quando_procurar_urgencia": [],
            "perguntas_para_medico": [],
            "recusa": False,
            "motivo_recusa": None,
            "_raw": obj,
        }
    except Exception:
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


def analyze_exam_or_rx_text(extracted_text: str, doc_type: str, model: Optional[str] = None) -> Dict[str, Any]:
    client = _get_client()
    used_model = (model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()

    prompt = _build_prompt_text(extracted_text, doc_type)

    resp = client.responses.create(
        model=used_model,
        input=prompt,
        temperature=0.2,
    )

    return _parse_json_or_fallback(getattr(resp, "output_text", "") or "", doc_type)


def analyze_exam_or_rx_image_bytes(
    image_bytes: bytes,
    mime_type: str,
    doc_type: str,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analisa imagem (jpg/png/webp) via visão.
    Envia base64 no formato data:<mime>;base64,<...>
    """
    if not image_bytes or len(image_bytes) < 20:
        raise RuntimeError("Imagem vazia ou inválida.")
    mime = (mime_type or "").strip().lower()
    if mime not in ("image/jpeg", "image/jpg", "image/png", "image/webp"):
        raise RuntimeError("Formato de imagem não suportado. Use JPG/PNG/WEBP.")

    client = _get_client()
    used_model = (model or os.getenv("OPENAI_MODEL_VISION") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()

    prompt = _build_prompt_image(doc_type)
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime};base64,{b64}"

    # Estrutura de conteúdo com imagem (image_url.url)
    resp = client.responses.create(
        model=used_model,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": {"url": data_url}},
                ],
            }
        ],
        temperature=0.2,
    )

    return _parse_json_or_fallback(getattr(resp, "output_text", "") or "", doc_type)
