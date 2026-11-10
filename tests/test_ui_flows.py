"""Fluxos completos das telas (login, navegação, caixa, PDV, produtos, pós-venda)."""

from __future__ import annotations

import sqlite3

import pytest

from mercadofacil import database
from mercadofacil.models import Product
from mercadofacil.services import auth, cash_register, catalog, sales
from tests.conftest import CPF_A
from tests.ui_harness import UiApp

PASSWORDS = {"gestor": "gestor123", "operador": "operador123", "estoquista": "estoque123"}


def sign_in(app: UiApp, username: str) -> None:
    app.shell()
    app.type("login_username", username).type("login_password", PASSWORDS[username])
    app.click("Entrar")
    app.shell()


def product_by_name(name: str) -> Product:
    with database.connect() as conn:
        found = catalog.search_products(conn, term=name)
    assert found, name
    return found[0]


def db() -> sqlite3.Connection:
    return database.get_connection()


# ----------------------------------------------------------------------------- login
def test_login_com_sucesso_leva_a_tela_inicial_do_perfil(app: UiApp) -> None:
    sign_in(app, "operador")
    assert app.contains("Frente de caixa", "Operador de Demonstração")
    assert app.contains("Caixa fechado")  # RF01 (manual): cabeçalho mostra o estado do caixa


def test_login_invalido_mostra_erro_sem_revelar_o_campo(app: UiApp) -> None:
    app.shell()
    app.type("login_username", "operador").type("login_password", "errada")
    app.click("Entrar")
    app.shell()
    assert app.contains("Usuário ou senha inválidos")
    assert not app.contains("Caixa fechado")


@pytest.mark.parametrize(
    ("username", "paginas", "ausentes"),
    [
        (
            "operador",
            ["Frente de caixa", "Vendas e pós-venda", "Abertura e fechamento"],
            ["Movimentações", "Produtos e estoque"],
        ),
        (
            "estoquista",
            ["Produtos e estoque", "Movimentações", "Visão geral"],
            ["Frente de caixa", "Abertura e fechamento"],
        ),
        (
            "gestor",
            ["Frente de caixa", "Produtos e estoque", "Movimentações", "Projeto e operação"],
            [],
        ),
    ],
)
def test_menu_lateral_respeita_o_perfil(
    app: UiApp, username: str, paginas: list[str], ausentes: list[str]
) -> None:
    sign_in(app, username)
    labels = " ".join(app.st.labels("button"))
    for pagina in paginas:
        assert pagina in labels
    for pagina in ausentes:
        assert pagina not in labels


def test_sair_encerra_a_sessao(app: UiApp) -> None:
    sign_in(app, "gestor")
    app.click("logout")
    app.shell()
    assert app.contains("Entrar", "Senha")
    assert "auth_user" not in app.st.session_state


def test_navegar_troca_de_tela(app: UiApp) -> None:
    sign_in(app, "gestor")
    app.click("nav_movements")
    app.shell()
    assert app.contains("Unidades que entraram")
    app.click("nav_project")
    app.shell()
    assert app.contains("Visão geral do projeto")


def test_usuario_desativado_perde_o_acesso_na_proxima_acao(app: UiApp) -> None:
    sign_in(app, "operador")
    with db() as conn:
        conn.execute("UPDATE users SET active = 0 WHERE username = 'operador'")
    app.shell()
    assert app.contains("não está mais ativo", "Entrar")


# ---------------------------------------------------------------------------- caixa
def go(app: UiApp, page: str) -> None:
    app.click(f"nav_{page}")
    app.shell()


def open_cash(username: str = "operador", cents: int = 10_000) -> None:
    with database.connect() as conn:
        user = auth.reload_user(conn, username)
        assert user is not None
        cash_register.open_register(conn, user, cents)


def test_abrir_caixa_pela_tela_atualiza_o_cabecalho(app: UiApp) -> None:
    sign_in(app, "operador")
    go(app, "register")
    assert app.contains("Caixa fechado", "Abrir caixa")
    app.type("open_register_fund", "100,00").click("Abrir caixa")
    app.shell()
    assert app.contains("Caixa aberto com fundo inicial de R$ 100,00.")
    assert app.contains("● Caixa aberto")
    assert app.contains("Esperado na gaveta", "R$ 100,00")


