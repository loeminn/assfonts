"""Upstream #35: derived face names, precedence, database migration and TTCs."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from fontTools.ttLib import TTCollection, TTFont
from cli_fixture import subtitle

binary = str(Path(sys.argv[1]).resolve())
font_root = Path('/usr/share/fonts/truetype/dejavu')


def make_font(bold, family, full, typographic=None):
    font = TTFont(font_root / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'))
    font['name'].names = []
    entries = {1: family, 2: 'Bold' if bold else 'Regular', 4: full,
               6: full.replace(' ', '-')}
    if typographic:
        entries.update({16: typographic, 17: 'Heavy'})
    for key, value in entries.items():
        font['name'].setName(value, key, 3, 1, 0x409)
    return font


with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    fonts = root / 'fonts'
    fonts.mkdir()
    db = root / 'db'
    db.mkdir()
    make_font(False, 'Issue35 Demo', 'Issue35 Regular Face').save(fonts / 'regular.ttf')
    bold = make_font(True, 'Issue35 Demo', 'Issue35 Bold Face', 'Issue35 Typographic')
    for key, value in {1: '测试字体', 2: '粗体',
                       16: '排印测试字体', 17: '特粗'}.items():
        bold['name'].setName(value, key, 3, 1, 0x804)
    # These must never be combined across language or encoding records.
    bold['name'].setName('Unpaired Language', 1, 3, 1, 0x411)
    bold['name'].setName('Unpaired Encoding', 1, 3, 10, 0x409)
    bold.save(fonts / 'bold.ttf')

    def run(name, query, flags=(), scan=fonts, database=db, success=True):
        work = root / name
        work.mkdir()
        source = work / 'input.ass'
        source.write_text(subtitle.replace('DejaVu Sans', query), encoding='utf-8')
        args = [binary, '-i', str(source), '-o', str(work), '-d', str(database), *flags]
        if scan is not None:
            args += ['-f', str(scan)]
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        assert (result.returncode == 0) == success, result.stdout + result.stderr
        return work, result.stdout

    for alias_index, query in enumerate(['Issue35 Demo Bold',
                                         'Issue35 Typographic Heavy',
                                         '排印测试字体 特粗']):
        for mode, flags in [('embed', ['-e']), ('subset', []), ('rename', ['-r'])]:
            work, log = run(f'{alias_index}-{mode}', query, flags)
            assert f'"{fonts / "bold.ttf"}"[0]' in log, log
            output = work / ('input.rename.assfonts.ass' if mode == 'rename' else 'input.assfonts.ass')
            assert '[Fonts]' in output.read_text(encoding='utf-8')
            if mode != 'embed':
                font_dir, = work.glob('*_subsetted')
                # Use only generated fonts and an empty database. A successful
                # initial match must survive subsetting, including name IDs 16/17.
                source = work / ('input.rename.ass' if mode == 'rename' else 'input.ass')
                result = subprocess.run([binary, '-e', '-i', str(source),
                                         '-o', str(work), '-f', str(font_dir), '-d', str(db)],
                                        capture_output=True, text=True, timeout=30)
                assert result.returncode == 0, result.stdout + result.stderr
    for index, name in enumerate(['Issue35 Typographic Heavy', '测试字体 粗体',
                                   'issue35 demo bold', 'Issue35 Bold Face',
                                   'Issue35-Bold-Face']):
        _, log = run('name-' + str(index), name, ['-e'])
        assert f'"{fonts / "bold.ttf"}"[0]' in log, log
    _, log = run('family', 'Issue35 Demo', ['-e'])
    assert f'"{fonts / "regular.ttf"}"[0]' in log, log
    for index, name in enumerate(['Unpaired Language Bold', 'Unpaired Encoding Bold']):
        run('unpaired-' + str(index), name, ['-e'], success=False)

    def build_db():
        result = subprocess.run([binary, '-b', '-f', str(fonts), '-d', str(db)],
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads((db / 'fonts.json').read_text())

    records = build_db()
    bold_record = next(record for record in records if record['path'] == str(fonts / 'bold.ttf'))
    assert 'issue35 demo bold' in bold_record['aliases']
    for mode in ['new', 'old']:
        records_for_test = [dict(record) for record in records]
        if mode == 'old':
            for record in records_for_test:
                record.pop('aliases', None)
        (db / 'fonts.json').write_text(json.dumps(records_for_test))
        _, log = run('database-' + mode, 'Issue35 Demo Bold', ['-e'], scan=None)
        assert f'"{fonts / "bold.ttf"}"[0]' in log, log
    # Rebuilding an old database must not reuse records lacking aliases.
    assert 'issue35 demo bold' in next(record for record in build_db()
                                      if record['path'] == str(fonts / 'bold.ttf'))['aliases']

    # A real name from the database outranks a derived name in a scanned folder.
    exact_dir = root / 'exact'
    exact_dir.mkdir()
    exact = exact_dir / 'exact.ttf'
    make_font(False, 'Other Family', 'Issue35 Demo Bold').save(exact)
    subprocess.run([binary, '-b', '-f', str(exact_dir), '-d', str(db)],
                   check=True, capture_output=True, timeout=30)
    _, log = run('exact-priority', 'Issue35 Demo Bold', ['-e'])
    assert f'"{exact}"[0]' in log, log

    collection_dir = root / 'collection'
    collection_dir.mkdir()
    collection = TTCollection()
    collection.fonts = [make_font(False, 'Collection Demo', 'Collection Regular'),
                        make_font(True, 'Collection Demo', 'Collection Bold Face')]
    collection.save(collection_dir / 'faces.ttc')
    _, log = run('collection-face', 'Collection Demo Bold', ['-e'], scan=collection_dir)
    assert f'"{collection_dir / "faces.ttc"}"[1]' in log, log

print('Font aliases, exact-name precedence, legacy database refresh and TTC face selection passed')
