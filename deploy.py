# deploy.py
import os
import shutil
from pathlib import Path
import sys
from packaging.version import Version
import scripts.constants
from scripts.constants import (
    APP_NAME,
    APP_ICON,
    APP_VERSION,
    APP_SHORT_NAME,
    DEPLOY_INFO_PATH,
    write_json_file,
    read_json_file
)

# -----------------------------------------
# Load previous deploy info or initialize
if os.path.exists(DEPLOY_INFO_PATH):
    deploy_info = read_json_file(DEPLOY_INFO_PATH)
else:
    deploy_info = {
        "APP_NAME": APP_NAME,
        "APP_VERSION": APP_VERSION,
        "change_made": "patch"
    }

# Confirm version changes


def confirm_version(d_i):
    start = input(
        "What kind of changes have you made? (0: no changes, 1: major, 2: minor, 3: patch) > "
    )

    current_version = Version(d_i['APP_VERSION'])

    if start == '1':  # major
        new_version = f"{current_version.major + 1}.0.0"
        start_type = 'major'
    elif start == '2':  # minor
        new_version = f"{current_version.major}.{current_version.minor + 1}.0"
        start_type = 'minor'
    elif start == '3':  # patch
        new_version = f"{current_version.major}.{current_version.minor}.{current_version.micro + 1}"
        start_type = 'patch'
    elif start == '0':
        print("No changes made, exiting.")
        sys.exit()
    else:
        # Assume explicit version
        new_version = start.strip()
        start_type = 'explicit'

    d_i['APP_VERSION'] = new_version
    d_i['change_made'] = start_type
    return start_type


# Ask for version update
start = confirm_version(deploy_info)
APP_FULLNAME = f"{deploy_info['APP_NAME']} {deploy_info['APP_VERSION']}"

# NSIS installer template

NSIS_INSTALLER_TEMPLATE = r"""

!include "MUI2.nsh"
!include "nsDialogs.nsh"

Name "{APP_FULLNAME}"
OutFile "dist\{finished_app_installer}"
InstallDir "$LOCALAPPDATA\BM\{APP_SHORT_NAME}"
RequestExecutionLevel user  ; 🚫 No admin rights, per-user only

;--------------------------------
; Modern UI Settings
!define MUI_ABORTWARNING
!define MUI_ICON "{APP_ICON}"
!define MUI_UNICON "{APP_ICON}"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP ".\\imgs\\banner_h.bmp"
!define MUI_WELCOMEFINISHPAGE_BITMAP ".\\imgs\\banner_v.bmp"
!define MUI_UNFINISHPAGE_BITMAP ".\\imgs\\banner_v.bmp"
BrandingText "TNR Software"

; Finish Page Launch Configuration (Updated to use a function for reliability)
!define MUI_FINISHPAGE_RUN "Launch {APP_NAME}"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchApp
Function LaunchApp
    Exec '"$INSTDIR\\{APP_FULLNAME}.exe"'
FunctionEnd

;--------------------------------
; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH


!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH
!insertmacro MUI_LANGUAGE "English"

;--------------------------------
Section "Install"
    SetOutPath "$INSTDIR"
    File "dist\{APP_FULLNAME}\{APP_FULLNAME}.exe"
    File /r "dist\{APP_FULLNAME}\_internal"

    ; Create Start Menu shortcut (user only)
    CreateDirectory "$SMPROGRAMS\{APP_NAME}"
    CreateShortCut "$SMPROGRAMS\{APP_NAME}\{APP_NAME}.lnk" \
        "$INSTDIR\{APP_FULLNAME}.exe" "" "$INSTDIR\{APP_FULLNAME}.exe" 0

    ; Create Desktop shortcut (user only)
    CreateShortCut "$DESKTOP\{APP_NAME}.lnk" \
        "$INSTDIR\{APP_FULLNAME}.exe" "" "$INSTDIR\{APP_FULLNAME}.exe" 0

    ; Write uninstaller
    WriteUninstaller "$INSTDIR\Uninstall_{APP_SHORT_NAME}.exe"

    ; Add to Add/Remove Programs (per-user)
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}" "DisplayName" "{APP_NAME}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}" "DisplayVersion" "{APP_VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}" "UninstallString" "$INSTDIR\Uninstall_{APP_SHORT_NAME}.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}" "Publisher" "TNR Software"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}" "DisplayIcon" "$INSTDIR\{APP_FULLNAME}.exe"

    ; Set app environment variable (user only)
    WriteRegExpandStr HKCU "Environment" "{APP_SHORT_NAME}" "$INSTDIR"
    System::Call 'user32::SendMessageTimeout(i ${{HWND_BROADCAST}}, i ${{WM_SETTINGCHANGE}}, i 0, t "Environment", i 0, i 1000, *i .r0)'
SectionEnd

;--------------------------------
Section "Uninstall"
    
    ; Delete shortcuts
    Delete "$SMPROGRAMS\{APP_NAME}\{APP_NAME}.lnk"
    RMDir "$SMPROGRAMS\{APP_NAME}"
    Delete "$DESKTOP\{APP_NAME}.lnk"

    ; Delete uninstaller
    Delete "$INSTDIR\Uninstall_{APP_SHORT_NAME}.exe"

    ; Remove from Add/Remove Programs
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"

    ; Remove environment variable
    DeleteRegValue HKCU "Environment" "{APP_SHORT_NAME}"
    System::Call 'user32::SendMessageTimeout(i ${{HWND_BROADCAST}}, i ${{WM_SETTINGCHANGE}}, i 0, t "Environment", i 0, i 1000, *i .r0)'

    ; Remove install directory
    RMDir /r "$INSTDIR"
SectionEnd


"""
# Build executable

