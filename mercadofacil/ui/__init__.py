"""Interface web (Streamlit) do Mercado Fácil.

A interface só apresenta e coleta dados: toda regra de negócio é validada pelas
camadas `services` (RNF03/RNF05). Os módulos sem dependência do Streamlit
(`cart`, `formatting`, `navigation`, `theme`, `docs_content`) são testados diretamente.
"""
