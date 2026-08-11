import os
import re
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from common import OUTPUT_DIRECTORY, find_value, value

# --------------------------------------------------
# VTJOE TEMPLATE
# --------------------------------------------------
# Measured off the operator's own reference document ("NAV VTTWJ - (VTJOE
# DOWNLOAD)") with a text/rect bbox extraction, so the layout copies that
# PDF rather than re-interpreting it.
#
# Page 1 belongs to MLOVE's family - FLIGHT INFO / TIME / FUEL / WEIGHT /
# MISC blocks, then ATC ROUTE, DEP and TAXI CLEARANCE, then the ALT1/ALT2
# summaries - but laid out in its own grid, with an OFF BLK / ON BLK /
# BLK TIME log in the TIME block and an MDF (minimum divert fuel) row in
# the FUEL block.
#
# Page 2 is unique to this template: a full hand-fill DEPARTURE ATIS /
# TAKE OFF DATA / ARRAIVAL ATIS / LANDING DATA / ALTERNATE form, printed
# verbatim (including the reference's own "ARRAIVAL" spelling).
#
# Pages 3+ are the stacked 12-column navlog, at this template's widths and
# a smaller 8.2pt body, followed by AIRPORT INFO and the ATC flight plan /
# ENROUTE WINDS page.

PAGE_W, PAGE_H = A4

FONT = "Times-Roman"

SIZE = 9.4
SIZE_TABLE = 8.2

FRAME_X0 = 34.4
FRAME_X1 = 560.9
FRAME_TOP = 34.4
FRAME_BOTTOM = 806.0

CENTER_X = (FRAME_X0 + FRAME_X1) / 2

ROW_STEP = 14.15


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


def _rule(pdf, y):
    """The heavy separators page 1 draws between its lower blocks."""
    _hline(pdf, 46.0, 549.3, y, width=1.4)


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


def _nm(v):
    v = value(v)
    if not v:
        return ""
    return v if v.upper().endswith("NM") else f"{v}NM"


def _space_fl(s):
    return re.sub(r"\bFL(\d)", r"FL \1", value(s))


