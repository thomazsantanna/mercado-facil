# Mercado Fácil — Sistema de Caixa e Gestão de Vendas de Supermercado

Projeto da disciplina 2026.2 · Análise e Desenvolvimento de Sistemas · Engenharia de Software Ágil
**Grupo 4 — Thomaz, Victor, Lucas, Yago**

Implementação completa do sistema descrito na documentação do projeto: frente de caixa (PDV),
cadastro de produtos, movimentações de estoque, histórico de vendas com cancelamento, devolução e
troca, abertura e fechamento de caixa, cashback e painel de indicadores.

Stack: **Python + Streamlit + SQLite** (banco relacional), com as regras de negócio validadas no
servidor (camada de serviços), nunca apenas na tela.

## Como executar

Requer Python 3.10 ou superior.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py               # sempre a partir da pasta raiz do projeto
```

**No Windows**, basta dar duplo clique em `iniciar_mercado_facil.bat`: ele cria o ambiente virtual,
instala as dependências e abre o sistema no navegador.

Na primeira execução o banco (`data/mercado_facil.db`) é criado sozinho, com produtos, clientes e
três usuários de demonstração:

| Perfil     | Usuário      | Senha          |
|------------|--------------|----------------|
| Gestor     | `gestor`     | `gestor123`    |
| Operador   | `operador`   | `operador123`  |
| Estoquista | `estoquista` | `estoque123`   |

### Variáveis de ambiente (opcionais)

| Variável                       | Efeito                                                           | Padrão                    |
|--------------------------------|------------------------------------------------------------------|---------------------------|
| `MERCADO_FACIL_DB`             | Caminho do arquivo SQLite                                        | `data/mercado_facil.db`   |
| `MERCADO_FACIL_SEED`           | `0` = só cria os 3 usuários, sem produtos/clientes de exemplo    | `1`                       |
| `MERCADO_FACIL_SHOW_DEMO_USERS`| `0` = esconde as credenciais de demonstração na tela de login    | `1`                       |
| `MERCADO_FACIL_TZ`             | Fuso horário das datas exibidas e dos períodos                   | `America/Sao_Paulo`       |

> Para uso real, defina `MERCADO_FACIL_SEED=0` e `MERCADO_FACIL_SHOW_DEMO_USERS=0` e troque as
> senhas de demonstração.

## Perfis e permissões (RNF08)

| Ação                                              | Operador | Estoquista | Gestor |
|---------------------------------------------------|:--------:|:----------:|:------:|
| Visão geral (indicadores)                         | ✔ | ✔ | ✔ |
| Abrir/fechar o próprio caixa, vender (PDV)        | ✔ |   | ✔ |
| Consultar vendas; registrar pós-venda*            | ✔ |   | ✔ |
| Cadastrar/editar/inativar produtos, movimentar estoque, ver histórico |   | ✔ | ✔ |
| Ver o caixa de todos os operadores                |   |   | ✔ |
| Gerar cópia de segurança (backup)                 |   |   | ✔ |

\* Cancelamento, devolução e troca exigem a **autorização de um gestor** (usuário e senha do
gestor na própria tela), conforme a documentação.

## Telas

1. **Visão geral** — vendas do dia, cashback, itens abaixo do estoque mínimo, últimas operações.
2. **PDV** — leitura de código de barras ou busca por nome, carrinho, pagamento (dinheiro, cartão,
   Pix), troco calculado, CPF/cashback, cupom *sem valor fiscal*.
3. **Produtos** — cadastro, edição, inativação e entrada/saída de estoque, com alerta de reposição.
4. **Vendas** — histórico com cancelamento de venda ou item, devolução e troca.
5. **Caixa** — abertura com fundo inicial e fechamento com conferência (esperado × contado).
6. **Movimentações** — histórico de entradas, saídas e ajustes, com exportação CSV.
7. **Projeto e operação** — documentação completa dentro do sistema, matriz de rastreabilidade,
   botão que **executa os casos de teste CT01–CT12 ao vivo**, manual operacional e backup.

## Regras de negócio principais

- Valores em **centavos inteiros** (sem erro de ponto flutuante).
- **Cashback de 1 %** sobre o total líquido da venda, arredondado para baixo (RB07); só é gerado
  para cliente identificado e pode ser usado como forma de pagamento parcial, nunca acima do saldo.
- Estoque nunca fica negativo; venda só com **caixa aberto** do próprio operador.
- Dinheiro recebido menor que o total bloqueia o pagamento; maior gera troco.
- Cancelamento devolve itens ao estoque; devolução é limitada ao que foi vendido e reembolsa de
  forma proporcional; troca liquida a diferença de preço.
- Aprovação de cartão/Pix é **simulada** (há uma opção para simular recusa).

## Qualidade e testes

```bash
pip install -r requirements-dev.txt
python scripts/check.py        # ruff format/check, mypy --strict, compilação, rastreabilidade, pytest
python -m pytest               # só os testes
python scripts/gen_traceability.py   # regenera docs/RASTREABILIDADE.md
```

- `tests/test_casos_de_teste.py` — os 12 casos de teste da documentação (CT01–CT12), um por função.
- Testes de serviços e repositórios (regras RB01–RB12, estoque, caixa, pós-venda, backup, esquema).
- `tests/test_ui_*.py` — executam o código **real** das telas sobre um Streamlit simulado
  (`tests/fake_streamlit.py`): login, navegação, PDV, produtos, vendas, caixa, contraste de cores.
- `tests/test_architecture.py` — garante a separação em camadas (`ui → services → repositories`).
- `tests/test_traceability.py` — garante que cada RF/RNF/RB aponta para código e testes que existem.
- [`docs/RASTREABILIDADE.md`](docs/RASTREABILIDADE.md) — matriz requisito → código → teste.

## Estrutura

```
app.py                      ponto de entrada do Streamlit
iniciar_mercado_facil.bat   atalho para Windows (instala e abre o sistema)
.streamlit/config.toml      tema claro com alto contraste
mercadofacil/
  config.py, models.py, money.py, validators.py, errors.py, database.py, seed.py, bootstrap.py
  repositories/             acesso ao SQL
  services/                 regras de negócio (autenticação, vendas, estoque, caixa, pós-venda…)
  ui/                       telas, componentes, tema, documentação embutida
scripts/                    check.py, gen_traceability.py
tests/                      suíte automatizada
docs/RASTREABILIDADE.md     matriz de rastreabilidade
```

## Decisões e interpretações da documentação

- O documento tem **RF01–RF16** (não há RF17), **RNF01–RNF11** e **RB01–RB12**; todos estão
  implementados e rastreados.
- **RNF11 ("emitir NF, por enquanto…")** foi interpretado como emissão fiscal fora do escopo,
  coerente com a seção 9.2: o cupom exibido é **sem valor fiscal**.
- Na tabela do manual (§9), a conferência do passo *Pós-venda* trazia texto repetido de outra
  linha; foi substituída por uma verificação coerente com o passo.
- Banco **SQLite** (WAL, chaves estrangeiras, índice único parcial para código de barras ativo,
  *triggers* que impedem estoque negativo no próprio banco).

## Limites do protótipo (seção 9.2)

Aprovação de cartões e Pix simulada; sem emissão fiscal, impressora, balança, TEF, fornecedores,
compras nem perfis detalhados de permissão. Esses recursos exigem integrações e homologações
específicas antes de uso comercial.
