; Inno Setup 6 script for UWCC Control Center (Windows).
; Compiled by build_windows.ps1, twice:
;   ISCC /DAppVersion=1.6.1 /DSrcDir=dist\ControlCenter /DOutDir=dist windows\ControlCenter.iss            non-free: OEM driver + WMI
;   ISCC /DAppVersion=1.6.1 /DSrcDir=dist\ControlCenter-free /DOutDir=dist /DFree windows\ControlCenter.iss  free: WMI only,
;     no proprietary files; the OEM driver can be put into C:\ProgramData\UWCC\driver by the user

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
#ifdef Free
  #define Edition " (free)"
  #define SetupName "open-uniwill-cc-windows-" + AppVersion + "-free-setup"
#else
  #define Edition ""
  #define SetupName "open-uniwill-cc-windows-" + AppVersion + "-setup"
#endif
#define RunName "UWCC Control Center"

[Setup]
AppId={{6B0E1F43-5C1D-4F0B-9E43-55A1C0C7D7A1}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}{#Edition}
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
OutputBaseFilename={#SetupName}
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
en.EcTitle=Embedded controller access
ru.EcTitle=Доступ к встроенному контроллеру
en.EcDesc=How Control Center reaches fans, modes, power limits and battery protection
ru.EcDesc=Как Control Center управляет вентиляторами, режимами, пределами мощности и защитой батареи
en.EcSub=Choose how the service talks to the embedded controller (EC). This can be changed later in EC Manager.
ru.EcSub=Выберите, как служба обращается к встроенному контроллеру (EC). Это можно изменить позже в менеджере EC.
en.EcAuto=OEM driver + WMI (recommended)
ru.EcAuto=OEM-драйвер + WMI (рекомендуется)
en.EcOem=OEM driver only
ru.EcOem=Только OEM-драйвер
en.EcWmi=WMI only - open implementation (not recommended, beta)
ru.EcWmi=Только WMI - открытая реализация (не рекомендуется, бета)
en.EcNote=OEM driver: the manufacturer's UWACPIDriver.sys, all functions. WMI: the Windows built-in driver, no proprietary files; about 125 ms per EC access, no liquid-cooling power boost (PWUP), approximate power limits (no SMRW). Documentation: github.com/aspidovss/open-uniwill-cc/tree/main/docs/EC
ru.EcNote=OEM-драйвер: UWACPIDriver.sys производителя, все функции. WMI: встроенный драйвер Windows, без проприетарных файлов; около 125 мс на обращение к EC, нет повышенной мощности с СЖО (PWUP), пределы мощности примерные (нет SMRW). Документация: github.com/aspidovss/open-uniwill-cc/tree/main/docs/EC
en.EcRed=WE DO NOT RECOMMEND the WMI implementation on platforms other than MAIBENBEN Tsunami X629 / Mechrevo Questyle 16 Super / XMG NEO 16 (E23).
ru.EcRed=НЕ РЕКОМЕНДУЕМ использовать реализацию через WMI на платформах, отличных от MAIBENBEN Tsunami X629 / Mechrevo Questyle 16 Super / XMG NEO 16 (E23).
en.EcRights=By choosing the OEM driver you confirm that you have the right to use this file (UWACPIDriver.sys, part of the laptop manufacturer's Control Center).
ru.EcRights=Выбирая OEM-драйвер, вы подтверждаете, что у вас есть право использовать этот файл (UWACPIDriver.sys, часть Control Center производителя ноутбука).
en.FreeNote=FREE BUILD: it does not contain the original OEM driver (UWACPIDriver.sys) and is distributed completely freely (open source, MIT licence). Without the driver the program uses the open WMI implementation (beta). Recommended: put the OEM driver of the manufacturer's Control Center (UWACPIDriver.inf, .sys, .cat) into C:\ProgramData\UWCC\driver — the installer and EC Manager install it from there.
ru.FreeNote=СВОБОДНАЯ СБОРКА: не содержит оригинального OEM-драйвера (UWACPIDriver.sys) и распространяется полностью свободно (открытый код, лицензия MIT). Без драйвера программа работает через открытую реализацию WMI (бета). Рекомендуем положить OEM-драйвер из Control Center производителя (UWACPIDriver.inf, .sys, .cat) в C:\ProgramData\UWCC\driver — установщик и менеджер EC установят его оттуда.
en.FreeFound=Driver files found in C:\ProgramData\UWCC\driver — they will be installed with the OEM option.
ru.FreeFound=Файлы драйвера найдены в C:\ProgramData\UWCC\driver — они будут установлены при выборе OEM.
en.FreeMissing=No driver files in C:\ProgramData\UWCC\driver yet (a driver installed by the manufacturer's Control Center is used if present). You can put them there later and install them in EC Manager.
ru.FreeMissing=В C:\ProgramData\UWCC\driver пока нет файлов драйвера (если драйвер уже установлен Control Center производителя, используется он). Их можно положить туда позже и установить в менеджере EC.
en.DrvRisk10=The OEM driver check: this driver version is not in the list of known versions (the signature is valid).%n%nI still want to use this driver and understand the risk — install it?
ru.DrvRisk10=Проверка OEM-драйвера: этой версии драйвера нет в списке известных (подпись действительна).%n%nЯ всё равно хочу использовать этот драйвер и понимаю риск — установить его?
en.DrvRisk11=The OEM driver check: the signature of the driver is not valid or could not be checked.%n%nI still want to use this driver and understand the risk — install it?
ru.DrvRisk11=Проверка OEM-драйвера: подпись драйвера недействительна или её не удалось проверить.%n%nЯ всё равно хочу использовать этот драйвер и понимаю риск — установить его?
en.DrvBad=The OEM driver package cannot be used (files missing or it is a driver for another device). It is not installed; the program uses WMI. Details: uwccctl driver-verify "FOLDER".
ru.DrvBad=Пакет OEM-драйвера нельзя использовать (не хватает файлов или это драйвер другого устройства). Он не установлен; программа работает через WMI. Подробности: uwccctl driver-verify "ПАПКА".
en.Svc=Registering the service...
ru.Svc=Регистрация службы...

[Tasks]
Name: "oem"; Description: "{cm:TaskOEM}"
Name: "autostart"; Description: "{cm:TaskAuto}"
Name: "path"; Description: "{cm:TaskPath}"

[Dirs]
#ifdef Free
Name: "{commonappdata}\UWCC\driver"; Flags: uninsneveruninstall
#endif

[Files]
Source: "{#SrcDir}\*"; DestDir: "{app}"; Excludes: "\driver\*"; Flags: ignoreversion recursesubdirs createallsubdirs
#ifdef Free
Source: "driver-folder-README.txt"; DestDir: "{commonappdata}\UWCC\driver"; DestName: "README.txt"; Flags: ignoreversion uninsneveruninstall
#endif
; the proprietary OEM driver is copied only when an OEM option is chosen (public builds have no driver folder)
Source: "{#SrcDir}\driver\*"; DestDir: "{app}\driver"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist; Check: UseOem

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
Filename: "{sys}\pnputil.exe"; Parameters: "/add-driver ""{code:DriverInf}"" /install"; \
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

[InstallDelete]
; WMI only: remove an OEM driver package copied by an earlier installation (the installed driver itself stays)
Type: filesandordirs; Name: "{app}\driver"; Check: not UseOem

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
var
  EcPage: TInputOptionWizardPage;

function EcChoice: String;
begin
  Result := 'auto';
  if EcPage = nil then
    Result := Lowercase(ExpandConstant('{param:ECPATH|auto}'))
  else if EcPage.Values[1] then
    Result := 'oem'
  else if EcPage.Values[2] then
    Result := 'wmi';
  if (Result <> 'auto') and (Result <> 'oem') and (Result <> 'wmi') then
    Result := 'auto';
end;

function UseOem: Boolean;
begin
  Result := EcChoice <> 'wmi';
end;

function DriverInf(Param: String): String;
begin
#ifdef Free
  Result := ExpandConstant('{commonappdata}\UWCC\driver\UWACPIDriver.inf');
#else
  Result := ExpandConstant('{app}\driver\UWACPIDriver.inf');
#endif
end;

procedure InitializeWizard;
var
  Note, Red, Rights: TNewStaticText;
  Def, Sub: String;
begin
  Sub := CustomMessage('EcSub');
#ifdef Free
  Sub := CustomMessage('FreeNote') + #13#10#13#10 + Sub;
#endif
  EcPage := CreateInputOptionPage(wpSelectTasks, CustomMessage('EcTitle'), CustomMessage('EcDesc'),
    Sub, True, False);
  EcPage.Add(CustomMessage('EcAuto'));
  EcPage.Add(CustomMessage('EcOem'));
  EcPage.Add(CustomMessage('EcWmi'));
  Def := Lowercase(ExpandConstant('{param:ECPATH|auto}'));
  EcPage.Values[0] := (Def <> 'oem') and (Def <> 'wmi');
  EcPage.Values[1] := Def = 'oem';
  EcPage.Values[2] := Def = 'wmi';
  EcPage.CheckListBox.Height := ScaleY(66);

  Note := TNewStaticText.Create(EcPage);
  Note.Parent := EcPage.Surface;
  Note.WordWrap := True;
  Note.Width := EcPage.SurfaceWidth;
  Note.Top := EcPage.CheckListBox.Top + EcPage.CheckListBox.Height + ScaleY(8);
  Note.Caption := CustomMessage('EcNote');
#ifdef Free
  if FileExists(ExpandConstant('{commonappdata}\UWCC\driver\UWACPIDriver.inf')) then
    Note.Caption := CustomMessage('FreeFound') + #13#10 + Note.Caption
  else
    Note.Caption := CustomMessage('FreeMissing') + #13#10 + Note.Caption;
#endif

  Red := TNewStaticText.Create(EcPage);
  Red.Parent := EcPage.Surface;
  Red.WordWrap := True;
  Red.Width := EcPage.SurfaceWidth;
  Red.Top := Note.Top + Note.Height + ScaleY(10);
  Red.Font.Color := clRed;
  Red.Font.Style := [fsBold];
  Red.Caption := CustomMessage('EcRed');

  Rights := TNewStaticText.Create(EcPage);
  Rights.Parent := EcPage.Surface;
  Rights.WordWrap := True;
  Rights.Width := EcPage.SurfaceWidth;
  Rights.Top := Red.Top + Red.Height + ScaleY(10);
  Rights.Caption := CustomMessage('EcRights');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Dir: String;
begin
  if CurStep = ssInstall then
  begin
    { the service applies this choice on its next start (setting ec_backend) and deletes the file }
    Dir := ExpandConstant('{commonappdata}\UWCC\data');
    ForceDirectories(Dir);
    SaveStringToFile(Dir + '\ec_backend.install', EcChoice, False);
  end;
end;

function ServiceExists(Name: String): Boolean;
var
  RC: Integer;
begin
  Result := Exec(ExpandConstant('{sys}\sc.exe'), 'query ' + Name, '', SW_HIDE, ewWaitUntilTerminated, RC) and (RC = 0);
end;

function NeedDriver: Boolean;
var
  RC: Integer;
begin
  Result := False;
  if not (UseOem and (not ServiceExists('UWACPIDriver')) and FileExists(DriverInf(''))) then
    exit;
  { minimal check before pnputil: files, INF for ACPI\INOU0000, signature, known SHA-256 (uwccd/drivercheck.py) }
  if not Exec(ExpandConstant('{app}\uwccctl.exe'), 'driver-verify "' + ExtractFileDir(DriverInf('')) + '"', '',
              SW_HIDE, ewWaitUntilTerminated, RC) then
    RC := 11;
  case RC of
    0: Result := True;
    10, 11: Result := SuppressibleMsgBox(CustomMessage('DrvRisk' + IntToStr(RC)), mbConfirmation,
                                         MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES;
  else
    SuppressibleMsgBox(CustomMessage('DrvBad'), mbError, MB_OK, IDOK);
  end;
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
