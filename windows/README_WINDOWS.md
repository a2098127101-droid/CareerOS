# CareerOS Windows Desktop Startup — v0.6.1

## Recommended first-time setup

Double-click:

`windows/Setup_CareerOS_Windows.cmd`

It will:
1. Detect Python 3.11+;
2. Create `.venv`;
3. Install dependencies;
4. Create a Windows Desktop shortcut named `CareerOS`.

The Desktop shortcut now launches directly through:

`.venv\Scripts\pythonw.exe -> desktop_launcher.pyw`

It no longer depends on VBScript/Windows Script Host, avoiding UTF-8/ANSI parsing errors such as `800A0401`.

## Daily use

Double-click **CareerOS** on the Windows Desktop.

CareerOS will:
- start the local FastAPI service silently;
- select an available local port;
- open Microsoft Edge in App Mode as a standalone window.

No PowerShell command and no manual localhost URL are required.

## Repair an existing Desktop shortcut

Double-click:

`windows/Repair_CareerOS_Desktop.cmd`

This recreates the Desktop shortcut without reinstalling project data.

## Source-folder fallback launchers

You can also double-click:

- `Start CareerOS.cmd` — robust CMD launcher;
- `CareerOS Desktop.vbs` — compatibility wrapper only.

The VBS wrapper is intentionally ASCII-only in v0.6.1 to avoid Windows Script Host encoding problems.

## Build a real EXE on Windows

After setup, double-click:

`windows/Build_CareerOS_EXE.cmd`

Output:

`dist\CareerOS\CareerOS.exe`
