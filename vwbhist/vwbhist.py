#!/usr/bin/env python3
"""
vwbhist - version history for HBK Perception virtual workbenches (.pVWB) and settings files (.pSet)

Unofficial helper, read-only on your workbench files. Python 3.8+, standard library only.

  python vwbhist.py snapshot  <file.pVWB> [-m "note"]    save a version if the setup changed
  python vwbhist.py watch     <folder> [--interval 10]   auto-snapshot every workbench saved in a folder
  python vwbhist.py log       <file.pVWB>                list saved versions with change counts
  python vwbhist.py diff      <file.pVWB> [v1 [v2]]      diff two versions (default: last two; 'current' = file on disk)
  python vwbhist.py compare   <A.pVWB> <B.pVWB>          diff any two workbench files
  python vwbhist.py dump      <file.pVWB>                print normalized settings text (for git textconv)

Options: -v / --verbose  include display/layout details and volatile fields
History lives next to the workbench in  <name>_history/  (copies of the binary + readable text exports).
"""
import sys, os, re, struct, hashlib, shutil, time, argparse, getpass, datetime
import xml.etree.ElementTree as ET
from collections import Counter

# ----------------------------------------------------------------------------------------------
# Nicolet Structured Storage reader (container format of .pVWB / .pSet / .pNRF)
# ----------------------------------------------------------------------------------------------
MAGIC = b'Nicolet Structured Storage\x1a'
END = 0xFFFFFFFF


class NSS:
    def __init__(self, data):
        if not data.startswith(MAGIC):
            raise ValueError('not a Perception structured-storage file')
        self.d = data
        self.ss = struct.unpack_from('<I', data, 0x24)[0]
        self.n = len(data) // self.ss
        per, fat, s, seen = self.ss // 4, [], 1, set()
        while s != END and s not in seen and s < self.n and len(fat) < self.n:
            seen.add(s)
            fat += struct.unpack_from('<%dI' % per, data, s * self.ss)
            s = fat[s] if s < len(fat) else END
        self.fat = fat

    def chain(self, start, size):
        out, s, seen = bytearray(), start, set()
        while s != END and s < self.n and s not in seen and len(out) < size:
            seen.add(s)
            out += self.d[s * self.ss:(s + 1) * self.ss]
            s = self.fat[s] if s < len(self.fat) else END
        return bytes(out[:size])

    @staticmethod
    def entry(b, off):
        name = b[off:off + 64].decode('utf-16le', errors='replace').split('\x00')[0]
        return name, b[off + 64], struct.unpack_from('<I', b, off + 0x50)[0], struct.unpack_from('<Q', b, off + 0x58)[0]

    def walk(self, prefix=''):
        yield from self._dir(self.entry(self.d, 0x40), prefix)

    def _dir(self, ent, prefix):
        blob = self.chain(ent[2], ent[3])
        for off in range(0, len(blob) - 127, 128):
            e = self.entry(blob, off)
            if not e[0]:
                continue
            path, data = prefix + '/' + e[0], self.chain(e[2], e[3])
            if data.startswith(MAGIC):
                try:
                    yield from NSS(data).walk(path)
                    continue
                except Exception:
                    pass
            if e[1] == 2:
                yield path, data
            else:
                yield from self._dir(e, path)


def read_streams(path):
    out = {}
    for p, b in NSS(open(path, 'rb').read()).walk():
        try:
            out[p.split('/')[-1]] = b.decode('utf-16')
        except UnicodeDecodeError:
            out[p.split('/')[-1]] = b.decode('latin-1')
    return out


# ----------------------------------------------------------------------------------------------
# XML flattening with stable, name-based keys
# ----------------------------------------------------------------------------------------------
ID_PATHS = ['ChannelInfoSettings/PhysicalName', 'RecorderInfoSettings/PhysicalName',
            'NonAcquisitionModuleInfoSettings/PhysicalName', 'Name', 'PhysicalName', 'UserName',
            'm_strUserName', 'Key', 'ID', 'id']


def _ident(e):
    for p in ID_PATHS:
        n = e.find(p)
        if n is not None and (n.text or '').strip():
            return n.text.strip()
    return None


def _xml(s):
    s = re.sub(r'^\s*<\?xml[^>]*\?>', '', s.strip().lstrip('﻿')).strip()
    if not s.startswith('<'):
        return None
    for t in (s, '<_w>' + s + '</_w>'):
        try:
            return ET.fromstring(t)
        except ET.ParseError:
            pass
    return None


def _flatten(e, path, out):
    kids = list(e)
    if not kids:
        v = (e.text or '').strip()
        sub = _xml(v) if v.startswith('<') or v.startswith('﻿<') else None
        if sub is not None:
            _flatten(sub, path, out)
        else:
            out[path] = v
        return
    count, seen = Counter(k.tag for k in kids), Counter()
    for k in kids:
        seg = k.tag
        if count[k.tag] > 1:
            i = _ident(k)
            if not i and not list(k) and (k.text or '').strip() and len((k.text or '').strip()) < 80:
                i = (k.text or '').strip()          # plain string lists -> compare as sets
            if not i:
                t = (k.get('type') or '').split(',')[0].split('.')[-1]
                seen[(k.tag, t)] += 1
                i = (t + '#' if t else '') + str(seen[(k.tag, t)])
            seg += '[%s]' % i
        _flatten(k, path + '/' + seg, out)


def flat(text):
    root = _xml(text)
    out = {}
    if root is not None:
        _flatten(root, root.tag, out)
    return out


# ----------------------------------------------------------------------------------------------
# Normalization: what counts as "the setup"
# ----------------------------------------------------------------------------------------------
VOLATILE = re.compile(
    r'recordingSequenceNumber|ExperimentName_Number|StartSequenceNumber|RestoreBounds|/GUID$|BarManager|'
    r'DockManager|SheetIndex$|UIStates|SheetIconBase64|workbench/item$|/StartTime$|MainframeConnectedIpAddress|'
    r'ReviewLiveSplitRatio|FloatLocation|FloatSize')
SECTIONS = [  # stream, title, include-by-default
    ('Settings.xml', 'Hardware settings', True),
    ('RTFDB', 'RT-FDB formulas', True),
    ('PowerWizardSetup.data', 'ePower / eDrive setup', True),
    ('Formulas.data', 'Formula database', True),
    ('HardwareConfiguration.xml', 'Hardware configuration', True),
    ('InfoSheet.data', 'Info sheet', True),
    ('InfoData.data', 'Info data', True),
    ('Sheets', 'Sheets', True),
    ('Workbench.xml', 'Displays & layout', False),
    ('Restrictions.xml', 'Restrictions', False),
    ('PreferredDisplayLayout.xml', 'Preferred display layout', False),
    ('WorkbenchSettings.xml', 'Workbench settings', False),
    ('WorkbenchRecording.xml', 'Workbench recording', False),
    ('Options.xml', 'Options', False),
]


def rtfdb(settings_text):
    root, out = _xml(settings_text), {}
    if root is None:
        return out
    for f in root.iter('RTFDBFormula'):
        tl = f.find('TextLine')
        e = _xml(tl.text or '') if tl is not None else None
        if e is None:
            continue
        d = {c.tag: (c.text or '').strip() for c in e}
        key = d.get('Name') or '# ' + d.get('Formula', '')[:70]
        k, i = key, 2
        while k in out:
            k, i = '%s (%d)' % (key, i), i + 1
        for fld, v in d.items():
            out['%s :: %s' % (k, fld)] = v
    return out


def model(path, verbose=False):
    """Return {section: {key: value}} describing the workbench setup."""
    S = read_streams(path)
    M = {}
    for stream, _, default in SECTIONS:
        if stream == 'RTFDB':
            M[stream] = rtfdb(S.get('Settings.xml', ''))
            continue
        if stream == 'Sheets':
            w = flat(S.get('Workbench.xml', ''))
            names = [v for p, v in w.items() if re.search(r'objects/item\[[^\]]+\]/UserName$', p)
                     and v and not v.startswith(('Display', 'XY ', 'Phasor'))]
            M[stream] = {n: 'present' for n in names}
            continue
        if stream not in S or not (default or verbose):
            continue
        d = flat(S[stream])
        if stream == 'Settings.xml':
            d = {k: v for k, v in d.items() if '/RTFDBFormulas/' not in k}
        if not verbose:
            d = {k: v for k, v in d.items() if not VOLATILE.search(k)}
        M[stream] = d
    return M


def tidy(k):
    k = k.replace('AcquisitionSystem/', '')
    k = re.sub(r'Groups/Group\[([^\]]+)\]/Recorders/Recorder(\[[^\]]+\])?/', r'[\1] ', k)
    k = re.sub(r'(Channels/Channel|TimerCounterChannels/TimerCounterChannel|EventChannels/EventChannel)', 'Ch', k)
    return k


def clip(v, n=160):
    v = re.sub(r'\s+', ' ', v).strip()
    return v if len(v) <= n else v[:n - 3] + '...'


def dump_text(M):
    lines = []
    for stream, title, _ in SECTIONS:
        if stream in M and M[stream]:
            lines.append('### %s' % title)
            lines += ['%s = %s' % (tidy(k), clip(v, 400)) for k, v in sorted(M[stream].items())]
            lines.append('')
    return '\n'.join(lines)


