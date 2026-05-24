import base64
import time

import fitz  # PyMuPDF
import httpx
import structlog

from shared import s3
from shared.config import settings
from shared.observability import figure_describe_latency

log = structlog.get_logger()


def extract_and_describe_figure(pdf_path: str, fig: dict, doi_slug: str) -> dict:
    coords = fig.get("coords", {})

    # Step 1: Crop figure region from the PDF page
    doc = fitz.open(pdf_path)
    page_num = coords.get("page", 1) - 1  # 0-indexed
    if page_num < 0 or page_num >= len(doc):
        page_num = 0
    page = doc[page_num]

    x, y, w, h = (
        coords.get("x", 0.0),
        coords.get("y", 0.0),
        coords.get("w", 100.0),
        coords.get("h", 100.0),
    )
    clip = fitz.Rect(x, y, x + w, y + h)
    pix = page.get_pixmap(clip=clip, dpi=150)
    img_bytes = pix.tobytes("png")
    doc.close()

    # Step 2: Upload PNG to S3
    fig_id = fig.get("fig_id", "fig_unknown")
    s3_key = f"parsed/{doi_slug}/figures/{fig_id}.png"
    s3.upload(img_bytes, key=s3_key, content_type="image/png")

    # Step 3: LLM description via OpenRouter
    t0 = time.perf_counter()
    description = _describe_figure(img_bytes, fig.get("caption", ""))
    figure_describe_latency.observe(time.perf_counter() - t0)

    # Step 4: Upload description text to S3
    desc_key = s3_key.replace(".png", "_desc.txt")
    s3.upload(description.encode(), key=desc_key, content_type="text/plain")

    log.info("figure_extracted", fig_id=fig_id, doi_slug=doi_slug)
    return {**fig, "s3_img_key": s3_key, "description": description}


def _describe_figure(img_bytes: bytes, caption: str) -> str:
    b64 = base64.b64encode(img_bytes).decode()
    resp = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
        json={
            "model": "openai/gpt-4o",
            "max_tokens": 400,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                        {
                            "type": "text",
                            "text": (
                                "This figure is from a medical research paper. "
                                f'Caption: "{caption}". '
                                "Describe what this figure shows in 2-4 sentences, "
                                "focusing on data, trends, and clinical significance."
                            ),
                        },
                    ],
                }
            ],
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    return str(resp.json()["choices"][0]["message"]["content"])
