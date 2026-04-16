from __future__ import annotations

import base64
import io
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel
from PIL import Image

from util.omniparser import Omniparser

ROOT = Path(__file__).resolve().parent


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _build_config() -> dict[str, Any]:
    weights_dir = Path(os.getenv("OMNIPARSER_WEIGHTS_DIR", str(ROOT / "weights")))
    return {
        "som_model_path": os.getenv(
            "OMNIPARSER_SOM_MODEL_PATH",
            str(weights_dir / "icon_detect" / "model.pt"),
        ),
        "caption_model_name": os.getenv("OMNIPARSER_CAPTION_MODEL_NAME", "florence2"),
        "caption_model_path": os.getenv(
            "OMNIPARSER_CAPTION_MODEL_PATH",
            str(weights_dir / "icon_caption_florence"),
        ),
        "BOX_TRESHOLD": _env_float("OMNIPARSER_BOX_THRESHOLD", 0.05),
        "device": os.getenv("OMNIPARSER_DEVICE", "cpu"),
    }


app = FastAPI(title="OmniParser v2 API")
_startup_error = ""
omniparser = None
try:
    omniparser = Omniparser(_build_config())
except Exception as e:  # pragma: no cover
    _startup_error = str(e)


class ParseRequest(BaseModel):
    base64_image: str


def _decode_image_bytes(image_bytes: bytes) -> tuple[str, tuple[int, int]]:
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return b64, img.size


def _normalize_elements(raw_elements: list[dict[str, Any]], image_size: tuple[int, int]) -> list[dict[str, Any]]:
    w, h = image_size
    out: list[dict[str, Any]] = []
    for obj in raw_elements:
        if not isinstance(obj, dict):
            continue
        bbox = obj.get("bbox")
        if not (isinstance(bbox, (list, tuple)) and len(bbox) >= 4):
            continue
        try:
            x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        except (TypeError, ValueError):
            continue
        if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 1.5:
            x1, x2 = x1 * w, x2 * w
            y1, y2 = y1 * h, y2 * h
        out.append(
            {
                "bbox": [x1, y1, x2, y2],
                "text": str(obj.get("content") or obj.get("text") or ""),
                "interactivity": bool(obj.get("interactivity", True)),
                "type": str(obj.get("type") or ""),
                "source": "omniparser_v2",
            }
        )
    return out


@app.get("/")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "omniparser-v2",
        "ready": bool(omniparser is not None),
        "startup_error": _startup_error or None,
    }


@app.post("/parse")
async def parse(image: UploadFile = File(...)) -> dict[str, Any]:
    if omniparser is None:
        raise HTTPException(status_code=503, detail=f"OmniParser not ready: {_startup_error!r}")
    image_bytes = await image.read()
    image_b64, size = _decode_image_bytes(image_bytes)
    try:
        _som_img_b64, parsed_content_list = omniparser.parse(image_b64)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {e}")
    elements = _normalize_elements(parsed_content_list or [], size)
    return {"elements": elements}


@app.post("/parse_base64")
async def parse_base64(req: ParseRequest) -> dict[str, Any]:
    if omniparser is None:
        raise HTTPException(status_code=503, detail=f"OmniParser not ready: {_startup_error!r}")
    try:
        image_bytes = base64.b64decode(req.base64_image)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64_image")
    _img_b64, size = _decode_image_bytes(image_bytes)
    try:
        _som_img_b64, parsed_content_list = omniparser.parse(req.base64_image)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {e}")
    elements = _normalize_elements(parsed_content_list or [], size)
    return {"elements": elements}
