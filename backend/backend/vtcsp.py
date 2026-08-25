import os
import re
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from common import OUTPUT_DIRECTORY, find_value, value

# --------------------------------------------------
# VTCSP TEMPLATE
# --------------------------------------------------
# Every coordinate in this file was measured off VTCSP's own reference PDF
# ("NAVLOG VTCSP VABB 1415-VOMM") with a text/rect bbox extraction, so the
# layout is a direct copy of that document rather than a re-interpretation
# of it. VTCSP is US-Letter (612x792) - NOT A4 like MLOVE/VTVIK - and its
# page 1 is its own template: single-line banner, DEP/DIST/TRACK +
# DEST/CRUISE/PAX header block, COMPUTED FUEL pairs, PLAN TIME & FUEL /
# PLAN WT columns, DIFFERENT LEVEL CALCULATION / ACTUALS block, then the
# ATC CLEARANCE / ATIS / V-speed hand-fill lines and the certification
# footer.
#
# Nothing here draws with common.py's page-height-dependent helpers - this
# module keeps its own top-down drawing primitives so a Letter page can be
# rendered without disturbing the shared A4 page height other templates
# rely on.

PAGE_W, PAGE_H = letter

FONT = "Times-Roman"
FONT_BOLD = "Times-Bold"

# The reference renders its body text at an effective ~8.8pt Times.
SIZE = 8.8
SIZE_SMALL = 7.1
SIZE_CERT = 8.5

# Page 1's frame, and the (very slightly wider) frame the table pages use.
FRAME_X0 = 58.5
FRAME_X1 = 553.8
FRAME_TOP = 32.4
FRAME_BOTTOM = 758.2

TABLE_X0 = 58.1
TABLE_X1 = 556.3
TABLE_TOP = 32.9
TABLE_BOTTOM_LIMIT = 729.5
PAGE_FRAME_BOTTOM = 757.2

CENTER_X = (FRAME_X0 + FRAME_X1) / 2
BANNER_CENTER_X = 287.0

