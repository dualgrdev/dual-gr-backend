from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import SessionLocal
from app.models.finance_lancamento import FinanceLancamento
from app.models.finance_categoria import FinanceCategoria
from app.models.finance_forma_pagamento import FinanceFormaPagamento
from app.models.finance_conta import FinanceConta


router = APIRouter(tags=["Financeiro - Caixa"])


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


@router.get("/financeiro", response_class=HTMLResponse)
def financeiro_index(request: Request):
    guard = require_finance_login(request)
    if guard:
        return guard
    return RedirectResponse(url="/financeiro/dashboard", status_code=303)


@router.get("/financeiro/dashboard", response_class=HTMLResponse)
def financeiro_dashboard(request: Request, db: Session = Depends(get_db)):
    guard = require_finance_login(request)
    if guard:
        return guard

    today = date.today()
    start_month = date(today.year, today.month, 1)

    receita_mes = (
        db.query(func.coalesce(func.sum(FinanceLancamento.valor), 0))
        .filter(
            FinanceLancamento.is_active == True,
            FinanceLancamento.tipo == "ENTRADA",
            FinanceLancamento.status == "PAGO",
            FinanceLancamento.data >= start_month,
        )
        .scalar()
        or 0
    )

    despesa_mes = (
        db.query(func.coalesce(func.sum(FinanceLancamento.valor), 0))
        .filter(
            FinanceLancamento.is_active == True,
            FinanceLancamento.tipo == "SAIDA",
            FinanceLancamento.status == "PAGO",
            FinanceLancamento.data >= start_month,
        )
        .scalar()
        or 0
    )

    pendentes = (
        db.query(func.count(FinanceLancamento.id))
        .filter(FinanceLancamento.is_active == True, FinanceLancamento.status == "PENDENTE")
        .scalar()
        or 0
    )

    saldo_mes = float(receita_mes) - float(despesa_mes)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "financeiro/dashboard.html",
        {
            "request": request,
            "receita_mes": float(receita_mes),
            "despesa_mes": float(despesa_mes),
            "pendentes": int(pendentes),
            "saldo_mes": float(saldo_mes),
        },
    )


@router.get("/financeiro/lancamentos", response_class=HTMLResponse)
def lancamentos_list(request: Request, db: Session = Depends(get_db)):
    guard = require_finance_login(request)
    if guard:
        return guard

    qp = request.query_params
    dt_ini = _parse_date(qp.get("dt_ini"))
    dt_fim = _parse_date(qp.get("dt_fim"))
    tipo = (qp.get("tipo") or "").strip().upper()      # ENTRADA/SAIDA/""
    status = (qp.get("status") or "").strip().upper()  # PAGO/PENDENTE/""
    cat_id = qp.get("cat_id")
    forma_id = qp.get("forma_id")
    conta_id = qp.get("conta_id")

    q = db.query(FinanceLancamento).filter(FinanceLancamento.is_active == True)

    if dt_ini:
        q = q.filter(FinanceLancamento.data >= dt_ini)
    if dt_fim:
        q = q.filter(FinanceLancamento.data <= dt_fim)
    if tipo in ("ENTRADA", "SAIDA"):
        q = q.filter(FinanceLancamento.tipo == tipo)
    if status in ("PAGO", "PENDENTE"):
        q = q.filter(FinanceLancamento.status == status)
    if cat_id and cat_id.isdigit():
        q = q.filter(FinanceLancamento.categoria_id == int(cat_id))
    if forma_id and forma_id.isdigit():
        q = q.filter(FinanceLancamento.forma_pagamento_id == int(forma_id))
    if conta_id and conta_id.isdigit():
        q = q.filter(FinanceLancamento.conta_id == int(conta_id))

    lancs = q.order_by(FinanceLancamento.data.desc(), FinanceLancamento.id.desc()).limit(500).all()

    # Totais na tela (com filtros)
    total_entrada = (
        db.query(func.coalesce(func.sum(FinanceLancamento.valor), 0))
        .filter(FinanceLancamento.is_active == True, FinanceLancamento.tipo == "ENTRADA")
        .filter(*(q._where_criteria))
        .scalar()
        or 0
    )
    total_saida = (
        db.query(func.coalesce(func.sum(FinanceLancamento.valor), 0))
        .filter(FinanceLancamento.is_active == True, FinanceLancamento.tipo == "SAIDA")
        .filter(*(q._where_criteria))
        .scalar()
        or 0
    )

    categorias = db.query(FinanceCategoria).filter(FinanceCategoria.is_active == True).order_by(FinanceCategoria.nome.asc()).all()
    formas = db.query(FinanceFormaPagamento).filter(FinanceFormaPagamento.is_active == True).order_by(FinanceFormaPagamento.nome.asc()).all()
    contas = db.query(FinanceConta).filter(FinanceConta.is_active == True).order_by(FinanceConta.nome.asc()).all()

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "financeiro/lancamentos.html",
        {
            "request": request,
            "lancs": lancs,
            "categorias": categorias,
            "formas": formas,
            "contas": contas,
            "total_entrada": float(total_entrada),
            "total_saida": float(total_saida),
        },
    )


