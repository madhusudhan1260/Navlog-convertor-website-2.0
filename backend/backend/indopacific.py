import os
import re
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from common import OUTPUT_DIRECTORY, find_value, value

# --------------------------------------------------
# INDO PACIFIC TEMPLATE (1 ALT / 2 ALT)
# --------------------------------------------------
# Measured off the operator's own reference documents ("NAV VTBBN - INDO
# PACIFIC 1 ALT" and "... 2 ALT") with a text/rect bbox extraction, so the
# layout copies those PDFs rather than re-interpreting them.
#
# The two documents are one layout: every anchor is identical down to the
# ALTN1 row, and the second alternate then pushes the block beneath it
# down by exactly one plan row. INDO PACIFIC 1 and INDO PACIFIC 2 are
# offered as separate output formats because the operator files them as
# separate documents - format 2 reserves the ALTN2 row even before the
# second alternate is uploaded, so the sheet matches the one that was
# asked for.
#
# Page 1 is the same family as VTCSP - banner, DEP/DIST/TRACK +
# DEST/CRUISE/PAX block, COMPUTED FUEL pairs, PLAN TIME & FUEL / PLAN WT
# columns, DIFFERENT LEVEL CALCULATION / ACTUALS, hand-fill ATIS blocks,
# V-speeds and a certification footer - but this one is A4 rather than
# Letter, sets its body text a little larger, prints its ACTUALS and
# V-speed rules as underscore characters rather than drawn lines, and
# closes with a two-line certification instead of four.
#
# Pages 2+ are NOT VTCSP's flat 19-column navlog: this template stacks
# its pairs (HDG over CRS, TAS over GS, and so on) into 12 columns, the
# same column model MLOVE uses, at its own widths.

PAGE_W, PAGE_H = A4

FONT = "Times-Roman"
FONT_BOLD = "Times-Bold"

SIZE = 9.4
SIZE_CRUISE = 7.5
SIZE_CERT = 9.0
SIZE_FPL = 8.2

# One PLAN TIME & FUEL row - also how far the block below it moves when
# a second alternate adds an ALTN2 row.
PLAN_ROW_STEP = 14.15

FRAME_X0 = 34.4
FRAME_X1 = 560.9
FRAME_TOP = 34.4
FRAME_BOTTOM = 806.0

CENTER_X = (FRAME_X0 + FRAME_X1) / 2
# The reference sets its banner slightly left of the frame's centre.
BANNER_CENTER_X = 280.5

# --------------------------------------------------
# DRAWING PRIMITIVES (y measured DOWN from the page top)
# --------------------------------------------------


def _text(pdf, x, y, content, size=SIZE, font=FONT):
    if content in (None, ""):
        return
    pdf.setFont(font, size)
    pdf.drawString(x, PAGE_H - y, str(content))


def _text_right(pdf, x, y, content, size=SIZE, font=FONT):
    if content in (None, ""):
        return
    pdf.setFont(font, size)
    pdf.drawRightString(x, PAGE_H - y, str(content))


def _text_center(pdf, x, y, content, size=SIZE, font=FONT):
    if content in (None, ""):
        return
    pdf.setFont(font, size)
    pdf.drawCentredString(x, PAGE_H - y, str(content))


def _hline(pdf, x0, x1, y, width=0.75):
    pdf.setLineWidth(width)
    pdf.line(x0, PAGE_H - y, x1, PAGE_H - y)


def _vline(pdf, x, y0, y1, width=0.75):
    pdf.setLineWidth(width)
    pdf.line(x, PAGE_H - y0, x, PAGE_H - y1)


def _rect(pdf, x0, y0, x1, y1, width=0.9):
    pdf.setLineWidth(width)
    pdf.rect(x0, PAGE_H - y1, x1 - x0, y1 - y0, stroke=1, fill=0)


def _wrap(content, size, max_width, font=FONT):
    from reportlab.pdfbase.pdfmetrics import stringWidth

    words = str(content or "").split()
    if not words:
        return []

    lines = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if stringWidth(trial, font, size) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


# --------------------------------------------------
# VALUE FORMATTING
# --------------------------------------------------


def _lbs(v):
    v = value(v)
    if not v:
        return ""
    return v if v.upper().endswith("LBS") else f"{v} LBS"


def _nm(v):
    v = value(v)
    if not v:
        return ""
    return v if v.upper().endswith("NM") else f"{v}NM"


def _space_fl(s):
    return re.sub(r"\bFL(\d)", r"FL \1", value(s))


