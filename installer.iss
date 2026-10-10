; 笔画输入法 安装程序
; 使用 Inno Setup 编译

#define MyAppName "笔画输入法"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Stroke Input"
#define MyAppExeName "笔画输入法.exe"

[Setup]
AppId={{B2A1D5E6-3F4A-4C1B-9A5D-7E8F6C9D0A1B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=LICENSE
InfoBeforeFile=NOTICE
OutputDir=Output
OutputBaseFilename=笔画输入法-安装包
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标:"; Flags: unchecked
Name: "startupicon"; Description: "开机自动启动"; GroupDescription: "启动:"; Flags: unchecked

[Files]
Source: "dist\笔画输入法\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
Source: "LICENSE"; DestDir: "{app}"
Source: "NOTICE"; DestDir: "{app}"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\配置文件"; Filename: "{app}\config.json"
Name: "{group}\许可协议"; Filename: "{app}\LICENSE"
Name: "{group}\第三方版权声明"; Filename: "{app}\NOTICE"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent
