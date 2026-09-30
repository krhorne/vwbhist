#!/usr/bin/env python3
"""
vwbhist GUI - point-and-click front end for vwbhist.py (same folder). Python 3.8+, standard library only.

  pythonw vwbhist_gui.py [folder | file.pVWB]      (or double-click vwbhist_gui.bat)

Tabs:
  Folder vs reference  explorer tree of a folder; every workbench is compared with one master reference
                       and re-checked automatically when it is saved. Click a file to see its differences.
  History              versions of one workbench: snapshot, show changes, roll back
  Compare two files    any two workbenches
Reports appear in the pane at the bottom (double-click in the folder tree opens one in its own window).
"""
import os, sys, time, json, threading, queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vwbhist as V  # noqa: E402
try:
    import sv_ttk  # optional Windows 11 look (pip install sv-ttk); plain Tk look without it
except ImportError:
    sv_ttk = None

FILETYPES = [('Perception workbench', '*.pVWB *.pSet'), ('All files', '*.*')]
COLS = [('version', 'Version', 220), ('time', 'Saved', 140), ('user', 'User', 90),
        ('summary', 'Summary', 330), ('note', 'Note', 260)]
LIGHT = dict(text_bg='#ffffff', text_fg='#1f2328', sec='#0550ae', chg='#9a6700', rem='#cf222e', add='#1a7f37',
             hint='#6e7781', tip_bg='#fbfbfb', tip_fg='#1f2328', tip_border='#c9c9c9')
DARK = dict(text_bg='#1c1c1c', text_fg='#e6edf3', sec='#79c0ff', chg='#e3b341', rem='#ff7b72', add='#56d364',
            hint='#9a9a9a', tip_bg='#2b2b2b', tip_fg='#e6edf3', tip_border='#4a4a4a')
APP_VERSION = '0.9 beta'
AUTHOR = 'Kevin Horne'
REPO_URL = 'https://github.com/krhorne/vwbhist'
CFG = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), 'vwbhist', 'gui.json')


def fmt_error(ex):
    if isinstance(ex, SystemExit):
        return str(ex.code)
    if isinstance(ex, FileNotFoundError):
        return 'file not found: %s' % ex.filename
    if isinstance(ex, ValueError):
        return str(ex)
    return '%s: %s' % (type(ex).__name__, ex)


def clean(p):
    return p.strip().strip('"')


def same_file(a, b):
    return bool(a and b) and os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def stat_key(p):
    try:
        s = os.stat(p)
        return s.st_mtime, s.st_size
    except OSError:
        return None


def windows_dark():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize')
        return winreg.QueryValueEx(k, 'AppsUseLightTheme')[0] == 0
    except Exception:
        return False


def dark_title_bar(win):
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        on = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), ctypes.sizeof(on))
    except Exception:
        pass


def apply_theme(root, dark):
    """sv-ttk theme. Its colours hang off a <<ThemeChanged>> event that does not reach the root window on
    current Tk builds, so apply them directly."""
    sv_ttk.set_theme('dark' if dark else 'light')
    try:
        root.tk.call('configure_colors')
    except tk.TclError:
        pass


def load_cfg():
    try:
        return json.load(open(CFG, encoding='utf-8'))
    except Exception:
        return {}


def save_cfg(cfg):
    try:
        os.makedirs(os.path.dirname(CFG), exist_ok=True)
        json.dump(cfg, open(CFG, 'w', encoding='utf-8'), indent=1)
    except Exception:
        pass


# ----------------------------------------------------------------------------------------------
# Hover help
# ----------------------------------------------------------------------------------------------
class Tip:
    """Small help popup shown when the mouse rests on a widget. text may be a function(event) -> str
    for widgets whose help depends on what is under the mouse (tree rows)."""
    pal = LIGHT
    DELAY = 600

    def __init__(self, widget, text):
        self.w, self.text, self.win, self.job, self.cur = widget, text, None, None, None
        widget.bind('<Enter>', self.enter, add='+')
        widget.bind('<Leave>', self.hide, add='+')
        widget.bind('<ButtonPress>', self.hide, add='+')
        if callable(text):
            widget.bind('<Motion>', self.moved, add='+')

    def enter(self, e):
        if not callable(self.text):
            self.hide()
            self.cur = self.text
            self.job = self.w.after(self.DELAY, self.show)

    def moved(self, e):
        t = self.text(e)
        if t != self.cur:
            self.hide()
            self.cur = t
            if t:
                self.job = self.w.after(self.DELAY, self.show)

    def show(self):
        self.job = None
        if not self.cur or not self.w.winfo_exists():
            return
        c = Tip.pal
        x, y = self.w.winfo_pointerxy()
        win = self.win = tk.Toplevel(self.w)
        win.overrideredirect(True)
        win.attributes('-topmost', True)
        tk.Label(win, text=self.cur, justify='left', wraplength=420, bg=c['tip_bg'], fg=c['tip_fg'],
                 font=('Segoe UI', 9), padx=8, pady=5, highlightthickness=1,
                 highlightbackground=c['tip_border']).pack()
        win.update_idletasks()
        x = min(x + 12, win.winfo_screenwidth() - win.winfo_reqwidth() - 4)
        y = y + 20 if y + 20 + win.winfo_reqheight() < win.winfo_screenheight() else y - win.winfo_reqheight() - 8
        win.geometry('+%d+%d' % (x, y))

    def hide(self, e=None):
        if self.job:
            self.w.after_cancel(self.job)
            self.job = None
        if self.win:
            self.win.destroy()
            self.win = None
        if e is not None and e.type == tk.EventType.Leave:
            self.cur = None


def tip(widget, text):
    Tip(widget, text)
    return widget


