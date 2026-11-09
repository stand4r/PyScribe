# PyScribe Windows installer

PyScribe is packaged as a PyInstaller **onedir** application and then installed by Inno Setup.

## Important
The computer where PyScribe is installed **does not need Python**.

The Python interpreter, Python DLLs, Qt/PyQt libraries and all application dependencies are bundled inside:

`C:\Program Files\PyScribe\_internal\`

The build computer does need Python + PyInstaller because they are used to create the self-contained application package. The target computer does not.

## Build
1. Run `build_exe.bat` from the project root.
2. Run `installer\build_installer.bat`.
3. Get `installer_output\PyScribe-Setup.exe`.

The installer:
- copies the complete `dist\PyScribe` directory;
- creates Start Menu and optional Desktop shortcuts;
- includes the bundled Python runtime, so no separate Python installation is needed.

Do not copy only `PyScribe.exe`: the `_internal` directory is part of the application.