def _degrees(v):
    v = value(v)
    if not v:
        return ""
    return v if v.upper().endswith("DEG") else f"{v} DEG"


def _rank(name):
    name = value(name).upper()
    if not name:
        return ""
    if re.match(r"^(CAPT|CPT|CMDR|MR|MS|MRS|FO|F/O)\b", name):
        return name
    return f"CAPT {name}"


def _cruise_tail(profile_text):
    """MAIN ROUTE prints the cruise-profile tail (after "@ FLxxx - ")
    ahead of the ATC route."""
    match = re.search(r"@\s*FL\d+\s*-\s*(.+)$", value(profile_text), re.IGNORECASE)
    return match.group(1).strip().upper() if match else ""


def _page_header(pdf, data):
    header = data.get("page1", {}).get("header", {})
    flight = data.get("page1", {}).get("flightInfo", {})

    route_title = value(header.get("routeTitle"))
    registration = value(header.get("registration") or flight.get("registration"))

    _text_right(pdf, 554.9, 27.9, f"{route_title}     {registration}".strip())


# --------------------------------------------------
# PAGE ONE
# --------------------------------------------------


def draw_page_one(pdf, data, force_alternate2=False):
    page1 = data.get("page1", {})
    flight = page1.get("flightInfo", {})
    time_info = page1.get("time", {})
    fuel = page1.get("fuel", {})
    weight = page1.get("weight", {})
    misc = page1.get("misc", {})
    header = page1.get("header", {})
    operational = page1.get("operational", {})
    alternates = page1.get("alternates", [])
    level_calcs = data.get("levelCalculations", [])
    atc = data.get("atcFlightPlan", {})

    _page_header(pdf, data)
    _rect(pdf, FRAME_X0, FRAME_TOP, FRAME_X1, FRAME_BOTTOM)

    # ---- banner ----
    registration = value(header.get("registration") or flight.get("registration"))
    ac_type = find_value(header, flight, atc, "aircraftType", "type", "acType")
    date_str = value(flight.get("date"))
    etd = value(time_info.get("etd"))
    eta = value(time_info.get("eta"))

    banner = (
        f"- - - - - {registration} ({ac_type}) {date_str} "
        f"NAV LOG/ OPS FPL FOR ETD {etd} (ETA {eta}) - - - - -"
    )
    banner = re.sub(r"\s+", " ", banner).replace("() ", "").replace("(ETA ) ", "")
    _text_center(pdf, BANNER_CENTER_X, 69.9, banner)

    # ---- DEP / DEST + DIST / CRUISE + TRACK / PAX ----
    dep_code = value(flight.get("departure"))
    dest_code = value(flight.get("destination"))

    _text(pdf, 50.5, 95.7, "DEP")
    _text(pdf, 77.0, 95.7, ":")
    _text(pdf, 82.6, 95.7, dep_code)

    _text(pdf, 50.5, 109.8, "DEST")
    _text(pdf, 77.0, 109.8, ":")
    _text(pdf, 82.6, 109.8, dest_code)

    _text(pdf, 251.2, 92.3, "DIST")
    _text(pdf, 301.2, 92.3, ":")
    _text(pdf, 308.9, 92.3, _nm(time_info.get("plannedRouteDistance")))

    _text(pdf, 251.2, 109.8, "CRUISE")
    _text(pdf, 301.2, 109.8, ":")

    cruise_lines = _wrap(value(misc.get("plannedProfile")).upper(), SIZE_CRUISE, 140.0)
    cruise_y = 104.7
    for cruise_line in cruise_lines[:4]:
        _text(pdf, 308.9, cruise_y, cruise_line, size=SIZE_CRUISE)
        cruise_y += 8.9

    _text(pdf, 451.9, 95.7, "TRACK")
    _text(pdf, 486.7, 95.7, ":")
    _text(pdf, 492.3, 95.7, _degrees(time_info.get("track")))

    _text(pdf, 451.9, 109.8, "PAX")
    _text(pdf, 486.7, 109.8, ":")
    _text(pdf, 492.3, 109.8, weight.get("pax"))

    # ---- MAIN ROUTE / crew ----
    main_route = " ".join(
        part
        for part in [
            value(flight.get("flightLevel")),
            "-" if _cruise_tail(misc.get("plannedProfile")) else "",
            _cruise_tail(misc.get("plannedProfile")),
            value(data.get("routes", {}).get("mainRoute")),
        ]
        if part
    )
    _text(pdf, 48.3, 132.5, f"MAIN ROUTE : {main_route}".strip())

    _text(pdf, 48.3, 149.7, f"PIC : {_rank(flight.get('pic'))}".rstrip())
    _text(pdf, 299.1, 149.7, f"FO : {_rank(flight.get('fo'))}".rstrip())

    # ---- COMPUTED FUEL block ----
    landing_fuel = find_value(fuel, "landingReported") or value(fuel.get("landing"))

    fuel_pairs = [
        ("COMPUTED FUEL", _lbs(fuel.get("ramp")), "BLOCK FUEL", _lbs(fuel.get("flight"))),
        ("MIN. TRIP FUEL", _lbs(fuel.get("minTripFuel")), "TAKE OFF FUEL", _lbs(fuel.get("takeoff"))),
        ("MAX. TRIP FUEL", _lbs(fuel.get("maxTripFuel")), "LANDING FUEL", _lbs(landing_fuel)),
    ]

    for (left_label, left_val, right_label, right_val), y in zip(
        fuel_pairs, [170.5, 184.7, 198.8]
    ):
        _text(pdf, 50.5, y, left_label)
        _text(pdf, 130.9, y, ":")
        _text_right(pdf, 215.1, y, left_val)

        _text(pdf, 301.4, y, right_label)
        _text(pdf, 375.2, y, ":")
        _text_right(pdf, 474.2, y, right_val)

    _text(pdf, 50.5, 213.0, "TOP CLIMB TEMP")
    _text(pdf, 130.9, 213.0, ":")
    _text(pdf, 136.5, 213.0, _space_fl(time_info.get("topClimbTemp")))

    _text(pdf, 301.4, 213.0, "WIND")
    _text(pdf, 375.2, 213.0, ":")
    _text(pdf, 385.5, 213.0, value(time_info.get("averageWinds")).upper())

    # ---- PLAN TIME & FUEL / PLAN WT ----
    _text(
        pdf,
        51.0,
        231.6,
        "- - - - - - - - PLAN TIME & FUEL - - - - - - - - - - - - - - - - - - - - - - "
        "- - - - - - PLAN WT (in LBS) - - - - - - - - - - - - - - -",
    )

    alt1 = alternates[0] if len(alternates) > 0 else {}
    alt2 = alternates[1] if len(alternates) > 1 else {}

    # The ALTN2 row appears when a second alternate was filed, or when the
    # operator explicitly asked for the two-alternate sheet (in which case
    # it prints as an empty row for them to fill by hand).
    show_alternate2 = bool(alt2) or force_alternate2

    plan_rows = [
        ("TRIP", find_value(fuel, "tripTime", "trip_time"), fuel.get("trip")),
        ("TAXI", find_value(fuel, "taxiTime", "taxi_time"), fuel.get("taxi")),
        (
            "CONTINGENCY 5%",
            find_value(fuel, "contingencyTime", "contingency_time"),
            fuel.get("contingency"),
        ),
        (
            "FINAL RESERVE FUEL",
            find_value(fuel, "finalReserveTime", "final_reserve_time"),
            fuel.get("finalReserve"),
        ),
        ("XTRA", find_value(fuel, "extraEndurance", "extra_endurance"), fuel.get("extra")),
        ("ALTN1", find_value(fuel, "alternateTime", "alternate_time"), fuel.get("alternate")),
    ]

    # The single-alternate reference has no ALTN2 row at all.
    if show_alternate2:
        plan_rows.append(
            ("ALTN2", find_value(fuel, "alternate2Time", "alternate2_time"),
             fuel.get("alternate2Fuel"))
        )

    plan_y = 250.2
    for label, time_val, fuel_val in plan_rows:
        _text(pdf, 50.5, plan_y, label)
        _text(pdf, 150.9, plan_y, ":")
        _text(pdf, 161.2, plan_y, time_val)
        _text_right(pdf, 233.0, plan_y, _lbs(fuel_val))
        plan_y += PLAN_ROW_STEP

    weight_rows = [
        ("BASIC WT", weight.get("basicOperatingWeight")),
        ("LOAD", weight.get("load")),
        ("ZERO FUEL", weight.get("zeroFuelWeight")),
        ("T.OFF WT", weight.get("takeoffWeight")),
        ("LAND WT", weight.get("estimatedLandingWeight")),
    ]

    weight_y = 250.2
    for label, weight_val in weight_rows:
        _text(pdf, 301.4, weight_y, label)
        _text(pdf, 362.4, weight_y, ":")
        _text_right(pdf, 420.9, weight_y, _lbs(weight_val))
        weight_y += PLAN_ROW_STEP

    # A second alternate adds an ALTN2 row to the plan column, and the
    # reference pushes everything below it - the ENDURANCE rule, the level
    # calculation / ACTUALS block, the briefing lines, the V-speeds and the
    # certification - down by exactly that one row. The right-hand ALTN /
    # MIN DIVERT / route lines stay where they are.
    shift = PLAN_ROW_STEP if show_alternate2 else 0.0

    alt1_dist = _nm(alt1.get("distance"))
    if alt1_dist:
        _text(pdf, 301.4, 323.9, f"ALTN : {alt1_dist}")

    min_divert = _lbs(fuel.get("minDivertFuel"))
    if min_divert:
        _text(pdf, 384.2, 323.9, f"MIN DIVERT FUEL: {min_divert}")

    routes = data.get("routes", {})
    first_route = value(routes.get("alternate1Route")).replace("Route", "").strip()
    second_route = value(routes.get("alternate2Route")).replace("Route", "").strip()

    if first_route:
        _text(pdf, 301.4, 338.1, f"FIRST ALTN ROUTE : {first_route}")
    if second_route:
        _text(pdf, 301.4, 352.2, f"SECOND ALTN ROUTE : {second_route}")

    # ---- ENDURANCE ----
    _text(pdf, 161.2, 335.1 + shift, "---------")
    _text(pdf, 192.3, 335.1 + shift, "-------------")

    _text(pdf, 90.1, 349.2 + shift, "ENDURANCE")
    _text(pdf, 150.9, 349.2 + shift, ":")
    _text(pdf, 161.2, 349.2 + shift, fuel.get("enduranceTime"))
    _text_right(pdf, 233.0, 349.2 + shift, _lbs(fuel.get("ramp")))

    # ---- DIFFERENT LEVEL CALCULATION / ACTUALS ----
    _text(
        pdf,
        51.0,
        367.8 + shift,
        "- - - - - DIFFERENT LEVEL CALCULATION - - - - - - - - - - - - - - - - - - - "
        "- - - - ACTUALS - - - - - - - - - - - - - - - - - - - -",
    )

    _text(pdf, 66.2, 386.5 + shift, "FL")
    _text(pdf, 103.6, 386.5 + shift, "WC")
    _text(pdf, 141.9, 386.5 + shift, "TIME")
    _text(pdf, 196.8, 386.5 + shift, "TRIP")

    level_y = 400.6 + shift
    for row in level_calcs[:5]:
        fl_disp = _space_fl(row.get("fl"))
        # Below the transition altitude a level-calc row is a raw altitude
        # ("3000 ft"), not a flight level - only bare numbers get an "FL "
        # prefix added, not values that already carry their own unit.
        if fl_disp and not fl_disp.upper().startswith("FL") and "ft" not in fl_disp.lower():
            fl_disp = f"FL {fl_disp}"

        _text(pdf, 58.0, level_y, fl_disp)
        _text(pdf, 105.5, level_y, row.get("wc"))
        _text(pdf, 141.9, level_y, find_value(row, "timeAll") or value(row.get("time")))
        _text_right(pdf, 223.9, level_y, _lbs(row.get("trip")))
        level_y += PLAN_ROW_STEP

    # The reference rules these with underscore characters, not drawn lines.
    actual_rows = [
        ("CHOCKS OFF", "LANDING", 393.2),
        ("CHOCKS ON", "AIRBORNE", 414.1),
        ("BLOCK TIME", "FLT TIME", 435.0),
        ("BLOCK FUEL", "FIC-ADC", 455.9),
    ]

    for left_label, right_label, y in actual_rows:
        _text_right(pdf, 321.4, y + shift, left_label)
        _text(pdf, 324.2, y + shift, ": _________")

        _text_right(pdf, 472.0, y + shift, right_label)
        _text(pdf, 474.9, y + shift, ": _________")

    # ---- hand-fill briefing blocks ----
    briefing_rows = [
        ("ATC CLEARANCE", 135.2, 476.5, operational.get("departureClearance")),
        ("DEP ATIS", 98.7, 519.9, operational.get("departureAtis")),
        ("ARR ATIS", 100.2, 563.3, operational.get("arrivalAtis")),
        ("DEST ALTN ATIS", 131.8, 606.7, operational.get("destAltnAtis")),
    ]

    for label, colon_x, y, entered in briefing_rows:
        _text(pdf, 48.3, y + shift, label)
        _text(pdf, colon_x, y + shift, ":")
        _text(pdf, colon_x + 9, y + shift, entered)

    # ---- V speeds ----
    v_speeds = data.get("vSpeeds", {}) or {}
    v_layout = [
        ("V1:", "v1", 48.3, 65.3),
        ("VR:", "vr", 138.6, 157.3),
        ("V2:", "v2", 230.6, 247.6),
        ("VFTO:", "vfto", 321.0, 351.0),
        ("VREF:", "vref", 424.4, 453.9),
    ]

    for label, key, label_x, rule_x in v_layout:
        # The reference drops the last rule a point and a half below its
        # neighbours; kept so the row matches line for line.
        rule_y = (654.6 if label == "VREF:" else 653.1) + shift
        _text(pdf, label_x, 653.1 + shift, label)
        _text(pdf, rule_x, rule_y, "_______________")
        _text(pdf, rule_x + 6, rule_y - 1.5, v_speeds.get(key))

    # ---- certification footer ----
    pdf.setLineWidth(1.5)
    pdf.line(46.0, PAGE_H - (667.3 + shift), 549.3, PAGE_H - (667.3 + shift))

    certification = [
        "I certify that all my licenses, ratings etc are current / valid and I am legally/",
        "medically fit for operating flight.",
    ]

    cert_y = 691.6 + shift
    for cert_line in certification:
        _text_center(pdf, 298.0, cert_y, cert_line, size=SIZE_CERT)
        cert_y += 10.7

    # The signature sits near the frame's foot and barely moves with the
    # rest - the reference shifts it by under 3pt for a second alternate.
    _text_right(pdf, 547.4, 761.3 + (2.8 if show_alternate2 else 0.0), "(PILOT/COPILOT SIGNATURE)")


