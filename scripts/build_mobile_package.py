"""Build a portable archive of the mobile web app and its full source corpus."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "bilam-mobile-web.zip"
BACKEND = (
    "app.py", "server.py", "corpus_reader.py", "requirements.txt", "Procfile",
)
FRONTEND = (
    "index.html", "app.js", "style.css", "manifest.json", "service-worker.js",
)


def main():
    files = [ROOT / "MOBILE.md"]
    files.extend(ROOT / "backend" / name for name in BACKEND)
    files.extend(ROOT / "frontend" / name for name in FRONTEND)
    files.extend(path for path in (ROOT / "frontend" / "icons").iterdir() if path.is_file())
    files.extend(
        path for path in (ROOT / "plugins" / "bilam-standalone").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )
    missing = [str(path.relative_to(ROOT)) for path in files if not path.is_file()]
    if missing:
        raise SystemExit(f"Missing package files: {', '.join(missing)}")
    OUTPUT.parent.mkdir(exist_ok=True)
    with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(ROOT).as_posix())
    with ZipFile(OUTPUT) as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise SystemExit(f"Corrupt package member: {corrupt}")
        print(f"Built {OUTPUT} ({OUTPUT.stat().st_size:,} bytes, {len(archive.namelist())} files)")


if __name__ == "__main__":
    main()
