import os
import re
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from common import OUTPUT_DIRECTORY, find_value, value

# --------------------------------------------------
# DEFAULT 1 TEMPLATE
# --------------------------------------------------
# Measured off the operator's own reference document (the VTVIN VOBZ-VOVI
# sheet) with a text/rect bbox extraction, so the layout copies that PDF
# rather than re-interpreting it.
#
# Page 1 is the INDO PACIFIC sheet's twin: every label sits at the same x,
# and the whole block below MAIN ROUTE simply sits 8.9pt lower, with the
# DEP/DEST/TRACK/PAX rows 4.4pt lower. It carries the row INDO PACIFIC
# has and VTKCM drops (TOP CLIMB TEMP), and closes with the four-line
# certification VTKCM uses rather than INDO PACIFIC's two-line one. The
# DIFFERENT LEVEL CALCULATION columns are centred here, where INDO
# PACIFIC left- and right-aligns them.
#
# Page 2 is NOT either of those: it is a flat 19-column navlog whose rows
# grow from 22.4pt to 33.5pt when a waypoint carries a navaid, printing
# the ident and city concatenated on the first line and the frequency
# underneath. Its last column deliberately overhangs the page frame -
# the reference rules the table out to x=593 while the frame stops at
# x=560.9 - and that overhang is reproduced rather than corrected.
#
# Page 3 is INDO PACIFIC's final page with the wind bands on a slightly
# wider pitch.

PAGE_W, PAGE_H = A4

FONT = "Times-Roman"
FONT_BOLD = "Times-Bold"

SIZE = 9.4
SIZE_CRUISE = 7.5
SIZE_CERT = 9.0
SIZE_FPL = 8.2

# One PLAN TIME & FUEL row, and one DIFFERENT LEVEL CALCULATION row.
PLAN_ROW_STEP = 14.138

# Which DIFFERENT LEVEL CALCULATION rows carry a time figure, and what it
# says - see the note at the point of use.
LEVEL_TIME_ROWS = (1, 3)
LEVEL_TIME_TEXT = "(0:00)"

FRAME_X0 = 34.4
FRAME_X1 = 560.9
FRAME_TOP = 34.4
FRAME_BOTTOM = 806.0

CENTER_X = (FRAME_X0 + FRAME_X1) / 2

# The banner is left-aligned here, not centred: both reference sheets start
# it at exactly this x and end at different ones, because their
# registrations are different widths.
BANNER_X = 96.34

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


def _width(content, size=SIZE, font=FONT):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    return stringWidth(str(content or ""), font, size)


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
    v = value(v).strip()
    if not v:
        return ""
    return v if v.upper().endswith("LBS") else f"{v} LBS"


def _nm(v):
    v = value(v).strip()
    if not v:
        return ""
    return v if v.upper().endswith("NM") else f"{v}NM"


def _space_fl(s):
    return re.sub(r"\bFL(\d)", r"FL \1", value(s))


