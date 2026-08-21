@echo off
REM ============================================================================
REM  rebuild_rummikub.bat  --  Reconstruction complete de Rummikub (Windows)
REM  Calque sur rebuild_scrabble.bat. 9 etapes (0 a 8) :
REM    0. Localiser ISCC.exe (Inno Setup 6)
REM    1. Copier le projet vers C:\Temp\RummikubBuild
REM    2. Environnement virtuel .venv_build + dependances
REM    3. Fermer Rummikub.exe si en cours
REM    4. PyInstaller (rummikub.spec)
REM    5. Verifier dist\Rummikub\Rummikub.exe + taille (dossier non compresse)
REM    6. ISCC (installeur) + copie du Setup (local + partage) + garde-fou taille
REM    7. manifest.json + zip (dist + manifest) + copie + garde-fou taille
REM       (rummikub-vN.zip en --publier, rummikub.zip sinon)
REM    8. Nettoyage %BUILDDIR% + reset git du clone CCW
REM ============================================================================
setlocal EnableExtensions EnableDelayedExpansion

REM --- Analyse des arguments ------------------------------------------------
REM  Sans argument : comportement historique inchange (aucune publication).
REM  --publier      : apres l'etape 7, met a jour version.json (build + SHA-256)
REM                   et fait un commit local dans le clone partage. Jamais de
REM                   git push ni de gh release create (ces deux etapes restent
REM                   manuelles, cf. rappel en fin de script).
REM  --build N      : force le numero de build (sinon = build de version.json + 1).
set "PUBLIER=0"
set "BUILD_OVERRIDE="
:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--publier" ( set "PUBLIER=1" & shift /1 & goto parse_args )
if /i "%~1"=="--build" ( set "BUILD_OVERRIDE=%~2" & shift /1 & shift /1 & goto parse_args )
echo [ATTENTION] Argument inconnu ignore : %~1
shift /1
goto parse_args
:args_done

