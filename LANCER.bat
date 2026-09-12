@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo.
echo ================================================================
echo   KALMAN v6 - Test automatique de la strategie
echo ================================================================
echo.

REM --- trouver Python ---
set PY=
where py >nul 2>&1 && set PY=py
if "%PY%"=="" (where python >nul 2>&1 && set PY=python)

if "%PY%"=="" (
  echo   PYTHON N'EST PAS INSTALLE.
  echo.
  echo   1. Va sur https://www.python.org/downloads/
  echo   2. Telecharge et installe Python
  echo   3. IMPORTANT : coche "Add Python to PATH" pendant l'installation
  echo   4. Relance ce fichier
  echo.
  pause
  exit /b 1
)

echo   Python trouve : %PY%
echo.
echo   [1] Installation des dependances (une seule fois, ~1 min)...
%PY% -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo.
  echo   Echec de l'installation. Verifie ta connexion internet.
  pause
  exit /b 1
)
echo   OK
echo.
echo   [2] Telechargement des donnees et test de la strategie...
echo   Cela peut prendre 5 a 15 minutes la premiere fois.
echo.

%PY% run_auto.py %*

echo.
echo   Termine. Le rapport s'ouvre dans ton navigateur.
echo   Si ce n'est pas le cas, ouvre le fichier "rapport.html" dans ce dossier.
echo.
pause
