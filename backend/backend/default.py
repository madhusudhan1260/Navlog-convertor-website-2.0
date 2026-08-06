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

AIRPORT_NAME_LOOKUP = {
    "VOHY": "BEGUMPET",
    "VIDP": "DELHI",
    "VECC": "KOLKATA",
}

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

def kv(c, label_x, value_right_x, y, label, val, unit="", font=FONT_NORMAL, size=8.5, bold_label=False, colon_x=None):
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
    if not s:
        return s
    s = re.sub(r'\bFL(\d)', r'FL \1', s)
    s = re.sub(r'(ISA:\s*[+-]?\d+)(?!\s*°)', r'\1°C', s)
    return s

def _build_summary_fallback(data, page1):
    merged = {}
    merged.update(page1.get("flightInfo", {}) or {})
    merged.update(data.get("atcFlightPlan", {}) or {})
    return merged


# ==================================================
# PAGE 1 (MAIN OPERATIONAL FLIGHT PLAN)
# ==================================================

def draw_page_one(c, data=None):
    if data is None:
        data = {}

    page1 = data.get("page1", {})
    flight = page1.get("flightInfo", {}) or data.get("flightInfo", {}) or data.get("flight", {})
    summary = _build_summary_fallback(data, page1)
    fuel = page1.get("fuel", {}) or data.get("fuel", {})
    weight = page1.get("weight", {}) or data.get("weight", {})
    time_info = page1.get("time", {}) or data.get("time", {})
    header = page1.get("header", {}) or data.get("header", {})
    misc = page1.get("misc", {}) or data.get("misc", {})
    routes = data.get("routes", {}) or page1.get("routes", {})
    airports = data.get("airportInformation", []) or data.get("airportData", [])

    # Exact Grid Alignment X-Coordinates
    C1 = MARGIN_X + 20          # 55pt
    C1_COLON = C1 + 105         # 160pt
    C1_VAL_RIGHT = C1 + 220     # 275pt

    C2 = 295                    # 295pt
    C2_COLON = C2 + 80          # 375pt
    RIGHT_MARGIN_VAL = W - MARGIN_X - 15  # 545pt

    C3 = 445                    # 445pt
    C3_COLON = C3 + 38          # 483pt

    # Outer Frame Border
    c.setLineWidth(1)
    c.rect(MARGIN_X, MARGIN_Y, INNER_W, INNER_H)

    # 1. Top-Right Header (outside frame top)
    reg = find_value(flight, summary, header, data, "registration", "reg", "tailNumber") or "VTECG"
    dep_code = find_value(flight, summary, header, data, "departure", "dep", "depCode", "origin") or "VIDP"
    dest_code = find_value(flight, summary, header, data, "destination", "dest", "destCode") or "VECC"

    header_right_str = f"{dep_code} - {dest_code}   {reg}".strip()
    text_right(c, W - MARGIN_X, H - MARGIN_Y + 10, header_right_str, font=FONT_NORMAL, size=9)

    # 2. Main Title Banner
    ac_type = find_value(header, summary, flight, data, "aircraftType", "type", "acType") or "C25A"
    date_str = find_value(header, summary, flight, data, "date", "flightDate", "dof", "dayOfFlight") or "04AUG26"
    etd = find_value(time_info, summary, "etd", "etd_utc") or "0945Z"
    eta = find_value(time_info, summary, "eta", "eta_utc") or "1155Z"

    banner_title = f"- - - - - {reg} ({ac_type}) {date_str} NAV LOG/ OPS FPL FOR ETD {etd} (ETA {eta}) - - - - -"
    text_center(c, W / 2, H - MARGIN_Y - 20, banner_title, font=FONT_NORMAL, size=8.5)

    # 3. Flight Summary Block
    dep_name = find_value(flight, summary, "departureName", "dep_name") or "DELHI"
    dest_name = find_value(flight, summary, "destinationName", "dest_name") or "KOLKATA"

    dep_disp = f"{dep_code} - {dep_name}" if dep_name else dep_code
    dest_disp = f"{dest_code} - {dest_name}" if dest_name else dest_code

    dist_val = find_value(time_info, summary, flight, "plannedRouteDistance", "dist") or "716NM"
    if dist_val and not dist_val.endswith("NM"):
        dist_val = f"{dist_val}NM"

    track_val = "045 DEG"
    pax_val = find_value(weight, flight, summary, data, "pax") or "5"

    y = H - MARGIN_Y - 45
    text(c, C1, y, "DEP", font=FONT_NORMAL, size=8.5)
    text(c, C1 + 38, y, ":", font=FONT_NORMAL, size=8.5)
    text(c, C1 + 48, y, dep_disp, font=FONT_NORMAL, size=8.5)

    text(c, C2, y, "DIST", font=FONT_NORMAL, size=8.5)
    text(c, C2 + 45, y, ":", font=FONT_NORMAL, size=8.5)
    text(c, C2 + 55, y, dist_val, font=FONT_NORMAL, size=8.5)

    text(c, C3, y, "TRACK", font=FONT_NORMAL, size=8.5)
    text(c, C3_COLON, y, ":", font=FONT_NORMAL, size=8.5)
    text(c, C3_COLON + 10, y, track_val, font=FONT_NORMAL, size=8.5)

    y -= 14
    text(c, C1, y, "DEST", font=FONT_NORMAL, size=8.5)
    text(c, C1 + 38, y, ":", font=FONT_NORMAL, size=8.5)
    text(c, C1 + 48, y, dest_disp, font=FONT_NORMAL, size=8.5)

    text(c, C2, y, "CRUISE", font=FONT_NORMAL, size=8.5)
    text(c, C2 + 45, y, ":", font=FONT_NORMAL, size=8.5)

    text(c, C3, y, "PAX", font=FONT_NORMAL, size=8.5)
    text(c, C3_COLON, y, ":", font=FONT_NORMAL, size=8.5)
    text(c, C3_COLON + 10, y, pax_val, font=FONT_NORMAL, size=8.5)

    # Cruise Text Auto-Wrap
    cruise_text = "IFR 230 KIAS/M0.55 - MAXIMUM RANGE CRUISE @ FL450 - NORMAL 2000 FPM"
    p_style = ParagraphStyle(name="CruiseStyle", fontName=FONT_NORMAL, fontSize=8.5, leading=10)
    p = Paragraph(cruise_text, p_style)
    p_width = C3 - (C2 + 55) - 5
    w_p, h_p = p.wrap(p_width, 50)
    p.drawOn(c, C2 + 55, y - h_p + 8)

    y -= max(int(h_p), 22) + 2

    # Main Route
    main_route = "FL450 - NORMAL 2000 FPM DPN V18 ALI G452 LKN R460 CEA"
    text(c, C1, y, f"MAIN ROUTE : {main_route}", font=FONT_NORMAL, size=8.5)

    # PIC & FO Block
    y -= 15
    pic = find_value(data, flight, summary, page1, "pic", "captain") or "SHREYAS VYAS"
    if not pic.startswith("CAPT"):
        pic = f"CAPT {pic}"
        
    fo = find_value(data, flight, summary, page1, "fo", "copilot", "coPilot", "firstOfficer", "foName", "fo_name", "sic") or "CAPT SANSKAR MISHRA"
    
    text(c, C1, y, "PIC", font=FONT_NORMAL, size=8.5)
    text(c, C1 + 38, y, ":", font=FONT_NORMAL, size=8.5)
    text(c, C1 + 48, y, pic, font=FONT_NORMAL, size=8.5)

    text(c, C2, y, "FO", font=FONT_NORMAL, size=8.5)
    text(c, C2 + 45, y, ":", font=FONT_NORMAL, size=8.5)
    text(c, C2 + 55, y, fo, font=FONT_NORMAL, size=8.5)

    # 4. Computed Fuel & Weights Section
    block_fuel_raw = "3200"
    flight_fuel_raw = "1744"
    comp_fuel = block_fuel_raw
    min_trip_calc = 2962
    max_trip = "3329"

    top_climb = "FL 390 (ISA: -56°C)"
    takeoff_fuel_disp = 3075
    landing_fuel_disp = 1456
    wind_val = "3KT HEAD (045°/017)"

    y -= 18
    kv(c, C1, C1_VAL_RIGHT, y, "COMPUTED FUEL", comp_fuel, "LBS", font=FONT_NORMAL, bold_label=False, colon_x=C1_COLON)
    kv(c, C2, RIGHT_MARGIN_VAL, y, "BLOCK FUEL", flight_fuel_raw, "LBS", font=FONT_NORMAL, bold_label=False, colon_x=C2_COLON)

    y -= 13.5
    kv(c, C1, C1_VAL_RIGHT, y, "MIN. TRIP FUEL", min_trip_calc, "LBS", font=FONT_NORMAL, bold_label=False, colon_x=C1_COLON)
    kv(c, C2, RIGHT_MARGIN_VAL, y, "TAKE OFF FUEL", takeoff_fuel_disp, "LBS", font=FONT_NORMAL, bold_label=False, colon_x=C2_COLON)

    y -= 13.5
    kv(c, C1, C1_VAL_RIGHT, y, "MAX. TRIP FUEL", max_trip, "LBS", font=FONT_NORMAL, bold_label=False, colon_x=C1_COLON)
    kv(c, C2, RIGHT_MARGIN_VAL, y, "LANDING FUEL", landing_fuel_disp, "LBS", font=FONT_NORMAL, bold_label=False, colon_x=C2_COLON)

    y -= 13.5
    kv(c, C1, C1_VAL_RIGHT, y, "TOP CLIMB TEMP", top_climb, "", font=FONT_NORMAL, bold_label=False, colon_x=C1_COLON)
    kv(c, C2, RIGHT_MARGIN_VAL, y, "WIND", wind_val, "", font=FONT_NORMAL, bold_label=False, colon_x=C2_COLON)

    # 5. Plan Time & Fuel / Plan WT Matrix
    y -= 18
    text_center(c, W / 2, y, "- - - - - - - - - - PLAN TIME & FUEL - - - - - - - - - - - - - - - - - - - - - - - - - PLAN WT (in LBS) - - - - - - - - - - - - - - - - - - -", font=FONT_NORMAL, size=8)

    # FIX: CONTINGENCY was a hardcoded "0:13"/81 literal instead of the
    # real computed figure (5% of trip fuel vs. 30-min hold at 1,500ft,
    # whichever is higher) that claude.py now works out and passes
    # through in `fuel` - read it from there, falling back to the old
    # literal only if that data is somehow missing.
    contingency_time = find_value(fuel, "contingencyTime", "contingency_time") or "0:13"
    contingency_lbs = find_value(fuel, "contingency", "contingencyFuel") or 81

    plan_rows = [
        ("TRIP", "2:10", 1619),
        ("TAXI", "0:10", 125),
        ("CONTINGENCY", contingency_time, contingency_lbs),
        ("FINAL RESERVE FUEL", "0:30", 400),
        ("XTRA", "0:22", 238),
        ("ALTN1", "0:50", 737),
        ("ALTN2", "0:43", 647),
    ]

    weight_rows = [
        ("BASIC WT", 8301),
        ("LOAD", 995),
        ("ZERO FUEL", 9296),
        ("T.OFF WT", 12371),
        ("LAND WT", 10752),
    ]

    PLAN_TIME_X = C1 + 120

    y_p = y - 16
    for label_str, time_val, lbs_val in plan_rows:
        text(c, C1, y_p, label_str, font=FONT_NORMAL, size=8.5)
        text(c, C1_COLON, y_p, ":", font=FONT_NORMAL, size=8.5)
        if time_val:
            text(c, PLAN_TIME_X, y_p, str(time_val), font=FONT_NORMAL, size=8.5)
        if lbs_val not in (None, ""):
            text_right(c, C1_VAL_RIGHT, y_p, f"{lbs_val} LBS", font=FONT_NORMAL, size=8.5)
        y_p -= 13.5

    y_w = y - 16
    for label_str, lbs_val in weight_rows:
        kv(c, C2, RIGHT_MARGIN_VAL, y_w, label_str, lbs_val, "LBS", colon_x=C2_COLON, font=FONT_NORMAL, size=8.5, bold_label=False)
        y_w -= 13.5

    # Endurance & Alternate Details
    text(c, PLAN_TIME_X, y_p, "---------", font=FONT_NORMAL, size=8.5)
    text_right(c, C1_VAL_RIGHT, y_p, "-------------", font=FONT_NORMAL, size=8.5)
    y_p -= 12

    text(c, C1, y_p, "ENDURANCE", font=FONT_NORMAL, size=8.5)
    text(c, C1_COLON, y_p, ":", font=FONT_NORMAL, size=8.5)
    text(c, PLAN_TIME_X, y_p, "4:15", font=FONT_NORMAL, size=8.5)
    text_right(c, C1_VAL_RIGHT, y_p, "3200 LBS", font=FONT_NORMAL, size=8.5)

    y_w -= 2
    text(c, C2, y_w, "ALTN : 223NM", font=FONT_NORMAL, size=8.5)
    text(c, C2 + 100, y_w, "MIN DIVERT FUEL: 1137 LBS", font=FONT_NORMAL, size=8.5)

    y_w -= 13.5
    text(c, C2, y_w, "FIRST ALTN ROUTE : CEA W41 BBS", font=FONT_NORMAL, size=8.5)

    y_w -= 13.5
    text(c, C2, y_w, "SECOND ALTN ROUTE : CEA G450 JJS W109 RRC", font=FONT_NORMAL, size=8.5)

    # 6. Different Level Calculation Table & Actuals
    y = min(y_p, y_w) - 16
    text_center(c, W / 2, y, "- - - - - - - - - DIFFERENT LEVEL CALCULATION - - - - - - - - - - - - - - - - - - - - - - - - - - ACTUALS - - - - - - - - - - - - - - - - - - -", font=FONT_NORMAL, size=8)

    y -= 16
    LEVEL_COLS = [C1, C1 + 45, C1 + 85, C1 + 145]
    text(c, LEVEL_COLS[0], y, "FL", font=FONT_BOLD, size=8.5)
    text(c, LEVEL_COLS[1], y, "WC", font=FONT_BOLD, size=8.5)
    text(c, LEVEL_COLS[2], y, "TIME", font=FONT_BOLD, size=8.5)
    text(c, LEVEL_COLS[3], y, "TRIP", font=FONT_BOLD, size=8.5)

    levels_list = [
        {"fl": "FL 350", "wc": "H2", "time": "", "trip": "1772 LBS"},
        {"fl": "FL 370", "wc": "H2", "time": "(+0:08)", "trip": "1729 LBS"},
        {"fl": "FL 390", "wc": "H2", "time": "", "trip": "1693 LBS"},
        {"fl": "FL 410", "wc": "H2", "time": "(+0:05)", "trip": "1662 LBS"},
        {"fl": "FL 450", "wc": "H3", "time": "", "trip": "1619 LBS"},
    ]

    ACTUALS_LEFT_X = 295
    ACTUALS_RIGHT_X = 430

    actual_fields = [
        ("CHOCKS OFF : ________", "LANDING    : ________"),
        ("CHOCKS ON  : ________", "AIRBORNE   : ________"),
        ("BLOCK TIME : ________", "FLT TIME   : ________"),
        ("BLOCK FUEL : ________", "FIC-ADC    : ________"),
        ("LANDING FUEL: ________", "")
    ]

    for idx, (left_act, right_act) in enumerate(actual_fields):
        y -= 13.5
        if idx < len(levels_list):
            row = levels_list[idx]
            text(c, LEVEL_COLS[0], y, row["fl"], font=FONT_NORMAL, size=8.5)
            text(c, LEVEL_COLS[1], y, row["wc"], font=FONT_NORMAL, size=8.5)
            text(c, LEVEL_COLS[2], y, row["time"], font=FONT_NORMAL, size=8.5)
            text(c, LEVEL_COLS[3], y, row["trip"], font=FONT_NORMAL, size=8.5)

        text(c, ACTUALS_LEFT_X, y, left_act, font=FONT_NORMAL, size=8.5)
        if right_act:
            text(c, ACTUALS_RIGHT_X, y, right_act, font=FONT_NORMAL, size=8.5)

    # 7. Operational Briefings & Speeds Block
    y -= 38
    text(c, C1, y, "ATC CLEARANCE", font=FONT_BOLD, size=8.5)
    text(c, C1_COLON - 20, y, ":", font=FONT_BOLD, size=8.5)

    y -= 38
    text(c, C1, y, "DEP ATIS", font=FONT_BOLD, size=8.5)
    text(c, C1_COLON - 20, y, ":", font=FONT_BOLD, size=8.5)

    y -= 38
    text(c, C1, y, "ARR ATIS", font=FONT_BOLD, size=8.5)
    text(c, C1_COLON - 20, y, ":", font=FONT_BOLD, size=8.5)

    y -= 38
    text(c, C1, y, "DEST ALTN ATIS", font=FONT_BOLD, size=8.5)
    text(c, C1_COLON - 20, y, ":", font=FONT_BOLD, size=8.5)

    y -= 38
    speeds_line = "V1: ______________ VR: ______________ V2: ______________ VFTO: ______________ VREF: ______________"
    text(c, C1, y, speeds_line, font=FONT_NORMAL, size=8)

    # Certification Footer
    y -= 10
    c.setLineWidth(0.5)
    c.line(C1, y, W - C1, y)

    y -= 13
    c1 = "I certify that all my licenses, ratings etc are current / valid and I am legally/ medically fit for operating flight. I meet the qualification"
    c2 = "requirements to operate to concerned airfields as per category/routes indicated per OM D. I have read and understood the operations"
    c3 = "manual, OPS supplements, emails, NOTAMS and required compliance. (cars, circulars, aips, etc).BA test complied as per car section 5"
    c4 = "series F part 3."

    # Updated font size to 8.5 with matching vertical offsets
    text_center(c, W / 2, y, c1, size=8.5)
    text_center(c, W / 2, y - 11, c2, size=8.5)
    text_center(c, W / 2, y - 22, c3, size=8.5)
    text_center(c, W / 2, y - 33, c4, size=8.5)

    # Signature Line
    text_right(c, W - C1, y - 52, "(PILOT/COPILOT SIGNATURE)", font=FONT_BOLD, size=8.5)


