"""Local dev entrypoint:  python run.py  (then open http://127.0.0.1:5000)."""
from mlbboard import create_app

app = create_app()

if __name__ == "__main__":
    # Bind to 0.0.0.0 if you run this in a container.
    app.run(host="127.0.0.1", port=5000, debug=True)
