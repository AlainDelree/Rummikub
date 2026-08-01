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

[Setup]
; AppId identifie l'application de façon unique (NE PAS changer entre versions).
AppId={{1B579B83-44A3-46C3-9030-382F88704489}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
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

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Embarque tout le dossier onedir sauf les fichiers d'état utilisateur
; (config, journaux, base SQLite) qui seront recréés à l'exécution.
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "config.json,logs\*,data\parties.db,data\*.db"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Nettoie les données créées par l'application à la désinstallation.
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\data"
Type: files; Name: "{app}\config.json"
