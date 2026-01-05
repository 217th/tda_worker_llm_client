# Инструкция: подготовка и выгрузка `llm_schemas/{schemaId}` (LLM_REPORT_OUTPUT)

Цель: агент получает от пользователя **только `jsonSchema`** (JSON Schema для model‑owned `output`) и выполняет шаги:
1) провалидировать JSON,
2) провалидировать глубину вложенности **данных** (порог по умолчанию = **5**; менять порог можно только по явному согласию пользователя),
3) обернуть `jsonSchema` в служебные поля (`createdAt`, `description`, `isActive`, `kind`, `schemaId`, `sha256`),
4) посчитать `sha256` и записать в документ,
5) выгрузить документ в Firestore коллекцию `llm_schemas`.

> Примечание: “глубина вложенности” здесь — **вложенность данных**, описываемых схемой (структура результата), а не “глубина дерева JSON Schema как JSON”.

---

## Вход от пользователя (минимум)

Пользователь должен предоставить агенту:
- `schemaId`: строка вида `llm_schema_<timeframe>_<type>[_<suffix>]_v<major>_<minor>`
  (например `llm_schema_1M_report_v5_0`)
- `description`: строка (коротко, зачем схема)
- `jsonSchema`: JSON‑объект (корень — object)

---

## Важные правила (обязательные)

1) **Запрет на изменение структуры `jsonSchema` без согласия пользователя.**  
   Если схема не проходит проверки (например, по глубине), агент **не имеет права** самовольно “уплощать/переписывать/удалять поля” и затем выгружать изменённый вариант.

2) **Если схема не проходит проверку по глубине (Шаг 3)**, агент должен:
   - явно сообщить рассчитанную глубину и требуемый максимум;
   - предложить 2–3 конкретных варианта снижения глубины (например: заменить `array of object` → `array of string`, вынести вложенные объекты в строковые поля, убрать глубоко вложенные блоки);
   - **остановиться и дождаться согласия пользователя** на выбранный вариант перед генерацией/выгрузкой.

---

## Шаг 1 — провалидировать JSON (парсинг + тип корня)

Сохранить `jsonSchema` в файл, например: `input_json_schema.json`.

Проверка:
```bash
python3 - <<'PY'
import json
from pathlib import Path

p = Path("input_json_schema.json")
obj = json.loads(p.read_text("utf-8"))
if not isinstance(obj, dict):
    raise SystemExit("FAIL: jsonSchema must be a JSON object")
print("OK: valid JSON object")
PY
```

---

## Шаг 2 — провалидировать минимальные инварианты LLM_REPORT_OUTPUT

Воркера интересует, чтобы схема соответствовала MVP‑инвариантам (см. `worker_llm_client/app/services.py::_validate_llm_report_schema`):
- `jsonSchema.required` — массив строк и содержит `summary` и `details`
- `jsonSchema.properties.summary.required` содержит `markdown`
- `jsonSchema.properties.summary.properties.markdown.type == "string"`

Проверка:
```bash
python3 - <<'PY'
import json
from pathlib import Path

js = json.loads(Path("input_json_schema.json").read_text("utf-8"))

def fail(msg): raise SystemExit(f"FAIL: {msg}")

req = js.get("required")
if not isinstance(req, list) or not all(isinstance(x, str) for x in req):
    fail("jsonSchema.required must be an array of strings")
if "summary" not in req or "details" not in req:
    fail("jsonSchema must require summary and details")

props = js.get("properties")
if not isinstance(props, dict):
    fail("jsonSchema.properties must be an object")
summary = props.get("summary")
if not isinstance(summary, dict):
    fail("jsonSchema.properties.summary must be an object")

sreq = summary.get("required")
if not isinstance(sreq, list) or "markdown" not in sreq:
    fail("jsonSchema.properties.summary.required must include markdown")

sprops = summary.get("properties")
if not isinstance(sprops, dict):
    fail("jsonSchema.properties.summary.properties must be an object")

md = sprops.get("markdown")
if not isinstance(md, dict):
    fail("jsonSchema.properties.summary.properties.markdown must be an object")
if md.get("type") != "string":
    fail("jsonSchema.summary.markdown must be a string type")

print("OK: schema invariants pass")
PY
```

---

## Шаг 3 — провалидировать глубину вложенности данных (порог по умолчанию: 5)

Это метрика “глубины результата”, описываемого схемой:
- root object = depth 1
- `type: object` → переход в `properties` даёт `+1`
- `type: array` → переход в `items` даёт `+1`
- `anyOf`/`oneOf`/`allOf` не добавляют глубину, берётся максимум по веткам

Порог по умолчанию: **5** (эмпирически схема с `max_data_depth=5` была принята моделью без ошибок).

Важно:
- это **не гарантированный лимит** провайдера, а рабочая настройка процесса;
- если пользователь просит “строгий режим”, агент может понизить порог (например до 4) — но только по явному запросу;
- если пользователь просит “разрешить глубже”, агент может поднять порог/или продолжить выгрузку при превышении — но только по явному согласию (и с предупреждением о рисках 400).