# --------------------------------------------------
# NAVLOG TABLE (PAGES 2+)
# --------------------------------------------------
# 12 columns with stacked pairs, the same column model MLOVE uses, at the
# widths measured off this template's own reference.

COLUMN_X = [
    34.8, 149.7, 181.2, 219.3, 270.9, 296.3, 327.8, 364.3, 404.2, 432.2,
    463.7, 499.0, 560.5,
]

# (top group label, first line, second line, first key, second key)
COLUMNS = [
    ("",        "WAYPOINT", "AIRWAY", "waypoint",           "airway"),
    ("",        "HDG",      "CRS",    "heading",            "course"),
    ("",        "FL",       "",       "flightLevel",        None),
    ("WIND",    "DIR/SPD",  "CMP",    "windDirectionSpeed", "windComponent"),
    ("",        "ISA",      "",       "isa",                None),
    ("SPD\nKT", "TAS",      "GS",     "tas",                "gs"),
    ("DIST\nNM", "LEG",     "REM",    "legDistance",        "remainingDistance"),
    ("FUEL\nLB", "USED",    "REM",    "fuelUsed",           "fuelRemaining"),
    ("TIME",    "ETE",      "",       "ete",                None),
    ("TIME",    "LEG",      "REM",    "legTime",            "remainingTime"),
    ("",        "ETA",      "ATA",    "eta",                "ata"),
    ("",        "ACTUAL",   "FUEL",   "actualFuel",         None),
]