def _rank(name):
    name = value(name).upper()
    if not name:
        return ""
    if re.match(r"^(CAPT|CPT|CMDR|MR|MS|MRS|FO|F/O)\b", name):
        return name
    return f"CAPT {name}"


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
    atc = data.get("atcFlightPlan", {})

    _page_header(pdf, data)
    _rect(pdf, FRAME_X0, FRAME_TOP, FRAME_X1, FRAME_BOTTOM)

    # ---- crew header ----
    _text(pdf, 50.5, 57.2, "FLIGHT")
    _text(pdf, 86.8, 57.2, ":")
    _text(pdf, 92.5, 57.2, flight.get("flight"))

    _text(pdf, 50.5, 71.3, "DATE")
    _text(pdf, 86.8, 71.3, ":")
    _text(pdf, 92.5, 71.3, flight.get("date"))

    _text(pdf, 187.4, 62.7, "PIC")
    _text(pdf, 213.2, 62.7, ":")

    # A long PIC name wraps onto a second line, and the pair is centred on
    # the label's own baseline.
    pic_lines = _wrap(_rank(flight.get("pic")), SIZE, 125.0)[:2]
    if len(pic_lines) <= 1:
        _text(pdf, 221.5, 62.7, pic_lines[0] if pic_lines else "")
    else:
        _text(pdf, 221.5, 57.2, pic_lines[0])
        _text(pdf, 221.5, 68.3, pic_lines[1])

    _text(pdf, 187.4, 82.5, "F/O")
    _text(pdf, 213.2, 82.5, ":")
    _text(pdf, 221.5, 82.5, _rank(flight.get("fo")))

    _text(pdf, 347.0, 82.5, "COMMANDER SIGN")
    _text(pdf, 436.2, 82.5, ":")
    _text(pdf, 441.8, 82.5, "__________________")

    # ---- FLIGHT INFO / TIME ----
    _text(
        pdf,
        51.0,
        112.3,
        "- - - - - - - - - - FLIGHT INFO - - - - - - - - - -"
        "                                "
        "- - - - - - - - - - - - - - - - - TIME - - - - - - - - - - - -",
    )

    etd = value(time_info.get("etd"))
    etd_local = value(time_info.get("etdLocal"))
    eta = value(time_info.get("eta"))
    eta_local = value(time_info.get("etaLocal"))

    _text(pdf, 301.4, 142.2, f"ETD : {etd} (IST: {etd_local} )" if etd_local else f"ETD : {etd}")
    _text(pdf, 424.6, 142.2, f"ETA : {eta} (IST: {eta_local} )" if eta_local else f"ETA : {eta}")

    info_rows = [
        ("REG", flight.get("registration")),
        ("FL", flight.get("flightLevel")),
        ("FROM", flight.get("departure")),
        ("TO", flight.get("destination")),
        ("ALT1", flight.get("alternate1")),
    ]

    info_y = 144.8
    for label, val in info_rows:
        _text(pdf, 50.5, info_y, label)
        _text(pdf, 128.5, info_y, ":")
        _text(pdf, 143.3, info_y, val)
        info_y += ROW_STEP

    # The block-time log is filled in by hand on the day.
    time_rows = [
        ("CTOT", None, 166.1),
        ("OFF BLK", "AIRB", 183.9),
        ("ON BLK", "LAND", 201.8),
        ("BLK TIME", "AIR T", 219.6),
    ]

    for left_label, right_label, y in time_rows:
        _text(pdf, 303.6, y, left_label)
        _text(pdf, 350.6, y, "______")
        _text(pdf, 381.8, y, ":")
        _text(pdf, 387.4, y, "______")

        if right_label:
            _text(pdf, 428.3, y, right_label)
            _text(pdf, 457.3, y, "______")
            _text(pdf, 488.4, y, ":")
            _text(pdf, 494.0, y, "______")

    step_climb = _space_fl(time_info.get("stepClimb"))
    if step_climb:
        _text(pdf, 48.3, 222.3, f"STEP CLIMB   :   {step_climb}")

    # ---- FUEL / WEIGHT ----
    _text(
        pdf,
        51.0,
        241.3,
        "- - - - - - - - - - - - - - - - - FUEL - - - - - - - - - - - - - - - - -"
        "                "
        "- - - - - - - - - - - - - - WEIGHT - - - - - - - - - - - - - -",
    )

    fuel_rows = [
        ("TAXI", fuel.get("taxi"), "", ""),
        ("TRIP", fuel.get("trip"),
         find_value(fuel, "tripTime", "trip_time"),
         _nm(find_value(fuel, "tripDistance", "trip_distance"))),
        ("CONTINGENCY", fuel.get("contingency"),
         find_value(fuel, "contingencyTime", "contingency_time"), ""),
        ("ALT1", fuel.get("alternate"),
         find_value(fuel, "alternateTime", "alternate_time"),
         _nm(find_value(fuel, "alternateDistance", "alternate_distance"))),
        ("FRES", fuel.get("finalReserve"),
         find_value(fuel, "finalReserveTime", "final_reserve_time"), ""),
        ("REQ", fuel.get("required"),
         find_value(fuel, "requiredEndurance", "required_endurance"), ""),
        ("EXTRA", fuel.get("extra"),
         find_value(fuel, "extraEndurance", "extra_endurance"), ""),
        ("T/O FUEL", fuel.get("takeoff"),
         find_value(fuel, "takeoffEndurance", "takeoff_endurance"), ""),
        ("RAMP", fuel.get("ramp"),
         find_value(fuel, "rampEndurance", "ramp_endurance"), ""),
        ("MDF", fuel.get("minDivertFuel"),
         find_value(fuel, "minDivertEndurance", "min_divert_endurance"), ""),
    ]

    fuel_y = 259.9
    for label, fuel_val, time_val, distance in fuel_rows:
        _text(pdf, 50.5, fuel_y, label)
        _text(pdf, 145.5, fuel_y, ":")
        _text_right(pdf, 186.2, fuel_y, fuel_val)
        _text(pdf, 196.8, fuel_y, time_val)
        _text(pdf, 227.5, fuel_y, distance)
        fuel_y += ROW_STEP

    weight_rows = [
        ("BOW", weight.get("basicOperatingWeight")),
        ("PAX", weight.get("pax")),
        ("LOAD", weight.get("load")),
        ("ZFW", weight.get("zeroFuelWeight")),
        ("T/O FUEL", weight.get("takeoffFuel")),
        ("TOW", weight.get("takeoffWeight")),
        ("ELW", weight.get("estimatedLandingWeight")),
    ]

    weight_y = 263.7
    for label, val in weight_rows:
        _text(pdf, 303.6, weight_y, label)
        _text(pdf, 377.5, weight_y, ":")
        _text_right(pdf, 442.3, weight_y, val)
        weight_y += ROW_STEP

    # ---- MISC ----
    _text(
        pdf,
        51.0,
        405.8,
        "- - - - - - - - - - - - - - - - - MISC - - - - - - - - - - - - - - - - -",
    )

    # PLN PROFILE on this template is the tail and type, not the cruise
    # profile string the other templates print there.
    registration = value(header.get("registration") or flight.get("registration"))
    ac_type = find_value(header, flight, atc, "aircraftType", "type", "acType")
    profile = f"{registration} ({ac_type})" if ac_type else registration

    misc_rows = [
        ("PLND ROUTE", _nm(find_value(time_info, "plannedRouteDistance"))),
        ("AVG WINDS", find_value(time_info, "averageWinds").upper()),
        ("AVG.WC", find_value(time_info, "averageWindComponent").upper()),
        ("PLN PROFILE", profile),
        ("TAS", find_value(time_info, "tas")),
    ]

    misc_y = 424.4
    for label, val in misc_rows:
        _text(pdf, 50.5, misc_y, label)
        _text(pdf, 237.4, misc_y, ":")
        _text(pdf, 256.4, misc_y, val)
        misc_y += ROW_STEP

    # ---- routes and clearances ----
    _rule(pdf, 495.9)

    atc_route = value(misc.get("atcRoute")).upper()
    _text(pdf, 48.3, 511.6, f"ATC ROUTE   :   {atc_route}".rstrip())

    _rule(pdf, 524.3)

    _text(pdf, 48.3, 540.0, "DEP CLEARANCE")
    _text(pdf, 136.9, 540.0, ":")
    _text(pdf, 148.0, 540.0, operational.get("departureClearance"))

    _text(pdf, 48.3, 610.5, "TAXI CLEARANCE")
    _text(pdf, 136.9, 610.5, ":")
    _text(pdf, 148.0, 610.5, operational.get("depTaxiClearance"))

    _rule(pdf, 679.6)

    # ---- alternate summaries ----
    for index, y in ((0, 695.2), (1, 749.0)):
        alternate = alternates[index] if len(alternates) > index else {}

        _text(pdf, 48.3, y, f"ALT{index + 1}")
        _text(pdf, 96.2, y, ":")
        _text(pdf, 123.8, y, value(alternate.get("airport")))
        _text(pdf, 174.0, y, "Route")
        _text(pdf, 221.4, y, ":")
        _text(pdf, 249.0, y, value(alternate.get("route")).replace("Route", "").strip())

        _text(pdf, 48.3, y + 14.2, "FL")
        _text(pdf, 96.2, y + 14.2, ":")
        _text(pdf, 123.8, y + 14.2, value(alternate.get("flightLevel")))
        _text(pdf, 174.0, y + 14.2, "DIST")
        _text(pdf, 221.4, y + 14.2, ":")
        _text(pdf, 249.0, y + 14.2, _nm(alternate.get("distance")))
        _text(pdf, 303.2, y + 14.2, "ETE")
        _text(pdf, 345.4, y + 14.2, ":")
        _text(pdf, 376.0, y + 14.2, value(alternate.get("ete")))
        _text(pdf, 430.2, y + 14.2, "FUEL")
        _text(pdf, 478.6, y + 14.2, ":")

        alt_fuel = value(alternate.get("fuel"))
        if alt_fuel and not alt_fuel.lower().endswith("lbs"):
            alt_fuel = f"{alt_fuel} lbs"
        _text(pdf, 506.3, y + 14.2, alt_fuel)


