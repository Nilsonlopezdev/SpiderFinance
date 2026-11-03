; Instalador de TELARANA (Inno Setup 6). Se compila desde GitHub Actions.
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{7B1E5C2A-3D4F-4E6A-9C1B-0A1B2C3D4E5F}
AppName=TELARANA
AppVersion={#AppVersion}
AppPublisher=TELARANA
DefaultDirName={autopf32}\TELARANA
DefaultGroupName=TELARANA
DisableProgramGroupPage=yes
OutputDir=..\salida
OutputBaseFilename=TELARANA-Setup
SetupIconFile=..\assets\telarana.ico
UninstallDisplayIcon={app}\TELARANA.exe
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un icono en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\TELARANA\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\TELARANA"; Filename: "{app}\TELARANA.exe"
Name: "{autodesktop}\TELARANA"; Filename: "{app}\TELARANA.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TELARANA.exe"; Description: "Abrir TELARANA ahora"; Flags: nowait postinstall skipifsilent
