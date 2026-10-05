"""DiskLens Tk UI. Worker threads never touch widgets."""
import os
import queue
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from core import scan, human_size, export_csv
from ui import style, table


class App:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.running = False
        self.result = None
        self.paths = {}
        style(root, 'DiskLens — куда уходит место', '#6ee7b7')
        page = ttk.Frame(root, padding=24)
        page.pack(fill='both', expand=True)
        ttk.Label(page, text='DiskLens', style='Title.TLabel').pack(anchor='w')
        ttk.Label(page, text='Найдите тяжёлые файлы и оцените размер папок.', style='Muted.TLabel').pack(anchor='w', pady=(0, 15))
        self.folder = tk.StringVar()
        chooser = ttk.Frame(page)
        chooser.pack(fill='x')
        ttk.Entry(chooser, textvariable=self.folder).pack(side='left', fill='x', expand=True)
        ttk.Button(chooser, text='Выбрать…', command=self.choose).pack(side='left', padx=8)
        self.scan_button = ttk.Button(chooser, text='Анализировать', command=self.start)
        self.scan_button.pack(side='left')
        self.stop_button = ttk.Button(chooser, text='Отмена', command=self.cancel.set, state='disabled')
        self.stop_button.pack(side='left', padx=(8, 0))
        self.status = tk.StringVar(value='Выберите папку. Сканирование не изменяет файлы.')
        ttk.Label(page, textvariable=self.status, wraplength=920).pack(anchor='w', pady=12)
        self.progress = ttk.Progressbar(page, mode='indeterminate')
        self.progress.pack(fill='x')
        tabs = ttk.Notebook(page)
        tabs.pack(fill='both', expand=True, pady=12)
        self.tables = {}
        for key, title in [('files', 'Крупные файлы'), ('folders', 'Папки'), ('extensions', 'Типы файлов')]:
            frame = ttk.Frame(tabs)
            tabs.add(frame, text=title)
            self.tables[key] = table(frame, [('name', 'Путь' if key == 'files' else 'Группа', 570), ('size', 'Размер', 150), ('count', 'Файлов', 90)])
        self.tables['files'].bind('<Double-1>', lambda event: self.open_location())
        footer = ttk.Frame(page)
        footer.pack(fill='x')
        ttk.Button(footer, text='Открыть расположение', command=self.open_location).pack(side='left')
        ttk.Button(footer, text='Ошибки доступа', command=self.show_errors).pack(side='left', padx=8)
        self.export_button = ttk.Button(footer, text='Экспорт CSV', command=self.export, state='disabled')
        self.export_button.pack(side='right')
        ttk.Label(page, text='Размеры логические · ссылки пропускаются · в списке до 200 крупнейших файлов', style='Muted.TLabel').pack(anchor='w', pady=(12, 0))
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.poll_id = root.after(100, self.poll)

    def choose(self):
        selected = filedialog.askdirectory()
        if selected:
            self.folder.set(selected)

    def start(self):
        if self.running:
            return
        folder = self.folder.get().strip()
        if not folder:
            self.status.set('Сначала выберите папку.')
            return
        self.running = True
        self.result = None
        self.paths = {}
        for tree in self.tables.values():
            tree.delete(*tree.get_children())
        self.cancel.clear()
        self.scan_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        self.export_button.configure(state='disabled')
        self.progress.start(12)
        self.status.set('Читаем структуру папки…')

        def worker():
            try:
                result = scan(folder, self.cancel, lambda count, size: self.events.put(('progress', (count, size))))
                self.events.put(('done', result))
            except Exception as error:
                self.events.put(('error', str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        # Bounded processing keeps the GUI responsive if the event queue grows.
        for _ in range(20):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'progress':
                self.status.set(f'Просмотрено файлов: {value[0]:,} · {human_size(value[1])}')
            else:
                self.running = False
                self.progress.stop()
                self.scan_button.configure(state='normal')
                self.stop_button.configure(state='disabled')
                if kind == 'error':
                    self.status.set('Анализ не выполнен.')
                    messagebox.showerror('Анализ', value, parent=self.root)
                else:
                    self.result = value
                    self.show_result()
        self.poll_id = self.root.after(100, self.poll)

    def show_result(self):
        result = self.result
        for size, path in result.largest:
            key = self.tables['files'].insert('', 'end', values=(str(Path(path).relative_to(result.root)), human_size(size), 1))
            self.paths[key] = path
        for name, buckets in [('folders', result.folders), ('extensions', result.extensions)]:
            for group, (size, count) in sorted(buckets.items(), key=lambda row: row[1][0], reverse=True):
                self.tables[name].insert('', 'end', values=(group, human_size(size), count))
        state = 'Отменено — частичные данные' if result.cancelled else ('Готово — есть ошибки доступа' if result.errors else 'Готово')
        self.status.set(f'{state} · {result.count:,} файлов · {human_size(result.total)} · ошибок: {result.errors} · пропущено ссылок: {result.skipped}\n{result.root}')
        self.export_button.configure(state='normal')

    def open_location(self):
        selected = self.tables['files'].selection()
        if not selected:
            self.status.set('Выберите файл на вкладке «Крупные файлы».')
            return
        path = Path(self.paths[selected[0]])
        if not path.parent.exists():
            messagebox.showerror('Расположение', 'Папка больше не существует.', parent=self.root)
            return
        try:
            if os.name == 'nt':
                os.startfile(str(path.parent))
            else:
                subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(path.parent)])
        except OSError as error:
            messagebox.showerror('Расположение', str(error), parent=self.root)

    def show_errors(self):
        if self.result:
            messagebox.showinfo('Ошибки доступа (первые 100)', '\n'.join(self.result.error_details) or 'Ошибок доступа нет.', parent=self.root)

    def export(self):
        if not self.result:
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv', initialfile='disk-lens-report.csv', filetypes=[('CSV', '*.csv')])
        if path:
            try:
                export_csv(self.result, path)
            except OSError as error:
                messagebox.showerror('Экспорт', str(error), parent=self.root)

    def close(self):
        self.cancel.set()
        self.root.after_cancel(self.poll_id)
        self.root.destroy()


def main():
    with tempfile.TemporaryDirectory(prefix='disklens-smoke-') as tmp:
        root = tk.Tk()
        app = App(root)
        if '--smoke' in sys.argv:
            (Path(tmp) / 'пример.txt').write_text('Демонстрация', encoding='utf-8')
            app.folder.set(tmp)
            app.start()
            def finish():
                if app.running:
                    root.after(100, finish)
                else:
                    assert app.result is not None and app.result.count == 1
                    app.close()
            root.after(300, finish)
        root.mainloop()


if __name__ == '__main__':
    main()
