"""Smoke tests for the service-free remove-ai-marks-standalone skill."""

from __future__ import annotations

import json
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "remove-ai-marks-standalone"
VENDORED = (
    "av_meta.py",
    "clean_file.py",
    "clean_text.py",
    "common.py",
    "container_meta.py",
    "format_dispatch.py",
    "image_meta.py",
    "inspect_file.py",
    "inspect_text.py",
    "score_stylometry.py",
    "text_unicode.py",
)


def test_vendored_scripts_are_identical_to_service():
    # The standalone skill vendors the service's file pipeline byte-for-byte.
    # Any change to one side must be applied to both copies in the same commit.
    for name in VENDORED:
        service = (ROOT / "service" / "scripts" / name).read_bytes()
        vendored = (SKILL / "scripts" / name).read_bytes()
        assert service == vendored, name


def test_vendored_scripts_are_self_contained():
    # Every local import must resolve inside the skill, or the uploaded bundle
    # fails at runtime with no service checkout next to it.
    local = {path.stem for path in (ROOT / "service" / "scripts").glob("*.py")}
    vendored = {path.stem for path in (SKILL / "scripts").glob("*.py")}
    for path in (SKILL / "scripts").glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            words = line.split()
            if len(words) >= 2 and words[0] in ("import", "from"):
                module = words[1].split(".")[0].rstrip(",")
                if module in local:
                    assert module in vendored, f"{path.name} imports {module}"


def _png_with_ai_text() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"tEXt", b"Software\x00DALL-E 3 via OpenAI")
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + chunk(b"IEND", b"")
    )


def test_standalone_cleans_image_metadata_outside_the_repo(tmp_path):
    source = tmp_path / "shot.png"
    source.write_bytes(_png_with_ai_text())
    output = tmp_path / "shot.cleaned.png"

    result = subprocess.run(
        [
            sys.executable,
            str(SKILL / "scripts" / "clean_file.py"),
            str(source),
            "-o",
            str(output),
            "--json",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )

    report = json.loads(result.stdout)
    assert report["changed"] is True
    assert report["still_has_ai_metadata"] is False
    assert b"DALL-E" not in output.read_bytes()


def test_standalone_cleans_invisible_unicode(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("Hello​ world⁠.\n", encoding="utf-8")
    output = tmp_path / "notes.cleaned.md"

    subprocess.run(
        [sys.executable, str(SKILL / "scripts" / "clean_file.py"), str(source), "-o", str(output)],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    assert output.read_text(encoding="utf-8") == "Hello world.\n"