# Airport full names ForeFlight's export never carries. Anything not
# listed here falls back to the city name printed against the first (or
# last) navaid in the navlog - see _airport_name() - and finally to just
# the ICAO code.
AIRPORT_NAME_LOOKUP = {
    "VABB": "MUMBAI",
    "VOMM": "CHENNAI",
    "VOBL": "BENGALURU",
    "VOBG": "BENGALURU",
    "VIDP": "DELHI",
    "VECC": "KOLKATA",
    "VOHY": "BEGUMPET",
    "VOHS": "HYDERABAD",
    "VOTP": "TIRUPATI",
    "VILK": "LUCKNOW",
    "VEBS": "BHUBANESWAR",
    "VERC": "RANCHI",
    "VOCI": "KOCHI",
    "VOTV": "TRIVANDRUM",
    "VAAH": "AHMEDABAD",
    "VOGO": "GOA",
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
    "VABO": "VADODARA",
    "VAID": "INDORE",
    "VABP": "BHOPAL",
    "VOTR": "TIRUCHIRAPPALLI",
    "VOBZ": "VIJAYAWADA",
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


def _hline(pdf, x0, x1, y, width=0.5):
    pdf.setLineWidth(width)
    pdf.line(x0, PAGE_H - y, x1, PAGE_H - y)


def _vline(pdf, x, y0, y1, width=0.5):
    pdf.setLineWidth(width)
    pdf.line(x, PAGE_H - y0, x, PAGE_H - y1)


def _rect(pdf, x0, y0, x1, y1, width=0.8):
    pdf.setLineWidth(width)
    pdf.rect(x0, PAGE_H - y1, x1 - x0, y1 - y0, stroke=1, fill=0)


def _wrap(content, size, max_width, font=FONT):
    """Greedy word wrap against real Times metrics."""
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
    """"FL450" -> "FL 450" - VTCSP's spacing for flight levels quoted in
    prose fields (TOP CLIMB TEMP, the level-calculation table)."""
    return re.sub(r"\bFL(\d)", r"FL \1", value(s))


def _degrees(v):
    v = value(v)
    if not v:
        return ""
    return v if v.upper().endswith("DEG") else f"{v} DEG"


def _rank(name):
    """PIC/FO print with their rank on VTCSP's reference. Only prefixes
    when the operator hasn't already typed a rank in."""
    name = value(name).upper()
    if not name:
        return ""
    if re.match(r"^(CAPT|CPT|CMDR|MR|MS|MRS|FO|F/O)\b", name):
        return name
    return f"CAPT {name}"


def _cruise_tail(profile_text):
    """MAIN ROUTE prints the cruise-profile tail (the part after
    "@ FLxxx - ") ahead of the ATC route, exactly as VTVIK does."""
    match = re.search(r"@\s*FL\d+\s*-\s*(.+)$", value(profile_text), re.IGNORECASE)
    return match.group(1).strip().upper() if match else ""


def _navaid_city(rows, from_end=False):
    """ForeFlight prints the nearest navaid's city against each waypoint
    ("MUMBAI 116.6"). The first such city on the route is the departure
    city and the last is the destination city, which is the only place an
    airport's full name appears anywhere in the export."""
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


def _airport_name(code, rows, from_end=False):
    code = value(code).upper()
    if code in AIRPORT_NAME_LOOKUP:
        return AIRPORT_NAME_LOOKUP[code]
    return _navaid_city(rows, from_end=from_end)


def _airport_display(code, rows, from_end=False):
    code = value(code)
    name = _airport_name(code, rows, from_end=from_end)
    return (code, f"- {name}" if name else "")


def _page_header(pdf, data):
    """The "VABB - VOMM   VTCSP" line that sits above the frame on every
    page."""
    header = data.get("page1", {}).get("header", {})
    flight = data.get("page1", {}).get("flightInfo", {})

    route_title = value(header.get("routeTitle"))
    registration = value(header.get("registration") or flight.get("registration"))

    # Two separately anchored fields rather than one padded string, so the
    # tail always lands in the same place however long the route title is.
    _text_right(pdf, 509.7, 28.0, route_title)
    _text_right(pdf, 548.7, 28.0, registration)


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
    # The reference centres this banner on x=287, a little left of the
    # frame's own centre - kept as measured so the page matches it.
    banner = re.sub(r"\s+", " ", banner).replace("() ", "").replace("(ETA ) ", "")
    _text_center(pdf, BANNER_CENTER_X, 67.6, banner)

    # ---- DEP / DEST + DIST / CRUISE + TRACK / PAX ----
    dep_code, dep_name = _airport_display(flight.get("departure"), main_navlog)
    dest_code, dest_name = _airport_display(
        flight.get("destination"), main_navlog, from_end=True
    )

    _text(pdf, 73.7, 96.6, "DEP")
    _text(pdf, 98.3, 96.6, ":")
    _text(pdf, 103.5, 96.6, dep_code)
    _text(pdf, 136.9, 96.6, dep_name)

    _text(pdf, 73.7, 110.2, "DEST")
    _text(pdf, 98.3, 110.2, ":")
    _text(pdf, 103.5, 110.2, dest_code)
    _text(pdf, 137.1, 110.2, dest_name)

    _text(pdf, 262.3, 87.3, "DIST")
    _text(pdf, 310.1, 87.3, ":")
    _text(pdf, 317.3, 87.3, _nm(time_info.get("plannedRouteDistance")))

    _text(pdf, 262.3, 110.2, "CRUISE")
    _text(pdf, 310.0, 110.2, ":")

    # The cruise profile is the one long free-text field on this page; it
    # wraps into the gap between the CRUISE and TRACK/PAX columns.
    cruise_lines = _wrap(value(misc.get("plannedProfile")).upper(), SIZE_SMALL, 128.0)
    cruise_y = 99.0
    for cruise_line in cruise_lines[:4]:
        _text(pdf, 317.4, cruise_y, cruise_line, size=SIZE_SMALL)
        cruise_y += 8.9

    _text(pdf, 451.3, 94.7, "TRACK")
    _text(pdf, 480.0, 94.7, ":")
    _text(pdf, 486.0, 94.7, _degrees(time_info.get("track")))

    _text(pdf, 451.3, 108.0, "PAX")
    _text(pdf, 484.0, 108.0, ":")
    _text(pdf, 489.5, 108.0, weight.get("pax"))

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
    _text(pdf, 71.6, 133.7, f"MAIN ROUTE : {main_route}".strip())

    _text(pdf, 71.6, 149.8, f"PIC : {_rank(flight.get('pic'))}".rstrip())
    _text(pdf, 307.7, 149.8, f"FO : {_rank(flight.get('fo'))}".rstrip())

    # ---- COMPUTED FUEL block ----
    # BLOCK FUEL here is ForeFlight's "Flight Fuel" (taxi + trip), not the
    # ramp figure - COMPUTED FUEL above it is what actually goes on board.
    # LANDING FUEL prefers ForeFlight's own published figure over the
    # takeoff-minus-trip subtraction, which can differ by a pound or two.
    landing_fuel = find_value(fuel, "landingReported") or value(fuel.get("landing"))

    fuel_pairs = [
        ("COMPUTED FUEL", _lbs(fuel.get("ramp")), "BLOCK FUEL", _lbs(fuel.get("flight"))),
        ("MIN. TRIP FUEL", _lbs(fuel.get("minTripFuel")), "TAKE OFF FUEL", _lbs(fuel.get("takeoff"))),
        ("MAX. TRIP FUEL", _lbs(fuel.get("maxTripFuel")), "LANDING FUEL", _lbs(landing_fuel)),
    ]

    for (left_label, left_val, right_label, right_val), y in zip(
        fuel_pairs, [169.3, 182.7, 196.0]
    ):
        _text(pdf, 73.8, y, left_label)
        _text(pdf, 150.3, y, ":")
        _text_right(pdf, 227.9, y, left_val)

        _text(pdf, 309.8, y, right_label)
        _text(pdf, 379.5, y, ":")
        _text_right(pdf, 477.5, y, right_val)

    _text(pdf, 73.8, 210.5, "TOP CLIMB TEMP")
    _text(pdf, 150.3, 210.5, ":")
    _text(pdf, 157.0, 210.5, _space_fl(time_info.get("topClimbTemp")))

    _text(pdf, 309.6, 210.5, "WIND")
    _text(pdf, 379.5, 210.5, ":")
    _text(pdf, 390.8, 210.5, value(time_info.get("averageWinds")).upper())

    # ---- PLAN TIME & FUEL / PLAN WT ----
    _text(
        pdf,
        74.3,
        228.0,
        "- - - - - - - - PLAN TIME & FUEL - - - - - - - - - - - - - - - - - - - - "
        "- - - - - PLAN WT (in LBS ) - - - - - - - - - - - - - -",
    )

    alt1 = alternates[0] if len(alternates) > 0 else {}
    alt2 = alternates[1] if len(alternates) > 1 else {}

    def _alt_label(prefix, alternate):
        airport = value(alternate.get("airport"))
        return f"{prefix} - {airport}" if airport else prefix

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
        (
            _alt_label("ALTN1", alt1),
            find_value(fuel, "alternateTime", "alternate_time"),
            fuel.get("alternate"),
        ),
        (
            _alt_label("ALTN2", alt2),
            find_value(fuel, "alternate2Time", "alternate2_time"),
            fuel.get("alternate2Fuel"),
        ),
    ]

    plan_y = 246.9
    for label, time_val, fuel_val in plan_rows:
        _text(pdf, 74.3, plan_y, label)
        _text(pdf, 168.5, plan_y, ":")
        _text(pdf, 177.8, plan_y, time_val)
        _text_right(pdf, 244.7, plan_y, _lbs(fuel_val))
        plan_y += 13.3

    weight_rows = [
        ("BASIC WT", weight.get("basicOperatingWeight")),
        ("LOAD", weight.get("load")),
        ("ZERO FUEL", weight.get("zeroFuelWeight")),
        ("T.OFF WT", weight.get("takeoffWeight")),
        ("LAND WT", weight.get("estimatedLandingWeight")),
    ]

    weight_y = 245.3
    for label, weight_val in weight_rows:
        _text(pdf, 310.6, weight_y, label)
        _text(pdf, 366.2, weight_y, ":")
        _text_right(pdf, 421.7, weight_y, _lbs(weight_val))
        weight_y += 13.3

    alt1_dist = _nm(alt1.get("distance"))
    if alt1_dist:
        _text(pdf, 309.8, 314.8, f"ALTN : {alt1_dist}")

    min_divert = _lbs(fuel.get("minDivertFuel"))
    if min_divert:
        alt1_code = value(alt1.get("airport"))
        divert_label = f"MIN DIVERT FUEL ({alt1_code})" if alt1_code else "MIN DIVERT FUEL"
        _text(pdf, 309.8, 326.8, f"{divert_label}: {min_divert}")

    first_route = value(data.get("routes", {}).get("alternate1Route")).replace("Route", "").strip()
    second_route = value(data.get("routes", {}).get("alternate2Route")).replace("Route", "").strip()

    if first_route:
        _text(pdf, 309.8, 340.1, f"FIRST ALTN ROUTE : {first_route}")
    if second_route:
        _text(pdf, 309.8, 353.4, f"SECOND ALTN ROUTE : {second_route}")

    # ---- ENDURANCE (ruled off from the plan rows above it) ----
    _text(pdf, 178.0, 340.0, "- - - - - -    - - - - - - -")

    _text(pdf, 111.0, 353.3, "ENDURANCE")
    _text(pdf, 167.9, 353.3, ":")
    _text(pdf, 177.3, 353.3, fuel.get("enduranceTime"))
    _text_right(pdf, 244.6, 353.3, _lbs(fuel.get("ramp")))

    # ---- DIFFERENT LEVEL CALCULATION / ACTUALS ----
    _text(
        pdf,
        74.3,
        372.3,
        "- - - - - DIFFERENT LEVEL CALCULATION - - - - - - - - - - - - - - - - - - - "
        "- - - - ACTUALS - - - - - - - - - - - - - - - - - -",
    )

    _text(pdf, 88.3, 389.8, "FL")
    _text(pdf, 123.5, 389.8, "WC")
    _text(pdf, 159.7, 389.8, "TIME")
    _text(pdf, 211.3, 389.8, "TRIP")

    level_y = 403.3
    for row in level_calcs[:5]:
        fl_disp = _space_fl(row.get("fl"))
        # Below the transition altitude a level-calc row is a raw altitude
        # ("3000 ft"), not a flight level - only bare numbers get an "FL "
        # prefix added, not values that already carry their own unit.
        if fl_disp and not fl_disp.upper().startswith("FL") and "ft" not in fl_disp.lower():
            fl_disp = f"FL {fl_disp}"

        # The reference prints ForeFlight's delta as published, "(0:00)"
        # included, rather than blanking the zero the way the older
        # templates do.
        _text(pdf, 80.8, level_y, fl_disp)
        _text(pdf, 123.1, level_y, row.get("wc"))
        _text(pdf, 159.0, level_y, find_value(row, "timeAll") or value(row.get("time")))
        _text_right(pdf, 238.3, level_y, _lbs(row.get("trip")))
        level_y += 13.5

    actual_rows = [
        ("CHOCKS OFF :", "LANDING :", 396.1),
        ("CHOCKS ON :", "AIRBORNE :", 412.9),
        ("BLOCK TIME :", "FLT TIME :", 432.5),
        ("BLOCK FUEL :", "FIC-ADC :", 455.4),
    ]

    for left_label, right_label, y in actual_rows:
        _text_right(pdf, 333.7, y, left_label)
        _hline(pdf, 335.6, 377.5, y - 1.1)

        _text_right(pdf, 475.4, y, right_label)
        _hline(pdf, 477.2, 519.1, y - 1.1)

    # ---- hand-fill briefing blocks ----
    briefing_rows = [
        ("ATC CLEARANCE", 152.6, 474.5, operational.get("departureClearance")),
        ("DEP ATIS", 118.8, 515.3, operational.get("departureAtis")),
        ("ARR ATIS", 120.1, 556.1, operational.get("arrivalAtis")),
        ("DEST ALTN ATIS", 149.8, 596.9, operational.get("destAltnAtis")),
    ]

    for label, colon_x, y, entered in briefing_rows:
        _text(pdf, 71.6, y, label)
        _text(pdf, colon_x, y, ":")
        _text(pdf, colon_x + 8, y, entered)

    # ---- V speeds ----
    v_speeds = data.get("vSpeeds", {}) or {}
    v_layout = [
        ("V1:", "v1", 71.6, 87.2, 155.9),
        ("VR:", "vr", 155.9, 173.0, 242.3),
        ("V2:", "v2", 242.3, 257.9, 327.2),
        ("VFTO:", "vfto", 327.2, 355.2, 424.4),
        ("VREF:", "vref", 424.4, 451.9, 521.2),
    ]

    for label, key, label_x, rule_x0, rule_x1 in v_layout:
        _text(pdf, label_x, 640.6, label)
        _hline(pdf, rule_x0, rule_x1, 639.9)
        _text(pdf, rule_x0 + 4, 638.5, v_speeds.get(key))

    _hline(pdf, 71.6, 541.4, 650.0, width=0.8)

    # ---- certification footer ----
    certification = [
        "I certify that all my licenses, ratings etc are current / valid and I am legally/ medically fit for operating flight. I meet the qualification",
        "requirements to operate to concerned airfields as per category/routes indicated per OM D. I have read and understood the operations",
        "manual, OPS supplements, emails, NOTAMS and required compliance. (cars, circulars, aips, etc).BA test complied as per car section 5",
        "series F part 3.",
    ]

    cert_y = 666.6
    for cert_line in certification:
        _text_center(pdf, 306.4, cert_y, cert_line, size=SIZE_CERT)
        cert_y += 10.4

    _text_right(pdf, 541.4, 733.1, "(PILOT/COPILOT SIGNATURE)")


