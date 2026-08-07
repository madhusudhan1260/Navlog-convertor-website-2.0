import os
import re
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from common import (
    OUTPUT_DIRECTORY,
    NAV_COLUMNS,
    _cell_line_count,
    box,
    combined_row_value,
    field,
    find_value,
    labelled_value,
    line,
    route_header,
    set_page_height,
    value,
    write,
)

# --------------------------------------------------
# PAGE ONE (NAV LOG / OPS FPL SUMMARY)
# --------------------------------------------------
# Coordinates measured directly off VTVIK's own reference PDF via a text-
# bbox extraction - this page's layout (single-line banner title, DEP/
# DIST/TRACK + DEST/CRUISE/PAX rows, COMPUTED FUEL block, DIFFERENT
# LEVEL CALCULATION/ACTUALS block, dual DEP/ARR ATIS-CLEARANCE-RWY-V-
# speeds blocks) is unrelated to MLOVE/VTBBD's page 1 - it's its own
# template. VTVIK is A4-sized like MLOVE, so no page-height juggling is
# needed here.

TABLE_LEFT = 35
TABLE_WIDTH = 525

# Airport full names ForeFlight's export never carries - extend as new
# airports show up. Falls back to just the ICAO code when unknown.
AIRPORT_NAME_LOOKUP = {
    "VOTP": "TIRUPATI",
    "VOHY": "BEGUMPET",
    "VIDP": "DELHI",
    "VECC": "KOLKATA",
}


def _space_fl(s):
    """"FL450" -> "FL 450" - matches VTVIK's own spacing convention for
    flight levels quoted in prose fields (TOP CLIMB TEMP, level table)."""
    return re.sub(r"\bFL(\d)", r"FL \1", value(s))


def _cruise_tail(profile_text):
    """MAIN ROUTE wants just the cruise-speed portion of PLN PROFILE
    (the bit after "@ FLxxx - "), not the whole IFR/rules-prefixed
    string. Falls back to the full profile text if the pattern isn't
    found (still better than nothing)."""
    match = re.search(r"@\s*FL\d+\s*-\s*(.+)$", value(profile_text), re.IGNORECASE)
    return match.group(1).strip() if match else value(profile_text)


