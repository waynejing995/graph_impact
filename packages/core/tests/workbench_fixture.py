import json
from pathlib import Path


def write_live_fixture(root: Path, symbol: str = "DOORBELL_INTERRUPT_DISABLE") -> tuple[Path, Path]:
    corpus_root = root / "mxgpu"
    source = corpus_root / "libgv/core/hw/AI/mi200/nbio_v7_4.c"
    source.parent.mkdir(parents=True)
    source.write_text(
        "\n".join(
            [
                "static void reset_doorbell(void)",
                "{",
                "    uint32_t data = RREG32(BIF_DOORBELL_INT_CNTL);",
                f"    data = REG_SET_FIELD(data, BIF_DOORBELL_INT_CNTL, {symbol}, 1);",
                "    WREG32(BIF_DOORBELL_INT_CNTL, data);",
                "}",
            ]
        ),
        encoding="utf-8",
    )
    doc = corpus_root / "docs/doorbell.md"
    doc.parent.mkdir()
    doc.write_text(f"The {symbol} field is documented for reset sequencing.", encoding="utf-8")
    pdf = corpus_root / "docs/amd-note.pdf"
    pdf.write_text(
        f"%PDF-1.4\nBT\n(AMD PDF page describes {symbol} page evidence) Tj\nET\n",
        encoding="latin-1",
    )
    config_path = root / "corpus.json"
    config_path.write_text(
        json.dumps(
            {
                "name": "fixture-live",
                "model": {"preferred": "fixture-edge", "fallback": ""},
                "corpora": [
                    {
                        "id": "mxgpu",
                        "repo": "local-fixture",
                        "default_source_root": str(corpus_root),
                        "include": ["**/*.c", "**/*.md", "**/*.pdf"],
                    }
                ],
                "queries": [
                    {
                        "id": "doorbell-disable",
                        "corpus": "mxgpu",
                        "question": "Which field disables doorbell interrupt before reset?",
                        "terms": ["BIF_DOORBELL_INT_CNTL", symbol],
                        "expected_terms": ["BIF_DOORBELL_INT_CNTL", symbol],
                        "max_snippets": 3,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return config_path, corpus_root