def test_abrir_caixa_exige_o_fundo_inicial(app: UiApp) -> None:
    sign_in(app, "operador")
    go(app, "register")
    app.click("Abrir caixa")
    app.shell()
    assert app.contains("Informe o fundo inicial")
    assert app.contains("● Caixa fechado")


def test_fechar_caixa_com_falta_registra_o_valor_ct12(app: UiApp) -> None:
    open_cash(cents=10_000)
    sign_in(app, "operador")
    go(app, "register")
    app.type("close_register_counted", "95,00")
    app.shell()
    assert app.contains("Falta de R$ 5,00 será registrada")  # conferência antes de confirmar
    app.click("close_register_confirm")
    app.shell()
    assert app.contains("Caixa #1 fechado", "Falta de R$ 5,00 registrada")
    assert app.contains("● Caixa fechado", "Falta R$ 5,00")  # histórico com a diferença
    with db() as conn:
        row = conn.execute("SELECT status, difference_cents FROM registers").fetchone()
    assert (row["status"], row["difference_cents"]) == ("fechado", -500)


def test_fechar_caixa_exige_valor_contado(app: UiApp) -> None:
    open_cash()
    sign_in(app, "operador")
    go(app, "register")
    assert app.contains("Informe o valor contado para liberar o fechamento")
    app.click("close_register_confirm")
    app.shell()
    assert app.contains("● Caixa aberto")


def test_valor_monetario_invalido_e_explicado(app: UiApp) -> None:
    open_cash()
    sign_in(app, "operador")
    go(app, "register")
    app.type("close_register_counted", "abc")
    app.shell()
    assert app.contains("Valor inválido")


# ------------------------------------------------------------------------------- PDV
def pos(app: UiApp, username: str = "operador", *, cash: bool = True) -> None:
    if cash:
        open_cash(username)
    sign_in(app, username)
    if username != "operador":
        go(app, "pos")


def scan(app: UiApp, text: str) -> None:
    app.type("pos_scan", text).click("Adicionar ao carrinho")
    app.shell()


def stock_of(name: str) -> int:
    return product_by_name(name).stock


def test_bipar_codigo_adiciona_ao_carrinho_e_soma_repeticoes(app: UiApp) -> None:
    pos(app)
    arroz = product_by_name("Arroz")
    scan(app, arroz.barcode)
    assert app.contains("“Arroz Tipo 1 5kg” adicionado: 1 no carrinho.", "R$ 27,90")
    scan(app, arroz.barcode)
    assert app.contains("2 no carrinho", "R$ 55,80", "Carrinho (2 un.)")
    assert app.st.session_state["pos_cart"] == {arroz.id: 2}


def test_busca_por_nome_adiciona_quando_ha_um_unico_resultado(app: UiApp) -> None:
    pos(app)
    scan(app, "banana")
    assert app.contains("“Banana Prata” adicionado")


def test_busca_por_nome_com_varios_resultados_filtra_a_lista(app: UiApp) -> None:
    pos(app)
    scan(app, "agua")  # Água Mineral e Água Sanitária
    assert app.contains("Vários produtos correspondem a “agua”")
    assert app.st.session_state["pos_search"] == "agua"
    assert app.contains("Água Mineral 1,5L", "Água Sanitária 1L")
    assert not app.contains("Arroz Tipo 1 5kg")
    assert app.st.session_state.get("pos_cart", {}) == {}


def test_codigo_desconhecido_avisa_sem_alterar_o_carrinho(app: UiApp) -> None:
    pos(app)
    scan(app, "0000000000000")
    assert app.contains("Nenhum produto ativo encontrado")
    assert app.st.session_state.get("pos_cart", {}) == {}


def test_produto_sem_estoque_nao_entra_no_carrinho_ct08(app: UiApp) -> None:
    pos(app)
    scan(app, product_by_name("Óleo de Soja").barcode)
    assert app.contains("Venda bloqueada: estoque insuficiente", "disponível 0")
    assert app.st.session_state.get("pos_cart", {}) == {}


def test_alterar_quantidade_e_remover_item_rf04(app: UiApp) -> None:
    pos(app)
    arroz = product_by_name("Arroz")
    scan(app, arroz.barcode)
    app.type(f"pos_qty_{arroz.id}", 3)
    app.shell()
    assert app.st.session_state["pos_cart"] == {arroz.id: 3}
    assert app.contains("R$ 83,70")
    app.click(f"pos_remove_{arroz.id}")
    app.shell()
    assert app.st.session_state["pos_cart"] == {}
    assert app.contains("O carrinho está vazio")


