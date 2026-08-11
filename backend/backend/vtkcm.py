import os
import re
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from common import OUTPUT_DIRECTORY, find_value, value

# --------------------------------------------------
# VTKCM TEMPLATE
# --------------------------------------------------
# Measured off the operator's own reference document ("NAVLOG OF VTKCM")
# with a text/rect bbox extraction, so the layout copies that PDF rather
# than re-interpreting it.
#
# Page 1 is the PLAN TIME & FUEL family (VTCSP / INDO PACIFIC), on A4, but
# with its own row set:
#   * no TOP CLIMB TEMP - the COMPUTED FUEL block is three rows, with WIND
#     moved up beside MAX. TRIP FUEL
#   * an ADDITIONAL row between FINAL RESERVE and ALTN1
#   * DISCRETIONARY in place of XTRA (extra fuel less the additional)
#   * ACTUALS closes with FIC / ADC rather than BLOCK FUEL / FIC-ADC
#   * V-speeds are V1 / VR / V2 / VREF - no VFTO
#
# Page 2 is the flat 18-column navlog (one column per figure, not stacked
# pairs), whose TIME group carries LEG and a remaining-time column the
# reference heads "ETE", then AIRPORT INFO - which on this template lists
# the alternates as well as the departure and destination.

PAGE_W, PAGE_H = A4

FONT = "Times-Roman"

SIZE = 9.4
SIZE_CRUISE = 7.5
SIZE_CERT = 9.0
SIZE_TABLE = 8.2

FRAME_X0 = 34.4
FRAME_X1 = 560.9
FRAME_TOP = 34.4
FRAME_BOTTOM = 806.0

CENTER_X = (FRAME_X0 + FRAME_X1) / 2
BANNER_CENTER_X = 282.4

PLAN_ROW_STEP = 14.13

AIRPORT_NAME_LOOKUP = {
    "VOHY": "BEGUMPET",
    "VOHB": "HUBLI",
    "VOGA": "GOA",
    "VOSH": "SHOLAPUR",
    "VABB": "MUMBAI",
    "VOMM": "CHENNAI",
    "VOBL": "BENGALURU",
    "VOBG": "BENGALURU",
    "VIDP": "DELHI",
    "VECC": "KOLKATA",
    "VAAH": "AHMEDABAD",
    "VAHS": "HIRASAR",
    "VABO": "VADODARA",
    "VOHS": "HYDERABAD",
    "VOTP": "TIRUPATI",
    "VILK": "LUCKNOW",
    "VEBS": "BHUBANESWAR",
    "VERC": "RANCHI",
    "VOCI": "KOCHI",
    "VOTV": "TRIVANDRUM",
    "VANP": "NAGPUR",
    "VOMD": "MADURAI",
    "VEBN": "VARANASI",
    "VIJP": "JAIPUR",
    "VAPO": "PUNE",
    "VOCB": "COIMBATORE",
    "VEGY": "GAYA",
    "VEGT": "GUWAHATI",
    "VIAR": "AMRITSAR",
    "VOML": "MANGALORE",
    "VOVZ": "VISAKHAPATNAM",
    "VEPT": "PATNA",
    "VAID": "INDORE",
    "VABP": "BHOPAL",
    "VOBZ": "VIJAYAWADA",
    "VARK": "RAJKOT",
}


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
    match = re.search(r"@\s*FL\d+\s*-\s*(.+)$", value(profile_text), re.IGNORECASE)
    return match.group(1).strip().upper() if match else ""


def _navaid_city(rows, from_end=False):
    ordered = list(reversed(rows)) if from_end else list(rows)

    for row in ordered:
        detail = value(row.get("waypointDetail"))
        if not detail:
            continue
        word = detail.split()[0]
        if word.replace(".", "").isdigit():
            continue
        return word.upper()

    return ""


def _airport_display(code, rows, from_end=False):
    code = value(code)
    name = AIRPORT_NAME_LOOKUP.get(code.upper()) or _navaid_city(rows, from_end=from_end)
    return (code, f"- {name}" if name else "-")


