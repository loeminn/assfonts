"""Real CLI regressions for worker exceptions and processing exit status."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from cli_fixture import subtitle

binary = str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    db = root / 'db'
    out = root / 'out'
    db.mkdir()
    out.mkdir()
    good = root / 'good.ass'
    good.write_text(subtitle)
    bad = root / 'bad.ass'
    bad.write_text('Invalid ASS input')

    def run(inputs, extra=(), failed=True):
        result = subprocess.run([binary, '-i', *map(str, inputs), '-o', str(out),
                                 '-d', str(db), *extra], capture_output=True,
                                text=True, timeout=10)
        assert (result.returncode != 0) == failed, result
        return result

    # A missing font is a processing error, including when logs are disabled.
    for verbosity in range(4):
        result = run([good], ['-v', str(verbosity)])
        if verbosity == 0:
            assert not result.stdout and not result.stderr, result
    run([bad])
    run([good], ['-m', '0'])

    # This database entry throws std::out_of_range inside FindFont.
    record = dict(families=['dejavu sans'], fullnames=[], psnames=[],
                  weight=400, slant=0, path='x', index=0, last_write_time='')
    (db / 'fonts.json').write_text(json.dumps([record]))
    for extra in ([], ['-v', '0']):
        result = run([good], extra)
        if not extra:
            assert 'Subtitle task failed:' in result.stdout, result

    # A failed first subtitle must not prevent a later valid one completing.
    subprocess.run([binary, '-b', '-f', '/usr/share/fonts/truetype/dejavu',
                    '-d', str(db)], check=True, capture_output=True, timeout=30)
    for workers in ('1', '2'):
        output = out / 'good.assfonts.ass'
        output.unlink(missing_ok=True)
        run([bad, good], ['-m', workers])
        assert '[Fonts]' in output.read_text()
    run([good], failed=False)
print('CLI failures exit nonzero; exceptions complete; mixed batches continue')
