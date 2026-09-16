; Inno Setup script for Camera Count Tool.
;
; Built by packaging/build_installer.py, which fills in the version and paths.
; The installer only copies files and creates shortcuts: it installs no driver,
; no service, and no startup entry, and it touches nothing outside its own
; install directory.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceFolder
  #define SourceFolder "output\CameraCountTool"
#endif
#ifndef OutputFolder
  #define OutputFolder "output"
#endif

#define AppName "Camera Count Tool"
#define AppPublisher "Camera Count Tool contributors"
#define AppUrl "https://github.com/Osama01Anwar/camera-count-tool"
#define GuiExe "CameraCountTool.exe"

[Setup]
AppId={{7C4F5A18-2B0E-4A2E-9E1C-0F2C5B9D3A61}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases
DefaultDirName={autopf}\CameraCountTool
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir={#OutputFolder}
OutputBaseFilename=CameraCountTool-{#AppVersion}-windows-x64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
MinVersion=10.0
UninstallDisplayIcon={app}\{#GuiExe}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "addtopath"; Description: "Add the camera-count command to PATH"; GroupDescription: "Command line:"; Flags: unchecked

[Files]
Source: "{#SourceFolder}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#GuiExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#GuiExe}"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; \
    ValueData: "{olddata};{app}"; Check: NeedsAddPath('{app}'); Tasks: addtopath

[Run]
Filename: "{app}\{#GuiExe}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
function NeedsAddPath(Param: string): Boolean;
var
  OriginalPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OriginalPath) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + ExpandConstant(Param) + ';', ';' + OriginalPath + ';') = 0;
end;