def _page_header(pdf, data):
    header = data.get("page1", {}).get("header", {})
    flight = data.get("page1", {}).get("flightInfo", {})

    route_title = value(header.get("routeTitle"))
    registration = value(header.get("registration") or flight.get("registration"))

    _text_right(pdf, 554.9, 27.9, f"{route_title}     {registration}".strip())


# --------------------------------------------------
# PAGE ONE
# --------------------------------------------------


def draw_page_one(pdf, data):
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
    main_navlog = data.get("mainNavlog", [])

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
    dep_code, dep_name = _airport_display(flight.get("departure"), main_navlog)
    dest_code, dest_name = _airport_display(
        flight.get("destination"), main_navlog, from_end=True
    )

    _text(pdf, 50.5, 100.1, "DEP")
    _text(pdf, 77.0, 100.1, ":")
    _text(pdf, 82.6, 100.1, dep_code)
    _text(pdf, 112.6, 100.1, dep_name)

    _text(pdf, 50.5, 114.2, "DEST")
    _text(pdf, 77.0, 114.2, ":")
    _text(pdf, 82.6, 114.2, dest_code)
    _text(pdf, 112.6, 114.2, dest_name)

    _text(pdf, 251.2, 92.3, "DIST")
    _text(pdf, 300.4, 92.3, ":")
    _text(pdf, 308.0, 92.3, _nm(time_info.get("plannedRouteDistance")))

    _text(pdf, 251.2, 114.2, "CRUISE")
    _text(pdf, 300.4, 114.2, ":")

    cruise_lines = _wrap(value(misc.get("plannedProfile")).upper(), SIZE_CRUISE, 140.0)
    cruise_y = 104.7
    for cruise_line in cruise_lines[:4]:
        _text(pdf, 308.0, cruise_y, cruise_line, size=SIZE_CRUISE)
        cruise_y += 8.9

    _text(pdf, 451.9, 100.1, "TRACK")
    _text(pdf, 486.7, 100.1, ":")
    _text(pdf, 492.3, 100.1, _degrees(time_info.get("track")))

    _text(pdf, 451.9, 114.2, "PAX")
    _text(pdf, 486.7, 114.2, ":")
    _text(pdf, 492.3, 114.2, weight.get("pax"))

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
    _text(pdf, 48.3, 141.4, f"MAIN ROUTE : {main_route}".strip())

    _text(pdf, 48.3, 158.6, f"PIC : {_rank(flight.get('pic'))}".rstrip())
    _text(pdf, 299.1, 158.6, f"FO : {_rank(flight.get('fo'))}".rstrip())

    # ---- COMPUTED FUEL block (three rows - no TOP CLIMB TEMP here) ----
    landing_fuel = find_value(fuel, "landingReported") or value(fuel.get("landing"))

    fuel_pairs = [
        ("COMPUTED FUEL", _lbs(fuel.get("ramp")), "TAKE OFF FUEL", _lbs(fuel.get("takeoff"))),
        ("MIN. TRIP FUEL", _lbs(fuel.get("minTripFuel")), "LANDING FUEL", _lbs(landing_fuel)),
        ("MAX. TRIP FUEL", _lbs(fuel.get("maxTripFuel")), None, None),
    ]

    for (left_label, left_val, right_label, right_val), y in zip(
        fuel_pairs, [179.5, 193.6, 207.7]
    ):
        _text(pdf, 50.5, y, left_label)
        _text(pdf, 130.9, y, ":")
        _text_right(pdf, 179.4, y, left_val)

        if right_label:
            _text(pdf, 301.4, y, right_label)
            _text(pdf, 374.7, y, ":")
            _text_right(pdf, 473.5, y, right_val)

    _text(pdf, 301.4, 207.7, "WIND")
    _text(pdf, 374.7, 207.7, ":")
    _text(pdf, 385.0, 207.7, value(time_info.get("averageWinds")).upper())

    # ---- PLAN TIME & FUEL / PLAN WT ----
    _text(
        pdf,
        51.0,
        226.4,
        "- - - - - - - - PLAN TIME & FUEL - - - - - - - - - - - - - - - - - - - - - - "
        "- - - - - - PLAN WT (in LBS) - - - - - - - - - - - - -",
    )

    alt1 = alternates[0] if len(alternates) > 0 else {}

    plan_rows = [
        ("TRIP", find_value(fuel, "tripTime", "trip_time"), fuel.get("trip")),
        ("TAXI", find_value(fuel, "taxiTime", "taxi_time"), fuel.get("taxi")),
        ("CONTINGENCY", find_value(fuel, "contingencyTime", "contingency_time"),
         fuel.get("contingency")),
        ("FINAL RESERVE", find_value(fuel, "finalReserveTime", "final_reserve_time"),
         fuel.get("finalReserve")),
        ("ADDITIONAL", find_value(fuel, "additionalTime", "additional_time"),
         fuel.get("additional")),
        ("ALTN1", find_value(fuel, "alternateTime", "alternate_time"), fuel.get("alternate")),
        ("DISCRETIONARY", find_value(fuel, "discretionaryTime", "discretionary_time"),
         fuel.get("discretionary")),
    ]

    plan_y = 245.0
    for label, time_val, fuel_val in plan_rows:
        _text(pdf, 50.5, plan_y, label)
        _text(pdf, 131.4, plan_y, ":")
        _text(pdf, 141.7, plan_y, time_val)
        _text_right(pdf, 213.2, plan_y, _lbs(fuel_val))
        plan_y += PLAN_ROW_STEP

    weight_rows = [
        ("BASIC WT", weight.get("basicOperatingWeight")),
        ("LOAD", weight.get("load")),
        ("ZERO FUEL", weight.get("zeroFuelWeight")),
        ("T.OFF WT", weight.get("takeoffWeight")),
        ("LAND WT", weight.get("estimatedLandingWeight")),
    ]

    weight_y = 245.0
    for label, weight_val in weight_rows:
        _text(pdf, 301.4, weight_y, label)
        _text(pdf, 362.8, weight_y, ":")
        _text_right(pdf, 420.7, weight_y, _lbs(weight_val))
        weight_y += PLAN_ROW_STEP

    alt1_dist = _nm(alt1.get("distance"))
    if alt1_dist:
        _text(pdf, 301.4, 318.7, f"ALTN : {alt1_dist}")

    min_divert = _lbs(fuel.get("minDivertFuel"))
    if min_divert:
        _text(pdf, 379.5, 318.7, f"MIN DIVERT FUEL: {min_divert}")

    routes = data.get("routes", {})
    first_route = value(routes.get("alternate1Route")).replace("Route", "").strip()
    second_route = value(routes.get("alternate2Route")).replace("Route", "").strip()

    if first_route:
        _text(pdf, 301.4, 332.8, f"FIRST ALTN ROUTE : {first_route}")
    if second_route:
        _text(pdf, 301.4, 347.0, f"SECOND ALTN ROUTE : {second_route}")

    # ---- ENDURANCE ----
    _text(pdf, 141.7, 344.0, "---------")
    _text(pdf, 172.8, 344.0, "-------------")

    _text(pdf, 70.6, 358.1, "ENDURANCE")
    _text(pdf, 131.4, 358.1, ":")
    _text(pdf, 141.7, 358.1, fuel.get("enduranceTime"))
    _text_right(pdf, 213.2, 358.1, _lbs(fuel.get("ramp")))

    # ---- DIFFERENT LEVEL CALCULATION / ACTUALS ----
    _text(
        pdf,
        51.0,
        376.7,
        "- - - - - DIFFERENT LEVEL CALCULATION - - - - - - - - - - - - - - - - - - - "
        "- - - - ACTUALS - - - - - - - - - - - - - - - - - - - -",
    )

    _text(pdf, 65.0, 395.4, "FL")
    _text(pdf, 100.4, 395.4, "WC")
    _text(pdf, 141.4, 395.4, "TIME")
    _text(pdf, 198.3, 395.4, "TRIP")

    level_y = 409.5
    for row in level_calcs[:5]:
        fl_disp = _space_fl(row.get("fl"))
        if fl_disp and not fl_disp.upper().startswith("FL"):
            fl_disp = f"FL {fl_disp}"

        _text(pdf, 56.8, level_y, fl_disp)
        _text(pdf, 102.2, level_y, row.get("wc"))
        _text(pdf, 138.7, level_y, find_value(row, "timeAll") or value(row.get("time")))
        _text_right(pdf, 225.1, level_y, _lbs(row.get("trip")))
        level_y += PLAN_ROW_STEP

    actual_rows = [
        ("CHOCKS OFF", "LANDING", 402.1),
        ("CHOCKS ON", "AIRBORNE", 423.0),
        ("BLOCK TIME", "FLT TIME", 443.9),
        ("FIC", "ADC", 464.8),
    ]

    for left_label, right_label, y in actual_rows:
        _text_right(pdf, 321.4, y, left_label)
        _text(pdf, 324.2, y, ": _________")

        _text_right(pdf, 472.0, y, right_label)
        _text(pdf, 474.9, y, ": _________")

    # ---- hand-fill briefing blocks ----
    briefing_rows = [
        ("ATC CLEARANCE", 135.2, 485.5, operational.get("departureClearance")),
        ("DEP ATIS", 98.7, 525.1, operational.get("departureAtis")),
        ("ARR ATIS", 100.2, 564.7, operational.get("arrivalAtis")),
        ("DEST ALTN ATIS", 131.8, 604.4, operational.get("destAltnAtis")),
    ]

    for label, colon_x, y, entered in briefing_rows:
        _text(pdf, 48.3, y, label)
        _text(pdf, colon_x, y, ":")
        _text(pdf, colon_x + 9, y, entered)

    # ---- V speeds (no VFTO on this template) ----
    v_speeds = data.get("vSpeeds", {}) or {}
    v_layout = [
        ("V1:", "v1", 48.3, 65.3),
        ("VR:", "vr", 138.6, 157.3),
        ("V2:", "v2", 230.6, 247.6),
        ("VREF:", "vref", 321.0, 350.5),
    ]

    for label, key, label_x, rule_x in v_layout:
        # The reference drops the last rule a point and a half below its
        # neighbours; kept so the row matches line for line.
        rule_y = 648.5 if label == "VREF:" else 647.0
        _text(pdf, label_x, 647.0, label)
        _text(pdf, rule_x, rule_y, "_______________")
        _text(pdf, rule_x + 6, rule_y - 1.5, v_speeds.get(key))

    # ---- certification footer ----
    pdf.setLineWidth(1.4)
    pdf.line(46.0, PAGE_H - 660.9, 549.3, PAGE_H - 660.9)

    certification = [
        "I certify that all my licenses, ratings etc are current / valid and I am legally/ medically fit for operating flight. I meet the qualification",
        "requirements to operate to concerned airfields as per category/routes indicated per OM D. I have read and understood the operations",
        "manual, OPS supplements, emails, NOTAMS and required compliance. (cars, circulars, aips, etc).BA test complied as per car section 5",
        "series F part 3.",
    ]

    cert_y = 674.3
    for cert_line in certification:
        _text_center(pdf, 297.6, cert_y, cert_line, size=SIZE_CERT)
        cert_y += 10.7

    _text(pdf, 416.6, 742.8, "(PILOT/COPILOT SIGNATURE)")