def draw_page_one(pdf, data):
    page1 = data.get("page1", {})
    flight = page1.get("flightInfo", {})
    time_info = page1.get("time", {})
    fuel = page1.get("fuel", {})
    weight = page1.get("weight", {})
    misc = page1.get("misc", {})
    header = page1.get("header", {})
    alternates = page1.get("alternates", [])
    level_calcs = data.get("levelCalculations", [])
    atc = data.get("atcFlightPlan", {})

    route_title = header.get("routeTitle") or data.get("routeTitle", "")
    reg_val = header.get("registration") or flight.get("registration", "")
    route_header(pdf, route_title, reg_val)

    box(pdf, TABLE_LEFT, 33, TABLE_WIDTH, 775)

    ac_type = find_value(header, flight, atc, "aircraftType", "type", "acType")
    date_str = flight.get("date", "")
    etd = time_info.get("etd", "")
    eta = time_info.get("eta", "")

    banner = f"- - - - - {reg_val} ({ac_type}) {date_str} NAV LOG/ OPS FPL FOR ETD {etd} (ETA {eta}) - - - - -"
    write(pdf, banner, TABLE_LEFT, 41, TABLE_WIDTH, {"size": 8.5, "align": "center", "lineBreak": False})

    dep_code = flight.get("departure", "")
    dest_code = flight.get("destination", "")
    dep_disp = f"{dep_code} - {AIRPORT_NAME_LOOKUP[dep_code]}" if dep_code in AIRPORT_NAME_LOOKUP else dep_code
    dest_disp = f"{dest_code} - {AIRPORT_NAME_LOOKUP[dest_code]}" if dest_code in AIRPORT_NAME_LOOKUP else dest_code

    dist_val = value(time_info.get("plannedRouteDistance"))
    track_val = value(time_info.get("track"))
    track_disp = f"{track_val} DEG" if track_val else ""
    pax_val = weight.get("pax", "")

    write(pdf, "DEP", 50, 61, 25, {"size": 8.5, "lineBreak": False})
    write(pdf, ":", 77, 61, 8, {"size": 8.5, "lineBreak": False})
    write(pdf, dep_disp, 83, 61, 155, {"size": 8.5, "lineBreak": False})

    write(pdf, "DIST", 251, 60, 25, {"size": 8.5, "lineBreak": False})
    write(pdf, ":", 302, 60, 8, {"size": 8.5, "lineBreak": False})
    write(pdf, dist_val, 310, 60, 60, {"size": 8.5, "lineBreak": False})

    write(pdf, "TRACK", 452, 61, 35, {"size": 8.5, "lineBreak": False})
    write(pdf, ":", 487, 61, 8, {"size": 8.5, "lineBreak": False})
    write(pdf, track_disp, 492, 61, 60, {"size": 8.5, "lineBreak": False})

    write(pdf, "DEST", 50, 77, 25, {"size": 8.5, "lineBreak": False})
    write(pdf, ":", 77, 77, 8, {"size": 8.5, "lineBreak": False})
    write(pdf, dest_disp, 83, 77, 155, {"size": 8.5, "lineBreak": False})

    write(pdf, "CRUISE", 251, 77, 30, {"size": 8.5, "lineBreak": False})
    write(pdf, ":", 302, 77, 8, {"size": 8.5, "lineBreak": False})
    write(pdf, "PAX", 452, 77, 20, {"size": 8.5, "lineBreak": False})
    write(pdf, ":", 487, 77, 8, {"size": 8.5, "lineBreak": False})
    write(pdf, pax_val, 492, 77, 40, {"size": 8.5, "lineBreak": False})

    cruise_text = value(misc.get("plannedProfile")).upper()
    write(pdf, cruise_text, 310, 82, 155, {"size": 7.5})

    flight_level = flight.get("flightLevel", "")
    main_route_str = f"{flight_level} - {_cruise_tail(misc.get('plannedProfile'))} {data.get('routes', {}).get('mainRoute', '')}".strip()
    write(pdf, f"MAIN ROUTE : {main_route_str}", TABLE_LEFT + 13, 100, TABLE_WIDTH - 20, {"size": 8.5, "lineBreak": False})

    write(pdf, "PIC", TABLE_LEFT + 13, 117, 20, {"size": 8.5, "lineBreak": False})
    write(pdf, ":", 65, 117, 8, {"size": 8.5, "lineBreak": False})
    write(pdf, flight.get("pic", ""), 70, 117, 220, {"size": 8.5, "lineBreak": False})

    write(pdf, "FO", 299, 117, 15, {"size": 8.5, "lineBreak": False})
    write(pdf, ":", 313, 117, 8, {"size": 8.5, "lineBreak": False})
    write(pdf, flight.get("fo", ""), 318, 117, 220, {"size": 8.5, "lineBreak": False})

    # ---- Computed fuel & weights ----
    fuel_pairs = [
        ("COMPUTED FUEL", fuel.get("computedFuel"), "BLOCK FUEL", fuel.get("ramp")),
        ("MIN. TRIP FUEL", fuel.get("minTripFuel"), "TAKE OFF FUEL", fuel.get("takeoff")),
        ("MAX. TRIP FUEL", fuel.get("maxTripFuel"), "LANDING FUEL", fuel.get("landing")),
        ("TOP CLIMB TEMP", _space_fl(time_info.get("topClimbTemp")), "WIND", value(time_info.get("averageWinds")).upper()),
    ]
    rows_y = [138, 152, 166, 180]
    for (l1, v1, l2, v2), y in zip(fuel_pairs, rows_y):
        write(pdf, l1, 50, y, 80, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 131, y, 8, {"size": 8.5, "lineBreak": False})
        v1_disp = f"{value(v1)} LBS" if v1 not in (None, "") and "TEMP" not in l1 else value(v1)
        write(pdf, v1_disp, 137, y, 78, {"size": 8.5, "align": "right", "lineBreak": False})

        write(pdf, l2, 301, y, 74, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 375, y, 8, {"size": 8.5, "lineBreak": False})
        v2_disp = f"{value(v2)} LBS" if v2 not in (None, "") and l2 != "WIND" else value(v2)
        write(pdf, v2_disp, 381, y, 89, {"size": 8.5, "align": "right", "lineBreak": False})

    write(
        pdf,
        "- - - - - - - - PLAN TIME & FUEL - - - - - - - - - - - - - - - - - - - - - - - - - - - - - PLAN WT (in LBS) - - - - - - - - - - - - - - - -",
        TABLE_LEFT,
        199,
        TABLE_WIDTH,
        {"size": 8, "align": "center", "lineBreak": False},
    )

    plan_rows = [
        ("TRIP", fuel.get("trip"), find_value(fuel, "tripTime", "trip_time")),
        ("TAXI", fuel.get("taxi"), ""),
        ("CONTINGENCY 5%", fuel.get("contingency"), find_value(fuel, "contingencyTime", "contingency_time")),
        ("FINAL RESERVE FUEL", fuel.get("finalReserve"), find_value(fuel, "finalReserveTime", "final_reserve_time")),
        ("XTRA", fuel.get("extra"), find_value(fuel, "extraEndurance", "extra_endurance")),
        ("ALTN1", fuel.get("alternate"), find_value(fuel, "alternateTime", "alternate_time")),
        ("ALTN2", fuel.get("alternate2Fuel"), find_value(fuel, "alternate2Time", "alternate2_time")),
    ]
    weight_rows = [
        ("BASIC WT", weight.get("basicOperatingWeight")),
        ("LOAD", weight.get("load")),
        ("ZERO FUEL", weight.get("zeroFuelWeight")),
        ("T.OFF WT", weight.get("takeoffWeight")),
        ("LAND WT", weight.get("estimatedLandingWeight")),
    ]
    plan_rows_y = [218, 232, 246, 260, 274, 288, 302]
    weight_rows_y = [218, 232, 246, 260, 274]

    for (label, fuel_val, time_val), y in zip(plan_rows, plan_rows_y):
        write(pdf, label, 50, y, 100, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 151, y, 8, {"size": 8.5, "lineBreak": False})
        write(pdf, time_val, 161, y, 35, {"size": 8.5, "lineBreak": False})
        fuel_disp = f"{value(fuel_val)} LBS" if fuel_val not in (None, "") else ""
        write(pdf, fuel_disp, 190, y, 48, {"size": 8.5, "align": "right", "lineBreak": False})

    for (label, val), y in zip(weight_rows, weight_rows_y):
        write(pdf, label, 301, y, 60, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 361, y, 8, {"size": 8.5, "lineBreak": False})
        val_disp = f"{value(val)} LBS" if val not in (None, "") else ""
        write(pdf, val_disp, 367, y, 54, {"size": 8.5, "align": "right", "lineBreak": False})

    alt1 = alternates[0] if len(alternates) > 0 else {}
    alt2 = alternates[1] if len(alternates) > 1 else {}

    write(pdf, "ALTN", 301, 291, 30, {"size": 8.5, "lineBreak": False})
    write(pdf, ":", 329, 291, 8, {"size": 8.5, "lineBreak": False})
    alt1_dist = field(alt1, "distance")
    if alt1_dist and not alt1_dist.upper().endswith("NM"):
        alt1_dist = f"{alt1_dist}NM"
    write(pdf, alt1_dist, 334, 291, 40, {"size": 8.5, "lineBreak": False})

    min_divert = fuel.get("minDivertFuel")
    write(pdf, "MIN DIVERT FUEL:", 384, 291, 90, {"size": 8.5, "lineBreak": False})
    write(pdf, f"{value(min_divert)} LBS" if min_divert not in (None, "") else "", 470, 291, 60, {"size": 8.5, "lineBreak": False})

    write(pdf, "FIRST ALTN ROUTE :", 301, 305, 100, {"size": 8.5, "lineBreak": False})
    write(pdf, value(field(alt1, "route")).replace("Route", "").strip(), 395, 305, 150, {"size": 8.5, "lineBreak": False})

    write(pdf, "SECOND ALTN ROUTE :", 301, 320, 105, {"size": 8.5, "lineBreak": False})
    write(pdf, value(field(alt2, "route")).replace("Route", "").strip(), 407, 320, 150, {"size": 8.5, "lineBreak": False})

    line(pdf, 161, 322, 233, 322)
    write(pdf, "ENDURANCE", 90, 331, 60, {"size": 8.5, "lineBreak": False})
    write(pdf, ":", 151, 331, 8, {"size": 8.5, "lineBreak": False})
    write(pdf, fuel.get("enduranceTime", ""), 161, 331, 35, {"size": 8.5, "lineBreak": False})
    computed_fuel = fuel.get("computedFuel")
    write(pdf, f"{value(computed_fuel)} LBS" if computed_fuel not in (None, "") else "", 195, 331, 43, {"size": 8.5, "align": "right", "lineBreak": False})

    # ---- Different level calculation / actuals ----
    write(
        pdf,
        "- - - - - - - - - DIFFERENT LEVEL CALCULATION - - - - - - - - - - - - - - - - - - - - - - - - - - ACTUALS - - - - - - - - - - - - - - - - - - -",
        TABLE_LEFT,
        350,
        TABLE_WIDTH,
        {"size": 8, "align": "center", "lineBreak": False},
    )

    write(pdf, "FL", 57, 378, 20, {"size": 8.5, "bold": True, "lineBreak": False})
    write(pdf, "WC", 104, 378, 20, {"size": 8.5, "bold": True, "lineBreak": False})
    write(pdf, "TIME", 140, 378, 30, {"size": 8.5, "bold": True, "lineBreak": False})
    write(pdf, "TRIP", 196, 378, 30, {"size": 8.5, "bold": True, "lineBreak": False})

    level_rows_y = [392, 406, 420, 434, 448]
    for row, y in zip(level_calcs[:5], level_rows_y):
        fl_disp = value(row.get("fl"))
        if fl_disp and not fl_disp.upper().startswith("FL"):
            fl_disp = f"FL {fl_disp}"
        write(pdf, fl_disp, 57, y, 30, {"size": 8.5, "lineBreak": False})
        write(pdf, row.get("wc", ""), 104, y, 25, {"size": 8.5, "lineBreak": False})
        write(pdf, row.get("time", ""), 140, y, 40, {"size": 8.5, "lineBreak": False})
        trip_val = value(row.get("trip"))
        write(pdf, f"{trip_val} LBS" if trip_val else "", 186, y, 45, {"size": 8.5, "lineBreak": False})

    actuals_left = [
        ("PAX", 375), ("CREW", 396), ("SOB", 417), ("FIC", 438), ("ADC", 458),
    ]
    for label, y in actuals_left:
        write(pdf, label, 264, y, 30, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 285, y, 8, {"size": 8.5, "lineBreak": False})
        line(pdf, 291, y + 8, 332, y + 8)

    actuals_mid = [
        ("ON BLK FUEL", 375), ("OFF BLK FUEL", 396), ("FUEL USED", 417), ("BTIME", 458),
    ]
    for label, y in actuals_mid:
        write(pdf, label, 347, y, 65, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 410, y, 8, {"size": 8.5, "lineBreak": False})
        line(pdf, 416, y + 8, 457, y + 8)

    actuals_right = [
        ("C/OFF", 375), ("T/O", 396), ("LDG", 417), ("C/ON", 438), ("F/T", 458),
    ]
    for label, y in actuals_right:
        write(pdf, label, 466, y, 30, {"size": 8.5, "align": "right", "lineBreak": False})
        write(pdf, ":", 496, y, 8, {"size": 8.5, "lineBreak": False})
        line(pdf, 501, y + 8, 543, y + 8)

    # ---- ATIS / clearance / runway / V-speed blocks (dep + arr) ----
    line(pdf, TABLE_LEFT, 476, TABLE_LEFT + TABLE_WIDTH, 476)

    def atis_block(prefix, atis_key, clearance_key, taxi_key, y0, operational):
        labelled_value(pdf, f"{prefix} ATIS", operational.get(atis_key), TABLE_LEFT, y0, 55, TABLE_WIDTH - 10)
        labelled_value(pdf, f"{prefix} CLEARANCE", operational.get(clearance_key), TABLE_LEFT, y0 + 19, 90, TABLE_WIDTH - 10)
        labelled_value(pdf, "TAXI CLEARANCE", operational.get(taxi_key), TABLE_LEFT, y0 + 37, 95, TABLE_WIDTH - 10)

        rwy_y = y0 + 56
        write(pdf, "RWY", TABLE_LEFT + 13, rwy_y, 25, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 77, rwy_y, 8, {"size": 8.5, "lineBreak": False})
        line(pdf, 82, rwy_y + 8, 134, rwy_y + 8)
        write(pdf, "FLAPS", 143, rwy_y, 32, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 178, rwy_y, 8, {"size": 8.5, "lineBreak": False})
        line(pdf, 184, rwy_y + 8, 235, rwy_y + 8)
        write(pdf, "RWY: DRY / WET / CONT   A/I: OFF/ON", 245, rwy_y, 220, {"size": 8.5, "lineBreak": False})

        v_y = rwy_y + 22
        v_labels = ["V1", "VR", "V2", "Vapp", "VFS"]
        v_x = [50, 139, 231, 321, 420]
        for label, x in zip(v_labels, v_x):
            write(pdf, f"{label}:", x, v_y, 30, {"size": 8.5, "lineBreak": False})
            line(pdf, x + (24 if len(label) <= 2 else 32), v_y + 8, x + (24 if len(label) <= 2 else 32) + 68, v_y + 8)

        return v_y + 18

    operational = page1.get("operational", {})
    y_after_dep = atis_block("DEP", "departureAtis", "departureClearance", "depTaxiClearance", 491, operational)
    line(pdf, TABLE_LEFT, y_after_dep, TABLE_LEFT + TABLE_WIDTH, y_after_dep)
    y_after_arr = atis_block("ARR", "arrivalAtis", "arrivalClearance", "arrTaxiClearance", y_after_dep + 15, operational)
    line(pdf, TABLE_LEFT, y_after_arr, TABLE_LEFT + TABLE_WIDTH, y_after_arr)

    labelled_value(pdf, "DEST ALTNATIS", operational.get("destAltnAtis"), TABLE_LEFT - 2, y_after_arr + 16, 70, TABLE_WIDTH - 10)

    line(pdf, TABLE_LEFT, 727, TABLE_LEFT + TABLE_WIDTH, 727, 1.2)

    write(
        pdf,
        "I certify that all my licenses, ratings etc are current / valid and I am legally/ medically fit for operating flight.",
        TABLE_LEFT,
        740,
        TABLE_WIDTH,
        {"size": 8.5, "align": "center", "lineBreak": False},
    )

    write(pdf, "PILOT SIGN :", TABLE_LEFT + 13, 755, 70, {"size": 8.5, "lineBreak": False})
    write(pdf, "LICS NO :", TABLE_LEFT + 13, 767, 70, {"size": 8.5, "lineBreak": False})
    write(pdf, "BA NO :", TABLE_LEFT + 13, 779, 70, {"size": 8.5, "lineBreak": False})

    write(pdf, "COPILOT SIGN :", 314, 755, 80, {"size": 8.5, "lineBreak": False})
    write(pdf, "LICS NO :", 314, 767, 70, {"size": 8.5, "lineBreak": False})
    write(pdf, "BA NO :", 314, 779, 70, {"size": 8.5, "lineBreak": False})


