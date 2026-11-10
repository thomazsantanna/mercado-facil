@echo off
chcp 65001 >nul
title Mercado Facil
cd /d "%~dp0"

set "PY=python"
where py >nul 2>nul && set "PY=py -3"

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Criando o ambiente virtual...
  %PY% -m venv .venv
  if errorlevel 1 goto erro
)

echo [2/3] Verificando as dependencias ^(a primeira vez demora um pouco^)...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 goto erro

echo [3/3] Abrindo o Mercado Facil no navegador (http://localhost:8501)...
echo Para encerrar, feche esta janela ou pressione Ctrl+C.
".venv\Scripts\python.exe" -m streamlit run app.py
goto fim

:erro
echo.
echo Nao foi possivel iniciar. Confirme que o Python 3.10 ou superior esta instalado
echo (https://www.python.org/downloads/ - marque "Add python.exe to PATH") e tente de novo.

:fim
pause