def test_quantidade_acima_do_estoque_e_sinalizada_e_a_venda_e_bloqueada_ct08(app: UiApp) -> None:
    pos(app)
    macas = product_by_name("Maçã")
    scan(app, macas.barcode)
    app.type(f"pos_qty_{macas.id}", macas.stock + 4)
    app.shell()
    assert app.contains("Estoque insuficiente", f"Disponível: {macas.stock}")
    app.type("pos_received", "500,00")
    app.click("pos_finalize")
    app.shell()
    assert app.contains("Venda bloqueada: estoque insuficiente")
    assert stock_of("Maçã") == macas.stock  # nada foi baixado
    assert app.st.session_state["pos_cart"] == {macas.id: macas.stock + 4}  # carrinho preservado


def test_troco_e_calculado_automaticamente_ct06(app: UiApp) -> None:
    pos(app)
    scan(app, product_by_name("Sal Refinado").barcode)  # R$ 2,49
    scan(app, product_by_name("Café Torrado").barcode)  # R$ 18,90
    app.type("pos_received", "50,00")
    app.shell()
    assert app.contains("TOTAL A PAGAR", "R$ 21,39", "TROCO", "R$ 28,61")


def test_valor_recebido_menor_que_o_total_e_bloqueado_ct05(app: UiApp) -> None:
    pos(app)
    scan(app, product_by_name("Café Torrado").barcode)
    app.type("pos_received", "10,00")
    app.shell()
    assert app.contains("Pagamento bloqueado", "Faltam R$ 8,90")
    assert not app.contains("TROCO")
    app.click("pos_finalize")
    app.shell()
    assert app.contains("Pagamento bloqueado")
    assert stock_of("Café Torrado") == 8  # a venda não foi registrada


def test_atalho_valor_exato_preenche_o_recebido(app: UiApp) -> None:
    pos(app)
    scan(app, product_by_name("Café Torrado").barcode)
    app.click("pos_cash_1890")
    app.shell()
    assert app.st.session_state["pos_received"] == "18,90"
    assert app.contains("TROCO", "R$ 0,00")


def test_finalizar_venda_mostra_comprovante_baixa_estoque_e_limpa_o_carrinho(app: UiApp) -> None:
    pos(app)
    arroz = product_by_name("Arroz")
    scan(app, arroz.barcode)
    app.type("pos_received", "50,00")
    app.shell()
    app.click("pos_finalize")
    app.shell()
    assert app.contains("Venda concluída", "TOTAL", "R$ 27,90", "TROCO", "R$ 22,10")
    assert app.contains("Comprovante da venda")
    assert "MERCADO FÁCIL" in app.raw()
    assert app.st.downloads[0]["file_name"].startswith("comprovante_V")
    assert stock_of("Arroz") == arroz.stock - 1
    assert app.st.session_state.get("pos_cart") is None
    assert app.contains("O carrinho está vazio")
    app.click("pos_new_sale")
    app.shell()
    assert not app.contains("Venda concluída")


def test_venda_com_caixa_fechado_e_nao_autorizada_ct04(app: UiApp) -> None:
    pos(app, cash=False)
    assert app.contains("Caixa fechado", "RB01")
    scan(app, product_by_name("Café Torrado").barcode)
    app.type("pos_received", "50,00")
    app.click("pos_finalize")
    app.shell()
    assert app.contains("Venda não autorizada: o caixa está fechado")
    assert stock_of("Café Torrado") == 8


def test_pix_nao_pede_valor_recebido_e_aprovacao_pode_ser_recusada(app: UiApp) -> None:
    pos(app)
    scan(app, product_by_name("Café Torrado").barcode)
    app.type("pos_method", "pix")
    app.shell()
    assert not app.contains("Valor recebido")
    assert app.contains("Simulação do sistema de pagamento")
    app.type("pos_decline_payment", True)
    app.click("pos_finalize")
    app.shell()
    assert app.contains("não aprovado")
    assert stock_of("Café Torrado") == 8
    app.type("pos_decline_payment", False)
    app.click("pos_finalize")
    app.shell()
    assert app.contains("Venda concluída", "Pix")
    assert not app.contains("TROCO")