TABLE_TOP = 36.3
HEADER_TOP_HEIGHT = 33.5
HEADER_BOTTOM_HEIGHT = 33.6
ROW_HEIGHT = 33.65
ROW_LINE_STEP = 11.1
TABLE_BOTTOM_LIMIT = 780.0
BANNER_HEIGHT = 45.6


def _draw_table_header(pdf, y):
    top_bottom = y + HEADER_TOP_HEIGHT
    bottom_bottom = top_bottom + HEADER_BOTTOM_HEIGHT

    for line_y in (y, top_bottom, bottom_bottom):
        _hline(pdf, COLUMN_X[0], COLUMN_X[-1], line_y)
    for x in COLUMN_X:
        _vline(pdf, x, y, bottom_bottom)

    # Group labels, centred over their span. "TIME" covers ETE and the
    # LEG/REM time pair; the rest sit over a single (stacked) column.
    index = 0
    while index < len(COLUMNS):
        group = COLUMNS[index][0]
        if not group:
            index += 1
            continue

        last = index
        while last + 1 < len(COLUMNS) and COLUMNS[last + 1][0] == group:
            last += 1

        center = (COLUMN_X[index] + COLUMN_X[last + 1]) / 2
        parts = group.split("\n")
        if len(parts) == 1:
            _text_center(pdf, center, y + 20.1, parts[0])
        else:
            _text_center(pdf, center, y + 14.5, parts[0])
            _text_center(pdf, center, y + 25.6, parts[1])

        index = last + 1

    for column_index, (_, line1, line2, _, _) in enumerate(COLUMNS):
        left = COLUMN_X[column_index]
        center = (left + COLUMN_X[column_index + 1]) / 2

        if not line2:
            _text_center(pdf, center, top_bottom + 20.2, line1)
            continue

        if column_index == 0:
            # The waypoint heading is the one left-aligned label.
            _text(pdf, left + 2.6, top_bottom + 14.6, line1)
            _text(pdf, left + 2.6, top_bottom + 25.7, line2)
        else:
            _text_center(pdf, center, top_bottom + 14.6, line1)
            _text_center(pdf, center, top_bottom + 25.7, line2)

    return bottom_bottom


