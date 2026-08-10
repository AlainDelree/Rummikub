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
; Numéro de build installé. Injecté dynamiquement par build\rebuild_rummikub.bat
; via ISCC (/DRummikubBuildInstalle=<build>), valeur issue de version.json (comme
; Scrabble avec /DScrabbleBuildInstalle). Il alimente à la fois :
;   - le nom du fichier Setup (OutputBaseFilename ci-dessous : Rummikub-Setup-vN) ;
;   - les métadonnées de Rummikub-Setup.exe (section [Setup], VersionInfo*
;     ci-dessous : clic droit -> Propriétés -> Détails -> Version du fichier) ;
;   - le champ build_installe de config_rummikub.json ([Code], procédure
;     CreerConfigRummikub) consommé par l'updater Actualise.
; Repli de secours UNIQUEMENT pour une compilation manuelle isolée (ISCC lancé à
; la main, sans /D) : en pipeline normal la valeur vient toujours du flag /D.
; Plus de numéro à bumper ici : la source unique est désormais version.json.
#ifndef RummikubBuildInstalle
  #define RummikubBuildInstalle "1"
#endif
#define MyDistDir "..\dist\Rummikub"
; Icône affichée sur les raccourcis (Bureau/menu Démarrer), déployée dans
; {app} par la section [Files] ci-dessous et référencée par IconFilename dans
; [Icons].
#define MyAppIcoName "rummikub.ico"
; Actualise est désormais une instance PARTAGÉE entre toutes les applications
; (auparavant une instance par application : C:\Actualise_Rummikub). Le
; dossier C:\Actualise héberge l'updater et les fichiers de configuration
; config_<app>.json / config_actualise.json.
; NB : chemin codé en dur (C:\Actualise) et NON {sd}\Actualise. Dans un
; #define InnoSetup, {sd} est traité comme une chaîne littérale par le
; préprocesseur : réinjecté tel quel dans les sections [Files]/[Dirs]/[Icons],
; il n'était pas résolu et le setup installait dans un dossier erroné. Le
; disque système est C: sur toutes les cibles ; on le fige donc explicitement.
#define MyActualiseDir "C:\Actualise"
; Ancienne instance dédiée à Rummikub, purgée à l'installation (voir [Code],
; CurStepChanged). Codé en dur pour la même raison que MyActualiseDir.
#define MyOldActualiseDir "C:\Actualise_Rummikub"

[Setup]
; AppId identifie l'application de façon unique (NE PAS changer entre versions).
AppId={{1B579B83-44A3-46C3-9030-382F88704489}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Droits administrateur requis : l'installation dépose l'instance Actualise
; partagée dans C:\Actualise, à la racine du disque système,
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
OutputBaseFilename=Rummikub-Setup-v{#RummikubBuildInstalle}
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
; Métadonnées de l'exécutable d'installation Rummikub-Setup.exe (clic droit ->
; Propriétés -> Détails). VersionInfoVersion => champ « Version du fichier »,
; permettant de distinguer visuellement deux builds sans ouvrir le fichier.
VersionInfoVersion={#RummikubBuildInstalle}.0.0.0
VersionInfoProductVersion={#RummikubBuildInstalle}.0.0.0
VersionInfoProductName={#MyAppName}
VersionInfoDescription=Rummikub Setup build {#RummikubBuildInstalle}
VersionInfoCompany={#MyAppPublisher}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Files]
; Embarque tout le dossier onedir sauf les fichiers d'état utilisateur
; (config, journaux, base SQLite) qui seront recréés à l'exécution.
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "config.json,logs\*,data\parties.db,data\*.db"
; Icône des raccourcis : rummikub.spec ne l'embarque pas dans dist\Rummikub
; (elle sert seulement d'icône à l'exe), on la déploie donc explicitement dans
; {app} pour la référencer via IconFilename dans [Icons].
Source: "..\assets\rummikub.ico"; DestDir: "{app}"; DestName: "{#MyAppIcoName}"; Flags: ignoreversion

[Dirs]
Name: "{#MyActualiseDir}"

[Icons]
; Les raccourcis pointent directement vers Rummikub.exe dans {app}.
; {autoprograms} (et non {group}) reste valide avec PrivilegesRequired=admin :
; il résout vers le menu Démarrer commun (tous les utilisateurs), ce qui est le
; comportement attendu.
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppIcoName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppIcoName}"

[Code]
// Actualise est une instance PARTAGÉE (C:\Actualise) : chaque application y
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
    '  "build_installe": {#RummikubBuildInstalle},' + #13#10 +
    '  "repertoire_installation": "' + EchapperJSON(RepertoireInstallation) + '",' + #13#10 +
    '  "executable": "Rummikub.exe",' + #13#10 +
    '  "icone": "' + EchapperJSON(ExpandConstant('{app}') + '\rummikub.ico') + '",' + #13#10 +
    '  "topic_ntfy": "hyppocampe-rummikub-QMJ7oH"' + #13#10 +
    '}' + #13#10;

  SaveStringToFile(DossierActualise + 'config_rummikub.json', Contenu, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  AncienDossier: String;
begin
  if CurStep = ssPostInstall then
  begin
    // Migration instance dédiée -> instance partagée : supprime entièrement
    // l'ancien dossier C:\Actualise_Rummikub s'il subsiste, AVANT d'écrire
    // les nouvelles configurations dans C:\Actualise.
    AncienDossier := ExpandConstant('{#MyOldActualiseDir}');
    if DirExists(AncienDossier) then
      DelTree(AncienDossier, True, True, True);

    CreerConfigRummikub();
  end;
end;

// Désinstallation : ne pas supprimer aveuglément l'instance partagée
// C:\Actualise (d'autres applications peuvent l'utiliser). On ne la retire
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
