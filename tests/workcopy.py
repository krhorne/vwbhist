"""Manage the working copy workbenches/Test.pVWB for manual history tests.
   reset : Test.pVWB = six_step_to_PWM.pVWB
   edit  : Test.pVWB = EPT_SC_demo.pVWB   (simulates a big setup change)
   toggle: swap between the two"""
import os, sys, shutil, filecmp
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, 'workbenches')
A, B, T = (os.path.join(W, f) for f in ('six_step_to_PWM.pVWB', 'EPT_SC_demo.pVWB', 'Test.pVWB'))
cmd = sys.argv[1] if len(sys.argv) > 1 else 'toggle'
if cmd == 'toggle':
    cmd = 'reset' if os.path.exists(T) and filecmp.cmp(T, B, shallow=False) else 'edit'
src = A if cmd == 'reset' else B
shutil.copyfile(src, T)
print('Test.pVWB <- %s' % os.path.basename(src))
