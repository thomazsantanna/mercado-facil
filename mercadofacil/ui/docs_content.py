"""Conteúdo da documentação do projeto exibido na tela "Projeto e operação".

Reproduz o documento do Grupo 4 (seções 1 a 9) e acrescenta a rastreabilidade
requisito → código → teste. `tests/test_traceability.py` garante que toda
referência de código e de teste citada aqui realmente existe.
"""

from __future__ import annotations

from dataclasses import dataclass

TITLE = "Mercado Fácil — Sistema de Caixa e Gestão de Vendas de Supermercado"
SUBTITLE = "Projeto da disciplina 2026.2 · Análise e Desenvolvimento de Sistemas · Engenharia de Software Ágil"
GROUP = "Grupo 4 — Thomaz, Victor, Lucas, Yago"

# --------------------------------------------------------------------------- 1. Visão geral
OVERVIEW = [
    (
        "Problema",
        "Registros dispersos de vendas e estoque dificultam a conferência de caixa, a reposição "
        "e a rastreabilidade.",
    ),
    (
        "Objetivo",
        "Centralizar a operação do supermercado, reduzir erros manuais e manter histórico confiável.",
    ),
    ("Público", "Operadores de caixa, estoquistas, gestores e clientes identificados por CPF."),
    (
        "Escopo",
        "PDV, pagamentos, troco, cashback, produtos, estoque, pós-venda, caixa e relatórios operacionais.",
    ),
    (
        "Entrega",
        "Aplicação web operacional, banco persistente, dados de demonstração e esta documentação.",
    ),
]

IDENTIFICATION = [
    (
        "Informações armazenadas",
        "Produtos, códigos de barras, categorias, preços, custos, quantidades, estoque mínimo, "
        "localização, clientes, CPF, cashback, vendas, itens, pagamentos, caixas e movimentações.",
    ),
    (
        "Atividades controladas",
        "Abertura e fechamento, registro e cancelamento de vendas, cancelamento de item, "
        "recebimentos, troco, entradas, saídas, devoluções, trocas e apuração de diferença.",
    ),
    ("Usuários", "Operador de caixa, estoquista, gestor e cliente identificado."),
]

SUCCESS_CRITERIA = (
    "O sistema é considerado adequado quando o operador conclui uma venda sem treinamento técnico, "
    "o estoque é atualizado automaticamente, regras críticas impedem inconsistências e o gestor "
    "consegue consultar a origem de cada alteração."
)

# --------------------------------------------------------------------- 2. Viabilidade
FEASIBILITY = [
    (
        "Técnica",
        "Interface web em Python e Streamlit, persistência relacional em SQL e regras executadas no servidor.",
        "Viável com tecnologias maduras e amplamente documentadas.",
    ),
    (
        "Econômica",
        "Protótipo de baixo custo. Necessita computador e leitor de código de barras; impressora e "
        "gaveta são opcionais. Custos reais dependem do ambiente.",
        "Viável para pequeno e médio varejo, com implantação incremental.",
    ),
    (
        "Operacional",
        "Navegação separada por tarefa, termos do cotidiano e mensagens claras. "
        "Treinamento estimado em até uma hora.",
        "Viável para funcionários com conhecimento básico de computador.",
    ),
]

RESOURCES = [
    ("Computador com navegador", "Obrigatório", "Pode reutilizar equipamento existente."),
    ("Leitor USB de código de barras", "Recomendado", "Funciona como entrada de teclado."),
    (
        "Gaveta, impressora térmica e balança",
        "Opcional",
        "Podem ser integradas em uma etapa futura.",
    ),
    (
        "Desenvolvimento e treinamento",
        "Obrigatório",
        "Maior parcela do investimento; varia conforme equipe e integrações.",
    ),
    ("Hospedagem e banco", "Obrigatório", "Custo recorrente proporcional ao uso."),
]

PROTECTION = (
    "Coletar apenas os dados necessários; o CPF é opcional e usado para identificação e cashback. "
    "No sistema, o cadastro do cliente guarda somente CPF e nome, e os comprovantes mascaram o CPF."
)

