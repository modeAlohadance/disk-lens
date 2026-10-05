"""Publish a draft Windows release using GitHub Actions' scoped token."""
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

repo = os.environ['GITHUB_REPOSITORY']
sha = os.environ['GITHUB_SHA']
name = os.environ['APP_NAME']
tag = os.environ.get('RELEASE_TAG', 'v0.1.0')
if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', tag):
    raise ValueError('Use a version such as v0.1.0')

def api(path, data=None, method=None, binary=None):
    url = path if path.startswith('https://') else 'https://api.github.com' + path
    if urllib.parse.urlparse(url).hostname not in {'api.github.com', 'uploads.github.com'}:
        raise ValueError('Unexpected API host')
    headers = {'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
               'Accept': 'application/vnd.github+json', 'User-Agent': name + '-release'}
    payload = json.dumps(data).encode() if data is not None else binary
    if payload is not None:
        headers['Content-Type'] = 'application/octet-stream' if binary is not None else 'application/json'
    req = urllib.request.Request(url, data=payload, headers=headers, method=method or ('POST' if payload is not None else 'GET'))
    with urllib.request.urlopen(req, timeout=120) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}

prefix = '/repos/' + repo
releases = api(prefix + '/releases?per_page=100')
existing = next((release for release in releases if release['tag_name'] == tag), None)
if existing and not existing['draft']:
    raise RuntimeError('This version is already public. Choose a new tag; published releases are never overwritten.')
notes = (f'{name} для Windows x64. Скачайте {name}.exe и запустите: Python не требуется. '
         'Интерфейс на русском, работа локально и без аккаунта. EXE не подписан цифровым сертификатом.\n\n'
         'Сборка создана GitHub Actions из опубликованного кода. Перед публикацией выполнены unit-тесты '
         'и проверки запуска интерфейса и EXE. SHA256SUMS.txt содержит контрольную сумму.\n\n'
         f'Исходный коммит: {sha}')
properties = {'tag_name': tag, 'target_commitish': sha, 'name': name + ' ' + tag, 'body': notes, 'draft': True}
release = api(prefix + '/releases/' + str(existing['id']), properties, method='PATCH') if existing else api(prefix + '/releases', properties)
exe = Path('dist') / (name + '.exe')
checksum = Path('dist/SHA256SUMS.txt')
checksum.write_text(hashlib.sha256(exe.read_bytes()).hexdigest() + '  ' + exe.name + '\n', encoding='utf-8')
assets = [exe, checksum]
# Only replace our own incomplete draft assets; published assets are protected above.
for asset in release['assets']:
    if asset['name'] in {file.name for file in assets}:
        api(prefix + '/releases/assets/' + str(asset['id']), method='DELETE')
upload = release['upload_url'].split('{')[0]
for file in assets:
    api(upload + '?name=' + urllib.parse.quote(file.name), binary=file.read_bytes())
released = api(prefix + '/releases/' + str(release['id']), {'draft': False}, method='PATCH')
print(released['html_url'])
