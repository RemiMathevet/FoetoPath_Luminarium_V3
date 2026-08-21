"""Blueprint feedback / suggestions (widget ampoule)."""

import os
from datetime import datetime

from flask import Blueprint, jsonify, request, session

from auth_bp import login_required

feedback_bp = Blueprint("feedback", __name__)

FEEDBACK_DIR = os.path.join(os.path.dirname(__file__), "feedback")


@feedback_bp.route("/api/feedback", methods=["GET", "POST"])
@login_required
def feedback():
    if request.method == "GET":
        items = []
        if os.path.isdir(FEEDBACK_DIR):
            for fname in sorted(os.listdir(FEEDBACK_DIR), reverse=True):
                if not fname.endswith(".txt"):
                    continue
                filepath = os.path.join(FEEDBACK_DIR, fname)
                with open(filepath, "r") as f:
                    lines = f.read().split("\n")
                item = {"file": fname, "author": "", "type": "", "page": "", "date": "", "text": ""}
                in_body = False
                body_lines = []
                for line in lines:
                    if line.startswith("---"):
                        in_body = True
                        continue
                    if in_body:
                        body_lines.append(line)
                    elif line.startswith("Date : "):
                        item["date"] = line[7:]
                    elif line.startswith("Auteur : "):
                        item["author"] = line[9:]
                    elif line.startswith("Type : "):
                        item["type"] = line[7:]
                    elif line.startswith("Page : "):
                        item["page"] = line[7:]
                item["text"] = "\n".join(body_lines).strip()
                items.append(item)
        return jsonify(items=items)

    data = request.get_json(silent=True)
    if not data or not data.get("text"):
        return jsonify(ok=False, error="texte requis"), 400
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = data.get("name", "Anonyme").replace("/", "-")[:30]
    typ = data.get("type", "idee")[:20]
    page = data.get("page", "inconnue").replace("/", "").replace(".html", "")[:40]
    user = session.get("username", "?")
    filename = f"{ts}_{page}_{typ}_{name}.txt"
    content = (
        f"Date : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Auteur : {name}\n"
        f"Type : {typ}\n"
        f"Page : {page}\n"
        f"Utilisateur connecté : {user}\n"
        f"---\n"
        f"{data['text']}\n"
    )
    os.makedirs(FEEDBACK_DIR, exist_ok=True)
    with open(os.path.join(FEEDBACK_DIR, filename), "w") as f:
        f.write(content)
    return jsonify(ok=True)