def _degrees(v):
    v = value(v).strip()
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

    # Left-aligned. Right-aligning happened to match one reference because
    # its two idents were the same width; the operator's other sheet ends
    # 3.2pt further right, and both start at exactly this x.
    _text(pdf, 450.71, 27.93, f"{route_title}     {registration}".strip())


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
    _text(pdf, BANNER_X, 69.93, banner)

    # ---- DEP / DEST + DIST / CRUISE + TRACK / PAX ----
    dep_code = value(flight.get("departure"))
    dest_code = value(flight.get("destination"))

    _text(pdf, 50.5, 100.1, "DEP")
    _text(pdf, 77.0, 100.1, ":")
    _text(pdf, 82.6, 100.1, dep_code)

    _text(pdf, 50.5, 114.25, "DEST")
    _text(pdf, 77.0, 114.25, ":")
    _text(pdf, 82.6, 114.25, dest_code)

    _text(pdf, 251.2, 92.3, "DIST")
    _text(pdf, 300.33, 92.3, ":")
    _text(pdf, 307.9, 92.3, _nm(time_info.get("plannedRouteDistance")))

    _text(pdf, 251.2, 114.25, "CRUISE")
    _text(pdf, 300.33, 114.25, ":")

    cruise_lines = _wrap(value(misc.get("plannedProfile")).upper(), SIZE_CRUISE, 140.0)
    cruise_y = 104.7
    for cruise_line in cruise_lines[:4]:
        _text(pdf, 307.9, cruise_y, cruise_line, size=SIZE_CRUISE)
        cruise_y += 8.91

    _text(pdf, 451.9, 100.1, "TRACK")
    _text(pdf, 486.7, 100.1, ":")
    _text(pdf, 492.3, 100.1, _degrees(time_info.get("track")))

    _text(pdf, 451.9, 114.25, "PAX")
    _text(pdf, 486.7, 114.25, ":")
    _text(pdf, 492.3, 114.25, weight.get("pax"))

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
    _text(pdf, 48.3, 141.43, f"MAIN ROUTE : {main_route}".strip())

    _text(pdf, 48.3, 158.57, f"PIC : {_rank(flight.get('pic'))}".rstrip())
    _text(pdf, 299.1, 158.57, f"FO : {_rank(flight.get('fo'))}".rstrip())

    # ---- COMPUTED FUEL block ----
    landing_fuel = find_value(fuel, "landingReported") or value(fuel.get("landing"))

    fuel_pairs = [
        ("COMPUTED FUEL", _lbs(fuel.get("ramp")), "BLOCK FUEL", _lbs(fuel.get("flight"))),
        ("MIN. TRIP FUEL", _lbs(fuel.get("minTripFuel")), "TAKE OFF FUEL", _lbs(fuel.get("takeoff"))),
        ("MAX. TRIP FUEL", _lbs(fuel.get("maxTripFuel")), "LANDING FUEL", _lbs(landing_fuel)),
    ]

    for (left_label, left_val, right_label, right_val), y in zip(
        fuel_pairs, [179.46, 193.59, 207.73]
    ):
        _text(pdf, 50.5, y, left_label)
        _text(pdf, 130.9, y, ":")
        _text_right(pdf, 215.1, y, left_val)

        _text(pdf, 301.4, y, right_label)
        _text(pdf, 375.2, y, ":")
        _text_right(pdf, 474.2, y, right_val)

    _text(pdf, 50.5, 221.87, "TOP CLIMB TEMP")
    _text(pdf, 130.9, 221.87, ":")
    _text(pdf, 136.5, 221.87, _space_fl(time_info.get("topClimbTemp")))

    _text(pdf, 301.4, 221.87, "WIND")
    _text(pdf, 375.2, 221.87, ":")
    _text(pdf, 385.5, 221.87, value(time_info.get("averageWinds")).upper())

    # ---- PLAN TIME & FUEL / PLAN WT ----
    _text(
        pdf,
        51.0,
        240.51,
        "- - - - - - - - PLAN TIME & FUEL - - - - - - - - - - - - - - - - - - - - - - "
        "- - - - - - - - PLAN WT (in LBS) - - - - - - - - - - - - - - -",
    )

    alt1 = alternates[0] if len(alternates) > 0 else {}
    alt2 = alternates[1] if len(alternates) > 1 else {}

    # A second alternate adds an ALTN2 row, and the reference pushes
    # everything under it - the ENDURANCE rule, the level calculation and
    # ACTUALS, the briefing lines, the V-speeds and the certification -
    # down by exactly that one row. The right-hand ALTN / MIN DIVERT /
    # FIRST ALTN ROUTE lines stay where they are.
    show_alternate2 = bool(alt2) or bool(value(fuel.get("alternate2Fuel")))

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

    if show_alternate2:
        plan_rows.append((
            "ALTN2",
            find_value(fuel, "alternate2Time", "alternate2_time"),
            fuel.get("alternate2Fuel"),
        ))

    plan_y = 259.14
    for label, time_val, fuel_val in plan_rows:
        _text(pdf, 50.5, plan_y, label)
        _text(pdf, 150.9, plan_y, ":")
        _text(pdf, 161.2, plan_y, time_val)
        _text_right(pdf, 235.37, plan_y, _lbs(fuel_val))
        plan_y += PLAN_ROW_STEP

    weight_rows = [
        ("BASIC WT", weight.get("basicOperatingWeight")),
        ("TOT.LOAD", weight.get("load")),
        ("ZERO FUEL", weight.get("zeroFuelWeight")),
        ("T.OFF WT", weight.get("takeoffWeight")),
        ("LAND WT", weight.get("estimatedLandingWeight")),
    ]

    weight_y = 259.14
    for label, weight_val in weight_rows:
        _text(pdf, 301.4, weight_y, label)
        _text(pdf, 362.04, weight_y, ":")
        _text_right(pdf, 420.9, weight_y, _lbs(weight_val))
        weight_y += PLAN_ROW_STEP

    shift = PLAN_ROW_STEP if show_alternate2 else 0.0

    alt1_dist = _nm(alt1.get("distance"))
    min_divert = _lbs(fuel.get("minDivertFuel"))

    # One string with nine spaces between the halves - which is why MIN
    # DIVERT starts 4.7pt further right on a three-digit alternate distance.
    if alt1_dist or min_divert:
        altn_line = f"ALTN : {alt1_dist}" if alt1_dist else ""
        if min_divert:
            altn_line = f"{altn_line}{' ' * 9}MIN DIVERT FUEL: {min_divert}"
        _text(pdf, 301.4, 332.83, altn_line.strip() if not alt1_dist else altn_line)

    routes = data.get("routes", {})
    first_route = value(routes.get("alternate1Route")).replace("Route", "").strip()
    second_route = value(routes.get("alternate2Route")).replace("Route", "").strip()

    if first_route:
        _text(pdf, 301.4, 346.97, f"FIRST ALTN ROUTE : {first_route}")

    if second_route:
        # The reference wraps this one onto a second line rather than
        # letting it run past the frame.
        second_lines = _wrap(f"SECOND ALTN ROUTE : {second_route}", SIZE, 224.0)
        second_y = 361.11
        for second_line in second_lines[:2]:
            _text(pdf, 301.4, second_y, second_line)
            second_y += 11.13

    # ---- ENDURANCE ----
    _text(pdf, 161.2, 343.97 + shift, "---------")
    _text(pdf, 192.3, 343.97 + shift, "-------------")

    _text(pdf, 90.1, 358.11 + shift, "ENDURANCE")
    _text(pdf, 150.9, 358.11 + shift, ":")
    _text(pdf, 161.2, 358.11 + shift, fuel.get("enduranceTime"))
    _text_right(pdf, 235.37, 358.11 + shift, _lbs(fuel.get("ramp")))

    # ---- DIFFERENT LEVEL CALCULATION / ACTUALS ----
    _text(
        pdf,
        51.0,
        376.74 + shift,
        "- - - - - DIFFERENT LEVEL CALCULATION - - - - - - - - - - - - - - - - - - - "
        "- - - - ACTUALS - - - - - - - - - - - - - - - - - - - -",
    )

    # Unlike INDO PACIFIC, this sheet centres all four level columns - the
    # heading and its figures share one centre line.
    #
    # The operator's own two documents do not agree on where those centres
    # sit: the whole four-column block is centred at x=141.73 in both, but
    # the internal split moves by up to 1.3pt between them (their generator
    # sizes the columns from the content). These are the midpoints of the
    # two, which puts every column within ~0.65pt of both sheets - a fifth
    # of a character, and the closest a single set of constants can get.
    LEVEL_FL_X = 71.53
    LEVEL_WC_X = 111.42
    LEVEL_TIME_X = 153.98
    LEVEL_TRIP_X = 207.24

    _text_center(pdf, LEVEL_FL_X, 395.38 + shift, "FL")
    _text_center(pdf, LEVEL_WC_X, 395.38 + shift, "WC")
    _text_center(pdf, LEVEL_TIME_X, 395.38 + shift, "TIME")
    _text_center(pdf, LEVEL_TRIP_X, 395.38 + shift, "TRIP")

    level_y = 409.52 + shift
    for index, row in enumerate(level_calcs[:5]):
        fl_disp = _space_fl(row.get("fl"))
        # Below the transition altitude a level-calc row is a raw altitude
        # ("3000 ft"), not a flight level - only bare numbers get an "FL "
        # prefix added, not values that already carry their own unit.
        if fl_disp and not fl_disp.upper().startswith("FL") and "ft" not in fl_disp.lower():
            fl_disp = f"FL {fl_disp}"

        _text_center(pdf, LEVEL_FL_X, level_y, fl_disp)
        _text_center(pdf, LEVEL_WC_X, level_y, row.get("wc"))
        # The TIME cell is positional on this sheet, not calculated: both
        # of the operator's reference documents print "(0:00)" on the
        # second and fourth rows and leave the other three blank, across
        # two unrelated flights with different aircraft, routes, winds and
        # trip fuels. Reproduced on the operator's instruction so the sheet
        # matches the one their existing system issues.
        #
        # It is therefore NOT ForeFlight's computed delta, which for the
        # VTYAN flight is (-0:01) at FL 240. If this column is ever wanted
        # as a real figure, print value(row.get("time")) instead.
        _text_center(pdf, LEVEL_TIME_X, level_y,
                     LEVEL_TIME_TEXT if index in LEVEL_TIME_ROWS else "")
        _text_center(pdf, LEVEL_TRIP_X, level_y, _lbs(row.get("trip")))
        level_y += PLAN_ROW_STEP

    # The reference rules these with underscore characters, not drawn lines.
    actual_rows = [
        ("CHOCKS OFF", "LANDING", 402.13 + shift),
        ("CHOCKS ON", "AIRBORNE", 423.02 + shift),
        ("BLOCK TIME", "FLT TIME", 443.91 + shift),
        ("BLOCK FUEL", "FIC-ADC", 464.79 + shift),
    ]

    for left_label, right_label, y in actual_rows:
        _text_right(pdf, 321.4, y, left_label)
        _text(pdf, 324.2, y, ": _________")

        _text_right(pdf, 472.0, y, right_label)
        _text(pdf, 474.9, y, ": _________")

    # ---- hand-fill briefing blocks ----
    # The reference draws each of these as a single string - label, four
    # spaces, colon - which is what puts the colons at 135.22 and 98.66.
    briefing_rows = [
        ("ATC CLEARANCE", 135.22, 485.46 + shift, operational.get("departureClearance")),
        ("DEP ATIS", 98.66, 528.84 + shift, operational.get("departureAtis")),
        ("ARR ATIS", 100.23, 572.23 + shift, operational.get("arrivalAtis")),
        ("DEST ALTN ATIS", 131.83, 615.62 + shift, operational.get("destAltnAtis")),
    ]

    for label, colon_x, y, entered in briefing_rows:
        _text(pdf, 48.27, y, f"{label}    :")
        _text(pdf, colon_x + 9, y, entered)

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
        rule_y = (663.51 if label == "VREF:" else 662.01) + shift
        _text(pdf, label_x, 662.01 + shift, label)
        _text(pdf, rule_x, rule_y, "_______________")
        _text(pdf, rule_x + 6, rule_y - 1.5, v_speeds.get(key))

    # ---- certification footer ----
    pdf.setLineWidth(1.5)
    pdf.line(46.0, PAGE_H - (676.24 + shift), 549.3, PAGE_H - (676.24 + shift))

    certification = [
        "I certify that all my licenses, ratings etc are current / valid and I am legally/ medically fit for operating flight. I meet the qualification",
        "requirements to operate to concerned airfields as per category/routes indicated per OM D. I have read and understood the operations",
        "manual, OPS supplements, emails, NOTAMS and required compliance. (cars, circulars, aips, etc).BA test complied as per car section 5",
        "series F part 3.  ",
    ]

    cert_y = 689.29 + shift
    for cert_line in certification:
        _text_center(pdf, 297.6, cert_y, cert_line, size=SIZE_CERT)
        cert_y += 10.69

    _text(pdf, 416.56, 757.8 + shift, "(PILOT/COPILOT SIGNATURE)")


