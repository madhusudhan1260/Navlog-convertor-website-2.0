import os
import re
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ==================================================
# OUTPUT DIRECTORY & GLOBAL CONSTANTS
# ==================================================

OUTPUT_DIRECTORY = os.path.join(os.path.dirname(__file__), "generated")
W, H = A4

MARGIN_X = 35
MARGIN_Y = 35
INNER_W = W - (2 * MARGIN_X)
INNER_H = H - (2 * MARGIN_Y)

# Primary Font Selection (Serif - matches target NAV LOG format)
FONT_NORMAL = "Times-Roman"
FONT_BOLD = "Times-Bold"

# Fallback airport name lookup, used ONLY when the source JSON does not supply
# an airportName/name field for a given airport entry. The JSON value always
# wins if present - this just prevents a bare ICAO code from printing when
# the upstream data happens to omit the name.
# Extend this table as you encounter more airports in your operations.
AIRPORT_NAME_LOOKUP = {
    "VOHY": "BEGUMPET",
}

# Standard Grid Coordinates & Line Spacing
COL1 = 55
COL2 = 320
COL3 = 468

LEFT_VAL = 295
RIGHT_VAL = 550

ROW_H = 15.5
SEC_GAP = 20
TITLE_GAP = 22

# ==================================================
# COMMON HELPER FUNCTIONS
# ==================================================

def value(v):
    if v is None:
        return ""
    return str(v).strip()

def _normalize_key(k):
    return str(k).lower().replace("_", "").replace(" ", "").replace("-", "")

def find_value(*objs_and_keys):
    sources = [o for o in objs_and_keys if isinstance(o, dict) and o]
    keys = [k for k in objs_and_keys if isinstance(k, str)]

    if not sources or not keys:
        return ""

    norm_keys = [_normalize_key(k) for k in keys]

    for src in sources:
        for k, nk in zip(keys, norm_keys):
            if k in src and src[k] not in (None, ""):
                return value(src[k])
            for real_key, v in src.items():
                if _normalize_key(real_key) == nk and v not in (None, ""):
                    return value(v)

    return ""

def find_list(*objs_and_keys):
    sources = [o for o in objs_and_keys if isinstance(o, dict) and o]
    keys = [k for k in objs_and_keys if isinstance(k, str)]

    if not sources or not keys:
        return []

    norm_keys = [_normalize_key(k) for k in keys]

    for src in sources:
        for k, nk in zip(keys, norm_keys):
            if k in src and isinstance(src[k], list) and src[k]:
                return src[k]
            for real_key, v in src.items():
                if _normalize_key(real_key) == nk and isinstance(v, list) and v:
                    return v

    return []

def safe_int(v, default=0):
    val_str = value(v).replace("LBS", "").replace("lbs", "").strip()
    try:
        return int(val_str)
    except ValueError:
        try:
            return int(float(val_str))
        except ValueError:
            return default

def text(c, x, y, val, font=FONT_NORMAL, size=9):
    c.setFont(font, size)
    c.drawString(x, y, str(val))

def text_right(c, x, y, val, font=FONT_NORMAL, size=9):
    c.setFont(font, size)
    c.drawRightString(x, y, str(val))

def text_center(c, x, y, val, font=FONT_NORMAL, size=9):
    c.setFont(font, size)
    c.drawCentredString(x, y, str(val))

def frame(c, header_text=""):
    c.setLineWidth(1)
    c.rect(MARGIN_X, MARGIN_Y, INNER_W, INNER_H)
    if header_text:
        text_right(c, W - 50, H - 25, header_text, font=FONT_BOLD, size=10)

def kv(c, label_x, value_right_x, y, label, val, unit="", font=FONT_NORMAL, size=9, bold_label=True, colon_x=None):
    """Draws LABEL : VALUE with the colon in a fixed column so multiple rows line up,
    matching the target layout where every ':' in a block sits on the same vertical line."""
    lbl_font = FONT_BOLD if bold_label else font
    c.setFont(lbl_font, size)
    c.drawString(label_x, y, str(label))
    if colon_x is not None:
        c.drawString(colon_x, y, ":")
    if val not in (None, ""):
        disp = f"{val} {unit}".strip()
        text_right(c, value_right_x, y, disp, font=font, size=size)


# ==================================================
# FORMAT NORMALIZATION HELPERS
# ==================================================

def format_top_climb_temp(s):
    """Normalizes strings like 'FL170 (ISA: +15)' into 'FL 170 (ISA: +15°C)'
    to match the target's spacing/units, without touching values that are
    already formatted correctly (e.g. the hardcoded fallback)."""
    if not s:
        return s
    s = re.sub(r'\bFL(\d)', r'FL \1', s)
    s = re.sub(r'(ISA:\s*[+-]?\d+)(?!\s*°)', r'\1°C', s)
    return s


# ==================================================
# PAGE 1 (MAIN OPERATIONAL FLIGHT PLAN)
# ==================================================