def test_identificar_cliente_mostra_nome_e_saldo_rf07(app: UiApp) -> None:
    pos(app)
    app.type("pos_cpf_input", "529.982.247-25").click("Identificar cliente")
    app.shell()
    assert app.contains("Cliente identificado", "Maria Silva", "R$ 12,34", "***.982.247-**")
    assert "529.982.247-25" not in app.text()  # CPF mascarado na tela


def test_cpf_invalido_e_cpf_novo(app: UiApp) -> None:
    pos(app)
    app.type("pos_cpf_input", "111.111.111-11").click("Identificar cliente")
    app.shell()
    assert app.contains("CPF")
    assert app.st.session_state.get("pos_customer_cpf") is None
    app.type("pos_cpf_input", "453.178.287-91").click(
        "Identificar cliente"
    )  # válido e não cadastrado
    app.shell()
    assert app.contains("ainda não está cadastrado", "Cadastrar e identificar")
    app.type("pos_name_input", "Carlos Novo").click("Cadastrar e identificar")
    app.shell()
    assert app.contains("Carlos Novo", "Cliente identificado")


def test_cashback_maior_que_o_saldo_e_bloqueado_ct07(app: UiApp) -> None:
    pos(app)
    app.type("pos_cpf_input", CPF_A).click("Identificar cliente")
    app.shell()
    scan(app, product_by_name("Café Torrado").barcode)
    app.type("pos_use_cashback", True)
    app.shell()
    app.type("pos_cashback_amount", "50,00")
    app.shell()
    assert app.contains("Uso bloqueado", "RB06")
    app.click("pos_finalize")
    app.shell()
    assert app.contains("Uso bloqueado")
    assert stock_of("Café Torrado") == 8


def test_venda_com_cashback_e_acumulo_de_1_por_cento_rb07(app: UiApp) -> None:
    pos(app)
    app.type("pos_cpf_input", CPF_A).click("Identificar cliente")  # saldo R$ 12,34
    app.shell()
    scan(app, product_by_name("Café Torrado").barcode)  # R$ 18,90
    app.type("pos_use_cashback", True)
    app.shell()
    assert app.st.session_state["pos_cashback_amount"] == "12,34"  # sugere o máximo permitido
    app.type("pos_received", "10,00")
    app.shell()
    assert app.contains("Cashback utilizado", "-R$ 12,34", "R$ 6,56", "R$ 0,06")  # 1% de 6,56
    app.click("pos_finalize")
    app.shell()
    assert app.contains(
        "Venda concluída", "Cashback gerado: R$ 0,06", "novo saldo de Maria Silva: R$ 0,06"
    )


def test_compra_quitada_integralmente_com_cashback(app: UiApp) -> None:
    pos(app)
    app.type("pos_cpf_input", "390.533.447-05").click("Identificar cliente")  # Ana: saldo R$ 48,50
    app.shell()
    scan(app, product_by_name("Sal Refinado").barcode)  # R$ 2,49
    app.type("pos_use_cashback", True)
    app.shell()
    app.type("pos_cashback_amount", "2,49")
    app.shell()
    assert app.contains("Compra quitada integralmente com o saldo de cashback")
    app.click("pos_finalize")
    app.shell()
    assert app.contains("Venda concluída", "Cashback")


def test_descartar_venda_limpa_o_carrinho(app: UiApp) -> None:
    pos(app)
    scan(app, product_by_name("Sal Refinado").barcode)
    app.click("pos_clear")
    app.shell()
    assert app.contains("Venda em andamento descartada", "O carrinho está vazio")
    assert stock_of("Sal Refinado") == 50


# ---------------------------------------------------------------------------- produtos
def stocker(app: UiApp) -> None:
    sign_in(app, "estoquista")


def fill_new_product(app: UiApp, **fields: str) -> None:
    defaults = {"barcode": "", "name": "", "price": "", "cost": "", "location": ""}
    for field, value in {**defaults, **fields}.items():
        app.type(f"new_product_{field}", value)


def test_estoquista_ve_alerta_de_reposicao_e_catalogo_rf10(app: UiApp) -> None:
    stocker(app)
    assert app.contains("Reposição necessária", "Óleo de Soja 900ml", "Sem estoque", "Repor")
    assert app.contains("Arroz Tipo 1 5kg", "R$ 27,90")


