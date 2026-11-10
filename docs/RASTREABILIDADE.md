# Rastreabilidade — Mercado Fácil

> Arquivo gerado por `python scripts/gen_traceability.py`; não edite à mão.
> `tests/test_traceability.py` confere que cada função e cada teste citado existe.

## Requisitos funcionais (RF01–RF16)

| ID | Requisito | Implementado em | Verificado por |
|----|-----------|-----------------|----------------|
| RF01 | Abrir o caixa com fundo inicial. | `mercadofacil/services/cash_register.py:open_register`<br>`mercadofacil/ui/views/register.py:_open_panel` | `tests/test_cash_register.py::test_abrir_caixa_com_fundo_inicial_rf01`<br>`tests/test_cash_register.py::test_fundo_inicial_invalido` |
| RF02 | Fechar o caixa com valor contado e diferença calculada. | `mercadofacil/services/cash_register.py:close_register`<br>`mercadofacil/services/cash_register.py:calculate_difference`<br>`mercadofacil/ui/views/register.py:_close_panel` | `tests/test_cash_register.py::test_calcular_diferenca`<br>`tests/test_casos_de_teste.py::test_ct12_fechar_com_contado_menor_que_o_esperado` |
| RF03 | Ler código de barras ou localizar produto manualmente. | `mercadofacil/services/catalog.py:find_by_barcode`<br>`mercadofacil/services/catalog.py:search_products`<br>`mercadofacil/ui/views/pos.py:_on_scan` | `tests/test_catalog.py::test_leitura_de_codigo_de_barras_rf03`<br>`tests/test_catalog.py::test_busca_manual_ignora_acentos_e_caixa` |
| RF04 | Adicionar, alterar quantidade e cancelar item no carrinho. | `mercadofacil/ui/cart.py:add`<br>`mercadofacil/ui/cart.py:set_quantity`<br>`mercadofacil/ui/cart.py:remove`<br>`mercadofacil/services/sales.py:price_cart` | `tests/test_ui_cart_formatting.py::test_carrinho_adicionar_soma_quantidades`<br>`tests/test_ui_cart_formatting.py::test_carrinho_alterar_e_remover`<br>`tests/test_sales.py::test_precificar_carrinho_agrupa_linhas_repetidas` |
| RF05 | Aceitar dinheiro, Pix, débito e crédito. | `mercadofacil/services/payments.py:validate_method`<br>`mercadofacil/services/payments.py:authorize_electronic_payment`<br>`mercadofacil/services/sales.py:finalize_sale` | `tests/test_sales.py::test_forma_de_pagamento_invalida`<br>`tests/test_sales.py::test_pagamento_eletronico_recusado_nao_registra_a_venda` |
| RF06 | Calcular troco automaticamente no pagamento em dinheiro. | `mercadofacil/services/payments.py:calculate_change`<br>`mercadofacil/ui/views/pos.py:_payment_section` | `tests/test_sales.py::test_venda_em_dinheiro_calcula_o_troco_rf06`<br>`tests/test_casos_de_teste.py::test_ct06_receber_r50_em_venda_de_r32_50` |
| RF07 | Identificar cliente pelo CPF e controlar cashback. | `mercadofacil/services/customers.py:find_customer`<br>`mercadofacil/services/customers.py:register_customer`<br>`mercadofacil/services/customers.py:validate_cashback_use`<br>`mercadofacil/ui/views/pos.py:_customer_panel` | `tests/test_sales.py::test_cadastro_minimo_de_cliente`<br>`tests/test_sales.py::test_busca_de_cliente_por_cpf`<br>`tests/test_sales.py::test_cliente_identificado_recebe_1_por_cento_rb07` |
| RF08 | Cadastrar produto, preço, custo, unidade e localização. | `mercadofacil/services/catalog.py:create_product`<br>`mercadofacil/services/catalog.py:update_product`<br>`mercadofacil/ui/views/products.py:_new_product_dialog` | `tests/test_catalog.py::test_cadastro_completo` |
| RF09 | Registrar entradas e saídas com motivo e referência. | `mercadofacil/services/stock.py:register_movement`<br>`mercadofacil/services/stock.py:adjust_stock`<br>`mercadofacil/ui/views/products.py:_move_dialog` | `tests/test_stock.py::test_entrada_aumenta_o_saldo_e_registra_a_origem`<br>`tests/test_stock.py::test_motivo_e_obrigatorio_rf09` |
| RF10 | Exibir alerta de estoque mínimo. | `mercadofacil/services/stock.py:products_to_restock`<br>`mercadofacil/ui/views/products.py:_restock_alert`<br>`mercadofacil/ui/views/overview.py:_restock_panel` | `tests/test_stock.py::test_alerta_de_reposicao_ordenado_por_urgencia`<br>`tests/test_catalog.py::test_filtro_de_estoque_minimo_rf10` |
| RF11 | Cancelar venda completa e devolver itens ao estoque. | `mercadofacil/services/post_sale.py:cancel_sale`<br>`mercadofacil/ui/views/sales.py:_cancel_sale_dialog` | `tests/test_post_sale.py::test_cancelar_venda_devolve_itens_e_marca_cancelada_rf11`<br>`tests/test_casos_de_teste.py::test_ct09_cancelar_venda_concluida` |
| RF12 | Cancelar item de venda concluída. | `mercadofacil/services/post_sale.py:cancel_item`<br>`mercadofacil/ui/views/sales.py:_cancel_item_dialog` | `tests/test_post_sale.py::test_cancelar_item_de_venda_concluida_rf12` |
| RF13 | Registrar devolução parcial. | `mercadofacil/services/post_sale.py:return_item`<br>`mercadofacil/ui/views/sales.py:_return_dialog` | `tests/test_post_sale.py::test_devolucao_parcial_rf13` |
| RF14 | Registrar troca e movimentar os dois produtos. | `mercadofacil/services/post_sale.py:exchange_item`<br>`mercadofacil/ui/views/sales.py:_exchange_dialog` | `tests/test_post_sale.py::test_troca_movimenta_os_dois_produtos_rf14` |
| RF15 | Consultar vendas, itens, pagamentos e ocorrências. | `mercadofacil/services/sales.py:list_sales`<br>`mercadofacil/services/sales.py:get_sale_detail`<br>`mercadofacil/services/post_sale.py:list_operations`<br>`mercadofacil/ui/views/sales.py:render` | `tests/test_sales.py::test_consulta_de_vendas_com_filtros_rf15`<br>`tests/test_post_sale.py::test_ocorrencias_sao_listadas_e_nunca_apagadas_rb12` |
| RF16 | Consultar histórico de movimentações. | `mercadofacil/services/stock.py:list_movements`<br>`mercadofacil/ui/views/movements.py:render` | `tests/test_stock.py::test_historico_filtra_por_tipo_produto_texto_e_data` |