# --------------------------------------------------
# NAVLOG TABLE (PAGES 2+)
# --------------------------------------------------
# 19 flat columns, exactly as the reference: the group headers (WIND,
# SPD KT, DIST NM, FUEL LB, TIME) sit in a shallow top row spanning their
# member columns, ETA/ATA and ACT FUEL are two-line labels merged across
# both header rows, and every data column is single-line except WAYPOINT,
# which wraps.

COLUMN_X = [
    58.1, 131.4, 171.2, 193.8, 213.8, 240.8, 263.0, 300.2, 318.0, 338.2,
    354.8, 375.4, 397.9, 424.4, 447.0, 467.6, 490.2, 509.8, 531.4, 556.3,
]

COLUMN_KEYS = [
    "waypoint", "airway", "heading", "course", "flightLevel", "windComponent",
    "windDirectionSpeed", "isa", "tas", "gs", "legDistance", "remainingDistance",
    "fuelUsed", "fuelRemaining", "legTime", "remainingTime", "ete", "ata",
    "actualFuel",
]

COLUMN_LABELS = [
    "WAYPOINT", "AIRWAY", "HDG", "CRS", "ALT", "CMP", "DIR/SPD", "ISA", "TAS",
    "GS", "LEG", "REM", "USED", "REM", "LEG", "REM", "ETE",
]