REM --- Racine du depot = dossier parent de ce .bat (build\ -> ..) -------------
pushd "%~dp0.." || (echo [ERREUR] Impossible d'atteindre la racine du projet. & exit /b 1)
set "ORIGDIR=%CD%"
popd

set "BUILDDIR=C:\Temp\RummikubBuild"
set "OUTPUTDIR=C:\Temp\RummikubOutput"

echo ============================================================================
echo   Reconstruction de Rummikub
echo   Projet source : %ORIGDIR%
echo ============================================================================

REM ===========================================================================
REM  ETAPE 0 : localiser ISCC.exe
REM ===========================================================================
echo.
echo [0/8] Recherche de ISCC.exe ^(Inno Setup 6^)...
set "ISCC=%ORIGDIR%\.tools\InnoSetup6\ISCC.exe"

REM  Aucun fallback reseau (issue #111) : l'ancien partage \\VBOXSVR\CCW_Share\...
REM  n'existe plus sur le PC fixe physique et faisait boucler robocopy en retry
REM  infini. Le binaire DOIT etre present localement dans .tools\InnoSetup6\ ;
REM  sinon on echoue immediatement et proprement (cf. rebuild_scrabble.bat).
if not exist "%ISCC%" (
    echo [ERREUR] ISCC.exe introuvable : %ISCC%
    echo          Installez Inno Setup 6 dans .tools\InnoSetup6\ avant de relancer le build.
    exit /b 1
)
echo       ISCC : %ISCC%

REM ===========================================================================
REM  ETAPE 1 : copie du projet vers le repertoire de build temporaire
REM ===========================================================================
echo.
echo [1/8] Copie du projet vers %BUILDDIR% ...
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
echo [2/8] Preparation de l'environnement virtuel .venv_build ...
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
echo [3/8] Fermeture de Rummikub.exe si necessaire...
taskkill /im Rummikub.exe /f >nul 2>&1
if errorlevel 1 (
    echo       Aucune instance de Rummikub.exe en cours.
) else (
    echo       Rummikub.exe ferme.
)

REM ===========================================================================
REM  ETAPE 3bis : injection du numero de build dans version_info.txt
REM  PyInstaller lit version_info.txt (cf. rummikub.spec, parametre version=)
REM  pour renseigner la ressource VERSIONINFO de Rummikub.exe (clic droit ->
REM  Proprietes -> Details -> Version du fichier). Le fichier versionne du depot
REM  contient le jeton « BUILD » ; on le remplace ICI, dans la COPIE de build
REM  (%BUILDDIR%, ou l'on est deja positionne via pushd), par le numero de build
REM  reel AVANT l'appel a PyInstaller. Le depot d'origine garde le jeton intact.
REM  Numero retenu = meme regle que MANIFESTBUILD : build courant de
REM  version.json, +1 en mode --publier, ou --build N s'il est fourni.
REM  Remplacement via String.Replace (.NET) = sensible a la casse : seul le
REM  jeton « BUILD » en majuscules est substitue, pas le mot « build ».
REM ===========================================================================
echo.
echo [3bis/8] Injection du numero de build dans version_info.txt...
set "EXEBUILD="
for /f "usebackq delims=" %%B in (`powershell -NoProfile -Command "[int]((ConvertFrom-Json (Get-Content -Raw '%ORIGDIR%\version.json')).build)"`) do set "EXEBUILD=%%B"
if not defined EXEBUILD (
    echo [ERREUR] Lecture du build courant impossible depuis %ORIGDIR%\version.json
    popd & exit /b 1
)
if "%PUBLIER%"=="1" (
    if defined BUILD_OVERRIDE (
        set "EXEBUILD=%BUILD_OVERRIDE%"
    ) else (
        set /a EXEBUILD=EXEBUILD+1
    )
)
if not exist "version_info.txt" (
    echo       [ATTENTION] version_info.txt introuvable : metadonnees de version non injectees.
) else (
    powershell -NoProfile -Command "(Get-Content -Raw 'version_info.txt').Replace('BUILD','!EXEBUILD!') | Set-Content -NoNewline -Encoding utf8 'version_info.txt'"
    if errorlevel 1 (
        echo [ERREUR] Echec du remplacement de BUILD dans version_info.txt.
        popd & exit /b 1
    )
    echo       version_info.txt : jeton BUILD -^> !EXEBUILD!
)

REM ===========================================================================
REM  ETAPE 4 : build PyInstaller
REM ===========================================================================
echo.
echo [4/8] Construction avec PyInstaller ^(rummikub.spec^)...
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
echo [5/8] Verification de dist\Rummikub\Rummikub.exe ...
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
REM  ETAPE 6 : installeur Inno Setup + copie (local + partage) + garde-fou
REM  Garde-fou sur l'INSTALLEUR FINAL COMPRESSE (Rummikub-Setup.exe).
REM  Distinct de l'etape 5 (dossier dist\ non compresse) : ici on mesure le .exe
REM  d'installation genere par Inno Setup, soit ~12 Mo (12 180 000 octets observes).
REM  Fourchette de sanite : 5 Mo a 25 Mo (5242880 a 26214400 octets).
REM  Hors de cette fourchette -> simple avertissement, pas d'echec.
REM ===========================================================================
echo.
echo [6/8] Generation de l'installeur avec Inno Setup...
REM  Numero de build injecte dynamiquement (issue #91), sur le modele de Scrabble
REM  (/DScrabbleBuildInstalle) : EXEBUILD provient de version.json (etape 3bis,
REM  +1 en --publier, --build N sinon). Le .iss n'a plus de #define hardcode ; le
REM  nom du Setup (Rummikub-Setup-vN) reste donc toujours en phase avec version.json.
"%ISCC%" /DRummikubBuildInstalle=!EXEBUILD! installeur\rummikub.iss
if errorlevel 1 (
    echo [ERREUR] Echec de la compilation de l'installeur ^(ISCC^).
    popd & exit /b 1
)

REM --- Nom du Setup produit par ISCC (issues #87 / #91) ----------------------
REM  rummikub.iss definit OutputBaseFilename=Rummikub-Setup-v{#RummikubBuildInstalle},
REM  donc ISCC produit Rummikub-Setup-v{N}.exe (et non plus Rummikub-Setup.exe).
REM  Le numero N est desormais INJECTE via /DRummikubBuildInstalle=!EXEBUILD! a
REM  l'appel ISCC ci-dessus (issue #91). On le connait donc directement : plus
REM  besoin de le relire depuis le .iss par regex PowerShell (ancienne logique
REM  issue #90 supprimee). !EXEBUILD! est toujours en phase avec version.json.
set "SETUPNAME=Rummikub-Setup-v!EXEBUILD!.exe"
echo       Setup attendu : !SETUPNAME! ^(build !EXEBUILD!^)

set "SETUP=%OUTPUTDIR%\%SETUPNAME%"
if not exist "%SETUP%" (
    echo [ERREUR] Installeur introuvable : %SETUP%
    popd & exit /b 1
)

echo       Copie de l'installeur ^(staging local %BUILDDIR%\installeur\output^)...
if not exist "installeur\output" mkdir "installeur\output"
copy /y "%SETUP%" "installeur\output\%SETUPNAME%" >nul
if errorlevel 1 ( echo [ERREUR] Echec de la copie locale de l'installeur. & popd & exit /b 1 )

echo       Copie de l'installeur vers le partage ^(%ORIGDIR%\installeur\output^)...
if not exist "%ORIGDIR%\installeur\output" mkdir "%ORIGDIR%\installeur\output"
copy /y "%SETUP%" "%ORIGDIR%\installeur\output\%SETUPNAME%" >nul
if errorlevel 1 ( echo [ERREUR] Echec de la copie de l'installeur vers le partage. & popd & exit /b 1 )

set "SETUPSIZE=0"
for /f "usebackq delims=" %%S in (`powershell -NoProfile -Command "(Get-Item '%SETUP%').Length"`) do set "SETUPSIZE=%%S"
echo       Taille de l'installeur %SETUPNAME% ^(compresse^) : %SETUPSIZE% octets
if %SETUPSIZE% LSS 5242880 echo       [ATTENTION] Installeur inhabituellement PETIT ^(attendu ~12 Mo, fourchette 5-25 Mo^).
if %SETUPSIZE% GTR 26214400 echo       [ATTENTION] Installeur inhabituellement GRAND ^(attendu ~12 Mo, fourchette 5-25 Mo^).

REM ===========================================================================
REM  Determination du numero de build et du nom du zip
REM  CURBUILD (build courant lu dans version.json) est desormais lu dans LES DEUX
REM  modes : il fournit MANIFESTBUILD, la valeur ecrite dans manifest.json a
REM  l'etape 7, pour que ce manifest reste coherent avec le build reel meme en
REM  build de test (sans --publier).
REM  En mode --publier, le zip publie doit s'appeler rummikub-vN.zip (format
REM  versionne attendu par Actualise pour construire l'URL de telechargement) ;
REM  on calcule donc NEWBUILD DES MAINTENANT, avant l'etape 7, pour nommer le
REM  zip de facon coherente entre l'etape 7 et l'etape 7bis, et MANIFESTBUILD
REM  prend alors la valeur de NEWBUILD. Sans --publier, le zip garde le nom fixe
REM  rummikub.zip (build de test local, jamais publie).
REM ===========================================================================
set "ZIPNAME=rummikub.zip"

REM --- Build courant (CURBUILD) lu dans version.json DANS LES DEUX MODES.
REM     Sert de valeur de build pour le manifest de l'etape 7 en mode test
REM     (sans --publier) et de base au calcul de NEWBUILD en mode --publier.
set "CURBUILD="
for /f "usebackq delims=" %%B in (`powershell -NoProfile -Command "[int]((ConvertFrom-Json (Get-Content -Raw '%ORIGDIR%\version.json')).build)"`) do set "CURBUILD=%%B"
if not defined CURBUILD (
    echo [ERREUR] Lecture du build courant impossible depuis %ORIGDIR%\version.json
    popd & exit /b 1
)

REM --- Build embarque dans le manifest de l'etape 7 : par defaut le build courant.
REM     En mode --publier il sera remplace par NEWBUILD (cf. bloc ci-dessous).
set "MANIFESTBUILD=!CURBUILD!"

if not "%PUBLIER%"=="1" goto zipname_done

REM --- Numero de build : --build N prioritaire, sinon version.json + 1 --------
if defined BUILD_OVERRIDE (
    set "NEWBUILD=%BUILD_OVERRIDE%"
    echo       Build impose via --build : !NEWBUILD!
    goto build_determine
)
set /a NEWBUILD=CURBUILD+1
echo       Build courant : !CURBUILD! -- nouveau build : !NEWBUILD!
:build_determine
set "MANIFESTBUILD=!NEWBUILD!"
set "ZIPNAME=rummikub-v!NEWBUILD!.zip"
:zipname_done

REM ===========================================================================
REM  ETAPE 7 : manifest.json + zip (dist\Rummikub\* + manifest.json)
REM  Le zip = dist\Rummikub\ + manifest.json, sans dossier englobant
REM  (l'updater Actualise l'extrait directement par-dessus le dossier installe).
REM  Nom : rummikub-vN.zip en --publier (format versionne, cf. bloc ci-dessus),
REM  rummikub.zip sinon (build de test local non publie).
REM  Garde-fou de taille sur le zip : fourchette 5 Mo a 25 Mo (memes bornes que
REM  l'installeur compresse) -> hors fourchette = simple avertissement.
REM ===========================================================================
echo.
echo [7/8] Creation de manifest.json et de !ZIPNAME!...
> manifest.json echo {"build": !MANIFESTBUILD!, "supprimer": []}
if not exist "installeur\output" mkdir "installeur\output"
if exist "installeur\output\!ZIPNAME!" del /f /q "installeur\output\!ZIPNAME!"
powershell -NoProfile -Command "try { Compress-Archive -Path 'dist\Rummikub\*','manifest.json' -DestinationPath 'installeur\output\!ZIPNAME!' -Force } catch { exit 1 }"
if errorlevel 1 (
    echo [ERREUR] Echec de la creation de !ZIPNAME!.
    popd & exit /b 1
)
if not exist "installeur\output\!ZIPNAME!" (
    echo [ERREUR] installeur\output\!ZIPNAME! introuvable apres compression.
    popd & exit /b 1
)
set "ZIPSIZE=0"
for /f "usebackq delims=" %%S in (`powershell -NoProfile -Command "(Get-Item 'installeur\output\!ZIPNAME!').Length"`) do set "ZIPSIZE=%%S"
echo       Taille de !ZIPNAME! ^(compresse^) : %ZIPSIZE% octets
if %ZIPSIZE% LSS 5242880 echo       [ATTENTION] !ZIPNAME! inhabituellement PETIT ^(attendu ~13 Mo, fourchette 5-25 Mo^).
if %ZIPSIZE% GTR 26214400 echo       [ATTENTION] !ZIPNAME! inhabituellement GRAND ^(attendu ~13 Mo, fourchette 5-25 Mo^).

echo       Copie de !ZIPNAME! vers le partage ^(%ORIGDIR%\installeur\output^)...
copy /y "installeur\output\!ZIPNAME!" "%ORIGDIR%\installeur\output\!ZIPNAME!" >nul
if errorlevel 1 ( echo [ERREUR] Echec de la copie de !ZIPNAME! vers le partage. & popd & exit /b 1 )

REM ===========================================================================
REM  ETAPE 7bis (--publier uniquement) : version.json + SHA-256 + commit local
REM  Ne s'execute qu'avec l'argument --publier. Reprend le zip rummikub-vN.zip
REM  genere a l'etape 7 (NEWBUILD deja calcule avant l'etape 7) pour :
REM    - reecrire manifest.json avec ce numero et regenerer rummikub-vN.zip ;
REM    - calculer le SHA-256 du zip ;
REM    - ecrire version.json a la racine du clone partage (%ORIGDIR%) ;
REM    - commiter version.json EN LOCAL (jamais de git push).
REM  git push et la creation de la Release GitHub restent MANUELS (voir la fin).
REM ===========================================================================
if not "%PUBLIER%"=="1" goto fin_publier

echo.
echo [7bis/8] Mode --publier : version.json ^(build + SHA-256^) et commit local...

REM --- Reecrire manifest.json avec le nouveau build et regenerer le zip -------
REM  NEWBUILD et ZIPNAME ^(rummikub-vN.zip^) ont ete determines avant l'etape 7.
echo       Reecriture de manifest.json ^(build !NEWBUILD!^) et du zip !ZIPNAME!...
> manifest.json echo {"build": !NEWBUILD!, "supprimer": []}
if exist "installeur\output\!ZIPNAME!" del /f /q "installeur\output\!ZIPNAME!"
powershell -NoProfile -Command "try { Compress-Archive -Path 'dist\Rummikub\*','manifest.json' -DestinationPath 'installeur\output\!ZIPNAME!' -Force } catch { exit 1 }"
if errorlevel 1 (
    echo [ERREUR] Echec de la regeneration de !ZIPNAME! ^(--publier^).
    popd & exit /b 1
)
copy /y "installeur\output\!ZIPNAME!" "%ORIGDIR%\installeur\output\!ZIPNAME!" >nul
if errorlevel 1 ( echo [ERREUR] Echec de la copie de !ZIPNAME! vers le partage ^(--publier^). & popd & exit /b 1 )

REM --- SHA-256 du zip regenere -----------------------------------------------
set "ZIPSHA="
for /f "usebackq delims=" %%H in (`powershell -NoProfile -Command "(Get-FileHash 'installeur\output\!ZIPNAME!' -Algorithm SHA256).Hash.ToLower()"`) do set "ZIPSHA=%%H"
if not defined ZIPSHA (
    echo [ERREUR] Calcul du SHA-256 de !ZIPNAME! impossible.
    popd & exit /b 1
)
echo       SHA-256 : !ZIPSHA!

REM --- version.json a la racine du clone partage (%ORIGDIR% = C:\CCW_Share\CCW\rummikub) -
> "%ORIGDIR%\version.json" echo {"build": !NEWBUILD!, "sha256": "!ZIPSHA!"}
echo       version.json ecrit : %ORIGDIR%\version.json

REM --- Commit LOCAL de version.json (jamais de git push) ---------------------
echo       Commit local de version.json dans le clone partage...
git -C "%ORIGDIR%" add version.json
git -C "%ORIGDIR%" commit -m "Rummikub v!NEWBUILD! : version.json (build !NEWBUILD! + SHA-256 du zip)" -- version.json
if errorlevel 1 echo       [ATTENTION] git commit n'a rien commite ^(version.json inchange ?^).
:fin_publier

popd

REM ===========================================================================
REM  ETAPE 8 : nettoyage du build local + reset du clone CCW
REM ===========================================================================
echo.
echo [8/8] Nettoyage de %BUILDDIR% et reset du depot partage...
echo       Nettoyage de %BUILDDIR% ...
rmdir /s /q "%BUILDDIR%"

if "%PUBLIER%"=="1" (
    echo       [--publier] Reset git IGNORE pour preserver le commit version.json.
) else (
    echo       Reset du depot partage ^(git reset --hard origin/master^)...
    git -C C:\CCW_Share\CCW\rummikub reset --hard origin/master
)

echo.
echo ============================================================================
echo   Termine. Installeur : %ORIGDIR%\installeur\output\!SETUPNAME!
echo             Archive    : %ORIGDIR%\installeur\output\!ZIPNAME!
echo ============================================================================
if "%PUBLIER%"=="1" (
    echo.
    echo   --- PUBLICATION ^(--publier^) : etapes MANUELLES restantes ---
    echo   version.json a ete mis a jour ^(build !NEWBUILD!, SHA-256 du zip^) et
    echo   COMMITE EN LOCAL dans %ORIGDIR%.
    echo.
    echo   Le script ne fait JAMAIS de git push ni de gh release create. A la main :
    echo     1^) git -C "%ORIGDIR%" push
    echo     2^) Creer la Release GitHub ^(tag v!NEWBUILD!^) et y attacher :
    echo          - installeur\output\!SETUPNAME!
    echo          - installeur\output\!ZIPNAME!
    echo   ============================================================================
)
endlocal
exit /b 0