# ------------------------------------------------------------------- 3. Atores e funcionalidades
ACTORS = [
    (
        "Operador de caixa",
        "Abrir caixa; bipar ou buscar produtos; identificar cliente; receber; calcular troco; "
        "concluir venda; fechar caixa.",
    ),
    (
        "Estoquista",
        "Cadastrar produtos; definir localização; registrar entrada, saída, perda e ajuste; "
        "acompanhar estoque mínimo.",
    ),
    (
        "Gestor",
        "Consultar indicadores, vendas e movimentações; analisar diferenças; acompanhar e autorizar pós-venda.",
    ),
    (
        "Cliente",
        "Informar CPF opcionalmente; utilizar e acumular cashback; pagar; receber troco e comprovante.",
    ),
    (
        "Sistema de pagamento",
        "Representa a confirmação de Pix, débito ou crédito; no protótipo, a aprovação é simulada.",
    ),
]


# -------------------------------------------------------------------- Requisitos e rastreabilidade
@dataclass(frozen=True)
class Requirement:
    """Requisito ou regra, com onde foi implementado e quais testes o verificam."""

    id: str
    text: str
    code: tuple[str, ...]  # "arquivo.py:função"
    tests: tuple[str, ...]  # "tests/arquivo.py::teste"


CASH = "mercadofacil/services/cash_register.py"
CATALOG = "mercadofacil/services/catalog.py"
CUSTOMERS = "mercadofacil/services/customers.py"
PAYMENTS = "mercadofacil/services/payments.py"
POST_SALE = "mercadofacil/services/post_sale.py"
SALES = "mercadofacil/services/sales.py"
STOCK = "mercadofacil/services/stock.py"
UI = "mercadofacil/ui"

