from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz


def main() -> None:
    pdf_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = fitz.open(pdf_path)
    pages = []
    chapter2_candidates = []
    chapter3_candidates = []
    for index, page in enumerate(pdf):
        text = page.get_text("text")
        compact = "".join(text.split())
        if "第2章系统需求分析" in compact:
            chapter2_candidates.append(index)
        if "第3章系统开发环境与关键技术" in compact:
            chapter3_candidates.append(index)
        pages.append(
            {
                "index": index,
                "text_chars": len(compact),
                "image_count": len(page.get_images(full=True)),
                "first_text": " ".join(text.split())[:120],
            }
        )
    chapter2_page = chapter2_candidates[-1] if chapter2_candidates else None
    chapter3_page = chapter3_candidates[-1] if chapter3_candidates else None
    if chapter2_page is None or chapter3_page is None or chapter2_page >= chapter3_page:
        raise RuntimeError(
            f"Cannot locate chapters: ch2={chapter2_candidates}, ch3={chapter3_candidates}"
        )
    rendered = []
    matrix = fitz.Matrix(1.5, 1.5)
    for index in range(chapter2_page, chapter3_page + 1):
        output = out_dir / f"page-{index + 1:02d}.png"
        pdf[index].get_pixmap(matrix=matrix, alpha=False).save(output)
        rendered.append(str(output))
    chapter_pages = pages[chapter2_page:chapter3_page]
    report = {
        "pdf": str(pdf_path),
        "page_count": len(pdf),
        "chapter2_page": chapter2_page + 1,
        "chapter3_page": chapter3_page + 1,
        "chapter2_page_count": chapter3_page - chapter2_page,
        "chapter2_pages": chapter_pages,
        "blank_like_pages": [p["index"] + 1 for p in chapter_pages if p["text_chars"] < 20],
        "rendered": rendered,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