def _cell_lines(row, column):
    """The one or two lines a cell prints."""
    _, _, _, key1, key2 = column

    if key1 == "waypoint":
        waypoint = " ".join(
            part for part in
            [value(row.get("waypoint")), value(row.get("waypointDetail"))] if part
        )
        return [line for line in [waypoint, value(row.get("airway"))] if line] or [""]

    if key2 is None:
        return [value(row.get(key1))]

    return [value(row.get(key1)), value(row.get(key2))]


def _draw_row(pdf, row, y):
    height = ROW_HEIGHT

    _hline(pdf, COLUMN_X[0], COLUMN_X[-1], y + height)
    for x in COLUMN_X:
        _vline(pdf, x, y, y + height)

    for column_index, column in enumerate(COLUMNS):
        lines = _cell_lines(row, column)
        left = COLUMN_X[column_index]
        center = (left + COLUMN_X[column_index + 1]) / 2

        if len(lines) == 1:
            baselines = [y + 20.2]
        else:
            baselines = [y + 14.7, y + 25.8]

        for line_text, baseline in zip(lines, baselines):
            if column_index == 0:
                _text(pdf, left + 2.6, baseline, line_text)
            else:
                _text_center(pdf, center, baseline, line_text)

    return y + height


def _draw_banner(pdf, left_text, right_text, y):
    # A banner spans the whole table, so its border belongs on the frame's
    # own edges, not COLUMN_X[0]/[-1] - those are the navlog table's own
    # column grid and can sit off the frame by a point or so, which showed
    # up as a short stray vertical stroke since no ordinary row draws that
    # rightmost boundary itself.
    bottom = y + BANNER_HEIGHT
    _hline(pdf, FRAME_X0, FRAME_X1, bottom)
    _vline(pdf, FRAME_X0, y, bottom)
    _vline(pdf, FRAME_X1, y, bottom)

    _text(pdf, COLUMN_X[0] + 2.6, y + 26.1, left_text)
    _text(pdf, 196.0, y + 26.1, right_text)

    return bottom


