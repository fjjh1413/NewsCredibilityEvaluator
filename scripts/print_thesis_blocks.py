from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    for block in data["blocks"]:
        if not start <= block["index"] < end:
            continue
        print(f'[{block["index"]}] {block["type"]} {block.get("style", "")}')
        if block["type"] == "paragraph":
            print(block.get("text", ""))
        else:
            for row in block["text"]:
                print(" | ".join(row))
        print()


if __name__ == "__main__":
    main()
