import json
import os
import sys
import struct
import zlib

from google import genai
from google.genai import types


MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
API_KEY = os.getenv("GEMINI_API_KEY")

SIZES = [int(x) for x in os.getenv("IMAGE_SIZES", "128,512,1024").split(",") if x]
COUNTS = [int(x) for x in os.getenv("IMAGE_COUNTS", "1,4,8").split(",") if x]
STOP_ON_ERROR = os.getenv("STOP_ON_ERROR", "1") == "1"
VERBOSE = os.getenv("SPIKE_VERBOSE", "0") == "1"


def _png_bytes(size: int) -> bytes:
    width, height = size, size
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            r = (x * 255) // max(1, width - 1)
            g = (y * 255) // max(1, height - 1)
            b = 128
            raw.extend([r, g, b, 255])

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


def _response_json(response) -> dict:
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if hasattr(response, "to_dict"):
        return response.to_dict()
    return json.loads(response.model_dump_json()) if hasattr(response, "model_dump_json") else {}


def _extract_text(response):
    if hasattr(response, "text") and response.text:
        return response.text
    return response.candidates[0].content.parts[0].text


def main() -> int:
    if not API_KEY:
        print("Missing GEMINI_API_KEY", file=sys.stderr)
        return 2

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "details"],
        "properties": {
            "summary": {"type": "string"},
            "details": {
                "type": "object",
                "additionalProperties": False,
                "required": ["has_image", "image_count", "image_size"],
                "properties": {
                    "has_image": {"type": "boolean"},
                    "image_count": {"type": "integer"},
                    "image_size": {"type": "integer"},
                },
            },
        },
    }

    client = genai.Client(api_key=API_KEY)
    results = []

    for size in SIZES:
        image_bytes = _png_bytes(size)
        for count in COUNTS:
            request_debug = {
                "model": MODEL,
                "size": size,
                "count": count,
                "bytes_len": len(image_bytes),
                "total_bytes": len(image_bytes) * count,
            }
            if VERBOSE:
                print("request:", json.dumps(request_debug, ensure_ascii=True))

            contents = [
                types.Part.from_text(
                    text=(
                        "Return JSON only. You received images. "
                        "Set details.has_image=true, details.image_count to the number of images, "
                        "details.image_size to the image size in pixels."
                    )
                )
            ]
            for _ in range(count):
                contents.append(
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png")
                )

            try:
                response = client.models.generate_content(
                    model=MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_json_schema=schema,
                    ),
                )
                raw_text = _extract_text(response)
                parsed = json.loads(raw_text)
                response_json = _response_json(response)
                usage = response_json.get("usage_metadata", {}) or {}
                result = {
                    "size": size,
                    "count": count,
                    "bytes_len": len(image_bytes),
                    "total_bytes": len(image_bytes) * count,
                    "ok": True,
                    "prompt_token_count": usage.get("prompt_token_count"),
                    "total_token_count": usage.get("total_token_count"),
                    "parsed": parsed,
                }
            except Exception as exc:
                result = {
                    "size": size,
                    "count": count,
                    "bytes_len": len(image_bytes),
                    "total_bytes": len(image_bytes) * count,
                    "ok": False,
                    "error": repr(exc),
                }
                results.append(result)
                print("result:", json.dumps(result, ensure_ascii=True))
                if STOP_ON_ERROR:
                    return 1
                continue

            results.append(result)
            print("result:", json.dumps(result, ensure_ascii=True))

    print("summary:", json.dumps(results, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
