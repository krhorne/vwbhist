vwbhist - version history for Perception virtual workbenches
============================================================

What it does
  Keeps a history of every change to a Perception workbench (.pVWB) or settings file (.pSet):
  a copy of each version, a readable text export of the full setup, and a change report
  against the previous version. Your workbench files are only read, never modified.

  A version is only saved when the SETUP changes (hardware settings, RT-FDB formulas,
  ePower/eDrive configuration, formula database, info sheet, sheet list). Saves that only
  move windows or bump the recording number are ignored.

Requirements
  Windows PC with Python 3.8 or newer (python.org). No extra packages.

Quick start
  0. Prefer windows to typing? Double-click  vwbhist_gui.bat  (or drag a folder / .pVWB onto it).
     Folder vs reference tab: pick the folder with your workbenches, then pick the master
     reference file (select it, click "Use selected file"). Every workbench in the folder is
     compared with the master and re-checked automatically whenever it is saved:
        green  = same as reference     orange = N differences     red = cannot read
     Click a file to see exactly what differs; double-click opens the report in its own window.
     Tick "Also keep a version history" to record versions as well (replaces the watch .bat).
     The History and Compare tabs do the snapshot/diff/compare commands below.
     The folder and its reference are remembered for next time.
  1. Put vwbhist.py, vwbhist_gui.py (and the .bat files) in a folder, e.g. C:\Tools\vwbhist
  2. Easiest: double-click  watch_workbenches.bat  and leave it running while you work.
     Edit the folder path at the top of the .bat first. Every time Perception saves a
     workbench in that folder, a new version is recorded automatically.
  3. Or record a version by hand, with a note:
        python vwbhist.py snapshot "C:\Workbenches\Dyno3.pVWB" -m "set min pulse width to 5 us"

Looking at the history
  python vwbhist.py log  "C:\Workbenches\Dyno3.pVWB"            list versions, who, when, how much changed
  python vwbhist.py diff "C:\Workbenches\Dyno3.pVWB"            what changed in the last save
  python vwbhist.py diff "C:\Workbenches\Dyno3.pVWB" 3 7        version 3 vs version 7
  python vwbhist.py diff "C:\Workbenches\Dyno3.pVWB" 5          version 5 vs the file on disk now
  python vwbhist.py compare A.pVWB B.pVWB                       any two workbenches (e.g. two test cells)
  Add -v to include display/layout details.

Where things are stored (next to the workbench)
  Dyno3_history\
     history.log                    one line per version: file, time, Windows user, summary, note
     v0003_20261002_141500.pVWB     exact copy - open it in Perception to roll back
     v0003_...settings.txt          full setup as text (one "setting = value" per line)
     v0003_...changes.txt           what changed vs the previous version

Rolling back
  Open the vNNNN_....pVWB copy in Perception and save it under the working name.

Optional: git
  If the workbenches live in a git repository, git can show readable diffs:
     .gitattributes :   *.pVWB diff=pvwb
     one-time      :   git config diff.pvwb.textconv "python C:/Tools/vwbhist/vwbhist.py dump"

Notes
  - Unofficial helper; not an HBK-supported product. Built and tested with Perception 8.x workbench files.
  - Some settings are stored by Perception as codes rather than units (e.g. DebounceFilterTime,
    Mode, InputCoupling); the report shows the stored value.