## Requisitos não funcionais (RNF01–RNF11)

| ID | Requisito | Implementado em | Verificado por |
|----|-----------|-----------------|----------------|
| RNF01 | Interface responsiva, objetiva e de fácil aprendizagem. | `mercadofacil/ui/theme.py:build_css`<br>`mercadofacil/ui/shell.py:main`<br>`mercadofacil/ui/navigation.py:visible_pages` | `tests/test_ui_theme.py::test_pares_de_texto_tem_contraste_minimo_wcag_aa`<br>`tests/test_ui_navigation.py::test_cada_perfil_ve_somente_as_suas_telas` |
| RNF02 | Persistência relacional para dados que devem sobreviver a sessões. | `mercadofacil/database.py:init_schema`<br>`mercadofacil/bootstrap.py:initialize` | `tests/test_schema_seed.py::test_esquema_e_idempotente_e_versionado`<br>`tests/test_schema_seed.py::test_bootstrap_cria_banco_com_demonstracao_uma_unica_vez` |
| RNF03 | Validação das regras críticas no servidor. | `mercadofacil/services/sales.py:finalize_sale`<br>`mercadofacil/services/post_sale.py:exchange_item`<br>`mercadofacil/services/stock.py:apply_movement` | `tests/test_sales.py::test_venda_exige_caixa_aberto_rb01`<br>`tests/test_auth_permissions.py::test_servidor_barra_acao_fora_do_perfil` |
| RNF04 | Rastreabilidade de movimentações por data, operador, motivo e referência. | `mercadofacil/services/stock.py:apply_movement`<br>`mercadofacil/services/stock.py:list_movements` | `tests/test_sales.py::test_venda_baixa_estoque_com_movimentacao_referenciada`<br>`tests/test_stock.py::test_entrada_aumenta_o_saldo_e_registra_a_origem` |
| RNF05 | Separação entre interface, regras de negócio e acesso a dados. | `mercadofacil/ui/shell.py:main`<br>`mercadofacil/services/sales.py:finalize_sale`<br>`mercadofacil/repositories/sales.py:insert_sale` | `tests/test_architecture.py::test_camadas_respeitam_a_direcao_das_dependencias` |
| RNF06 | Mensagens de erro claras, estados vazios e confirmações visuais. | `mercadofacil/ui/components.py:alert`<br>`mercadofacil/ui/components.py:run_action`<br>`mercadofacil/ui/components.py:empty_state` | `tests/test_ui_components.py::test_erros_de_regra_aparecem_como_alerta_claro`<br>`tests/test_ui_components.py::test_tabela_vazia_mostra_estado_vazio` |
| RNF07 | Navegação por teclado e controles adequados para toque. | `mercadofacil/ui/theme.py:build_css`<br>`mercadofacil/ui/compat.py:focus_input` | `tests/test_ui_theme.py::test_css_garante_alvo_de_toque_e_foco_visivel` |
| RNF08 | Acesso protegido e permissões compatíveis com a função. | `mercadofacil/services/auth.py:authenticate`<br>`mercadofacil/services/permissions.py:can`<br>`mercadofacil/ui/views/login.py:render` | `tests/test_auth_permissions.py::test_senha_nunca_fica_em_texto_puro`<br>`tests/test_auth_permissions.py::test_matriz_de_permissoes` |
| RNF09 | Código com nomes significativos e funções de responsabilidade específica. | `pyproject.toml:ruff`<br>`scripts/check.py:main` | `tests/test_architecture.py::test_nenhuma_funcao_de_servico_importa_a_interface` |
| RNF10 | Backup e recuperação definidos antes do uso comercial. | `mercadofacil/services/backup.py:backup_bytes`<br>`mercadofacil/services/backup.py:backup_to_file`<br>`mercadofacil/ui/views/project.py:_backup_tab` | `tests/test_reports_backup_receipts.py::test_backup_gera_copia_consistente_e_restauravel` |
| RNF11 | Emitir NF (por enquanto). | `mercadofacil/services/receipts.py:build_receipt` | `tests/test_reports_backup_receipts.py::test_comprovante_em_dinheiro_mostra_total_troco_e_cashback` |

