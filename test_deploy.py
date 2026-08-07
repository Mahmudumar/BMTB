# test_deploy.py
# Script to build the executable and create a desktop shortcut on Windows

# It is a script that just is for quick test.
# now we want to make a proper installer with NSIS in a new deploy.py file

import os
import shutil

from pathlib import Path
import win32com.client


from scripts.constants import APP_NAME


def build_exe(script_path):
    script_path = Path(script_path).resolve()
    cmd = f'pyinstaller --noconfirm -n "{APP_NAME}" --noconsole --onefile "{script_path}"'
    print(cmd)
    os.system(cmd)

    # cleanup unwanted artifacts
    for item in ["build", "__pycache__", f"{APP_NAME}.spec"]:
        p = Path(item)
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file():
            p.unlink(missing_ok=True)
# dist\Thought Book\Thought Book.exe
    return script_path.parent / "dist" / (APP_NAME + ".exe")


def create_shortcut(target, shortcut_path, hotkey=None, workdir=None, description="", icon=None):
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortcut(str(shortcut_path))
    shortcut.TargetPath = str(target)
    shortcut.WorkingDirectory = str(workdir or Path(target).parent)
    shortcut.Description = description
    if hotkey:
        shortcut.Hotkey = hotkey  # format "CTRL+ALT+N"

    if icon:
        # icon can be "C:\\Windows\\System32\\shell32.dll,XX"
        shortcut.IconLocation = icon

    shortcut.save()
    return shortcut_path


def main():
    # 1. Build exe
    exe_path = build_exe("note_app.py")
    print(f"Built exe at: {exe_path}")

    # 2. Create shortcut on Desktop
    desktop = Path.home() / "Desktop"
    shortcut_path = desktop / f"{APP_NAME}.lnk"
    create_shortcut(
        target=exe_path,
        shortcut_path=shortcut_path,
        hotkey="CTRL+ALT+T",  # Control + Alt + T (think)
        description="Launch Thought Book: A place to think in peace",
        # 172 = “computer with speech bubble” on most systems
        icon=r"C:\Windows\System32\shell32.dll,172"
    )
    print(f"Shortcut created: {shortcut_path}")


if __name__ == "__main__":
    main()