# (label, first column index, last column index) for the shallow top row.
COLUMN_GROUPS = [
    ("WIND", 5, 6),
    ("SPD KT", 8, 9),
    ("DIST NM", 10, 11),
    ("FUEL LB", 12, 13),
    ("TIME", 14, 16),
]

HEADER_TOP_HEIGHT = 21.9
HEADER_BOTTOM_HEIGHT = 31.6
ROW_HEIGHT = 21.0
ROW_LINE_HEIGHT = 10.4
BANNER_HEIGHT = 43.0


def _draw_table_header(pdf, y):
    """Draws the two header rows and returns the y the first data row
    starts at."""
    top_bottom = y + HEADER_TOP_HEIGHT
    bottom_bottom = top_bottom + HEADER_BOTTOM_HEIGHT

    _hline(pdf, COLUMN_X[0], COLUMN_X[-1], y)
    _hline(pdf, COLUMN_X[0], COLUMN_X[-1], top_bottom)
    _hline(pdf, COLUMN_X[0], COLUMN_X[-1], bottom_bottom)

    grouped = set()
    for _, start, end in COLUMN_GROUPS:
        grouped.update(range(start + 1, end + 1))

    # Verticals: every column boundary through the bottom header row, but
    # only the group boundaries through the shallow top row.
    for index in range(len(COLUMN_X)):
        top_of_line = top_bottom if index in grouped else y
        # ETA/ATA and ACT FUEL merge across both rows, so their boundaries
        # always run the full height.
        if index >= len(COLUMN_LABELS):
            top_of_line = y
        _vline(pdf, COLUMN_X[index], top_of_line, bottom_bottom)

    for label, start, end in COLUMN_GROUPS:
        center = (COLUMN_X[start] + COLUMN_X[end + 1]) / 2
        _text_center(pdf, center, y + 16.2, label)

    for index, label in enumerate(COLUMN_LABELS):
        center = (COLUMN_X[index] + COLUMN_X[index + 1]) / 2
        _text_center(pdf, center, top_bottom + 20.6, label)

    for index, (line1, line2) in enumerate([("ETA", "ATA"), ("ACT", "FUEL")]):
        column = len(COLUMN_LABELS) + index
        center = (COLUMN_X[column] + COLUMN_X[column + 1]) / 2
        _text_center(pdf, center, y + 37.4, line1)
        _text_center(pdf, center, y + 47.7, line2)

    return bottom_bottom