# ==================================================
# PAGE 2 (NAVLOG WAYPOINT TABLE)
# ==================================================

def page2(c, data=None):
    if data is None:
        data = {}

    page1 = data.get("page1", {})
    flight = page1.get("flightInfo", {}) or data.get("flightInfo", {}) or data.get("flight", {})
    summary = _build_summary_fallback(data, page1)
    header = page1.get("header", {}) or data.get("header", {})

    reg = find_value(flight, summary, header, data, "registration", "reg", "tailNumber") or "VTECG"
    dep_code = find_value(flight, summary, header, data, "departure", "dep", "depCode") or "VIDP"
    dest_code = find_value(flight, summary, header, data, "destination", "dest", "destCode") or "VECC"

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
    summary = _build_summary_fallback(data, page1)
    header = page1.get("header", {}) or data.get("header", {})
    atc = data.get("atcFlightPlan", {})

    reg = find_value(flight, summary, header, data, "registration", "reg", "tailNumber") or "VTECG"
    dep_code = find_value(flight, summary, header, data, "departure", "dep", "depCode") or "VIDP"
    dest_code = find_value(flight, summary, header, data, "destination", "dest", "destCode") or "VECC"

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
                        text(c, w_cols[col_idx + 1] + 10, y_winds, value(row[col_idx]), font=FONT_NORMAL, size=8)
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