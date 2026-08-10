# ======================================================
# FOREFLIGHT -> FORUM AVIATION OPS FPL TRANSFORMER
# ======================================================

import re


# ======================================================
# PER-TAIL FUEL CONSTANTS (LAST-RESORT FALLBACK ONLY)
# ======================================================
# MIN/MAX TRIP FUEL are aircraft-config constants (not derivable from the
# flight plan itself) that should normally come from user_input on the
# frontend form. This table exists purely as a last-resort fallback for
# known tails when the form genuinely doesn't supply a value - it must
# NEVER override an explicit user_input figure. Extend as needed.
AIRCRAFT_FUEL_LIMITS = {
    "VTSRE": {"minTrip": "2845", "maxTrip": "3961"},
    # VTCSP (C56X): MAX TRIP FUEL taken from the operator's own reference
    # OPS FPL for this tail. MIN TRIP FUEL is not listed - that template
    # derives it from REQUIRED fuel per flight.
    "VTCSP": {"maxTrip": "6175"},
    "VTBBN": {"maxTrip": "3235"},
}


# VTCSP and INDO PACIFIC 1 are the same document family: the same page-1
# "PLAN TIME & FUEL" layout, and the same derivation rules behind it (flat
# taxi time, contingency, MIN TRIP FUEL, TRACK and TOP CLIMB TEMP).
PLAN_TIME_TEMPLATES = ("VTCSP", "INDOPACIFIC", "INDOPACIFIC1", "INDOPACIFIC2")

# Contingency time on those templates is a tenth of trip time, but never
# less than five minutes - see the contingency block below.
CONTINGENCY_MINIMUM_MINUTES = 5


# ======================================================
# HELPERS
# ======================================================

def object_(value):
    """
    Returns the dictionary if value is a dict,
    otherwise returns an empty dict.
    """
    if isinstance(value, dict):
        return value
    return {}


def array(value):
    """
    Returns the list if value is a list,
    otherwise returns an empty list.
    """
    if isinstance(value, list):
        return value
    return []


def first(*values):
    """
    Returns the first non-empty value.
    """
    for value in values:
        if value is None:
            continue

        if str(value).strip() != "":
            return value

    return ""


def sum_if_complete(*values):
    """
    Returns empty string unless all supplied values
    are valid numbers.
    """
    nums = []

    for v in values:
        if v is None or str(v).strip() == "":
            continue

        try:
            nums.append(float(v))
        except:
            return ""

    if len(nums) == 0:
        return ""

    return str(round(sum(nums)))


def subtract_if_complete(a, b):
    if a is None or str(a).strip() == "":
        return ""

    if b is None or str(b).strip() == "":
        return ""

    try:
        na = float(a)
        nb = float(b)
    except:
        return ""

    return str(round(na - nb))


def utc_to_ist(time_str):
    digits = re.sub(r"[^\d]", "", str(time_str or ""))

    if len(digits) < 4:
        return ""

    hh = int(digits[:2])
    mm = int(digits[2:4])

    total_minutes = (hh * 60 + mm + 330) % 1440

    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def hhmm_to_minutes(value):
    """Parse "H:MM", "HH:MM" or bare "HHMM"/"HMM" into total minutes.
    Returns None if it can't be parsed as a clock duration."""
    v = str(value or "").strip()
    if not v:
        return None

    match = re.match(r"^(\d{1,3}):(\d{2})$", v)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))

    digits = re.sub(r"[^\d]", "", v)
    if len(digits) in (3, 4):
        return int(digits[:-2]) * 60 + int(digits[-2:])

    return None


def minutes_to_hhmm(total_minutes):
    if total_minutes is None:
        return ""
    total_minutes = max(0, round(total_minutes))
    return f"{total_minutes // 60}:{total_minutes % 60:02d}"


def minutes_to_hm_upper(total_minutes):
    """0h50m-style duration, e.g. 50 -> "0H50M" - the format the ALT1/
    ALT2 summary block at the bottom of page 1 uses for ETE, matching
    ForeFlight's own "0h50m" spelling (just uppercased), as opposed to
    the "0:50" colon format used everywhere else in this template."""
    if total_minutes is None:
        return ""
    total_minutes = max(0, round(total_minutes))
    return f"{total_minutes // 60}H{total_minutes % 60:02d}M"


# Standard per-head weight allowances used by VTBBD's PAX / CC rows.
PAX_UNIT_WEIGHT = 165
CC_UNIT_WEIGHT = 187

# VTBBD's own page-3 footnote spells its trip fuel out as
# "A TO B + APCH & LDG AT B". The approach-and-landing allowance is a
# fixed 220 lbs / 6 minutes - the same pair vtbbd.py subtracts from the
# navlog's last REM to print its APPROCH AND LAND row.
APPROACH_LANDING_FUEL = 220
APPROACH_LANDING_MINUTES = 6

# The TAXI row on these templates is a flat operator standard, not a
# derived figure - both reference documents print 0:10.
FLAT_TAXI_MINUTES = 10


def last_value(rows, key):
    """Last row of a navlog carrying a non-empty, non-dash `key`."""
    for row in reversed(array(rows)):
        raw = str(object_(row).get(key, "")).strip()
        if raw and raw != "-":
            return raw
    return ""


def last_numeric(rows, key):
    """Last row of a navlog carrying a usable number under `key`. The
    tail rows of a ForeFlight export can be dashes, so this walks
    backwards until it finds a real figure."""
    for row in reversed(array(rows)):
        raw = str(object_(row).get(key, "")).replace(",", "").strip()
        try:
            return float(raw)
        except ValueError:
            continue
    return None


def expand_head_count(value_in, unit_weight):
    """VTBBD prints PAX / CC as "<count> - <total weight>": one passenger
    at 165 lbs shows as "1 - 165", two as "2 - 330". Given a plain head
    count this expands it. Anything that already contains a dash, or that
    isn't a whole number, is passed straight through so an operator can
    still type the pair by hand."""
    raw = str(value_in or "").strip()
    if not raw or "-" in raw:
        return raw

    try:
        count = int(float(raw))
    except ValueError:
        return raw

    return f"{count} - {count * unit_weight}"