def test_filtro_abaixo_do_minimo(app: UiApp) -> None:
    stocker(app)
    app.st.choose("Situação", "Abaixo do mínimo")
    app.shell()
    assert app.contains("Café Torrado", "Óleo de Soja")
    assert not app.contains("Arroz Tipo 1 5kg ")  # a linha do arroz sai do filtro
    assert not any("Arroz" in str(df.to_dict("records")) for df in app.st.dataframes)


def test_cadastrar_produto_rf08(app: UiApp) -> None:
    stocker(app)
    app.hold("products_new")
    app.shell()
    assert app.contains("Código de barras *", "Preço de venda (R$) *")
    fill_new_product(
        app,
        barcode="7899999999991",
        name="Biscoito Recheado",
        price="3,49",
        cost="2,10",
        location="Corredor 9",
    )
    app.type("new_product_min_stock", 5).type("new_product_initial_stock", 12)
    app.click("Cadastrar produto")
    app.shell()
    assert app.contains("Produto “Biscoito Recheado” cadastrado com saldo inicial de 12 un.")
    created = product_by_name("Biscoito")
    assert (created.price_cents, created.cost_cents, created.stock, created.location) == (
        349,
        210,
        12,
        "Corredor 9",
    )
    assert app.contains("Biscoito Recheado")


def test_cadastro_com_codigo_duplicado_e_bloqueado_ct01(app: UiApp) -> None:
    stocker(app)
    existente = product_by_name("Arroz")
    app.hold("products_new")
    app.shell()
    fill_new_product(app, barcode=existente.barcode, name="Outro Arroz", price="9,99")
    app.click("Cadastrar produto")
    app.shell()
    assert app.contains("Cadastro bloqueado", "já existe um produto ativo", "RB02")
    assert len(catalog.search_products(db(), term="Outro Arroz")) == 0


def test_cadastro_com_campo_obrigatorio_vazio_e_rejeitado_ct02(app: UiApp) -> None:
    stocker(app)
    app.hold("products_new")
    app.shell()
    fill_new_product(app, barcode="7899999999991", name="", price="3,00")
    app.click("Cadastrar produto")
    app.shell()
    assert app.contains("Confira os dados informados", "nome do produto")
    fill_new_product(app, barcode="7899999999991", name="Sem preço", price="")
    app.click("Cadastrar produto")
    app.shell()
    assert app.contains("Informe o preço de venda")
    assert catalog.count_products(db(), term="Sem preço") == 0


def select_product(app: UiApp, name: str) -> Product:
    app.st.choose("Produto selecionado", name)
    app.shell()
    return product_by_name(name)


def test_saida_maior_que_o_saldo_e_impedida_ct03(app: UiApp) -> None:
    stocker(app)
    arroz = select_product(app, "Arroz")
    app.hold("products_move")
    app.shell()
    assert app.contains(f"Saldo atual: {arroz.stock} pct")
    key = f"move_{arroz.id}"
    app.type(f"{key}_kind", "saida")
    app.shell()
    app.type(f"{key}_qty_saida", arroz.stock + 1)
    app.shell()
    assert app.contains("Estoque negativo impedido")  # prévia na própria tela
    app.click(f"{key}_submit")
    app.shell()
    assert app.contains("Regra de negócio RB03", "Estoque negativo impedido")
    assert product_by_name("Arroz").stock == arroz.stock


def test_entrada_com_motivo_e_referencia_atualiza_o_saldo_rf09(app: UiApp) -> None:
    stocker(app)
    cafe = select_product(app, "Café Torrado")
    app.hold("products_move")
    app.shell()
    key = f"move_{cafe.id}"
    app.type(f"{key}_qty_entrada", 20).type(f"{key}_reference", "NF 4321")
    app.shell()
    assert app.contains(f"Novo saldo previsto: {cafe.stock + 20} pct")
    app.click(f"{key}_submit")
    app.shell()
    assert app.contains("Entrada de 20 registrada", f"Novo saldo: {cafe.stock + 20}")
    assert product_by_name("Café Torrado").stock == cafe.stock + 20
    last = (
        db()
        .execute("SELECT reason, reference, operator FROM stock_movements ORDER BY id DESC")
        .fetchone()
    )
    assert (last["reason"], last["reference"], last["operator"]) == (
        "Reposição de mercadoria",
        "NF 4321",
        "estoquista",
    )