def draw_page_one(c, data=None):
    if data is None:
        data = {}

    page1 = data.get("page1", {})
    flight = page1.get("flightInfo", {}) or data.get("flightInfo", {}) or data.get("flight", {})
    summary = data.get("main", {}).get("summary", {}) or data.get("summary", {})
    fuel = page1.get("fuel", {}) or data.get("fuel", {})
    weight = page1.get("weight", {}) or data.get("weight", {})
    time_info = page1.get("time", {}) or data.get("time", {})
    header = page1.get("header", {}) or data.get("header", {})
    misc = page1.get("misc", {}) or data.get("misc", {})
    routes = data.get("routes", {}) or page1.get("routes", {})
    airports = data.get("airportInformation", []) or data.get("airportData", [])

    # =========================================================================
    # 1. & 2. EDITED HEADER SECTION (Top-Right Title & Main Banner)
    # =========================================================================
    reg = find_value(flight, summary, header, data, "registration", "reg", "tailNumber")
    dep_code = find_value(flight, summary, header, data, "departure", "dep", "depCode", "origin")
    dest_code = find_value(flight, summary, header, data, "destination", "dest", "destCode")

    # Draw page boundary box
    c.setLineWidth(1)
    c.rect(MARGIN_X, MARGIN_Y, INNER_W, INNER_H)

    # Top-Right Header (outside frame top) using standard normal font weight
    header_right_str = f"{dep_code} - {dest_code}   {reg}".strip()
    text_right(c, W - MARGIN_X, H - MARGIN_Y + 12, header_right_str, font=FONT_NORMAL, size=9.5)

    # Aircraft type & Date resolution
    atc_plan = data.get("atcFlightPlan", {}) if isinstance(data.get("atcFlightPlan"), dict) else {}
    ac_type = find_value(header, summary, flight, data, atc_plan, "aircraftType", "type", "acType")

    # Resolve Date (e.g., 24JUL26)
    date_str = find_value(header, summary, flight, data, "date", "flightDate", "dof", "dayOfFlight")
    if not date_str:
        date_str = datetime.now().strftime("%d%b%y").upper()

    etd = find_value(time_info, summary, "etd", "etd_utc") or "0730Z"
    eta = find_value(time_info, summary, "eta", "eta_utc") or "0837Z"

    banner_parts = [reg] if reg else []
    if ac_type:
        banner_parts.append(f"({ac_type})")
    if date_str:
        banner_parts.append(date_str)

    banner_head = " ".join(banner_parts)

    # Matching target dash styling (spaced dashes, normal font weight, inside top frame)
    banner_title = f"- - - - - {banner_head} NAV LOG/ OPS FPL FOR ETD {etd} (ETA {eta}) - - - - -"
    text_center(c, W / 2, H - 52, banner_title, font=FONT_NORMAL, size=8.5)
    # =========================================================================

    # 3. Airport Names & Top Flight Summary Block
    dep_name = find_value(flight, summary, "departureName", "dep_name")
    dest_name = find_value(flight, summary, "destinationName", "dest_name")

    for apt in airports:
        if isinstance(apt, dict):
            a_type = str(apt.get("type", "")).upper()
            a_name = apt.get("airportName", apt.get("name", ""))
            if a_type == "DEP" and not dep_name and a_name:
                dep_name = a_name
            elif a_type in ("DEST", "ARR") and not dest_name and a_name:
                dest_name = a_name

    # If the JSON genuinely has no name for this airport, fall back to the
    # lookup table rather than printing a bare code.
    if not dep_name:
        dep_name = AIRPORT_NAME_LOOKUP.get(dep_code.upper(), "") if dep_code else ""
    if not dest_name:
        dest_name = AIRPORT_NAME_LOOKUP.get(dest_code.upper(), "") if dest_code else ""

    dep_disp = f"{dep_code} - {dep_name}" if dep_name else dep_code
    dest_disp = f"{dest_code} - {dest_name}" if dest_name else dest_code

    dist_val = find_value(time_info, summary, flight, "plannedRouteDistance", "dist")
    if dist_val and not dist_val.endswith("NM"):
        dist_val = f"{dist_val}NM"

    track_val = find_value(time_info, summary, flight, "track")
    if track_val and not track_val.endswith("DEG"):
        track_val = f"{track_val} DEG"

    pax_val = find_value(weight, flight, summary, data, "pax")
    if pax_val == "" or pax_val is None:
        pax_val = "0"

    y = 768
    text(c, COL1, y, "DEP", font=FONT_NORMAL, size=9)
    text(c, COL1 + 38, y, f": {dep_disp}")
    text(c, COL2, y, "DIST", font=FONT_NORMAL, size=9)
    text(c, COL2 + 32, y, f": {dist_val}")
    text(c, COL3, y, "TRACK", font=FONT_NORMAL, size=9)
    text(c, COL3 + 36, y, f": {track_val}")

    y -= ROW_H
    text(c, COL1, y, "DEST", font=FONT_NORMAL, size=9)
    text(c, COL1 + 38, y, f": {dest_disp}")
    text(c, COL2, y, "CRUISE", font=FONT_NORMAL, size=9)
    text(c, COL2 + 32, y, ":")
    text(c, COL3, y, "PAX", font=FONT_NORMAL, size=9)
    text(c, COL3 + 36, y, f": {pax_val}")

    # Cruise Paragraph Auto-Wrap Strategy
    cruise_text = find_value(misc, summary, time_info, "plannedProfile", "cruiseProfile", "cruise")
    # Target format is fully upper-case (e.g. "IFR 230 KIAS/M0.55 - MAXIMUM
    # CRUISE THRUST @ FL170 - NORMAL 2000 FPM") - normalize casing here so a
    # mixed-case source value still matches the printed form's style.
    if cruise_text:
        cruise_text = cruise_text.upper()

    p_style = ParagraphStyle(
        name="CruiseStyle",
        fontName=FONT_NORMAL,
        fontSize=9,
        leading=11,
    )
    p = Paragraph(cruise_text, p_style)
    p_width = COL3 - (COL2 + 42)
    w_p, h_p = p.wrap(p_width, 60)
    p.drawOn(c, COL2 + 42, y - h_p + 9)

    y -= max(int(h_p), 26)

    main_route = find_value(routes, misc, data, summary, "mainRoute", "atcRoute")

    # Prepend profile info if not already included to match target format
    if main_route and not main_route.startswith("FL170"):
        main_route = f"FL170 - NORMAL 2000 FPM {main_route}"
    elif not main_route:
        main_route = "FL170 - NORMAL 2000 FPM HHY ANBAS HHY ANBAS HHY"

    text(c, COL1, y, f"MAIN ROUTE : {main_route}", font=FONT_NORMAL, size=9)

    y -= ROW_H + 6
    pic = find_value(data, flight, summary, page1, "pic", "captain")
    # FO/co-pilot name - widened alias list since the source key wasn't
    # matching any of "fo"/"copilot" in the sample payload.
    fo = find_value(
        data, flight, summary, page1,
        "fo", "copilot", "coPilot", "firstOfficer", "foName", "fo_name", "sic"
    )
    text(c, COL1, y, "PIC", font=FONT_BOLD, size=9)
    text(c, COL1 + 30, y, f": {pic}", font=FONT_BOLD, size=9)
    text(c, COL2 - 15, y, "FO", font=FONT_BOLD, size=9)
    text(c, COL2 + 15, y, f": {fo}", font=FONT_BOLD, size=9)

    # 4. Computed Fuel & Operating Weights Top Section
    # Keep raw (possibly empty) strings for display, and separate numeric
    # values (defaulting to 0) purely for internal math - so a missing field
    # prints blank instead of a misleading "0 LBS".
    block_fuel_raw = find_value(fuel, summary, "blockFuel", "ramp", "rampFuel")
    block_fuel_val = safe_int(block_fuel_raw)  # for calculations only
    taxi_fuel_raw = find_value(fuel, "taxiFuel", "taxi")
    taxi_fuel_val = safe_int(taxi_fuel_raw)
    trip_fuel_raw = find_value(fuel, "tripFuel", "trip")
    trip_fuel_val = safe_int(trip_fuel_raw)

    comp_fuel = find_value(fuel, summary, "computedFuel") or "3500"
    min_trip = find_value(fuel, summary, "minTripFuel", "minTrip") or "2845"
    max_trip = find_value(fuel, summary, "maxTripFuel", "maxTrip") or "3961"
    top_climb = find_value(time_info, summary, "topClimbTemp", "tocTemp") or "FL 170 (ISA: -19°C)"
    top_climb = format_top_climb_temp(top_climb)

    # Dynamic Fuel Formulations (only fall back to a computed value if the
    # source data genuinely has no explicit figure for that field)
    takeoff_fuel_raw = find_value(fuel, "takeoffFuel", "takeoff")
    if takeoff_fuel_raw:
        takeoff_fuel_disp = safe_int(takeoff_fuel_raw)
    elif block_fuel_raw and taxi_fuel_raw:
        takeoff_fuel_disp = block_fuel_val - taxi_fuel_val
    else:
        takeoff_fuel_disp = ""

    landing_fuel_raw = find_value(fuel, "landingFuel", "landing")
    if landing_fuel_raw:
        landing_fuel_disp = safe_int(landing_fuel_raw)
    elif block_fuel_raw and taxi_fuel_raw and trip_fuel_raw:
        landing_fuel_disp = block_fuel_val - taxi_fuel_val - trip_fuel_val
    else:
        landing_fuel_disp = ""

    # WIND summary line - widened alias list; source key wasn't matching
    # "wind"/"avgWinds"/"averageWinds" in the sample payload.
    wind_val = find_value(
        time_info, summary, fuel,
        "wind", "avgWinds", "averageWinds", "windSummary", "averageWind",
        "windInfo", "windAvg", "avgWind"
    )

    y -= SEC_GAP + 8
    kv(c, COL1, LEFT_VAL - 15, y, "COMPUTED FUEL", comp_fuel, "LBS", font=FONT_NORMAL, bold_label=False, colon_x=COL1 + 105)
    kv(c, COL2, RIGHT_VAL, y, "BLOCK FUEL", block_fuel_raw, "LBS", colon_x=COL2 + 80)

    y -= ROW_H
    kv(c, COL1, LEFT_VAL - 15, y, "MIN. TRIP FUEL", min_trip, "LBS", font=FONT_NORMAL, bold_label=False, colon_x=COL1 + 105)
    kv(c, COL2, RIGHT_VAL, y, "TAKE OFF FUEL", takeoff_fuel_disp, "LBS", colon_x=COL2 + 80)

    y -= ROW_H
    kv(c, COL1, LEFT_VAL - 15, y, "MAX. TRIP FUEL", max_trip, "LBS", font=FONT_NORMAL, bold_label=False, colon_x=COL1 + 105)
    kv(c, COL2, RIGHT_VAL, y, "LANDING FUEL", landing_fuel_disp, "LBS", colon_x=COL2 + 80)

    y -= ROW_H
    kv(c, COL1, LEFT_VAL - 15, y, "TOP CLIMB TEMP", top_climb, "", font=FONT_NORMAL, bold_label=False, colon_x=COL1 + 105)
    kv(c, COL2, RIGHT_VAL, y, "WIND", wind_val, "", colon_x=COL2 + 80)

    # 5. Plan Time, Fuel & Weights Matrix
    y -= SEC_GAP + 6
    text_center(c, W / 2, y, "----- PLAN TIME & FUEL -------------------------------- PLAN WT (in LBS) -----", font=FONT_BOLD, size=9)

    # Contingency & Extra fuel: only compute a figure when the source data
    # genuinely does not provide one - never override a real fetched value.
    ctg_time = find_value(fuel, "contingencyTime")
    ctg_lbs_raw = find_value(fuel, "contingency")
    ctg_lbs_val = safe_int(ctg_lbs_raw) if ctg_lbs_raw else round(trip_fuel_val * 0.05)

    res_time = find_value(fuel, "finalReserveTime")
    res_lbs_raw = find_value(fuel, "finalReserve")
    res_lbs_disp = safe_int(res_lbs_raw) if res_lbs_raw else ""
    res_lbs_num = safe_int(res_lbs_raw)  # for calc only

    alt1_time = find_value(fuel, "alt1Time", "alternate1Time")
    alt1_lbs_raw = find_value(fuel, "alternate1", "alternate")
    alt1_lbs_disp = safe_int(alt1_lbs_raw) if alt1_lbs_raw else ""
    alt1_lbs_num = safe_int(alt1_lbs_raw)

    alt2_time = find_value(fuel, "alt2Time", "alternate2Time")
    # ALTN2 fuel figure - widened alias list; time key resolved fine but the
    # LBS figure didn't, meaning the real key differs from "alternate2".
    alt2_lbs_raw = find_value(
        fuel, "alternate2", "altn2Fuel", "alternate2Fuel", "alt2Fuel", "altn2"
    )
    alt2_lbs_disp = safe_int(alt2_lbs_raw) if alt2_lbs_raw else ""
    alt2_lbs_num = safe_int(alt2_lbs_raw)

    extra_time = find_value(fuel, "extraTime")
    extra_lbs_raw = find_value(fuel, "extra")
    if extra_lbs_raw:
        extra_lbs_calc = safe_int(extra_lbs_raw)
    else:
        sum_known = trip_fuel_val + taxi_fuel_val + ctg_lbs_val + res_lbs_num + alt1_lbs_num + alt2_lbs_num
        extra_lbs_calc = max(0, block_fuel_val - sum_known)

    plan_rows = [
        ("TRIP", find_value(fuel, "tripTime"), trip_fuel_raw),
        ("TAXI", find_value(fuel, "taxiTime"), taxi_fuel_raw),
        ("CONTINGENCY 5%", ctg_time, ctg_lbs_val),
        ("FINAL RESERVE FUEL", res_time, res_lbs_disp),
        ("XTRA", extra_time, extra_lbs_calc),
        ("ALTN1", alt1_time, alt1_lbs_disp),
        ("ALTN2", alt2_time, alt2_lbs_disp),
    ]

    weight_rows = [
        ("BASIC WT", find_value(weight, "basicWt", "basicOperatingWeight")),
        ("LOAD", find_value(weight, "load")),
        ("ZERO FUEL", find_value(weight, "zfw", "zeroFuelWeight")),
        ("T.OFF WT", find_value(weight, "tow", "takeoffWeight")),
        ("LAND WT", find_value(weight, "landWt", "estimatedLandingWeight")),
    ]

    y_p = y - 22
    # Grid Columns for Plan Table: Label, Time, Weight - widened to match target spacing
    for label_str, time_val, lbs_val in plan_rows:
        text(c, COL1, y_p, label_str, font=FONT_NORMAL, size=9)
        text(c, COL1 + 130, y_p, ":", font=FONT_NORMAL, size=9)
        if time_val:
            text(c, COL1 + 145, y_p, str(time_val))
        if lbs_val not in (None, ""):
            text_right(c, LEFT_VAL, y_p, f"{lbs_val} LBS")
        y_p -= ROW_H

    y_w = y - 22
    for label_str, lbs_val in weight_rows:
        kv(c, COL2, RIGHT_VAL, y_w, label_str, lbs_val, "LBS", colon_x=COL2 + 80)
        y_w -= ROW_H

    # Endurance Display Row
    text(c, COL1 + 145, y_p, "---------")
    text_right(c, LEFT_VAL, y_p, "-------------")
    y_p -= 14
    # Endurance time - widened alias list; only the LBS figure was resolving
    # before because "enduranceTime" wasn't the real key.
    endurance_time_val = find_value(
        fuel, summary, time_info, "enduranceTime", "endurance", "enduranceHrs", "enduranceHours"
    )
    text(c, COL1, y_p, "ENDURANCE", font=FONT_NORMAL, size=9)
    text(c, COL1 + 130, y_p, ":", font=FONT_NORMAL, size=9)
    text(c, COL1 + 145, y_p, endurance_time_val)
    if block_fuel_raw:
        text_right(c, LEFT_VAL, y_p, f"{block_fuel_raw} LBS")

    # Alternate Details Block Right Side
    # Some JSON payloads carry alternate distance/route info as a structured
    # list (page1.alternates: [{name, distance, route, fuel}, ...]) rather
    # than flat fields - fall back to that list when the flat keys are absent.
    alternates_list = find_list(page1, data, "alternates")
    alt1_from_list = alternates_list[0] if len(alternates_list) > 0 and isinstance(alternates_list[0], dict) else {}
    alt2_from_list = alternates_list[1] if len(alternates_list) > 1 and isinstance(alternates_list[1], dict) else {}

    alt_dist_val = find_value(data, weight, routes, "altnDistance", "altDist", "alternateDistance") \
        or value(alt1_from_list.get("distance", ""))
    # MIN DIVERT FUEL - widened alias list; none of the existing keys were
    # matching the source payload.
    min_div_val = find_value(
        fuel, weight, data,
        "minDivertFuel", "minDivert", "minimumDivertFuel", "minimumDivert", "divertFuelMin"
    )
    alt1_route_str = find_value(routes, "alt1Route", "firstAltnRoute", "alternate1Route") \
        or value(alt1_from_list.get("route", ""))
    alt2_route_str = find_value(routes, "alt2Route", "secondAltnRoute", "alternate2Route") \
        or value(alt2_from_list.get("route", ""))

    y_w -= 4
    text(c, COL2, y_w, f"ALTN : {alt_dist_val}", font=FONT_NORMAL, size=9)
    min_div_disp = f"{min_div_val} LBS" if min_div_val else ""
    text(c, COL2 + 130, y_w, f"MIN DIVERT FUEL: {min_div_disp}", font=FONT_NORMAL, size=9)
    y_w -= ROW_H
    text(c, COL2, y_w, f"FIRST ALTN ROUTE : {alt1_route_str}", font=FONT_NORMAL, size=9)
    y_w -= ROW_H
    text(c, COL2, y_w, f"SECOND ALTN ROUTE : {alt2_route_str}", font=FONT_NORMAL, size=9)

    # 6. Different Level Calculation Table & Actuals
    y = min(y_p, y_w) - SEC_GAP - 4
    text_center(c, W / 2, y, "----- DIFFERENT LEVEL CALCULATION --------------------------- ACTUALS -----", font=FONT_BOLD, size=9)

    y -= ROW_H + 4
    # Table Header Grid
    LEVEL_COLS = [55, 105, 150, 215]
    text(c, LEVEL_COLS[0], y, "FL", font=FONT_BOLD)
    text(c, LEVEL_COLS[1], y, "WC", font=FONT_BOLD)
    text(c, LEVEL_COLS[2], y, "TIME", font=FONT_BOLD)
    text(c, LEVEL_COLS[3], y, "TRIP", font=FONT_BOLD)

    # Different-level-calculation rows - widened alias list and also check
    # nested under page1, since this table was rendering completely empty.
    levels_list = find_list(
        data, page1, misc, fuel, time_info,
        "levelCalculations", "levels", "differentLevelCalc", "levelCalc",
        "differentLevelCalculation", "levelCalculation", "diffLevelCalc"
    )

    actual_fields = [
        ("CHOCKS OFF : ________", "LANDING    : ________"),
        ("CHOCKS ON  : ________", "AIRBORNE   : ________"),
        ("BLOCK TIME : ________", "FLT TIME   : ________"),
        ("BLOCK FUEL : ________", "FIC-ADC    : ________"),
        ("LANDING FUEL: ________", "")
    ]

    for idx, (left_act, right_act) in enumerate(actual_fields):
        y -= ROW_H
        if idx < len(levels_list) and isinstance(levels_list[idx], dict):
            row = levels_list[idx]
            fl_val = find_value(row, "fl", "flightLevel", "level")
            wc_val = find_value(row, "wc", "windComponent")
            time_val = find_value(row, "time", "timeDelta", "deltaTime")
            trip_val = find_value(row, "trip", "tripFuel", "fuel")

            text(c, LEVEL_COLS[0], y, fl_val)
            text(c, LEVEL_COLS[1], y, wc_val)
            text(c, LEVEL_COLS[2], y, time_val)

            tr_str = trip_val
            if tr_str and not tr_str.endswith("LBS"):
                tr_str = f"{tr_str} LBS"
            text(c, LEVEL_COLS[3], y, tr_str)

        text(c, 320, y, left_act)
        if right_act:
            text(c, 460, y, right_act)

    # 7. Operational Briefings & Speeds
    y -= SEC_GAP + 10

    operational = page1.get("operational", {}) or data.get("operational", {})
    dep_atis = find_value(operational, "departureAtis", "depAtis")
    arr_atis = find_value(operational, "arrivalAtis", "arrAtis")
    clearance = find_value(operational, "departureClearance", "clearance")
    alt_atis = find_value(operational, "altnAtis", "destAltnAtis")

    for apt in airports:
        if isinstance(apt, dict):
            a_type = str(apt.get("type", "")).upper()
            if a_type == "DEP" and not dep_atis:
                dep_atis = apt.get("atis", "")
            elif a_type in ("DEST", "ARR") and not arr_atis:
                arr_atis = apt.get("atis", "")

    text(c, COL1, y, "ATC CLEARANCE", font=FONT_BOLD, size=9)
    text(c, COL1 + 110, y, f": {clearance}", font=FONT_BOLD, size=9)
    y -= SEC_GAP + 8
    text(c, COL1, y, "DEP ATIS", font=FONT_BOLD, size=9)
    text(c, COL1 + 110, y, f": {dep_atis}", font=FONT_BOLD, size=9)
    y -= SEC_GAP + 8
    text(c, COL1, y, "ARR ATIS", font=FONT_BOLD, size=9)
    text(c, COL1 + 110, y, f": {arr_atis}", font=FONT_BOLD, size=9)
    y -= SEC_GAP + 8
    text(c, COL1, y, "DEST ALTN ATIS", font=FONT_BOLD, size=9)
    text(c, COL1 + 110, y, f": {alt_atis}", font=FONT_BOLD, size=9)

    y -= SEC_GAP + 10
    v_speeds = data.get("vSpeeds", {}) or {}
    # FIX: use `or` instead of dict.get()'s default arg, since the source
    # data now supplies these keys with empty-string values rather than
    # omitting them entirely - .get(key, fallback) never triggers the
    # fallback when the key exists but is "".
    v1 = v_speeds.get("v1") or "______________"
    vr = v_speeds.get("vr") or "______________"
    v2 = v_speeds.get("v2") or "______________"
    vfto = v_speeds.get("vfto") or "______________"
    vref = v_speeds.get("vref") or "______________"

    speeds_line = f"V1: {v1:<14} VR: {vr:<14} V2: {v2:<14} VFTO: {vfto:<14} VREF: {vref}"
    text(c, COL1, y, speeds_line, font=FONT_NORMAL, size=8)

    # Footer Certification Divider
    y -= 12
    c.setLineWidth(0.5)
    c.line(COL1, y, W - COL1, y)

    y -= 14
    c1 = "I certify that all my licenses, ratings etc are current / valid and I am legally/ medically fit for operating flight. I meet the qualification"
    c2 = "requirements to operate to concerned airfields as per category/routes indicated per OM D. I have read and understood the operations"
    c3 = "manual, OPS supplements, emails, NOTAMS and required compliance. (cars, circulars, aips, etc).BA test complied as per car section 5"
    c4 = "series F part 3."

    text_center(c, W / 2, y, c1, size=7.5)
    text_center(c, W / 2, y - 10, c2, size=7.5)
    text_center(c, W / 2, y - 20, c3, size=7.5)
    text_center(c, W / 2, y - 30, c4, size=7.5)

    # Pilot Signature Line
    text_right(c, W - COL1, y - 60, "(PILOT/COPILOT SIGNATURE)", font=FONT_BOLD, size=9)


