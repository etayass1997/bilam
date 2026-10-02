"""Build a self-contained Bilam plugin from the canonical source corpus.

The generated corpus is split across small skill bundles so the complete
source text can travel with the plugin, without a remote MCP dependency.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import re
import shutil
import zipfile
from contextlib import ExitStack
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "backend" / "kb" / "kb_data.json.gz"
PLUGIN = ROOT / "plugins" / "bilam-standalone"
DIST = ROOT / "dist" / "bilam-standalone.zip"
SHARD_COUNT = 12
TOKEN_RE = re.compile(r"[\w\u0590-\u05ff]+", re.UNICODE)


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def package():
    DIST.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(DIST, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in PLUGIN.rglob("*"):
            if (path.is_file() and path.name != "mcp.json" and path.suffix != ".pyc"
                    and "__pycache__" not in path.parts):
                archive.write(path, path.relative_to(PLUGIN).as_posix())
    return DIST.stat().st_size


def main(package_only=False):
    if package_only:
        print(compact_json({"zip": str(DIST), "zip_bytes": package()}))
        return
    with gzip.open(SOURCE, "rt", encoding="utf-8") as handle:
        docs = json.load(handle)

    parashot = sorted({doc["metadata"]["parasha"] for doc in docs})
    commentators = sorted({doc["metadata"]["commentator_name"] for doc in docs if doc["metadata"].get("commentator_name")})
    parasha_ids = {name: i for i, name in enumerate(parashot)}
    commentator_ids = {name: i for i, name in enumerate(commentators)}

    # Assign complete portions to balanced shards, retaining the original
    # document ordinal for the same stable BM25 tie break as the server.
    weights = collections.Counter()
    for doc in docs:
        weights[doc["metadata"]["parasha"]] += len(doc["text"].encode("utf-8"))
    shard_weights = [0] * SHARD_COUNT
    shard_for = {}
    for name in sorted(parashot, key=lambda p: weights[p], reverse=True):
        shard = min(range(SHARD_COUNT), key=lambda i: shard_weights[i])
        shard_for[name] = shard
        shard_weights[shard] += weights[name]

    skill_root = PLUGIN / "skills"
    for directory in skill_root.glob("bilam-corpus-*"):
        shutil.rmtree(directory)
    study_assets = skill_root / "bilam-study" / "assets"
    study_assets.mkdir(parents=True, exist_ok=True)

    shard_files = []
    for i in range(SHARD_COUNT):
        skill = skill_root / f"bilam-corpus-{i + 1:02d}"
        assets = skill / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: bilam-corpus-{i + 1:02d}\n"
            f"description: Internal Bilam Torah commentary corpus shard {i + 1:02d}; use through the bilam-study skill.\n"
            "---\n\nThis shard is data for the bilam-study script. Do not quote it without running the script.\n",
            encoding="utf-8",
        )
        shard_files.append(assets / "commentaries.jsonl.gz")

    df = collections.Counter()
    total_terms = 0
    verse_count = 0
    commentary_count = 0
    # gzip files are independently compressed; ZIP stores their bytes rather
    # than wasting time trying to compress the same data a second time.
    with ExitStack() as stack:
        verses = stack.enter_context(gzip.open(study_assets / "verses.jsonl.gz", "wt", encoding="utf-8", compresslevel=9))
        shards = [stack.enter_context(gzip.open(path, "wt", encoding="utf-8", compresslevel=9)) for path in shard_files]
        for ordinal, doc in enumerate(docs):
            meta = doc["metadata"]
            tokens = TOKEN_RE.findall(doc["text"].lower())
            df.update(set(tokens))
            total_terms += len(tokens)
            commentator = meta.get("commentator_name")
            row = [
                ordinal,
                parasha_ids[meta["parasha"]],
                meta.get("chapter"),
                meta.get("verse"),
                commentator_ids[commentator] if commentator else -1,
                doc["text"],
                meta.get("source_url"),
                meta.get("ref_he"),
                len(tokens),
            ]
            if meta.get("source_type") == "torah":
                verses.write(compact_json(row) + "\n")
                verse_count += 1
            else:
                shards[shard_for[meta["parasha"]]].write(compact_json(row) + "\n")
                commentary_count += 1

    # rank_bm25 replaces negative IDF values with epsilon times the mean IDF.
    n = len(docs)
    raw_idfs = [math.log(n - frequency + 0.5) - math.log(frequency + 0.5) for frequency in df.values()]
    mean_idf = sum(raw_idfs) / len(raw_idfs)
    catalog = {
        "format": 1,
        "parashot": parashot,
        "commentators": commentators,
        "shards": {name: shard_for[name] + 1 for name in parashot},
        "documents": n,
        "torah_verses": verse_count,
        "commentaries": commentary_count,
        "average_document_length": total_terms / n,
        "epsilon_idf": 0.25 * mean_idf,
    }
    (study_assets / "catalog.json").write_text(compact_json(catalog), encoding="utf-8")
    with gzip.open(study_assets / "document_frequency.json.gz", "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(df, handle, ensure_ascii=False, separators=(",", ":"))

    print(compact_json({
        "plugin": str(PLUGIN),
        "zip": str(DIST),
        "zip_bytes": package(),
        "shards": [path.stat().st_size for path in shard_files],
        "documents": n,
        "torah_verses": verse_count,
        "commentaries": commentary_count,
    }))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-only", action="store_true", help="Repack existing generated corpus without recompressing it")
    main(parser.parse_args().package_only)
