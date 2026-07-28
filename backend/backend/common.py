import os

from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# --------------------------------------------------
# OUTPUT DIRECTORY
# --------------------------------------------------

# Anchored to this file's directory so both pdf_generator.py and
# pdf_generator_default.py resolve to the same "generated" folder
# regardless of which one is the entrypoint.
OUTPUT_DIRECTORY = os.path.join(os.path.dirname(__file__), "generated")

# --------------------------------------------------
# FONT REGISTRATION (TIMES-ROMAN STANDARD)
# --------------------------------------------------

FONT_NAME = "Times-Roman"
FONT_BOLD = "Times-Bold"

try:
    font_dir = os.path.dirname(__file__)
    regular_path = os.path.join(font_dir, "Times.ttf")
    bold_path = os.path.join(font_dir, "Times-Bold.ttf")

    if os.path.exists(regular_path):
        pdfmetrics.registerFont(TTFont("CustomTimes", regular_path))
        FONT_NAME = "CustomTimes"

    if os.path.exists(bold_path):
        pdfmetrics.registerFont(TTFont("CustomTimes-Bold", bold_path))
        FONT_BOLD = "CustomTimes-Bold"
    elif FONT_NAME == "CustomTimes":
        FONT_BOLD = "CustomTimes"
except Exception:
    FONT_NAME = "Times-Roman"
    FONT_BOLD = "Times-Bold"

# --------------------------------------------------
# PAGE & CONSTANTS
# --------------------------------------------------

PAGE = {
    "left": 58,
    "right": 554,
    "top": 26,
    "bottom": 760,
}

PAGE_OFFSET = -6

DEFAULT_FONT_SIZE = 8.5
DEFAULT_LINE_WIDTH = 0.5
DEFAULT_PADDING = 2

# Set to True to print every dict's real keys the first time each
# section function touches it. Extremely useful for tracking down
# "why is this field blank" bugs without opening a debugger.
DEBUG_DUMP_KEYS = False


# --------------------------------------------------
# VALUE / FIELD HELPERS
# --------------------------------------------------


def value(v):
    if v is None:
        return ""
    return str(v)


def field(obj, key):
    if not obj:
        return ""
    return value(obj.get(key))


def _normalize_key(k):
    """Collapse case / underscores / spaces so 'etd_local', 'etdLocal',
    'ETD Local' and 'etdlocal' are all treated as the same key."""
    return str(k).lower().replace("_", "").replace(" ", "").replace("-", "")


def find_value(*objs_and_keys):
    """Robust multi-source, multi-key-name lookup.

    Usage: find_value(dict1, dict2, ..., 'key1', 'key2', ...)
    Any dict before the first string argument is treated as a source to
    search; any string argument is treated as a candidate key name.
    Returns the first non-empty match, trying an exact key match across
    all sources first, then a normalized (case/underscore-insensitive)
    match across all sources.
    """
    sources = [o for o in objs_and_keys if isinstance(o, dict) and o]
    keys = [k for k in objs_and_keys if isinstance(k, str)]

    if DEBUG_DUMP_KEYS:
        for src in sources:
            print(f"[DEBUG] available keys: {sorted(src.keys())}")

    # Exact match pass
    for src in sources:
        for k in keys:
            if k in src and src[k] not in (None, ""):
                return value(src[k])

    # Normalized match pass (handles etdLocal vs etd_local vs ETD_LOCAL etc.)
    norm_keys = {_normalize_key(k) for k in keys}
    for src in sources:
        for real_key, v in src.items():
            if _normalize_key(real_key) in norm_keys and v not in (None, ""):
                return value(v)

    return ""


def wrap_text(text, font_name, font_size, width):
    text = value(text)
    if text == "":
        return [""]

    pdf = canvas.Canvas(None)
    pdf.setFont(font_name, font_size)

    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue

        current = words[0]
        for word in words[1:]:
            trial = current + " " + word
            if stringWidth(trial, font_name, font_size) <= width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)

    return lines