def _start_blank_page(pdf, data):
    pdf.showPage()
    _page_header(pdf, data)
    _rect(pdf, FRAME_X0, FRAME_TOP, FRAME_X1, FRAME_BOTTOM)
    return TABLE_TOP


def _start_table_page(pdf, data):
    return _draw_table_header(pdf, _start_blank_page(pdf, data))


def draw_navlog_pages(pdf, data):
    y = _start_table_page(pdf, data)

    destination = value(data.get("page1", {}).get("flightInfo", {}).get("alternate1"))
    routes = data.get("routes", {})
    alternates = data.get("page1", {}).get("alternates", [])

    blocks = [(None, None, data.get("mainNavlog", []))]

    for position, (navlog_key, route_key) in enumerate([
        ("alternate1Navlog", "alternate1Route"),
        ("alternate2Navlog", "alternate2Route"),
    ]):
        rows = data.get(navlog_key, [])
        if not rows:
            continue

        airport = ""
        if len(alternates) > position:
            airport = value(alternates[position].get("airport"))

        banner_left = "Alternate route for " + ",".join(
            part for part in [destination.split(",")[0], airport] if part
        )
        route_text = value(routes.get(route_key)).replace("Route", "").strip()
        banner_right = f"Route {route_text}" if route_text else ""

        blocks.append((banner_left, banner_right, rows))

    for banner_left, banner_right, rows in blocks:
        if banner_left is not None:
            if y + BANNER_HEIGHT + ROW_HEIGHT > TABLE_BOTTOM_LIMIT:
                y = _start_table_page(pdf, data)
            y = _draw_banner(pdf, banner_left, banner_right, y)

        for row in rows:
            if y + ROW_HEIGHT > TABLE_BOTTOM_LIMIT:
                y = _start_table_page(pdf, data)
            y = _draw_row(pdf, row, y)

    return y


