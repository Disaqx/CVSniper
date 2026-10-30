; CVSniper - Windows installer (Inno Setup 6)
;
; Do not compile this by hand: installer\build_installer.ps1 stages the files
; it needs (the app from `git archive`, a private copy of Python with every
; dependency already installed) and then calls ISCC with the paths below.
;
; What the user gets:
;   - CVSniper in the Start menu (and optionally the desktop), like any app
;   - an entry in Settings > Apps > Installed apps, so it can be uninstalled
;   - no Python, pip or terminal: the bundled Python lives in {app}\python
;   - per-user install, no administrator prompt
;
; The config files, CSVs, resumes and logs the bot writes are NOT part of the
; installer, so an upgrade never touches them; the uninstaller asks whether to
; delete them.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef AppDir
  #define AppDir "..\build\app"
#endif
#ifndef PythonDir
  #define PythonDir "..\build\python"
#endif
#define AppName "CVSniper"

[Setup]
; Never change AppId: it is how Windows recognises an upgrade of the same app.
AppId={{40788D52-54D8-43FC-A8CA-28FA142558D4}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Disaqx
AppPublisherURL=https://github.com/Disaqx/CVSniper
AppSupportURL=https://github.com/Disaqx/CVSniper/issues
DefaultDirName={localappdata}\Programs\{#AppName}
; The folder is fixed on purpose: the uninstaller deletes the user's data
; folders inside it on request, and that must never point at, say, Documents.
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=CVSniper-Setup-{#AppVersion}
SetupIconFile=cvsniper.ico
UninstallDisplayIcon={app}\cvsniper.ico
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
spanish.NoChrome=No se encontró Google Chrome, y CVSniper lo necesita para funcionar.%n%n¿Quieres abrir la página de descarga de Chrome? La instalación de CVSniper continuará de todos modos.
english.NoChrome=Google Chrome was not found, and CVSniper needs it to work.%n%nOpen the Chrome download page? CVSniper will be installed either way.
spanish.AskDeleteData=¿Borrar también tus datos de CVSniper?%n%nIncluye tu configuración (datos personales, claves de API), el historial de postulaciones, los CVs generados y los registros.%n%nElige No si piensas volver a instalarlo y quieres conservarlos.
english.AskDeleteData=Also delete your CVSniper data?%n%nThat is your configuration (personal details, API keys), the application history, generated resumes and logs.%n%nChoose No if you plan to reinstall and want to keep them.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; An upgrade replaces the bundled Python wholesale, so no stale package from
; the previous version can linger in site-packages.
Type: filesandordirs; Name: "{app}\python"

[Files]
; Only what the bot runs: dev scripts, tests and docs stay out.
Source: "{#AppDir}\*"; DestDir: "{app}"; Excludes: "\installer,\tests,\docs,\setup,\.github,\INICIAR.bat,\start.sh,\.gitattributes,\.gitignore,\CLAUDE.md"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#PythonDir}\*"; DestDir: "{app}\python"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "CVSniper.cmd"; DestDir: "{app}"; Flags: ignoreversion
Source: "cvsniper.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Minimised: the console only carries the log, the bot itself is its own window.
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\CVSniper.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\cvsniper.ico"; Flags: runminimized
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\CVSniper.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\cvsniper.ico"; Flags: runminimized; Tasks: desktopicon

[Run]
Filename: "{app}\CVSniper.cmd"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent shellexec runminimized

[Code]
var
  DeleteUserData: Boolean;

function ChromeInstalled(): Boolean;
begin
  Result :=
    RegKeyExists(HKLM, 'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe') or
    RegKeyExists(HKCU, 'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe') or
    FileExists(ExpandConstant('{commonpf64}\Google\Chrome\Application\chrome.exe')) or
    FileExists(ExpandConstant('{commonpf32}\Google\Chrome\Application\chrome.exe')) or
    FileExists(ExpandConstant('{localappdata}\Google\Chrome\Application\chrome.exe'));
end;

function InitializeSetup(): Boolean;
var
  ErrorCode: Integer;
begin
  Result := True;
  if not ChromeInstalled() then
    if SuppressibleMsgBox(CustomMessage('NoChrome'), mbConfirmation, MB_YESNO, IDNO) = IDYES then
      ShellExec('open', 'https://www.google.com/chrome/', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  // A silent uninstall (scripts, upgrades) never deletes personal data.
  DeleteUserData := (not UninstallSilent()) and
    (MsgBox(CustomMessage('AskDeleteData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES);
end;

// Python writes __pycache__ folders next to the code at run time. They are not
// in the uninstall log, so without this every folder holding one would be
// left behind, half-empty.
procedure DeletePycache(Dir: String);
var
  FindRec: TFindRec;
begin
  if FindFirst(Dir + '\*', FindRec) then
  try
    repeat
      if (FindRec.Name <> '.') and (FindRec.Name <> '..') and
         ((FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0) then
      begin
        if CompareText(FindRec.Name, '__pycache__') = 0 then
          DelTree(Dir + '\' + FindRec.Name, True, True, True)
        else
          DeletePycache(Dir + '\' + FindRec.Name);
      end;
    until not FindNext(FindRec);
  finally
    FindClose(FindRec);
  end;
end;

procedure DeleteStoredCredential(Target: String);
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\cmdkey.exe'), '/delete:' + Target, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  App: String;
begin
  App := ExpandConstant('{app}');
  if CurUninstallStep = usUninstall then
  begin
    // Before the uninstall log runs, so the folders it then finds empty are removed.
    DelTree(App + '\python', True, True, True);
    DeletePycache(App);
  end
  else if CurUninstallStep = usPostUninstall then
  begin
    if DeleteUserData then
    begin
      // Only the folders the bot writes to: never a blanket DelTree of {app}.
      DelTree(App + '\config', True, True, True);
      DelTree(App + '\all excels', True, True, True);
      DelTree(App + '\all resumes', True, True, True);
      DelTree(App + '\logs', True, True, True);
      DeleteFile(App + '\qa_database.json');
      // The LinkedIn password and API key, kept in Windows Credential Manager
      // by modules\credentials.py (keyring names them service / user@service).
      DeleteStoredCredential('CVSniper');
      DeleteStoredCredential('password@CVSniper');
      DeleteStoredCredential('llm_api_key@CVSniper');
    end;
    RemoveDir(App);
  end;
end;