def parse_fuel_flow_per_hour(text):
    """Parses ForeFlight's free-text "NNN lbs/hr (Per Engine)" Fuel Flow
    figure into a single total lbs/hr number. Doubles the figure when the
    text says "Per Engine" (this fleet is twin-engine); returns None if
    no number can be found at all."""
    v = str(text or "")
    match = re.search(r"([\d.]+)\s*lbs?/hr", v, re.IGNORECASE)
    if not match:
        return None

    rate = float(match.group(1))
    if re.search(r"per\s*engine", v, re.IGNORECASE):
        rate *= 2
    return rate


# ======================================================
# VALIDATE / SHAPE OUTPUT
# ======================================================

def validate(data):
    data = object_(data)

    data["page1"] = object_(data.get("page1"))
    page1 = data["page1"]

    page1["header"] = object_(page1.get("header"))
    page1["flightInfo"] = object_(page1.get("flightInfo"))
    page1["time"] = object_(page1.get("time"))
    page1["fuel"] = object_(page1.get("fuel"))
    page1["weight"] = object_(page1.get("weight"))
    page1["misc"] = object_(page1.get("misc"))
    page1["operational"] = object_(page1.get("operational"))
    page1["alternates"] = array(page1.get("alternates"))

    data["routes"] = object_(data.get("routes"))
    data["atcFlightPlan"] = object_(data.get("atcFlightPlan"))

    data["mainNavlog"] = array(data.get("mainNavlog"))
    data["alternate1Navlog"] = array(data.get("alternate1Navlog"))
    data["alternate2Navlog"] = array(data.get("alternate2Navlog"))

    data["airportInformation"] = array(data.get("airportInformation"))

    data["enrouteWindBands"] = array(data.get("enrouteWindBands"))
    data["enrouteWinds"] = array(data.get("enrouteWinds"))

    # FIX: these two were being parsed by htmlParser.py but never carried
    # through by convert_with_claude() below, so they always rendered
    # empty in the PDF regardless of what the source HTML contained.
    data["levelCalculations"] = array(data.get("levelCalculations"))
    data["vSpeeds"] = object_(data.get("vSpeeds"))

    return data


# ======================================================
# WAYPOINT ROW MAPPING
# ======================================================

def map_waypoint_row(row):
    row = object_(row)

    return {
        "waypoint": row.get("waypoint", ""),
        "waypointDetail": row.get("waypointDetail", ""),
        "airway": row.get("airway", ""),
        "heading": row.get("heading", ""),
        "course": row.get("course", ""),
        "flightLevel": row.get("flightLevel", ""),
        "windComponent": row.get("windComponent", ""),
        "windDirectionSpeed": row.get("windDirectionSpeed", ""),
        "isa": row.get("isa", ""),
        "tas": row.get("tas", ""),
        "gs": row.get("gs", ""),
        "legDistance": row.get("legDistance", ""),
        "remainingDistance": row.get("remainingDistance", ""),
        "fuelUsed": row.get("fuelUsed", ""),
        "fuelRemaining": row.get("fuelRemaining", ""),
        "actualFuel": row.get("actualFuel", ""),
        "legTime": row.get("legTime", ""),
        "remainingTime": row.get("remainingTime", ""),
        "ete": row.get("ete", ""),
        "eta": row.get("eta", ""),
        "ata": row.get("ata", "")
    }


def map_airport_row(row):
    row = object_(row)

    return {
        "type": row.get("type", ""),
        "airport": row.get("airport", ""),
        "eta": row.get("eta", ""),
        "atis": row.get("atis", ""),
        "tower": row.get("tower", ""),
        "clearance": row.get("clearance", ""),
        "ground": row.get("ground", ""),
        "elevation": row.get("elevation", ""),
        "longestRunway": row.get("runway", ""),
        "runwayLength": row.get("runwayLength", "")
    }


def map_level_calculation_row(row):
    """FIX: mirrors htmlParser.py's parse_level_calculations() output
    shape ({fl, wc, time, trip}) so default.py's DIFFERENT LEVEL
    CALCULATION table has something to render."""
    row = object_(row)

    return {
        "fl": row.get("fl", ""),
        "wc": row.get("wc", ""),
        "time": row.get("time", ""),
        # ForeFlight's unedited delta, zeros included - see htmlParser.
        "timeAll": row.get("timeAll", row.get("time", "")),
        "trip": row.get("trip", "")
    }


# ======================================================
# MAIN CONVERSION FUNCTION
# ======================================================