# --------------------------------------------------
# NAVLOG TABLE (PAGES 2+)
# --------------------------------------------------
# 19 flat columns. The last one (ACTUAL FUEL) sits outside the page frame
# in the reference, which rules the table to x=593 while the frame stops
# at x=560.9 - so the horizontal rules run the full width but the closing
# vertical is only drawn on the alternate-route banner.

# The navlog table is sized from its own contents, not from fixed columns.
# The operator's two reference sheets prove it: the same template gives the
# WAYPOINT column 104.8pt when the longest ident is "VVZVISAKHAPATNAM" and
# 65.8pt when it is "JJBJABALPUR", and every other column is its widest cell
# plus a near-constant pad (3.70pt on one sheet, 4.00pt on the other). The
# midpoint is used here. This is also why the table can overhang the page
# frame: a long ident simply pushes the right-hand columns past x=560.9,
# exactly as the reference does.
TABLE_X0 = 34.77

# Each column is its widest cell plus this pad...
COLUMN_PAD = 3.68

# ...except that the table is never narrower than the page frame: when the
# content leaves it short, the slack is shared equally between the columns
# and the pad grows. That single rule reproduces both of the operator's
# reference sheets - the one whose longest ident is "JJBJABALPUR" fills the
# frame exactly with a 4.09pt pad, and the one carrying
# "VVZVISAKHAPATNAM" overhangs the frame on the base pad.
TABLE_MIN_RIGHT = 560.51

