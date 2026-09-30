# vwbhist test workspace

Test bench for comparing Perception workbenches (.pVWB) and keeping a setup version history.
See `EPT_TechNote_XXX_pVWB_Setup_Comparison.docx` for the method.

## Open it
Double-click **`vwbhist-test.code-workspace`** (or File → Open Workspace from File…). The tasks, debug
configs and settings are embedded in that file. If you prefer opening the folder itself, run
`install_vscode_config.bat` once to copy them into `.vscode/`.

## Layout
| Path | What |
|---|---|
| `vwbhist/` | the tool as it would ship to a customer (`vwbhist.py`, .bat launchers, README) |
| `workbenches/` | two HBK EPT demo workbenches; `Test.pVWB` is created as a working copy |
| `tests/selftest.py` | automated check of the whole workflow on the demo files |
| `tests/workcopy.py` | swaps `Test.pVWB` between the two demos to simulate edits |
| `tests/git_setup.py` | builds `gitdemo/`, a git repo with readable pVWB diffs |
| `reports/` | output of the compare/dump tasks |

## Run (Terminal -> Run Task…, or Ctrl+Shift+P "Tasks: Run Task")
1. **Self-test** - expect `11/11 passed`.
2. **Compare demo workbenches** - opens `reports/compare_demo.txt`.
3. **Reset working copy**, then **Snapshot Test.pVWB** - creates `workbenches/Test_history/v0001…`.
4. **Snapshot** again - should report *no setup change*.
5. **Simulate edit**, **Snapshot**, then **Log** and **Diff** - v0002 with 231 differences.
6. **Watch workbenches folder**, then run *Simulate edit* / *Reset* from a second terminal
   (or save Test.pVWB from Perception) - each change is recorded automatically. Ctrl+C to stop.
7. **Git: init repo** (needs Git for Windows) - then open `gitdemo/` in Source Control and click
   `Rig.pVWB` in the history: the diff shows settings, not "binary file".
8. **Open the vwbhist window (GUI)** - opens on `workbenches/`. Select `six_step_to_PWM.pVWB`, click
   *Use selected file* to make it the master reference: `EPT_SC_demo.pVWB` shows *231 differences*.
   Run *Simulate edit* / *Reset* - `Test.pVWB` flips between same/different within a few seconds.
   Customers start it with `vwbhist/vwbhist_gui.bat`.

## Real-world test with Perception
Open `workbenches/Test.pVWB` in Perception, change one known setting (e.g. timer/counter
minimum pulse width on the speed channel), File -> Save virtual workbench, then run
**Snapshot** + **Diff**. This is also how to calibrate the stored codes
(`DebounceFilterTime`, `Mode`, `InputCoupling`): change one value per save and note the code.

Requires Python 3.8+ on PATH (`python --version`). Debug configs are in `.vscode/launch.json`.