def _row_lines(row):
    """Cell text per column, with the waypoint column wrapped."""
    waypoint = " ".join(
        part for part in [value(row.get("waypoint")), value(row.get("waypointDetail"))] if part
    )

    cells = []
    for index, key in enumerate(COLUMN_KEYS):
        if index == 0:
            width = COLUMN_X[1] - COLUMN_X[0] - 5
            cells.append(_wrap(waypoint, SIZE, width) or [""])
        else:
            cells.append([value(row.get(key))])

    return cells


def _draw_row(pdf, row, y):
    cells = _row_lines(row)
    line_count = max(len(cell) for cell in cells)
    height = ROW_HEIGHT + (line_count - 1) * ROW_LINE_HEIGHT

    _hline(pdf, COLUMN_X[0], COLUMN_X[-1], y + height)
    for x in COLUMN_X:
        _vline(pdf, x, y, y + height)

    for index, cell in enumerate(cells):
        first_baseline = (
            y + height / 2 - (len(cell) - 1) * ROW_LINE_HEIGHT / 2 + 4.6
        )
        for line_index, cell_line in enumerate(cell):
            baseline = first_baseline + line_index * ROW_LINE_HEIGHT
            if index == 0:
                _text(pdf, COLUMN_X[0] + 2.7, baseline, cell_line)
            else:
                center = (COLUMN_X[index] + COLUMN_X[index + 1]) / 2
                _text_center(pdf, center, baseline, cell_line)

    return y + height