# --------------------------------------------------
# NAVLOG TABLE (PAGES 2+)
# --------------------------------------------------
# 18 flat columns. The TIME group heads only the LEG column; the column
# beside it, headed "ETE", carries the remaining-time figure.

COLUMN_X = [
    34.8, 116.5, 157.6, 181.1, 202.2, 230.7, 253.8, 292.3, 311.2, 332.3,
    350.3, 371.8, 395.4, 422.9, 446.7, 472.8, 493.6, 517.8, 560.5,
]

COLUMN_KEYS = [
    "waypoint", "airway", "heading", "course", "flightLevel", "windComponent",
    "windDirectionSpeed", "isa", "tas", "gs", "legDistance", "remainingDistance",
    "fuelUsed", "fuelRemaining", "legTime", "remainingTime", "ata", "actualFuel",
]

COLUMN_LABELS = [
    "WAYPOINT", "AIRWAY", "HDG", "CRS", "ALT", "CMP", "DIR/SPD", "ISA", "TAS",
    "GS", "LEG", "REM", "USED", "REM", "LEG", "ETE",
]

# (label, first column index, last column index) for the shallow top row.
COLUMN_GROUPS = [
    ("WIND", 5, 6),
    ("SPD KT", 8, 9),
    ("DIST NM", 10, 11),
    ("FUEL LB", 12, 13),
    ("TIME", 14, 14),
]