TREE_TIPS = {
    'ref': 'The master reference. Every other workbench is compared with this file.\n'
           'To change it: right-click another file -> Set as reference.',
    'same': 'Setup is identical to the reference.\n(Window positions and recording numbers are ignored.)',
    'diff': 'Setup differs from the reference. Click to list every difference in the report below; '
            'double-click to open the report in its own window.',
    'err': 'This file could not be read - it may be damaged, still being saved, or not a Perception workbench.',
    'pending': 'Being compared with the reference...',
}

HELP = """# vwbhist help

vwbhist compares Perception workbench (.pVWB) and settings (.pSet) files setting by setting and can keep a
version history of them. Your workbench files are only ever read, never changed.
Hover the mouse over any button or field for a short hint. Press F1 to open this help at the current tab.
Type in the Filter box above to search this help.

## Folder vs reference tab
Checks that every workbench in a folder (e.g. one per test cell) matches a master "golden" setup.
1. Folder: click Browse... and pick the folder that holds the workbenches. Sub-folders are included;
   <name>_history folders are hidden.
2. Reference: select the master workbench in the tree and click "Use selected file"
   (or right-click it -> Set as reference, or Browse... to a master stored somewhere else).
3. Every other file is then compared with the reference:
     \u2605 reference            the master file
     \u2713 same as reference    identical setup
     \u2260 N differences        click it to list every difference in the report pane
     cannot read          damaged, still being saved, or not a workbench
   Folder rows show how many files in them differ; the top right shows the totals.
4. Click a file to see its report below. Double-click opens it in its own window.
   Right-click a file for: set as reference, version history, open in Perception, open its folder.
Leave the window open while you work: files are re-checked every few seconds, and a file saved from Perception
shows its new result straight away. The folder and its reference are remembered for next time.
Tick "Also keep a version history" to also save a copy of each workbench every time its setup changes
(see the History tab). Untick it to only compare - then nothing is written anywhere.

## History tab
Versions of one workbench over time. Pick it with Browse... (or right-click a file in the folder tree ->
Version history...).
- Snapshot now saves the current file as a new version, with an optional note. Nothing is saved if the setup
  has not changed since the last version.
- Select one version and click Show changes (or double-click it): what changed in that save.
- Select two versions (Ctrl+click) and click Show changes: everything that differs between them.
- Selected vs file on disk: what has changed since that version, including edits not yet saved as a version.
- View settings: the full setup of a version (or of the current file) as text.
- Roll back: select a version, click Open in Perception, then save it from Perception under the working name.

## Compare two files tab
Any two workbenches, e.g. two test cells or a colleague's file vs yours. Pick A (before) and B (after) and click
Compare. Swap A/B reverses the direction of the report.

## Reading a report
The first line gives the total number of setup differences. Differences are grouped by section (Hardware
settings, RT-FDB formulas, ePower / eDrive setup, ...), each with its own counts. Each line is one setting:
  ~ [group] Ch[Ch A1]/ModeSpecific/Scaling/Units: A  ->  V        changed: old value -> new value
  - [group] Ch[Ch B3]/...                                        only in the first file (removed)
  + [group] Ch[Ch B4]/...                                        only in the second file (added)
Filter: type e.g. Ch A1, Trigger or u_1 to show only matching lines. Save report... writes it to a text file.

## What counts as a change
Only the measurement setup: hardware and channel settings, RT-FDB formulas, ePower/eDrive configuration, the
formula database, info sheet and the list of sheets. Window positions, display layout, recording numbers and
similar are ignored - tick "Include display/layout details" (bottom right) to include them.
Perception stores some values as codes rather than units (e.g. DebounceFilterTime, Mode, InputCoupling);
the report shows the stored code. To learn a code, change one value in Perception, save, and compare.

## Where things are stored
Versions are kept next to each workbench in <name>_history\\ :
  history.log                 one line per version: file, time, Windows user, summary, note
  vNNNN_<date>_<time>.pVWB    exact copy of the workbench (open it in Perception to roll back)
  vNNNN_....settings.txt      the full setup as text
  vNNNN_....changes.txt       what changed against the previous version
The chosen folder and reference are remembered in %APPDATA%\\vwbhist\\gui.json.
"""