def write(pdf, text, x, y, width, options=None):
    if options is None:
        options = {}

    font = FONT_BOLD if options.get("bold") else FONT_NAME
    size = options.get("size", DEFAULT_FONT_SIZE)
    align = options.get("align", "left")
    line_break = options.get("lineBreak", True)
    padding = options.get("padding", DEFAULT_PADDING)

    pdf.setFont(font, size)
    page_height = letter[1]

    if not line_break:
        yy = page_height - y
        if align == "center":
            pdf.drawCentredString(x + width / 2, yy, value(text))
        elif align == "right":
            pdf.drawRightString(x + width, yy, value(text))
        else:
            pdf.drawString(x + padding, yy, value(text))
        return

    lines = wrap_text(text, font, size, width - padding * 2)
    line_height = size + 1
    yy = page_height - y

    for line_text in lines:
        if align == "center":
            pdf.drawCentredString(x + width / 2, yy, line_text)
        elif align == "right":
            pdf.drawRightString(x + width, yy, line_text)
        else:
            pdf.drawString(x + padding, yy, line_text)
        yy -= line_height


def line(pdf, x1, y1, x2, y2, width=DEFAULT_LINE_WIDTH):
    page_height = letter[1]
    pdf.setLineWidth(width)
    pdf.line(x1, page_height - y1, x2, page_height - y2)


def box(pdf, x, y, width, height):
    page_height = letter[1]
    pdf.setLineWidth(DEFAULT_LINE_WIDTH)
    pdf.rect(x, page_height - y - height, width, height, stroke=1, fill=0)


def route_header(pdf, title, registration):
    write(
        pdf,
        f"{value(title)}    {value(registration)}",
        PAGE["left"],
        18,
        496,
        {"size": 10, "align": "right", "lineBreak": False},
    )


def section_heading(pdf, title, x, y, width):
    write(
        pdf,
        f"- - - - - - - - - - - - - {title} - - - - - - - - - - - - -",
        x,
        y,
        width,
        {"size": 8.5, "bold": False, "align": "center", "lineBreak": False},
    )


def labelled_value(pdf, label, data, x, y, label_width=76, total_width=220):
    write(pdf, label, x, y, label_width, {"size": 8.5, "lineBreak": False})
    write(pdf, ":", x + label_width, y, 8, {"size": 8.5, "lineBreak": False})
    write(
        pdf,
        data,
        x + label_width + 12,
        y,
        total_width - label_width - 12,
        {"size": 8.5},
    )


# --------------------------------------------------
# NAVLOG COLUMNS (PAGE 2 & 3) -- shared table layout
# --------------------------------------------------

NAV_COLUMNS = [
    ("waypoint", "", "WAYPOINT\nAIRWAY", 93),
    ("heading", "", "HDG\nCRS", 30),
    ("flightLevel", "", "FL", 37),
    ("windDirectionSpeed", "WIND", "DIR/SPD\nCMP", 49),
    ("isa", "", "ISA", 25),
    ("tas", "SPD KT", "TAS\nGS", 32),
    ("legDistance", "DIST NM", "LEG\nREM", 37),
    ("fuelUsed", "FUEL LB", "USED\nREM", 39),
    ("ete", "TIME", "ETE", 28),
    ("legTimeRemaining", "TIME", "LEG\nREM", 30),
    ("eta", "", "ETA ATA", 36),
    ("actualFuel", "", "ACTUAL FUEL", 60),
]


