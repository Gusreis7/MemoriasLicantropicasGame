import json
from datetime import UTC, datetime
from uuid import uuid4


def event_json(event_type: str, data: dict, source: str = "rules") -> str:
    return json.dumps({"id": str(uuid4()), "type": event_type,
                       "occurred_at": datetime.now(UTC).isoformat(),
                       "source": source, "data": data}, ensure_ascii=False)