# The WAYPOINT column carries a slightly different pad from the rest in
# both references; this splits the difference.
WAYPOINT_EXTRA = 0.23

COLUMN_KEYS = [
    "waypoint", "airway", "heading", "course", "flightLevel", "windComponent",
    "windDirectionSpeed", "isa", "tas", "gs", "legDistance", "remainingDistance",
    "fuelUsed", "fuelRemaining", "legTime", "remainingTime", "ete", "ata",
    "actualFuel",
]

# The single-line headings; the last two columns stack their two lines.
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

# Five columns carry a trailing space on every cell that holds a figure
# (a dash never has one). A centred string with a trailing space sits half
# a space-width - 1.17pt - to the left, and the reference does this
# consistently: 13/13 ISA cells, 12/12 GS, 13/13 remaining-fuel, 12/12
# leg-time and 11/11 ETE. Reproduced so the figures land where the
# operator's own sheet puts them.
TRAILING_SPACE_KEYS = {"isa", "gs", "fuelRemaining", "legTime", "ete"}

# The ALT column takes one too, but only when the cell holds a flight level
# rather than an altitude in feet - true of both reference sheets.
def _trails_space(key, cell):
    if key in TRAILING_SPACE_KEYS:
        return True
    return key == "flightLevel" and re.match(r"^FL\d{3}$", cell.upper()) is not None