# --------------------------------------------------
# NAVLOG TABLE (PAGES 2 & 3) - same column model as MLOVE/VTBBD, just
# a wider table (525pt) starting at x=35 to match VTVIK's own frame.
# --------------------------------------------------


def _draw_table_header(pdf, y):
    x = TABLE_LEFT
    top_header_height = 18
    bottom_header_height = 34
    total_header_height = top_header_height + bottom_header_height
    font_size = 7.5

    scale = TABLE_WIDTH / 496.0
    idx = 0
    while idx < len(NAV_COLUMNS):
        key, top_title, bottom_title, base_width = NAV_COLUMNS[idx]
        width = base_width * scale

        if top_title:
            span_width = width
            next_idx = idx + 1
            while next_idx < len(NAV_COLUMNS) and NAV_COLUMNS[next_idx][1] == top_title:
                span_width += NAV_COLUMNS[next_idx][3] * scale
                next_idx += 1

            box(pdf, x, y, span_width, top_header_height)
            write(pdf, top_title, x + 2, y + 12, span_width - 4, {"size": font_size, "align": "center", "lineBreak": False})

            sub_x = x
            for sub_i in range(idx, next_idx):
                _, _, s_bottom, s_base_width = NAV_COLUMNS[sub_i]
                s_width = s_base_width * scale
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