## Regras de negócio (RB01–RB12)

| ID | Requisito | Implementado em | Verificado por |
|----|-----------|-----------------|----------------|
| RB01 | Uma venda somente pode ser concluída com caixa aberto. | `mercadofacil/services/sales.py:finalize_sale`<br>`mercadofacil/services/cash_register.py:require_open_register` | `tests/test_sales.py::test_venda_exige_caixa_aberto_rb01`<br>`tests/test_casos_de_teste.py::test_ct04_finalizar_venda_com_caixa_fechado` |
| RB02 | Dois produtos ativos não podem ter o mesmo código de barras. | `mercadofacil/services/catalog.py:create_product`<br>`mercadofacil/database.py:init_schema` | `tests/test_catalog.py::test_codigo_de_barras_duplicado_e_bloqueado_rb02`<br>`tests/test_casos_de_teste.py::test_ct01_cadastrar_barcode_ativo_duplicado` |
| RB03 | O estoque não pode ficar negativo. | `mercadofacil/services/stock.py:apply_movement`<br>`mercadofacil/services/sales.py:price_cart` | `tests/test_stock.py::test_saida_maior_que_o_saldo_e_bloqueada_rb03`<br>`tests/test_casos_de_teste.py::test_ct03_registrar_saida_maior_que_o_saldo`<br>`tests/test_casos_de_teste.py::test_ct08_vender_quantidade_maior_que_o_estoque` |
| RB04 | O valor recebido em dinheiro não pode ser menor que o total. | `mercadofacil/services/payments.py:calculate_change` | `tests/test_sales.py::test_valor_recebido_menor_que_o_total_e_bloqueado_rb04`<br>`tests/test_casos_de_teste.py::test_ct05_receber_r30_em_venda_de_r50` |
| RB05 | Troco somente é calculado para dinheiro. | `mercadofacil/services/payments.py:calculate_change` | `tests/test_sales.py::test_troco_so_existe_para_dinheiro_rb05` |
| RB06 | Cashback utilizado não pode superar saldo ou valor da compra. | `mercadofacil/services/customers.py:validate_cashback_use`<br>`mercadofacil/services/customers.py:max_usable_cashback` | `tests/test_sales.py::test_cashback_maior_que_o_saldo_e_bloqueado_rb06`<br>`tests/test_casos_de_teste.py::test_ct07_utilizar_cashback_maior_que_o_saldo` |
| RB07 | Cliente identificado recebe 1% de cashback sobre o total líquido. | `mercadofacil/services/customers.py:calculate_cashback_earned` | `tests/test_sales.py::test_cliente_identificado_recebe_1_por_cento_rb07`<br>`tests/test_sales.py::test_cashback_e_calculado_sobre_o_total_liquido` |
| RB08 | Cancelamento devolve ao estoque somente a quantidade ainda ativa. | `mercadofacil/services/post_sale.py:cancel_sale`<br>`mercadofacil/services/post_sale.py:cancel_item` | `tests/test_post_sale.py::test_cancelamento_devolve_somente_a_quantidade_ainda_ativa_rb08` |
| RB09 | Devolução não pode superar a quantidade disponível do item. | `mercadofacil/services/post_sale.py:return_item` | `tests/test_post_sale.py::test_devolucao_maior_que_o_disponivel_e_bloqueada_rb09`<br>`tests/test_casos_de_teste.py::test_ct10_devolver_mais_itens_que_o_disponivel` |
| RB10 | Troca exige saldo do produto substituto. | `mercadofacil/services/post_sale.py:exchange_item` | `tests/test_post_sale.py::test_troca_por_produto_sem_saldo_e_bloqueada_rb10`<br>`tests/test_casos_de_teste.py::test_ct11_trocar_por_produto_sem_estoque` |
| RB11 | Fechamento registra valor esperado, contado e diferença. | `mercadofacil/services/cash_register.py:close_register`<br>`mercadofacil/services/cash_register.py:summarize` | `tests/test_cash_register.py::test_fechar_sem_diferenca_rb11`<br>`tests/test_cash_register.py::test_falta_e_sobra_ficam_registradas_com_sinal` |
| RB12 | Históricos não são apagados; o status representa o resultado. | `mercadofacil/database.py:init_schema`<br>`mercadofacil/services/post_sale.py:recompute_status` | `tests/test_schema_seed.py::test_historico_nunca_e_apagado_rb12`<br>`tests/test_post_sale.py::test_status_da_venda_representa_o_resultado` |

