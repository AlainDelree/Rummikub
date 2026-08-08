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
; Actualise est désormais une instance PARTAGÉE entre toutes les applications
; (auparavant une instance par application : {sd}\Actualise_Rummikub). Le
; dossier {sd}\Actualise héberge l'updater et les fichiers de configuration
; config_<app>.json / config_actualise.json.
#define MyActualiseDir "{sd}\Actualise"

[Setup]
; AppId identifie l'application de façon unique (NE PAS changer entre versions).
AppId={{1B579B83-44A3-46C3-9030-382F88704489}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Droits administrateur requis : l'installation dépose l'instance Actualise
; partagée dans {sd}\Actualise (= C:\Actualise), à la racine du disque système,
; protégée en écriture pour les utilisateurs standards. PrivilegesRequired=lowest
; échouait donc à créer ce dossier (Actualise non déployé, raccourci pointant
; vers une installation incorrecte). Avec PrivilegesRequired=admin,
; {autopf}/{autodesktop}/{autoprograms} résolvent respectivement vers
; C:\Program Files, le Bureau commun et le menu Démarrer "tous les utilisateurs",
; et l'écriture dans C:\Actualise devient possible.
PrivilegesRequired=admin
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
; PAS de flag ignoreversion ici : instance partagée, on laisse Inno Setup
; comparer les versions et ne remplacer Actualise.exe (et son runtime) que si
; la version embarquée est plus récente que celle déjà installée par une autre
; application (ex. Scrabble). Évite d'écraser une version d'Actualise plus
; récente déjà présente.
Source: "{#MyActualiseSrcDir}\*"; DestDir: "{#MyActualiseDir}"; Flags: recursesubdirs createallsubdirs

[Dirs]
Name: "{#MyActualiseDir}"
Name: "{#MyActualiseDir}\attente"

[Icons]
; Les raccourcis pointent vers Actualise.exe (jamais directement vers
; Rummikub.exe) : Actualise met Rummikub à jour depuis les GitHub Releases
; avant de le lancer, à chaque démarrage. {autoprograms} (et non {group}) reste
; valide avec PrivilegesRequired=admin : il résout vers le menu Démarrer commun
; (tous les utilisateurs), ce qui est le comportement attendu.
; Parameters "--config rummikub" : instance Actualise partagée, on précise
; quelle application lancer/mettre à jour (lit config_rummikub.json).
Name: "{autoprograms}\{#MyAppName}"; Filename: "{#MyActualiseDir}\{#MyActualiseExeName}"; Parameters: "--config rummikub"; IconFilename: "{app}\{#MyAppIcoName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{#MyActualiseDir}\{#MyActualiseExeName}"; Parameters: "--config rummikub"; IconFilename: "{app}\{#MyAppIcoName}"

[Code]
// Actualise est une instance PARTAGÉE ({sd}\Actualise) : chaque application y
// dépose son propre fichier config_<app>.json, plus un config_actualise.json
// commun à l'updater. Ces fichiers sont consommés par Actualise.exe au
// lancement pour savoir quel dépôt GitHub surveiller, où est installée
// l'application et où stocker les archives téléchargées.
function EchapperJSON(const Texte: String): String;
begin
  Result := Texte;
  StringChangeEx(Result, '\', '\\', True);
end;

// config_rummikub.json : configuration propre à Rummikub. Toujours (ré)écrit,
// il remplace l'ancien config.json de l'instance dédiée.
procedure CreerConfigRummikub();
var
  DossierActualise, RepertoireInstallation, Contenu: String;
begin
  DossierActualise := ExpandConstant('{#MyActualiseDir}') + '\';
  RepertoireInstallation := ExpandConstant('{app}') + '\';

  Contenu :=
    '{' + #13#10 +
    '  "nom": "Rummikub",' + #13#10 +
    '  "depot_github": "AlainDelree/Rummikub",' + #13#10 +
    '  "build_installe": 5,' + #13#10 +
    '  "repertoire_installation": "' + EchapperJSON(RepertoireInstallation) + '",' + #13#10 +
    '  "executable": "Rummikub.exe",' + #13#10 +
    '  "icone": "' + EchapperJSON(ExpandConstant('{app}') + '\rummikub.ico') + '",' + #13#10 +
    '  "topic_ntfy": "hyppocampe-rummikub-QMJ7oH"' + #13#10 +
    '}' + #13#10;

  SaveStringToFile(DossierActualise + 'config_rummikub.json', Contenu, False);
end;

// config_actualise.json : configuration commune de l'updater. Écrit UNIQUEMENT
// s'il n'existe pas déjà, afin de ne pas écraser celui qu'une autre application
// (ex. Scrabble) aurait déjà déposé dans l'instance partagée.
procedure CreerConfigActualise();
var
  DossierActualise, ZoneAttente, Contenu: String;
begin
  DossierActualise := ExpandConstant('{#MyActualiseDir}') + '\';
  if FileExists(DossierActualise + 'config_actualise.json') then
    exit;

  ZoneAttente := DossierActualise + 'attente\';

  Contenu :=
    '{' + #13#10 +
    '  "build_installe": 3,' + #13#10 +
    '  "depot_github": "AlainDelree/Actualise",' + #13#10 +
    '  "zone_attente": "' + EchapperJSON(ZoneAttente) + '"' + #13#10 +
    '}' + #13#10;

  SaveStringToFile(DossierActualise + 'config_actualise.json', Contenu, False);
end;

// actualise_path.txt : dépose dans {app} le chemin de l'instance Actualise
// partagée, pour que Rummikub sache où la trouver au démarrage.
procedure EcrireActualisePath();
begin
  SaveStringToFile(ExpandConstant('{app}') + '\actualise_path.txt',
    ExpandConstant('{#MyActualiseDir}') + '\', False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  AncienDossier: String;
begin
  if CurStep = ssPostInstall then
  begin
    // Migration instance dédiée -> instance partagée : supprime entièrement
    // l'ancien dossier {sd}\Actualise_Rummikub s'il subsiste, AVANT d'écrire
    // les nouvelles configurations dans {sd}\Actualise.
    AncienDossier := ExpandConstant('{sd}\Actualise_Rummikub');
    if DirExists(AncienDossier) then
      DelTree(AncienDossier, True, True, True);

    CreerConfigRummikub();
    CreerConfigActualise();
    EcrireActualisePath();
  end;
end;

// Désinstallation : ne pas supprimer aveuglément l'instance partagée
// {sd}\Actualise (d'autres applications peuvent l'utiliser). On ne la retire
// que si plus aucun config_*.json n'y subsiste.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DossierActualise: String;
  FindRec: TFindRec;
  ResteConfig: Boolean;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DossierActualise := ExpandConstant('{#MyActualiseDir}') + '\';
    // Retire notre propre configuration (au cas où [UninstallDelete] ne
    // l'aurait pas encore traitée), puis vérifie s'il reste des config_*.json.
    DeleteFile(DossierActualise + 'config_rummikub.json');

    ResteConfig := False;
    if FindFirst(DossierActualise + 'config_*.json', FindRec) then
    begin
      try
        ResteConfig := True;
      finally
        FindClose(FindRec);
      end;
    end;

    if not ResteConfig then
      DelTree(ExpandConstant('{#MyActualiseDir}'), True, True, True);
  end;
end;

[UninstallDelete]
; Nettoie les données créées par l'application à la désinstallation.
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\data"
Type: files; Name: "{app}\config.json"
Type: files; Name: "{app}\actualise_path.txt"
; Instance partagée : on retire UNIQUEMENT la configuration propre à Rummikub.
; Le dossier {#MyActualiseDir} lui-même n'est PAS supprimé ici (voir
; CurUninstallStepChanged, qui ne le retire que si plus aucun config_*.json
; n'y subsiste).
Type: files; Name: "{#MyActualiseDir}\config_rummikub.json"
