; -*- coding: utf-8 -*-
; Script Inno Setup pour Rummikub (adapté de installeur\scrabble.iss).
;
; Compilation (Windows, depuis la racine du dépôt) :
;     .tools\InnoSetup6\ISCC.exe installeur\rummikub.iss
;
; Produit C:\Temp\RummikubOutput\Rummikub-Setup.exe à partir du dossier
; onedir dist\Rummikub produit par PyInstaller (rummikub.spec).

#define MyAppName "Rummikub"
#define MyAppExeName "Rummikub.exe"
#define MyAppPublisher "Alain Delree"
#define MyAppVersion "1.0"
#define MyDistDir "..\dist\Rummikub"
; Actualise (dépôt AlainDelree/Actualise) est l'updater autonome qui met
; Rummikub à jour depuis les GitHub Releases avant de le lancer (même
; mécanisme que Scrabble). Le raccourci utilisateur doit pointer vers lui,
; jamais directement vers Rummikub.exe.
#define MyActualiseExeName "Actualise.exe"
; Icône affichée sur les raccourcis (Bureau/menu Démarrer), déployée dans
; {app} par la section [Files] ci-dessous : sans elle, les raccourcis pointant
; vers Actualise.exe afficheraient l'icône générique d'Actualise.
#define MyAppIcoName "rummikub.ico"
; Déposé par build\rebuild_rummikub.bat avant l'appel à ISCC (Actualise.exe +
; son dossier _internal\, runtime Python + DLL, mode PyInstaller --onedir).
#define MyActualiseSrcDir "C:\Temp\RummikubBuild\Actualise_dist"
#define MyActualiseDir "{sd}\Actualise"

[Setup]
; AppId identifie l'application de façon unique (NE PAS changer entre versions).
AppId={{1B579B83-44A3-46C3-9030-382F88704489}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Aucun droit administrateur requis : installation dans le profil utilisateur
; courant. Nécessaire pour qu'Actualise puisse écrire dans le dossier
; d'installation sans droits admin. Avec PrivilegesRequired=lowest,
; {autopf}/{autodesktop}/{autoprograms} résolvent respectivement vers
; %LOCALAPPDATA%\Programs, le Bureau et le menu Démarrer de l'utilisateur
; courant (pas les emplacements "tous les utilisateurs", qui nécessiteraient
; des droits admin).
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
SetupIconFile=..\assets\rummikub.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
OutputDir=C:\Temp\RummikubOutput
OutputBaseFilename=Rummikub-Setup
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Files]
; Embarque tout le dossier onedir sauf les fichiers d'état utilisateur
; (config, journaux, base SQLite) qui seront recréés à l'exécution.
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "config.json,logs\*,data\parties.db,data\*.db"
; Icône des raccourcis : rummikub.spec ne l'embarque pas dans dist\Rummikub
; (elle sert seulement d'icône à l'exe), on la déploie donc explicitement dans
; {app} pour que les raccourcis pointant vers Actualise.exe (voir [Icons])
; l'affichent.
Source: "..\assets\rummikub.ico"; DestDir: "{app}"; DestName: "{#MyAppIcoName}"; Flags: ignoreversion
; Actualise : updater autonome, installé à côté de Rummikub (pas dans {app})
; car il survit aux mises à jour/réinstallations de Rummikub lui-même. Copie
; récursive (Actualise.exe + _internal\, runtime Python + DLL, mode
; PyInstaller --onedir).
Source: "{#MyActualiseSrcDir}\*"; DestDir: "{#MyActualiseDir}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{#MyActualiseDir}"
Name: "{#MyActualiseDir}\attente"

[Icons]
; Les raccourcis pointent vers Actualise.exe (jamais directement vers
; Rummikub.exe) : Actualise met Rummikub à jour depuis les GitHub Releases
; avant de le lancer, à chaque démarrage. {autoprograms} (et non {group}) est
; requis avec PrivilegesRequired=lowest.
Name: "{autoprograms}\{#MyAppName}"; Filename: "{#MyActualiseDir}\{#MyActualiseExeName}"; IconFilename: "{app}\{#MyAppIcoName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{#MyActualiseDir}\{#MyActualiseExeName}"; IconFilename: "{app}\{#MyAppIcoName}"

[Code]
// Génère le config.json d'Actualise, consommé par Actualise.exe au
// lancement pour savoir quel dépôt GitHub surveiller, où est installé
// Rummikub et où stocker les archives téléchargées.
function EchapperJSON(const Texte: String): String;
begin
  Result := Texte;
  StringChangeEx(Result, '\', '\\', True);
end;

procedure CreerConfigActualise();
var
  DossierActualise, RepertoireInstallation, ZoneAttente, Contenu: String;
begin
  DossierActualise := ExpandConstant('{#MyActualiseDir}') + '\';
  RepertoireInstallation := ExpandConstant('{app}') + '\';
  ZoneAttente := DossierActualise + 'attente\';

  Contenu :=
    '{' + #13#10 +
    '  "actualise": {' + #13#10 +
    '    "build_installe": 1,' + #13#10 +
    '    "depot_github": "AlainDelree/Actualise"' + #13#10 +
    '  },' + #13#10 +
    '  "application_cible": {' + #13#10 +
    '    "nom": "Rummikub",' + #13#10 +
    '    "depot_github": "AlainDelree/Rummikub",' + #13#10 +
    '    "build_installe": 1,' + #13#10 +
    '    "repertoire_installation": "' + EchapperJSON(RepertoireInstallation) + '",' + #13#10 +
    '    "executable": "Rummikub.exe",' + #13#10 +
    '    "icone": "' + EchapperJSON(ExpandConstant('{app}') + '\rummikub.ico') + '"' + #13#10 +
    '  },' + #13#10 +
    '  "zone_attente": "' + EchapperJSON(ZoneAttente) + '",' + #13#10 +
    '  "topic_ntfy": ""' + #13#10 +
    '}' + #13#10;

  SaveStringToFile(DossierActualise + 'config.json', Contenu, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    CreerConfigActualise();
end;

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Nettoie les données créées par l'application à la désinstallation.
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\data"
Type: files; Name: "{app}\config.json"