# --------------------------------------------------
# AIRPORT INFO
# --------------------------------------------------

AIRPORT_COLUMN_X = [
    34.8, 81.5, 135.5, 184.1, 226.8, 314.8, 352.6, 411.5, 459.2, 507.9, 560.5,
]

AIRPORT_HEADERS = [
    "", "Airport", "ETA", "ATIS", "TWR/CTAF", "CLR", "GND", "ELEV", "LONGEST RWY", "",
]

AIRPORT_ROW_HEIGHT = 22.4


def draw_airport_info(pdf, data, y):
    airports = data.get("airportInformation", [])
    if not airports:
        return y

    needed = 53.5 + AIRPORT_ROW_HEIGHT * (len(airports) + 1)
    if y + needed > TABLE_BOTTOM_LIMIT:
        y = _start_blank_page(pdf, data)

    y += 42.6
    _text(pdf, 34.8, y, "AIRPORT INFO")
    y += 10.9

    def _row(cells, header=False):
        nonlocal y
        bottom = y + AIRPORT_ROW_HEIGHT
        _hline(pdf, AIRPORT_COLUMN_X[0], AIRPORT_COLUMN_X[-1], y)
        _hline(pdf, AIRPORT_COLUMN_X[0], AIRPORT_COLUMN_X[-1], bottom)

        for index, x in enumerate(AIRPORT_COLUMN_X):
            # The runway number and length share one "LONGEST RWY" heading.
            if header and index == len(AIRPORT_COLUMN_X) - 2:
                continue
            _vline(pdf, x, y, bottom)

        for index, cell in enumerate(cells):
            if index >= len(AIRPORT_COLUMN_X) - 1:
                break
            if not value(cell):
                continue
            if header:
                _text(pdf, AIRPORT_COLUMN_X[index] + 2.7, y + 14.9, cell)
            else:
                center = (AIRPORT_COLUMN_X[index] + AIRPORT_COLUMN_X[index + 1]) / 2
                _text_center(pdf, center, y + 14.9, cell)

        y = bottom

    _row(AIRPORT_HEADERS, header=True)

    for airport in airports:
        _row([
            airport.get("type"),
            airport.get("airport"),
            airport.get("eta"),
            airport.get("atis"),
            airport.get("tower"),
            airport.get("clearance"),
            airport.get("ground"),
            airport.get("elevation"),
            airport.get("longestRunway") or airport.get("runway"),
            airport.get("runwayLength"),
        ])

    return y


# --------------------------------------------------
# FINAL PAGE (ATC FLIGHT PLAN + ENROUTE WINDS)
# --------------------------------------------------

# Flight-plan block leading: normal, onto the RMK/ remarks paragraph, and
# between the wrapped parts of one long line.
# The reference wraps its flight-plan lines a little short of the
# frame - measured off where its own RMK/ lines break.
FPL_WIDTH = 500.0
FPL_LEADING = 11.25
FPL_LEADING_REMARKS = 10.1
FPL_LEADING_WRAP = 9.85

WIND_IDENT_X = 48.3
WIND_FIRST_X = 120.4
WIND_TMP_OFFSET = 51.3
WIND_STEP = 90.15
WIND_ROW_HEIGHT = 14.138