FUNCTIONAL: tuple[Requirement, ...] = (
    Requirement(
        "RF01",
        "Abrir o caixa com fundo inicial.",
        (f"{CASH}:open_register", f"{UI}/views/register.py:_open_panel"),
        (
            "tests/test_cash_register.py::test_abrir_caixa_com_fundo_inicial_rf01",
            "tests/test_cash_register.py::test_fundo_inicial_invalido",
        ),
    ),
    Requirement(
        "RF02",
        "Fechar o caixa com valor contado e diferença calculada.",
        (
            f"{CASH}:close_register",
            f"{CASH}:calculate_difference",
            f"{UI}/views/register.py:_close_panel",
        ),
        (
            "tests/test_cash_register.py::test_calcular_diferenca",
            "tests/test_casos_de_teste.py::test_ct12_fechar_com_contado_menor_que_o_esperado",
        ),
    ),
    Requirement(
        "RF03",
        "Ler código de barras ou localizar produto manualmente.",
        (
            f"{CATALOG}:find_by_barcode",
            f"{CATALOG}:search_products",
            f"{UI}/views/pos.py:_on_scan",
        ),
        (
            "tests/test_catalog.py::test_leitura_de_codigo_de_barras_rf03",
            "tests/test_catalog.py::test_busca_manual_ignora_acentos_e_caixa",
        ),
    ),
    Requirement(
        "RF04",
        "Adicionar, alterar quantidade e cancelar item no carrinho.",
        (
            f"{UI}/cart.py:add",
            f"{UI}/cart.py:set_quantity",
            f"{UI}/cart.py:remove",
            f"{SALES}:price_cart",
        ),
        (
            "tests/test_ui_cart_formatting.py::test_carrinho_adicionar_soma_quantidades",
            "tests/test_ui_cart_formatting.py::test_carrinho_alterar_e_remover",
            "tests/test_sales.py::test_precificar_carrinho_agrupa_linhas_repetidas",
        ),
    ),
    Requirement(
        "RF05",
        "Aceitar dinheiro, Pix, débito e crédito.",
        (
            f"{PAYMENTS}:validate_method",
            f"{PAYMENTS}:authorize_electronic_payment",
            f"{SALES}:finalize_sale",
        ),
        (
            "tests/test_sales.py::test_forma_de_pagamento_invalida",
            "tests/test_sales.py::test_pagamento_eletronico_recusado_nao_registra_a_venda",
        ),
    ),
    Requirement(
        "RF06",
        "Calcular troco automaticamente no pagamento em dinheiro.",
        (f"{PAYMENTS}:calculate_change", f"{UI}/views/pos.py:_payment_section"),
        (
            "tests/test_sales.py::test_venda_em_dinheiro_calcula_o_troco_rf06",
            "tests/test_casos_de_teste.py::test_ct06_receber_r50_em_venda_de_r32_50",
        ),
    ),
    Requirement(
        "RF07",
        "Identificar cliente pelo CPF e controlar cashback.",
        (
            f"{CUSTOMERS}:find_customer",
            f"{CUSTOMERS}:register_customer",
            f"{CUSTOMERS}:validate_cashback_use",
            f"{UI}/views/pos.py:_customer_panel",
        ),
        (
            "tests/test_sales.py::test_cadastro_minimo_de_cliente",
            "tests/test_sales.py::test_busca_de_cliente_por_cpf",
            "tests/test_sales.py::test_cliente_identificado_recebe_1_por_cento_rb07",
        ),
    ),
    Requirement(
        "RF08",
        "Cadastrar produto, preço, custo, unidade e localização.",
        (
            f"{CATALOG}:create_product",
            f"{CATALOG}:update_product",
            f"{UI}/views/products.py:_new_product_dialog",
        ),
        ("tests/test_catalog.py::test_cadastro_completo",),
    ),
    Requirement(
        "RF09",
        "Registrar entradas e saídas com motivo e referência.",
        (
            f"{STOCK}:register_movement",
            f"{STOCK}:adjust_stock",
            f"{UI}/views/products.py:_move_dialog",
        ),
        (
            "tests/test_stock.py::test_entrada_aumenta_o_saldo_e_registra_a_origem",
            "tests/test_stock.py::test_motivo_e_obrigatorio_rf09",
        ),
    ),
    Requirement(
        "RF10",
        "Exibir alerta de estoque mínimo.",
        (
            f"{STOCK}:products_to_restock",
            f"{UI}/views/products.py:_restock_alert",
            f"{UI}/views/overview.py:_restock_panel",
        ),
        (
            "tests/test_stock.py::test_alerta_de_reposicao_ordenado_por_urgencia",
            "tests/test_catalog.py::test_filtro_de_estoque_minimo_rf10",
        ),
    ),
    Requirement(
        "RF11",
        "Cancelar venda completa e devolver itens ao estoque.",
        (f"{POST_SALE}:cancel_sale", f"{UI}/views/sales.py:_cancel_sale_dialog"),
        (
            "tests/test_post_sale.py::test_cancelar_venda_devolve_itens_e_marca_cancelada_rf11",
            "tests/test_casos_de_teste.py::test_ct09_cancelar_venda_concluida",
        ),
    ),
    Requirement(
        "RF12",
        "Cancelar item de venda concluída.",
        (f"{POST_SALE}:cancel_item", f"{UI}/views/sales.py:_cancel_item_dialog"),
        ("tests/test_post_sale.py::test_cancelar_item_de_venda_concluida_rf12",),
    ),
    Requirement(
        "RF13",
        "Registrar devolução parcial.",
        (f"{POST_SALE}:return_item", f"{UI}/views/sales.py:_return_dialog"),
        ("tests/test_post_sale.py::test_devolucao_parcial_rf13",),
    ),
    Requirement(
        "RF14",
        "Registrar troca e movimentar os dois produtos.",
        (f"{POST_SALE}:exchange_item", f"{UI}/views/sales.py:_exchange_dialog"),
        ("tests/test_post_sale.py::test_troca_movimenta_os_dois_produtos_rf14",),
    ),
    Requirement(
        "RF15",
        "Consultar vendas, itens, pagamentos e ocorrências.",
        (
            f"{SALES}:list_sales",
            f"{SALES}:get_sale_detail",
            f"{POST_SALE}:list_operations",
            f"{UI}/views/sales.py:render",
        ),
        (
            "tests/test_sales.py::test_consulta_de_vendas_com_filtros_rf15",
            "tests/test_post_sale.py::test_ocorrencias_sao_listadas_e_nunca_apagadas_rb12",
        ),
    ),
    Requirement(
        "RF16",
        "Consultar histórico de movimentações.",
        (f"{STOCK}:list_movements", f"{UI}/views/movements.py:render"),
        ("tests/test_stock.py::test_historico_filtra_por_tipo_produto_texto_e_data",),
    ),
)

