import os
import json
import traceback

from flask import (
    Flask,
    request,
    jsonify,
    send_from_directory
)

from flask_cors import CORS
from werkzeug.utils import secure_filename

from htmlParser import parse_html
from claude import convert_with_claude
from pdfGenerator import generate_pdf


# =====================================================
# APP
# =====================================================

app = Flask(__name__)

CORS(app)

PORT = int(
    os.getenv("PORT", 5000)
)

# Base URL the browser uses to fetch a generated PDF, so it has to be the
# service's PUBLIC address.
#
# RENDER_EXTERNAL_URL is injected by Render on every web service and holds
# the full "https://name.onrender.com". A blueprint's
# `fromService: property: host` does NOT - it resolves to the bare
# internal service name ("eflightops-api"), and download links built from
# it point at a host that does not exist off-platform.


def _is_reachable_base(url):
    """Could a browser on the public internet actually resolve this?

    A bare label with no dot ("eflightops-api") is an internal service
    name, not a hostname. Removing such a value from render.yaml does not
    unset it on an already-provisioned service, so an operator-supplied
    PUBLIC_BASE_URL is only trusted when it looks externally routable -
    otherwise the platform's own value wins.
    """
    if not url:
        return False
    host = url.split("://")[-1].split("/")[0].split(":")[0]
    return "." in host or host == "localhost"


_configured = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
_platform = (os.getenv("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")

if _is_reachable_base(_configured):
    PUBLIC_URL = _configured
elif _is_reachable_base(_platform):
    PUBLIC_URL = _platform
else:
    PUBLIC_URL = f"http://localhost:{PORT}"

# A hostname supplied without a scheme still has to end up absolute, or
# the link resolves relative to the frontend's origin.
if "://" not in PUBLIC_URL:
    PUBLIC_URL = f"https://{PUBLIC_URL}"

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(__file__),
    "uploads"
)

GENERATED_FOLDER = os.path.join(
    os.path.dirname(__file__),
    "generated"
)

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

os.makedirs(
    GENERATED_FOLDER,
    exist_ok=True
)

DEFAULT_TEMPLATE = "MLOVE"


# =====================================================
# STATIC PDF FOLDER
# (Equivalent to express.static())
# =====================================================

@app.route("/generated/<path:filename>")
def generated_files(filename):

    return send_from_directory(
        GENERATED_FOLDER,
        filename
    )


# =====================================================
# HOME
# =====================================================

@app.route("/", methods=["GET"])
def home():

    return "🚀 EFLIGHT AI Backend Running"


# =====================================================
# EMPTY ROUTE
# =====================================================

def empty_route():

    return {

        "header": "",

        "performance": {},

        "fuel": {},

        "weight": {},

        "route": "",

        "waypoints": [],

        "airportInfo": {}

    }


# =====================================================
# CONVERT
# =====================================================

@app.route("/convert", methods=["POST"])
def convert():

    try:

        print(
            "\n========== NEW CONVERSION ==========\n"
        )

        # -------------------------------------

        if "mainFile" not in request.files:

            return jsonify({

                "success": False,

                "message":
                    "Main HTML file missing."

            }), 400

        # -------------------------------------
        # USER INPUT
        # -------------------------------------

        user_input = json.loads(

            request.form["userInput"]

        )

        print(user_input)

        # -------------------------------------
        # PDF TEMPLATE SELECTION
        # -------------------------------------

        template = user_input.get("selectedFormat", DEFAULT_TEMPLATE).strip().upper()

        print(f"📄 Using PDF template: {template}")

        # -------------------------------------
        # MAIN ROUTE
        # -------------------------------------

        main_file = request.files["mainFile"]

        main_path = os.path.join(

            UPLOAD_FOLDER,

            secure_filename(
                main_file.filename
            )

        )

        main_file.save(main_path)

        with open(

            main_path,

            "r",

            encoding="utf8"

        ) as f:

            main_html = f.read()

        main_route = parse_html(

            main_html

        )

        # -------------------------------------
        # ALT 1
        # -------------------------------------

        alternate1 = empty_route()

        if "alternate1File" in request.files:

            file = request.files[
                "alternate1File"
            ]

            path = os.path.join(

                UPLOAD_FOLDER,

                secure_filename(
                    file.filename
                )

            )

            file.save(path)

            with open(

                path,

                "r",

                encoding="utf8"

            ) as f:

                html = f.read()

            alternate1 = parse_html(html)

        # -------------------------------------
        # ALT 2
        # -------------------------------------

        alternate2 = empty_route()

        if "alternate2File" in request.files:

            file = request.files[
                "alternate2File"
            ]

            path = os.path.join(

                UPLOAD_FOLDER,

                secure_filename(
                    file.filename
                )

            )

            file.save(path)

            with open(

                path,

                "r",

                encoding="utf8"

            ) as f:

                html = f.read()

            alternate2 = parse_html(html)

        # -------------------------------------
        # MASTER JSON
        # -------------------------------------

        master_json = {

            "userInput": user_input,

            "mainRoute": main_route,

            "alternate1": alternate1,

            "alternate2": alternate2

        }

        print(

            json.dumps(

                master_json,

                indent=2

            )

        )

        # -------------------------------------
        # CLAUDE
        # -------------------------------------

        final_json = convert_with_claude(

            master_json,

            template

        )

        # -------------------------------------
        # PDF
        # -------------------------------------

        pdf_path = generate_pdf(

            final_json,

            file_prefix=template

        )

        # -------------------------------------
        # DELETE TEMP FILES
        # -------------------------------------

        for file in request.files.values():

            try:

                os.remove(

                    os.path.join(

                        UPLOAD_FOLDER,

                        secure_filename(
                            file.filename
                        )

                    )

                )

            except:

                pass

        # -------------------------------------
        # RESPONSE
        # -------------------------------------

        return jsonify({

            "success": True,

            "template": template,

            "pdf":

                f"{PUBLIC_URL}/"

                + pdf_path.replace(

                    os.sep,

                    "/"

                ),

            "data": final_json

        })

    except Exception as error:

        traceback.print_exc()

        return jsonify({

            "success": False,

            "message": str(error)

        }), 500


# =====================================================
# START
# =====================================================

if __name__ == "__main__":

    print(

        f"🚀 Backend Running on {PUBLIC_URL}"

    )

    app.run(

        host="0.0.0.0",

        port=PORT,

        debug=True

    )