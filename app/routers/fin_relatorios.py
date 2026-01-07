from datetime import date, datetime
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.db.session import SessionLocal
from app.models.finance_lancamento import FinanceLancamento


router = APIRouter(tags=["Financeiro - Relatórios"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_finance_login(request: Request):
    if not request.session.get("finance_user_id"):
        return RedirectResponse(url="/financeiro/login", status_code=303)
    return None


def _parse_date(s: str | None) -> Optional[date]:
    if not s:
        return None
    try:
        y, m, d = s.split("-")
        return date(int(y), int(m), int(d))
    except Exception:
        return None


@router.get("/financeiro/relatorios", response_class=HTMLResponse)
def relatorios_page(request: Request):
    guard = require_finance_login(request)
    if guard:
        return guard
    templates = request.app.state.templates
    return templates.TemplateResponse("financeiro/relatorios.html", {"request": request})


@router.get("/financeiro/relatorios/export.xlsx")
def export_xlsx(request: Request, db: Session = Depends(get_db)):
    guard = require_finance_login(request)
    if guard:
        return guard

    qp = request.query_params
    dt_ini = _parse_date(qp.get("dt_ini"))
    dt_fim = _parse_date(qp.get("dt_fim"))
    tipo = (qp.get("tipo") or "").strip().upper()
    status = (qp.get("status") or "").strip().upper()

    q = db.query(FinanceLancamento).filter(FinanceLancamento.is_active == True)
    if dt_ini:
        q = q.filter(FinanceLancamento.data >= dt_ini)
    if dt_fim:
        q = q.filter(FinanceLancamento.data <= dt_fim)
    if tipo in ("ENTRADA", "SAIDA"):
        q = q.filter(FinanceLancamento.tipo == tipo)
    if status in ("PAGO", "PENDENTE"):
        q = q.filter(FinanceLancamento.status == status)

    lancs = q.order_by(FinanceLancamento.data.desc(), FinanceLancamento.id.desc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Lancamentos"
    ws.append(["Data", "Tipo", "Status", "Valor", "Descricao", "CategoriaID", "FormaPagamentoID", "ContaID"])

    for l in lancs:
        ws.append([
            l.data.isoformat(),
            l.tipo,
            l.status,
            float(l.valor),
            l.descricao,
            l.categoria_id,
            l.forma_pagamento_id,
            l.conta_id,
        ])

    out = BytesIO()
    wb.save(out)
    out.seek(0)

    return StreamingResponse(
        out,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="finance_lancamentos.xlsx"'},
    )


@router.get("/financeiro/relatorios/export.pdf")
def export_pdf(request: Request, db: Session = Depends(get_db)):
    guard = require_finance_login(request)
    if guard:
        return guard

    lancs = (
        db.query(FinanceLancamento)
        .filter(FinanceLancamento.is_active == True)
        .order_by(FinanceLancamento.data.desc(), FinanceLancamento.id.desc())
        .limit(200)
        .all()
    )

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    y = h - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "Relatório Financeiro - Lançamentos")
    y -= 18

    c.setFont("Helvetica", 9)
    c.drawString(40, y, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    y -= 18

    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, y, "Data")
    c.drawString(90, y, "Tipo")
    c.drawString(150, y, "Status")
    c.drawString(210, y, "Valor")
    c.drawString(270, y, "Descrição")
    y -= 12

    c.setFont("Helvetica", 9)
    for l in lancs:
        if y < 60:
            c.showPage()
            y = h - 40
            c.setFont("Helvetica-Bold", 9)
            c.drawString(40, y, "Data")
            c.drawString(90, y, "Tipo")
            c.drawString(150, y, "Status")
            c.drawString(210, y, "Valor")
            c.drawString(270, y, "Descrição")
            y -= 12
            c.setFont("Helvetica", 9)

        desc = (l.descricao or "")
        if len(desc) > 55:
            desc = desc[:55] + "..."

        c.drawString(40, y, l.data.strftime("%d/%m/%Y"))
        c.drawString(90, y, l.tipo)
        c.drawString(150, y, l.status)
        c.drawRightString(250, y, f"{float(l.valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        c.drawString(270, y, desc)
        y -= 12

    c.showPage()
    c.save()
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="finance_lancamentos.pdf"'},
    )
