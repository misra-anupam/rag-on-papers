from shared.models import Chunk


def inject_header(chunk: Chunk, paper: dict) -> str:
    lines = [
        f"Paper: {paper.get('title', '')}",
        f"Journal: {paper.get('journal', '')}  |  Date: {paper.get('pub_date', '')}",
        f"Section: {chunk.section_heading}",
        "---",
        chunk.text,
    ]
    return "\n".join(lines)