NON_FUNCTIONAL: tuple[Requirement, ...] = (
    Requirement(
        "RNF01",
        "Interface responsiva, objetiva e de fácil aprendizagem.",
        (f"{UI}/theme.py:build_css", f"{UI}/shell.py:main", f"{UI}/navigation.py:visible_pages"),
        (
            "tests/test_ui_theme.py::test_pares_de_texto_tem_contraste_minimo_wcag_aa",
            "tests/test_ui_navigation.py::test_cada_perfil_ve_somente_as_suas_telas",
        ),
    ),
    Requirement(
        "RNF02",
        "Persistência relacional para dados que devem sobreviver a sessões.",
        ("mercadofacil/database.py:init_schema", "mercadofacil/bootstrap.py:initialize"),
        (
            "tests/test_schema_seed.py::test_esquema_e_idempotente_e_versionado",
            "tests/test_schema_seed.py::test_bootstrap_cria_banco_com_demonstracao_uma_unica_vez",
        ),
    ),
    Requirement(
        "RNF03",
        "Validação das regras críticas no servidor.",
        (f"{SALES}:finalize_sale", f"{POST_SALE}:exchange_item", f"{STOCK}:apply_movement"),
        (
            "tests/test_sales.py::test_venda_exige_caixa_aberto_rb01",
            "tests/test_auth_permissions.py::test_servidor_barra_acao_fora_do_perfil",
        ),
    ),
    Requirement(
        "RNF04",
        "Rastreabilidade de movimentações por data, operador, motivo e referência.",
        (f"{STOCK}:apply_movement", f"{STOCK}:list_movements"),
        (
            "tests/test_sales.py::test_venda_baixa_estoque_com_movimentacao_referenciada",
            "tests/test_stock.py::test_entrada_aumenta_o_saldo_e_registra_a_origem",
        ),
    ),
    Requirement(
        "RNF05",
        "Separação entre interface, regras de negócio e acesso a dados.",
        (
            f"{UI}/shell.py:main",
            "mercadofacil/services/sales.py:finalize_sale",
            "mercadofacil/repositories/sales.py:insert_sale",
        ),
        ("tests/test_architecture.py::test_camadas_respeitam_a_direcao_das_dependencias",),
    ),
    Requirement(
        "RNF06",
        "Mensagens de erro claras, estados vazios e confirmações visuais.",
        (
            f"{UI}/components.py:alert",
            f"{UI}/components.py:run_action",
            f"{UI}/components.py:empty_state",
        ),
        (
            "tests/test_ui_components.py::test_erros_de_regra_aparecem_como_alerta_claro",
            "tests/test_ui_components.py::test_tabela_vazia_mostra_estado_vazio",
        ),
    ),
    Requirement(
        "RNF07",
        "Navegação por teclado e controles adequados para toque.",
        (f"{UI}/theme.py:build_css", f"{UI}/compat.py:focus_input"),
        ("tests/test_ui_theme.py::test_css_garante_alvo_de_toque_e_foco_visivel",),
    ),
    Requirement(
        "RNF08",
        "Acesso protegido e permissões compatíveis com a função.",
        (
            "mercadofacil/services/auth.py:authenticate",
            "mercadofacil/services/permissions.py:can",
            f"{UI}/views/login.py:render",
        ),
        (
            "tests/test_auth_permissions.py::test_senha_nunca_fica_em_texto_puro",
            "tests/test_auth_permissions.py::test_matriz_de_permissoes",
        ),
    ),
    Requirement(
        "RNF09",
        "Código com nomes significativos e funções de responsabilidade específica.",
        ("pyproject.toml:ruff", "scripts/check.py:main"),
        ("tests/test_architecture.py::test_nenhuma_funcao_de_servico_importa_a_interface",),
    ),
    Requirement(
        "RNF10",
        "Backup e recuperação definidos antes do uso comercial.",
        (
            "mercadofacil/services/backup.py:backup_bytes",
            "mercadofacil/services/backup.py:backup_to_file",
            f"{UI}/views/project.py:_backup_tab",
        ),
        (
            "tests/test_reports_backup_receipts.py::test_backup_gera_copia_consistente_e_restauravel",
        ),
    ),
    Requirement(
        "RNF11",
        "Emitir NF (por enquanto).",
        ("mercadofacil/services/receipts.py:build_receipt",),
        (
            "tests/test_reports_backup_receipts.py::"
            "test_comprovante_em_dinheiro_mostra_total_troco_e_cashback",
        ),
    ),
)

