import os
import re
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from common import OUTPUT_DIRECTORY, find_value, value

# --------------------------------------------------
# VTHYR TEMPLATE (EC145 helicopter, KG, coordinate waypoints)
# --------------------------------------------------
# Measured off the operator's own reference document ("NAV HYR DOF 14 AUG
# 2026") with a text/rect bbox extraction. VTHYR is closest to VTKCM's own
# shape (same ACTUALS grid, ATC CLEARANCE/DEP ATIS/ARR ATIS/DEST ALTN ATIS
# blank rows, four-line certification paragraph, PILOT/COPILOT SIGNATURE),
# reused wholesale below - pages 2-4 are unchanged from vtkcm.py. Page 1's
# fuel block instead follows VTVIK's own row set:
#   * TOP CLIMB TEMP is present, glued to COMPUTED FUEL/BLOCK FUEL's block
#   * PLAN TIME & FUEL rows are TRIP/TAXI/CONTINGENCY 5%/FINAL RESERVE
#     FUEL/XTRA/ALTN1 - no ADDITIONAL row, no DISCRETIONARY rename
#   * a single ALTN1/FIRST ALTN ROUTE pair (no SECOND ALTN ROUTE on this
#     particular reference, though the code still prints one if a second
#     alternate is uploaded) with the dashed divider row before ENDURANCE
#   * weight unit is detected per upload (htmlParser.detect_weight_unit)
#     and printed as whichever the source used - KG or LBS - defaulting
#     to KG (this fleet's historical norm) when neither is detectable
#   * DEP/DEST are lat/long coordinates ("3049N07653E"), not ICAO codes -
#     no name ever follows the trailing dash, which _airport_display
#     already handles correctly since it falls back to "-" alone when
#     neither AIRPORT_NAME_LOOKUP nor the navaid-city guess finds a name
#   * V-speeds are V1 / VR / V2 / VFTO / VREF (five, not VTKCM's four)

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
BANNER_CENTER_X = 279.2

PLAN_ROW_STEP = 14.13

# The level-calc TIME cell is positional on this sheet, not calculated -
# same convention as default1.py's own DIFFERENT LEVEL CALCULATION table:
# "(0:00)" only on the second and fourth rows, every other row blank,
# regardless of what the row's own computed time delta actually is.
LEVEL_TIME_ROWS = (1, 3)
LEVEL_TIME_TEXT = "(0:00)"

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


def _weight(v, unit="KG"):
    v = value(v)
    if not v:
        return ""
    unit = (unit or "KG").strip().upper()
    return v if v.upper().endswith(unit) else f"{v} {unit}"


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
    # This fleet's PLN PROFILE quotes altitude in feet ("@ 2000' - ..."),
    # not a flight level ("@ FL290 - ..."), so both forms need to match.
    match = re.search(r"@\s*(?:FL\d+|\d+')\s*-\s*(.+)$", value(profile_text), re.IGNORECASE)
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

    # DEP/DEST are lat/long coordinates here, so "routeTitle" runs much
    # longer than any ICAO-code pair - the reference wraps it onto two
    # lines (dep on top, dest + registration below) rather than letting
    # one long line run past the frame.
    from reportlab.pdfbase.pdfmetrics import stringWidth

    if stringWidth(route_title, FONT, SIZE) <= 90.0 or " - " not in route_title:
        _text_right(pdf, 554.9, 27.93, f"{route_title}     {registration}".strip())
        return

    # Both wrapped lines are left-aligned at a fixed point, not each
    # right-aligned to the frame edge on their own - measured off the
    # reference, where a much shorter first line ("dep -") and a longer
    # second line share the exact same x0.
    # Shifted up from the single-line baseline (27.93) - the second of
    # these two lines sat right on FRAME_TOP (34.4), so the frame's own
    # top border cut straight through "2906N07558E   VTHYR".
    dep, dest = route_title.split(" - ", 1)
    _text(pdf, 450.71, 18.93, f"{dep} -")
    _text(pdf, 450.71, 30.06, f"{dest}     {registration}".strip())


# --------------------------------------------------
# PAGE ONE
# --------------------------------------------------


