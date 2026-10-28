@echo off
REM ============================================================================
REM  rebuild_rummikub.bat  --  Reconstruction complete de Rummikub (Windows)
REM  Calque sur rebuild_scrabble.bat / rebuild_actualise.bat. 10 etapes (0 a 9) :
REM    0.    Localiser ISCC.exe (Inno Setup 6)
REM    0bis. Determiner et valider le numero de build (garde-fou, issue #178)
REM    1.    Copier le projet vers C:\Temp\RummikubBuild
REM    2.    Environnement virtuel .venv_build + dependances
REM    3.    Fermer Rummikub.exe si en cours
REM    4.    PyInstaller (rummikub.spec)
REM    5.    Verifier dist\Rummikub\Rummikub.exe + taille (dossier non compresse)
REM    5bis. Autotest fonctionnel de l'exe (--autotest : solveur exact, issue #208)
REM    6.    ISCC (installeur) + copie du Setup (local + worktree) + garde-fou taille
REM    7.    manifest.json + zip (dist + manifest) + copie vers le worktree + garde-fou taille
REM    8.    Copie de l'installeur et du zip vers le dossier fixe hors worktree
REM          (issue #178), dans tous les modes -- --publier ajoute en plus la
REM          mise a jour de version.json (build + SHA-256) et un commit local.
REM    9.    Nettoyage de %BUILDDIR%
REM  Le script construit entierement dans un dossier local (%BUILDDIR%) puis
REM  n'ecrit que dans le worktree courant (%ORIGDIR%) et dans le dossier fixe
REM  hors worktree ci-dessus : il n'a plus aucune notion de clone partage.
REM ============================================================================
setlocal EnableExtensions EnableDelayedExpansion

REM --- Analyse des arguments ------------------------------------------------
REM  Syntaxe : build\rebuild_rummikub.bat [--publier] [--build N]
REM  Sans argument : construit l'installeur et l'archive (build de test, non
REM  publie) et les copie quand meme vers le dossier fixe hors worktree.
REM  --publier      : en plus de la construction, met a jour version.json
REM                   (build + SHA-256 de l'archive) et fait un commit local
REM                   dans le worktree. Jamais de git push ni de
REM                   gh release create (etapes manuelles, cf. rappel final).
REM  --build N      : force le numero de build (sinon = build de version.json
REM                   + 1), dans tous les modes. N doit etre un entier
REM                   strictement superieur au build courant de version.json :
REM                   refuse sinon, avant toute copie, construction ou
REM                   ecriture (garde-fou, issue #178), car la copie vers le
REM                   dossier fixe a lieu dans tous les modes, --publier ou
REM                   non. --build sans valeur, ou tout argument inconnu, est
REM                   egalement refuse (plus d'avertissement silencieux).
set "PUBLIER=0"
set "BUILD_OVERRIDE="
:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--publier" ( set "PUBLIER=1" & shift /1 & goto parse_args )
if /i "%~1"=="--build" (
    if "%~2"=="" (
        echo [ERREUR] --build necessite une valeur numerique ^(exemple : --build 42^).
        echo           Arguments acceptes : --publier, --build N
        exit /b 1
    )
    echo %~2| findstr /r "^[0-9][0-9]*$" >nul
    if errorlevel 1 (
        echo [ERREUR] --build necessite un entier positif ; recu : %~2
        echo           Arguments acceptes : --publier, --build N
        exit /b 1
    )
    set "BUILD_OVERRIDE=%~2"
    shift /1
    shift /1
    goto parse_args
)
echo [ERREUR] Argument inconnu : %~1
echo           Arguments acceptes : --publier, --build N
exit /b 1
:args_done

REM --- Racine du depot = dossier parent de ce .bat (build\ -> ..) -------------
pushd "%~dp0.." || (echo [ERREUR] Impossible d'atteindre la racine du projet. & exit /b 1)
set "ORIGDIR=%CD%"
popd

set "BUILDDIR=C:\Temp\RummikubBuild"
set "OUTPUTDIR=C:\Temp\RummikubOutput"
set "FIXEDSHARE=C:\CCW_Share\_derniers_builds\rummikub"

echo ============================================================================
echo   Reconstruction de Rummikub
echo   Projet source : %ORIGDIR%
echo ============================================================================

REM ===========================================================================
REM  ETAPE 0 : localiser ISCC.exe
REM ===========================================================================
echo.
echo [0/9] Recherche de ISCC.exe ^(Inno Setup 6^)...
set "ISCC_CCW=C:\CCW\tools\InnoSetup6\ISCC.exe"
set "ISCC_LOCAL=%ORIGDIR%\.tools\InnoSetup6\ISCC.exe"

REM  Aucun fallback reseau (issue #111) : l'ancien partage \\VBOXSVR\CCW_Share\...
REM  n'existe plus sur le PC fixe physique et faisait boucler robocopy en retry
REM  infini. Depuis l'issue #176, on cherche D'ABORD C:\CCW\tools\InnoSetup6\
REM  (installe hors des depots, donc accessible depuis n'importe quel worktree
REM  CCW frais ou .tools\ n'existe pas), puis on se rabat sur l'ancien chemin
REM  local .tools\InnoSetup6\ (utile hors d'un worktree CCW, ex. build local
REM  par Alain). Si aucun des deux n'existe, on echoue immediatement et
REM  proprement (cf. rebuild_scrabble.bat).
if exist "%ISCC_CCW%" (
    set "ISCC=%ISCC_CCW%"
) else if exist "%ISCC_LOCAL%" (
    set "ISCC=%ISCC_LOCAL%"
) else (
    echo [ERREUR] ISCC.exe introuvable dans aucun des emplacements suivants :
    echo            - %ISCC_CCW%
    echo            - %ISCC_LOCAL%
    echo          Installez Inno Setup 6 dans l'un de ces deux dossiers avant de relancer le build.
    exit /b 1
)
echo       ISCC : %ISCC%

REM ===========================================================================
REM  ETAPE 0bis : determiner et valider le numero de build (garde-fou, issue #178)
REM  Lu AVANT toute copie/construction/ecriture, car la copie vers le dossier
REM  fixe hors worktree (etape 8) a lieu dans tous les modes, --publier ou non.
REM  N (fourni via --build, deja valide numerique a l'analyse des arguments, ou
REM  build courant + 1 par defaut) doit toujours etre strictement superieur au
REM  build courant de version.json.
REM ===========================================================================
echo.
echo [0bis/9] Determination et validation du numero de build...
set "CURBUILD="
for /f "usebackq delims=" %%B in (`powershell -NoProfile -Command "try { [int]((ConvertFrom-Json (Get-Content -Raw '%ORIGDIR%\version.json')).build) } catch { '' }"`) do set "CURBUILD=%%B"
if not defined CURBUILD (
    echo [ERREUR] Lecture du build courant impossible depuis %ORIGDIR%\version.json
    exit /b 1
)
echo       Build courant ^(version.json^) : !CURBUILD!

if defined BUILD_OVERRIDE (
    set "EXEBUILD=%BUILD_OVERRIDE%"
) else (
    set /a EXEBUILD=CURBUILD+1
)

if not !EXEBUILD! gtr !CURBUILD! (
    echo [ERREUR] Numero de build demande ^(!EXEBUILD!^) invalide.
    echo          Build courant de version.json : !CURBUILD!.
    echo          Regle : le numero de build doit toujours etre strictement
    echo          superieur au build courant de version.json, --publier ou
    echo          non, car la copie vers le dossier fixe a lieu dans tous les
    echo          modes.
    exit /b 1
)
echo       Numero de build retenu : !EXEBUILD!

REM ===========================================================================
REM  ETAPE 1 : copie du projet vers le repertoire de build temporaire
REM ===========================================================================
echo.
echo [1/9] Copie du projet vers %BUILDDIR% ...
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
echo [2/9] Preparation de l'environnement virtuel .venv_build ...
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
echo [3/9] Fermeture de Rummikub.exe si necessaire...
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
REM  Numero retenu = !EXEBUILD!, deja determine et valide a l'etape 0bis.
REM  Remplacement via String.Replace (.NET) = sensible a la casse : seul le
REM  jeton « BUILD » en majuscules est substitue, pas le mot « build ».
REM ===========================================================================
echo.
echo [3bis/9] Injection du numero de build dans version_info.txt...
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
echo [4/9] Construction avec PyInstaller ^(rummikub.spec^)...
call ".venv_build\Scripts\python.exe" -m PyInstaller rummikub.spec -y
if errorlevel 1 (
    echo [ERREUR] Echec de PyInstaller
    popd & exit /b 1
)

REM ===========================================================================
REM  ETAPE 5 : verification de l'executable produit
REM  Gabarit de taille attendu : cette mesure porte sur le DOSSIER dist\Rummikub
REM  NON COMPRESSE (arborescence PyInstaller onedir), et non sur l'installeur.
REM  Depuis le solveur exact d'Expert (issue #206 : numpy ~43 Mo + highspy
REM  ~12 Mo, soit ~+55 Mo sur disque), le dossier passe d'environ 26 Mo (build
REM  13) a environ 80 Mo attendus. Fourchette de sanite ELARGIE (issue #208) :
REM  20 Mo a 120 Mo (20971520 a 125829120 octets). Valeurs PROVISOIRES a
REM  confirmer/resserrer apres le premier build Windows avec highspy/numpy.
REM  Hors de cette fourchette -> simple avertissement, pas d'echec.
REM  (Le garde-fou sur l'installeur final compresse est a l'etape 6.)
REM ===========================================================================
echo.
echo [5/9] Verification de dist\Rummikub\Rummikub.exe ...
if not exist "dist\Rummikub\Rummikub.exe" (
    echo [ERREUR] dist\Rummikub\Rummikub.exe introuvable apres le build.
    popd & exit /b 1
)
set "TOTAL=0"
for /f "usebackq delims=" %%S in (`powershell -NoProfile -Command "(Get-ChildItem -Recurse -File 'dist\Rummikub' | Measure-Object -Sum Length).Sum"`) do set "TOTAL=%%S"
echo       OK : dist\Rummikub\Rummikub.exe present.
echo       Taille totale du dossier dist\Rummikub ^(non compresse^) : %TOTAL% octets
if %TOTAL% LSS 20971520 echo       [ATTENTION] Dossier dist\ inhabituellement PETIT ^(attendu ~80 Mo, fourchette 20-120 Mo^).
if %TOTAL% GTR 125829120 echo       [ATTENTION] Dossier dist\ inhabituellement GRAND ^(attendu ~80 Mo, fourchette 20-120 Mo^).

REM ===========================================================================
REM  ETAPE 5bis : autotest fonctionnel de l'executable (issue #208)
REM  Lance dist\Rummikub\Rummikub.exe --autotest, qui verifie SANS ouvrir de
REM  fenetre (et sans charger pywebview) que le solveur exact d'Expert
REM  (highspy + numpy) est bien collecte et FONCTIONNE dans le binaire gele :
REM  sinon Expert retomberait silencieusement sur l'ancienne recherche sans que
REM  personne ne le voie (risque n^o 1 de l'issue #206/#208). L'executable etant
REM  fenetre (console=False), sa sortie standard est perdue : --autotest ecrit
REM  donc son compte rendu dans le fichier passe en argument, qu'on reprend ici
REM  via "type". Code de sortie != 0 => build REFUSE (echec franc, pas un simple
REM  avertissement : un paquet ou Expert est casse ne doit pas etre publie).
REM ===========================================================================
echo.
echo [5bis/9] Autotest de l'executable ^(--autotest^)...
set "AUTOTEST_LOG=%BUILDDIR%\autotest_rapport.txt"
if exist "!AUTOTEST_LOG!" del /f /q "!AUTOTEST_LOG!"
"dist\Rummikub\Rummikub.exe" --autotest "!AUTOTEST_LOG!"
set "AUTOTEST_RC=!errorlevel!"
if exist "!AUTOTEST_LOG!" (
    echo       --- Compte rendu de l'autotest ---
    type "!AUTOTEST_LOG!"
    echo       --- Fin du compte rendu ---
) else (
    echo       [ATTENTION] Aucun rapport d'autotest produit ^(!AUTOTEST_LOG! absent^).
)
if not "!AUTOTEST_RC!"=="0" (
    echo [ERREUR] L'autotest de l'executable a echoue ^(code de sortie !AUTOTEST_RC!^).
    echo          Le solveur exact d'Expert ne fonctionne PAS dans l'executable
    echo          construit : highspy/numpy mal collectes par PyInstaller, ou
    echo          ressources web absentes. Expert retomberait silencieusement sur
    echo          l'ancienne recherche. Build REFUSE -- voir le compte rendu ci-dessus.
    popd & exit /b 1
)
echo       Autotest OK ^(code 0^) : le solveur exact fonctionne dans l'executable.

REM ===========================================================================
REM  ETAPE 6 : installeur Inno Setup + copie (local + worktree) + garde-fou
REM  Garde-fou sur l'INSTALLEUR FINAL COMPRESSE (Rummikub-Setup.exe).
REM  Distinct de l'etape 5 (dossier dist\ non compresse) : ici on mesure le .exe
REM  d'installation genere par Inno Setup, soit ~12,8 Mo au build 13 ; avec le
REM  solveur exact (issue #206) il grossira nettement (numpy + highspy).
REM  Fourchette de sanite ELARGIE (issue #208) : 5 Mo a 50 Mo (5242880 a
REM  52428800 octets). Valeurs PROVISOIRES a confirmer apres le premier build
REM  Windows avec highspy/numpy. Hors fourchette -> simple avertissement.
REM ===========================================================================
echo.
echo [6/9] Generation de l'installeur avec Inno Setup...
REM  Numero de build injecte dynamiquement (issue #91), sur le modele de Scrabble
REM  (/DScrabbleBuildInstalle) : EXEBUILD provient de version.json (etape 0bis).
REM  Le .iss n'a plus de #define hardcode ; le nom du Setup (Rummikub-Setup-vN)
REM  reste donc toujours en phase avec version.json.
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

echo       Copie de l'installeur vers le worktree ^(%ORIGDIR%\installeur\output^)...
if not exist "%ORIGDIR%\installeur\output" mkdir "%ORIGDIR%\installeur\output"
copy /y "%SETUP%" "%ORIGDIR%\installeur\output\%SETUPNAME%" >nul
if errorlevel 1 ( echo [ERREUR] Echec de la copie de l'installeur vers le worktree. & popd & exit /b 1 )

set "SETUPSIZE=0"
for /f "usebackq delims=" %%S in (`powershell -NoProfile -Command "(Get-Item '%SETUP%').Length"`) do set "SETUPSIZE=%%S"
echo       Taille de l'installeur %SETUPNAME% ^(compresse^) : %SETUPSIZE% octets
if %SETUPSIZE% LSS 5242880 echo       [ATTENTION] Installeur inhabituellement PETIT ^(attendu ~30 Mo, fourchette 5-50 Mo^).
if %SETUPSIZE% GTR 52428800 echo       [ATTENTION] Installeur inhabituellement GRAND ^(attendu ~30 Mo, fourchette 5-50 Mo^).

REM ===========================================================================
REM  ETAPE 7 : manifest.json + zip (dist\Rummikub\* + manifest.json)
REM  Le zip = dist\Rummikub\ + manifest.json, sans dossier englobant
REM  (l'updater Actualise l'extrait directement par-dessus le dossier installe).
REM  Nom toujours numerote (rummikub-vN.zip), publie ou non (issue #178) : le
REM  dossier fixe hors worktree (etape 8) a besoin du numero reel dans tous les
REM  modes, donc plus de nom fixe "rummikub.zip" pour les builds de test.
REM  Garde-fou de taille sur le zip : fourchette 5 Mo a 50 Mo (memes bornes que
REM  l'installeur compresse, elargies issue #208 pour numpy+highspy) -> hors
REM  fourchette = simple avertissement.
REM ===========================================================================
set "ZIPNAME=rummikub-v!EXEBUILD!.zip"
echo.
echo [7/9] Creation de manifest.json et de !ZIPNAME!...
> manifest.json echo {"build": !EXEBUILD!, "supprimer": []}
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
if %ZIPSIZE% LSS 5242880 echo       [ATTENTION] !ZIPNAME! inhabituellement PETIT ^(attendu ~30 Mo, fourchette 5-50 Mo^).
if %ZIPSIZE% GTR 52428800 echo       [ATTENTION] !ZIPNAME! inhabituellement GRAND ^(attendu ~30 Mo, fourchette 5-50 Mo^).

echo       Copie de !ZIPNAME! vers le worktree ^(%ORIGDIR%\installeur\output^)...
copy /y "installeur\output\!ZIPNAME!" "%ORIGDIR%\installeur\output\!ZIPNAME!" >nul
if errorlevel 1 ( echo [ERREUR] Echec de la copie de !ZIPNAME! vers le worktree. & popd & exit /b 1 )

popd

REM ===========================================================================
REM  ETAPE 8 : copie vers le dossier fixe hors worktree + publication eventuelle
REM  installeur\output est ignore par git : il disparait avec le worktree quand
REM  on le supprime (perte constatee sur l'installeur Rummikub v13, issue #178).
REM  On copie donc aussi l'installeur et l'archive dans un dossier fixe hors
REM  worktree, dans TOUS les modes (meme sans --publier), comme le font deja
REM  rebuild_scrabble.bat (issue #472) et rebuild_actualise.bat (issue #71).
REM  --publier ajoute en plus, apres cette copie, le calcul du SHA-256, l'ecriture
REM  de version.json et un commit local (jamais de git push).
REM ===========================================================================
echo.
echo [8/9] Copie vers %FIXEDSHARE% ...
if not exist "%FIXEDSHARE%" mkdir "%FIXEDSHARE%"
if not exist "%FIXEDSHARE%" (
    echo [ERREUR] Impossible de creer %FIXEDSHARE%.
    exit /b 1
)
copy /y "%ORIGDIR%\installeur\output\!SETUPNAME!" "%FIXEDSHARE%\!SETUPNAME!" >nul
if errorlevel 1 ( echo [ERREUR] Echec de la copie de !SETUPNAME! vers %FIXEDSHARE%. & exit /b 1 )
copy /y "%ORIGDIR%\installeur\output\!ZIPNAME!" "%FIXEDSHARE%\!ZIPNAME!" >nul
if errorlevel 1 ( echo [ERREUR] Echec de la copie de !ZIPNAME! vers %FIXEDSHARE%. & exit /b 1 )

set "FIXEDSETUPSIZE=0"
for /f "usebackq delims=" %%S in (`powershell -NoProfile -Command "(Get-Item '%FIXEDSHARE%\!SETUPNAME!').Length"`) do set "FIXEDSETUPSIZE=%%S"
set "FIXEDZIPSIZE=0"
for /f "usebackq delims=" %%S in (`powershell -NoProfile -Command "(Get-Item '%FIXEDSHARE%\!ZIPNAME!').Length"`) do set "FIXEDZIPSIZE=%%S"
echo       Copie vers %FIXEDSHARE% terminee.
echo       !SETUPNAME! : !FIXEDSETUPSIZE! octets
echo       !ZIPNAME! : !FIXEDZIPSIZE! octets

REM ===========================================================================
REM  ETAPE 8bis (--publier uniquement) : version.json + SHA-256 + commit local
REM  Reprend l'archive !ZIPNAME! deja construite et copiee ci-dessus (meme
REM  numero de build !EXEBUILD! depuis l'etape 0bis, pas de recalcul) pour :
REM    - calculer son SHA-256 ;
REM    - ecrire version.json a la racine du worktree (%ORIGDIR%) ;
REM    - commiter version.json EN LOCAL (jamais de git push).
REM  git push et la creation de la Release GitHub restent MANUELS (voir la fin).
REM ===========================================================================
if not "%PUBLIER%"=="1" goto fin_publier

echo.
echo [8bis/9] Mode --publier : version.json ^(build + SHA-256^) et commit local...

set "ZIPSHA="
for /f "usebackq delims=" %%H in (`powershell -NoProfile -Command "(Get-FileHash '%ORIGDIR%\installeur\output\!ZIPNAME!' -Algorithm SHA256).Hash.ToLower()"`) do set "ZIPSHA=%%H"
if not defined ZIPSHA (
    echo [ERREUR] Calcul du SHA-256 de !ZIPNAME! impossible.
    exit /b 1
)
echo       SHA-256 : !ZIPSHA!

> "%ORIGDIR%\version.json" echo {"build": !EXEBUILD!, "sha256": "!ZIPSHA!"}
echo       version.json ecrit : %ORIGDIR%\version.json

echo       Commit local de version.json dans le worktree...
git -C "%ORIGDIR%" add version.json
git -C "%ORIGDIR%" commit -m "Rummikub v!EXEBUILD! : version.json (build !EXEBUILD! + SHA-256 du zip)" -- version.json
if errorlevel 1 echo       [ATTENTION] git commit n'a rien commite ^(version.json inchange ?^).
:fin_publier

REM ===========================================================================
REM  ETAPE 9 : nettoyage du build local
REM ===========================================================================
echo.
echo [9/9] Nettoyage de %BUILDDIR% ...
rmdir /s /q "%BUILDDIR%"

echo.
echo ============================================================================
echo   Termine. Installeur : %ORIGDIR%\installeur\output\!SETUPNAME!
echo             Archive    : %ORIGDIR%\installeur\output\!ZIPNAME!
echo ============================================================================
echo   --- Copie hors worktree (issue #178) ---
echo   Inno Setup utilise : %ISCC%
echo   Dossier fixe        : %FIXEDSHARE%
echo     !SETUPNAME! : !FIXEDSETUPSIZE! octets
echo     !ZIPNAME! : !FIXEDZIPSIZE! octets
echo ============================================================================
if "%PUBLIER%"=="1" (
    echo.
    echo   --- PUBLICATION ^(--publier^) : etapes MANUELLES restantes ---
    echo   version.json a ete mis a jour ^(build !EXEBUILD!, SHA-256 du zip^) et
    echo   COMMITE EN LOCAL dans %ORIGDIR%.
    echo.
    echo   Le script ne fait JAMAIS de git push ni de gh release create. A la main :
    echo     1^) git -C "%ORIGDIR%" push
    echo     2^) Creer la Release GitHub ^(tag v!EXEBUILD!^) avec DEUX fichiers attaches :
    echo          - installeur\output\!SETUPNAME!
    echo          - installeur\output\!ZIPNAME!
    echo   ============================================================================
)
endlocal
exit /b 0
