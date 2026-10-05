"""Small shared UI and local data helpers; no external runtime dependencies."""
import os
from pathlib import Path
from tkinter import ttk

def data_path(name):
    base = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share'))
    folder = base / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder / 'data.sqlite3'

def style(root, title, accent):
    root.title(title)
    root.geometry('1020x720')
    root.minsize(820, 620)
    root.configure(bg='#111827')
    theme = ttk.Style(root)
    theme.theme_use('clam')
    theme.configure('.', font=('Segoe UI', 10))
    theme.configure('TFrame', background='#111827')
    theme.configure('TLabel', background='#111827', foreground='#e5e7eb')
    theme.configure('Title.TLabel', font=('Segoe UI', 26, 'bold'), foreground=accent)
    theme.configure('Muted.TLabel', foreground='#a8b4c6')
    theme.configure('Clock.TLabel', font=('Consolas', 66, 'bold'), foreground=accent)
    theme.configure('TButton', padding=(12, 8), background='#25334a', foreground='#ffffff')
    theme.map('TButton', background=[('active', '#384b68')], foreground=[('disabled', '#8793a5')])
    theme.configure('TEntry', fieldbackground='#f3f4f6', foreground='#111827', padding=6)
    theme.configure('Treeview', rowheight=30, background='#182235', fieldbackground='#182235', foreground='#e5e7eb')
    theme.configure('Treeview.Heading', background='#25334a', foreground='#ffffff', padding=7)
    theme.map('Treeview', background=[('selected', '#365879')])
    theme.configure('TNotebook', background='#111827')
    theme.configure('TNotebook.Tab', padding=(15, 8))

def table(parent, columns):
    frame = ttk.Frame(parent)
    frame.pack(fill='both', expand=True, pady=10)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show='headings')
    for key, title, width in columns:
        tree.heading(key, text=title)
        tree.column(key, width=width, minwidth=70)
    scroll = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
    horizontal = ttk.Scrollbar(frame, orient='horizontal', command=tree.xview)
    tree.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    tree.grid(row=0, column=0, sticky='nsew')
    scroll.grid(row=0, column=1, sticky='ns')
    horizontal.grid(row=1, column=0, sticky='ew')
    return tree