# ----------------------------------------------------------------------------------------------
# Report pane: colour-coded report text with a filter box and Save
# ----------------------------------------------------------------------------------------------
class ReportView(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app, self.report = app, ''
        bar = ttk.Frame(self)
        bar.pack(fill='x', pady=(0, 4))
        self.heading = ttk.Label(bar, text='Report', font=('Segoe UI', 10, 'bold'))
        self.heading.pack(side='left')
        tip(ttk.Button(bar, text='Save report...', command=self.save),
            'Save the whole report as a text file, e.g. to attach to a test log.').pack(side='right')
        self.filt = tk.StringVar()
        self.filt.trace_add('write', lambda *_: self.render())
        tip(ttk.Entry(bar, textvariable=self.filt, width=30),
            'Show only lines containing this text, e.g. "Ch A1", "Trigger" or "u_1".\n'
            'Section headings stay visible. Clear it to see everything.').pack(side='right', padx=4)
        ttk.Label(bar, text='Filter:').pack(side='right')
        tf = ttk.Frame(self)
        tf.pack(fill='both', expand=True)
        c = app.pal
        t = self.text = tk.Text(tf, wrap='none', font=('Consolas', 10), state='disabled', undo=False, bd=0,
                                highlightthickness=0, padx=6, pady=4, bg=c['text_bg'], fg=c['text_fg'],
                                insertbackground=c['text_fg'])
        sy = ttk.Scrollbar(tf, orient='vertical', command=t.yview)
        sx = ttk.Scrollbar(tf, orient='horizontal', command=t.xview)
        t.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.pack(side='right', fill='y')
        sx.pack(side='bottom', fill='x')
        t.pack(side='left', fill='both', expand=True)
        t.tag_configure('head', font=('Consolas', 11, 'bold'))
        t.tag_configure('sec', font=('Consolas', 10, 'bold'), foreground=c['sec'])
        t.tag_configure('chg', foreground=c['chg'])
        t.tag_configure('rem', foreground=c['rem'])
        t.tag_configure('add', foreground=c['add'])

    def show(self, title, text):
        self.heading.config(text=title)
        self.report = text
        self.render()

    def render(self):
        lines = self.report.split('\n')
        f = self.filt.get().strip().lower()
        if f:  # keep the title, matching lines, and the section header above each match
            out, hdr = lines[:1], None
            for ln in lines[1:]:
                if ln.startswith('#'):
                    hdr = ln
                elif f in ln.lower():
                    if hdr is not None:
                        out += ['', hdr]
                        hdr = None
                    out.append(ln)
            lines = out
        t = self.text
        t.config(state='normal')
        t.delete('1.0', 'end')
        for ln in lines:
            tag = ('head' if ln.startswith('# ') else 'sec' if ln.startswith('##') else
                   'chg' if ln.startswith('  ~') else 'rem' if ln.startswith('  -') else
                   'add' if ln.startswith('  +') else '')
            t.insert('end', ln + '\n', tag)
        t.config(state='disabled')

    def save(self):
        if not self.report:
            return
        p = filedialog.asksaveasfilename(parent=self, defaultextension='.txt', filetypes=[('Text', '*.txt')])
        if p:
            open(p, 'w', encoding='utf-8').write(self.report + '\n')
            self.app.status.set('report saved to ' + p)


# ----------------------------------------------------------------------------------------------
# Folder vs reference: explorer tree, every workbench compared with one master file
# ----------------------------------------------------------------------------------------------
class FolderView(ttk.Frame):
    POLL_MS = 3000

    def __init__(self, parent, app):
        super().__init__(parent, padding=6)
        self.app = app
        self.folder = tk.StringVar()
        self.ref = tk.StringVar()
        self.record = tk.BooleanVar(value=False)
        self.summary = tk.StringVar()
        self.root_dir = self.ref_path = self.ref_key = None
        self.files = None      # workbench paths currently in the tree
        self.keys = {}         # path -> (mtime, size)
        self.want = {}         # path -> (generation, mtime, size): the comparison we are waiting for
        self.results = {}      # path -> (want key, report, n differences, error)
        self.gen, self.vb, self.rec = 0, False, False
        self.jobs = queue.Queue()
        self._build()
        threading.Thread(target=self._worker, daemon=True).start()
        self.tick_id = self.after(self.POLL_MS, self._tick)

    def _build(self):
        g = ttk.Frame(self)
        g.pack(fill='x')
        ttk.Label(g, text='Folder:').grid(row=0, column=0, sticky='w')
        e = tip(ttk.Entry(g, textvariable=self.folder), 'The folder that holds your workbenches (.pVWB / .pSet). '
                'Sub-folders are included.\nType a path and press Enter, or use Browse...')
        e.grid(row=0, column=1, sticky='ew', padx=4)
        e.bind('<Return>', lambda _: self.load())
        tip(ttk.Button(g, text='Browse...', command=self.browse_folder), 'Choose the folder to check.').grid(row=0, column=2, sticky='ew')
        ttk.Label(g, text='Reference:').grid(row=1, column=0, sticky='w', pady=(4, 0))
        e = tip(ttk.Entry(g, textvariable=self.ref), 'The master ("golden") workbench that every other file is '
                'compared with.')
        e.grid(row=1, column=1, sticky='ew', padx=4, pady=(4, 0))
        e.bind('<Return>', lambda _: self.set_ref(clean(self.ref.get())))
        tip(ttk.Button(g, text='Browse...', command=self.browse_ref),
            'Pick the master workbench file - it may also be outside the folder.').grid(row=1, column=2, sticky='ew', pady=(4, 0))
        tip(ttk.Button(g, text='Use selected file', command=self.use_selected),
            'Make the file selected in the tree below the master reference.').grid(row=1, column=3, padx=(4, 0), pady=(4, 0))
        g.columnconfigure(1, weight=1)

        opt = ttk.Frame(self)
        opt.pack(fill='x', pady=(6, 2))
        tip(ttk.Checkbutton(opt, text='Also keep a version history (saves a copy in <name>_history each time a file changes)',
                            variable=self.record, command=self.record_changed),
            'On: every time a workbench changes, a copy is saved next to it so you can see its history '
            'and roll back (History tab).\nOff: only compare - nothing is written.').pack(side='left')
        tip(ttk.Label(opt, textvariable=self.summary, font=('Segoe UI', 9, 'bold')),
            'How many workbenches match the reference.').pack(side='right')
        ttk.Label(self, foreground=self.app.pal['hint'], text='Click a file to see how it differs from the reference - double-click opens '
                  'the report in its own window, right-click for more. Files are re-checked automatically when saved.'
                  ).pack(anchor='w', pady=(0, 4))

        tf = ttk.Frame(self)
        tf.pack(fill='both', expand=True)
        t = self.tree = ttk.Treeview(tf, columns=('status', 'modified'), selectmode='browse')
        t.heading('#0', text='Name', anchor='w')
        t.heading('status', text='Compared with reference', anchor='w')
        t.heading('modified', text='Saved', anchor='w')
        t.column('#0', width=380)
        t.column('status', width=320)
        t.column('modified', width=140, stretch=False)
        sb = ttk.Scrollbar(tf, orient='vertical', command=t.yview)
        t.configure(yscrollcommand=sb.set)
        t.pack(side='left', fill='both', expand=True)
        sb.pack(side='left', fill='y')
        bold = tkfont.nametofont('TkDefaultFont').copy()
        bold.configure(weight='bold')
        t.tag_configure('dir', font=bold)
        c = self.app.pal
        t.tag_configure('ref', font=bold, foreground=c['sec'])
        t.tag_configure('same', foreground=c['add'])
        t.tag_configure('diff', foreground=c['chg'])
        t.tag_configure('err', foreground=c['rem'])
        t.tag_configure('pending', foreground=c['hint'])
        t.bind('<<TreeviewSelect>>', lambda _: self.show_selected())
        t.bind('<Double-1>', lambda _: self.popup_selected())
        t.bind('<Button-3>', self.context_menu)
        Tip(t, self.tree_tip)

    def tree_tip(self, e):
        iid = self.tree.identify_row(e.y)
        if not iid:
            return ''
        if iid.startswith('dir:'):
            return 'Sub-folder: how many workbenches in it (and below it) differ from the reference.'
        tags = self.tree.item(iid, 'tags')
        return TREE_TIPS.get(tags[0] if tags else '', '')

    # -------------------------------------------------------------- choosing folder / reference
    def browse_folder(self):
        p = filedialog.askdirectory(initialdir=self.root_dir or None)
        if p:
            self.folder.set(os.path.normpath(p))
            self.load()

    def load(self, folder=None):
        folder = os.path.normpath(os.path.abspath(clean(folder or self.folder.get())))
        if not os.path.isdir(folder):
            messagebox.showerror('vwbhist', 'folder not found: ' + folder)
            return
        self.folder.set(folder)
        self.root_dir, self.files = folder, None
        cfg = self.app.cfg
        cfg['folder'] = folder
        remembered = cfg.setdefault('refs', {}).get(os.path.normcase(folder))
        save_cfg(cfg)
        if remembered and os.path.exists(remembered):
            self.set_ref(remembered)
        elif self.ref_path and not os.path.exists(self.ref_path):
            self.set_ref('')
        else:
            self.check()
        if not self.ref_path:
            self.app.status.set('Now pick the master reference: select a file and click "Use selected file" '
                                '(or right-click it -> Set as reference).')

    def browse_ref(self):
        p = filedialog.askopenfilename(filetypes=FILETYPES, initialdir=self.root_dir or None)
        if p:
            self.set_ref(p)

    def use_selected(self):
        p = self.selected_file()
        if p:
            self.set_ref(p)
        else:
            messagebox.showinfo('vwbhist', 'Select a workbench in the tree first.')

    def set_ref(self, p):
        if p:
            p = os.path.normpath(os.path.abspath(p))
            if not os.path.isfile(p):
                messagebox.showerror('vwbhist', 'file not found: ' + p)
                return
        self.ref.set(p)
        self.ref_path = p or None
        self.ref_key = stat_key(p) if p else None
        if self.root_dir and p:
            self.app.cfg.setdefault('refs', {})[os.path.normcase(self.root_dir)] = p
            save_cfg(self.app.cfg)
        self.gen += 1
        self.check()
        if p:
            self.app.status.set('Reference: %s - comparing every file with it.' % os.path.basename(p))
            self.show_selected()

    def record_changed(self):
        self.rec = self.record.get()
        self.gen += 1  # re-run everything so the current state of each file is recorded too
        self.check()

    def set_verbose(self, vb):
        self.vb = vb
        self.gen += 1
        self.check()

    # -------------------------------------------------------------- scanning (UI thread, every POLL_MS)
    def scan(self):
        out = []
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if not d.endswith('_history') and not d.startswith('.')]
            out += [os.path.join(root, f) for f in files if f.lower().endswith(('.pvwb', '.pset'))]
        return sorted(out, key=str.lower)

    def _tick(self):
        try:
            if self.root_dir and os.path.isdir(self.root_dir):
                self.check()
        finally:
            self.tick_id = self.after(self.POLL_MS, self._tick)

    def check(self):
        """Find new, removed and re-saved files and queue the comparisons that are out of date."""
        if not self.root_dir:
            return
        files = self.scan()
        if files != self.files:
            self.rebuild(files)
        if self.ref_path:
            rk = stat_key(self.ref_path)
            if rk != self.ref_key:  # reference itself was re-saved: compare everything again
                self.ref_key = rk
                self.gen += 1
        for p in files:
            k = stat_key(p)
            if k is None:
                continue
            self.keys[p] = k
            w = (self.gen,) + k
            if self.ref_path and self.want.get(p) != w:
                self.want[p] = w
                self.jobs.put((p, w, self.ref_path, self.vb, self.rec))
        self.paint_all()

    def rebuild(self, files):
        sel = self.selected_file()
        t = self.tree
        t.delete(*t.get_children())
        tree = {'dirs': {}, 'files': []}
        for p in files:
            rel = os.path.relpath(os.path.dirname(p), self.root_dir)
            node = tree
            for part in ([] if rel == '.' else rel.split(os.sep)):
                node = node['dirs'].setdefault(part, {'dirs': {}, 'files': []})
            node['files'].append(p)
        self._insert('', tree, self.root_dir)
        self.files = files
        if sel and t.exists(sel):
            t.selection_set(sel)
            t.see(sel)

    def _insert(self, parent, node, path):
        for name in sorted(node['dirs'], key=str.lower):  # folders first, like Explorer
            p = os.path.join(path, name)
            iid = self.tree.insert(parent, 'end', iid='dir:' + p, text=name, open=True, tags=('dir',))
            self._insert(iid, node['dirs'][name], p)
        for p in node['files']:
            self.tree.insert(parent, 'end', iid=p, text=os.path.basename(p))

    # -------------------------------------------------------------- painting
    def result(self, p):
        r = self.results.get(p)
        return r if r and r[0] == self.want.get(p) else None

    def paint_all(self):
        for p in self.files or []:
            self.paint(p)
        n_diff, n_all, n_wait = self.paint_dir('')
        if not self.files:
            self.summary.set('no workbenches in this folder' if self.root_dir else '')
        elif not self.ref_path:
            self.summary.set('%d workbenches - pick a reference' % len(self.files))
        else:
            self.summary.set('%d compared: %d same, %d differ%s' % (
                n_all, n_all - n_diff - n_wait, n_diff, ', %d checking...' % n_wait if n_wait else ''))

    def paint(self, p):
        if not self.tree.exists(p):
            return
        k = self.keys.get(p)
        mod = time.strftime('%Y-%m-%d %H:%M', time.localtime(k[0])) if k else ''
        r = self.result(p)
        if same_file(p, self.ref_path):
            st, tag = '★ reference', 'ref'
        elif not self.ref_path:
            st, tag = '', ''
        elif r is None:
            st, tag = 'checking...', 'pending'
        elif r[3]:
            st, tag = 'cannot read: ' + r[3], 'err'
        elif r[2] == 0:
            st, tag = '✓ same as reference', 'same'
        else:
            st, tag = '≠ %d difference%s' % (r[2], '' if r[2] == 1 else 's'), 'diff'
        self.tree.item(p, values=(st, mod), tags=(tag,))

    def paint_dir(self, iid):
        n_diff = n_all = n_wait = 0
        for c in self.tree.get_children(iid):
            if c.startswith('dir:'):
                d, a, w = self.paint_dir(c)
            elif same_file(c, self.ref_path):
                d = a = w = 0
            else:
                r = self.result(c)
                a, w = 1, int(r is None)
                d = int(r is not None and bool(r[2] or r[3]))
            n_diff, n_all, n_wait = n_diff + d, n_all + a, n_wait + w
        if iid:
            self.tree.item(iid, values=(('%d of %d differ' % (n_diff, n_all)) if self.ref_path and n_all else '', ''))
        return n_diff, n_all, n_wait

    # -------------------------------------------------------------- comparisons (worker thread)
    def _worker(self):
        ref_cache = (None, None)
        while True:
            p, w, ref, vb, rec = self.jobs.get()
            if self.want.get(p) != w:
                continue  # superseded by a newer save / new reference
            try:
                age = time.time() - os.path.getmtime(p)
                if age < 1.5:
                    time.sleep(1.5 - age)  # let Perception finish writing
                if rec:
                    V.snapshot(p, 'auto (folder view)', quiet=True)
                if same_file(p, ref):
                    res = ('', 0, None)
                else:
                    rk = (ref, w[0], vb)
                    if ref_cache[0] != rk:
                        ref_cache = (rk, V.model(ref, vb))
                    rep, n = V.diff_models(ref_cache[1], V.model(p, vb),
                                           'reference ' + os.path.basename(ref), os.path.basename(p))
                    res = (rep, n, None)
            except BaseException as ex:
                res = ('# %s\n\ncannot read: %s' % (os.path.basename(p), fmt_error(ex)), 0, fmt_error(ex))
            self.app.q.put(('folder', p, w, res))

    def on_result(self, p, w, res):
        if self.want.get(p) != w:
            return
        prev = self.results.get(p)
        self.results[p] = (w,) + res
        self.paint_all()
        if prev and prev[0][1:] != w[1:] and not same_file(p, self.ref_path):  # the file itself was re-saved
            self.app.status.set('%s  %s saved - %s' % (time.strftime('%H:%M:%S'), os.path.basename(p),
                                                       self.tree.set(p, 'status') if self.tree.exists(p) else ''))
        if same_file(p, self.selected_file()):
            self.show_selected()

    # -------------------------------------------------------------- selection, pop-ups, menu
    def selected_file(self):
        sel = self.tree.selection()
        return sel[0] if sel and not sel[0].startswith('dir:') else None

    def report_for(self, p):
        name = os.path.basename(p)
        if same_file(p, self.ref_path):
            return name + ' (reference)', ('# %s is the master reference\n\nEvery other workbench in the folder is '
                                           'compared with this file.' % name)
        if not self.ref_path:
            return name, '# No reference chosen yet\n\nSelect the master workbench and click "Use selected file".'
        r = self.result(p)
        if r is None:
            return name, '# %s\n\nchecking...' % name
        return '%s  vs  reference %s' % (name, os.path.basename(self.ref_path)), r[1]

    def show_selected(self):
        p = self.selected_file()
        if p:
            self.app.show(*self.report_for(p))

    def popup_selected(self):
        p = self.selected_file()
        if p:
            self.app.popup(*self.report_for(p))

    def context_menu(self, e):
        iid = self.tree.identify_row(e.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        m = tk.Menu(self, tearoff=0)
        if iid.startswith('dir:'):
            m.add_command(label='Open folder', command=lambda: os.startfile(iid[4:]))
        else:
            m.add_command(label='Show differences in a new window', command=self.popup_selected)
            m.add_command(label='Set as reference', command=lambda: self.set_ref(iid))
            m.add_command(label='Version history...', command=lambda: self.app.open_history(iid))
            m.add_separator()
            m.add_command(label='Open in Perception', command=lambda: os.startfile(iid))
            m.add_command(label='Open containing folder', command=lambda: os.startfile(os.path.dirname(iid)))
        m.tk_popup(e.x_root, e.y_root)


# ----------------------------------------------------------------------------------------------
# Main window
# ----------------------------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self, target=''):
        super().__init__()
        self.title('vwbhist %s - Perception workbench history' % APP_VERSION)
        self.geometry('1150x800')
        self.minsize(800, 500)
        self.dark = windows_dark() and sv_ttk is not None
        self.pal = DARK if self.dark else LIGHT
        if sv_ttk:
            apply_theme(self, self.dark)
        if self.dark:
            dark_title_bar(self)
        Tip.pal = self.pal
        self.bind_all('<F1>', lambda _: self.help())
        self.q = queue.Queue()
        self.busy = 0
        self.rows = []
        self.cfg = load_cfg()
        self.wb = tk.StringVar()
        self.verbose = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value='Choose a folder and a master reference workbench.')
        self._build()
        self.verbose.trace_add('write', lambda *_: self.folder_view.set_verbose(self.verbose.get()))
        self.poll_id = self.after(100, self._poll)
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        if target and os.path.isfile(target):
            self.open_history(target)
            self.folder_view.load(os.path.dirname(os.path.abspath(target)))
            self.nb.select(self.hist_tab)
        elif target and os.path.isdir(target):
            self.folder_view.load(target)
        elif self.cfg.get('folder') and os.path.isdir(self.cfg['folder']):
            self.folder_view.load(self.cfg['folder'])

    # ------------------------------------------------------------------ layout
    def _build(self):
        bottom = ttk.Frame(self)
        bottom.pack(fill='x', side='bottom')
        tip(ttk.Button(bottom, text='About', command=self.about, width=7),
            'Version, developer and support status.').pack(side='right', padx=(0, 6))
        tip(ttk.Button(bottom, text='? Help', command=self.help, width=7),
            'How to use vwbhist (F1).').pack(side='right', padx=(0, 4))
        tip(ttk.Checkbutton(bottom, text='Include display/layout details', variable=self.verbose),
            'Also compare display layout, window positions and similar details.\n'
            'Off: only real setup changes are reported.').pack(side='right', padx=6)
        ttk.Label(bottom, textvariable=self.status, relief='sunken', anchor='w', padding=(6, 2)).pack(fill='x', side='left', expand=True)

        pw = ttk.PanedWindow(self, orient='vertical')
        pw.pack(fill='both', expand=True, padx=8, pady=8)
        nb = self.nb = ttk.Notebook(pw)
        pw.add(nb, weight=3)
        self.folder_view = FolderView(nb, self)
        nb.add(self.folder_view, text='  Folder vs reference  ')
        self.hist_tab = self._history_tab(nb)
        nb.add(self.hist_tab, text='  History  ')
        nb.add(self._compare_tab(nb), text='  Compare two files  ')
        self.report_view = ReportView(pw, self)
        pw.add(self.report_view, weight=2)

    def _history_tab(self, parent):
        f = ttk.Frame(parent, padding=6)
        top = ttk.Frame(f)
        top.pack(fill='x', pady=(0, 6))
        ttk.Label(top, text='Workbench:').pack(side='left')
        e = tip(ttk.Entry(top, textvariable=self.wb), 'The workbench whose history you want to see.\n'
                'Type a path and press Enter, or use Browse...')
        e.pack(side='left', fill='x', expand=True, padx=4)
        e.bind('<Return>', lambda _: self.refresh())
        tip(ttk.Button(top, text='Browse...', command=self.browse_wb), 'Choose a workbench.').pack(side='left')

        bar = ttk.Frame(f)
        bar.pack(fill='x')
        tip(ttk.Button(bar, text='Snapshot now', command=self.do_snapshot),
            'Save the workbench as it is now as a new version.\n'
            'Nothing is saved if its setup has not changed since the last version.').pack(side='left')
        ttk.Label(bar, text='Note:').pack(side='left', padx=(8, 2))
        self.note = tip(ttk.Entry(bar, width=36), 'Optional note stored with the version, '
                        'e.g. "set min pulse width to 5 us".\nPress Enter to take the snapshot.')
        self.note.pack(side='left')
        self.note.bind('<Return>', lambda _: self.do_snapshot())
        ttk.Separator(bar, orient='vertical').pack(side='left', fill='y', padx=10)
        tip(ttk.Button(bar, text='Show changes', command=self.do_changes),
            'One version selected: what changed in that save.\n'
            'Two selected (Ctrl+click): everything that differs between them.\n'
            'Nothing selected: the last save.').pack(side='left')
        tip(ttk.Button(bar, text='Selected vs file on disk', command=self.do_vs_current),
            'What differs between the selected version (or the latest one) and the workbench file as it is now.'
            ).pack(side='left', padx=4)
        tip(ttk.Button(bar, text='View settings', command=self.do_settings),
            'The full setup of the selected version as text - or of the current file if nothing is selected.'
            ).pack(side='left')
        ttk.Separator(bar, orient='vertical').pack(side='left', fill='y', padx=10)
        tip(ttk.Button(bar, text='Open in Perception', command=self.open_version),
            'Open the selected version in Perception.\n'
            'To roll back, save it from Perception under the working name.').pack(side='left')
        tip(ttk.Button(bar, text='History folder', command=self.open_folder),
            'Open the <name>_history folder with all saved copies and text reports.').pack(side='left', padx=4)
        tip(ttk.Button(bar, text='Refresh', command=self.refresh), 'Re-read the list of versions.').pack(side='right')

        ttk.Label(f, foreground=self.pal['hint'], text='Select one version to see what changed in it, two (Ctrl+click) to compare them. '
                  'Double-click = show changes.').pack(anchor='w', pady=(6, 2))
        tf = ttk.Frame(f)
        tf.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(tf, columns=[c[0] for c in COLS], show='headings', selectmode='extended')
        for key, title, w in COLS:
            self.tree.heading(key, text=title, anchor='w')
            self.tree.column(key, width=w, anchor='w', stretch=key in ('summary', 'note'))
        sb = ttk.Scrollbar(tf, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='left', fill='y')
        self.tree.bind('<Double-1>', lambda _: self.do_changes())
        Tip(self.tree, lambda e: 'Saved versions, oldest first. Double-click one to see what changed in it; '
            'Ctrl+click two and click Show changes to compare them.' if self.tree.identify_row(e.y) else '')
        return f

    def _compare_tab(self, parent):
        f = ttk.Frame(parent, padding=10)
        self.cmp = [tk.StringVar(), tk.StringVar()]
        for i, lab in enumerate(('Workbench A (before):', 'Workbench B (after):')):
            ttk.Label(f, text=lab).grid(row=i, column=0, sticky='w', pady=3)
            what = ('The "before" workbench.', 'The "after" workbench.')[i]
            tip(ttk.Entry(f, textvariable=self.cmp[i]), what).grid(row=i, column=1, sticky='ew', padx=4)
            tip(ttk.Button(f, text='Browse...', command=lambda i=i: self.browse_cmp(i)), what).grid(row=i, column=2)
        f.columnconfigure(1, weight=1)
        bar = ttk.Frame(f)
        bar.grid(row=2, column=1, sticky='w', pady=8)
        tip(ttk.Button(bar, text='Compare', command=self.do_compare),
            'List every setup difference from A to B.').pack(side='left')
        tip(ttk.Button(bar, text='Swap A/B', command=self.swap_cmp),
            'Swap A and B, so the report reads the other way round.').pack(side='left', padx=4)
        ttk.Label(f, foreground=self.pal['hint'], text='Use this for two test cells, or a colleague\'s workbench vs yours. '
                  'Files are only read.').grid(row=3, column=1, sticky='w')
        return f

    # ------------------------------------------------------------------ background work
    def run(self, label, fn, done):
        """Run fn() in a thread (parsing a workbench takes a moment), then done(result) in the UI thread."""
        self.busy += 1
        self.status.set(label + ' ...')
        self.config(cursor='watch')

        def work():
            try:
                self.q.put(('done', done, fn(), None))
            except BaseException as ex:  # SystemExit from resolve() too
                self.q.put(('done', done, None, ex))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == 'folder':
                    self.folder_view.on_result(*msg[1:])
                    continue
                _, done, result, ex = msg
                self.busy -= 1
                if not self.busy:
                    self.config(cursor='')
                if ex is not None:
                    self.status.set(fmt_error(ex))
                    messagebox.showerror('vwbhist', fmt_error(ex))
                else:
                    done(result)
        except queue.Empty:
            pass
        self.poll_id = self.after(100, self._poll)

    def on_close(self):
        self.after_cancel(self.poll_id)
        self.folder_view.after_cancel(self.folder_view.tick_id)
        self.destroy()

    # ------------------------------------------------------------------ reports
    def show(self, title, text):
        self.report_view.show(title, text)

    def popup(self, title, text):
        w = tk.Toplevel(self)
        w.title(title)
        w.geometry('1000x600')
        if self.dark:
            dark_title_bar(w)
        rv = ReportView(w, self)
        rv.pack(fill='both', expand=True, padx=8, pady=8)
        rv.show(title, text)
        return rv

    def help(self):
        """Help window, scrolled to the section for the tab in front."""
        rv = self.popup('vwbhist help', HELP)
        rv.text.config(wrap='word', font=('Segoe UI', 10))
        rv.text.tag_configure('head', font=('Segoe UI', 13, 'bold'))
        rv.text.tag_configure('sec', font=('Segoe UI', 11, 'bold'))
        for tag in ('chg', 'rem', 'add'):
            rv.text.tag_configure(tag, font=('Consolas', 10))
        tab = self.nb.index('current')
        pos = rv.text.search(('## Folder vs reference', '## History tab', '## Compare two files')[tab], '1.0')
        if pos and tab:
            rv.text.yview(pos)

    def about(self):
        w = tk.Toplevel(self)
        w.title('About vwbhist')
        w.resizable(False, False)
        w.transient(self)
        if self.dark:
            dark_title_bar(w)
        f = ttk.Frame(w, padding=(24, 18))
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='vwbhist', font=('Segoe UI', 18, 'bold')).pack(anchor='w')
        ttk.Label(f, text='Version %s' % APP_VERSION).pack(anchor='w')
        ttk.Label(f, text='Version history and setup comparison for HBK Perception workbenches (.pVWB / .pSet).',
                  wraplength=440, justify='left').pack(anchor='w', pady=(10, 0))
        ttk.Label(f, text='Developed by ' + AUTHOR, font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(10, 0))
        ttk.Label(f, text='BETA - UNSUPPORTED', font=('Segoe UI', 11, 'bold'),
                  foreground=self.pal['rem']).pack(anchor='w', pady=(14, 2))
        ttk.Label(f, wraplength=440, justify='left', text=(
            'This is a beta project and is provided as is, without support or warranty of any kind. '
            'It is not an official HBK product and is not supported by HBK. '
            'Check important settings in Perception itself before relying on a result.\n\n'
            'Your workbench files are only ever read, never changed.')).pack(anchor='w')
        link = ttk.Label(f, text=REPO_URL, foreground=self.pal['sec'], cursor='hand2')
        link.pack(anchor='w', pady=(12, 0))
        link.bind('<Button-1>', lambda _: __import__('webbrowser').open(REPO_URL))
        tip(link, 'Source code and updates (opens in your browser).')
        ttk.Button(f, text='OK', command=w.destroy, width=10).pack(anchor='e', pady=(16, 0))
        w.bind('<Escape>', lambda _: w.destroy())
        w.update_idletasks()
        w.geometry('+%d+%d' % (self.winfo_rootx() + (self.winfo_width() - w.winfo_reqwidth()) // 2,
                               self.winfo_rooty() + (self.winfo_height() - w.winfo_reqheight()) // 3))
        w.grab_set()
        w.focus_set()

    # ------------------------------------------------------------------ history tab
    def browse_wb(self):
        p = filedialog.askopenfilename(filetypes=FILETYPES)
        if p:
            self.wb.set(os.path.normpath(p))
            self.refresh()

    def open_history(self, p):
        self.wb.set(os.path.normpath(os.path.abspath(p)))
        self.refresh()
        self.nb.select(self.hist_tab)

    def need_wb(self):
        wb = clean(self.wb.get())
        if not wb:
            messagebox.showinfo('vwbhist', 'Choose a workbench first (Browse...).')
        return wb

    def refresh(self, quiet=False):
        wb = clean(self.wb.get())
        keep = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        self.rows = V.read_log(wb) if wb else []
        for r in self.rows:
            if not self.tree.exists(r[0]):
                self.tree.insert('', 'end', iid=r[0], values=r)
        sel = [i for i in keep if self.tree.exists(i)]
        if sel:
            self.tree.selection_set(sel)
        if self.rows:
            self.tree.see(self.rows[-1][0])
        if not quiet and wb:
            self.status.set('%d version(s) of %s' % (len(self.rows), os.path.basename(wb)) if self.rows else
                            'No history yet for %s - click "Snapshot now" to save the first version.' % os.path.basename(wb))

    def selected(self):
        order = [r[0] for r in self.rows]
        return sorted(self.tree.selection(), key=order.index)

    def vpath(self, name):
        return os.path.join(V.hist_dir(clean(self.wb.get())), name)

    def do_snapshot(self):
        wb = self.need_wb()
        if not wb:
            return
        note = self.note.get().strip()

        def done(name):
            self.refresh(quiet=True)
            if name:
                self.note.delete(0, 'end')
                self.status.set('saved ' + name)
                self.tree.selection_set([name])
                self.do_changes()
            else:
                self.status.set('No setup change since the last version - nothing saved.')
        self.run('saving snapshot', lambda: V.snapshot(wb, note, quiet=True), done)

    def diff(self, p1, l1, p2, l2):
        vb = self.verbose.get()
        self.run('comparing %s and %s' % (l1, l2),
                 lambda: V.diff_models(V.model(p1, vb), V.model(p2, vb), l1, l2),
                 lambda r: (self.show('%s  ->  %s' % (l1, l2), r[0]),
                            self.status.set('%d setup differences' % r[1])))

    def do_changes(self):
        if not self.need_wb():
            return
        order = [r[0] for r in self.rows]
        sel = self.selected()
        if not sel:
            if len(order) < 2:
                self.status.set('Need at least two saved versions.')
                return
            sel = order[-1:]
        if len(sel) == 1:
            i = order.index(sel[0])
            if i == 0:
                return self.settings_of(self.vpath(sel[0]), sel[0],
                                        '%s is the first version - showing its full settings.' % sel[0])
            a, b = order[i - 1], sel[0]
        else:
            a, b = sel[0], sel[-1]
        self.diff(self.vpath(a), a, self.vpath(b), b)

    def do_vs_current(self):
        wb = self.need_wb()
        sel = self.selected()
        if not wb:
            return
        if not sel and self.rows:
            sel = [self.rows[-1][0]]
        if not sel:
            self.status.set('No saved versions yet.')
            return
        self.diff(self.vpath(sel[0]), sel[0], os.path.abspath(wb), 'file on disk')

    def do_settings(self):
        wb = self.need_wb()
        if not wb:
            return
        sel = self.selected()
        if sel:
            self.settings_of(self.vpath(sel[0]), sel[0])
        else:
            self.settings_of(os.path.abspath(wb), os.path.basename(wb))

    def settings_of(self, path, label, note=''):
        vb = self.verbose.get()
        self.run('reading ' + label, lambda: V.dump_text(V.model(path, vb)),
                 lambda txt: (self.show('Settings of ' + label, '# %s : full setup\n\n%s' % (label, txt)),
                              self.status.set(note or 'full setup of ' + label)))

    def open_version(self):
        sel = self.selected()
        path = self.vpath(sel[0]) if sel else clean(self.wb.get())
        if not path:
            return
        if not os.path.exists(path):
            messagebox.showerror('vwbhist', 'file not found: ' + path)
        elif sel and not messagebox.askokcancel(
                'vwbhist', 'Open %s in Perception?\n\nTo roll back, save it from Perception under the working name.' % sel[0]):
            return
        else:
            os.startfile(path)

    def open_folder(self):
        wb = self.need_wb()
        if wb:
            d = V.hist_dir(wb)
            os.startfile(d if os.path.isdir(d) else os.path.dirname(os.path.abspath(wb)))

    # ------------------------------------------------------------------ compare tab
    def browse_cmp(self, i):
        p = filedialog.askopenfilename(filetypes=FILETYPES)
        if p:
            self.cmp[i].set(os.path.normpath(p))

    def swap_cmp(self):
        a, b = self.cmp[0].get(), self.cmp[1].get()
        self.cmp[0].set(b)
        self.cmp[1].set(a)

    def do_compare(self):
        a, b = (clean(v.get()) for v in self.cmp)
        if not (a and b):
            messagebox.showinfo('vwbhist', 'Choose two workbenches to compare.')
            return
        self.diff(a, os.path.basename(a), b, os.path.basename(b))


if __name__ == '__main__':
    App(sys.argv[1] if len(sys.argv) > 1 else '').mainloop()