TABLE_TOP = 36.3
HEADER_TOP_HEIGHT = 21.0
HEADER_BOTTOM_HEIGHT = 30.9
ROW_HEIGHT = 21.0
ROW_TALL_HEIGHT = 30.9
TABLE_BOTTOM_LIMIT = 780.0
BANNER_HEIGHT = 45.6


def _draw_table_header(pdf, y):
    top_bottom = y + HEADER_TOP_HEIGHT
    bottom_bottom = top_bottom + HEADER_BOTTOM_HEIGHT

    for line_y in (y, top_bottom, bottom_bottom):
        _hline(pdf, COLUMN_X[0], COLUMN_X[-1], line_y)

    # Every boundary is ruled through both header rows on this template,
    # including the ones inside a group's span.
    for x in COLUMN_X:
        _vline(pdf, x, y, bottom_bottom)

    for label, start, end in COLUMN_GROUPS:
        center = (COLUMN_X[start] + COLUMN_X[end + 1]) / 2
        _text_center(pdf, center, y + 13.4, label, size=SIZE_TABLE)

    for index, label in enumerate(COLUMN_LABELS):
        center = (COLUMN_X[index] + COLUMN_X[index + 1]) / 2
        _text_center(pdf, center, top_bottom + 18.4, label, size=SIZE_TABLE)

    for index, (line1, line2) in enumerate([("ETA", "ATA"), ("ACTUAL", "FUEL")]):
        column = len(COLUMN_LABELS) + index
        center = (COLUMN_X[column] + COLUMN_X[column + 1]) / 2
        _text_center(pdf, center, y + 34.5, line1, size=SIZE_TABLE)
        _text_center(pdf, center, y + 44.3, line2, size=SIZE_TABLE)

    return bottom_bottom