def _draw_table_rows(pdf, rows, start_y, maximum_y):
    y = start_y
    if rows is None:
        rows = []

    font_size = 7.5
    line_height = font_size + 1
    min_height = 26
    vertical_padding = 4
    scale = TABLE_WIDTH / 496.0

    for index, row in enumerate(rows):
        max_lines = 1
        for key, _, _, base_width in NAV_COLUMNS:
            cell_text = combined_row_value(row, key)
            max_lines = max(max_lines, _cell_line_count(cell_text, font_size, base_width * scale))

        content_height = max_lines * line_height + vertical_padding
        height = max(min_height, content_height)

        if y + height > maximum_y:
            return {"y": y, "remaining": rows[index:]}

        x = TABLE_LEFT
        for key, _, _, base_width in NAV_COLUMNS:
            width = base_width * scale
            box(pdf, x, y, width, height)
            cell_text = combined_row_value(row, key)
            line_count = _cell_line_count(cell_text, font_size, width)
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


def _draw_table_title(pdf, title_left, title_right, y):
    banner_height = 24
    box(pdf, TABLE_LEFT, y, TABLE_WIDTH, banner_height)
    text_y = y + 15

    write(pdf, title_left, TABLE_LEFT + 6, text_y, 180, {"size": 8.5, "lineBreak": False})
    write(pdf, title_right, TABLE_LEFT + 190, text_y, 320, {"size": 8.5, "lineBreak": False})

    return y + banner_height