def test_motivo_outro_exige_detalhe(app: UiApp) -> None:
    stocker(app)
    cafe = select_product(app, "Café Torrado")
    app.hold("products_move")
    app.shell()
    key = f"move_{cafe.id}"
    app.type(f"{key}_reason_entrada", "Outro")
    app.shell()
    assert app.contains("Detalhe do motivo (obrigatório)")
    app.click(f"{key}_submit")
    app.shell()
    assert app.contains("Informe o motivo da movimentação")


def test_ajuste_de_inventario_define_o_saldo(app: UiApp) -> None:
    stocker(app)
    cafe = select_product(app, "Café Torrado")
    app.hold("products_move")
    app.shell()
    key = f"move_{cafe.id}"
    app.type(f"{key}_kind", "ajuste")
    app.shell()
    app.type(f"{key}_counted", 3)
    app.click(f"{key}_submit")
    app.shell()
    assert product_by_name("Café Torrado").stock == 3
    assert app.contains("Saída de 5 registrada", "Novo saldo: 3")


def test_editar_produto_nao_altera_o_saldo(app: UiApp) -> None:
    stocker(app)
    cafe = select_product(app, "Café Torrado")
    app.hold("products_edit")
    app.shell()
    assert app.contains("Saldo atual (somente leitura)")
    key = f"edit_product_{cafe.id}"
    app.type(f"{key}_price", "19,90").type(f"{key}_location", "Corredor 2 · B")
    app.click("Salvar alterações")
    app.shell()
    updated = product_by_name("Café Torrado")
    assert (updated.price_cents, updated.location, updated.stock) == (
        1990,
        "Corredor 2 · B",
        cafe.stock,
    )
    assert app.contains("Produto “Café Torrado 500g” atualizado")


def test_inativar_e_reativar_produto_preserva_historico(app: UiApp) -> None:
    stocker(app)
    cafe = select_product(app, "Café Torrado")
    app.click("products_toggle")
    app.shell()
    assert app.contains("Produto “Café Torrado 500g” inativado", "RB12")
    assert not catalog.search_products(db(), term="Café Torrado")
    assert catalog.get_product(db(), cafe.id).active == 0
    app.st.choose("Situação", "Inclui inativos")
    app.shell()
    app.st.choose("Produto selecionado", "Café Torrado")
    app.shell()
    app.click("products_toggle")
    app.shell()
    assert app.contains("reativado")
    assert catalog.get_product(db(), cafe.id).active == 1


# ------------------------------------------------------------- vendas e pós-venda
def make_sale(product_name: str = "Café Torrado", quantity: int = 3, *, method: str = "pix") -> str:
    """Operador vende pelos serviços (o caixa precisa estar aberto) e devolve o ID da venda."""
    open_cash()
    with database.connect() as conn:
        operator = auth.reload_user(conn, "operador")
        assert operator is not None
        product = catalog.search_products(conn, term=product_name)[0]
        detail = sales.finalize_sale(
            conn, operator, [(product.id, quantity)], payment_method=method, received_cents=None
        )
    return detail.sale.id


def open_sale(app: UiApp, sale_id: str) -> None:
    app.st.choose("Venda", sale_id)
    app.shell()


def test_consultar_venda_com_itens_pagamento_e_ocorrencias_rf15(app: UiApp) -> None:
    sale_id = make_sale()
    sign_in(app, "gestor")
    go(app, "sales")
    assert app.contains("1 venda(s) encontrada(s)", sale_id, "Pix", "R$ 56,70")
    open_sale(app, sale_id)
    assert app.contains("Detalhe da venda", "Café Torrado 500g", "Itens", "Pagamento: Pix")
    assert app.contains("Nenhuma ocorrência registrada nesta venda", "Comprovante")
    assert app.contains("Cancelar item", "Devolver", "Trocar", "Cancelar venda inteira")


def test_filtros_de_vendas(app: UiApp) -> None:
    sale_id = make_sale()
    sign_in(app, "gestor")
    go(app, "sales")
    app.st.choose("Pagamento", "Dinheiro")
    app.shell()
    assert app.contains("Nenhuma venda encontrada")
    app.st.choose("Pagamento", "Pix")
    app.type("sales_text", "ninguém")
    app.shell()
    assert app.contains("Nenhuma venda encontrada")
    app.type("sales_text", sale_id[-4:])
    app.shell()
    assert app.contains("1 venda(s) encontrada(s)")


