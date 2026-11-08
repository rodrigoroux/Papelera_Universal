[Setup]
AppId={{AD08A378-7696-44A8-9FF4-FCD661EC005C}
AppName=Papelera Universal OS
AppVersion=0.2
DefaultDirName={localappdata}\Programs\Papelera Universal OS
DefaultGroupName=Papelera Universal OS
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=PapeleraUniversalOS-Setup-x64
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\PapeleraUniversalOS.exe

[Files]
Source: "..\dist\PapeleraUniversalOS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Papelera Universal OS"; Filename: "{app}\PapeleraUniversalOS.exe"
Name: "{userdesktop}\Papelera Universal OS"; Filename: "{app}\PapeleraUniversalOS.exe"