def _draw_banner(pdf, left_text, right_text, y):
    # A banner spans the whole table, so its border belongs on the frame's
    # own edges, not COLUMN_X[0]/[-1] - those are the navlog table's own
    # column grid and sit off the frame (COLUMN_X[-1]=556.3 vs
    # FRAME_X1=553.8), which showed up as a short stray vertical stroke
    # since no ordinary row draws that rightmost boundary itself.
    bottom = y + BANNER_HEIGHT
    _hline(pdf, FRAME_X0, FRAME_X1, bottom)
    _vline(pdf, FRAME_X0, y, bottom)
    _vline(pdf, FRAME_X1, y, bottom)

    _text(pdf, COLUMN_X[0] + 2.7, y + 26.7, left_text)
    _text(pdf, 196.7, y + 26.7, right_text)

    return bottom


def _row_height(row):
    cells = _row_lines(row)
    line_count = max(len(cell) for cell in cells)
    return ROW_HEIGHT + (line_count - 1) * ROW_LINE_HEIGHT


def _start_blank_table_page(pdf, data):
    """A framed continuation page with no navlog header on it."""
    pdf.showPage()
    _page_header(pdf, data)
    _vline(pdf, TABLE_X0, TABLE_TOP, PAGE_FRAME_BOTTOM, width=0.8)
    _vline(pdf, TABLE_X1, TABLE_TOP, PAGE_FRAME_BOTTOM, width=0.8)
    _hline(pdf, TABLE_X0, TABLE_X1, PAGE_FRAME_BOTTOM, width=0.8)
    return TABLE_TOP