def test_cancelar_venda_inteira_ct09(app: UiApp) -> None:
    sale_id = make_sale(quantity=3)
    assert stock_of("Café Torrado") == 5
    sign_in(app, "gestor")
    go(app, "sales")
    open_sale(app, sale_id)
    app.hold(f"sales_cancel_{sale_id}")
    app.shell()
    assert app.contains(f"Cancelar a venda {sale_id}?", "Você é gestor")
    prefix = f"cancel_sale_{sale_id}"
    app.type(f"{prefix}_notes", "Cliente desistiu")
    app.click("Cancelar venda")
    app.shell()  # sem confirmar: bloqueia
    assert app.contains("Confirmação necessária")
    assert stock_of("Café Torrado") == 5
    app.type(f"{prefix}_confirm", True).click("Cancelar venda")
    app.shell()
    assert app.contains(f"Venda {sale_id} cancelada; itens ativos devolvidos ao estoque")
    assert stock_of("Café Torrado") == 8
    open_sale(app, sale_id)
    assert app.contains("Cancelada", "não aceita novas operações", "Cancelamento de venda")


def test_operador_precisa_da_autorizacao_do_gestor_para_devolver(app: UiApp) -> None:
    sale_id = make_sale(quantity=3)
    sign_in(app, "operador")
    go(app, "sales")
    open_sale(app, sale_id)
    assert app.contains("exige a autorização de um gestor")
    app.hold(f"sales_return_{sale_id}")
    app.shell()
    prefix = f"return_{sale_id}"
    assert app.contains("Autorização do gestor", "Usuário do gestor", "Senha do gestor")
    app.type(f"{prefix}_qty", 1).type(f"{prefix}_notes", "Embalagem rasgada")
    app.click("Registrar devolução")
    app.shell()
    assert app.contains("exige autorização de um gestor")  # sem credenciais
    app.type(f"{prefix}_sup_user", "gestor").type(f"{prefix}_sup_pass", "errada")
    app.click("Registrar devolução")
    app.shell()
    assert app.contains("Autorização negada")
    app.type(f"{prefix}_sup_pass", "gestor123")
    app.click("Registrar devolução")
    app.shell()
    assert app.contains("Devolução registrada", "Devolvido R$ 18,90 (Pix)")
    assert stock_of("Café Torrado") == 5 + 1  # 8 - 3 vendidos + 1 devolvido
    with db() as conn:
        op = conn.execute("SELECT operator, authorized_by FROM post_sale_operations").fetchone()
    assert (op["operator"], op["authorized_by"]) == ("operador", "gestor")


def test_devolver_mais_que_o_disponivel_e_bloqueado_ct10(app: UiApp) -> None:
    sale_id = make_sale(quantity=2)
    sign_in(app, "gestor")
    go(app, "sales")
    open_sale(app, sale_id)
    app.hold(f"sales_return_{sale_id}")
    app.shell()
    prefix = f"return_{sale_id}"
    app.type(f"{prefix}_qty", 3).type(f"{prefix}_notes", "Teste")
    app.click("Registrar devolução")
    app.shell()
    assert app.contains("Operação bloqueada", "RB09")
    assert stock_of("Café Torrado") == 6


def test_cancelar_item_parcial_rf12(app: UiApp) -> None:
    sale_id = make_sale(quantity=3)
    sign_in(app, "gestor")
    go(app, "sales")
    open_sale(app, sale_id)
    app.hold(f"sales_cancel_item_{sale_id}")
    app.shell()
    prefix = f"cancel_item_{sale_id}"
    app.type(f"{prefix}_qty", 2).type(f"{prefix}_notes", "Cliente trouxe só um")
    app.click("Cancelar item")
    app.shell()
    assert app.contains("Item cancelado na venda", "Devolvido R$ 37,80")
    assert stock_of("Café Torrado") == 7
    open_sale(app, sale_id)
    assert app.contains("Parcialmente alterada")