# --------------------------------------------------
# PAGE TWO (ATIS / TAKE OFF / LANDING FORM)
# --------------------------------------------------
# Printed verbatim from the reference, the operator's own "ARRAIVAL"
# spelling included - this page is filled in by hand on the day.

FORM_SECTIONS = [
    (64.3, "DEPARTURE ATIS"),
    (276.3, "TAKE OFF DATA"),
    (424.7, "ARRAIVAL ATIS"),
    (636.6, "LANDING DATA"),
    (743.9, "ALTERNATE"),
]

FORM_LINES = [
    (96.1, "APT:____________________________   ATIS/TIME:____________________________________________________________Z"),
    (127.8, "T.ALT______________   RWY______________   INTX_____________   WIND___________/__________ VIS  /  RVR ________"),
    (159.6, "WX___________________________________   CLDS_____________________________________________________________"),
    (191.4, "TEMP__________________C   DEW POINT_________________C   QNH____________________   TREND________________"),
    (223.1, "REMARKS_________________________________________________________________________________________________"),
    (308.0, "RWY COND: DRY/WET/CONT                 BLEEDS: ON/OFF                 PACKS: ON/OFF                 ANTI ICE: ON/OFF"),
    (339.8, "TORA:__________________________TODR:________________________________TOW:_________________________________"),
    (371.5, "V1____________   VR____________   V2___________   VFTO___________STAB   TRIM___________   FLAPS_____________"),
    (456.4, "APT:_________________________________________   ATIS/TIME:_______________________________________________Z"),
    (488.2, "T.LVL_________________   RMY_________________   WIND_______________/______________   VIS/RVR_______________"),
    (520.0, "WX_______________________________   CLDS__________________________________________________________________"),
    (551.7, "TEMP__________________C   DEWPOINT__________________C   QNH_____________   TREND_____________________"),
    (583.5, "REMARKS_______________________________________________________________________________________________"),
    (668.4, "RWY COND: DRY/WET/CONT                                                                                                                ANTI ICE: ON/OFF"),
    (700.2, "VERF:___________   VAPP:___________   VAC:___________   LDA:___________   LDR:___________   LDW:____________"),
]