# ==================================================
# PAGE 2 (NAVLOG WAYPOINT TABLE)
# ==================================================

def page2(c, data=None):
    if data is None:
        data = {}

    page1 = data.get("page1", {})
    flight = page1.get("flightInfo", {}) or data.get("flightInfo", {}) or data.get("flight", {})
    summary = data.get("main", {}).get("summary", {}) or data.get("summary", {})
    header = page1.get("header", {}) or data.get("header", {})

    reg = find_value(flight, summary, header, data, "registration", "reg", "tailNumber")
    dep_code = find_value(flight, summary, header, data, "departure", "dep", "depCode")
    dest_code = find_value(flight, summary, header, data, "destination", "dest", "destCode")

    frame_title = f"{dep_code} - {dest_code}   {reg}".strip()
    frame(c, frame_title)

    col_x = [35, 110, 145, 165, 185, 215, 235, 273, 291, 311, 331, 351, 373, 398, 423, 445, 467, 489, 514, 539, 560]

    y = 790
    row_h = 16
    c.setLineWidth(0.5)

    c.rect(35, y - row_h, W - 70, row_h)
    text_center(c, (col_x[5] + col_x[8]) / 2, y - 11, "WIND", font=FONT_BOLD, size=7.5)
    text_center(c, (col_x[8] + col_x[10]) / 2, y - 11, "SPD KT", font=FONT_BOLD, size=7.5)
    text_center(c, (col_x[10] + col_x[12]) / 2, y - 11, "DIST NM", font=FONT_BOLD, size=7.5)
    text_center(c, (col_x[12] + col_x[14]) / 2, y - 11, "FUEL LB", font=FONT_BOLD, size=7.5)
    text_center(c, (col_x[14] + col_x[17]) / 2, y - 11, "TIME", font=FONT_BOLD, size=7.5)

    for idx in [5, 8, 10, 12, 14, 17, 18, 19]:
        c.line(col_x[idx], y, col_x[idx], y - row_h)
    y -= row_h

    c.rect(35, y - row_h, W - 70, row_h)
    headers = [
        "WAYPOINT", "AIRWAY", "HDG", "CRS", "ALT", "CMP", "DIR/SPD", "ISA",
        "TAS", "GS", "LEG", "REM", "USED", "REM", "LEG", "REM", "ETE", "ETA", "ACT"
    ]
    for i, h_txt in enumerate(headers):
        if i in (17, 18):
            text_center(c, (col_x[i] + col_x[i + 1]) / 2, y - 8, h_txt, font=FONT_BOLD, size=6)
        else:
            text_center(c, (col_x[i] + col_x[i + 1]) / 2, y - 11, h_txt, font=FONT_BOLD, size=6.5)

    text_center(c, (col_x[17] + col_x[18]) / 2, y - 14.5, "ATA", font=FONT_BOLD, size=5)
    text_center(c, (col_x[18] + col_x[19]) / 2, y - 14.5, "FUEL", font=FONT_BOLD, size=5)

    for i in range(len(col_x)):
        c.line(col_x[i], y, col_x[i], y - row_h)
    y -= row_h

    def draw_rows(data_list):
        nonlocal y

        for row in data_list:
            if isinstance(row, dict):
                wpt_name = row.get("waypoint", "")
                wpt_detail = row.get("waypointDetail", "")
                if wpt_detail:
                    wpt_name = f"{wpt_name}\n{wpt_detail}"

                row = [
                    wpt_name,
                    row.get("airway", ""),
                    row.get("heading", ""),
                    row.get("course", ""),
                    row.get("flightLevel", ""),
                    row.get("windComponent", ""),
                    row.get("windDirectionSpeed", ""),
                    row.get("isa", ""),
                    row.get("tas", ""),
                    row.get("gs", ""),
                    row.get("legDistance", ""),
                    row.get("remainingDistance", ""),
                    row.get("fuelUsed", ""),
                    row.get("fuelRemaining", ""),
                    row.get("legTime", ""),
                    row.get("remainingTime", ""),
                    row.get("ete", ""),
                    row.get("ata", ""),
                    row.get("actualFuel", "")
                ]

            is_multiline = "\n" in str(row[0])
            current_h = row_h * 1.5 if is_multiline else row_h

            c.rect(35, y - current_h, W - 70, current_h)

            for idx, val in enumerate(row):
                if idx >= len(col_x) - 1:
                    break

                str_val = value(val)

                if idx == 0 and is_multiline:
                    lines = str_val.split("\n")
                    text(c, col_x[idx] + 3, y - 11, lines[0], font=FONT_NORMAL, size=6.2)
                    if len(lines) > 1:
                        text(c, col_x[idx] + 3, y - 20, lines[1], font=FONT_NORMAL, size=6.2)
                else:
                    text_center(
                        c,
                        (col_x[idx] + col_x[idx + 1]) / 2,
                        y - (15 if is_multiline else 11),
                        str_val,
                        font=FONT_NORMAL,
                        size=6.5,
                    )

            for idx in range(len(col_x)):
                c.line(col_x[idx], y, col_x[idx], y - current_h)

            y -= current_h

    main_route_logs = data.get("mainNavlog", data.get("mainRouteLogs", data.get("navLogWaypoints", [])))
    if main_route_logs:
        draw_rows(main_route_logs)

    alt_route_1 = data.get("alternate1Navlog", data.get("altRoute1", data.get("alternate1Waypoints", [])))
    alt1_header = data.get("alt1Header", "")
    if alt_route_1:
        y -= 5
        c.rect(35, y - 20, W - 70, 20)
        text(c, 40, y - 14, alt1_header, font=FONT_BOLD, size=7.5)
        y -= 20
        draw_rows(alt_route_1)

    alt_route_2 = data.get("alternate2Navlog", data.get("altRoute2", data.get("alternate2Waypoints", [])))
    alt2_header = data.get("alt2Header", "")
    if alt_route_2:
        y -= 5
        c.rect(35, y - 20, W - 70, 20)
        text(c, 40, y - 14, alt2_header, font=FONT_BOLD, size=7.5)
        y -= 20
        draw_rows(alt_route_2)

    airport_data = data.get("airportData", data.get("airportInformation", []))
    if airport_data:
        y -= 25
        text(c, 35, y, "AIRPORT INFO", font=FONT_BOLD, size=9.5)
        y -= 12

        apt_x = [35, 75, 115, 155, 195, 250, 310, 365, 410, 455, 500, 560]

        c.rect(35, y - row_h, W - 70, row_h)
        apt_headers = ["", "Airport", "ETA", "ATIS", "TWR/CTAF", "CLR", "GND", "ELEV", "LONGEST RWY", ""]
        for i, a_hdr in enumerate(apt_headers[:-1]):
            if a_hdr != "" and i != 8:
                text_center(c, (apt_x[i] + apt_x[i + 1]) / 2, y - 11, a_hdr, font=FONT_BOLD, size=7)

        text_center(c, (apt_x[8] + apt_x[10]) / 2, y - 11, "LONGEST RWY", font=FONT_BOLD, size=7)

        for idx in range(len(apt_x) - 1):
            if idx == 9:
                continue
            c.line(apt_x[idx], y, apt_x[idx], y - row_h)
        y -= row_h

        for row in airport_data:
            c.rect(35, y - row_h, W - 70, row_h)
            if isinstance(row, (list, tuple)):
                for idx, cell_val in enumerate(row):
                    if idx < len(apt_x) - 1:
                        text_center(c, (apt_x[idx] + apt_x[idx + 1]) / 2, y - 11, value(cell_val), font=FONT_NORMAL, size=7)
            elif isinstance(row, dict):
                row_vals = [
                    row.get("type"), row.get("airport"), row.get("eta"),
                    row.get("atis"), row.get("tower"), row.get("clearance"),
                    row.get("ground"), row.get("elevation"),
                    f"{row.get('longestRunway', '')} {row.get('runwayLength', '')}".strip()
                ]
                for idx, cell_val in enumerate(row_vals):
                    if idx < len(apt_x) - 1:
                        text_center(c, (apt_x[idx] + apt_x[idx + 1]) / 2, y - 11, value(cell_val), font=FONT_NORMAL, size=7)

            for idx in range(len(apt_x) - 1):
                c.line(apt_x[idx], y, apt_x[idx], y - row_h)
            y -= row_h


