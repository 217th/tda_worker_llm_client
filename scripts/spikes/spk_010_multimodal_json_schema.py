import json
import os
import sys
import struct
import zlib

from google import genai
from google.genai import types


MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
API_KEY = os.getenv("GEMINI_API_KEY")
VERBOSE = os.getenv("SPIKE_VERBOSE", "0") == "1"


def _extract_text(response):
    if hasattr(response, "text") and response.text:
        return response.text
    try:
        return response.candidates[0].content.parts[0].text
    except Exception as exc:  # pragma: no cover - defensive for spike
        raise RuntimeError("Unable to extract text from response") from exc


def _response_json(response) -> str:
    if hasattr(response, "model_dump_json"):
        return response.model_dump_json(indent=2)
    if hasattr(response, "to_json"):
        return response.to_json()
    try:
        return json.dumps(response, default=str, indent=2)
    except Exception:
        return repr(response)


def _png_bytes() -> bytes:
    width, height = 2, 2
    pixels = [
        (255, 0, 0, 255),
        (0, 255, 0, 255),
        (0, 0, 255, 255),
        (255, 255, 255, 255),
    ]

    raw = bytearray()
    for y in range(height):
        raw.append(0)  # no filter
        for x in range(width):
            r, g, b, a = pixels[y * width + x]
            raw.extend([r, g, b, a])

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return (
            struct.pack("!I", len(data))
            + tag
            + data
            + struct.pack("!I", crc)
        )

    ihdr = struct.pack("!IIBBBBB", width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(
        b"IEND", b""
    )


def main() -> int:
    if not API_KEY:
        print("Missing GEMINI_API_KEY", file=sys.stderr)
        return 2

    image_bytes = _png_bytes()

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "details"],
        "properties": {
            "summary": {"type": "string"},
            "details": {
                "type": "object",
                "additionalProperties": False,
                "required": ["has_image", "model"],
                "properties": {
                    "has_image": {"type": "boolean"},
                    "model": {"type": "string"},
                },
            },
        },
    }

    request_debug = {
        "model": MODEL,
        "text": (
            "Return JSON only. You received a tiny image. "
            "Set details.has_image=true and echo the model name in details.model."
        ),
        "image": {"mime_type": "image/png", "bytes_len": len(image_bytes)},
        "schema": schema,
        "config": {"response_mime_type": "application/json", "response_json_schema": True},
    }

    if VERBOSE:
        print("request:", json.dumps(request_debug, ensure_ascii=True))

    client = genai.Client(api_key=API_KEY)
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_text(
                text=request_debug["text"]
            ),
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=schema,
        ),
    )

    if VERBOSE:
        print("response_raw:", _response_json(response))

    raw_text = _extract_text(response)
    data = json.loads(raw_text)

    print("model:", MODEL)
    print("json_valid: true")
    print("json_payload:", json.dumps(data, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
