"""Regression for upstream #18: style Format order and rename offsets."""
from pathlib import Path
import subprocess
import sys
import tempfile

from cli_fixture import subtitle

binary = str(Path(sys.argv[1]).resolve())
lines = subtitle.splitlines()
format_line = next(line for line in lines if line.startswith('Format:'))
style_line = next(line for line in lines if line.startswith('Style:'))
fields = format_line.partition(':')[2].strip().split(', ')
values = style_line.partition(':')[2].strip().split(',')
style = dict(zip(fields, values))
style.update(Bold='-1', Italic='-1')
# Text contains commas: the shared line splitter must preserve them.
base = subtitle.replace('Batch test 123', 'Batch, test, 123')


def script(order, names=None):
    return base.replace(format_line, 'Format: ' + ', '.join(names or order)).replace(
        style_line, 'Style: ' + ','.join(style[field] for field in order))


with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    db = root / 'db'
    db.mkdir()
    subprocess.run([binary, '-b', '-f', '/usr/share/fonts/truetype/dejavu',
                    '-d', str(db)], check=True, capture_output=True, timeout=30)

    def run(name, content, extra=(), success=True):
        work = root / name
        work.mkdir()
        source = work / 'input.ass'
        source.write_text(content, encoding='utf-8')
        result = subprocess.run([binary, '-i', str(source), '-o', str(work),
                                 '-d', str(db), *extra], capture_output=True,
                                text=True, timeout=30)
        assert (result.returncode == 0) == success, result.stdout + result.stderr
        return work, result.stdout

    # Includes the exact field ordering reported in #18.
    issue_order = ('Name Alignment Angle BackColour Bold BorderStyle Encoding '
                   'Fontname Fontsize Italic MarginL MarginR MarginV Outline '
                   'OutlineColour PrimaryColour ScaleX ScaleY SecondaryColour '
                   'Shadow Spacing StrikeOut Underline').split()
    layouts = [fields, issue_order, list(reversed(fields)),
               ['Italic', 'Bold', 'Name', 'Fontname']]
    for index, order in enumerate(layouts):
        content = script(order, [field.swapcase() for field in order])
        for mode, flags in [('embed', ['-e']), ('subset', []), ('rename', ['-r'])]:
            work, log = run(f'{index}-{mode}', content, flags)
            assert '"DejaVu Sans" (700,100)' in log, log
            output_path = work / ('input.rename.assfonts.ass' if mode == 'rename'
                                  else 'input.assfonts.ass')
            output = output_path.read_text(encoding='utf-8')
            assert '[Fonts]' in output and 'fontname:' in output
            assert 'Batch, test, 123' in output
            output_style = next(line for line in output.splitlines()
                                if line.startswith('Style:')).partition(':')[2].strip().split(',')
            for field, value in zip(order, output_style):
                if mode == 'rename' and field == 'Fontname':
                    assert value and value != style[field]
                else:
                    assert value == style[field], (field, value)
            if mode == 'rename':
                # Verify that the renamed style resolves against generated fonts.
                font_dir, = work.glob('*_subsetted')
                result = subprocess.run([binary, '-e', '-i', str(work / 'input.rename.ass'),
                                         '-o', str(work), '-f', str(font_dir)],
                                        capture_output=True, text=True, timeout=30)
                assert result.returncode == 0, result.stdout + result.stderr

    run('legacy', script(fields).replace(format_line + '\n', ''), ['-e'])
    run('ssa', script(fields).replace('[V4+ Styles]', '[V4 Styles]'), ['-e'])
    for field in ['Name', 'Fontname', 'Bold', 'Italic']:
        order = [entry for entry in fields if entry != field]
        run('missing-' + field, script(order), success=False)
    run('duplicate', script(fields, fields[:-1] + ['Fontname']), success=False)
    run('short-row', script(fields).replace(',10,10,10,1', ',10'), success=False)
    run('extra-field', script(fields).replace(',10,10,10,1', ',10,10,10,1,extra'), success=False)
    run('empty-format', base.replace(format_line, 'Format:'), success=False)
    run('empty-font', script(fields).replace('DejaVu Sans', ''), success=False)

print('Style Format ordering, rename round-trip, legacy fallback and invalid formats passed')
