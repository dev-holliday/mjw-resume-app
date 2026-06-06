"""
Wedding RSVP Backend — Flask app for Azure App Service
-------------------------------------------------------
Handles:
  GET  /          → serves the wedding invitation page
  POST /rsvp      → accepts JSON RSVP, checks for duplicates,
                    writes to rsvp_list.txt, updates count
  GET  /thanks    → serves the confirmation page (redirect target)
  GET  /admin     → simple password-protected guest list view
"""

import os
import json
import sys
from datetime import datetime

# fcntl is Unix-only; skip locking gracefully on Windows (local dev)
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, abort

app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
# Set SECRET_KEY as an environment variable in Azure App Service settings
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")

# Admin password — set ADMIN_PASSWORD env var in Azure
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "wedding2026")

# Data directory: use Azure persistent storage or local fallback
# In Azure App Service, /home is the persistent mount point
DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

RSVP_FILE  = DATA_DIR / "rsvp_list.txt"
COUNT_FILE = DATA_DIR / "rsvp_count.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize_name(first: str, last: str) -> str:
    """Return a lowercased 'first last' key for duplicate checking."""
    return f"{first.strip().lower()} {last.strip().lower()}"


def load_count() -> dict:
    """Load the count JSON, initializing if missing."""
    if COUNT_FILE.exists():
        try:
            return json.loads(COUNT_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"total_guests": 0, "total_rsvps": 0}


def save_count(data: dict) -> None:
    """Atomically write count JSON."""
    COUNT_FILE.write_text(json.dumps(data, indent=2))


def get_all_names() -> set:
    """Return a set of normalized 'first last' strings from the RSVP file."""
    names = set()
    if not RSVP_FILE.exists():
        return names
    for line in RSVP_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("NAME:"):
            # Format: NAME: First Last
            parts = line[5:].strip().split(" ", 1)
            if len(parts) == 2:
                names.add(normalize_name(parts[0], parts[1]))
    return names


