#!/bin/bash
set -u

echo "[mealprepper] Starte Mealprepper auf Port 5050"
python3 -u /app/main.py &
API_PID=$!

TOKEN="$(python3 - <<'PY'
import json
from pathlib import Path

path = Path("/data/options.json")
data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
raw = str(data.get("cloudflare_tunnel_token") or "").strip().strip('"').strip("'")
if "eyJ" in raw:
    raw = raw[raw.find("eyJ") :]
raw = "".join(raw.split())
print(raw)
PY
)"

if [[ -n "${TOKEN}" ]]; then
    echo "[mealprepper] Cloudflare-Token erkannt (${#TOKEN} Zeichen), starte Tunnel"
    export TUNNEL_TOKEN="${TOKEN}"
    (
        while true; do
            cloudflared tunnel --no-autoupdate run
            status=$?
            echo "[mealprepper] Tunnel beendet (Code ${status}), Neustart in 5s"
            sleep 5
        done
    ) &
else
    echo "[mealprepper] Kein Cloudflare-Tunnel-Token — API nur über Ingress erreichbar"
fi

wait "${API_PID}"