def convert_with_claude(master_json, template="MLOVE"):
    print("🔧 Building Forum Aviation OPS FPL JSON (deterministic transform)...")

    template = str(template or "MLOVE").upper()

    user_input = object_(master_json.get("userInput"))
    main = object_(master_json.get("mainRoute"))
    alt1 = object_(master_json.get("alternate1"))
    alt2 = object_(master_json.get("alternate2"))

    summary = object_(main.get("summary"))
    fw = object_(main.get("fuelWeights"))

    alt1_summary = object_(alt1.get("summary"))
    alt1_fw = object_(alt1.get("fuelWeights"))

    alt2_summary = object_(alt2.get("summary"))
    alt2_fw = object_(alt2.get("fuelWeights"))

    data = validate({})
    page1 = data["page1"]

    # ======================================================
    # FLIGHT INFO
    # ======================================================

    page1["flightInfo"]["flight"] = first(
        user_input.get("callSign"),
        summary.get("registration")
    )

    page1["flightInfo"]["pic"] = first(
        user_input.get("pilotName"),
        user_input.get("picName"),
        user_input.get("commanderName"),
        user_input.get("captainName"),
        summary.get("pic")
    )

    # FIX #3: FO Fallback added
    page1["flightInfo"]["fo"] = first(
        user_input.get("coPilotName"),
        user_input.get("foName"),
        user_input.get("firstOfficerName"),
        user_input.get("fo"),
        summary.get("fo")
    )

    # VTBBD-only: cabin crew name, printed as a second line under F/O.
    page1["flightInfo"]["cc"] = first(
        user_input.get("cabinCrewName"),
        user_input.get("ccName"),
        user_input.get("cc")
    )

    page1["flightInfo"]["registration"] = first(
        summary.get("registration"),
        user_input.get("callSign")
    )

    page1["flightInfo"]["departure"] = first(
        user_input.get("departure"),
        main.get("departure")
    )

    page1["flightInfo"]["destination"] = first(
        user_input.get("destination"),
        main.get("destination")
    )

    page1["flightInfo"]["flightLevel"] = first(
        user_input.get("flightLevel"),
        summary.get("altitude")
    )

    page1["flightInfo"]["date"] = first(
        user_input.get("date"),
        user_input.get("flightDate"),
        user_input.get("dateOfFlight"),
        summary.get("date")
    )

    alt1_dest = first(alt1.get("destination"), "")
    alt2_dest = first(alt2.get("destination"), "")

    # FIX: this field is the FLIGHT INFO box's single "ALT1" line, which
    # ForeFlight's source PDFs render as "<main destination>,<alt1
    # destination>" (the diversion path out of the destination), NOT a
    # list of both alternates' own destinations. It was previously built
    # as "alt1_dest,alt2_dest", which is a different pair of airports
    # entirely and also propagated into the "Alternate route for ..."
    # banner on page 2/3.
    main_dest = first(main.get("destination"), "")
    page1["flightInfo"]["alternate1"] = ",".join(
        [x for x in [main_dest, alt1_dest] if x]
    )

    # ======================================================
    # HEADER
    # ======================================================

    page1["header"]["registration"] = first(
        summary.get("registration"),
        user_input.get("callSign")
    )

    if main.get("departure") and main.get("destination"):
        page1["header"]["routeTitle"] = (
            f"{main.get('departure')} - {main.get('destination')}"
        )
    else:
        page1["header"]["routeTitle"] = first("", main.get("route"))

    # ======================================================
    # TIME / NAV SPECS
    # ======================================================

    page1["time"]["etd"] = first(summary.get("etd"))
    page1["time"]["eta"] = first(summary.get("eta"))

    page1["time"]["etdLocal"] = utc_to_ist(page1["time"]["etd"])
    page1["time"]["etaLocal"] = utc_to_ist(page1["time"]["eta"])

    page1["time"]["plannedRouteDistance"] = (
        str(summary.get("distance")) if summary.get("distance") else ""
    )

    # FIX #2: AVERAGE WINDS (Includes summary.get("averageWind"))
    page1["time"]["averageWinds"] = first(
        user_input.get("averageWinds"),
        summary.get("averageWinds"),
        summary.get("averageWind"),
        summary.get("wind")
    )

    # FIX: "AVG.WC" is not present anywhere in the main route's own HTML -
    # ForeFlight only ever gives ONE "Avg Wind" figure per route, and the
    # main route's copy of that already fills AVERAGE WINDS above. What
    # this second field actually shows is the wind used for the ALT1
    # diversion-fuel calc, i.e. Alternate 1's own "Avg Wind" summary figure.
    page1["time"]["averageWindComponent"] = first(
        user_input.get("averageWindComponent"),
        summary.get("averageWindComponent"),
        alt1_summary.get("averageWinds"),
        alt1_summary.get("averageWind")
    )

    # FIX: ForeFlight's export has no single "planned TAS" figure - each
    # waypoint leg has its own TAS that varies with ISA deviation. Best
    # available proxy for the planned cruise TAS is the highest TAS value
    # reached across the main route's legs (climb/descent legs fly slower,
    # so the max is the cruise figure). Best-effort only.
    waypoints = array(main.get("waypoints"))
    max_tas = 0
    for wpt in waypoints:
        try:
            tas_num = float(str(wpt.get("tas", "")).strip())
        except (TypeError, ValueError):
            continue
        if tas_num > max_tas:
            max_tas = tas_num

    page1["time"]["tas"] = first(
        user_input.get("tas"),
        summary.get("tas"),
        str(int(max_tas)) if max_tas else ""
    )

    # FIX #1: TRACK SELECTION (Filters out empty and "-" placeholders)
    track = ""
    for wpt in waypoints:
        course = str(wpt.get("course", "")).strip()
        if course and course != "-":
            track = course
            break

    # VTCSP's TRACK is the bearing quoted inside its own WIND figure - its
    # reference prints "TRACK : 078 DEG" against "12KT HEAD (078°/035)",
    # and the operator's older VIDP-VECC document pairs "045 DEG" with
    # "3kt head (045°/017)" the same way. Note that this is the wind's
    # direction, not the aircraft's track (the first enroute course on that
    # flight is 124), but it is what this template has always printed, so
    # it is reproduced here rather than silently corrected. Swap the order
    # of the last two entries below to print the real course instead.
    wind_bearing = ""
    wind_bearing_match = re.search(
        r"\((\d{2,3})\s*°", str(page1["time"]["averageWinds"] or "")
    )
    if wind_bearing_match:
        wind_bearing = wind_bearing_match.group(1).zfill(3)

    page1["time"]["track"] = first(
        user_input.get("track"),
        summary.get("track"),
        wind_bearing if template in PLAN_TIME_TEMPLATES else "",
        track
    )

    # The winds-aloft column headers are the only place ForeFlight states a
    # level together with its temperature, already formatted exactly as
    # "FL nnn (ISA: -nn°C)". The middle band is used by STEP CLIMB below,
    # and by VTCSP's TOP CLIMB TEMP.
    main_wind_bands = array(object_(main.get("enrouteWinds")).get("bands"))
    mid_band = main_wind_bands[len(main_wind_bands) // 2] if main_wind_bands else ""

    # TOP CLIMB TEMP
    toc_temp = ""
    for wpt in waypoints:
        if "TOC" in str(wpt.get("waypoint", "")).upper():
            toc_fl = wpt.get("flightLevel", "")
            toc_isa = wpt.get("isa", "")
            if toc_fl or toc_isa:
                toc_temp = f"{toc_fl} (ISA: {toc_isa})" if toc_isa else toc_fl
            break

    # VTCSP quotes the middle winds-aloft band here, not the TOC waypoint's
    # own level: its reference prints "FL 390 (ISA: -56°C)" on a flight
    # whose TOC is FL410 at ISA +7, and FL 390 is the middle of that
    # export's FL350/370/390/410/450 bands - temperature included, in the
    # band header's own °C formatting. (The operator's older VIDP-VECC
    # document shows the same pairing.)
    page1["time"]["topClimbTemp"] = first(
        user_input.get("topClimbTemp"),
        mid_band if template in PLAN_TIME_TEMPLATES else "",
        toc_temp
    )

    # FIX: STEP CLIMB is meant to show the recommended intermediate cruise
    # level (this aircraft climbs to a lower level first, then steps up to
    # the ceiling FL as it burns off weight), not the TOC waypoint's own
    # level. The only place a recommended intermediate level shows up in
    # ForeFlight's export is as the MIDDLE column of the winds-aloft table
    # (bands are normally centered on cruise; when cruise sits at the
    # aircraft's ceiling - as it does here - the bands run from several
    # steps below up to the ceiling, and the middle one is the suggested
    # step-climb level). That column header is already formatted exactly
    # as "FL nnn (ISA: nn°C)", so it can be used as-is (computed above).
    page1["time"]["stepClimb"] = first(
        user_input.get("stepClimb"),
        mid_band,
        page1["time"]["topClimbTemp"]
    )

    # ======================================================
    # FUEL
    # ======================================================

    # Registration used to key the per-tail fuel-limit fallback table
    # (AIRCRAFT_FUEL_LIMITS) below. Never used to override an explicit
    # user_input value - only fills in when the form provides nothing.
    _reg_for_limits = str(first(
        summary.get("registration"),
        user_input.get("callSign"),
        ""
    )).upper().strip()
    _fuel_limits = AIRCRAFT_FUEL_LIMITS.get(_reg_for_limits, {})

    page1["fuel"]["taxi"] = fw.get("taxiFuel")

    # ------------------------------------------------------
    # OPERATOR "FUEL" / "FUEL 1" TOP-UPS
    # ------------------------------------------------------
    # Two optional operator-entered figures, each with its own time:
    #   FUEL        -> added to TRIP fuel;   FUEL TIME   -> added to TAXI time
    #   FUEL 1      -> added to ALT1 fuel;   FUEL 1 TIME -> added to ALT1 time
    # EXTRA is NOT adjusted here: REQUIRED already sums trip + alternate,
    # and EXTRA is block fuel minus REQUIRED, so both top-ups come back
    # out of EXTRA automatically (same for the time column).
    _user_fuel = user_input.get("fuel")
    _user_fuel1 = user_input.get("fuel1")
    _user_fuel_time = hhmm_to_minutes(user_input.get("fuelTime"))
    _user_fuel1_time = hhmm_to_minutes(user_input.get("fuel1Time"))

    # Kept separately from the displayed TRIP figure: the taxi-time
    # estimate below divides by the flight's real burn rate, and padding
    # trip fuel with an operator top-up must not distort that rate.
    _base_trip_fuel = subtract_if_complete(
        fw.get("flightFuel"),
        fw.get("taxiFuel")
    )

    # VTBBD prices TRIP as "A TO B + APCH & LDG AT B", and its "A TO B"
    # is the navlog's own cumulative USED at the last waypoint less taxi
    # - NOT ForeFlight's flightFuel, which carries a pad of its own and
    # comes out 20 lbs high against the operator's reference sheet.
    if template == "VTBBD":
        _enroute_used = last_numeric(main.get("waypoints"), "fuelUsed")
        if _enroute_used is not None:
            _enroute_trip = subtract_if_complete(
                str(round(_enroute_used)),
                fw.get("taxiFuel")
            )
            if _enroute_trip != "":
                _base_trip_fuel = sum_if_complete(
                    _enroute_trip,
                    APPROACH_LANDING_FUEL
                )

    page1["fuel"]["trip"] = sum_if_complete(_base_trip_fuel, _user_fuel)

    page1["fuel"]["tripTime"] = summary.get("ete")

    if template == "VTBBD":
        _enroute_minutes = hhmm_to_minutes(page1["fuel"]["tripTime"])
        if _enroute_minutes is not None:
            page1["fuel"]["tripTime"] = minutes_to_hhmm(
                _enroute_minutes + APPROACH_LANDING_MINUTES
            )

    page1["fuel"]["tripDistance"] = (
        str(summary.get("distance")) if summary.get("distance") else ""
    )

    # FIX: CONTINGENCY has no field of its own anywhere in ForeFlight's
    # export, so this used to be permanently blank unless the operator
    # typed a value in by hand. Per the operator's own instructions, each
    # template handles it differently:
    #   - DEFAULT: HIGHER of (a) 5% of trip fuel, or (b) fuel to fly 30
    #     minutes at 1,500ft over the destination.
    #   - VTBBD: HIGHER of (a) 5% of trip fuel, or (b) fuel to fly 5
    #     minutes at 1,500ft - per VTBBD's own printed footnote ("5% OF
    #     TRIP FUEL OR 5 MIN FLYING AT 1500FT (WHICHEVER IS MORE)").
    #   - MLOVE: a fixed constant (250 lbs / 0:13), not computed.
    # A manually-entered user_input figure always overrides any of these.
    _computed_contingency_fuel = None
    _computed_contingency_time = None
    _trip_time_minutes_for_contingency = hhmm_to_minutes(page1["fuel"]["tripTime"])
    _five_pct_fuel = None
    _five_pct_time = None
    try:
        _five_pct_fuel = float(page1["fuel"]["trip"]) * 0.05
    except (TypeError, ValueError):
        pass
    if _trip_time_minutes_for_contingency is not None:
        _five_pct_time = _trip_time_minutes_for_contingency * 0.05

    if template == "DEFAULT":
        # (b) needs a holding-altitude fuel flow rate, which ForeFlight
        # also never states directly - the closest available figure is
        # the flight's own published enroute "Fuel Flow" (e.g. "372
        # lbs/hr (Per Engine)"), used here as a best-effort stand-in.
        _holding_rate = parse_fuel_flow_per_hour(summary.get("fuelFlow"))
        _holding_fuel = _holding_rate * 0.5 if _holding_rate else None  # 30 min
        _holding_time = 30 if _holding_rate else None

        if _five_pct_fuel is not None and _holding_fuel is not None:
            if _five_pct_fuel >= _holding_fuel:
                _computed_contingency_fuel, _computed_contingency_time = _five_pct_fuel, _five_pct_time
            else:
                _computed_contingency_fuel, _computed_contingency_time = _holding_fuel, _holding_time
        elif _five_pct_fuel is not None:
            _computed_contingency_fuel, _computed_contingency_time = _five_pct_fuel, _five_pct_time
        elif _holding_fuel is not None:
            _computed_contingency_fuel, _computed_contingency_time = _holding_fuel, _holding_time
    elif template == "VTBBD":
        # (b) here reuses the flight's OWN trip fuel/trip time ratio as
        # the burn rate (rather than a separately published fuel-flow
        # figure) - verified against VTBBD's own reference document,
        # where this reproduces its printed CONTINGENCY figures exactly.
        _trip_rate_per_min = None
        if _trip_time_minutes_for_contingency:
            try:
                _trip_rate_per_min = float(page1["fuel"]["trip"]) / _trip_time_minutes_for_contingency
            except (TypeError, ValueError, ZeroDivisionError):
                _trip_rate_per_min = None

        _five_min_fuel = _trip_rate_per_min * 5 if _trip_rate_per_min else None

        if _five_pct_fuel is not None and _five_min_fuel is not None:
            if _five_pct_fuel >= _five_min_fuel:
                _computed_contingency_fuel = _five_pct_fuel
            else:
                _computed_contingency_fuel = _five_min_fuel
            _computed_contingency_time = _computed_contingency_fuel / _trip_rate_per_min
        elif _five_pct_fuel is not None:
            _computed_contingency_fuel, _computed_contingency_time = _five_pct_fuel, _five_pct_time
        elif _five_min_fuel is not None:
            _computed_contingency_fuel, _computed_contingency_time = _five_min_fuel, 5
    elif template in ("VTVIK",) + PLAN_TIME_TEMPLATES:
        # VTVIK's and VTCSP's own references both label this row
        # "CONTINGENCY 5%" and print exactly 5% of trip fuel (VTVIK: 108
        # lbs on a 2160 lb trip; VTCSP: 117 lbs on a 2341 lb trip) - no
        # "whichever is higher" comparison, unlike DEFAULT/VTBBD.
        if _five_pct_fuel is not None:
            _computed_contingency_fuel, _computed_contingency_time = _five_pct_fuel, _five_pct_time

        # On these templates the contingency TIME does not track the 5%
        # fuel figure - it is 10% of trip time, floored at five minutes.
        # All three of the operator's reference documents agree:
        #   VTCSP        117 lbs / 0:09 on a 1:32 trip  -> a tenth of 92
        #   VIDP-VECC     81 lbs / 0:13 on a 2:10 trip  -> a tenth of 130
        #   INDO PACIFIC  24 lbs / 0:05 on a 0:18 trip  -> the 5 min floor
        # The XTRA and ENDURANCE rows on each document only add up with it.
        if template in PLAN_TIME_TEMPLATES and _trip_time_minutes_for_contingency is not None:
            _computed_contingency_time = max(
                _trip_time_minutes_for_contingency * 0.10,
                CONTINGENCY_MINIMUM_MINUTES,
            )
    else:
        _computed_contingency_fuel, _computed_contingency_time = 250, 13

    page1["fuel"]["contingency"] = first(
        user_input.get("contingencyFuel"),
        fw.get("contingencyFuel"),
        str(round(_computed_contingency_fuel)) if _computed_contingency_fuel is not None else ""
    )

    page1["fuel"]["contingencyTime"] = first(
        user_input.get("contingencyTime"),
        fw.get("contingencyTime"),
        minutes_to_hhmm(_computed_contingency_time) if _computed_contingency_time is not None else ""
    )

    _alt1_fuel_fixed = subtract_if_complete(
        alt1_fw.get("flightFuel"),
        alt1_fw.get("taxiFuel")
    )

    page1["fuel"]["alternate"] = sum_if_complete(
        first(
            _alt1_fuel_fixed,
            fw.get("alternateFuel")
        ),
        _user_fuel1
    )

    # FIX: pdfGenerator's ALT1 row also has a 4th (distance) column, which
    # was never populated - Alternate 1's own "Distance" summary figure
    # (already parsed by htmlParser, e.g. "223NM") was simply never wired
    # through to this key.
    page1["fuel"]["alternateDistance"] = (
        str(alt1_summary.get("distance")) if alt1_summary.get("distance") else ""
    )

    # FIX: ALT2's diversion-fuel figure was never computed anywhere in this
    # file (only ALT1's was, above), so default.py's ALTN2 fuel column had
    # nothing to find no matter what key names it tried. This mirrors the
    # exact same ALT1 calculation, using alt2's own fuel/taxi figures, and
    # stores it under "alternate2Fuel" - a key default.py already checks.
    _alt2_fuel_fixed = subtract_if_complete(
        alt2_fw.get("flightFuel"),
        alt2_fw.get("taxiFuel")
    )

    page1["fuel"]["alternate2Fuel"] = first(
        _alt2_fuel_fixed,
        alt2_fw.get("alternateFuel")
    )

    # FIX: pdfGenerator's ALT1 row reads "alternateTime"/"alternate_time",
    # but this only ever set "alternate1Time" - a key nothing renders -
    # so the ALT1 row's time column was always blank. Keep both key
    # spellings so a future ALT2-aware template (default.py's dual-
    # alternate layout) still has "alternate2Time" available too.
    # ALT1's own ETE, plus the operator's optional "FUEL 1 TIME" top-up.
    _alt1_ete_minutes = hhmm_to_minutes(alt1_summary.get("ete"))
    if _alt1_ete_minutes is not None and _user_fuel1_time is not None:
        _alt1_display_time = minutes_to_hhmm(_alt1_ete_minutes + _user_fuel1_time)
    else:
        _alt1_display_time = alt1_summary.get("ete", "")

    page1["fuel"]["alternateTime"] = _alt1_display_time
    page1["fuel"]["alternate1Time"] = _alt1_display_time
    page1["fuel"]["alternate2Time"] = alt2_summary.get("ete", "")

    page1["fuel"]["finalReserve"] = fw.get("reserveFuel")

    page1["fuel"]["finalReserveTime"] = first(
        user_input.get("finalReserveTime"),
        fw.get("reserveTime"),
        "0:30"
    )

    # FIX: MIN DIVERT FUEL was never computed anywhere in this pipeline -
    # default.py has always looked for keys like "minDivertFuel" but
    # nothing upstream ever set them, so the field was permanently blank
    # regardless of source data. Min divert fuel = fuel required to reach
    # the first alternate + final reserve fuel (standard definition).
    page1["fuel"]["minDivertFuel"] = sum_if_complete(
        page1["fuel"]["alternate"],
        fw.get("reserveFuel")
    )

    # ...and its endurance is the matching sum: time to fly the diversion
    # plus the 30-minute final reserve. The diversion leg is taken from
    # the alternate NAVLOG's own cumulative ETE rather than the ALT1 fuel
    # row, because ALT1's figure can carry the missed-approach and climb
    # allowances the footnote describes, which are already burnt before
    # the diversion starts. Falls back to the ALT1 row when the navlog
    # doesn't carry a usable time.
    _min_divert_leg_minutes = hhmm_to_minutes(first(
        last_value(alt1.get("waypoints"), "ete"),
        page1["fuel"]["alternateTime"]
    ))
    _fres_minutes = hhmm_to_minutes(page1["fuel"]["finalReserveTime"])
    page1["fuel"]["minDivertEndurance"] = (
        minutes_to_hhmm(_min_divert_leg_minutes + _fres_minutes)
        if _min_divert_leg_minutes is not None and _fres_minutes is not None
        else ""
    )

    page1["fuel"]["required"] = sum_if_complete(
        fw.get("taxiFuel"),
        page1["fuel"]["trip"],
        page1["fuel"]["contingency"],
        page1["fuel"]["alternate"],
        fw.get("reserveFuel")
    )

    # FIX: REQ/EXTRA/T-O FUEL/RAMP's TIME columns (next to their fuel
    # figures) were never computed at all - only REQ's fuel amount was.
    # These mirror the fuel-side formulas exactly, one clock-time term at
    # a time:
    #   REQ time  = TAXI time + TRIP time + CONTINGENCY time + ALT1 time
    #               + FRES time            (same terms as REQ fuel)
    #   RAMP time = ENDURANCE               (the operator's own total
    #               usable-endurance figure - not derivable from the
    #               ForeFlight export, must come from user_input)
    #   T/O FUEL time = RAMP time - TAXI time   (same relationship as
    #               T/O FUEL = RAMP fuel - TAXI fuel)
    #   EXTRA time = RAMP time - REQ time       (same relationship as
    #               EXTRA fuel = RAMP fuel - REQUIRED fuel)
    # TAXI time itself has no field of its own anywhere in this template
    # (its column is left blank, same as ForeFlight's own export never
    # states a taxi time) - it only exists here as an intermediate value,
    # derived from taxi fuel against the flight's own actual enroute burn
    # rate (trip fuel / trip time), since that is the only burn rate this
    # pipeline can compute without parsing the free-text "NNN lbs/hr (Per
    # Engine)" Fuel Flow field.
    _trip_time_minutes = hhmm_to_minutes(page1["fuel"]["tripTime"])
    _taxi_time_minutes = None
    if _trip_time_minutes and _base_trip_fuel:
        try:
            _trip_fuel_num = float(_base_trip_fuel)
            _taxi_fuel_num = float(fw.get("taxiFuel") or "")
            if _trip_fuel_num > 0:
                _taxi_time_minutes = _taxi_fuel_num * _trip_time_minutes / _trip_fuel_num
        except (TypeError, ValueError):
            _taxi_time_minutes = None

    # These templates print a flat 10 minutes in the TAXI row rather than
    # a figure derived from taxi fuel - the references show 0:10 against
    # and its ENDURANCE line only balances (TRIP + TAXI + CONTINGENCY +
    # FRES + XTRA + ALTN1 = the operator's total) when taxi is that flat
    # 10. The operator's "FUEL TIME" still tops it up below.
    if template in PLAN_TIME_TEMPLATES:
        _taxi_time_minutes = FLAT_TAXI_MINUTES

    # Operator's "FUEL TIME" tops up the taxi time, which then flows into
    # REQ time (and so out of EXTRA time) exactly like the fuel side.
    if _user_fuel_time is not None:
        _taxi_time_minutes = (_taxi_time_minutes or 0) + _user_fuel_time

    page1["fuel"]["taxiTime"] = minutes_to_hhmm(_taxi_time_minutes)

    _contingency_time_minutes = hhmm_to_minutes(page1["fuel"]["contingencyTime"])
    _alt1_time_minutes = hhmm_to_minutes(page1["fuel"]["alternateTime"])
    _fres_time_minutes = hhmm_to_minutes(page1["fuel"]["finalReserveTime"])

    _req_time_minutes = None
    if None not in (
        _taxi_time_minutes,
        _trip_time_minutes,
        _contingency_time_minutes,
        _alt1_time_minutes,
        _fres_time_minutes,
    ):
        _req_time_minutes = (
            _taxi_time_minutes
            + _trip_time_minutes
            + _contingency_time_minutes
            + _alt1_time_minutes
            + _fres_time_minutes
        )

    page1["fuel"]["requiredEndurance"] = minutes_to_hhmm(_req_time_minutes)

    page1["fuel"]["computedFuel"] = first(
        user_input.get("computedFuel"),
        fw.get("computedFuel"),
        page1["fuel"]["required"]
    )

    # FIX: MIN/MAX TRIP FUEL are aircraft-config constants that ForeFlight's
    # export never contains (fw has no such keys) - they can only come from
    # the frontend form. Previously this only checked the exact key names
    # "minTripFuel"/"maxTripFuel" in user_input, so any other spelling sent
    # by the form (e.g. "min_trip_fuel", "minimumTripFuel") silently failed
    # and these fields rendered blank. Widened the alias list, and added a
    # last-resort per-tail fallback (AIRCRAFT_FUEL_LIMITS above) for known
    # aircraft so the fields aren't permanently blank if the form omits them.
    page1["fuel"]["minTripFuel"] = first(
        user_input.get("minTripFuel"),
        user_input.get("min_trip_fuel"),
        user_input.get("minimumTripFuel"),
        user_input.get("minTrip"),
        fw.get("minTripFuel"),
        _fuel_limits.get("minTrip"),
        # VTCSP's reference prints REQUIRED fuel (taxi + trip +
        # contingency + alternate + final reserve) in this row - the
        # minimum that legally has to be on board for the trip - rather
        # than an aircraft-config constant. Only used when the form
        # supplies nothing.
        page1["fuel"]["required"] if template in PLAN_TIME_TEMPLATES else "",
        ""
    )

    page1["fuel"]["maxTripFuel"] = first(
        user_input.get("maxTripFuel"),
        user_input.get("max_trip_fuel"),
        user_input.get("maximumTripFuel"),
        user_input.get("maxTrip"),
        fw.get("maxTripFuel"),
        _fuel_limits.get("maxTrip"),
        ""
    )

    page1["fuel"]["extra"] = subtract_if_complete(
        fw.get("blockFuel"),
        page1["fuel"]["required"]
    )

    page1["fuel"]["extraTime"] = first(
        user_input.get("extraTime"),
        fw.get("extraTime"),
        ""
    )

    # FIX: this used to just echo the raw ENDURANCE user_input straight
    # into the EXTRA row's time column (e.g. "0415" verbatim, unformatted,
    # and not actually the extra-time figure at all). ENDURANCE is really
    # the RAMP row's time (total usable endurance on the ramp); EXTRA time
    # is RAMP time minus REQUIRED time - see the comment above required().
    # FIX: ENDURANCE drives the RAMP/T-O FUEL/XTRA time columns, and when
    # the form's Endurance box is left empty they all render blank. The
    # figure is, however, usually already in the pasted ICAO flight plan -
    # operators file it as "ENDURANCE 0310" in the RMK/ field - so fall
    # back to that before giving up.
    _fpl_text = str(first(
        user_input.get("icaoFlightPlan"),
        user_input.get("fullFPL"),
        user_input.get("icaoFPL"),
        user_input.get("shortFPL"),
        ""
    ))
    _fpl_endurance_match = re.search(
        r"\bENDURANCE\s*[:\-]?\s*(\d{1,2}:\d{2}|\d{4})\b", _fpl_text, re.IGNORECASE
    )
    _fpl_endurance = minutes_to_hhmm(
        hhmm_to_minutes(_fpl_endurance_match.group(1))
    ) if _fpl_endurance_match else ""

    page1["fuel"]["enduranceTime"] = first(
        user_input.get("enduranceTime"),
        user_input.get("endurance"),
        summary.get("endurance"),
        _fpl_endurance,
        ""
    )
    _endurance_minutes = hhmm_to_minutes(page1["fuel"]["enduranceTime"])

    _extra_time_minutes = None
    if _endurance_minutes is not None and _req_time_minutes is not None:
        _extra_time_minutes = _endurance_minutes - _req_time_minutes

    page1["fuel"]["extraEndurance"] = minutes_to_hhmm(_extra_time_minutes)

    page1["fuel"]["takeoff"] = subtract_if_complete(
        fw.get("blockFuel"),
        fw.get("taxiFuel")
    )

    _takeoff_time_minutes = None
    if _endurance_minutes is not None and _taxi_time_minutes is not None:
        _takeoff_time_minutes = _endurance_minutes - _taxi_time_minutes

    page1["fuel"]["takeoffEndurance"] = minutes_to_hhmm(_takeoff_time_minutes)

    page1["fuel"]["ramp"] = fw.get("blockFuel")
    page1["fuel"]["rampEndurance"] = minutes_to_hhmm(_endurance_minutes)

    # ForeFlight's own "Flight Fuel" (taxi + trip, block to block). VTCSP
    # prints this as its BLOCK FUEL figure, distinct from the ramp fuel
    # it calls COMPUTED FUEL.
    page1["fuel"]["flight"] = fw.get("flightFuel")

    page1["fuel"]["landing"] = subtract_if_complete(
        page1["fuel"]["takeoff"],
        page1["fuel"]["trip"]
    )

    # ForeFlight publishes a landing-fuel figure of its own in the
    # performance-summary strip. It can differ by a pound or two from the
    # takeoff-minus-trip subtraction above (rounding), so keep it
    # separately for templates that quote ForeFlight's number verbatim.
    page1["fuel"]["landingReported"] = fw.get("landingFuel")
    if not page1["fuel"]["landing"]:
        page1["fuel"]["landing"] = first(
            fw.get("landingFuel"),
            fw.get("elwFuel")
        )

    # ======================================================
    # WEIGHT
    # ======================================================

    page1["weight"]["basicOperatingWeight"] = subtract_if_complete(
        fw.get("zfw"),
        fw.get("payload")
    )

    # FIX #4: PAX Fallback added
    _pax_value = first(
        user_input.get("paxWeight"),
        summary.get("soulsOnBoard"),
        summary.get("pax")
    )

    # VTBBD-only: cabin crew count/weight row, between PAX and LOAD.
    _cc_value = first(
        user_input.get("ccWeight"),
        user_input.get("cabinCrewCount")
    )

    # VTBBD prints these two rows as "<count> - <total weight>" using the
    # standard per-head allowances. MLOVE/VTVIK print a plain head count,
    # so the expansion is scoped to VTBBD only.
    if template == "VTBBD":
        _pax_value = expand_head_count(_pax_value, PAX_UNIT_WEIGHT)
        _cc_value = expand_head_count(_cc_value, CC_UNIT_WEIGHT)

    page1["weight"]["pax"] = _pax_value
    page1["weight"]["cc"] = _cc_value

    page1["weight"]["load"] = fw.get("payload")

    page1["weight"]["zeroFuelWeight"] = fw.get("zfw")

    page1["weight"]["takeoffFuel"] = page1["fuel"]["takeoff"]

    page1["weight"]["takeoffWeight"] = fw.get("tow")

    page1["weight"]["estimatedLandingWeight"] = fw.get("elw")

    # ======================================================
    # MISC
    # ======================================================

    page1["misc"]["plannedProfile"] = summary.get("profile")

    # FIX: IFR/VFR was only ever taken from user_input, which the frontend
    # form has no field for - so PLN PROFILE always rendered without the
    # rules prefix. ForeFlight's own title line ends with "... IFR"/"VFR",
    # which htmlParser.py now extracts into summary["flightRules"].
    flight_rules = first(
        user_input.get("flightRules"),
        user_input.get("rules"),
        summary.get("flightRules")
    )

    if flight_rules:
        page1["misc"]["plannedProfile"] = (
            f"{flight_rules} {page1['misc']['plannedProfile']}".strip()
        )

    # FIX: this used to fall back to user_input["shortFPL"] first, but that
    # is the SAME field the full ICAO flight-plan text below reads from
    # ("ATC Short Flight Plan" -> icaoFlightPlan/fullFPL/icaoFPL/shortFPL
    # chain). Whenever an operator pasted the full multi-line ICAO FPL
    # text into that one box, it clobbered this short ATC ROUTE line with
    # the entire FPL block. The parsed route string is always the correct
    # short route on its own - no user override needed here.
    page1["misc"]["atcRoute"] = first(main.get("route"))

    # ======================================================
    # OPERATIONAL (ATIS, CLEARANCE, AND AIRPORT INFO)
    # ======================================================
    # FIX: these three fields were being auto-filled from the airport-
    # frequencies table (which is reference data - published frequencies,
    # always shown on page 3's AIRPORT INFO table). DEPARTURE ATIS/DEP
    # CLEARANCE/ARRIVAL ATIS on page 1 are a different thing: blank fields
    # for the crew to log the ATIS letter/clearance actually RECEIVED on
    # the day, filled in by hand. They must stay blank unless the operator
    # explicitly typed something into user_input.

    page1["operational"]["departureAtis"] = first(
        user_input.get("departureAtis")
    )

    page1["operational"]["arrivalAtis"] = first(
        user_input.get("arrivalAtis")
    )

    page1["operational"]["departureClearance"] = first(
        user_input.get("departureClearance")
    )

    # VTVIK-only fields - same "blank unless the operator typed it"
    # policy as the three above.
    page1["operational"]["arrivalClearance"] = first(
        user_input.get("arrivalClearance")
    )
    page1["operational"]["depTaxiClearance"] = first(
        user_input.get("depTaxiClearance")
    )
    page1["operational"]["arrTaxiClearance"] = first(
        user_input.get("arrTaxiClearance")
    )
    page1["operational"]["destAltnAtis"] = first(
        user_input.get("destAltnAtis")
    )

    # ======================================================
    # ALTERNATES
    # ======================================================

    def build_alternate(name, alt):
        if not alt or not alt.get("destination"):
            return None

        alt_summary = object_(alt.get("summary"))
        alt_fw_local = object_(alt.get("fuelWeights"))

        return {
            "name": name,
            "airport": alt.get("destination"),
            "route": alt.get("route", ""),
            "flightLevel": alt_summary.get("altitude", ""),
            "distance": (
                str(alt_summary.get("distance"))
                if alt_summary.get("distance")
                else ""
            ),
            # FIX: this used the colon-format ete ("0:50", already
            # converted by htmlParser for use elsewhere in the template) -
            # but the expected PDF's ALT1/ALT2 summary block at the bottom
            # of page 1 uses ForeFlight's own "0h50m"-style duration,
            # uppercased ("0H50M"). Re-derive that format here rather than
            # reusing the colon-converted value.
            "ete": minutes_to_hm_upper(hhmm_to_minutes(alt_summary.get("ete", ""))),
            "fuel": alt_fw_local.get("flightFuel", "")
        }

    data["page1"]["alternates"] = list(
        filter(
            None,
            [
                build_alternate("ALT1", alt1),
                build_alternate("ALT2", alt2)
            ]
        )
    )

    # ======================================================
    # ROUTES
    # ======================================================

    data["routes"]["mainRoute"] = main.get("route", "")
    data["routes"]["alternate1Route"] = alt1.get("route", "")
    data["routes"]["alternate2Route"] = alt2.get("route", "")

    # ======================================================
    # ATC FLIGHT PLAN
    # ======================================================

    data["atcFlightPlan"] = {
        "title": (
            f"ATC FLIGHT PLAN "
            f"{first(main.get('departure'))} "
            f"to "
            f"{first(main.get('destination'))}"
        ),
        "flightPlanText": first(
            user_input.get("icaoFlightPlan"),
            user_input.get("fullFPL"),
            user_input.get("icaoFPL"),
            user_input.get("shortFPL"),
            ""
        ),
        "flightRules": flight_rules,
        "flightType": "",
        "aircraftNumber": first(summary.get("registration")),
        "aircraftType": first(summary.get("aircraftType")),
        "wakeTurbulence": "",
        "equipment": "",
        "surveillance": "",
        "departure": first(main.get("departure")),
        "departureTime": first(summary.get("etd")),
        "speed": "",
        "level": first(
            user_input.get("flightLevel"),
            summary.get("altitude")
        ),
        "route": first(main.get("route")),
        "destination": first(main.get("destination")),
        "totalEET": first(summary.get("ete")),
        "alternate1": alt1_dest,
        "alternate2": alt2_dest,
        "otherInformation": ""
    }

    # ======================================================
    # NAVLOGS
    # ======================================================

    data["mainNavlog"] = [
        map_waypoint_row(row)
        for row in array(main.get("waypoints"))
    ]

    data["alternate1Navlog"] = [
        map_waypoint_row(row)
        for row in array(alt1.get("waypoints"))
    ]

    data["alternate2Navlog"] = [
        map_waypoint_row(row)
        for row in array(alt2.get("waypoints"))
    ]

    # ======================================================
    # LEVEL CALCULATIONS & V-SPEEDS
    # ======================================================
    # FIX: htmlParser.py already extracts these (parse_level_calculations),
    # but convert_with_claude() previously dropped them on the floor instead
    # of copying them into the output. That's why the DIFFERENT LEVEL
    # CALCULATION table and V-speed line were always empty regardless of
    # what was in the source HTML.

    data["levelCalculations"] = [
        map_level_calculation_row(row)
        for row in array(main.get("levelCalculations"))
    ]

    data["vSpeeds"] = object_(main.get("vSpeeds"))

    # ======================================================
    # AIRPORT INFORMATION
    # ======================================================
    # FIX: this used to pull DEP/DEST rows from the main route AND both
    # alternates, producing 4-5 rows (VIDP/VECC plus the alternates' own
    # departure/destination). The page 3 AIRPORT INFO table is only meant
    # to cover the main route's own departure and destination (2 rows) -
    # the alternates' airport details aren't part of it.

    seen_airports = set()
    airport_rows = []

    for row in array(main.get("airportInfo")):
        key = f"{row.get('type')}-{row.get('airport')}"

        if key in seen_airports:
            continue

        seen_airports.add(key)
        airport_rows.append(map_airport_row(row))

    data["airportInformation"] = airport_rows

    # ======================================================
    # ENROUTE WINDS
    # ======================================================

    main_winds = object_(main.get("enrouteWinds"))
    alt1_winds = object_(alt1.get("enrouteWinds"))
    alt2_winds = object_(alt2.get("enrouteWinds"))

    data["enrouteWindBands"] = array(main_winds.get("bands"))

    data["enrouteWinds"] = (
        array(main_winds.get("rows"))
        + array(alt1_winds.get("rows"))
        + array(alt2_winds.get("rows"))
    )

    print("✅ Transform complete")
    print(f"   Main navlog: {len(data['mainNavlog'])} waypoints")
    print(f"   Alt1 navlog: {len(data['alternate1Navlog'])} waypoints")
    print(f"   Alt2 navlog: {len(data['alternate2Navlog'])} waypoints") 
    print(f"   Airports: {len(data['airportInformation'])}")
    print(f"   Level calc rows: {len(data['levelCalculations'])}")
    print(
        f"   Wind bands: {len(data['enrouteWindBands'])}, "
        f"rows: {len(data['enrouteWinds'])}"
    )

    return data