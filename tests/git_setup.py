"""Create gitdemo/ : a git repo whose .pVWB diffs are shown as readable settings (textconv)."""
import os, sys, shutil, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, 'gitdemo')
TOOL = os.path.join(ROOT, 'vwbhist', 'vwbhist.py').replace('\\', '/')
if not shutil.which('git'):
    sys.exit('git not found on PATH - install Git for Windows first')


def git(*a):
    print('> git ' + ' '.join(a))
    subprocess.run(['git', *a], cwd=G, check=True)


if os.path.exists(G):
    sys.exit('gitdemo/ already exists - delete it to start over')
os.makedirs(G)
git('init', '-q')
git('config', 'user.name', 'vwbhist test'); git('config', 'user.email', 'test@example.com')
git('config', 'diff.pvwb.textconv', '"%s" "%s" dump' % (sys.executable.replace('\\', '/'), TOOL))
open(os.path.join(G, '.gitattributes'), 'w').write('*.pVWB diff=pvwb\n*.pSet diff=pvwb\n')
shutil.copyfile(os.path.join(ROOT, 'workbenches', 'six_step_to_PWM.pVWB'), os.path.join(G, 'Rig.pVWB'))
git('add', '.'); git('commit', '-q', '-m', 'baseline: six-step setup')
shutil.copyfile(os.path.join(ROOT, 'workbenches', 'EPT_SC_demo.pVWB'), os.path.join(G, 'Rig.pVWB'))
git('add', '.'); git('commit', '-q', '-m', 'switch to PWM / phase-to-phase setup')
print('\nDone. Try:  cd gitdemo  then  git log -p Rig.pVWB   (or open gitdemo in the VS Code Source Control view)')
subprocess.run(['git', '--no-pager', 'diff', '--stat', 'HEAD~1', 'HEAD'], cwd=G)
subprocess.run(['git', '--no-pager', 'diff', 'HEAD~1', 'HEAD', '--', 'Rig.pVWB'], cwd=G, stdout=open(os.path.join(G, 'last_diff.txt'), 'w', encoding='utf-8'))
print('Readable diff of the last commit written to gitdemo/last_diff.txt')