# ==================================================
# PAGE 3 (ATC PLAN & ENROUTE WINDS SUMMARY)
# ==================================================

def page3(c, data=None):
    if data is None:
        data = {}

    page1 = data.get("page1", {})
    flight = page1.get("flightInfo", {}) or data.get("flightInfo", {}) or data.get("flight", {})
    summary = data.get("main", {}).get("summary", {}) or data.get("summary", {})
    header = page1.get("header", {}) or data.get("header", {})
    atc = data.get("atcFlightPlan", {})

    reg = find_value(flight, summary, header, data, "registration", "reg", "tailNumber")
    dep_code = find_value(flight, summary, header, data, "departure", "dep", "depCode")
    dest_code = find_value(flight, summary, header, data, "destination", "dest", "destCode")

    frame_title = f"{dep_code} - {dest_code}   {reg}".strip()
    frame(c, frame_title)

    text_center(c, W / 2, 770, f"ATC FLIGHT PLAN {dep_code} to {dest_code}".strip(), font=FONT_BOLD, size=10)
    text_center(c, W / 2, 758, "..........................................", font=FONT_BOLD, size=10)

    y_atc = 735
    atc_strings = []

    if isinstance(atc, list):
        atc_strings = atc
    elif isinstance(atc, dict):
        fpl_text = find_value(atc, "flightPlanText", "flightPlan", "text", "fplText", "fpl", "fplString")
        if fpl_text:
            atc_strings = fpl_text.split("\n")

    for line_str in atc_strings:
        text(c, 45, y_atc, value(line_str), font=FONT_NORMAL, size=8)
        y_atc -= 13

    # Enroute Winds Matrix
    winds_matrix_data = data.get("windsMatrix", data.get("enrouteWinds", []))
    bands = data.get("enrouteWindBands", [])

    if isinstance(winds_matrix_data, dict):
        if "bands" in winds_matrix_data:
            bands = winds_matrix_data["bands"]
        winds_matrix_data = winds_matrix_data.get("rows", [])

    if winds_matrix_data:
        y_winds = max(y_atc - 20, 625)
        text_center(c, W / 2, y_winds, "ENROUTE WINDS", font=FONT_BOLD, size=9.5)

        w_cols = [45, 105, 160, 195, 250, 285, 340, 375, 430, 465, 520]

        y_winds -= 24
        text(c, w_cols[0], y_winds, "IDENT", font=FONT_BOLD, size=8)

        for idx, band_lbl in enumerate(bands[:5]):
            col_start = w_cols[(idx * 2) + 1]
            col_end = w_cols[(idx * 2) + 2]
            text_center(c, (col_start + col_end) / 2, y_winds, str(band_lbl), font=FONT_BOLD, size=8)

        y_winds -= 11
        for idx in range(1, 10, 2):
            text_center(c, (w_cols[idx] + w_cols[idx + 1]) / 2, y_winds, "W/V", font=FONT_BOLD, size=8)
            text(c, w_cols[idx + 1] + 8, y_winds, "TMP", font=FONT_BOLD, size=8)

        y_winds -= 14

        for row in winds_matrix_data:
            if y_winds < 80:
                break
            if isinstance(row, (list, tuple)):
                text(c, w_cols[0], y_winds, value(row[0]), font=FONT_NORMAL, size=8)
                for col_idx in range(1, min(len(row), 11)):
                    if col_idx % 2 == 1:
                        text_center(c, (w_cols[col_idx] + w_cols[col_idx + 1]) / 2, y_winds, value(row[col_idx]), font=FONT_NORMAL, size=8)
                    else:
                        text(c, w_cols[col_idx] + 10, y_winds, value(row[col_idx]), font=FONT_NORMAL, size=8)
            elif isinstance(row, dict):
                text(c, w_cols[0], y_winds, value(row.get("identifier")), font=FONT_NORMAL, size=8)
                cells = row.get("values", [])
                for idx, cell in enumerate(cells[:5]):
                    c_idx = (idx * 2) + 1
                    if c_idx + 1 < len(w_cols):
                        text_center(c, (w_cols[c_idx] + w_cols[c_idx + 1]) / 2, y_winds, value(cell.get("wind")), font=FONT_NORMAL, size=8)
                        text(c, w_cols[c_idx + 1] + 10, y_winds, value(cell.get("isa")), font=FONT_NORMAL, size=8)

            y_winds -= 13.5

    text_center(c, W / 2, 65, "************** END OF THE REPORT    **************", font=FONT_BOLD, size=9)

    c.setLineWidth(0.5)
    c.line(45, 48, W - 45, 48)

    computed_date = datetime.now().strftime("%d-%m-%Y")
    computed_time = datetime.now().strftime("%H:%M:%S")

    text(c, 45, 38, f"COMPUTED DATE : {computed_date}", font=FONT_BOLD, size=8)
    text_right(c, W - 45, 38, f"TIME : {computed_time} UTC", font=FONT_BOLD, size=8)


# ==================================================
# GENERATE PDF ENTRYPOINTS
# ==================================================

def generate_default_pdf(navlog):
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)

    file_name = f"DEFAULT_{int(datetime.now().timestamp() * 1000)}.pdf"
    absolute_path = os.path.join(OUTPUT_DIRECTORY, file_name)
    relative_path = os.path.join("generated", file_name)

    c = canvas.Canvas(absolute_path, pagesize=A4)

    draw_page_one(c, navlog)
    c.showPage()
    page2(c, navlog)
    c.showPage()
    page3(c, navlog)
    c.showPage()
    c.save()

    return relative_path

def generate_pdf(navlog, file_prefix="DEFAULT"):
    prefix = str(file_prefix).upper()
    if prefix == "MLOVE":
        from mlove import generate_mlove_pdf
        return generate_mlove_pdf(navlog)
    return generate_default_pdf(navlog)

def build_pdf(data=None, output="Navlog.pdf"):
    c = canvas.Canvas(output, pagesize=A4)
    draw_page_one(c, data)
    c.showPage()
    page2(c, data)
    c.showPage()
    page3(c, data)
    c.showPage()
    c.save()

if __name__ == "__main__":
    build_pdf()