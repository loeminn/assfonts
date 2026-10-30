"""Exercise SubOxide's two-pass pipeline with real fonts and parallel processes."""
import concurrent.futures
from pathlib import Path
import subprocess
import sys
import tempfile

binary = str(Path(sys.argv[1]).resolve())
subtitle = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,40,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,Default,,0,0,0,,Batch test 123
"""


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
