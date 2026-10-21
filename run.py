"""Entry point: `python run.py` (dev) or `python run.py --prod` (waitress)."""
import sys

from app import create_app

app = create_app()

if __name__ == "__main__":
    if "--prod" in sys.argv:
        from waitress import serve

        app.logger.info("serving via waitress on 127.0.0.1:8000")
        serve(app, host="127.0.0.1", port=8000)
    else:
        app.run(debug=True, host="127.0.0.1", port=5000, use_reloader=False)