def draw_pages_two_and_three(pdf, data):
    title = data.get("page1", {}).get("header", {}).get("routeTitle", "")
    registration = data.get("page1", {}).get("header", {}).get("registration", "")

    pdf.showPage()
    route_header(pdf, title, registration)
    box(pdf, TABLE_LEFT, 32, TABLE_WIDTH, 728)

    y = _draw_table_header(pdf, 32)
    main_result = _draw_table_rows(pdf, data.get("mainNavlog", []), y, 680)
    y = main_result["y"]

    alternate_name = data.get("page1", {}).get("flightInfo", {}).get("alternate1", "")
    alternate_route = data.get("routes", {}).get("alternate1Route", "")
    clean_alt_route = value(alternate_route).replace("Route", "").strip()

    title_left = f"Alternate route for {alternate_name}"
    title_right = f"Route {clean_alt_route}" if clean_alt_route else ""

    y = _draw_table_title(pdf, title_left, title_right, y)
    alternate_result = _draw_table_rows(pdf, data.get("alternate1Navlog", []), y, 744)

    pdf.showPage()
    route_header(pdf, title, registration)
    box(pdf, TABLE_LEFT, 32, TABLE_WIDTH, 728)

    y = _draw_table_header(pdf, 32)

    remaining_rows = main_result["remaining"] + alternate_result["remaining"]
    alt2_rows = data.get("alternate2Navlog", [])

    if remaining_rows:
        continuation = _draw_table_rows(pdf, remaining_rows, y, 400)
        y = continuation["y"]

    if alt2_rows:
        alternate2_name = data.get("page1", {}).get("flightInfo", {}).get("alternate1", "")
        alternate2_route = data.get("routes", {}).get("alternate2Route", "")
        clean_alt2_route = value(alternate2_route).replace("Route", "").strip()
        y = _draw_table_title(
            pdf,
            f"Alternate route for {alternate2_name}",
            f"Route {clean_alt2_route}" if clean_alt2_route else "",
            y,
        )
        continuation2 = _draw_table_rows(pdf, alt2_rows, y, 690)
        y = continuation2["y"]

    y += 22
    write(pdf, "AIRPORT INFO", TABLE_LEFT, y, 150, {"size": 8.5, "bold": False, "lineBreak": False})

    y += 20

    scale = TABLE_WIDTH / 496.0
    airport_columns = [
        ("type", "", 40),
        ("airport", "Airport", 45),
        ("eta", "ETA", 50),
        ("atis", "ATIS", 50),
        ("tower", "TWR/CTAF", 72),
        ("clearance", "CLR", 65),
        ("ground", "GND", 48),
        ("elevation", "ELEV", 46),
        ("longestRunway", "LONGEST RWY", 80),
    ]

    x = TABLE_LEFT
    for _, heading, base_width in airport_columns:
        width = base_width * scale
        box(pdf, x, y, width, 22)
        write(pdf, heading, x + 2, y + 8, width - 4, {"size": 7.5, "align": "center"})
        x += width

    y += 22

    for airport in data.get("airportInformation", []):
        x = TABLE_LEFT
        for key, _, base_width in airport_columns:
            width = base_width * scale
            box(pdf, x, y, width, 22)
            airport_value = airport.get(key)
            if key == "longestRunway":
                r_num = value(airport.get("longestRunway") or airport.get("runway"))
                r_len = value(airport.get("runwayLength"))
                airport_value = f"{r_num} {r_len}".strip()

            write(pdf, airport_value, x + 2, y + 8, width - 4, {"size": 7.5, "align": "center"})
            x += width
        y += 22


