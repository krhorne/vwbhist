"""Self-test: runs the full history workflow on the two demo workbenches in a temp folder."""
import os, sys, shutil, tempfile, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'vwbhist'))
import vwbhist as V  # noqa: E402

A = os.path.join(ROOT, 'workbenches', 'six_step_to_PWM.pVWB')
B = os.path.join(ROOT, 'workbenches', 'EPT_SC_demo.pVWB')
results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(('PASS  ' if cond else 'FAIL  ') + name)


tmp = tempfile.mkdtemp(prefix='vwbhist_selftest_')
try:
    wb = os.path.join(tmp, 'Rig.pVWB')
    quiet = io.StringIO()
    with contextlib.redirect_stdout(quiet):
        shutil.copy(A, wb); v1 = V.snapshot(wb, 'baseline')
        v_same = V.snapshot(wb, 'no change')
        shutil.copy(B, wb); v2 = V.snapshot(wb, 'switch to SC demo')
    check('container parses (12 streams)', len(V.read_streams(A)) == 12)
    check('first snapshot saved', v1 is not None)
    check('unchanged save is skipped', v_same is None)
    check('changed save recorded as v0002', v2 is not None and v2.startswith('v0002_'))
    rep, n = V.diff_models(V.model(A), V.model(B), 'A', 'B')
    check('231 setup differences between demos', n == 231)
    check('Ch A1 units A -> V detected', 'Ch[Ch A1]/ModeSpecific/Scaling/Units: A  ->  V' in rep)
    check('Ch A8 DebounceFilterTime 5 -> 6 detected', 'TimerCounterSettings/DebounceFilterTime: 5  ->  6' in rep)
    check('RT-FDB u_1 formula change detected', '( RTFormulas.Inverter.out.u_12 - RTFormulas.Inverter.out.u_31 ) / 3' in rep)
    check('ePower current filter 50k -> 200k detected', 'CurrentFilterFrequency: 50000  ->  200000' in rep)
    same, n0 = V.diff_models(V.model(A), V.model(A))
    check('file vs itself = 0 differences', n0 == 0)
    hist = V.hist_dir(wb)
    check('history files written', all(os.path.exists(os.path.join(hist, f)) for f in ['history.log']) and
          len([f for f in os.listdir(hist) if f.endswith('.changes.txt')]) == 1)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

bad = [n for n, ok in results if not ok]
print('\n%d/%d passed' % (len(results) - len(bad), len(results)))
sys.exit(1 if bad else 0)