def _start_table_page(pdf, data):
    return _draw_table_header(pdf, _start_blank_table_page(pdf, data))


def draw_navlog_pages(pdf, data):
    """Draws every navlog block (main route, then each alternate behind
    its own banner), starting new pages as they fill. Returns the y the
    AIRPORT INFO table can continue from."""
    y = _start_table_page(pdf, data)

    destination = value(data.get("page1", {}).get("flightInfo", {}).get("alternate1"))
    routes = data.get("routes", {})

    blocks = [(None, None, data.get("mainNavlog", []))]

    for label_key, route_key in [
        ("alternate1Navlog", "alternate1Route"),
        ("alternate2Navlog", "alternate2Route"),
    ]:
        rows = data.get(label_key, [])
        if not rows:
            continue

        alternate_index = 0 if label_key == "alternate1Navlog" else 1
        alternates = data.get("page1", {}).get("alternates", [])
        airport = ""
        if len(alternates) > alternate_index:
            airport = value(alternates[alternate_index].get("airport"))

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
    58.1, 101.0, 154.2, 198.4, 242.6, 324.6, 376.7, 416.9, 460.2, 504.0, 555.8,
]

AIRPORT_HEADERS = [
    "", "Airport", "ETA", "ATIS", "TWR/CTAF", "CLR", "GND", "ELEV", "LONGEST RWY", "",
]

AIRPORT_ROW_HEIGHT = 21.0


def draw_airport_info(pdf, data, y):
    airports = data.get("airportInformation", [])
    if not airports:
        return y

    needed = 56.0 + AIRPORT_ROW_HEIGHT * (len(airports) + 1)
    if y + needed > TABLE_BOTTOM_LIMIT:
        # A continuation page carries only the airport table, so it gets a
        # frame without the navlog column header.
        y = _start_blank_table_page(pdf, data)

    y += 30.0
    _text(pdf, 58.3, y, "AIRPORT INFO")
    y += 25.9

    def _row(cells, header=False):
        nonlocal y
        bottom = y + AIRPORT_ROW_HEIGHT
        _hline(pdf, AIRPORT_COLUMN_X[0], AIRPORT_COLUMN_X[-1], y)
        _hline(pdf, AIRPORT_COLUMN_X[0], AIRPORT_COLUMN_X[-1], bottom)
        for index, x in enumerate(AIRPORT_COLUMN_X):
            # The runway number and length share one "LONGEST RWY" heading,
            # so their separator only exists in the data rows.
            if header and index == len(AIRPORT_COLUMN_X) - 2:
                continue
            _vline(pdf, x, y, bottom)

        for index, cell in enumerate(cells):
            if index >= len(AIRPORT_COLUMN_X) - 1:
                break
            if not value(cell):
                continue
            if header:
                _text(pdf, AIRPORT_COLUMN_X[index] + 2.4, y + 15.1, cell)
            else:
                center = (AIRPORT_COLUMN_X[index] + AIRPORT_COLUMN_X[index + 1]) / 2
                _text_center(pdf, center, y + 15.1, cell)

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

WIND_IDENT_X = 71.6
WIND_FIRST_X = 151.6
WIND_STEP = 82.3
WIND_ROW_HEIGHT = 13.3