def draw_page_one(pdf, data):
    page1 = data.get("page1", {})
    flight = page1.get("flightInfo", {})
    time_info = page1.get("time", {})
    fuel = page1.get("fuel", {})
    weight = page1.get("weight", {})
    # Detected off the upload itself (see claude.py) - some tails on this
    # fleet report in LBS rather than the historical KG default.
    unit = (fuel.get("weightUnit") or "KG").strip().upper()
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
    _text_center(pdf, BANNER_CENTER_X, 69.93, banner)

    # ---- DEP / DEST + DIST / CRUISE + TRACK / PAX ----
    # DEP/DEST are lat/long coordinates, not ICAO codes - _airport_display
    # already falls back to a bare "-" (no name) when neither
    # AIRPORT_NAME_LOOKUP nor the navaid-city guess finds anything, which
    # is exactly what this reference prints.
    dep_code, dep_name = _airport_display(flight.get("departure"), main_navlog)
    dest_code, dest_name = _airport_display(
        flight.get("destination"), main_navlog, from_end=True
    )

    _text(pdf, 50.5, 100.1, "DEP")
    _text(pdf, 76.95, 100.1, f":{dep_code}")
    _text(pdf, 142.6, 100.1, dep_name)

    _text(pdf, 50.5, 114.25, "DEST")
    _text(pdf, 76.95, 114.25, f":{dest_code}")
    _text(pdf, 142.6, 114.25, dest_name)

    _text(pdf, 251.2, 92.3, "DIST")
    _text(pdf, 302.2, 92.3, ":")
    _text(pdf, 310.0, 92.3, _nm(time_info.get("plannedRouteDistance")))

    _text(pdf, 251.2, 114.25, "CRUISE")
    _text(pdf, 302.2, 114.25, ":")

    cruise_lines = _wrap(value(misc.get("plannedProfile")).upper(), SIZE_CRUISE, 134.0)
    cruise_y = 104.67
    for cruise_line in cruise_lines[:4]:
        _text(pdf, 310.0, cruise_y, cruise_line, size=SIZE_CRUISE)
        cruise_y += 8.91

    _text(pdf, 451.9, 100.1, f"TRACK:{_degrees(time_info.get('track'))}")

    _text(pdf, 451.9, 114.25, "PAX")
    _text(pdf, 486.7, 114.25, f":{value(weight.get('pax'))}")

    # ---- MAIN ROUTE / crew ----
    # Unlike VTKCM, this reference repeats the cruise-speed tail here
    # (matching VTVIK's own convention), e.g. "2000' - 500 FPM 120 KIAS
    # 3049N07634E ...".
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

    # ---- COMPUTED FUEL block (four rows, with TOP CLIMB TEMP - VTVIK's
    # own row set, not VTKCM's three-row one) ----
    landing_fuel = find_value(fuel, "landingReported") or value(fuel.get("landing"))

    fuel_pairs = [
        ("COMPUTED FUEL", fuel.get("ramp"), "BLOCK FUEL", fuel.get("flight")),
        ("MIN. TRIP FUEL", fuel.get("minTripFuel"), "TAKE OFF FUEL", fuel.get("takeoff")),
        ("MAX. TRIP FUEL", fuel.get("maxTripFuel"), "LANDING FUEL", landing_fuel),
    ]

    for (left_label, left_val, right_label, right_val), y in zip(
        fuel_pairs, [179.46, 193.59, 207.73]
    ):
        _text(pdf, 50.5, y, left_label)
        _text(pdf, 130.86, y, ":")
        _text_right(pdf, 202.53, y, _weight(left_val, unit))

        _text(pdf, 301.4, y, right_label)
        _text(pdf, 375.21, y, ":")
        _text_right(pdf, 474.21, y, _weight(right_val, unit))

    _text(pdf, 50.5, 221.87, f"TOP CLIMB TEMP:{_space_fl(time_info.get('topClimbTemp'))}")
    _text(pdf, 301.4, 221.87, "WIND")
    _text(pdf, 375.21, 221.87, ":")
    _text_right(pdf, 474.21, 221.87, value(time_info.get("averageWinds")).upper())

    # ---- PLAN TIME & FUEL / PLAN WT ----
    _text(
        pdf,
        51.05,
        240.51,
        "- - - - - - - - PLAN TIME & FUEL - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - "
        f"PLAN WT (in {unit}) - - - - - - - - - - - - - - -",
    )

    alt1 = alternates[0] if len(alternates) > 0 else {}
    alt2 = alternates[1] if len(alternates) > 1 else {}

    # FIX: everything below "DIFFERENT LEVEL CALCULATION" used fixed
    # y-coordinates measured off the operator's reference, which only ever
    # showed a single alternate. ALTN2 adds a row to plan_rows below (see
    # the comment above it), which is fine on its own since divider_y/
    # endurance_y are computed from grid_y and move with it - but nothing
    # past that point followed, so DIFFERENT LEVEL CALCULATION and
    # everything under it stayed put and got run straight over by
    # ENDURANCE and SECOND ALTN ROUTE. Shifting the whole rest of the page
    # down by one plan row's height when a second alternate is present
    # reopens exactly the gap the reference already validated for the
    # single-alternate case.
    _shift = PLAN_ROW_STEP if alt2 else 0.0

    # Same grid VTVIK uses: TRIP/TAXI/CONTINGENCY 5%/FINAL RESERVE FUEL/
    # XTRA/ALTN1(/ALTN2), a dashed divider row, then ENDURANCE - all on
    # one continuous 14.14pt step, so the divider/ENDURANCE position moves
    # down automatically if a second alternate adds its own row.
    plan_rows = [
        ("TRIP", fuel.get("trip"), find_value(fuel, "tripTime", "trip_time")),
        ("TAXI", fuel.get("taxi"), find_value(fuel, "taxiTime", "taxi_time")),
        ("CONTINGENCY 5%", fuel.get("contingency"), find_value(fuel, "contingencyTime", "contingency_time")),
        ("FINAL RESERVE FUEL", fuel.get("finalReserve"), find_value(fuel, "finalReserveTime", "final_reserve_time")),
        ("XTRA", fuel.get("extra"), find_value(fuel, "extraEndurance", "extra_endurance")),
        ("ALTN1", fuel.get("alternate"), find_value(fuel, "alternateTime", "alternate_time")),
    ]
    if alt2:
        plan_rows.append(
            ("ALTN2", fuel.get("alternate2Fuel"), find_value(fuel, "alternate2Time", "alternate2_time"))
        )

    weight_rows = [
        ("BASIC WT", weight.get("basicOperatingWeight")),
        ("TOT.LOAD", weight.get("load")),
        ("ZERO FUEL", weight.get("zeroFuelWeight")),
        ("T.OFF WT", weight.get("takeoffWeight")),
        ("LAND WT", weight.get("estimatedLandingWeight")),
    ]

    grid_y = [259.14 + PLAN_ROW_STEP * i for i in range(len(plan_rows) + 3)]

    for (label, fuel_val, time_val), y in zip(plan_rows, grid_y):
        _text(pdf, 50.5, y, label)
        _text(pdf, 150.91, y, ":")
        _text(pdf, 161.21, y, time_val)
        _text_right(pdf, 232.96, y, _weight(fuel_val, unit))

    for (label, weight_val), y in zip(weight_rows, grid_y):
        _text(pdf, 301.4, y, label)
        _text(pdf, 365.94, y, ":")
        _text_right(pdf, 420.92, y, _weight(weight_val, unit))

    divider_y = grid_y[len(plan_rows)]
    endurance_y = grid_y[len(plan_rows) + 1]

    _text(pdf, 161.21, divider_y, "----------------------")

    alt_summary_y = grid_y[len(plan_rows) - 1] + 3.0
    alt1_dist = _nm(alt1.get("distance"))
    min_divert = _weight(fuel.get("minDivertFuel"), unit)
    _text(
        pdf, 301.4, alt_summary_y,
        f"ALTN : {alt1_dist}         MIN DIVERT FUEL: {min_divert}",
    )

    routes = data.get("routes", {})
    first_route = value(routes.get("alternate1Route")).replace("Route", "").strip()
    second_route = value(routes.get("alternate2Route")).replace("Route", "").strip()

    if first_route:
        _text(pdf, 301.4, alt_summary_y + PLAN_ROW_STEP, f"FIRST ALTN ROUTE : {first_route}")
    if second_route:
        _text(pdf, 301.4, alt_summary_y + PLAN_ROW_STEP * 2, f"SECOND ALTN ROUTE : {second_route}")

    _text(pdf, 90.11, endurance_y, "ENDURANCE:")
    _text(pdf, 161.21, endurance_y, fuel.get("enduranceTime"))
    _text_right(pdf, 232.96, endurance_y, _weight(fuel.get("ramp"), unit))

    # ---- DIFFERENT LEVEL CALCULATION / ACTUALS ----
    _text(
        pdf,
        51.05,
        376.74 + _shift,
        "- - - - - DIFFERENT LEVEL CALCULATION - - - - - - - - - - - - - - - - - - - - - - - "
        "ACTUALS - - - - - - - - - - - - - - - - - - - -",
    )

    _text(pdf, 64.06, 395.38 + _shift, "FL")
    _text(pdf, 100.08, 395.38 + _shift, "WC")
    _text(pdf, 140.37, 395.38 + _shift, "TIME")
    _text(pdf, 196.72, 395.38 + _shift, "TRIP")

    level_y = 409.52 + _shift
    for index, row in enumerate(level_calcs[:5]):
        fl_disp = _space_fl(row.get("fl"))
        # Below the transition altitude a level-calc row is a raw altitude
        # ("3000 ft"), not a flight level - only bare numbers get an "FL "
        # prefix added, not values that already carry their own unit.
        if fl_disp and not fl_disp.upper().startswith("FL") and "ft" not in fl_disp.lower():
            fl_disp = f"FL {fl_disp}"

        _text(pdf, 58.2, level_y, fl_disp)
        _text(pdf, 101.9, level_y, row.get("wc"))
        _text(pdf, 140.37, level_y, LEVEL_TIME_TEXT if index in LEVEL_TIME_ROWS else "")
        _text_right(pdf, 221.93, level_y, _weight(row.get("trip"), unit))
        level_y += PLAN_ROW_STEP

    actual_rows = [
        ("CHOCKS OFF", 263.64, "LANDING", 429.18, 402.13 + _shift),
        ("CHOCKS ON", 267.30, "AIRBORNE", 423.96, 423.02 + _shift),
        ("BLOCK TIME", 264.18, "FLT TIME", 429.95, 443.91 + _shift),
        ("BLOCK FUEL", 263.65, "FIC-ADC", 434.38, 464.79 + _shift),
    ]

    for left_label, left_x, right_label, right_x, y in actual_rows:
        _text(pdf, left_x, y, f"{left_label}: _________")
        _text(pdf, right_x, y, f"{right_label}: _________")

    # ---- hand-fill briefing blocks (no underscore fill, blank-label
    # rows exactly like VTKCM's own) ----
    briefing_rows = [
        ("ATC CLEARANCE", 135.22, 485.46 + _shift, operational.get("departureClearance")),
        ("DEP ATIS", 98.66, 528.84 + _shift, operational.get("departureAtis")),
        ("ARR ATIS", 100.23, 572.23 + _shift, operational.get("arrivalAtis")),
        ("DEST ALTN ATIS", 131.82, 615.62 + _shift, operational.get("destAltnAtis")),
    ]

    for label, colon_x, y, entered in briefing_rows:
        _text(pdf, 48.3, y, label)
        _text(pdf, colon_x, y, ":")
        _text(pdf, colon_x + 9, y, entered)

    # ---- V speeds - five on this template (V1/VR/V2/VFTO/VREF), not
    # VTKCM's four ----
    v_speeds = data.get("vSpeeds", {}) or {}
    v_layout = [
        ("V1:", "v1", 48.27, 62.37),
        ("VR:", "vr", 132.87, 148.54),
        ("V2:", "v2", 219.04, 233.14),
        ("VFTO:", "vfto", 303.64, 330.80),
    ]

    for label, key, label_x, rule_x in v_layout:
        _text(pdf, label_x, 662.01 + _shift, label)
        _text(pdf, rule_x, 662.01 + _shift, "_______________")
        _text(pdf, rule_x + 6, 660.51 + _shift, v_speeds.get(key))

    # VREF's own fill sits apart from the others - same quirk as VTVIK's
    # own last-V-speed row.
    _text(pdf, 401.30, 662.01 + _shift, "VREF:")
    _text(pdf, 453.92, 663.51 + _shift, "_______________")
    _text(pdf, 459.92, 662.01 + _shift, v_speeds.get("vref"))

    # ---- certification footer (no divider line on this reference) ----
    certification = [
        "I certify that all my licenses, ratings etc are current / valid and I am legally/ medically fit for operating flight. I meet the qualification",
        "requirements to operate to concerned airfields as per category/routes indicated per OM D. I have read and understood the operations",
        "manual, OPS supplements, emails, NOTAMS and required compliance. (cars, circulars, aips, etc).BA test complied as per car section 5",
        "series F part 3.",
    ]

    cert_y = 689.29 + _shift
    for cert_line in certification:
        _text_center(pdf, 297.6, cert_y, cert_line, size=SIZE_CERT)
        cert_y += 10.69

    _text(pdf, 416.56, 757.80 + _shift, "(PILOT/COPILOT SIGNATURE)")


