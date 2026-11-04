; Instalador de SpiderFinance (Inno Setup 6). Se compila desde GitHub Actions.
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{7B1E5C2A-3D4F-4E6A-9C1B-0A1B2C3D4E5F}
AppName=SpiderFinance
AppVersion={#AppVersion}
AppPublisher=SpiderFinance
DefaultDirName={autopf32}\SpiderFinance
DefaultGroupName=SpiderFinance
DisableProgramGroupPage=yes
OutputDir=..\salida
OutputBaseFilename=SpiderFinance-Setup
SetupIconFile=..\assets\spiderfinance.ico
UninstallDisplayIcon={app}\SpiderFinance.exe
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un icono en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\SpiderFinance\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\SpiderFinance"; Filename: "{app}\SpiderFinance.exe"
Name: "{autodesktop}\SpiderFinance"; Filename: "{app}\SpiderFinance.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SpiderFinance.exe"; Description: "Abrir SpiderFinance ahora"; Flags: nowait postinstall skipifsilent