def test_trocar_por_produto_sem_estoque_e_bloqueado_ct11(app: UiApp) -> None:
    sale_id = make_sale(quantity=1)
    sign_in(app, "gestor")
    go(app, "sales")
    open_sale(app, sale_id)
    app.hold(f"sales_exchange_{sale_id}")
    app.shell()
    prefix = f"exchange_{sale_id}"
    app.st.choose(f"{prefix}_replacement", "Óleo de Soja")
    app.type(f"{prefix}_notes", "Cliente preferiu outro")
    app.shell()
    assert app.contains("Produto mais barato", "recebe R$ 11,41")
    app.click(f"{prefix}_submit")
    app.shell()
    assert app.contains("Troca bloqueada", "RB10")
    assert stock_of("Óleo de Soja") == 0


def test_trocar_por_produto_mais_caro_pede_forma_de_pagamento_da_diferenca(app: UiApp) -> None:
    sale_id = make_sale("Sal Refinado", 1)  # R$ 2,49
    sign_in(app, "gestor")
    go(app, "sales")
    open_sale(app, sale_id)
    app.hold(f"sales_exchange_{sale_id}")
    app.shell()
    prefix = f"exchange_{sale_id}"
    app.st.choose(f"{prefix}_replacement", "Café Torrado")
    app.type(f"{prefix}_notes", "Preferiu o café")
    app.shell()
    assert app.contains(
        "Produto mais caro", "paga a diferença de R$ 16,41", "Forma de pagamento da diferença"
    )
    app.type(f"{prefix}_settlement", "pix")
    app.click(f"{prefix}_submit")
    app.shell()
    assert app.contains("Troca registrada", "Recebido R$ 16,41 (Pix)")
    assert stock_of("Café Torrado") == 7 and stock_of("Sal Refinado") == 50


def test_estoquista_nao_tem_acesso_a_vendas(app: UiApp) -> None:
    sign_in(app, "estoquista")
    assert "🧾  Vendas e pós-venda" not in app.st.labels("button")
    app.st.session_state["nav_page"] = "sales"  # tentativa de abrir a tela por fora do menu
    app.shell()
    assert not app.contains("venda(s) encontrada(s)")
    assert app.contains("Produtos e estoque")  # volta para a tela permitida


# ------------------------------------------------------------------- movimentações
def test_historico_de_movimentacoes_rf16(app: UiApp) -> None:
    sale_id = make_sale(quantity=2)
    sign_in(app, "gestor")
    go(app, "movements")
    assert app.contains(
        sale_id, "Venda", "Estoque inicial", "Unidades que entraram", "▼ Saída", "▲ Entrada"
    )
    app.st.choose("Tipo", "Somente saídas")
    app.shell()
    assert not app.contains("▲ Entrada")
    app.type("movements_text", sale_id)
    app.shell()
    assert len(app.st.dataframes) == 1 and len(app.st.dataframes[0]) == 1
    assert app.st.downloads[0]["file_name"].startswith("movimentacoes_")
    assert app.st.downloads[0]["data"].startswith(b"\xef\xbb\xbf")  # BOM para o Excel
    app.type("movements_text", "nada disso existe")
    app.shell()
    assert app.contains("Nenhuma movimentação encontrada")


def test_operador_nao_ve_movimentacoes(app: UiApp) -> None:
    sign_in(app, "operador")
    assert "🔁  Movimentações" not in app.st.labels("button")


# ---------------------------------------------------------------------- visão geral
def test_visao_geral_resume_o_dia(app: UiApp) -> None:
    make_sale("Café Torrado", 2)
    sign_in(app, "gestor")
    assert app.contains("Visão geral", "Vendas concluídas", "R$ 37,80", "Ticket médio")
    assert app.contains("Produtos para repor", "Óleo de Soja", "Água Sanitária")
    assert app.contains("Pix", "Café Torrado 500g")
    app.st.choose("Período", "Últimos 30 dias")
    app.shell()
    assert app.contains("R$ 37,80")


def test_visao_geral_sem_vendas_tem_estados_vazios(app: UiApp) -> None:
    sign_in(app, "gestor")
    assert app.contains("Nenhuma venda registrada ainda", "Sem vendas no período")


def test_estoquista_ve_visao_geral_sem_vendas(app: UiApp) -> None:
    sign_in(app, "estoquista")
    go(app, "overview")
    assert app.contains("não consulta vendas", "Alertas de reposição")