BUSINESS_RULES: tuple[Requirement, ...] = (
    Requirement(
        "RB01",
        "Uma venda somente pode ser concluída com caixa aberto.",
        (f"{SALES}:finalize_sale", f"{CASH}:require_open_register"),
        (
            "tests/test_sales.py::test_venda_exige_caixa_aberto_rb01",
            "tests/test_casos_de_teste.py::test_ct04_finalizar_venda_com_caixa_fechado",
        ),
    ),
    Requirement(
        "RB02",
        "Dois produtos ativos não podem ter o mesmo código de barras.",
        (f"{CATALOG}:create_product", "mercadofacil/database.py:init_schema"),
        (
            "tests/test_catalog.py::test_codigo_de_barras_duplicado_e_bloqueado_rb02",
            "tests/test_casos_de_teste.py::test_ct01_cadastrar_barcode_ativo_duplicado",
        ),
    ),
    Requirement(
        "RB03",
        "O estoque não pode ficar negativo.",
        (f"{STOCK}:apply_movement", f"{SALES}:price_cart"),
        (
            "tests/test_stock.py::test_saida_maior_que_o_saldo_e_bloqueada_rb03",
            "tests/test_casos_de_teste.py::test_ct03_registrar_saida_maior_que_o_saldo",
            "tests/test_casos_de_teste.py::test_ct08_vender_quantidade_maior_que_o_estoque",
        ),
    ),
    Requirement(
        "RB04",
        "O valor recebido em dinheiro não pode ser menor que o total.",
        (f"{PAYMENTS}:calculate_change",),
        (
            "tests/test_sales.py::test_valor_recebido_menor_que_o_total_e_bloqueado_rb04",
            "tests/test_casos_de_teste.py::test_ct05_receber_r30_em_venda_de_r50",
        ),
    ),
    Requirement(
        "RB05",
        "Troco somente é calculado para dinheiro.",
        (f"{PAYMENTS}:calculate_change",),
        ("tests/test_sales.py::test_troco_so_existe_para_dinheiro_rb05",),
    ),
    Requirement(
        "RB06",
        "Cashback utilizado não pode superar saldo ou valor da compra.",
        (f"{CUSTOMERS}:validate_cashback_use", f"{CUSTOMERS}:max_usable_cashback"),
        (
            "tests/test_sales.py::test_cashback_maior_que_o_saldo_e_bloqueado_rb06",
            "tests/test_casos_de_teste.py::test_ct07_utilizar_cashback_maior_que_o_saldo",
        ),
    ),
    Requirement(
        "RB07",
        "Cliente identificado recebe 1% de cashback sobre o total líquido.",
        (f"{CUSTOMERS}:calculate_cashback_earned",),
        (
            "tests/test_sales.py::test_cliente_identificado_recebe_1_por_cento_rb07",
            "tests/test_sales.py::test_cashback_e_calculado_sobre_o_total_liquido",
        ),
    ),
    Requirement(
        "RB08",
        "Cancelamento devolve ao estoque somente a quantidade ainda ativa.",
        (f"{POST_SALE}:cancel_sale", f"{POST_SALE}:cancel_item"),
        (
            "tests/test_post_sale.py::test_cancelamento_devolve_somente_a_quantidade_ainda_ativa_rb08",
        ),
    ),
    Requirement(
        "RB09",
        "Devolução não pode superar a quantidade disponível do item.",
        (f"{POST_SALE}:return_item",),
        (
            "tests/test_post_sale.py::test_devolucao_maior_que_o_disponivel_e_bloqueada_rb09",
            "tests/test_casos_de_teste.py::test_ct10_devolver_mais_itens_que_o_disponivel",
        ),
    ),
    Requirement(
        "RB10",
        "Troca exige saldo do produto substituto.",
        (f"{POST_SALE}:exchange_item",),
        (
            "tests/test_post_sale.py::test_troca_por_produto_sem_saldo_e_bloqueada_rb10",
            "tests/test_casos_de_teste.py::test_ct11_trocar_por_produto_sem_estoque",
        ),
    ),
    Requirement(
        "RB11",
        "Fechamento registra valor esperado, contado e diferença.",
        (f"{CASH}:close_register", f"{CASH}:summarize"),
        (
            "tests/test_cash_register.py::test_fechar_sem_diferenca_rb11",
            "tests/test_cash_register.py::test_falta_e_sobra_ficam_registradas_com_sinal",
        ),
    ),
    Requirement(
        "RB12",
        "Históricos não são apagados; o status representa o resultado.",
        ("mercadofacil/database.py:init_schema", f"{POST_SALE}:recompute_status"),
        (
            "tests/test_schema_seed.py::test_historico_nunca_e_apagado_rb12",
            "tests/test_post_sale.py::test_status_da_venda_representa_o_resultado",
        ),
    ),
)