# --------------------------------------------------
# NAVLOG TABLE (PAGES 2+)
# --------------------------------------------------
# 19 flat columns, measured off the operator's own reference. The TIME
# group has three columns of its own - LEG, REM, ETE - not one: an
# earlier version of this table folded "REM" into the "ETE" slot and
# dropped the real ETE figure (htmlParser's cell(17), the "ete" key)
# entirely, so every row's actual estimated-time-enroute value was never
# drawn anywhere on the page.

COLUMN_X = [
    34.8, 95.6, 139.4, 164.2, 186.5, 209.9, 234.3, 275.3, 295.0, 317.2,
    335.8, 358.5, 383.4, 412.6, 437.5, 460.3, 485.3, 507.1, 531.6, 560.9,
]

COLUMN_KEYS = [
    "waypoint", "airway", "heading", "course", "flightLevel", "windComponent",
    "windDirectionSpeed", "isa", "tas", "gs", "legDistance", "remainingDistance",
    "fuelUsed", "fuelRemaining", "legTime", "remainingTime", "ete", "ata", "actualFuel",
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

# Matches FRAME_TOP exactly - a gap here doubles the top border, since
# the frame's own rect edge draws one line and the header's first hline
# draws a second one just below it (the same bug vtkcm.py had).
TABLE_TOP = FRAME_TOP
# +1.9 vs. the reference-measured 23.1: TABLE_TOP dropped by that same
# 1.9 (36.3 -> FRAME_TOP's 34.4) to kill the doubled border above, and
# every offset measured from it below is bumped the same amount so the
# already-verified absolute text/row positions don't move.
HEADER_TOP_HEIGHT = 25.0
HEADER_BOTTOM_HEIGHT = 33.0
ROW_HEIGHT = 22.4
ROW_TALL_HEIGHT = 33.5
TABLE_BOTTOM_LIMIT = 780.0
BANNER_HEIGHT = 45.6


def _draw_table_header(pdf, y):
    top_bottom = y + HEADER_TOP_HEIGHT
    bottom_bottom = top_bottom + HEADER_BOTTOM_HEIGHT

    for line_y in (y, top_bottom, bottom_bottom):
        _hline(pdf, COLUMN_X[0], COLUMN_X[-1], line_y)

    # The top row only rules group boundaries - ruling every column
    # boundary there too cut a stray divider straight through a group's
    # own centred label (e.g. "WIND", "FUEL LB"). The row beneath rules
    # every column.
    group_edges = {COLUMN_X[0], COLUMN_X[-1]}
    for label, start, end in COLUMN_GROUPS:
        group_edges.add(COLUMN_X[start])
        group_edges.add(COLUMN_X[end + 1])
    for index, x in enumerate(COLUMN_X[:-1]):
        inside_group = any(start < index <= end for _, start, end in COLUMN_GROUPS)
        if not inside_group:
            group_edges.add(x)

    for x in sorted(group_edges):
        _vline(pdf, x, y, top_bottom)
    for x in COLUMN_X:
        _vline(pdf, x, top_bottom, bottom_bottom)

    for label, start, end in COLUMN_GROUPS:
        center = (COLUMN_X[start] + COLUMN_X[end + 1]) / 2
        _text_center(pdf, center, y + 15.3, label, size=SIZE)

    for index, label in enumerate(COLUMN_LABELS):
        # WAYPOINT is left-aligned against the column edge, same as the
        # data rows below it (COLUMN_X[0] + 2.6) - the reference prints it
        # flush left, not centered like every other header label.
        if index == 0:
            _text(pdf, COLUMN_X[0] + 2.6, top_bottom + 18.4, label, size=SIZE)
            continue
        center = (COLUMN_X[index] + COLUMN_X[index + 1]) / 2
        _text_center(pdf, center, top_bottom + 18.4, label, size=SIZE)

    # The reference abbreviates this one to "ACT", not "ACTUAL" - confirmed
    # off its own text run (3 characters: A, C, T).
    for index, (line1, line2) in enumerate([("ETA", "ATA"), ("ACT", "FUEL")]):
        column = len(COLUMN_LABELS) + index
        center = (COLUMN_X[column] + COLUMN_X[column + 1]) / 2
        _text_center(pdf, center, y + 37.9, line1, size=SIZE)
        _text_center(pdf, center, y + 49.0, line2, size=SIZE)

    return bottom_bottom


def _waypoint_lines(row):
    waypoint = " ".join(
        part for part in
        [value(row.get("waypoint")), value(row.get("waypointDetail"))] if part
    )
    return _wrap(waypoint, SIZE, COLUMN_X[1] - COLUMN_X[0] - 5) or [""]


def _row_height(row):
    return ROW_HEIGHT if len(_waypoint_lines(row)) <= 1 else ROW_TALL_HEIGHT


def _draw_row(pdf, row, y):
    lines = _waypoint_lines(row)
    height = _row_height(row)

    _hline(pdf, COLUMN_X[0], COLUMN_X[-1], y + height)
    for x in COLUMN_X:
        _vline(pdf, x, y, y + height)

    if len(lines) <= 1:
        _text(pdf, COLUMN_X[0] + 2.6, y + 13.4, lines[0], size=SIZE)
        value_baseline = y + 13.4
    else:
        _text(pdf, COLUMN_X[0] + 2.6, y + 13.5, lines[0], size=SIZE)
        _text(pdf, COLUMN_X[0] + 2.6, y + 25.4, lines[1], size=SIZE)
        value_baseline = y + 18.4

    for index, key in enumerate(COLUMN_KEYS):
        if index == 0:
            continue
        center = (COLUMN_X[index] + COLUMN_X[index + 1]) / 2
        _text_center(pdf, center, value_baseline, value(row.get(key)), size=SIZE)

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
    # VTHYR's DEP/DEST are lat/long coordinates, much wider than VTKCM's
    # ICAO codes - this fixed x (carried over from vtkcm.py's own tuning)
    # sat underneath left_text's own tail end and the two ran together.
    _text(pdf, 203.9, y + 26.1, right_text)

    return bottom


def _start_blank_page(pdf, data):
    pdf.showPage()
    _page_header(pdf, data)
    _rect(pdf, FRAME_X0, FRAME_TOP, FRAME_X1, FRAME_BOTTOM)
    return TABLE_TOP


def _start_table_page(pdf, data):
    return _draw_table_header(pdf, _start_blank_page(pdf, data))


def _drop_origin_row(rows):
    """An alternate plan starts where the main route ended, so ForeFlight
    repeats that airport as the block's own origin row - no heading, no
    course, just the taxi fuel. The operator's sheet leaves it out: its
    alternate blocks open on the first navaid, while the main block does
    keep its own origin row. Same fix vtkcm.py already carries - this
    page is otherwise identical to that one and had simply never picked
    it up."""
    if rows and not value(rows[0].get("heading")).strip(" -"):
        return rows[1:]
    return rows


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

        blocks.append((banner_left, banner_right, _drop_origin_row(rows)))

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
    34.8, 79.5, 175.8, 222.2, 262.7, 346.9, 383.1, 422.7, 468.4, 514.4, 560.5,
]

AIRPORT_HEADERS = [
    "", "Airport", "ETA", "ATIS", "TWR/CTAF", "CLR", "GND", "ELEV", "LONGEST RWY", "",
]

AIRPORT_ROW_HEIGHT = 22.4


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
                _text(pdf, AIRPORT_COLUMN_X[index] + 2.6, y + 13.4, cell, size=SIZE)
            else:
                center = (AIRPORT_COLUMN_X[index] + AIRPORT_COLUMN_X[index + 1]) / 2
                _text_center(pdf, center, y + 13.5, cell, size=SIZE)

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
# GENERATE PDF ENTRYPOINT (VTHYR)
# --------------------------------------------------


def generate_vthyr_pdf(navlog):
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)

    file_name = f"VTHYR{int(datetime.now().timestamp() * 1000)}.pdf"
    absolute_path = os.path.join(OUTPUT_DIRECTORY, file_name)
    relative_path = os.path.join("generated", file_name)

    pdf = canvas.Canvas(absolute_path, pagesize=A4)

    draw_page_one(pdf, navlog)
    y = draw_navlog_pages(pdf, navlog)
    draw_airport_info(pdf, navlog, y)
    draw_final_page(pdf, navlog)

    pdf.save()

    return relative_path