def draw_final_page(pdf, data):
    atc = data.get("atcFlightPlan", {})

    pdf.showPage()
    _page_header(pdf, data)
    _rect(pdf, FRAME_X0, FRAME_TOP, FRAME_X1, FRAME_BOTTOM)

    title = value(atc.get("title")) or (
        f"ATC FLIGHT PLAN {find_value(atc, 'departure')} to {find_value(atc, 'destination')}"
    )
    _text_center(pdf, CENTER_X, 56.5, title)
    _text_center(pdf, CENTER_X, 66.9, "." * 34)

    flight_plan_text = find_value(
        atc,
        "flightPlanText", "flight_plan_text", "fplText", "fpl_text",
        "flightPlan", "flight_plan", "text", "planText", "plan_text",
        "icaoText", "icao_text", "fpl",
    )

    # The ICAO FPL is printed verbatim, one source line per printed line.
    # A long RMK/ line can run wider than the frame, so it is squeezed a
    # little rather than wrapped (the reference keeps each line whole);
    # only a line too long even at the floor size gets wrapped.
    from reportlab.pdfbase.pdfmetrics import stringWidth

    fpl_width = 548.7 - 69.5
    y = 87.6
    for raw_line in str(flight_plan_text or "").split("\n"):
        raw_line = raw_line.rstrip()
        if not raw_line:
            y += 10.8
            continue

        size = SIZE
        line_width = stringWidth(raw_line, FONT, size)
        if line_width > fpl_width:
            size = max(SIZE * fpl_width / line_width, 7.2)

        for wrapped in _wrap(raw_line, size, fpl_width) or [""]:
            _text(pdf, 69.5, y, wrapped, size=size)
            y += 10.8

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
    step = WIND_STEP if band_count <= 5 else (541.0 - WIND_FIRST_X) / band_count

    winds_y = max(y + 20.0, 193.5)
    _text_center(pdf, CENTER_X, winds_y, "ENROUTE WINDS")

    header_y = winds_y + 24.0
    for index, band in enumerate(bands):
        band_x = WIND_FIRST_X + index * step
        _text(pdf, band_x + 1.2, header_y - 5.4, str(band).split("(")[0].strip())
        _text(pdf, band_x + 11.8, header_y + 3.9, "W/V")
        _text(pdf, band_x + 42.9, header_y, "TMP")

    _text(pdf, WIND_IDENT_X, header_y, "IDENT")

    row_y = header_y + 18.6
    for row in wind_rows:
        if row_y > FRAME_BOTTOM - 45:
            pdf.showPage()
            _page_header(pdf, data)
            _rect(pdf, FRAME_X0, FRAME_TOP, FRAME_X1, FRAME_BOTTOM)
            row_y = 60.0

        _text(pdf, WIND_IDENT_X, row_y, value(row.get("identifier")))

        for index, cell in enumerate(row.get("values", [])[:band_count]):
            band_x = WIND_FIRST_X + index * step
            # ForeFlight prefixes each cell with its wind component -
            # "(H22) 084/029" - which the reference's table does not print
            # and which runs into the TMP column when left in.
            wind = value(cell.get("wind"))
            if "\n" in wind:
                wind = wind.split("\n")[-1].strip()
            if wind.startswith("(") and ")" in wind:
                wind = wind.split(")", 1)[-1].strip()

            _text(pdf, band_x, row_y, wind)
            _text_right(pdf, band_x + 60.8, row_y, value(cell.get("isa")))

        row_y += WIND_ROW_HEIGHT

    _draw_report_footer(pdf)


def _draw_report_footer(pdf):
    pdf.setFont("Courier-Bold", 8.0)
    pdf.drawCentredString(
        CENTER_X,
        PAGE_H - 729.0,
        "**************   END OF THE REPORT   **************",
    )

    computed_date = datetime.now().strftime("%d-%m-%Y")
    computed_time = datetime.now().strftime("%H:%M:%S")

    _text(pdf, 61.0, 756.6, f"COMPUTED DATE : {computed_date}", font=FONT_BOLD)
    _text_right(pdf, 541.4, 756.6, f"TIME : {computed_time} UTC", font=FONT_BOLD)


# --------------------------------------------------
# GENERATE PDF ENTRYPOINT (VTCSP)
# --------------------------------------------------


def generate_vtcsp_pdf(navlog, file_prefix="VTCSP"):
    """VTAHP is the same sheet as VTCSP - see the dispatcher note in
    pdfGenerator.py - so the prefix only names the file."""
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)

    file_name = f"{file_prefix}{int(datetime.now().timestamp() * 1000)}.pdf"
    absolute_path = os.path.join(OUTPUT_DIRECTORY, file_name)
    relative_path = os.path.join("generated", file_name)

    pdf = canvas.Canvas(absolute_path, pagesize=letter)

    draw_page_one(pdf, navlog)
    y = draw_navlog_pages(pdf, navlog)
    draw_airport_info(pdf, navlog, y)
    draw_final_page(pdf, navlog)

    pdf.save()

    return relative_path
