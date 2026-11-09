#define MyAppName "PyScribe"
; Single source of truth: the VERSION file in the project root. Bump it only
; there — the About dialog, updater and this installer all read that number.
#define MyAppVersion Trim(FileRead(FileOpen("..\VERSION")))
#define MyAppPublisher "PyScribe Development Team"
#define MyAppURL "https://github.com/stand4r/PyScribe"
#define MyAppExeName "PyScribe.exe"

#ifndef ReleaseBundle
  #define ReleaseBundle "..\dist\PyScribe"
#endif

[Setup]
AppId={{D4B1C3A2-8D6B-4F22-9D53-PYSCRIBE0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\installer_output
OutputBaseFilename=PyScribe-Setup-v{#MyAppVersion}
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\src\PyScribe.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Uninstallable=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#ReleaseBundle}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
; "Открыть с помощью" (per-user, no admin rights needed).
Root: HKCU; Subkey: "Software\Classes\Applications\PyScribe"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#MyAppName}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Applications\PyScribe\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\PyScribe.File\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey
; Explorer context menu: any file, any folder, folder background.
Root: HKCU; Subkey: "Software\Classes\*\shell\PyScribe"; ValueType: string; ValueName: "MUIVerb"; ValueData: "Открыть в PyScribe"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\*\shell\PyScribe\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\Directory\shell\PyScribe"; ValueType: string; ValueName: "MUIVerb"; ValueData: "Открыть папку в PyScribe"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Directory\shell\PyScribe\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\PyScribe"; ValueType: string; ValueName: "MUIVerb"; ValueData: "Открыть в PyScribe"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\PyScribe\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%V"""
Root: HKCU; Subkey: "Software\Classes\*\OpenWithProgids"; ValueType: string; ValueName: "PyScribe.File"; ValueData: ""

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
