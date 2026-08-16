from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify(status="ok", environment=os.environ.get("ENVIRONMENT", "unknown"))

@app.route("/")
def index():
    return jsonify(message="Azure DevOps multi-environment pipeline demo")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)