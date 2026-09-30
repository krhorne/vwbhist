# vwbhist: Perception workbench compare & version history (beta)

> **Beta, unsupported.** Developed by Kevin Horne. This is not an official HBK product and is not supported by
> HBK. It is provided as is, without support or warranty of any kind. Check important settings in Perception
> itself before relying on a result.

vwbhist compares HBK Perception virtual workbenches (`.pVWB`) and settings files (`.pSet`) setting by setting,
and can keep a version history of them. It reports only real **setup** changes and ignores window positions
and recording numbers. It only reads your workbench files and never changes them.

## Features
- **Folder vs reference.** Point it at a folder and pick one master ("golden") workbench. The Explorer-style
  tree then marks every other file ✓ *same as reference*, ≠ *N differences* or *cannot read*, with a count
  for each sub-folder. Click a file to see exactly what differs; double-click opens the report in its own
  window. Files are re-checked automatically whenever Perception saves them.
- **History.** Snapshot a workbench with a note and list its versions (who, when, how much changed). You can
  see what changed in any save, compare any two versions, or roll back.
- **Compare two files.** Compare any two workbenches, such as two test cells.
- **Readable reports.** Differences are grouped by section (hardware settings, RT-FDB formulas, ePower/eDrive,
  …), colour-coded, and each line reads `old -> new`. You can filter the report and save it as text.
- **Built-in help.** Hover over any control for a hint, press **F1** for the help page on the current tab,
  and click **About** for the version and support status.
- **Command line and git.** The same functions are available as commands, plus a `dump` command that gives
  readable `.pVWB` diffs in git.
- **Windows 11 look.** Light or dark follows your Windows setting when the optional `sv-ttk` package is
  installed.

## Requirements
- Windows with Python 3.8 or newer on PATH (`python --version`). No other packages are needed.
- Optional: `pip install sv-ttk` for the Windows 11 look. Without it, the window uses the plain look.

## Quick start
1. Double-click `vwbhist/vwbhist_gui.bat` (or drag a folder or a `.pVWB` file onto it).
2. **Folder vs reference** tab: click **Browse…** and pick the folder that holds your workbenches.
3. Select the master workbench in the tree and click **Use selected file**. Every other file is now
   compared with it.
4. Click any file marked ≠ to see its differences. Leave the window open while you work: files you save
   from Perception are re-checked within a few seconds.
5. Optional: tick **Also keep a version history** to also save a copy each time a setup changes. The
   **History** tab then shows each file's versions.

The folder and its reference are remembered for next time. `vwbhist/README.txt` is the customer-facing
guide and also covers the command line.

## Command line
```
python vwbhist/vwbhist.py snapshot Rig.pVWB -m "note"    save a version if the setup changed
python vwbhist/vwbhist.py log      Rig.pVWB              list versions
python vwbhist/vwbhist.py diff     Rig.pVWB [v1 [v2]]    what changed (default: last save)
python vwbhist/vwbhist.py compare  A.pVWB B.pVWB         any two workbenches
python vwbhist/vwbhist.py watch    <folder>              auto-snapshot every saved workbench
python vwbhist/vwbhist.py dump     Rig.pVWB              full setup as text (git textconv)
```
Add `-v` to include display/layout details.

## Repository layout
| Path | What |
|---|---|
| `vwbhist/` | The tool as it ships to a customer: `vwbhist.py` (engine and command line), `vwbhist_gui.py` (window), `.bat` launchers, `README.txt` |
| `workbenches/` | Two HBK EPT demo workbenches. `Test.pVWB` is created from them as a working copy. |
| `tests/selftest.py` | Automated check of the whole workflow on the demo files |
| `tests/workcopy.py` | Swaps `Test.pVWB` between the two demos to simulate edits |
| `tests/git_setup.py` | Builds `gitdemo/`, a git repo with readable `.pVWB` diffs |
| `vscode_config/` | VS Code tasks, debug configs and settings (also embedded in the `.code-workspace`) |
| `reports/` | Output of the compare and dump tasks |
| `EPT_TechNote_XXX_pVWB_Setup_Comparison.docx` | Tech note draft describing the method |

## Testing in VS Code
Open **`vwbhist-test.code-workspace`** (double-click it, or File → Open Workspace from File…). It contains the
tasks, debug configs and settings. If you'd rather open the folder itself, run `install_vscode_config.bat`
once to copy them into `.vscode/`.

Run the tasks with Terminal → Run Task…:
1. **Self-test**: expect `11/11 passed`.
2. **Compare demo workbenches**: opens `reports/compare_demo.txt`.
3. **Reset working copy**, then **Snapshot Test.pVWB**: creates `workbenches/Test_history/v0001…`.
4. **Snapshot** again: should report *no setup change*.
5. **Simulate edit**, **Snapshot**, then **Log** and **Diff**: v0002 with 231 differences.
6. **Watch workbenches folder** (command-line watch): run *Simulate edit* or *Reset* from a second terminal,
   or save `Test.pVWB` from Perception. Each change is recorded automatically. Press Ctrl+C to stop.
7. **Git: init repo** (needs Git for Windows): open `gitdemo/` in Source Control and click `Rig.pVWB` in the
   history. The diff shows settings, not "binary file".
8. **Open the vwbhist window (GUI)**: it opens on `workbenches/`. Select `six_step_to_PWM.pVWB` and click
   *Use selected file*; `EPT_SC_demo.pVWB` then shows *231 differences*. Run *Simulate edit* or *Reset*, and
   `Test.pVWB` switches between same and different within a few seconds. Hover over the buttons for hints,
   and press F1 for help.

## Real-world test with Perception
Open `workbenches/Test.pVWB` in Perception and change one known setting, such as the timer/counter minimum
pulse width on the speed channel. Save it (File → Save virtual workbench), then look at it in the GUI, or run
**Snapshot** and **Diff**. You can learn the stored codes (`DebounceFilterTime`, `Mode`, `InputCoupling`) the
same way: change one value per save and note the code.