FORM_RULES = [255.7, 404.2, 616.1, 723.4]


def draw_form_page(pdf, data):
    pdf.showPage()
    _page_header(pdf, data)
    _rect(pdf, FRAME_X0, FRAME_TOP, FRAME_X1, FRAME_BOTTOM)

    for y, title in FORM_SECTIONS:
        _text_center(pdf, CENTER_X, y, title)

    for y, line in FORM_LINES:
        _text(pdf, 46.0, y, line)

    for y in FORM_RULES:
        _hline(pdf, 46.0, 549.3, y, width=0.8)


# --------------------------------------------------
# NAVLOG TABLE
# --------------------------------------------------

COLUMN_X = [
    34.8, 145.2, 176.6, 214.6, 265.4, 291.0, 323.5, 361.0, 401.6, 429.7,
    461.1, 497.8, 560.5,
]

# (top group label, first line, second line, first key, second key)
COLUMNS = [
    ("",        "WAYPOINT", "AIRWAY", "waypoint",           "airway"),
    ("",        "HDG",      "CRS",    "heading",            "course"),
    ("",        "FL",       "",       "flightLevel",        None),
    ("WIND",    "DIR/SPD",  "CMP",    "windDirectionSpeed", "windComponent"),
    ("",        "ISA",      "",       "isa",                None),
    ("SPD KT",  "TAS",      "GS",     "tas",                "gs"),
    ("DIST NM", "LEG",      "REM",    "legDistance",        "remainingDistance"),
    ("FUEL LB", "USED",     "REM",    "fuelUsed",           "fuelRemaining"),
    ("TIME",    "ETE",      "",       "ete",                None),
    ("TIME",    "LEG",      "REM",    "legTime",            "remainingTime"),
    ("",        "ETA",      "ATA",    "eta",                "ata"),
    ("",        "ACTUAL FUEL", "",    "actualFuel",         None),
]

TABLE_TOP = 36.3
# Continuation pages start their table flush with the frame rather than
# a point and a half below it, as the first navlog page does.
CONTINUATION_TOP = 34.8
HEADER_TOP_HEIGHT = 21.0
HEADER_BOTTOM_HEIGHT = 32.3
ROW_HEIGHT = 32.3
TABLE_BOTTOM_LIMIT = 780.0
BANNER_HEIGHT = 45.7


def _draw_table_header(pdf, y):
    top_bottom = y + HEADER_TOP_HEIGHT
    bottom_bottom = top_bottom + HEADER_BOTTOM_HEIGHT

    for line_y in (y, top_bottom, bottom_bottom):
        _hline(pdf, COLUMN_X[0], COLUMN_X[-1], line_y)

    # Every boundary is ruled through both header rows except the one
    # inside the TIME group, which spans ETE and the LEG/REM time pair.
    grouped_interior = set()
    index = 0
    while index < len(COLUMNS):
        group = COLUMNS[index][0]
        if group:
            last = index
            while last + 1 < len(COLUMNS) and COLUMNS[last + 1][0] == group:
                last += 1
            grouped_interior.update(range(index + 1, last + 1))
            index = last + 1
        else:
            index += 1

    for column_index, x in enumerate(COLUMN_X):
        _vline(pdf, x, top_bottom if column_index in grouped_interior else y, bottom_bottom)

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
        _text_center(pdf, center, y + 13.4, group, size=SIZE_TABLE)
        index = last + 1

    for column_index, (_, line1, line2, _, _) in enumerate(COLUMNS):
        left = COLUMN_X[column_index]
        center = (left + COLUMN_X[column_index + 1]) / 2

        if not line2:
            _text_center(pdf, center, top_bottom + 19.1, line1, size=SIZE_TABLE)
        elif column_index == 0:
            _text(pdf, left + 2.6, top_bottom + 14.6, line1, size=SIZE_TABLE)
            _text(pdf, left + 2.6, top_bottom + 24.7, line2, size=SIZE_TABLE)
        elif line1 == "ETA":
            # The reference sets this pair a shade higher and tighter than
            # the other stacked headings.
            _text_center(pdf, center, top_bottom + 14.2, line1, size=SIZE_TABLE)
            _text_center(pdf, center, top_bottom + 24.0, line2, size=SIZE_TABLE)
        else:
            _text_center(pdf, center, top_bottom + 14.6, line1, size=SIZE_TABLE)
            _text_center(pdf, center, top_bottom + 24.7, line2, size=SIZE_TABLE)

    return bottom_bottom