def digest(M):
    return hashlib.sha1(dump_text(M).encode('utf-8')).hexdigest()


def diff_models(A, B, la='A', lb='B'):
    out, total = [], 0
    for stream, title, _ in SECTIONS:
        a, b = A.get(stream, {}), B.get(stream, {})
        if a == b:
            continue
        ch = sorted(k for k in a.keys() & b.keys() if a[k] != b[k])
        ra, rb = sorted(a.keys() - b.keys()), sorted(b.keys() - a.keys())
        if not (ch or ra or rb):
            continue
        if stream == 'RTFDB':
            nm = lambda ks: {k.split(' :: ')[0] for k in ks}
            na, nb = nm(a.keys()), nm(b.keys())
            c_, r_, a_ = len(nm(ch) & na & nb | (nm(ra) & nb) | (nm(rb) & na)), len(na - nb), len(nb - na)
        else:
            c_, r_, a_ = len(ch), len(ra), len(rb)
        total += c_ + r_ + a_
        out.append('\n## %s  (%d changed, %d removed, %d added)' % (title, c_, r_, a_))
        if stream == 'RTFDB':  # group by formula name
            names = sorted({k.split(' :: ')[0] for k in ch + ra + rb})
            for nm in names:
                fa = {k.split(' :: ')[1]: v for k, v in a.items() if k.split(' :: ')[0] == nm}
                fb = {k.split(' :: ')[1]: v for k, v in b.items() if k.split(' :: ')[0] == nm}
                if not fa:
                    out.append('  + %s = %s   [%s]' % (nm, clip(fb.get('Formula', '')), fb.get('Units', '')))
                elif not fb:
                    out.append('  - %s = %s' % (nm, clip(fa.get('Formula', ''))))
                else:
                    out.append('  ~ %s' % nm)
                    for f in sorted(fa.keys() | fb.keys()):
                        if fa.get(f) != fb.get(f):
                            out.append('      %s: %s  ->  %s' % (f, clip(fa.get(f, '<none>')), clip(fb.get(f, '<none>'))))
            continue
        seen = set()
        for k in ch:
            pair = (clip(a[k]), clip(b[k]))
            if len(pair[0]) > 60 and pair in seen:
                continue
            seen.add(pair)
            out.append('  ~ %s: %s  ->  %s' % (tidy(k), pair[0], pair[1]))
        out += ['  - %s: %s' % (tidy(k), clip(a[k])) for k in ra]
        out += ['  + %s: %s' % (tidy(k), clip(b[k])) for k in rb]
    head = '# %s  ->  %s : %d setup differences' % (la, lb, total)
    return head + ('\n'.join([''] + out) if out else '\n(no setup differences)'), total


# ----------------------------------------------------------------------------------------------
# History store
# ----------------------------------------------------------------------------------------------
def hist_dir(wb):
    base = os.path.splitext(os.path.abspath(wb))[0]
    return base + '_history'


def versions(wb):
    d = hist_dir(wb)
    if not os.path.isdir(d):
        return []
    ext = os.path.splitext(wb)[1]
    return sorted(f for f in os.listdir(d) if f.lower().endswith(ext.lower()) and re.match(r'v\d{4}_', f))


def snapshot(wb, note='', quiet=False, verbose=False):
    M = model(wb)
    dg = digest(M)
    d = hist_dir(wb)
    os.makedirs(d, exist_ok=True)
    vs = versions(wb)
    if vs:
        prev = os.path.join(d, vs[-1])
        prev_txt = os.path.splitext(prev)[0] + '.settings.txt'
        if os.path.exists(prev_txt) and hashlib.sha1(open(prev_txt, encoding='utf-8').read().encode('utf-8')).hexdigest() == dg:
            if not quiet:
                print('no setup change since %s - nothing saved' % vs[-1])
            return None
    num = len(vs) + 1
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    ext = os.path.splitext(wb)[1]
    name = 'v%04d_%s%s' % (num, stamp, ext)
    dst = os.path.join(d, name)
    shutil.copy2(wb, dst)
    txt = dump_text(M)
    open(os.path.splitext(dst)[0] + '.settings.txt', 'w', encoding='utf-8').write(txt)
    summary = 'initial version'
    if vs:
        rep, n = diff_models(model(os.path.join(d, vs[-1])), M, vs[-1], name)
        open(os.path.splitext(dst)[0] + '.changes.txt', 'w', encoding='utf-8').write(rep + '\n')
        summary = '%d setup differences vs %s' % (n, vs[-1])
    try:
        user = getpass.getuser()
    except Exception:
        user = '?'
    with open(os.path.join(d, 'history.log'), 'a', encoding='utf-8') as f:
        f.write('%s\t%s\t%s\t%s\t%s\n' % (name, datetime.datetime.now().isoformat(timespec='seconds'), user,
                                          summary, note.replace('\t', ' ')))
    if not quiet:
        print('saved %s  (%s)' % (name, summary))
    return name