## Casos de teste (seção 8)

| ID | Cenário | Resultado esperado | Teste automatizado |
|----|---------|--------------------|--------------------|
| CT01 | Cadastrar barcode ativo duplicado | Cadastro bloqueado e mensagem clara | `tests/test_casos_de_teste.py::test_ct01_cadastrar_barcode_ativo_duplicado` |
| CT02 | Cadastrar com campo obrigatório vazio | Requisição rejeitada | `tests/test_casos_de_teste.py::test_ct02_cadastrar_com_campo_obrigatorio_vazio` |
| CT03 | Registrar saída maior que o saldo | Estoque negativo impedido | `tests/test_casos_de_teste.py::test_ct03_registrar_saida_maior_que_o_saldo` |
| CT04 | Finalizar venda com caixa fechado | Venda não autorizada | `tests/test_casos_de_teste.py::test_ct04_finalizar_venda_com_caixa_fechado` |
| CT05 | Receber R$ 30,00 em venda de R$ 50,00 | Pagamento bloqueado | `tests/test_casos_de_teste.py::test_ct05_receber_r30_em_venda_de_r50` |
| CT06 | Receber R$ 50,00 em venda de R$ 32,50 | Troco calculado em R$ 17,50 | `tests/test_casos_de_teste.py::test_ct06_receber_r50_em_venda_de_r32_50` |
| CT07 | Utilizar cashback maior que o saldo | Uso bloqueado | `tests/test_casos_de_teste.py::test_ct07_utilizar_cashback_maior_que_o_saldo` |
| CT08 | Vender quantidade maior que estoque | Venda bloqueada | `tests/test_casos_de_teste.py::test_ct08_vender_quantidade_maior_que_o_estoque` |
| CT09 | Cancelar venda concluída | Itens retornam e venda fica cancelada | `tests/test_casos_de_teste.py::test_ct09_cancelar_venda_concluida` |
| CT10 | Devolver mais itens que o disponível | Operação bloqueada | `tests/test_casos_de_teste.py::test_ct10_devolver_mais_itens_que_o_disponivel` |
| CT11 | Trocar por produto sem estoque | Troca bloqueada | `tests/test_casos_de_teste.py::test_ct11_trocar_por_produto_sem_estoque` |
| CT12 | Fechar com contado menor que o esperado | Falta registrada com valor | `tests/test_casos_de_teste.py::test_ct12_fechar_com_contado_menor_que_o_esperado` |
