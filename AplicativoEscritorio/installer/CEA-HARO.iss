#ifndef MyAppName
  #define MyAppName "CEA HARO"
#endif
#ifndef MyAppExeName
  #define MyAppExeName "CEA-HARO.exe"
#endif
#ifndef MyAppPublisher
  #define MyAppPublisher "CEA HARO"
#endif
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#ifndef MyDistDirName
  #define MyDistDirName "CEA-HARO"
#endif

[Setup]
AppId={{8D3DA6E4-0E8B-4AA0-9B8E-97FBD5F11D22}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename={#MyAppName}-Setup
SetupIconFile=..\src\miproyecto\media\LogoHARO.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
DisableWelcomePage=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear icono en el escritorio"; GroupDescription: "Tareas adicionales:"; Flags: unchecked

[Files]
; Empaqueta la carpeta generada por PyInstaller (modo onedir recomendado).
Source: "..\dist\{#MyDistDirName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
