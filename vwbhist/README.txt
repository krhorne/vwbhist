vwbhist 0.9 beta - compare and version history for Perception virtual workbenches
=================================================================================

BETA - UNSUPPORTED
  Developed by Kevin Horne. This is a beta project, provided as is, without support or warranty
  of any kind. It is not an official HBK product and is not supported by HBK. Check important
  settings in Perception itself before relying on a result.
  Source and updates: https://github.com/krhorne/vwbhist

What it does
  Compares Perception workbenches (.pVWB) and settings files (.pSet) setting by setting, and can
  keep a history of every change: a copy of each version, a readable text export of the full
  setup, and a change report against the previous version.
  Your workbench files are only ever read, never modified.

  Only the SETUP counts: hardware settings, RT-FDB formulas, ePower/eDrive configuration, formula
  database, info sheet and the sheet list. Saves that only move windows or bump the recording
  number are ignored.

Requirements
  Windows PC with Python 3.8 or newer (python.org). No extra packages.
  Optional, for a modern Windows 11 look (light/dark follows Windows):  pip install sv-ttk

Installing
  Put vwbhist.py, vwbhist_gui.py and the .bat files together in one folder, e.g. C:\Tools\vwbhist

The window (recommended)
  Double-click  vwbhist_gui.bat  (or drag a folder or a .pVWB file onto it).
  Hover the mouse over any button for a hint, press F1 for help on the current tab.
  "About" shows the version and support status.

  Folder vs reference tab - check that every workbench matches a master setup
    1. Folder: Browse... to the folder with your workbenches (sub-folders are included).
    2. Select the master workbench in the tree and click "Use selected file"
       (or right-click it -> Set as reference).
    3. Every other file is compared with the master:
          ★ reference            the master file
          ✓ same as reference    identical setup (green)
          ≠ N differences        click it to see each difference (orange)
          cannot read            damaged, still being saved, or not a workbench (red)
       Click a file to see the report below; double-click opens it in its own window.
       Right-click for: set as reference, version history, open in Perception, open folder.
    Leave the window open while you work - files are re-checked a few seconds after Perception
    saves them. The folder and its reference are remembered for next time.
    Tick "Also keep a version history" to also save a copy of each file every time its setup
    changes (see History below). Untick it to only compare - then nothing is written.

  History tab - versions of one workbench
    Snapshot now (with an optional note) saves a version if the setup changed.
    Select one version + Show changes (or double-click): what changed in that save.
    Select two versions (Ctrl+click) + Show changes: everything that differs between them.
    Selected vs file on disk: what changed since that version.
    Open in Perception: open an old version, e.g. to roll back.

  Compare two files tab - any two workbenches, e.g. two test cells.

  Reports: one line per setting, grouped by section.
     ~ changed (old -> new)     - only in the first file     + only in the second file
  Type in Filter (e.g. "Ch A1", "Trigger") to narrow the report; Save report... writes it to a file.
  "Include display/layout details" (bottom right) also compares windows and displays.

Command line
  python vwbhist.py snapshot "C:\Workbenches\Dyno3.pVWB" -m "set min pulse width to 5 us"
  python vwbhist.py log      "C:\Workbenches\Dyno3.pVWB"         list versions, who, when, how much changed
  python vwbhist.py diff     "C:\Workbenches\Dyno3.pVWB"         what changed in the last save
  python vwbhist.py diff     "C:\Workbenches\Dyno3.pVWB" 3 7     version 3 vs version 7
  python vwbhist.py diff     "C:\Workbenches\Dyno3.pVWB" 5       version 5 vs the file on disk now
  python vwbhist.py compare  A.pVWB B.pVWB                       any two workbenches
  python vwbhist.py watch    "C:\Workbenches"                    record every save in a folder (Ctrl+C stops)
  python vwbhist.py dump     "C:\Workbenches\Dyno3.pVWB"         full setup as text
  Add -v to include display/layout details.
  Launchers: watch_workbenches.bat (edit the folder path at the top first), snapshot_now.bat and
  show_last_change.bat (drag a .pVWB onto them).

Where things are stored (next to the workbench)
  Dyno3_history\
     history.log                    one line per version: file, time, Windows user, summary, note
     v0003_20261002_141500.pVWB     exact copy - open it in Perception to roll back
     v0003_...settings.txt          full setup as text (one "setting = value" per line)
     v0003_...changes.txt           what changed vs the previous version
  The window remembers its folder and reference in %APPDATA%\vwbhist\gui.json.

Rolling back
  Open the vNNNN_....pVWB copy in Perception and save it under the working name.

Optional: git
  If the workbenches live in a git repository, git can show readable diffs:
     .gitattributes :   *.pVWB diff=pvwb
     one-time      :   git config diff.pvwb.textconv "python C:/Tools/vwbhist/vwbhist.py dump"

Notes
  - Built and tested with Perception 8.x workbench files.
  - Some settings are stored by Perception as codes rather than units (e.g. DebounceFilterTime,
    Mode, InputCoupling); the report shows the stored value. To learn a code, change one value
    in Perception, save, and compare.
