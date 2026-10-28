from flask import Flask, jsonify, render_template

import db
from routes.train import bp as train_bp
from routes.bus import bp as bus_bp

app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static",
)
app.json.ensure_ascii = False   # show Chinese characters as-is in JSON
app.register_blueprint(train_bp)
app.register_blueprint(bus_bp)


@app.get("/api/health")
def health():
    row = db.query("SELECT DATABASE() AS db, VERSION() AS version", one=True)
    return jsonify({"status": "ok", **row})


@app.get("/")
def api_tester():
    return render_template("api_tester.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)