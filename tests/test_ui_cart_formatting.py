"""Carrinho (RF04) e formatação de dados para a tela (funções puras)."""

from __future__ import annotations

from datetime import date

import pytest

from mercadofacil import clock
from mercadofacil.models import Product, Register
from mercadofacil.ui import cart, formatting


# -------------------------------------------------------------------------------- carrinho
def test_carrinho_adicionar_soma_quantidades() -> None:
    carrinho = cart.add({}, 7)
    carrinho = cart.add(carrinho, 7, 2)
    carrinho = cart.add(carrinho, 9)
    assert carrinho == {7: 3, 9: 1}
    assert cart.units(carrinho) == 4
    assert cart.as_lines(carrinho) == [(7, 3), (9, 1)]  # mantém a ordem de inclusão
    with pytest.raises(ValueError):
        cart.add(carrinho, 7, 0)


def test_carrinho_alterar_e_remover() -> None:
    original = {1: 2, 2: 5}
    assert cart.set_quantity(original, 1, 4) == {1: 4, 2: 5}
    assert cart.set_quantity(original, 1, 0) == {2: 5}  # zero remove
    assert cart.set_quantity(original, 99, 3) == original  # item que não existe é ignorado
    assert cart.remove(original, 2) == {1: 2}
    assert original == {1: 2, 2: 5}  # operações não alteram o carrinho original


# ------------------------------------------------------------------------------ formatação
def produto(**over: object) -> Product:
    base = {
        "id": 1,
        "barcode": "789",
        "name": "Arroz",
        "price_cents": 2790,
        "stock": 10,
        "min_stock": 3,
        "active": 1,
    }
    return Product(**{**base, **over})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("stock", "active", "esperado"),
    [(10, 1, "✔ Em estoque"), (3, 1, "⚠ Repor"), (0, 1, "⛔ Sem estoque"), (10, 0, "Inativo")],
)
def test_situacao_do_estoque(stock: int, active: int, esperado: str) -> None:
    assert formatting.stock_status_label(produto(stock=stock, active=active)) == esperado


def test_dinheiro_com_sinal() -> None:
    assert formatting.signed_money(500) == "+R$ 5,00"
    assert formatting.signed_money(-500) == "-R$ 5,00"
    assert formatting.signed_money(0) == "R$ 0,00"


def test_resumo_da_diferenca_do_caixa_rb11() -> None:
    assert formatting.difference_summary(-500) == ("danger", "Falta de R$ 5,00 será registrada.")
    assert formatting.difference_summary(-500, registered=True)[1] == "Falta de R$ 5,00 registrada."
    assert formatting.difference_summary(250) == ("warn", "Sobra de R$ 2,50 será registrada.")
    assert formatting.difference_summary(0) == ("ok", "Caixa conferido: sem diferença.")


def test_periodos() -> None:
    hoje = clock.today_iso()
    assert formatting.period_range(formatting.PERIOD_TODAY) == (hoje, hoje)
    inicio, fim = formatting.period_range(formatting.PERIOD_7_DAYS)
    assert fim == hoje and inicio == clock.days_ago_iso(6)
    assert formatting.period_range(formatting.PERIOD_30_DAYS)[0] == clock.days_ago_iso(29)
    assert formatting.period_range("inventado") == (hoje, hoje)


def test_intervalo_de_datas_do_seletor() -> None:
    a, b = date(2026, 10, 1), date(2026, 10, 31)
    assert formatting.date_range_iso((a, b)) == ("2026-10-01", "2026-10-31")
    assert formatting.date_range_iso((a,)) == ("2026-10-01", "2026-10-01")  # seleção em andamento
    assert formatting.date_range_iso(a) == ("2026-10-01", "2026-10-01")
    assert formatting.date_range_iso(()) == (None, None)
    assert formatting.date_range_iso(None) == (None, None)


def test_linhas_de_produto_usam_formato_brasileiro() -> None:
    (linha,) = formatting.product_rows([produto(price_cents=123456, cost_cents=100000)])
    assert linha["Preço"] == "R$ 1.234,56" and linha["Custo"] == "R$ 1.000,00"
    assert linha["Localização"] == "—"


def test_linha_do_historico_de_caixas() -> None:
    aberto = Register(
        id=1, operator="ana", status="aberto", opening_cents=10000, opened_at="2026-10-27 08:00:00"
    )
    fechado = Register(
        id=2,
        operator="ana",
        status="fechado",
        opening_cents=10000,
        opened_at="2026-10-27 08:00:00",
        expected_cents=25000,
        counted_cents=24500,
        difference_cents=-500,
        closed_at="2026-10-27 18:00:00",
    )
    linhas = formatting.register_rows([aberto, fechado])
    assert linhas[0]["Situação"] == "Aberto" and linhas[0]["Contado"] == "—"
    assert (
        linhas[1]["Diferença"] == "Falta R$ 5,00" and linhas[1]["Fechamento"] == "27/10/2026 18:00"
    )
    assert formatting.register_status_text(aberto) == "Caixa aberto"
    assert formatting.register_status_text(fechado) == "Caixa fechado"
    assert formatting.register_status_text(None) == "Caixa fechado"


def test_csv_para_excel_brasileiro() -> None:
    dados = formatting.rows_to_csv([{"Produto": "Arroz; tipo 1", "Preço": "R$ 27,90"}])
    assert dados.startswith(b"\xef\xbb\xbf")
    texto = dados.decode("utf-8-sig")
    assert texto.splitlines()[0] == "Produto;Preço"
    assert '"Arroz; tipo 1";R$ 27,90' in texto
    assert formatting.rows_to_csv([]) == b""


def test_tamanho_de_arquivo_legivel() -> None:
    assert formatting.file_size(900) == "900 B"
    assert formatting.file_size(2048) == "2,0 KB"
    assert formatting.file_size(5 * 1024 * 1024) == "5,0 MB"
