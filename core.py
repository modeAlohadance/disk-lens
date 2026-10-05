"""Read-only scanner with bounded top-file storage and cooperative cancellation."""
import csv
import heapq
import os
import stat
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from time import monotonic


@dataclass
class Result:
    root: str
    count: int = 0
    total: int = 0
    skipped: int = 0
    errors: int = 0
    error_details: list = field(default_factory=list)
    cancelled: bool = False
    largest: list = field(default_factory=list)
    extensions: dict = field(default_factory=lambda: defaultdict(lambda: [0, 0]))
    folders: dict = field(default_factory=lambda: defaultdict(lambda: [0, 0]))


def scan(folder, cancel=None, progress=None, limit=200):
    root = Path(folder).expanduser().resolve()
    if not root.is_dir():
        raise ValueError('Выберите существующую папку.')
    if limit < 1:
        raise ValueError('Лимит должен быть положительным.')
    cancel = cancel or Event()
    result = Result(str(root))
    stack = [(root, 'Файлы в корне')]
    heap = []
    last_update = monotonic()

    def failure(path, error):
        result.errors += 1
        if len(result.error_details) < 100:
            result.error_details.append(f'{path}: {error}')

    while stack and not cancel.is_set():
        directory, group = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if cancel.is_set():
                        break
                    try:
                        meta = entry.stat(follow_symlinks=False)
                        if stat.S_ISLNK(meta.st_mode) or getattr(meta, 'st_file_attributes', 0) & 0x400:
                            result.skipped += 1
                            continue
                        if stat.S_ISDIR(meta.st_mode):
                            stack.append((Path(entry.path), './' + entry.name if directory == root else group))
                        elif stat.S_ISREG(meta.st_mode):
                            size = meta.st_size
                            result.count += 1
                            result.total += size
                            suffix = Path(entry.name).suffix.lower() or '(без расширения)'
                            for buckets, key in [(result.extensions, suffix), (result.folders, group)]:
                                buckets[key][0] += size
                                buckets[key][1] += 1
                            item = (size, entry.path)
                            if len(heap) < limit:
                                heapq.heappush(heap, item)
                            elif item > heap[0]:
                                heapq.heapreplace(heap, item)
                    except OSError as error:
                        failure(entry.path, error)
                    if progress and monotonic() - last_update > .15:
                        progress(result.count, result.total)
                        last_update = monotonic()
        except OSError as error:
            failure(directory, error)
    result.cancelled = cancel.is_set()
    result.largest = sorted(heap, reverse=True)
    return result


def human_size(size):
    number = float(size)
    for unit in ('Б', 'КиБ', 'МиБ', 'ГиБ', 'ТиБ', 'ПиБ'):
        if number < 1024 or unit == 'ПиБ':
            return f'{number:.1f} {unit}'
        number /= 1024


def export_csv(result, path):
    def safe(value):
        return "'" + value if value.startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value
    with open(path, 'w', encoding='utf-8-sig', newline='') as out:
        writer = csv.writer(out)
        writer.writerow(['Раздел', 'Путь или группа', 'Байты', 'Файлов', 'Неполный отчёт'])
        partial = result.cancelled or result.errors > 0
        writer.writerow(['Итого', safe(result.root), result.total, result.count, partial])
        writer.writerow(['Пропущено ссылок', '', '', result.skipped, partial])
        writer.writerow(['Ошибок доступа', '', '', result.errors, partial])
        for size, filename in result.largest:
            writer.writerow(['Крупный файл', safe(filename), size, 1, partial])
        for title, buckets in [('Расширение', result.extensions), ('Папка', result.folders)]:
            for name, (size, count) in sorted(buckets.items(), key=lambda row: row[1][0], reverse=True):
                writer.writerow([title, safe(name), size, count, partial])