def draw_final_page(pdf, data):
    atc = data.get("atcFlightPlan", {})

    pdf.showPage()
    _page_header(pdf, data)
    _rect(pdf, FRAME_X0, FRAME_TOP, FRAME_X1, FRAME_BOTTOM)

    title = value(atc.get("title")) or (
        f"ATC FLIGHT PLAN {find_value(atc, 'departure')} to {find_value(atc, 'destination')}"
    )
    _text_center(pdf, CENTER_X, 58.8, title)
    _text_center(pdf, CENTER_X, 69.9, ". " * 34)

    flight_plan_text = find_value(
        atc,
        "flightPlanText", "flight_plan_text", "fplText", "fpl_text",
        "flightPlan", "flight_plan", "text", "planText", "plan_text",
        "icaoText", "icao_text", "fpl",
    )

    # The reference leads its flight-plan lines at 11.25pt, but tightens
    # onto the RMK/ remarks paragraph and again for any line that has to
    # wrap - reproduced here because everything below (ENROUTE WINDS and
    # its rows) is positioned relative to where this block ends.
    y = 90.5
    for raw_line in str(flight_plan_text or "").split("\n"):
        raw_line = raw_line.rstrip()
        if not raw_line:
            y += FPL_LEADING
            continue

        if raw_line.upper().startswith("RMK"):
            y -= FPL_LEADING - FPL_LEADING_REMARKS

        parts = _wrap(raw_line, SIZE_FPL, FPL_WIDTH) or [""]
        for index, wrapped in enumerate(parts):
            _text(pdf, 46.0, y, wrapped, size=SIZE_FPL)
            y += FPL_LEADING_WRAP if index + 1 < len(parts) else FPL_LEADING

    # ---- enroute winds ----
    bands = data.get("enrouteWindBands", [])
    wind_rows = data.get("enrouteWinds", [])

    if isinstance(wind_rows, dict):
        bands = wind_rows.get("bands", bands)
        wind_rows = wind_rows.get("rows", [])

    if not wind_rows:
        _draw_report_footer(pdf)
        return

    band_count = max(len(bands), 1)
    step = WIND_STEP if band_count <= 5 else (540.0 - WIND_FIRST_X) / band_count

    winds_y = max(y + 22.0, 200.0)
    _text_center(pdf, CENTER_X, winds_y, "ENROUTE WINDS")

    header_y = winds_y + 28.1
    for index, band in enumerate(bands):
        band_x = WIND_FIRST_X + index * step
        _text(pdf, band_x + 1.0, header_y - 5.6, str(band).split("(")[0].strip())
        _text(pdf, band_x + 12.5, header_y + 5.6, "W/V")
        _text(pdf, band_x + WIND_TMP_OFFSET - 4.6, header_y, "TMP")

    _text(pdf, WIND_IDENT_X, header_y, "IDENT")

    row_y = header_y + 19.7
    for row in wind_rows:
        if row_y > FRAME_BOTTOM - 55:
            pdf.showPage()
            _page_header(pdf, data)
            _rect(pdf, FRAME_X0, FRAME_TOP, FRAME_X1, FRAME_BOTTOM)
            row_y = 70.0

        _text(pdf, WIND_IDENT_X, row_y, value(row.get("identifier")))

        for index, cell in enumerate(row.get("values", [])[:band_count]):
            band_x = WIND_FIRST_X + index * step

            # ForeFlight prefixes each cell with its wind component,
            # "(H22) 084/029", which this table does not print.
            wind = value(cell.get("wind"))
            if "\n" in wind:
                wind = wind.split("\n")[-1].strip()
            if wind.startswith("(") and ")" in wind:
                wind = wind.split(")", 1)[-1].strip()

            _text(pdf, band_x, row_y, wind)
            _text(pdf, band_x + WIND_TMP_OFFSET, row_y, value(cell.get("isa")))

        row_y += WIND_ROW_HEIGHT

    _draw_report_footer(pdf)


def _draw_report_footer(pdf):
    pdf.setFont("Courier-Bold", SIZE)
    pdf.drawCentredString(
        298.0,
        PAGE_H - 773.3,
        "**************  END OF THE REPORT  **************",
    )

    computed_date = datetime.now().strftime("%d-%m-%Y")
    computed_time = datetime.now().strftime("%H:%M:%S")

    _text(pdf, 37.0, 802.6, f"COMPUTED DATE : {computed_date}")
    _text_right(pdf, 558.5, 802.6, f"TIME : {computed_time} UTC")


# --------------------------------------------------
# GENERATE PDF ENTRYPOINT (INDO PACIFIC 1)
# --------------------------------------------------


def generate_indopacific_pdf(navlog, alternates=1):
    """`alternates` selects which of the two sheets to print: 2 reserves
    the ALTN2 row whether or not a second alternate was uploaded."""
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)

    file_name = f"INDOPACIFIC{alternates}_{int(datetime.now().timestamp() * 1000)}.pdf"
    absolute_path = os.path.join(OUTPUT_DIRECTORY, file_name)
    relative_path = os.path.join("generated", file_name)

    pdf = canvas.Canvas(absolute_path, pagesize=A4)

    draw_page_one(pdf, navlog, force_alternate2=(alternates >= 2))
    y = draw_navlog_pages(pdf, navlog)
    draw_airport_info(pdf, navlog, y)
    draw_final_page(pdf, navlog)

    pdf.save()

    return relative_path
