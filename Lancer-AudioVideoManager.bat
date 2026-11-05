@echo off
rem AudioVideoManager — lanceur Windows (double-clic / raccourci bureau)
rem Utilise uniquement le Python du .venv local. Aucune elevation admin.
setlocal EnableExtensions
chcp 65001 >nul 2>&1

rem Repertoire du .bat (independant du repertoire de travail / raccourci)
cd /d "%~dp0" || (
  echo [AudioVideoManager] Impossible d'ouvrir le dossier du lanceur.
  echo Chemin : "%~dp0"
  pause
  exit /b 1
)

set "AVM_ROOT=%~dp0"
set "AVM_PYTHON=%AVM_ROOT%.venv\Scripts\python.exe"
set "AVM_ENTRY=%AVM_ROOT%audio_video_manager\__main__.py"

if not exist "%AVM_PYTHON%" (
  echo.
  echo [AudioVideoManager] Environnement Python introuvable.
  echo.
  echo Attendu : "%AVM_PYTHON%"
  echo.
  echo Creez le venv a la racine du projet, puis installez le paquet :
  echo   python -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -e ".[dev]"
  echo.
  echo Consultez docs\engineering\development.md pour le detail.
  echo.
  pause
  exit /b 1
)

if not exist "%AVM_ENTRY%" (
  echo.
  echo [AudioVideoManager] Point d'entree manquant.
  echo.
  echo Attendu : "%AVM_ENTRY%"
  echo Verifiez que ce lanceur se trouve a la racine du depot AudioVideoManager.
  echo.
  pause
  exit /b 1
)

rem Lancement via le module (meme entree que : python -m audio_video_manager)
"%AVM_PYTHON%" -m audio_video_manager %*
set "AVM_EXIT=%ERRORLEVEL%"

if not "%AVM_EXIT%"=="0" (
  echo.
  echo [AudioVideoManager] L'application s'est arretee avec le code %AVM_EXIT%.
  echo Les messages ci-dessus peuvent preciser la cause.
  echo.
  pause
  exit /b %AVM_EXIT%
)

endlocal & exit /b 0
