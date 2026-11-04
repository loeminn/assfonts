"""Exercise SubOxide's two-pass pipeline with real fonts and parallel processes."""
import concurrent.futures
from pathlib import Path
import subprocess
import sys
import tempfile

binary = str(Path(sys.argv[1]).resolve())
from cli_fixture import subtitle


def run(*args):
    result = subprocess.run([binary, *map(str, args)], capture_output=True,
                            text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)


with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    db = root / "db"
    db.mkdir()
    run("-b", "-f", "/usr/share/fonts/truetype/dejavu", "-d", db)
    assert (db / "fonts.json").is_file()

    def process(index):
        work = root / str(index)
        work.mkdir()
        source = work / "字幕.ass"
        source.write_text(subtitle, encoding="utf-8")
        subset = work / "subset"
        embed = work / "embed"
        subset.mkdir()
        embed.mkdir()
        run("-s", "-r", "-i", source, "-o", subset, "-d", db)
        renamed = subset / "字幕.rename.ass"
        assert renamed.is_file()
        font_dirs = list(subset.glob("*_subsetted"))
        assert len(font_dirs) == 1
        # Match the application: embedding uses the temporary subset fonts.
        run("-e", "-i", renamed, "-o", embed, "-f", font_dirs[0])
        outputs = list(embed.glob("*.ass"))
        assert len(outputs) == 1
        content = outputs[0].read_text(encoding="utf-8")
        assert "[Fonts]" in content and "fontname:" in content
        assert "Batch test 123" in content

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(process, range(32)))
print("32 subtitles subsetted and embedded successfully (2 concurrent processes)")
