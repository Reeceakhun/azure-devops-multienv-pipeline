from flask import Flask, jsonify
import os
from applicationinsights import TelemetryClient

app = Flask(__name__)

ai_key = os.environ.get("APPINSIGHTS_KEY")
tc = TelemetryClient(ai_key) if ai_key else None

@app.route("/health")
def health():
    if tc:
        tc.track_event("HealthCheckHit")
        tc.flush()
    return jsonify(status="ok", environment=os.environ.get("ENVIRONMENT", "unknown"))

@app.route("/")
def index():
    if tc:
        tc.track_event("IndexHit")
        tc.flush()
    return jsonify(message="Azure DevOps multi-environment pipeline demo")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)