# --------------------------------------------------
# PAGE FOUR (ATC FLIGHT PLAN + ENROUTE WINDS)
# --------------------------------------------------


def draw_page_four(pdf, data):
    title = data.get("page1", {}).get("header", {}).get("routeTitle", "")
    registration = data.get("page1", {}).get("header", {}).get("registration", "")
    atc = data.get("atcFlightPlan", {})

    pdf.showPage()

    route_header(pdf, title, registration)
    box(pdf, TABLE_LEFT, 26, TABLE_WIDTH, 734)

    write(
        pdf,
        atc.get("title", f"ATC FLIGHT PLAN {field(atc, 'departure')} to {field(atc, 'destination')}"),
        TABLE_LEFT + 60,
        48,
        TABLE_WIDTH - 120,
        {"size": 9, "align": "center", "lineBreak": False},
    )

    write(
        pdf,
        ". . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .",
        TABLE_LEFT + 100,
        60,
        TABLE_WIDTH - 200,
        {"size": 8, "align": "center", "lineBreak": False},
    )

    flight_plan_text = find_value(
        atc,
        "flightPlanText", "flight_plan_text", "fplText", "fpl_text",
        "flightPlan", "flight_plan", "text", "planText", "plan_text",
        "icaoText", "icao_text", "fpl",
    )
    if flight_plan_text:
        write(pdf, flight_plan_text, TABLE_LEFT + 10, 76, TABLE_WIDTH - 20, {"size": 8})

    table_left = TABLE_LEFT + 10
    table_width = TABLE_WIDTH - 20

    write(
        pdf,
        "ENROUTE WINDS",
        table_left,
        180,
        table_width,
        {"size": 8.5, "align": "center", "lineBreak": False},
    )

    enroute_data = data.get("enrouteWinds", {})
    if isinstance(enroute_data, dict):
        bands = enroute_data.get("bands", [])
        wind_rows = list(enroute_data.get("rows", []))
        for key, val in enroute_data.items():
            if key in ("bands", "rows"):
                continue
            if isinstance(val, list) and val and isinstance(val[0], dict):
                wind_rows.extend(val)
    else:
        bands = data.get("enrouteWindBands", [])
        wind_rows = data.get("enrouteWinds", []) or []

    num_bands = max(len(bands), 1)

    ident_col_width = 70
    available_width = table_width - ident_col_width
    pair_width = available_width / num_bands
    wv_width = pair_width * 0.65
    tmp_width = pair_width * 0.35

    y = 205
    row_height = 11.0

    write(pdf, "IDENT", table_left, y, ident_col_width, {"size": 8, "lineBreak": False})

    for b_idx, band in enumerate(bands):
        b_label = str(band).split("(")[0].strip()
        band_x = table_left + ident_col_width + (b_idx * pair_width)

        write(pdf, f"{b_label}\nW/V", band_x, y, wv_width, {"size": 7.5, "align": "center"})
        write(pdf, "TMP", band_x + wv_width, y + 7, tmp_width, {"size": 7.5, "align": "center", "lineBreak": False})

    y += 22

    for row in wind_rows:
        ident_str = value(row.get("identifier"))
        write(pdf, ident_str, table_left, y, ident_col_width, {"size": 8, "lineBreak": False})

        cells = row.get("values", [])
        for c_idx in range(min(len(cells), num_bands)):
            cell = cells[c_idx]
            band_x = table_left + ident_col_width + (c_idx * pair_width)

            raw_wind = value(cell.get("wind"))
            clean_wind = raw_wind.split("\n")[-1].strip() if "\n" in raw_wind else raw_wind.strip()
            if clean_wind.startswith("(") and ")" in clean_wind:
                clean_wind = clean_wind.split(")")[-1].strip()

            raw_isa = value(cell.get("isa")).strip()

            write(pdf, clean_wind, band_x, y, wv_width, {"size": 8, "align": "center", "lineBreak": False})
            write(pdf, raw_isa, band_x + wv_width, y, tmp_width, {"size": 8, "align": "center", "lineBreak": False})

        y += row_height

    page_height = A4[1]
    pdf.setFont("Courier-Bold", 8.5)
    end_report_text = "**************     END OF THE REPORT    **************"
    pdf.drawCentredString(TABLE_LEFT + TABLE_WIDTH / 2, page_height - 728, end_report_text)

    computed_date = datetime.now().strftime("%d-%m-%Y")
    computed_time = datetime.now().strftime("%H:%M:%S")

    write(pdf, f"COMPUTED DATE : {computed_date}", TABLE_LEFT, 756, 220, {"size": 8.5, "lineBreak": False, "padding": 0})
    write(pdf, f"TIME : {computed_time} UTC", TABLE_LEFT + TABLE_WIDTH - 220, 756, 220, {"size": 8.5, "align": "right", "lineBreak": False, "padding": 0})


# --------------------------------------------------
# GENERATE PDF ENTRYPOINT (VTVIK)
# --------------------------------------------------


def generate_vtvik_pdf(navlog):
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)

    file_name = f"VTVIK{int(datetime.now().timestamp() * 1000)}.pdf"
    absolute_path = os.path.join(OUTPUT_DIRECTORY, file_name)
    relative_path = os.path.join("generated", file_name)

    set_page_height(A4[1])
    pdf = canvas.Canvas(absolute_path, pagesize=A4)

    draw_page_one(pdf, navlog)
    draw_pages_two_and_three(pdf, navlog)
    draw_page_four(pdf, navlog)

    pdf.save()

    return relative_path