def _waypoint_lines(row):
    waypoint = " ".join(
        part for part in
        [value(row.get("waypoint")), value(row.get("waypointDetail"))] if part
    )
    return _wrap(waypoint, SIZE_TABLE, COLUMN_X[1] - COLUMN_X[0] - 5) or [""]


def _row_height(row):
    return ROW_HEIGHT if len(_waypoint_lines(row)) <= 1 else ROW_TALL_HEIGHT


def _draw_row(pdf, row, y):
    lines = _waypoint_lines(row)
    height = _row_height(row)

    _hline(pdf, COLUMN_X[0], COLUMN_X[-1], y + height)
    for x in COLUMN_X:
        _vline(pdf, x, y, y + height)

    if len(lines) <= 1:
        _text(pdf, COLUMN_X[0] + 2.6, y + 13.4, lines[0], size=SIZE_TABLE)
        value_baseline = y + 13.4
    else:
        _text(pdf, COLUMN_X[0] + 2.6, y + 13.5, lines[0], size=SIZE_TABLE)
        _text(pdf, COLUMN_X[0] + 2.6, y + 23.3, lines[1], size=SIZE_TABLE)
        value_baseline = y + 18.4

    for index, key in enumerate(COLUMN_KEYS):
        if index == 0:
            continue
        center = (COLUMN_X[index] + COLUMN_X[index + 1]) / 2
        _text_center(pdf, center, value_baseline, value(row.get(key)), size=SIZE_TABLE)

    return y + height