def append_rsvp(data: dict) -> None:
    """Append a new RSVP entry to the text file with a file lock (Unix) or plain write (Windows)."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"\n{'─' * 48}\n"
        f"NAME:        {data['first_name']} {data['last_name']}\n"
        f"EMAIL:       {data.get('email') or '—'}\n"
        f"GUEST COUNT: {data.get('guest_count', 1)}\n"
        f"GUESTS:      {data.get('guest_names') or '—'}\n"
        f"SUBMITTED:   {timestamp}\n"
    )
    with open(RSVP_FILE, "a", encoding="utf-8") as f:
        if HAS_FCNTL:
            fcntl.flock(f, fcntl.LOCK_EX)
        f.write(entry)
        if HAS_FCNTL:
            fcntl.flock(f, fcntl.LOCK_UN)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/rsvp", methods=["POST"])
def rsvp():
    body = request.get_json(silent=True) or {}

    first_name  = body.get("first_name", "").strip()
    last_name   = body.get("last_name", "").strip()
    email       = body.get("email", "").strip()
    guest_count = body.get("guest_count", "1")
    guest_names = body.get("guest_names", "").strip()

    # Validation
    if not first_name or not last_name:
        return jsonify({"message": "First and last name are required."}), 400

    # Sanitize guest count
    try:
        guest_count_int = max(1, min(20, int(guest_count)))
    except (ValueError, TypeError):
        guest_count_int = 1

    # Duplicate check
    existing = get_all_names()
    key = normalize_name(first_name, last_name)

    if key in existing:
        # Store info in session so thanks page can show the right state
        session["rsvp_data"] = {
            "first_name":    first_name,
            "last_name":     last_name,
            "guest_count":   guest_count_int,
            "already_rsvpd": True,
        }
        return jsonify({"redirect": url_for("thanks")}), 200

    # Write to file
    append_rsvp({
        "first_name":   first_name,
        "last_name":    last_name,
        "email":        email,
        "guest_count":  guest_count_int,
        "guest_names":  guest_names,
    })

    # Update count (simple read-modify-write; safe for low concurrency)
    counts = load_count()
    counts["total_guests"]  += guest_count_int
    counts["total_rsvps"]   += 1
    save_count(counts)

    session["rsvp_data"] = {
        "first_name":    first_name,
        "last_name":     last_name,
        "guest_count":   guest_count_int,
        "already_rsvpd": False,
    }

    return jsonify({"redirect": url_for("thanks")}), 200


@app.route("/thanks")
def thanks():
    rsvp_data = session.pop("rsvp_data", None)

    if not rsvp_data:
        # No session — redirect home gracefully
        return redirect(url_for("index"))

    counts = load_count()

    return render_template(
        "thanks.html",
        first_name    = rsvp_data.get("first_name", ""),
        last_name     = rsvp_data.get("last_name", ""),
        guest_count   = rsvp_data.get("guest_count", 1),
        already_rsvpd = rsvp_data.get("already_rsvpd", False),
        total_count   = counts.get("total_guests", 0),
        total_rsvps   = counts.get("total_rsvps", 0),
    )


# ── Admin view ────────────────────────────────────────────────────────────────

@app.route("/admin", methods=["GET", "POST"])
def admin():
    """Simple password-protected view of the RSVP list and count."""
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
        else:
            return _admin_login(error="Incorrect password.")

    if not session.get("admin"):
        return _admin_login()

    counts = load_count()
    raw    = RSVP_FILE.read_text(encoding="utf-8") if RSVP_FILE.exists() else "(No RSVPs yet)"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>RSVP Admin — Alex & Matt</title>
  <style>
    body {{ font-family: Georgia, serif; max-width: 720px; margin: 3rem auto;
            padding: 0 1.5rem; background: #f8f4f0; color: #2c1a20; }}
    h1 {{ font-size: 1.8rem; margin-bottom: 0.3rem; }}
    .stats {{ display: flex; gap: 2rem; margin: 1.5rem 0; }}
    .stat {{ background: #fff; border: 1px solid #d4b8c2; padding: 1rem 1.5rem;
             border-radius: 3px; text-align: center; }}
    .stat-n {{ font-size: 2.4rem; font-weight: bold; color: #6b2533; }}
    .stat-l {{ font-size: 0.78rem; letter-spacing: 0.2em; text-transform: uppercase;
               color: #8b6070; margin-top: 0.2rem; }}
    pre {{ background: #fff; border: 1px solid #d4b8c2; padding: 1.2rem;
           border-radius: 3px; white-space: pre-wrap; font-size: 0.88rem;
           max-height: 60vh; overflow-y: auto; color: #2c1a20; }}
    a {{ color: #6b2533; font-size: 0.88rem; }}
    .logout {{ margin-top: 1rem; display: block; }}
  </style>
</head>
<body>
  <h1>RSVP Guest List</h1>
  <p style="color:#8b6070;font-style:italic">Alex &amp; Matt — September 25, 2026</p>
  <div class="stats">
    <div class="stat">
      <div class="stat-n">{counts.get('total_rsvps', 0)}</div>
      <div class="stat-l">Parties RSVP'd</div>
    </div>
    <div class="stat">
      <div class="stat-n">{counts.get('total_guests', 0)}</div>
      <div class="stat-l">Total Guests</div>
    </div>
  </div>
  <pre>{raw}</pre>
  <a href="/admin/logout" class="logout">Log out</a>
</body>
</html>"""


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin"))


def _admin_login(error=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Admin Login</title>
  <style>
    body {{ font-family: Georgia, serif; display: flex; align-items: center;
            justify-content: center; min-height: 100vh; background: #f0e8e3; }}
    form {{ background: #faf6f2; border: 1px solid #d4b8c2; padding: 2.5rem;
            max-width: 340px; width: 100%; text-align: center; }}
    h2 {{ font-size: 1.3rem; margin-bottom: 1.2rem; color: #4a1a24; }}
    input[type=password] {{ width: 100%; padding: 0.6rem; margin: 0.8rem 0;
                            border: 1px solid #d4b8c2; font-size: 1rem; }}
    button {{ background: #6b2533; color: #faf6f2; border: none;
              padding: 0.7rem 2rem; cursor: pointer; font-size: 0.9rem;
              letter-spacing: 0.1em; width: 100%; }}
    .err {{ color: #c0392b; font-size: 0.9rem; margin-top: 0.5rem; }}
  </style>
</head>
<body>
  <form method="POST" action="/admin">
    <h2>RSVP Admin</h2>
    <input type="password" name="password" placeholder="Password" autofocus />
    <button type="submit">Enter</button>
    {'<p class="err">' + error + '</p>' if error else ''}
  </form>
</body>
</html>"""


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