def _cell_lines(row, column):
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
    _hline(pdf, COLUMN_X[0], COLUMN_X[-1], y + ROW_HEIGHT)
    for x in COLUMN_X:
        _vline(pdf, x, y, y + ROW_HEIGHT)

    for column_index, column in enumerate(COLUMNS):
        lines = _cell_lines(row, column)
        left = COLUMN_X[column_index]
        center = (left + COLUMN_X[column_index + 1]) / 2

        baselines = [y + 19.1] if len(lines) == 1 else [y + 14.6, y + 24.7]

        for line_text, baseline in zip(lines, baselines):
            if column_index == 0:
                _text(pdf, left + 2.6, baseline, line_text, size=SIZE_TABLE)
            else:
                _text_center(pdf, center, baseline, line_text, size=SIZE_TABLE)

    return y + ROW_HEIGHT


def _draw_banner(pdf, left_text, right_text, y):
    bottom = y + BANNER_HEIGHT
    _hline(pdf, COLUMN_X[0], COLUMN_X[-1], bottom)
    _vline(pdf, COLUMN_X[0], y, bottom)
    _vline(pdf, COLUMN_X[-1], y, bottom)

    _text(pdf, COLUMN_X[0] + 2.6, y + 26.2, left_text)
    _text(pdf, 176.3, y + 26.2, right_text)

    return bottom


def _start_blank_page(pdf, data, top=TABLE_TOP):
    pdf.showPage()
    _page_header(pdf, data)
    _rect(pdf, FRAME_X0, FRAME_TOP, FRAME_X1, FRAME_BOTTOM)
    return top


def _start_table_page(pdf, data, top=CONTINUATION_TOP):
    return _draw_table_header(pdf, _start_blank_page(pdf, data, top))


def draw_navlog_pages(pdf, data):
    y = _start_table_page(pdf, data, top=TABLE_TOP)

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
    34.8, 80.4, 133.0, 180.3, 229.9, 315.0, 372.3, 414.1, 460.6, 508.6, 560.5,
]

AIRPORT_HEADERS = [
    "", "Airport", "ETA", "ATIS", "TWR/CTAF", "CLR", "GND", "ELEV", "LONGEST RWY", "",
]

AIRPORT_ROW_HEIGHT = 21.05


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
                _text(pdf, AIRPORT_COLUMN_X[index] + 2.7, y + 13.4, cell, size=SIZE_TABLE)
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
WIND_FIRST_X = 130.0
WIND_TMP_RIGHT = 194.6
WIND_STEP = 87.95
WIND_ROW_HEIGHT = 14.135


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

    winds_y = max(y + 21.0, 201.5)
    _text_center(pdf, CENTER_X, winds_y, "ENROUTE WINDS")

    header_y = winds_y + 28.0
    for index, band in enumerate(bands):
        band_x = WIND_FIRST_X + index * step
        _text(pdf, band_x + 1.0, header_y - 5.5, str(band).split("(")[0].strip())
        _text(pdf, band_x + 12.5, header_y + 5.6, "W/V")
        _text_right(pdf, WIND_TMP_RIGHT + index * step, header_y, "TMP")

    _text(pdf, WIND_IDENT_X, header_y, "IDENT")

    row_y = header_y + 19.8
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
    _text_right(pdf, 558.6, 802.6, f"TIME : {computed_time} Asia/Kolkata")


# --------------------------------------------------
# GENERATE PDF ENTRYPOINT (VTJOE)
# --------------------------------------------------


def generate_vtjoe_pdf(navlog):
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)

    file_name = f"VTJOE{int(datetime.now().timestamp() * 1000)}.pdf"
    absolute_path = os.path.join(OUTPUT_DIRECTORY, file_name)
    relative_path = os.path.join("generated", file_name)

    pdf = canvas.Canvas(absolute_path, pagesize=A4)

    draw_page_one(pdf, navlog)
    draw_form_page(pdf, navlog)
    y = draw_navlog_pages(pdf, navlog)
    draw_airport_info(pdf, navlog, y)
    draw_final_page(pdf, navlog)

    pdf.save()

    return relative_path
