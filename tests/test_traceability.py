"""A matriz requisito → código → teste não pode citar nada que não exista."""

from __future__ import annotations

from pathlib import Path

from mercadofacil.ui import docs_content, traceability

ROOT = Path(__file__).resolve().parent.parent


def ids(requirements: tuple[docs_content.Requirement, ...]) -> list[str]:
    return [r.id for r in requirements]


def test_todos_os_requisitos_e_regras_do_documento_estao_presentes() -> None:
    assert ids(docs_content.FUNCTIONAL) == [f"RF{n:02d}" for n in range(1, 17)]
    assert ids(docs_content.NON_FUNCTIONAL) == [f"RNF{n:02d}" for n in range(1, 12)]
    assert ids(docs_content.BUSINESS_RULES) == [f"RB{n:02d}" for n in range(1, 13)]


def test_casos_de_teste_ct01_a_ct12_estao_presentes() -> None:
    assert [c.id for c in docs_content.TEST_CASES] == [f"CT{n:02d}" for n in range(1, 13)]
    for case in docs_content.TEST_CASES:
        assert case.test.startswith(f"test_ct{case.id[2:]}_")


def test_todas_as_referencias_apontam_para_codigo_e_testes_que_existem() -> None:
    assert traceability.problems() == []


def test_uma_referencia_quebrada_e_detectada() -> None:
    assert traceability.check_code_ref("mercadofacil/services/sales.py:nao_existe")
    assert traceability.check_code_ref("mercadofacil/nao_existe.py:finalize_sale")
    assert traceability.check_code_ref("sem-separador")
    assert traceability.check_test_ref("tests/test_sales.py::test_que_nao_existe")
    assert traceability.check_test_ref("tests/test_sales.py") is not None
    assert traceability.check_code_ref("mercadofacil/services/sales.py:finalize_sale") is None


def test_ids_sao_unicos_e_textos_nao_vazios() -> None:
    todos = ids(docs_content.ALL_REQUIREMENTS)
    assert len(todos) == len(set(todos)) == 39
    assert all(r.text.strip() for r in docs_content.ALL_REQUIREMENTS)


def test_documento_de_rastreabilidade_esta_atualizado() -> None:
    arquivo = ROOT / "docs" / "RASTREABILIDADE.md"
    assert arquivo.is_file(), "rode: python scripts/gen_traceability.py"
    assert arquivo.read_text(encoding="utf-8") == traceability.render_markdown()