def combined_row_value(row, key):
    if key == "waypoint":
        wp = value(row.get("waypoint"))
        detail = value(row.get("waypointDetail"))
        airway = value(row.get("airway"))
        line1 = f"{wp} {detail}".strip() if detail else wp
        return "\n".join([v for v in [line1, airway] if v])

    mappings = {
        "heading": [row.get("heading"), row.get("course")],
        "windDirectionSpeed": [row.get("windDirectionSpeed"), row.get("windComponent")],
        "tas": [row.get("tas"), row.get("gs")],
        "legDistance": [row.get("legDistance"), row.get("remainingDistance")],
        "fuelUsed": [row.get("fuelUsed"), row.get("fuelRemaining")],
        "legTimeRemaining": [row.get("legTime"), row.get("remainingTime")],
        "eta": [row.get("eta"), row.get("ata")],
    }

    if key in mappings:
        return "\n".join([value(v) for v in mappings[key] if value(v)])

    return value(row.get(key))


def draw_navlog_header(pdf, y):
    x = PAGE["left"]
    top_header_height = 18
    bottom_header_height = 34
    total_header_height = top_header_height + bottom_header_height
    font_size = 7.5

    idx = 0
    while idx < len(NAV_COLUMNS):
        key, top_title, bottom_title, width = NAV_COLUMNS[idx]

        if top_title:
            span_width = width
            next_idx = idx + 1
            while next_idx < len(NAV_COLUMNS) and NAV_COLUMNS[next_idx][1] == top_title:
                span_width += NAV_COLUMNS[next_idx][3]
                next_idx += 1

            box(pdf, x, y, span_width, top_header_height)
            write(pdf, top_title, x + 2, y + 12, span_width - 4, {"size": font_size, "align": "center", "lineBreak": False})

            sub_x = x
            for sub_i in range(idx, next_idx):
                s_key, s_top, s_bottom, s_width = NAV_COLUMNS[sub_i]
                box(pdf, sub_x, y + top_header_height, s_width, bottom_header_height)
                line_count = value(s_bottom).count("\n") + 1
                text_y = y + top_header_height + (bottom_header_height - (line_count * (font_size + 1))) / 2 + font_size - 1
                write(pdf, s_bottom, sub_x + 2, text_y, s_width - 4, {"size": font_size, "align": "center"})
                sub_x += s_width

            x += span_width
            idx = next_idx
        else:
            box(pdf, x, y, width, total_header_height)
            line_count = value(bottom_title).count("\n") + 1
            text_y = y + (total_header_height - (line_count * (font_size + 1))) / 2 + font_size - 1
            write(pdf, bottom_title, x + 2, text_y, width - 4, {"size": font_size, "align": "center"})
            x += width
            idx += 1

    return y + total_header_height


def draw_navlog_rows(pdf, rows, start_y, maximum_y):
    y = start_y
    if rows is None:
        rows = []

    font_size = 7.5
    line_height = font_size + 1
    min_height = 26
    vertical_padding = 4

    for index, row in enumerate(rows):
        max_lines = 1
        for key, _, _, _ in NAV_COLUMNS:
            cell_text = combined_row_value(row, key)
            max_lines = max(max_lines, value(cell_text).count("\n") + 1)

        content_height = max_lines * line_height + vertical_padding
        height = max(min_height, content_height)

        if y + height > maximum_y:
            return {"y": y, "remaining": rows[index:]}

        x = PAGE["left"]
        for key, _, _, width in NAV_COLUMNS:
            box(pdf, x, y, width, height)
            cell_text = combined_row_value(row, key)
            line_count = value(cell_text).count("\n") + 1
            text_y = y + (height - (line_count * line_height)) / 2 + font_size

            write(
                pdf,
                cell_text,
                x + 3,
                text_y,
                width - 6,
                {"size": font_size, "align": "left" if key == "waypoint" else "center"},
            )
            x += width

        y += height

    return {"y": y, "remaining": []}


def draw_navlog_title(pdf, title_left, title_right, y):
    banner_height = 24
    box(pdf, PAGE["left"], y, 496, banner_height)
    text_y = y + 15

    write(pdf, title_left, PAGE["left"] + 6, text_y, 180, {"size": 8.5, "lineBreak": False})
    write(pdf, title_right, PAGE["left"] + 190, text_y, 300, {"size": 8.5, "lineBreak": False})

    return y + banner_height