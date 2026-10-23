; Inno Setup 6 script for UWCC Control Center (Windows).
; Compiled by build_windows.ps1:
;   ISCC /DAppVersion=1.3.1 /DSrcDir=dist\ControlCenter /DOutDir=dist windows\ControlCenter.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SrcDir
  #define SrcDir "..\dist\ControlCenter"
#endif
#ifndef OutDir
  #define OutDir "..\dist"
#endif
#define AppName "UWCC Control Center"
#define RunName "UWCC Control Center"

[Setup]
AppId={{6B0E1F43-5C1D-4F0B-9E43-55A1C0C7D7A1}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=UWCC (open re-implementation)
AppPublisherURL=https://github.com/aspidovss/open-uniwill-cc
AppSupportURL=https://github.com/aspidovss/open-uniwill-cc/issues
AppUpdatesURL=https://github.com/aspidovss/open-uniwill-cc/releases
AppContact=OUCC@aspidov.ru
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutDir}
OutputBaseFilename=open-uniwill-cc-windows-{#AppVersion}-setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\ControlCenter.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesEnvironment=yes
CloseApplications=no
MinVersion=10.0

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"; LicenseFile: "..\uwccd\web\eula.en.txt"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"; LicenseFile: "..\uwccd\web\eula.ru.txt"

[CustomMessages]
en.TaskOEM=Disable the original Control Center service (GCUService) — recommended, two programs must not drive the same EC
ru.TaskOEM=Отключить службу оригинального Control Center (GCUService) — рекомендуется, две программы не должны управлять одним EC
en.TaskAuto=Start with Windows (hidden in the notification area)
ru.TaskAuto=Запускать вместе с Windows (скрыто в трее)
en.TaskPath=Add uwccctl to PATH
ru.TaskPath=Добавить uwccctl в PATH
en.Launch=Start Control Center
ru.Launch=Запустить Control Center
en.Drv=Installing the ACPI driver...
ru.Drv=Установка ACPI-драйвера...
en.Svc=Registering the service...
ru.Svc=Регистрация службы...

[Tasks]
Name: "oem"; Description: "{cm:TaskOEM}"
Name: "autostart"; Description: "{cm:TaskAuto}"
Name: "path"; Description: "{cm:TaskPath}"

[Files]
Source: "{#SrcDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\ControlCenter.exe"; Parameters: "--open"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

[Registry]
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#RunName}"; \
  ValueData: """{app}\ControlCenter.exe"""; Tasks: autostart; Flags: uninsdeletevalue
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "Path"; \
  ValueData: "{olddata};{app}"; Tasks: path; Check: NeedsAddPath(ExpandConstant('{app}'))

[Run]
Filename: "{sys}\sc.exe"; Parameters: "stop GCUService"; Flags: runhidden waituntilterminated; Tasks: oem
Filename: "{sys}\sc.exe"; Parameters: "config GCUService start= disabled"; Flags: runhidden waituntilterminated; Tasks: oem
Filename: "{sys}\pnputil.exe"; Parameters: "/add-driver ""{app}\driver\UWACPIDriver.inf"" /install"; \
  StatusMsg: "{cm:Drv}"; Flags: runhidden waituntilterminated; Check: NeedDriver
Filename: "{sys}\sc.exe"; Parameters: "create uwccd binPath= ""\""{app}\uwccd.exe\"""" start= auto DisplayName= ""UWCC Control Center service"""; \
  StatusMsg: "{cm:Svc}"; Flags: runhidden waituntilterminated; Check: not ServiceExists('uwccd')
Filename: "{sys}\sc.exe"; Parameters: "config uwccd binPath= ""\""{app}\uwccd.exe\"""" start= auto"; \
  Flags: runhidden waituntilterminated; Check: ServiceExists('uwccd')
Filename: "{sys}\sc.exe"; Parameters: "description uwccd ""Performance modes, fans, keyboard lighting, battery and liquid cooler for Uniwill/Tongfang laptops."""; \
  Flags: runhidden waituntilterminated
Filename: "{sys}\sc.exe"; Parameters: "failure uwccd reset= 86400 actions= restart/5000/restart/10000/restart/30000"; Flags: runhidden waituntilterminated
Filename: "{sys}\sc.exe"; Parameters: "start uwccd"; Flags: runhidden waituntilterminated
Filename: "{app}\ControlCenter.exe"; Description: "{cm:Launch}"; Flags: postinstall nowait runasoriginaluser

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im ControlCenter.exe /fi ""USERNAME ne SYSTEM"""; Flags: runhidden; RunOnceId: "KillTray"
Filename: "{sys}\sc.exe"; Parameters: "stop uwccd"; Flags: runhidden waituntilterminated; RunOnceId: "StopSvc"
Filename: "{cmd}"; Parameters: "/c timeout /t 2 /nobreak >nul"; Flags: runhidden waituntilterminated; RunOnceId: "Wait"
Filename: "{app}\uwccctl.exe"; Parameters: "release"; Flags: runhidden waituntilterminated; RunOnceId: "Release"
Filename: "{sys}\sc.exe"; Parameters: "delete uwccd"; Flags: runhidden waituntilterminated; RunOnceId: "DelSvc"
Filename: "{sys}\sc.exe"; Parameters: "config GCUService start= auto"; Flags: runhidden waituntilterminated; RunOnceId: "OemOn"
Filename: "{sys}\sc.exe"; Parameters: "start GCUService"; Flags: runhidden; RunOnceId: "OemStart"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
function ServiceExists(Name: String): Boolean;
var
  RC: Integer;
begin
  Result := Exec(ExpandConstant('{sys}\sc.exe'), 'query ' + Name, '', SW_HIDE, ewWaitUntilTerminated, RC) and (RC = 0);
end;

function NeedDriver: Boolean;
begin
  Result := (not ServiceExists('UWACPIDriver')) and FileExists(ExpandConstant('{app}\driver\UWACPIDriver.inf'));
end;

function NeedsAddPath(Dir: String): Boolean;
var
  Old: String;
begin
  if not RegQueryStringValue(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'Path', Old) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Old) + ';') = 0;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  RC: Integer;
begin
  { upgrade: close the tray and stop the service so the files can be replaced }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im ControlCenter.exe /fi "USERNAME ne SYSTEM"', '', SW_HIDE, ewWaitUntilTerminated, RC);
  if ServiceExists('uwccd') then
  begin
    Exec(ExpandConstant('{sys}\sc.exe'), 'stop uwccd', '', SW_HIDE, ewWaitUntilTerminated, RC);
    Sleep(2000);
  end;
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Path, Dir: String;
  P: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Dir := ExpandConstant('{app}');
    if RegQueryStringValue(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'Path', Path) then
    begin
      P := Pos(';' + Uppercase(Dir), Uppercase(Path));
      if P > 0 then
      begin
        Delete(Path, P, Length(Dir) + 1);
        RegWriteExpandStringValue(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'Path', Path);
      end;
    end;
    RegDeleteValue(HKCU, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run', '{#RunName}');
  end;
end;
