@echo off
REM ============================================================================
REM  rebuild_rummikub.bat  --  Reconstruction complete de Rummikub (Windows)
REM  Calque sur rebuild_scrabble.bat. 6 etapes :
REM    0. Localiser ISCC.exe (Inno Setup 6)
REM    1. Copier le projet vers C:\Temp\RummikubBuild
REM    2. Environnement virtuel .venv_build + dependances
REM    3. Fermer Rummikub.exe si en cours
REM    4. PyInstaller (rummikub.spec)
REM    5. Verifier dist\Rummikub\Rummikub.exe + taille
REM    6. ISCC (installeur) + copie du Setup + nettoyage + reset git
REM ============================================================================
setlocal EnableExtensions EnableDelayedExpansion

REM --- Racine du depot = dossier parent de ce .bat (build\ -> ..) -------------
pushd "%~dp0.." || (echo [ERREUR] Impossible d'atteindre la racine du projet. & exit /b 1)
set "ORIGDIR=%CD%"
popd

set "BUILDDIR=C:\Temp\RummikubBuild"
set "OUTPUTDIR=C:\Temp\RummikubOutput"
set "SHARE_ISCC=\\VBOXSVR\CCW_Share\CCW\scrabble\.tools\InnoSetup6"

echo ============================================================================
echo   Reconstruction de Rummikub
echo   Projet source : %ORIGDIR%
echo ============================================================================

REM ===========================================================================
REM  ETAPE 0 : localiser ISCC.exe
REM ===========================================================================
echo.
echo [0/6] Recherche de ISCC.exe ^(Inno Setup 6^)...
set "ISCC=%ORIGDIR%\.tools\InnoSetup6\ISCC.exe"

if not exist "%ISCC%" (
    echo       ISCC.exe absent, tentative de copie depuis le partage CCW...
    robocopy "%SHARE_ISCC%" "%ORIGDIR%\.tools\InnoSetup6" /E /NFL /NDL /NJH /NJS /NC /NS /NP
    if errorlevel 8 (
        echo [ERREUR] Echec de la copie de Inno Setup depuis %SHARE_ISCC%
        exit /b 1
    )
)

if not exist "%ISCC%" (
    echo [ERREUR] ISCC.exe introuvable : %ISCC%
    echo          Installez Inno Setup 6 dans .tools\InnoSetup6\ ou verifiez le partage :
    echo          %SHARE_ISCC%
    exit /b 1
)
echo       ISCC : %ISCC%

REM ===========================================================================
REM  ETAPE 1 : copie du projet vers le repertoire de build temporaire
REM ===========================================================================
echo.
echo [1/6] Copie du projet vers %BUILDDIR% ...
robocopy "%ORIGDIR%" "%BUILDDIR%" /MIR /XD .git venv .venv_build dist build __pycache__ .pytest_cache logs /NFL /NDL /NJH /NJS /NC /NS /NP
if errorlevel 8 (
    echo [ERREUR] Echec de la copie du projet vers %BUILDDIR%
    exit /b 1
)

pushd "%BUILDDIR%" || (echo [ERREUR] Impossible d'atteindre %BUILDDIR% & exit /b 1)

REM ===========================================================================
REM  ETAPE 2 : environnement virtuel + dependances
REM ===========================================================================
echo.
echo [2/6] Preparation de l'environnement virtuel .venv_build ...
if not exist ".venv_build\Scripts\python.exe" (
    python -m venv .venv_build
    if errorlevel 1 (
        echo [ERREUR] Echec de la creation de .venv_build
        popd & exit /b 1
    )
)
call ".venv_build\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 ( echo [ERREUR] Echec de la mise a jour de pip & popd & exit /b 1 )
call ".venv_build\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 ( echo [ERREUR] Echec de pip install -r requirements.txt & popd & exit /b 1 )
call ".venv_build\Scripts\python.exe" -m pip install pyinstaller
if errorlevel 1 ( echo [ERREUR] Echec de pip install pyinstaller & popd & exit /b 1 )

REM ===========================================================================
REM  ETAPE 3 : fermer Rummikub.exe si en cours d'execution
REM ===========================================================================
echo.
echo [3/6] Fermeture de Rummikub.exe si necessaire...
taskkill /im Rummikub.exe /f >nul 2>&1
if errorlevel 1 (
    echo       Aucune instance de Rummikub.exe en cours.
) else (
    echo       Rummikub.exe ferme.
)

REM ===========================================================================
REM  ETAPE 4 : build PyInstaller
REM ===========================================================================
echo.
echo [4/6] Construction avec PyInstaller ^(rummikub.spec^)...
call ".venv_build\Scripts\python.exe" -m PyInstaller rummikub.spec -y
if errorlevel 1 (
    echo [ERREUR] Echec de PyInstaller
    popd & exit /b 1
)

REM ===========================================================================
REM  ETAPE 5 : verification de l'executable produit
REM  Gabarit de taille attendu : cette mesure porte sur le DOSSIER dist\Rummikub
REM  NON COMPRESSE (arborescence PyInstaller onedir), et non sur l'installeur.
REM  Taille normale observee du dossier dist\Rummikub : ~28 Mo (28 712 051 octets).
REM  Fourchette de sanite : 20 Mo a 45 Mo (20971520 a 47185920 octets).
REM  Hors de cette fourchette -> simple avertissement, pas d'echec.
REM  (Le garde-fou sur l'installeur final compresse est a l'etape 6.)
REM ===========================================================================
echo.
echo [5/6] Verification de dist\Rummikub\Rummikub.exe ...
if not exist "dist\Rummikub\Rummikub.exe" (
    echo [ERREUR] dist\Rummikub\Rummikub.exe introuvable apres le build.
    popd & exit /b 1
)
set "TOTAL=0"
for /f "usebackq delims=" %%S in (`powershell -NoProfile -Command "(Get-ChildItem -Recurse -File 'dist\Rummikub' | Measure-Object -Sum Length).Sum"`) do set "TOTAL=%%S"
echo       OK : dist\Rummikub\Rummikub.exe present.
echo       Taille totale du dossier dist\Rummikub ^(non compresse^) : %TOTAL% octets
if %TOTAL% LSS 20971520 echo       [ATTENTION] Dossier dist\ inhabituellement PETIT ^(attendu ~28 Mo, fourchette 20-45 Mo^).
if %TOTAL% GTR 47185920 echo       [ATTENTION] Dossier dist\ inhabituellement GRAND ^(attendu ~28 Mo, fourchette 20-45 Mo^).

REM ===========================================================================
REM  ETAPE 6 : installeur Inno Setup + copie + nettoyage + reset git
REM ===========================================================================
echo.
echo [6/6] Generation de l'installeur avec Inno Setup...
"%ISCC%" installeur\rummikub.iss
if errorlevel 1 (
    echo [ERREUR] Echec de la compilation de l'installeur ^(ISCC^).
    popd & exit /b 1
)

set "SETUP=%OUTPUTDIR%\Rummikub-Setup.exe"
if not exist "%SETUP%" (
    echo [ERREUR] Installeur introuvable : %SETUP%
    popd & exit /b 1
)

echo       Copie de l'installeur ^(staging local %BUILDDIR%\installeur\output^)...
if not exist "installeur\output" mkdir "installeur\output"
copy /y "%SETUP%" "installeur\output\Rummikub-Setup.exe" >nul
if errorlevel 1 ( echo [ERREUR] Echec de la copie locale de l'installeur. & popd & exit /b 1 )

echo       Copie de l'installeur vers le partage ^(%ORIGDIR%\installeur\output^)...
if not exist "%ORIGDIR%\installeur\output" mkdir "%ORIGDIR%\installeur\output"
copy /y "%SETUP%" "%ORIGDIR%\installeur\output\Rummikub-Setup.exe" >nul
if errorlevel 1 ( echo [ERREUR] Echec de la copie de l'installeur vers le partage. & popd & exit /b 1 )

REM  Garde-fou sur l'INSTALLEUR FINAL COMPRESSE (Rummikub-Setup.exe).
REM  Distinct de l'etape 5 (dossier dist\ non compresse) : ici on mesure le .exe
REM  d'installation genere par Inno Setup, soit ~12 Mo (12 180 000 octets observes).
REM  Fourchette de sanite : 5 Mo a 25 Mo (5242880 a 26214400 octets).
REM  Hors de cette fourchette -> simple avertissement, pas d'echec.
set "SETUPSIZE=0"
for /f "usebackq delims=" %%S in (`powershell -NoProfile -Command "(Get-Item '%SETUP%').Length"`) do set "SETUPSIZE=%%S"
echo       Taille de l'installeur Rummikub-Setup.exe ^(compresse^) : %SETUPSIZE% octets
if %SETUPSIZE% LSS 5242880 echo       [ATTENTION] Installeur inhabituellement PETIT ^(attendu ~12 Mo, fourchette 5-25 Mo^).
if %SETUPSIZE% GTR 26214400 echo       [ATTENTION] Installeur inhabituellement GRAND ^(attendu ~12 Mo, fourchette 5-25 Mo^).

popd

echo.
echo       Nettoyage de %BUILDDIR% ...
rmdir /s /q "%BUILDDIR%"

echo       Reset du depot partage ^(git reset --hard origin/master^)...
git -C Z:\CCW\rummikub reset --hard origin/master

echo.
echo ============================================================================
echo   Termine. Installeur : %ORIGDIR%\installeur\output\Rummikub-Setup.exe
echo ============================================================================
endlocal
exit /b 0