@router.post("/financeiro/lancamentos/create")
def lancamentos_create(
    request: Request,
    tipo: str = Form(...),
    status: str = Form("PAGO"),
    data: str = Form(...),
    valor: str = Form(...),
    descricao: str = Form(...),
    categoria_id: str = Form(None),
    forma_pagamento_id: str = Form(None),
    conta_id: str = Form(None),
    db: Session = Depends(get_db),
):
    guard = require_finance_login(request)
    if guard:
        return guard

    tipo = (tipo or "").strip().upper()
    status = (status or "").strip().upper()
    dt = _parse_date(data)

    if tipo not in ("ENTRADA", "SAIDA"):
        return RedirectResponse(url="/financeiro/lancamentos?msg=tipo", status_code=303)
    if status not in ("PAGO", "PENDENTE"):
        status = "PAGO"
    if not dt:
        return RedirectResponse(url="/financeiro/lancamentos?msg=data", status_code=303)

    try:
        v = float(str(valor).replace(",", "."))
        if v <= 0:
            raise ValueError()
    except Exception:
        return RedirectResponse(url="/financeiro/lancamentos?msg=valor", status_code=303)

    desc = (descricao or "").strip()
    if len(desc) < 2:
        return RedirectResponse(url="/financeiro/lancamentos?msg=desc", status_code=303)

    def _int_or_none(x: str | None):
        if x and str(x).isdigit():
            return int(x)
        return None

    lanc = FinanceLancamento(
        tipo=tipo,
        status=status,
        data=dt,
        valor=v,
        descricao=desc,
        categoria_id=_int_or_none(categoria_id),
        forma_pagamento_id=_int_or_none(forma_pagamento_id),
        conta_id=_int_or_none(conta_id),
        created_at=datetime.utcnow(),
        is_active=True,
    )
    db.add(lanc)
    db.commit()

    return RedirectResponse(url="/financeiro/lancamentos?msg=ok", status_code=303)


@router.get("/financeiro/cadastros", response_class=HTMLResponse)
def cadastros_get(request: Request, db: Session = Depends(get_db)):
    guard = require_finance_login(request)
    if guard:
        return guard

    categorias = db.query(FinanceCategoria).order_by(FinanceCategoria.is_active.desc(), FinanceCategoria.nome.asc()).all()
    formas = db.query(FinanceFormaPagamento).order_by(FinanceFormaPagamento.is_active.desc(), FinanceFormaPagamento.nome.asc()).all()
    contas = db.query(FinanceConta).order_by(FinanceConta.is_active.desc(), FinanceConta.nome.asc()).all()

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "financeiro/index.html",
        {"request": request, "categorias": categorias, "formas": formas, "contas": contas},
    )


@router.post("/financeiro/categorias/create")
def cat_create(request: Request, nome: str = Form(...), db: Session = Depends(get_db)):
    guard = require_finance_login(request)
    if guard:
        return guard

    nome = (nome or "").strip()
    if len(nome) < 2:
        return RedirectResponse(url="/financeiro/cadastros?msg=cat", status_code=303)
    if db.query(FinanceCategoria).filter(FinanceCategoria.nome == nome).first():
        return RedirectResponse(url="/financeiro/cadastros?msg=cat_dup", status_code=303)

    db.add(FinanceCategoria(nome=nome, is_active=True))
    db.commit()
    return RedirectResponse(url="/financeiro/cadastros?msg=ok", status_code=303)


@router.post("/financeiro/formas/create")
def forma_create(request: Request, nome: str = Form(...), db: Session = Depends(get_db)):
    guard = require_finance_login(request)
    if guard:
        return guard

    nome = (nome or "").strip()
    if len(nome) < 2:
        return RedirectResponse(url="/financeiro/cadastros?msg=forma", status_code=303)
    if db.query(FinanceFormaPagamento).filter(FinanceFormaPagamento.nome == nome).first():
        return RedirectResponse(url="/financeiro/cadastros?msg=forma_dup", status_code=303)

    db.add(FinanceFormaPagamento(nome=nome, is_active=True))
    db.commit()
    return RedirectResponse(url="/financeiro/cadastros?msg=ok", status_code=303)


@router.post("/financeiro/contas/create")
def conta_create(request: Request, nome: str = Form(...), db: Session = Depends(get_db)):
    guard = require_finance_login(request)
    if guard:
        return guard

    nome = (nome or "").strip()
    if len(nome) < 2:
        return RedirectResponse(url="/financeiro/cadastros?msg=conta", status_code=303)
    if db.query(FinanceConta).filter(FinanceConta.nome == nome).first():
        return RedirectResponse(url="/financeiro/cadastros?msg=conta_dup", status_code=303)

    db.add(FinanceConta(nome=nome, is_active=True))
    db.commit()
    return RedirectResponse(url="/financeiro/cadastros?msg=ok", status_code=303)


@router.post("/financeiro/toggle")
def toggle(
    request: Request,
    kind: str = Form(...),   # cat / forma / conta
    item_id: int = Form(...),
    db: Session = Depends(get_db),
):
    guard = require_finance_login(request)
    if guard:
        return guard

    kind = (kind or "").strip()
    model = {"cat": FinanceCategoria, "forma": FinanceFormaPagamento, "conta": FinanceConta}.get(kind)
    if not model:
        return RedirectResponse(url="/financeiro/cadastros", status_code=303)

    item = db.query(model).filter(model.id == item_id).first()
    if not item:
        return RedirectResponse(url="/financeiro/cadastros", status_code=303)

    item.is_active = not item.is_active
    db.commit()
    return RedirectResponse(url="/financeiro/cadastros?msg=ok", status_code=303)