output_dir = Path("C:\\Users\\USER\\Documents\\PROGRAMMING\\FINISHED APPS")
output_dir.mkdir(exist_ok=True)


def build_exe(script_path="main.py", d_i=deploy_info):
    exe_dir = Path("dist")
    exe_dir.mkdir(exist_ok=True)
    cmd = f'pyinstaller --noconfirm -i "{APP_ICON}"'
    cmd += f' --add-data "{APP_ICON};data/imgs" -n "{APP_FULLNAME}"'
    cmd += f' -w --hide-console=hide-early "{script_path}"'
    print(cmd)
    os.system(cmd)
    for item in ["build", "__pycache__", f"{APP_FULLNAME}.spec"]:
        p = Path(item)
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file():
            p.unlink(missing_ok=True)
    return exe_dir /f"{APP_FULLNAME}"/ f"{APP_FULLNAME}.exe"

# Write NSIS script


def write_nsi(d_i=deploy_info):
    finished_app_installer = f"{APP_SHORT_NAME}_Installer_{d_i['APP_VERSION']}.exe"
    nsi_path = Path(f"{d_i['APP_NAME']}.nsi")
    with open(nsi_path, "w", encoding="utf-8") as f:
        f.write(NSIS_INSTALLER_TEMPLATE.format(
            APP_NAME=d_i['APP_NAME'],
            APP_VERSION=d_i['APP_VERSION'],
            APP_FULLNAME=APP_FULLNAME,
            APP_ICON=APP_ICON,
            APP_SHORT_NAME=APP_SHORT_NAME,
            finished_app_installer=finished_app_installer,
        ))
    print(f"NSIS script written: {nsi_path}")
    return nsi_path, finished_app_installer

# Compile installer


def compile_installer(nsi_path):
    os.system(f'makensis "{nsi_path}"')

# Main deployment flow

def update_version_number(num):
    try:
        with open(f"{scripts.constants.__file__}", "r") as r:
            lines = r.readlines()
            # print(lines)
            for i, line in enumerate(lines):
                if line.__contains__("APP_VERSION = "):
                    lines[i] = f'APP_VERSION = "{num}"\n'
                    break

            with open(f"{scripts.constants.__file__}", "w") as w:
                w.writelines(lines)
        print(f"Updated App version in constants.py to '{num}'")
    except Exception as e:
        print(f"Failed with constants.py: {e}")
        reminder_crucial()



def main():
    print(
        f"\n{'-'*60}\nMaking {start} changes to the app...\nVersion: {deploy_info['APP_VERSION']}\n{'-'*60}\n")

    update_version_number(deploy_info["APP_VERSION"])

    print("Building the executable...")
    exe_path = build_exe(d_i=deploy_info)
    print(f"Built exe: {exe_path}")

    print("Writing NSIS script...")
    nsi_path, finished_installer = write_nsi(d_i=deploy_info)

    compile_installer(nsi_path)
    print(f"Installer built successfully: '{finished_installer}'")

    
    installer_path = Path("dist") / finished_installer
    if installer_path.exists():
        shutil.move(str(installer_path), str(output_dir / finished_installer))
        print(f"Installer moved to: '{output_dir / finished_installer}'")
    else:
        print("Installer not found! Probably already moved or build failed.")


def reminder_crucial():
    print()
    print("*"*60)
    print("PLEASE ENSURE YOU UPDATE THE VERSION NUMBERS TO MATCH ALL "
          "THE RELEVANT FILES:")
    print(f"\t{scripts.constants.__file__}:36-40")
    print(f"APP_VERSION = {deploy_info['APP_VERSION']}")
    print("*"*60)
    print()

def open_output_folder(path):
    import os
    try:
        # This command uses the default application for the path, 
        # which is File Explorer for a folder.
        os.startfile(path)
    except FileNotFoundError:
        print(f"Error: Folder not found at {path}")
    # Downsides: This will not select/highlight a specific file. 
    # It only opens the folder.

if __name__ == "__main__":
    main()
    write_json_file(DEPLOY_INFO_PATH, deploy_info)
    open_output_folder(output_dir)
    # optionally modify the constants.py file after everydeploy
    # with the current deploy.
