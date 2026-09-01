import os
import re
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from common import (
    FONT_NAME,
    OUTPUT_DIRECTORY,
    NAV_COLUMNS,
    _cell_line_count,
    box,
    combined_row_value,
    field,
    find_value,
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

TABLE_LEFT = 34.77
TABLE_WIDTH = 525.74

# Airport full names ForeFlight's export never carries. Kept in sync with
# default1.py's own table - both fall back further, to the nearest navaid
# city the navlog itself carries, for anything not listed here.
AIRPORT_NAME_LOOKUP = {
    "VAAH": "AHMEDABAD",
    "VAHS": "HIRASAR",
    "VABO": "VADODARA",
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
    "VAID": "INDORE",
    "VABP": "BHOPAL",
    "VOTR": "TIRUCHIRAPPALLI",
    "VOBZ": "VIJAYAWADA",
    "VARK": "RAJKOT",
}


def _navaid_city(rows, from_end=False):
    """ForeFlight prints the nearest navaid's city against each waypoint
    ("AHMEDABAD 113.1") - the first on the route is the departure city and
    the last the destination city. Same fallback default1.py uses."""
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


def _city_name(code, rows, from_end=False):
    code = value(code)
    return AIRPORT_NAME_LOOKUP.get(code.upper()) or _navaid_city(rows, from_end=from_end)


def _wrap(content, size, max_width, font=FONT_NAME):
    """Word-wraps content to max_width at size - same greedy algorithm
    default1.py's own _wrap uses, since VTVIK's PLN PROFILE/alternate
    route text wraps onto reference PDF the same way."""
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


def _underscore_row(pdf, label, gap_before, gap_after, underscore_count, val, x0, y, size=9.4):
    """The DEP/ARR ATIS-CLEARANCE rows aren't drawn lines at all in the
    reference PDF - they're a single text string with a literal
    underscore fill for the operator to write into by hand. When actual
    operational data exists, it's overlaid starting where the fill
    begins."""
    prefix = f"{label}{' ' * gap_before}:{' ' * gap_after}"
    write(pdf, f"{prefix}{'_' * underscore_count}", x0 - 2, y, 500, {"size": size, "lineBreak": False})

    v = value(val)
    if v:
        overlay_x = x0 + stringWidth(prefix, FONT_NAME, size)
        write(pdf, v, overlay_x - 2, y, underscore_count * 10, {"size": size, "lineBreak": False})


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


def _drop_origin_row(rows):
    """An alternate plan starts where the main route ended, so ForeFlight
    repeats that airport as the block's own origin row - no heading, no
    course. The operator's sheet leaves it out (same quirk default1.py's
    own alternate blocks have)."""
    if rows and not value(rows[0].get("heading")).strip(" -"):
        return rows[1:]
    return rows


def _rank(name):
    """PIC/FO print with a "CAPT" prefix unless the operator already typed
    one - the same convention every other template applies at render
    time (claude.py stores the bare name)."""
    name = value(name).upper()
    if not name:
        return ""
    if re.match(r"^(CAPT|CPT|CMDR|MR|MS|MRS|FO|F/O)\b", name):
        return name
    return f"CAPT {name}"


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

    # Frame box measured directly off the reference PDF's own rect (same
    # frame default1.py uses: x 34.39-560.89, y 34.39-806.00).
    box(pdf, 34.39, 34.39, 526.5, 771.61)

    ac_type = find_value(header, flight, atc, "aircraftType", "type", "acType")
    date_str = flight.get("date", "")
    etd = time_info.get("etd", "")
    eta = time_info.get("eta", "")

    banner = f"- - - - - {reg_val} ({ac_type}) {date_str} NAV LOG/ OPS FPL FOR ETD {etd} (ETA {eta}) - - - - -"
    write(pdf, banner, TABLE_LEFT, 47.43, TABLE_WIDTH, {"size": 9.4, "align": "center", "lineBreak": False})

    main_navlog = data.get("mainNavlog", [])
    dep_code = value(flight.get("departure", ""))
    dest_code = value(flight.get("destination", ""))
    dep_name = _city_name(dep_code, main_navlog)
    dest_name = _city_name(dest_code, main_navlog, from_end=True)

    dist_val = value(time_info.get("plannedRouteDistance"))
    track_val = value(time_info.get("track"))
    track_disp = f"{track_val} DEG" if track_val else ""
    pax_val = weight.get("pax", "")

    # ---- DEP/DEST + DIST/CRUISE + TRACK/PAX ----
    write(pdf, "DEP", 48.52, 69.40, 25, {"size": 9.4, "lineBreak": False})
    write(pdf, f":{dep_code}", 74.95, 69.40, 45, {"size": 9.4, "lineBreak": False})
    if dep_name:
        write(pdf, f"-{dep_name}", 112.98, 69.40, 140, {"size": 9.4, "lineBreak": False})

    write(pdf, "DIST", 249.22, 66.06, 25, {"size": 9.4, "lineBreak": False})
    write(pdf, ":", 300.21, 66.06, 8, {"size": 9.4, "lineBreak": False})
    write(pdf, dist_val, 308.08, 66.06, 60, {"size": 9.4, "lineBreak": False})

    write(pdf, f"TRACK:{track_disp}", 449.92, 69.40, 100, {"size": 9.4, "lineBreak": False})

    write(pdf, "DEST", 48.52, 83.54, 25, {"size": 9.4, "lineBreak": False})
    write(pdf, f":{dest_code}", 74.95, 83.54, 45, {"size": 9.4, "lineBreak": False})
    if dest_name:
        write(pdf, f"-{dest_name}", 112.98, 83.54, 140, {"size": 9.4, "lineBreak": False})

    write(pdf, "CRUISE", 249.22, 83.54, 30, {"size": 9.4, "lineBreak": False})
    write(pdf, ":", 300.21, 83.54, 8, {"size": 9.4, "lineBreak": False})

    write(pdf, "PAX", 449.92, 83.54, 20, {"size": 9.4, "lineBreak": False})
    write(pdf, f":{pax_val}", 484.69, 83.54, 40, {"size": 9.4, "lineBreak": False})

    # The PLN PROFILE text word-wraps across the DIST/CRUISE value column,
    # same as default1.py's own CRUISE wrap (just a narrower, 2-row-tall
    # slot here rather than a dedicated 4-line block).
    cruise_lines = _wrap(value(misc.get("plannedProfile")).upper(), 7.5, 140.0)
    cruise_y = 78.42
    for cruise_line in cruise_lines[:3]:
        write(pdf, cruise_line, 308.08, cruise_y, 155, {"size": 7.5, "lineBreak": False})
        cruise_y += 8.91

    flight_level = flight.get("flightLevel", "")
    main_route_str = f"{flight_level} - {_cruise_tail(misc.get('plannedProfile'))} {data.get('routes', {}).get('mainRoute', '')}".strip()
    write(pdf, f"MAIN ROUTE : {main_route_str}", 46.27, 106.27, TABLE_WIDTH - 20, {"size": 9.4, "lineBreak": False})

    write(pdf, f"PIC : {_rank(flight.get('pic'))}".rstrip(), 46.27, 123.41, 240, {"size": 9.4, "lineBreak": False})
    write(pdf, f"FO : {_rank(flight.get('fo'))}".rstrip(), 297.14, 123.41, 240, {"size": 9.4, "lineBreak": False})

    # ---- Computed fuel & weights ----
    # COMPUTED FUEL is the RAMP figure and BLOCK FUEL is Flight Fuel - the
    # same "ramp"/"flight" keys every other plan-time template reads.
    # (Previously read "computedFuel"/"ramp" here, which happened to read
    # blank/wrong values because VTVIK didn't populate "required" fuel
    # until it joined PLAN_TIME_TEMPLATES - now that it does, the mismatch
    # became visible: COMPUTED FUEL was showing MIN. TRIP FUEL's own
    # figure instead of RAMP.)
    landing_fuel = find_value(fuel, "landingReported") or value(fuel.get("landing"))

    fuel_pairs = [
        ("COMPUTED FUEL", fuel.get("ramp"), "BLOCK FUEL", fuel.get("flight")),
        ("MIN. TRIP FUEL", fuel.get("minTripFuel"), "TAKE OFF FUEL", fuel.get("takeoff")),
        ("MAX. TRIP FUEL", fuel.get("maxTripFuel"), "LANDING FUEL", landing_fuel),
    ]
    fuel_rows_y = [144.30, 158.43, 172.57]
    for (l1, v1, l2, v2), y in zip(fuel_pairs, fuel_rows_y):
        write(pdf, l1, 48.52, y, 90, {"size": 9.4, "lineBreak": False})
        write(pdf, ":", 128.86, y, 8, {"size": 9.4, "lineBreak": False})
        v1_disp = f"{value(v1)} LBS" if v1 not in (None, "") else ""
        write(pdf, v1_disp, 137, y, 78.06, {"size": 9.4, "align": "right", "lineBreak": False})

        write(pdf, l2, 299.39, y, 74, {"size": 9.4, "lineBreak": False})
        write(pdf, ":", 373.21, y, 8, {"size": 9.4, "lineBreak": False})
        v2_disp = f"{value(v2)} LBS" if v2 not in (None, "") else ""
        write(pdf, v2_disp, 391.16, y, 78.39, {"size": 9.4, "align": "right", "lineBreak": False})

    # TOP CLIMB TEMP/WIND is a genuinely different row shape from the three
    # above it - label+colon+value all run together with no value column.
    write(pdf, f"TOP CLIMB TEMP:{_space_fl(time_info.get('topClimbTemp'))}", 48.52, 186.71, 240, {"size": 9.4, "lineBreak": False})
    write(pdf, "WIND", 299.39, 186.71, 30, {"size": 9.4, "lineBreak": False})
    write(pdf, ":", 373.21, 186.71, 8, {"size": 9.4, "lineBreak": False})
    write(pdf, value(time_info.get("averageWinds")).upper(), 391.16, 186.71, 78.39, {"size": 9.4, "align": "right", "lineBreak": False})

    write(
        pdf,
        "- - - - - - - - PLAN TIME & FUEL - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - PLAN WT (in LBS) - - - - - - - - - - - - - - -",
        TABLE_LEFT,
        205.35,
        TABLE_WIDTH,
        {"size": 9.4, "align": "center", "lineBreak": False},
    )

    plan_rows = [
        ("TRIP", fuel.get("trip"), find_value(fuel, "tripTime", "trip_time")),
        ("TAXI", fuel.get("taxi"), find_value(fuel, "taxiTime", "taxi_time")),
        ("CONTINGENCY 5%", fuel.get("contingency"), find_value(fuel, "contingencyTime", "contingency_time")),
        ("FINAL RESERVE FUEL", fuel.get("finalReserve"), find_value(fuel, "finalReserveTime", "final_reserve_time")),
        ("XTRA", fuel.get("extra"), find_value(fuel, "extraEndurance", "extra_endurance")),
        ("ALTN1", fuel.get("alternate"), find_value(fuel, "alternateTime", "alternate_time")),
        ("ALTN2", fuel.get("alternate2Fuel"), find_value(fuel, "alternate2Time", "alternate2_time")),
    ]
    weight_rows = [
        ("BASIC WT", weight.get("basicOperatingWeight")),
        ("TOT.LOAD", weight.get("load")),
        ("ZERO FUEL", weight.get("zeroFuelWeight")),
        ("T.OFF WT", weight.get("takeoffWeight")),
        ("LAND WT", weight.get("estimatedLandingWeight")),
    ]
    # One consistent 14.14pt-step grid runs from TRIP all the way down
    # through ENDURANCE (row 8) - the blank dashed divider (row 7) and
    # ENDURANCE are just further rows on the same grid, not separate
    # hand-placed elements.
    grid_y = [223.98 + 14.14 * i for i in range(9)]
    plan_rows_y = grid_y[:7]
    weight_rows_y = grid_y[:5]

    for (label, fuel_val, time_val), y in zip(plan_rows, plan_rows_y):
        write(pdf, label, 48.52, y, 100, {"size": 9.4, "lineBreak": False})
        write(pdf, ":", 148.91, y, 8, {"size": 9.4, "lineBreak": False})
        write(pdf, time_val, 159.21, y, 35, {"size": 9.4, "lineBreak": False})
        fuel_disp = f"{value(fuel_val)} LBS" if fuel_val not in (None, "") else ""
        write(pdf, fuel_disp, 157, y, 78.4, {"size": 9.4, "align": "right", "lineBreak": False})

    for (label, w_val), y in zip(weight_rows, weight_rows_y):
        write(pdf, label, 299.39, y, 60, {"size": 9.4, "lineBreak": False})
        write(pdf, ":", 359.07, y, 8, {"size": 9.4, "lineBreak": False})
        val_disp = f"{value(w_val)} LBS" if w_val not in (None, "") else ""
        write(pdf, val_disp, 342, y, 78.94, {"size": 9.4, "align": "right", "lineBreak": False})

    alt1 = alternates[0] if len(alternates) > 0 else {}
    alt2 = alternates[1] if len(alternates) > 1 else {}

    alt1_dist = field(alt1, "distance")
    if alt1_dist and not alt1_dist.upper().endswith("NM"):
        alt1_dist = f"{alt1_dist}NM"
    min_divert = fuel.get("minDivertFuel")
    min_divert_disp = f"{value(min_divert)} LBS" if min_divert not in (None, "") else ""
    write(
        pdf,
        f"ALTN : {alt1_dist}         MIN DIVERT FUEL: {min_divert_disp}",
        299.39, 297.67, 250,
        {"size": 9.4, "lineBreak": False},
    )

    first_route = value(field(alt1, "route")).replace("Route", "").strip()
    write(pdf, f"FIRST ALTN ROUTE : {first_route}", 299.39, 311.81, 250, {"size": 9.4, "lineBreak": False})

    # SECOND ALTN ROUTE wraps onto a second line (sharing ENDURANCE's own
    # row, on the right half where ENDURANCE has no content) when the
    # route string is long - matching default1.py's own equivalent wrap.
    second_route = value(field(alt2, "route")).replace("Route", "").strip()
    second_lines = _wrap(f"SECOND ALTN ROUTE : {second_route}", 9.4, 210.0)
    route2_y = 325.95
    for route_line in second_lines[:2]:
        write(pdf, route_line, 299.39, route2_y, 250, {"size": 9.4, "lineBreak": False})
        route2_y += 11.13

    write(pdf, "-" * 22, 159.21, grid_y[7], 100, {"size": 9.4, "lineBreak": False})

    write(pdf, "ENDURANCE:", 88.11, grid_y[8], 80, {"size": 9.4, "lineBreak": False})
    write(pdf, fuel.get("enduranceTime", ""), 159.21, grid_y[8], 35, {"size": 9.4, "lineBreak": False})
    # ENDURANCE's fuel figure is the same RAMP value COMPUTED FUEL shows,
    # not the separate "computedFuel" key (see the fuel_pairs note above).
    computed_fuel = fuel.get("ramp")
    endurance_fuel_disp = f"{value(computed_fuel)} LBS" if computed_fuel not in (None, "") else ""
    write(pdf, endurance_fuel_disp, 157, grid_y[8], 78.4, {"size": 9.4, "align": "right", "lineBreak": False})

    # ---- Different level calculation / actuals ----
    write(
        pdf,
        "- - - - - - - - - DIFFERENT LEVEL CALCULATION - - - - - - - - - - - - - - - - - - - - - - - - - - ACTUALS - - - - - - - - - - - - - - - - - - -",
        TABLE_LEFT,
        355.72,
        TABLE_WIDTH,
        {"size": 9.4, "align": "center", "lineBreak": False},
    )

    write(pdf, "FL", 63.41, 384.16, 20, {"size": 9.4, "lineBreak": False})
    write(pdf, "WC", 99.54, 384.16, 20, {"size": 9.4, "lineBreak": False})
    write(pdf, "TIME", 137.76, 384.16, 30, {"size": 9.4, "lineBreak": False})
    write(pdf, "TRIP", 194.01, 384.16, 30, {"size": 9.4, "lineBreak": False})

    level_rows_y = [398.30 + 14.14 * i for i in range(5)]
    for row, y in zip(level_calcs[:5], level_rows_y):
        fl_disp = value(row.get("fl"))
        # Below the transition altitude a level-calc row is a raw altitude
        # ("3000 ft"), not a flight level - only bare numbers get an "FL "
        # prefix added, not values that already carry their own unit.
        if fl_disp and not fl_disp.upper().startswith("FL") and "ft" not in fl_disp.lower():
            fl_disp = f"FL {fl_disp}"
        write(pdf, fl_disp, 55.21, y, 30, {"size": 9.4, "lineBreak": False})
        write(pdf, row.get("wc", ""), 101.88, y, 25, {"size": 9.4, "lineBreak": False})
        write(pdf, row.get("time", ""), 136.20, y, 40, {"size": 9.4, "lineBreak": False})
        trip_val = value(row.get("trip"))
        write(pdf, f"{trip_val} LBS" if trip_val else "", 185.03, y, 45, {"size": 9.4, "lineBreak": False})

    # ACTUALS is a fixed 3x5 grid of "LABEL: _________" fields for the crew
    # to fill in by hand post-flight - not drawn lines, and each cell sits
    # at its own hand-placed x0 (the reference doesn't align them to a
    # shared left margin).
    actuals = [
        ("PAX", 263.63, 381.11), ("CREW", 255.29, 402.00), ("SOB", 264.14, 422.88),
        ("FIC", 267.79, 443.77), ("ADC", 262.59, 464.66),
        ("ON BLK FUEL", 346.76, 381.11), ("OFF BLK FUEL", 343.11, 402.00),
        ("FUEL USED", 356.92, 422.88), ("BTIME", 378.01, 464.66),
        ("C/OFF", 466.41, 381.11), ("T/O", 477.36, 402.00), ("LDG", 473.20, 422.88),
        ("C/ON", 470.07, 443.77), ("F/T", 478.92, 464.66),
    ]
    for label, x0, y in actuals:
        write(pdf, f"{label}: _________", x0 - 2, y, 130, {"size": 9.4, "lineBreak": False})

    # ---- ATIS / clearance / runway / V-speed blocks (dep + arr) ----
    # None of this section is drawn with real line()/box() calls in the
    # reference PDF - every rule and fill-in blank is a literal dash or
    # underscore text string, which is why labelled_value()/line() never
    # matched it no matter how the coordinates were tuned.
    divider = ("- " * 85).strip()
    operational = page1.get("operational", {})

    write(pdf, divider, TABLE_LEFT, 481.80, TABLE_WIDTH, {"size": 9.4, "align": "center", "lineBreak": False})

    _underscore_row(pdf, "DEP ATIS", 4, 4, 81, operational.get("departureAtis"), 48.27, 496.68)
    _underscore_row(pdf, "DEP CLEARANCE", 4, 4, 74, operational.get("departureClearance"), 48.27, 515.32)
    _underscore_row(pdf, "TAXI CLEARANCE", 4, 4, 73, operational.get("depTaxiClearance"), 48.27, 533.96)

    write(
        pdf,
        "RWY   : ___________    FLAPS   : ___________    RWY: DRY / WET / CONT    A/I: OFF/ON",
        46.27, 552.60, TABLE_WIDTH, {"size": 9.4, "lineBreak": False},
    )
    write(
        pdf,
        "V1:_______________VR:_______________V2:_______________Vapp:_______________VFS:",
        46.27, 574.23, TABLE_WIDTH, {"size": 9.4, "lineBreak": False},
    )
    # VFS's own 15-underscore fill sits 1.5pt lower than the row's main
    # baseline - the same quirk default1.py's VREF row has.
    write(pdf, "_" * 15, 440.98, 575.73, 100, {"size": 9.4, "lineBreak": False})

    write(pdf, divider, TABLE_LEFT, 592.12, TABLE_WIDTH, {"size": 9.4, "align": "center", "lineBreak": False})

    _underscore_row(pdf, "ARR ATIS", 4, 4, 73, operational.get("arrivalAtis"), 48.27, 607.01)
    _underscore_row(pdf, "ARR CLEARANCE", 4, 4, 73, operational.get("arrivalClearance"), 48.27, 625.65)
    _underscore_row(pdf, "TAXI CLEARANCE", 4, 4, 73, operational.get("arrTaxiClearance"), 48.27, 644.28)

    write(
        pdf,
        "RWY   : ___________    FLAPS   : ___________    RWY: DRY / WET / CONT    A/I: OFF/ON",
        46.27, 662.92, TABLE_WIDTH, {"size": 9.4, "lineBreak": False},
    )
    write(
        pdf,
        "V1:_______________VR:_______________V2:_______________Vapp:_______________VFS:",
        46.27, 684.56, TABLE_WIDTH, {"size": 9.4, "lineBreak": False},
    )
    write(pdf, "_" * 15, 440.98, 686.06, 100, {"size": 9.4, "lineBreak": False})

    write(pdf, divider, TABLE_LEFT, 702.45, TABLE_WIDTH, {"size": 9.4, "align": "center", "lineBreak": False})

    dest_altn = value(operational.get("destAltnAtis"))
    write(
        pdf,
        f"DEST ALTNATIS :{(' ' + dest_altn) if dest_altn else ''}",
        44.02, 713.58, TABLE_WIDTH, {"size": 9.4, "lineBreak": False},
    )

    write(
        pdf,
        "I certify that all my licenses, ratings etc are current / valid and I am legally/ medically fit for operating flight.",
        TABLE_LEFT,
        740.86,
        TABLE_WIDTH,
        {"size": 9.0, "align": "center", "lineBreak": False},
    )

    write(pdf, "PILOT SIGN :", 46.27, 756.41, 70, {"size": 9.4, "lineBreak": False})
    write(pdf, "LICS NO :", 46.27, 768.30, 70, {"size": 9.4, "lineBreak": False})
    write(pdf, "BA NO :", 46.27, 779.44, 70, {"size": 9.4, "lineBreak": False})

    write(pdf, "COPILOT SIGN :", 347.31, 756.79, 80, {"size": 9.4, "lineBreak": False})
    write(pdf, "LICS NO :", 347.31, 767.92, 70, {"size": 9.4, "lineBreak": False})
    write(pdf, "BA NO :", 347.31, 779.06, 70, {"size": 9.4, "lineBreak": False})


# --------------------------------------------------
# NAVLOG TABLE (PAGES 2 & 3)
# --------------------------------------------------
# Column keys/order/top-bottom titles match NAV_COLUMNS exactly (confirmed
# against the reference PDF's own header text), but the widths and font
# size are VTVIK's own - measured directly off the reference's column-
# divider grid lines rather than reusing MLOVE/VTBBD's proportions.

VTVIK_COLUMN_WIDTHS = {
    "waypoint": 113.83,
    "heading": 31.58,
    "flightLevel": 38.27,
    "windDirectionSpeed": 51.66,
    "isa": 25.43,
    "tas": 31.64,
    "legDistance": 36.55,
    "fuelUsed": 40.04,
    "ete": 28.08,
    "legTimeRemaining": 31.58,
    "eta": 35.43,
    "actualFuel": 61.65,
}


def _header_text_y(box_top, box_height, line_count):
    # Empirically measured off the reference: a single line centers at
    # box_top + box_height/2 + 5.22, and each additional line pushes the
    # first line up by half of an 11.16pt line gap.
    return box_top + box_height / 2 + 5.22 - (line_count - 1) * 5.58


def _draw_table_header(pdf, y):
    x = TABLE_LEFT
    top_header_height = 33.52
    bottom_header_height = 33.64
    total_header_height = top_header_height + bottom_header_height
    font_size = 9.4

    idx = 0
    while idx < len(NAV_COLUMNS):
        key, top_title, bottom_title, _ = NAV_COLUMNS[idx]
        width = VTVIK_COLUMN_WIDTHS[key]

        if top_title:
            span_width = width
            next_idx = idx + 1
            while next_idx < len(NAV_COLUMNS) and NAV_COLUMNS[next_idx][1] == top_title:
                span_width += VTVIK_COLUMN_WIDTHS[NAV_COLUMNS[next_idx][0]]
                next_idx += 1

            box(pdf, x, y, span_width, top_header_height)
            # A two-word top title ("SPD KT", "DIST NM", "FUEL LB") stacks
            # onto two lines in the reference rather than staying on one.
            top_lines = top_title.replace(" ", "\n")
            top_line_count = top_lines.count("\n") + 1
            top_text_y = _header_text_y(y, top_header_height, top_line_count)
            write(pdf, top_lines, x + 2, top_text_y, span_width - 4, {"size": font_size, "align": "center"})

            sub_x = x
            bottom_box_top = y + top_header_height
            for sub_i in range(idx, next_idx):
                _, _, s_bottom, _ = NAV_COLUMNS[sub_i]
                s_width = VTVIK_COLUMN_WIDTHS[NAV_COLUMNS[sub_i][0]]
                box(pdf, sub_x, bottom_box_top, s_width, bottom_header_height)
                s_lines = s_bottom.replace(" ", "\n")
                line_count = s_lines.count("\n") + 1
                text_y = _header_text_y(bottom_box_top, bottom_header_height, line_count)
                write(pdf, s_lines, sub_x + 2, text_y, s_width - 4, {"size": font_size, "align": "center"})
                sub_x += s_width

            x += span_width
            idx = next_idx
        else:
            # No top title, but the text still vertically centers within
            # the bottom sub-row's slot, not the full two-row box height -
            # it's grouped with the other bottom-row headers visually even
            # though its own box spans the full header height.
            box(pdf, x, y, width, total_header_height)
            bottom_lines = bottom_title.replace(" ", "\n")
            line_count = bottom_lines.count("\n") + 1
            text_y = _header_text_y(y + top_header_height, bottom_header_height, line_count)
            align = "left" if key == "waypoint" else "center"
            text_x, text_width = (x + 0.6, width) if align == "left" else (x, width)
            write(pdf, bottom_lines, text_x, text_y, text_width, {"size": font_size, "align": align})
            x += width
            idx += 1

    return y + total_header_height


def _draw_table_rows(pdf, rows, start_y, maximum_y):
    y = start_y
    if rows is None:
        rows = []

    font_size = 9.4
    line_height = font_size + 1
    min_height = 33.64
    vertical_padding = 4

    for index, row in enumerate(rows):
        max_lines = 1
        for key, _, _, _ in NAV_COLUMNS:
            cell_text = combined_row_value(row, key)
            max_lines = max(max_lines, _cell_line_count(cell_text, font_size, VTVIK_COLUMN_WIDTHS[key]))

        content_height = max_lines * line_height + vertical_padding
        height = max(min_height, content_height)

        if y + height > maximum_y:
            return {"y": y, "remaining": rows[index:]}

        x = TABLE_LEFT
        for key, _, _, _ in NAV_COLUMNS:
            width = VTVIK_COLUMN_WIDTHS[key]
            box(pdf, x, y, width, height)
            cell_text = combined_row_value(row, key)
            line_count = _cell_line_count(cell_text, font_size, width)
            text_y = _header_text_y(y, height, line_count)
            align = "left" if key == "waypoint" else "center"
            text_x = x + 0.6 if align == "left" else x

            write(pdf, cell_text, text_x, text_y, width, {"size": font_size, "align": align})
            x += width

        y += height

    return {"y": y, "remaining": []}


def _draw_table_title(pdf, title, y):
    banner_height = 45.63
    box(pdf, TABLE_LEFT, y, TABLE_WIDTH, banner_height)
    write(pdf, title, TABLE_LEFT + 1, y + 26.16, TABLE_WIDTH - 4, {"size": 9.4, "lineBreak": False})

    return y + banner_height


TABLE_BOTTOM_LIMIT = 795


def _start_table_page(pdf, data):
    title = data.get("page1", {}).get("header", {}).get("routeTitle", "")
    registration = data.get("page1", {}).get("header", {}).get("registration", "")
    pdf.showPage()
    route_header(pdf, title, registration)
    box(pdf, 34.39, 34.39, 526.5, 771.61)
    return _draw_table_header(pdf, 34.39)


def draw_pages_two_and_three(pdf, data):
    alternates = data.get("page1", {}).get("alternates", [])
    alternate_name = data.get("page1", {}).get("flightInfo", {}).get("alternate1", "")
    routes = data.get("routes", {})

    # Content flows continuously across pages 2/3 - a page break happens
    # only when a block or row genuinely doesn't fit, matching how the
    # reference lets alternate2's table start right after alternate1's on
    # the same page rather than always restarting fresh on page 3.
    blocks = [(None, data.get("mainNavlog", []))]

    for position, (navlog_key, route_key) in enumerate([
        ("alternate1Navlog", "alternate1Route"),
        ("alternate2Navlog", "alternate2Route"),
    ]):
        rows = _drop_origin_row(data.get(navlog_key, []))
        if not rows:
            continue

        if position == 0:
            name = alternate_name
        else:
            # flightInfo["alternate1"] is only ever "<main dest>,<alt1
            # dest>" (there is no analogous pre-composed "alternate2"
            # field) - reusing it for the SECOND alternate's own banner
            # printed the first alternate's airport on both blocks
            # ("VOTP,VOMM" twice instead of "VOTP,VOMM" then "VOTP,VOBG").
            # Built the same way default1.py's equivalent banner is: the
            # main destination plus this specific alternate's own airport.
            main_dest = alternate_name.split(",")[0] if alternate_name else ""
            alt_airport = value(alternates[1].get("airport")) if len(alternates) > 1 else ""
            name = ",".join(part for part in [main_dest, alt_airport] if part)

        route_text = value(routes.get(route_key)).replace("Route", "").strip()
        title = f"Alternate route for {name}"
        if route_text:
            title += f"      Route {route_text}"
        blocks.append((title, rows))

    y = _start_table_page(pdf, data)

    for title, rows in blocks:
        if title is not None:
            if y + 45.63 + 33.64 > TABLE_BOTTOM_LIMIT:
                y = _start_table_page(pdf, data)
            y = _draw_table_title(pdf, title, y)

        remaining = rows
        while remaining:
            result = _draw_table_rows(pdf, remaining, y, TABLE_BOTTOM_LIMIT)
            y = result["y"]
            remaining = result["remaining"]
            if remaining:
                y = _start_table_page(pdf, data)

    airport_rows = data.get("airportInformation", [])
    airport_needed = 22.6 + 11.23 + 22.38 * (len(airport_rows) + 1)
    if airport_rows and y + airport_needed > TABLE_BOTTOM_LIMIT:
        y = _start_table_page(pdf, data)

    y += 22.6
    write(pdf, "AIRPORT INFO", TABLE_LEFT, y, 150, {"size": 9.4, "bold": False, "lineBreak": False})

    y += 11.23

    # Runway designator and length are two separate columns under a single
    # spanning "LONGEST RWY" header, not one combined cell.
    airport_columns = [
        ("type", "", 47.98),
        ("airport", "Airport", 55.27),
        ("eta", "ETA", 49.42),
        ("atis", "ATIS", 51.33),
        ("tower", "TWR/CTAF", 89.94),
        ("clearance", "CLR", 38.12),
        ("ground", "GND", 42.50),
        ("elevation", "ELEV", 48.50),
        ("runwayDesignator", "LONGEST RWY", 49.19),
        ("runwayLength", "LONGEST RWY", 54.28),
    ]

    x = TABLE_LEFT
    idx = 0
    while idx < len(airport_columns):
        key, heading, width = airport_columns[idx]
        span_width = width
        next_idx = idx + 1
        while next_idx < len(airport_columns) and airport_columns[next_idx][1] == heading and heading:
            span_width += airport_columns[next_idx][2]
            next_idx += 1

        # A single merged box, even when this heading spans two columns
        # ("LONGEST RWY" over runwayDesignator/runwayLength) - drawing the
        # two sub-column boxes here too, on top of this one, put a stray
        # vertical divider straight through the centred heading text. The
        # data rows below draw those two cells separately on their own.
        box(pdf, x, y, span_width, 22.38)
        write(pdf, heading, x + 2, y + 14.53, span_width - 4, {"size": 9.4, "align": "center", "lineBreak": False})

        x += span_width
        idx = next_idx

    y += 22.38

    for airport in data.get("airportInformation", []):
        x = TABLE_LEFT
        for key, _, width in airport_columns:
            box(pdf, x, y, width, 22.38)
            if key == "runwayDesignator":
                airport_value = value(airport.get("longestRunway") or airport.get("runway"))
            elif key == "runwayLength":
                airport_value = value(airport.get("runwayLength"))
            else:
                airport_value = airport.get(key)

            write(pdf, airport_value, x + 2, y + 14.54, width - 4, {"size": 9.4, "align": "center", "lineBreak": False})
            x += width
        y += 22.38


# --------------------------------------------------
# PAGE FOUR (ATC FLIGHT PLAN + ENROUTE WINDS)
# --------------------------------------------------


def draw_page_four(pdf, data):
    title = data.get("page1", {}).get("header", {}).get("routeTitle", "")
    registration = data.get("page1", {}).get("header", {}).get("registration", "")
    atc = data.get("atcFlightPlan", {})

    pdf.showPage()

    route_header(pdf, title, registration)
    box(pdf, 34.39, 34.39, 526.5, 771.61)

    write(
        pdf,
        atc.get("title", f"ATC FLIGHT PLAN {field(atc, 'departure')} to {field(atc, 'destination')}"),
        TABLE_LEFT + 60,
        58.77,
        TABLE_WIDTH - 120,
        {"size": 9.4, "align": "center", "lineBreak": False},
    )

    write(
        pdf,
        ". . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .",
        TABLE_LEFT + 100,
        69.93,
        TABLE_WIDTH - 200,
        {"size": 9.4, "bold": True, "align": "center", "lineBreak": False},
    )

    flight_plan_text = find_value(
        atc,
        "flightPlanText", "flight_plan_text", "fplText", "fpl_text",
        "flightPlan", "flight_plan", "text", "planText", "plan_text",
        "icaoText", "icao_text", "fpl",
    )
    if flight_plan_text:
        write(pdf, flight_plan_text, TABLE_LEFT + 10, 90.53, TABLE_WIDTH - 20, {"size": 8.2})

    table_left = TABLE_LEFT + 11.5
    table_width = TABLE_WIDTH - 20

    write(
        pdf,
        "ENROUTE WINDS",
        table_left,
        190.24,
        table_width,
        {"size": 9.4, "align": "center", "lineBreak": False},
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

    # A fixed per-band pitch (not derived from available page width) -
    # the reference doesn't stretch to fill the frame for fewer bands,
    # it just uses less of the page.
    ident_col_width = 75.82
    pair_width = 89.76
    wv_width = 51.23
    tmp_width = pair_width - wv_width

    write(pdf, "IDENT", table_left, 218.25, ident_col_width, {"size": 9.4, "lineBreak": False})

    for b_idx, band in enumerate(bands):
        b_label = str(band).split("(")[0].strip()
        band_x = table_left + ident_col_width + (b_idx * pair_width)
        band_step = b_idx * pair_width
        # "FL xxx" and "W/V" don't share one centered block - each line
        # has its own independent center (W/V, being shorter, centers a
        # bit further right than the FL label above it), and neither
        # aligns with the data rows' own band_x.
        write(pdf, b_label, 111.23 + band_step, 212.72, wv_width, {"size": 9.4, "align": "center", "lineBreak": False})
        write(pdf, "W/V", 118.13 + band_step, 223.88, wv_width, {"size": 9.4, "align": "center", "lineBreak": False})
        write(pdf, "TMP", 159.11 + band_step, 218.25, tmp_width, {"size": 9.4, "align": "center", "lineBreak": False})

    y = 238.01
    row_height = 14.14

    for row in wind_rows:
        ident_str = value(row.get("identifier"))
        write(pdf, ident_str, table_left, y, ident_col_width, {"size": 9.4, "lineBreak": False})

        cells = row.get("values", [])
        for c_idx in range(min(len(cells), num_bands)):
            cell = cells[c_idx]
            band_x = table_left + ident_col_width + (c_idx * pair_width)

            raw_wind = value(cell.get("wind"))
            clean_wind = raw_wind.split("\n")[-1].strip() if "\n" in raw_wind else raw_wind.strip()
            if clean_wind.startswith("(") and ")" in clean_wind:
                clean_wind = clean_wind.split(")")[-1].strip()

            raw_isa = value(cell.get("isa")).strip()

            write(pdf, clean_wind, band_x - 2, y, wv_width, {"size": 9.4, "lineBreak": False})
            write(pdf, raw_isa, band_x + wv_width - 2, y, tmp_width, {"size": 9.4, "lineBreak": False})

        y += row_height

    page_height = A4[1]
    pdf.setFont("Courier-Bold", 9.4)
    end_report_text = "**************  END OF THE REPORT  **************"
    pdf.drawCentredString(TABLE_LEFT + TABLE_WIDTH / 2, page_height - 773.30, end_report_text)

    computed_date = datetime.now().strftime("%d-%m-%Y")
    computed_time = datetime.now().strftime("%H:%M:%S")

    write(pdf, f"COMPUTED DATE : {computed_date}", 35.02, 802.65, 220, {"size": 9.4, "lineBreak": False, "padding": 0})
    write(pdf, f"TIME : {computed_time} UTC", 471.63, 802.65, 220, {"size": 9.4, "align": "right", "lineBreak": False, "padding": 0})


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