ALL_REQUIREMENTS: tuple[Requirement, ...] = FUNCTIONAL + NON_FUNCTIONAL + BUSINESS_RULES

# ------------------------------------------------------------------- 6. Modelo de dados
DATA_MODEL = [
    (
        "products",
        "Catálogo e saldo atual",
        "barcode, name, price_cents, stock, min_stock, location, active",
    ),
    ("customers", "Identificação e cashback", "cpf, name, cashback_cents"),
    ("registers", "Turnos de caixa", "status, opening, expected, counted, difference"),
    ("sales", "Cabeçalho da venda", "customer_cpf, total, payment_method, change, status"),
    (
        "sale_items",
        "Produtos vendidos",
        "product_id, quantity, unit_price, cancelled_qty, returned_qty",
    ),
    (
        "stock_movements",
        "Rastreabilidade",
        "type, quantity, balance_after, reason, reference, operator",
    ),
    (
        "post_sale_operations",
        "Ocorrências",
        "type, product, replacement, quantity, amount, notes",
    ),
]
DATA_MODEL_EXTRA = (
    "Além das tabelas do documento, o sistema usa `users` (acesso protegido, RNF08) e `payments` "
    "(classe Pagamento do diagrama de classes, 5.2)."
)

IMPLEMENTATION_DECISIONS = [
    "Valores monetários são armazenados em centavos inteiros para evitar erro de ponto flutuante.",
    "O código de barras é validado após o cadastro do produto e possui índice de unicidade "
    "combinado com o status ativo.",
    "Venda e movimentações são registradas juntas; assim, o saldo exibido acompanha a operação comercial.",
    "Dados iniciais de demonstração são inseridos somente quando a base está vazia.",
    "A interface usa componentes reutilizáveis para diálogos, tabelas, seletores, alertas e navegação lateral.",
]

# ------------------------------------------------------------------- 7. Telas e usabilidade
SCREEN_CONTROLS = {
    "overview": "Indicadores, vendas recentes e alertas de reposição",
    "pos": "Busca/barcode, grade de produtos, carrinho, CPF, cashback, pagamento e troco",
    "products": "Cadastro, busca, localização, quantidade mínima e movimentação",
    "sales": "Detalhe da venda, cancelamento, devolução e troca",
    "register": "Fundo inicial, esperado, contado, diferença e histórico",
    "movements": "Filtros de entrada/saída, motivo, saldo e referência",
    "project": "Manual, requisitos, modelagem e casos de teste",
}

USABILITY = [
    "A tarefa principal aparece antes de conteúdo explicativo.",
    "Cores informam estados: verde para concluído/entrada, amarelo para atenção e vermelho para "
    "cancelamento/erro.",
    "O operador recebe mensagens imediatas após cada ação.",
    "Tabelas mantêm cabeçalhos claros e permitem leitura horizontal em telas pequenas.",
    "O PDV preserva o resumo da venda e mostra total e troco com destaque.",
]


# --------------------------------------------------------------------- 8. Casos de teste
@dataclass(frozen=True)
class Scenario:
    id: str
    scenario: str
    expected: str
    test: str  # função em tests/test_casos_de_teste.py