def read_log(wb):
    """[[version, time, user, summary, note], ...] from history.log, oldest first."""
    lg = os.path.join(hist_dir(wb), 'history.log')
    if not os.path.exists(lg):
        return []
    rows = []
    for line in open(lg, encoding='utf-8'):
        if line.strip():
            p = (line.rstrip('\n').split('\t') + [''] * 5)[:5]
            p[1] = p[1].replace('T', ' ')
            rows.append(p)
    return rows


def watch_scan(folder, mt, log=print):
    """One pass over folder: snapshot every workbench whose file time changed since the last pass (mt)."""
    for root, dirs, files in os.walk(folder):
        dirs[:] = [x for x in dirs if not x.endswith('_history')]
        for fn in files:
            if not fn.lower().endswith(('.pvwb', '.pset')):
                continue
            p = os.path.join(root, fn)
            try:
                m = os.path.getmtime(p)
            except OSError:
                continue
            if mt.get(p) != m:
                first = p not in mt
                mt[p] = m
                time.sleep(1.0)  # let Perception finish writing
                try:
                    r = snapshot(p, 'auto (watch)' if not first else 'auto (watch start)', quiet=True)
                    if r:
                        log('%s  %s -> %s' % (time.strftime('%H:%M:%S'), fn, r))
                except Exception as ex:
                    log('%s  %s: skipped (%s)' % (time.strftime('%H:%M:%S'), fn, ex))


def resolve(wb, v):
    if v in (None, 'current'):
        return os.path.abspath(wb), 'current'
    vs = versions(wb)
    if re.fullmatch(r'-?\d+', v):
        i = int(v)
        m = [x for x in vs if x.startswith('v%04d_' % i)] if i > 0 else [vs[i]]
        if m:
            return os.path.join(hist_dir(wb), m[0]), m[0]
    m = [x for x in vs if x.startswith(v)]
    if m:
        return os.path.join(hist_dir(wb), m[0]), m[0]
    raise SystemExit('version not found: %s' % v)


def main():
    ap = argparse.ArgumentParser(description='Version history for Perception workbenches', epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['snapshot', 'watch', 'log', 'diff', 'compare', 'dump'])
    ap.add_argument('args', nargs='*')
    ap.add_argument('-m', '--message', default='')
    ap.add_argument('-v', '--verbose', action='store_true')
    ap.add_argument('--interval', type=float, default=10.0)
    o = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    a = o.args
    if o.cmd == 'dump':
        print(dump_text(model(a[0], o.verbose)))
    elif o.cmd == 'snapshot':
        for f in a:
            snapshot(f, o.message)
    elif o.cmd == 'compare':
        print(diff_models(model(a[0], o.verbose), model(a[1], o.verbose), os.path.basename(a[0]), os.path.basename(a[1]))[0])
    elif o.cmd == 'diff':
        wb = a[0]
        vs = versions(wb)
        if len(a) >= 3:
            p1, l1 = resolve(wb, a[1]); p2, l2 = resolve(wb, a[2])
        elif len(a) == 2:
            p1, l1 = resolve(wb, a[1]); p2, l2 = resolve(wb, 'current')
        else:
            if len(vs) < 2:
                raise SystemExit('need at least two saved versions (have %d)' % len(vs))
            p1, l1 = resolve(wb, vs[-2]); p2, l2 = resolve(wb, vs[-1])
        print(diff_models(model(p1, o.verbose), model(p2, o.verbose), l1, l2)[0])
    elif o.cmd == 'log':
        rows = read_log(a[0])
        if not rows:
            raise SystemExit('no history yet - run: vwbhist.py snapshot "%s"' % a[0])
        for p in rows:
            print('%-32s %s  %-10s %s%s' % (p[0], p[1], p[2], p[3], ('  | ' + p[4]) if p[4] else ''))
    elif o.cmd == 'watch':
        folder, mt = a[0], {}
        if not os.path.isdir(folder):
            raise SystemExit('folder not found: %s' % folder)
        print('watching %s for saved workbenches (Ctrl+C to stop)' % folder, flush=True)
        while True:
            watch_scan(folder, mt, lambda s: print(s, flush=True))
            time.sleep(o.interval)


if __name__ == '__main__':
    try:
        main()
    except FileNotFoundError as ex:
        raise SystemExit('file not found: %s' % ex.filename)
