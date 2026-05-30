import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify
from filters import sharia_list

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/check", methods=["POST"])
def check():
    ticker = request.json.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"error": "أدخل رمز السهم"})
    result = sharia_list.check(ticker)
    return jsonify({
        "ticker":     ticker,
        "decision":   result["decision"],
        "halal":      result["decision"] == "BUY_ALLOWED",
        "reason":     result["reason"],
        "purification": result["purification"],
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