TEST_CASES: tuple[Scenario, ...] = (
    Scenario(
        "CT01",
        "Cadastrar barcode ativo duplicado",
        "Cadastro bloqueado e mensagem clara",
        "test_ct01_cadastrar_barcode_ativo_duplicado",
    ),
    Scenario(
        "CT02",
        "Cadastrar com campo obrigatório vazio",
        "Requisição rejeitada",
        "test_ct02_cadastrar_com_campo_obrigatorio_vazio",
    ),
    Scenario(
        "CT03",
        "Registrar saída maior que o saldo",
        "Estoque negativo impedido",
        "test_ct03_registrar_saida_maior_que_o_saldo",
    ),
    Scenario(
        "CT04",
        "Finalizar venda com caixa fechado",
        "Venda não autorizada",
        "test_ct04_finalizar_venda_com_caixa_fechado",
    ),
    Scenario(
        "CT05",
        "Receber R$ 30,00 em venda de R$ 50,00",
        "Pagamento bloqueado",
        "test_ct05_receber_r30_em_venda_de_r50",
    ),
    Scenario(
        "CT06",
        "Receber R$ 50,00 em venda de R$ 32,50",
        "Troco calculado em R$ 17,50",
        "test_ct06_receber_r50_em_venda_de_r32_50",
    ),
    Scenario(
        "CT07",
        "Utilizar cashback maior que o saldo",
        "Uso bloqueado",
        "test_ct07_utilizar_cashback_maior_que_o_saldo",
    ),
    Scenario(
        "CT08",
        "Vender quantidade maior que estoque",
        "Venda bloqueada",
        "test_ct08_vender_quantidade_maior_que_o_estoque",
    ),
    Scenario(
        "CT09",
        "Cancelar venda concluída",
        "Itens retornam e venda fica cancelada",
        "test_ct09_cancelar_venda_concluida",
    ),
    Scenario(
        "CT10",
        "Devolver mais itens que o disponível",
        "Operação bloqueada",
        "test_ct10_devolver_mais_itens_que_o_disponivel",
    ),
    Scenario(
        "CT11",
        "Trocar por produto sem estoque",
        "Troca bloqueada",
        "test_ct11_trocar_por_produto_sem_estoque",
    ),
    Scenario(
        "CT12",
        "Fechar com contado menor que o esperado",
        "Falta registrada com valor",
        "test_ct12_fechar_com_contado_menor_que_o_esperado",
    ),
)
CT_TEST_FILE = "tests/test_casos_de_teste.py"

AUTOMATED_TESTS = (
    "O código inclui testes unitários para cálculo de troco, pagamento insuficiente, entrada e "
    "saída de estoque, bloqueio de saldo negativo, código de barras duplicado, cashback e diferença "
    "de fechamento. O processo de entrega também executa validação de tipos, lint e compilação de "
    "produção (`python scripts/check.py`)."
)

# ----------------------------------------------------------------- 9. Manual operacional
MANUAL = [
    (
        "Abrir",
        "Acesse Abertura e fechamento, clique em Abrir caixa e informe o fundo.",
        "Status do cabeçalho deve mostrar Caixa aberto.",
    ),
    (
        "Vender",
        "No PDV, bipe ou busque produtos e ajuste quantidades no carrinho.",
        "Confira itens, subtotal e saldo disponível.",
    ),
    (
        "Identificar",
        "Informe CPF quando o cliente desejar usar ou acumular cashback.",
        "Nome e saldo devem aparecer na tela.",
    ),
    (
        "Receber",
        "Selecione a forma. Em dinheiro, informe o valor recebido.",
        "Troco é mostrado automaticamente.",
    ),
    (
        "Finalizar",
        "Clique em Finalizar venda e aguarde a confirmação.",
        "Comprovante exibe ID, total, troco e cashback.",
    ),
    (
        "Repor",
        "Em Produtos e estoque, abra Movimentar e registre entrada com motivo.",
        "Novo saldo aparece na tabela e no histórico.",
    ),
    (
        "Pós-venda",
        "Abra a venda e escolha cancelar item, devolver, trocar ou cancelar tudo.",
        "A venda mostra o novo status e a ocorrência aparece no histórico.",
    ),
    (
        "Fechar",
        "Conte a gaveta, informe o valor e confirme o fechamento.",
        "Sistema registra esperado, contado e diferença.",
    ),
]

TRAINING = (
    "Realizar uma sessão de até uma hora com simulação completa: abrir caixa, registrar uma venda "
    "em dinheiro, usar CPF, cancelar um item, registrar entrada de mercadoria e fechar o turno. "
    "O gestor deve complementar o treinamento com as políticas reais do estabelecimento."
)

LIMITS = (
    "A aprovação de cartões e Pix é simulada; emissão fiscal, impressora, balança, TEF, "
    "fornecedores, compras e perfis detalhados de permissão não fazem parte do escopo atual. "
    "Esses recursos exigem integrações e homologações específicas antes do uso comercial."
)

BACKUP_STEPS = [
    "Como gestor, baixe a cópia do banco (arquivo .db) na aba “Backup e recuperação”, "
    "ao fim de cada dia ou antes de qualquer atualização.",
    "Guarde a cópia fora do computador do caixa (pendrive, nuvem ou outro servidor).",
    "Para recuperar: feche o sistema, substitua o arquivo data/mercado_facil.db pela cópia "
    "(ou aponte MERCADO_FACIL_DB para ela) e inicie o sistema novamente.",
    "Teste a recuperação periodicamente em outro computador: backup nunca testado não é backup.",
]
