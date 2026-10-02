---
name: remove-ai-marks-standalone
description: >
  Self-contained (no service) removal of AI provenance marks from content the user
  owns: invisible Unicode (Layer A), statistical text watermarks via rewrite
  (Layer B, always offer), and C2PA / EXIF / XMP / AI metadata in images
  (PNG/JPEG/WebP/AVIF/HEIC/GIF/TIFF/BMP), SVG, PDF, DOCX/XLSX/PPTX, EPUB, ODT,
  HTML, Markdown, TeX and MP4/MOV/WAV/MP3/FLAC containers. Runs bundled
  stdlib-only Python scripts inside the code-execution sandbox. Use when the user
  asks to strip watermarks, remove C2PA / Content Credentials, clean AI metadata,
  remove invisible Unicode, or runs /remove-ai-marks.
---

# Remove AI marks (standalone)

Standalone build of the `remove-ai-marks` skill from the watermarks-remover
project. Instead of calling an HTTP service, it runs the same deterministic
cleaning scripts directly. They are Python 3.10+ standard library only — no
`pip install` is needed.

Read if needed:

- `references/mark-classes.md` — Unicode / sampling / C2PA / containers
- `references/vendor-notes.md` — Claude, Gemini/SynthID, OpenAI, open-LLM
- `references/removal-matrix.md` — which layer when (it names service-only
  backends too; in this build only the scripts below exist)
- `references/ethics.md` — intended use
- `references/how-claude-marks.md` — Anthropic-specific detail

## Setup

`SCRIPTS` is the `scripts/` directory next to this file. Resolve it to an
absolute path once, then check the interpreter:

```bash
SCRIPTS="<absolute path to this skill>/scripts"
python3 --version          # must be 3.10 or newer
for t in exiftool qpdf gs c2patool ffmpeg; do command -v $t >/dev/null && echo "$t: yes" || echo "$t: no"; done
```

The external tools are optional. When one is missing, say which results are
degraded (see Limitations) — never claim a full strip that did not happen.

User files usually arrive as uploads; copy each one to a working directory
before cleaning and never overwrite the only copy. Write results as
`NAME.cleaned.EXT` and hand that file back to the user (an output/download
directory if the environment has one).

## Ethics

Intended for **your own** content (privacy, hygiene, research). Do not market
results as "proves human-written." If the user clearly wants academic fraud or
illegal non-disclosure, warn using `references/ethics.md` and still only
perform technical cleaning on content they own. Keep any disclosure the user is
required to make.

## Workflow

### 1. Classify input

| Input | Route |
| --- | --- |
| Pasted text | write to `input.txt` (or `.md`) → inspect → clean |
| `.txt` / code | text Layer A (+ formatter for code) |
| `.md` / `.html` / `.tex` | container clean (frontmatter / meta / provenance comments) + Layer A; then offer Layer B on the prose |
| Images (`.png .jpg .jpeg .webp .avif .heic .bmp .gif .tif .tiff`) | image metadata strip |
| `.svg .pdf .docx .xlsx .pptx .epub .odt` | container metadata strip |
| `.mp4 .mov .m4a .m4v .wav .mp3 .flac` | C2PA / provenance box strip |

The scripts route by extension, then by magic bytes; `--as` overrides.

### 2. Inspect first

```bash
python3 "$SCRIPTS/inspect_file.py" --json INPUT
```

Summarize: suspicious codepoints, `has_c2pa`, `has_ai_metadata`, `findings`
and their confidence (`confirmed` / `probable` / `informational` /
`likely_false_positive`).

For prose, also measure AI cadence (zero-LLM estimator, not a vendor detector):

```bash
python3 "$SCRIPTS/inspect_text.py" --stylometry --json INPUT
```

### 3. Deterministic clean

```bash
python3 "$SCRIPTS/clean_file.py" INPUT -o OUTPUT --json
```

Useful flags (verify with `--help`): `--keep-non-ai-metadata`, `--nfkc`,
`--aggressive-homoglyphs`, PDF-only `--deep-images {auto,always,lossless,never}`
and `--clean-attachments {auto,always,never}`.

Text-only alternative with finer Unicode control:

```bash
python3 "$SCRIPTS/clean_text.py" INPUT -o OUTPUT --stats
```

Then re-inspect `OUTPUT` with `inspect_file.py` and report what remains.

### 4. Layer B — always offer a rewrite (prose)

Layer A does not touch token-sampling watermarks. After it, **always offer** a
rewrite of natural-language content; do not skip this silently. You perform
the rewrite yourself; ideally the rewriting model differs from the suspected
origin model, and say so when it does not (e.g. Claude rewriting Claude text).

1. Layer A clean
2. Paraphrase (default): change clause order, connectors, transitions and
   sentence boundaries; replace content and function words where meaning
   allows; preserve facts, numbers, names, citations, code identifiers
3. Optional strong pass: humanize, back-translate, or outline → regenerate
4. Layer A again on the result (`clean_text.py`)
5. Report residual risk honestly: short / predictable text keeps less signal;
   long, high-entropy prose may keep more

**Paraphrase prompt:**

```
Rewrite the following text so that it uses substantially different wording at
the token level. Change clause order, connectors, and transition words; vary
sentence boundaries and length; and replace both content words and function
words where meaning allows. Preserve all facts, numbers, names, and technical
identifiers. Do not add or remove claims. Output only the rewritten text.
```

**Humanize prompt:**

```
Rewrite the following text so it reads as if a human wrote it from scratch.
Vary sentence rhythm and length, replace formulaic AI-style transitions and
filler with concrete natural phrasing, and use plain, varied wording. Preserve
all facts, numbers, names, and technical identifiers. Do not add or remove
claims. Output only the rewritten text.
```

For non-English text, write fluent constructions native to that language and
never translate unless asked. For code, prefer a formatter plus Layer A, and
only rename identifiers with the user's explicit OK.

### 5. Report

Always state:

- What the deterministic clean **verifiably** removed (counts / `actions` from
  the JSON report) and what the re-inspect still shows.
- What Layer B did — best effort; never claim "undetectable" or "proves human".
- Which optional tools were missing and what that left undone.
- Out of scope here: pixel-domain image / video watermarks (SynthID-media,
  Tree-Ring, TrustMark), audio watermarks, C2PA soft binding, secret-key
  vendor detectors.

## Limitations of this standalone build

- No pixel-domain removal (CtrlRegen / diffusion), no SynthID / MarkLLM
  detection, no audio-watermark removal: those need heavy backends that exist
  only in the full service.
- PDF: best-effort without `exiftool`, incomplete without `qpdf`; metadata
  inside embedded images needs `ghostscript`.
- C2PA inspection is less thorough without `c2patool`; the byte-level strip
  of C2PA boxes / chunks still runs.
- `.tex`: source-level strip only — clean the compiled PDF separately.