def _draw_banner(pdf, left_text, right_text, y):
    bottom = y + BANNER_HEIGHT
    _hline(pdf, COLUMN_X[0], COLUMN_X[-1], bottom)
    _vline(pdf, COLUMN_X[0], y, bottom)
    _vline(pdf, COLUMN_X[-1], y, bottom)

    _text(pdf, COLUMN_X[0] + 2.6, y + 26.1, left_text)
    _text(pdf, 179.9, y + 26.1, right_text)

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
            if y + _row_height(row) > TABLE_BOTTOM_LIMIT:
                y = _start_table_page(pdf, data)
            y = _draw_row(pdf, row, y)

    return y


# --------------------------------------------------
# AIRPORT INFO
# --------------------------------------------------

AIRPORT_COLUMN_X = [
    34.8, 90.2, 142.2, 189.1, 245.7, 330.0, 366.7, 415.8, 461.8, 509.2, 560.5,
]

AIRPORT_HEADERS = [
    "", "Airport", "ETA", "ATIS", "TWR/CTAF", "CLR", "GND", "ELEV", "LONGEST RWY", "",
]

AIRPORT_ROW_HEIGHT = 21.0


def draw_airport_info(pdf, data, y):
    airports = data.get("airportInformation", [])
    if not airports:
        return y

    needed = 53.9 + AIRPORT_ROW_HEIGHT * (len(airports) + 1)
    if y + needed > TABLE_BOTTOM_LIMIT:
        y = _start_blank_page(pdf, data)

    y += 42.6
    _text(pdf, 34.8, y, "AIRPORT INFO")
    y += 11.3

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
                _text(pdf, AIRPORT_COLUMN_X[index] + 2.6, y + 13.4, cell, size=SIZE_TABLE)
            else:
                center = (AIRPORT_COLUMN_X[index] + AIRPORT_COLUMN_X[index + 1]) / 2
                _text_center(pdf, center, y + 13.5, cell, size=SIZE_TABLE)

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
WIND_FIRST_X = 124.2
WIND_TMP_RIGHT = 189.4
WIND_STEP = 89.28
WIND_ROW_HEIGHT = 14.13


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

        parts = _wrap(raw_line, SIZE_TABLE, FPL_WIDTH) or [""]
        for index, wrapped in enumerate(parts):
            _text(pdf, 46.0, y, wrapped, size=SIZE_TABLE)
            y += FPL_LEADING_WRAP if index + 1 < len(parts) else FPL_LEADING

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

    winds_y = max(y + 21.0, 200.0)
    _text_center(pdf, CENTER_X, winds_y, "ENROUTE WINDS")

    header_y = winds_y + 28.1
    for index, band in enumerate(bands):
        band_x = WIND_FIRST_X + index * step
        _text(pdf, band_x + 1.1, header_y - 5.6, str(band).split("(")[0].strip())
        _text(pdf, band_x + 12.5, header_y + 5.6, "W/V")
        _text_right(pdf, WIND_TMP_RIGHT + index * step, header_y, "TMP")

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

            wind = value(cell.get("wind"))
            if "\n" in wind:
                wind = wind.split("\n")[-1].strip()
            if wind.startswith("(") and ")" in wind:
                wind = wind.split(")", 1)[-1].strip()

            _text(pdf, band_x, row_y, wind)
            _text_right(pdf, WIND_TMP_RIGHT + index * step, row_y, value(cell.get("isa")))

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
    _text_right(pdf, 558.6, 802.6, f"TIME : {computed_time} UTC")


# --------------------------------------------------
# GENERATE PDF ENTRYPOINT (VTKCM)
# --------------------------------------------------


def generate_vtkcm_pdf(navlog):
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)

    file_name = f"VTKCM{int(datetime.now().timestamp() * 1000)}.pdf"
    absolute_path = os.path.join(OUTPUT_DIRECTORY, file_name)
    relative_path = os.path.join("generated", file_name)

    pdf = canvas.Canvas(absolute_path, pagesize=A4)

    draw_page_one(pdf, navlog)
    y = draw_navlog_pages(pdf, navlog)
    draw_airport_info(pdf, navlog, y)
    draw_final_page(pdf, navlog)

    pdf.save()

    return relative_path