# The reference centres cell text 0.77pt to the right of the midpoint
# between its ruled column lines - a quirk of its own generator, applied
# to every centred cell on the navlog and airport tables.
CELL_CENTER_NUDGE = 0.77

def _column_x(data):
    """Left edge of every column, sized to the widest cell each one holds."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    rows = []
    for key in ("mainNavlog", "alternate1Navlog", "alternate2Navlog"):
        rows.extend(data.get(key, []) or [])

    stacked = {len(COLUMN_LABELS): ("ETA", "ATA"),
               len(COLUMN_LABELS) + 1: ("ACT", "FUEL")}

    widths = []
    for index, key in enumerate(COLUMN_KEYS):
        if index < len(COLUMN_LABELS):
            widest = stringWidth(COLUMN_LABELS[index], FONT, SIZE)
        else:
            widest = max(stringWidth(part, FONT, SIZE)
                         for part in stacked[index])

        for row in rows:
            if index == 0:
                cells = _waypoint_lines(row)
            else:
                cells = [value(row.get(key))]
            for cell in cells:
                widest = max(widest, stringWidth(cell, FONT, SIZE))

        widths.append(widest + (WAYPOINT_EXTRA if index == 0 else 0.0))

    slack = (TABLE_MIN_RIGHT - TABLE_X0 - sum(widths)) / len(widths)
    pad = max(COLUMN_PAD, slack)

    edges, x = [TABLE_X0], TABLE_X0
    for width in widths:
        x += width + pad
        edges.append(x)
    return edges


TABLE_TOP = 36.27
CONTINUATION_TOP = 34.77
HEADER_TOP_HEIGHT = 22.38
HEADER_BOTTOM_HEIGHT = 33.53
ROW_HEIGHT = 22.39
ROW_TALL_HEIGHT = 33.52
TABLE_BOTTOM_LIMIT = 780.0
BANNER_HEIGHT = 45.64

# AIRPORT INFO's own rows (22.39pt, no tall 2-line variant) don't need
# the navlog table's full safety margin - using TABLE_BOTTOM_LIMIT here
# was pushing the whole section onto a fresh, nearly-empty page whenever
# it fell just short (as little as ~11pt), leaving both the tail of the
# navlog page and the new page mostly blank.
AIRPORT_INFO_BOTTOM_LIMIT = FRAME_BOTTOM - 10.0


def _draw_table_header(pdf, y, COLUMN_X):
    top_bottom = y + HEADER_TOP_HEIGHT
    bottom_bottom = top_bottom + HEADER_BOTTOM_HEIGHT

    # Wide content can push COLUMN_X[-1] past the frame's own right edge
    # (see TABLE_MIN_RIGHT above) - column widths stay exactly as
    # calibrated, but the ruled line itself stops at the frame rather than
    # running on past it, which is what created a short stray-looking
    # sliver to the right of ACT/FUEL on wide-content sheets.
    right_edge = min(COLUMN_X[-1], FRAME_X1)
    for line_y in (y, top_bottom, bottom_bottom):
        _hline(pdf, COLUMN_X[0], right_edge, line_y)

    # The top row rules only the group boundaries; the row beneath rules
    # every column.
    group_edges = {COLUMN_X[0], COLUMN_X[-2]}
    for label, start, end in COLUMN_GROUPS:
        group_edges.add(COLUMN_X[start])
        group_edges.add(COLUMN_X[end + 1])
    for index, x in enumerate(COLUMN_X[:-1]):
        inside_group = any(start < index <= end for _, start, end in COLUMN_GROUPS)
        if not inside_group:
            group_edges.add(x)

    for x in sorted(group_edges):
        _vline(pdf, x, y, top_bottom)
    for x in COLUMN_X[:-1]:
        _vline(pdf, x, top_bottom, bottom_bottom)

    for label, start, end in COLUMN_GROUPS:
        center = (COLUMN_X[start] + COLUMN_X[end + 1]) / 2 + CELL_CENTER_NUDGE
        _text_center(pdf, center, y + 14.53, label)

    for index, label in enumerate(COLUMN_LABELS):
        center = (COLUMN_X[index] + COLUMN_X[index + 1]) / 2 + CELL_CENTER_NUDGE
        if index == 0:
            _text(pdf, COLUMN_X[0] + 2.62, top_bottom + 20.11, label)
        else:
            _text_center(pdf, center, top_bottom + 20.11, label)

    # ETA/ATA and ACTUAL/FUEL stack across both header rows.
    for index, (line1, line2) in enumerate([("ETA", "ATA"), ("ACT", "FUEL")]):
        column = len(COLUMN_LABELS) + index
        center = (COLUMN_X[column] + COLUMN_X[column + 1]) / 2 + CELL_CENTER_NUDGE
        _text_center(pdf, center, y + 36.92, line1)
        _text_center(pdf, center, y + 48.06, line2)

    return bottom_bottom


def _waypoint_lines(row):
    """The reference runs the ident straight into the navaid's city with no
    space ("BBZ" + "VIJAYAWADA") and drops the frequency to a second line,
    which is what makes a row tall."""
    ident = value(row.get("waypoint"))
    detail = value(row.get("waypointDetail"))

    if not detail:
        return [ident]

    parts = detail.split()
    if parts and parts[-1].replace(".", "").isdigit():
        return [f"{ident}{' '.join(parts[:-1])}", parts[-1]]

    return [f"{ident}{' '.join(parts)}"]


def _row_height(row):
    return ROW_HEIGHT if len(_waypoint_lines(row)) <= 1 else ROW_TALL_HEIGHT


def _draw_row(pdf, row, y, COLUMN_X):
    lines = _waypoint_lines(row)
    height = _row_height(row)

    # See _draw_table_header's own right_edge note - the ruled line stops
    # at the frame even when wide content pushes the column past it.
    _hline(pdf, COLUMN_X[0], min(COLUMN_X[-1], FRAME_X1), y + height)
    for x in COLUMN_X[:-1]:
        _vline(pdf, x, y, y + height)

    if len(lines) <= 1:
        _text(pdf, COLUMN_X[0] + 2.62, y + 14.53, lines[0])
        value_baseline = y + 14.53
    else:
        _text(pdf, COLUMN_X[0] + 2.62, y + 14.53, lines[0])
        _text(pdf, COLUMN_X[0] + 2.62, y + 25.67, lines[1])
        value_baseline = y + 20.10

    for index, key in enumerate(COLUMN_KEYS):
        if index == 0:
            continue
        center = (COLUMN_X[index] + COLUMN_X[index + 1]) / 2 + CELL_CENTER_NUDGE

        cell = value(row.get(key))
        if cell and cell != "-" and _trails_space(key, cell):
            cell = f"{cell} "

        _text_center(pdf, center, value_baseline, cell)

    return y + height


def _drop_origin_row(rows):
    """An alternate plan starts where the main route ended, so ForeFlight
    repeats that airport as the block's own origin row - no heading, no
    course, just the taxi fuel. The operator's sheet leaves it out: its
    alternate blocks open on the first navaid (JJBJABALPUR, not VAJB),
    while the main block does keep its origin row. Matched here."""
    if rows and not value(rows[0].get("heading")).strip(" -"):
        return rows[1:]
    return rows


def _draw_banner(pdf, left_text, right_text, y, COLUMN_X):
    # A banner spans the whole table, so its border should land on the
    # frame's own edges - not COLUMN_X[0]/[-1], which are the navlog
    # table's own column grid and can sit a hair inside the frame (or, for
    # wide waypoint content, outside it - see TABLE_MIN_RIGHT above).
    # Anchoring to COLUMN_X there left a short stray vertical stroke
    # floating past the frame's right edge wherever a banner appeared,
    # since no ordinary row ever draws that rightmost boundary itself.
    bottom = y + BANNER_HEIGHT
    _hline(pdf, FRAME_X0, FRAME_X1, bottom)
    _vline(pdf, FRAME_X0, y, bottom)
    _vline(pdf, FRAME_X1, y, bottom)

    banner = left_text
    if right_text:
        banner = f"{left_text}{' ' * 6}{right_text}"
    _text(pdf, COLUMN_X[0] + 2.62, y + 26.16, banner)

    return bottom


def _start_blank_page(pdf, data, first=False):
    pdf.showPage()
    _page_header(pdf, data)
    _rect(pdf, FRAME_X0, FRAME_TOP, FRAME_X1, FRAME_BOTTOM)
    return TABLE_TOP if first else CONTINUATION_TOP


def _start_table_page(pdf, data, COLUMN_X, first=False):
    return _draw_table_header(pdf, _start_blank_page(pdf, data, first), COLUMN_X)


def draw_navlog_pages(pdf, data):
    COLUMN_X = _column_x(data)
    y = _start_table_page(pdf, data, COLUMN_X, first=True)

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

        blocks.append((banner_left, banner_right, _drop_origin_row(rows)))

    for banner_left, banner_right, rows in blocks:
        if banner_left is not None:
            if y + BANNER_HEIGHT + ROW_HEIGHT > TABLE_BOTTOM_LIMIT:
                y = _start_table_page(pdf, data, COLUMN_X)
            y = _draw_banner(pdf, banner_left, banner_right, y, COLUMN_X)

        for row in rows:
            if y + _row_height(row) > TABLE_BOTTOM_LIMIT:
                y = _start_table_page(pdf, data, COLUMN_X)
            y = _draw_row(pdf, row, y, COLUMN_X)

    return y


# --------------------------------------------------
# AIRPORT INFO
# --------------------------------------------------

# Unlike the navlog, this table's columns are not sized from their contents
# - the TWR/CTAF column is 90pt wide for a six-character frequency in both
# reference sheets. The two sheets do differ by up to 3pt per boundary
# without a rule I could pin down, so these are the midpoints of the two,
# which keeps every boundary within ~1.9pt of either.
AIRPORT_COLUMN_X = [
    34.77, 82.13, 136.75, 185.92, 241.39, 330.50, 368.80, 411.38, 459.65,
    509.09, 560.51,
]

AIRPORT_HEADERS = [
    "", "Airport", "ETA", "ATIS", "TWR/CTAF", "CLR", "GND", "ELEV", "LONGEST RWY", "",
]

AIRPORT_ROW_HEIGHT = 22.39


def draw_airport_info(pdf, data, y):
    airports = data.get("airportInformation", [])
    if not airports:
        return y


    needed = 53.9 + AIRPORT_ROW_HEIGHT * (len(airports) + 1)
    if y + needed > AIRPORT_INFO_BOTTOM_LIMIT:
        y = _start_blank_page(pdf, data)

    y += 42.66
    _text(pdf, 34.77, y, "AIRPORT INFO")
    y += 11.23

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
                _text(pdf, AIRPORT_COLUMN_X[index] + 2.63, y + 14.53, cell)
            else:
                center = ((AIRPORT_COLUMN_X[index] + AIRPORT_COLUMN_X[index + 1]) / 2
                          + CELL_CENTER_NUDGE)
                _text_center(pdf, center, y + 14.53, cell)

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

FPL_WIDTH = 500.0
FPL_LEADING = 11.25
FPL_LEADING_REMARKS = 10.1
FPL_LEADING_WRAP = 9.85

WIND_IDENT_X = 48.27

# The wind bands are not on a fixed pitch: they start a fixed gap past the
# widest identifier and are spread evenly to a fixed right-hand edge, so a
# route with wider idents ("GOGVE") starts further right and steps a little
# tighter than one with narrow ones ("-TOC-").
WIND_IDENT_GAP = 43.15
WIND_LAST_X = 481.1
WIND_TMP_OFFSET = 51.24
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

    # The "IDENT" heading counts towards the column's width, which is what
    # keeps a route of short idents from pulling the bands left.
    widest_ident = max(
        [_width(value(row.get("identifier"))) for row in wind_rows]
        + [_width("IDENT")]
    )
    first_x = WIND_IDENT_X + widest_ident + WIND_IDENT_GAP
    step = (WIND_LAST_X - first_x) / max(band_count - 1, 1)

    # The winds block follows the flight-plan text rather than sitting at a
    # fixed height: on the sheet whose RMK line wraps it lands at y=200, and
    # on the one where it does not, 9.8pt higher.
    winds_y = y + 22.12
    _text_center(pdf, CENTER_X, winds_y, "ENROUTE WINDS")

    header_y = winds_y + 28.1
    for index, band in enumerate(bands):
        band_x = first_x + index * step
        # Right-aligned, not left: the reference's five band headings share
        # a right edge 30.8pt past the band anchor, which is what keeps them
        # on the same 90.45pt pitch as the figures underneath.
        _text_right(pdf, band_x + 30.8, header_y - 5.6,
                    str(band).split("(")[0].strip())
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
            band_x = first_x + index * step

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

    _text(pdf, 37.0, 802.65, f"COMPUTED DATE : {computed_date}")
    _text_right(pdf, 558.5, 802.65, f"TIME : {computed_time} UTC")


# --------------------------------------------------
# GENERATE PDF ENTRYPOINT (DEFAULT 1)
# --------------------------------------------------


def generate_default1_pdf(navlog, file_prefix="DEFAULT1"):
    """DEFAULT and DEFAULT 1 are the same sheet - see the dispatcher note in
    pdfGenerator.py - so the prefix only names the file."""
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)

    file_name = f"{file_prefix}_{int(datetime.now().timestamp() * 1000)}.pdf"
    absolute_path = os.path.join(OUTPUT_DIRECTORY, file_name)
    relative_path = os.path.join("generated", file_name)

    pdf = canvas.Canvas(absolute_path, pagesize=A4)

    draw_page_one(pdf, navlog)
    y = draw_navlog_pages(pdf, navlog)
    draw_airport_info(pdf, navlog, y)
    draw_final_page(pdf, navlog)

    pdf.save()

    return relative_path
