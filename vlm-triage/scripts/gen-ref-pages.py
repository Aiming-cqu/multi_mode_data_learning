#!/usr/bin/env -S pixi run -e mkdocs -- python

import os
import mkdocs_gen_files

from itertools import chain
from pathlib import Path


nav = mkdocs_gen_files.Nav()

root = Path(os.environ["PROJECT_ROOT"])
dirs = ["apps", "lib", "models", "scripts", "tests"]

for path in chain(*(sorted((root / d).rglob("*.py")) for d in dirs)):
    # if path.stem == 'test': continue

    module_path = path.relative_to(root).with_suffix("")
    doc_path = path.relative_to(root).with_suffix(".md")
    full_doc_path = Path("reference", doc_path)

    parts = tuple(module_path.parts)

    if parts[-1] == "__init__":
        # Skip empty __init__.py files to avoid duplicate symbol references
        if not path.read_text().strip():
            continue
        parts = parts[:-1]
        doc_path = doc_path.with_name("index.md")
        full_doc_path = full_doc_path.with_name("index.md")
    elif parts[-1] == "__main__":
        continue

    nav[parts] = doc_path.as_posix()

    with mkdocs_gen_files.open(full_doc_path, "w") as f:
        ident = ".".join(parts)
        f.write(f"::: {ident}")

    mkdocs_gen_files.set_edit_path(full_doc_path, path.relative_to(root))

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as f:
    f.writelines(nav.build_literate_nav())