Проверка:
```bash
python3 - <<'PY'
import json
from pathlib import Path

s = json.loads(Path("input_json_schema.json").read_text("utf-8"))

def max_data_depth(schema, depth=1):
    if not isinstance(schema, dict):
        return depth
    if "anyOf" in schema and isinstance(schema["anyOf"], list):
        return max(max_data_depth(sub, depth) for sub in schema["anyOf"])
    t = schema.get("type")
    if isinstance(t, list):
        t2 = [x for x in t if x != "null"]
        t = t2[0] if t2 else t[0]
    if t == "object":
        props = schema.get("properties", {})
        if not props:
            return depth
        return max(max_data_depth(v, depth+1) for v in props.values())
    if t == "array":
        items = schema.get("items")
        if items is None:
            return depth
        return max_data_depth(items, depth+1)
    return depth

d = max_data_depth(s)
print("max_data_depth =", d)

MAX_SUPPORTED = 5
if d > MAX_SUPPORTED:
    raise SystemExit(f"FAIL: max_data_depth {d} exceeds supported {MAX_SUPPORTED}")
print("OK: depth within supported limit")
PY
```

---

## Шаг 4 — собрать llm_schema документ и посчитать sha256

Требуемая обёртка (см. `docs/contracts/llm_schema.schema.json`):
- `schemaId` (Firestore doc id):
  `^llm_schema_[1-9][0-9]*[A-Za-z]+_(report|reco)(?:_[a-z0-9]{1,24})?_v[1-9][0-9]*_(?:0|[1-9][0-9]*)$`
- `kind`: `"LLM_REPORT_OUTPUT"`
- `createdAt`: RFC3339 (UTC)
- `description`: строка
- `jsonSchema`: ваш объект
- `sha256`: sha256 hex от canonical JSON encoding `jsonSchema`
- `isActive`: `true`

Canonical JSON для sha256:
```python
json.dumps(jsonSchema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
```

Генерация файла (пример: `llm_schema.upload.json`):
```bash
SCHEMA_ID="llm_schema_1M_report_v5_0" \
DESCRIPTION="Short human description" \
python3 - <<'PY'
import json, os, hashlib
from datetime import datetime, timezone
from pathlib import Path

json_schema = json.loads(Path("input_json_schema.json").read_text("utf-8"))

canonical = json.dumps(json_schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

doc = {
  "schemaId": os.environ["SCHEMA_ID"],
  "kind": "LLM_REPORT_OUTPUT",
  "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
  "description": os.environ.get("DESCRIPTION",""),
  "jsonSchema": json_schema,
  "sha256": sha256,
  "isActive": True,
}

out = Path("llm_schema.upload.json")
out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
print("Wrote", out)
print("sha256", sha256)
PY
```

---

## Шаг 5 — выгрузить документ в Firestore (`llm_schemas/{schemaId}`)

Вариант через Firestore REST API (как делалось в проекте ранее).

Требуется:
- переменные окружения `PROJECT_ID`, `FIRESTORE_DB` (обычно через `.env.prod.local`)
- доступ `gcloud auth print-access-token`

Загрузка:
```bash
source .env.prod.local
SCHEMA_ID="llm_schema_1M_report_v5_0"

TMPDIR="$(mktemp -d)"
OUT_PATH="${TMPDIR}/firestore_payload.json"

python3 - <<'PY'
import json, os
from pathlib import Path

doc = json.loads(Path("llm_schema.upload.json").read_text("utf-8"))

def to_fs(v):
    if v is None: return {"nullValue": None}
    if isinstance(v, bool): return {"booleanValue": v}
    if isinstance(v, int) and not isinstance(v, bool): return {"integerValue": str(v)}
    if isinstance(v, float): return {"doubleValue": v}
    if isinstance(v, str): return {"stringValue": v}
    if isinstance(v, list): return {"arrayValue": {"values": [to_fs(x) for x in v]}}
    if isinstance(v, dict): return {"mapValue": {"fields": {k: to_fs(x) for k, x in v.items()}}}
    return {"stringValue": str(v)}

fields = {
  "schemaId": to_fs(doc["schemaId"]),
  "kind": to_fs(doc["kind"]),
  "createdAt": {"timestampValue": doc["createdAt"]},
  "description": to_fs(doc.get("description","")),
  "jsonSchema": to_fs(doc["jsonSchema"]),
  "sha256": to_fs(doc["sha256"]),
  "isActive": to_fs(bool(doc.get("isActive", True))),
}

Path(os.environ["OUT_PATH"]).write_text(json.dumps({"fields": fields}), encoding="utf-8")
PY

ACCESS_TOKEN="$(gcloud auth print-access-token)"
FIRESTORE_BASE="https://firestore.googleapis.com/v1/projects/${PROJECT_ID}/databases/${FIRESTORE_DB}/documents"

curl -s -X PATCH \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  "${FIRESTORE_BASE}/llm_schemas/${SCHEMA_ID}" \
  --data-binary "@${OUT_PATH}"

rm -rf "${TMPDIR}"
echo "Uploaded ${SCHEMA_ID}"
```

Рекомендованная пост‑проверка:
- `GET` документа `llm_schemas/${schemaId}` и сверка `sha256`/`kind`/наличия `jsonSchema`.

---

## Примечания по безопасности

- Никогда не логировать и не коммитить секреты/токены.
- Не включать в схему или описание конфиденциальные данные.
- Для экспериментов предпочтительно создавать новые `schemaId` (v<major>_<minor>), а перезапись существующих делать только по явной команде пользователя.
