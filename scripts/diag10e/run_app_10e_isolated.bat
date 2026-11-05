@echo off
setlocal
set "AVM_10E_MODE=1"
if not defined LOCALAPPDATA (
	echo AVM-10E REFUS: LOCALAPPDATA absent.
	exit /b 2
)
if not defined USERPROFILE (
	echo AVM-10E REFUS: USERPROFILE absent.
	exit /b 2
)
for %%I in ("%~dp0..\..") do set "AVM_10E_REPO_ROOT=%%~fI"
set "AVM_DATA_DIR=%LOCALAPPDATA%\AudioVideoManager-10E"
set "AVM_LIBRARY_ROOT=%USERPROFILE%\Music\AVM-10E-Test-Library"
set "AVM_VENV=%AVM_10E_REPO_ROOT%\.venv"
if not exist "%AVM_VENV%\Scripts\activate.bat" (
	echo AVM-10E REFUS: activation venv absente: "%AVM_VENV%\Scripts\activate.bat"
	exit /b 2
)
cd /d "%AVM_10E_REPO_ROOT%"
if errorlevel 1 (
	echo AVM-10E REFUS: impossible de rejoindre la racine du depot.
	exit /b 2
)
call "%AVM_VENV%\Scripts\activate.bat"
if errorlevel 1 (
	echo AVM-10E REFUS: activation de l'environnement Python echouee.
	exit /b 2
)
for %%I in ("%VIRTUAL_ENV%") do set "AVM_ACTIVE_VENV=%%~fI"
for %%I in ("%AVM_VENV%") do set "AVM_EXPECTED_VENV=%%~fI"
if /I not "%AVM_ACTIVE_VENV%"=="%AVM_EXPECTED_VENV%" (
	echo AVM-10E REFUS: VIRTUAL_ENV ne correspond pas au venv du depot.
	exit /b 2
)
set "AVM_10E_PYTHON="
for /f "delims=" %%P in ('where python 2^>nul') do if not defined AVM_10E_PYTHON set "AVM_10E_PYTHON=%%~fP"
for %%I in ("%AVM_VENV%\Scripts\python.exe") do set "AVM_EXPECTED_PYTHON=%%~fI"
if /I not "%AVM_10E_PYTHON%"=="%AVM_EXPECTED_PYTHON%" (
	echo AVM-10E REFUS: Python resolu hors du venv: "%AVM_10E_PYTHON%"
	exit /b 2
)
"%AVM_10E_PYTHON%" -m audio_video_manager.diag10e_isolation
if errorlevel 1 exit /b 2
if /I "%AVM_10E_PREFLIGHT_ONLY%"=="1" exit /b 0
"%AVM_10E_PYTHON%" -m audio_video_manager
exit /b %errorlevel%
