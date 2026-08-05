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
}


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
        "trip": row.get("trip", "")
    }


# ======================================================
# MAIN CONVERSION FUNCTION
# ======================================================

def convert_with_claude(master_json):
    print("🔧 Building Forum Aviation OPS FPL JSON (deterministic transform)...")

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
        user_input.get("dateOfFlight")
    )

    alt1_dest = first(alt1.get("destination"), "")
    alt2_dest = first(alt2.get("destination"), "")

    page1["flightInfo"]["alternate1"] = ",".join(
        [x for x in [alt1_dest, alt2_dest] if x]
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

    page1["time"]["averageWindComponent"] = first(
        user_input.get("averageWindComponent"),
        summary.get("averageWindComponent")
    )

    page1["time"]["tas"] = first(
        user_input.get("tas"),
        summary.get("tas")
    )

    # FIX #1: TRACK SELECTION (Filters out empty and "-" placeholders)
    waypoints = array(main.get("waypoints"))
    track = ""
    for wpt in waypoints:
        course = str(wpt.get("course", "")).strip()
        if course and course != "-":
            track = course
            break

    page1["time"]["track"] = first(
        user_input.get("track"),
        summary.get("track"),
        track
    )

    # TOP CLIMB TEMP
    toc_temp = ""
    for wpt in waypoints:
        if "TOC" in str(wpt.get("waypoint", "")).upper():
            toc_fl = wpt.get("flightLevel", "")
            toc_isa = wpt.get("isa", "")
            if toc_fl or toc_isa:
                toc_temp = f"{toc_fl} (ISA: {toc_isa})" if toc_isa else toc_fl
            break

    page1["time"]["topClimbTemp"] = first(
        user_input.get("topClimbTemp"),
        toc_temp
    )

    page1["time"]["stepClimb"] = first(
        user_input.get("stepClimb"),
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

    page1["fuel"]["trip"] = subtract_if_complete(
        fw.get("flightFuel"),
        fw.get("taxiFuel")
    )

    page1["fuel"]["tripTime"] = summary.get("ete")

    page1["fuel"]["tripDistance"] = (
        str(summary.get("distance")) if summary.get("distance") else ""
    )

    page1["fuel"]["contingency"] = first(
        user_input.get("contingencyFuel"),
        fw.get("contingencyFuel"),
        ""
    )

    page1["fuel"]["contingencyTime"] = first(
        user_input.get("contingencyTime"),
        fw.get("contingencyTime"),
        ""
    )

    _alt1_fuel_fixed = subtract_if_complete(
        alt1_fw.get("flightFuel"),
        alt1_fw.get("taxiFuel")
    )

    page1["fuel"]["alternate"] = first(
        _alt1_fuel_fixed,
        fw.get("alternateFuel")
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

    page1["fuel"]["alternate1Time"] = alt1_summary.get("ete", "")
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

    page1["fuel"]["required"] = sum_if_complete(
        fw.get("taxiFuel"),
        page1["fuel"]["trip"],
        page1["fuel"]["contingency"],
        page1["fuel"]["alternate"],
        fw.get("reserveFuel")
    )

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

    page1["fuel"]["extraEndurance"] = first(
        user_input.get("endurance")
    )

    page1["fuel"]["enduranceTime"] = first(
        user_input.get("enduranceTime"),
        user_input.get("endurance"),
        summary.get("endurance"),
        ""
    )

    page1["fuel"]["takeoff"] = subtract_if_complete(
        fw.get("blockFuel"),
        fw.get("taxiFuel")
    )

    page1["fuel"]["ramp"] = fw.get("blockFuel")

    page1["fuel"]["landing"] = subtract_if_complete(
        page1["fuel"]["takeoff"],
        page1["fuel"]["trip"]
    )
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
    page1["weight"]["pax"] = first(
        user_input.get("paxWeight"),
        summary.get("soulsOnBoard"),
        summary.get("pax")
    )

    page1["weight"]["load"] = fw.get("payload")

    page1["weight"]["zeroFuelWeight"] = fw.get("zfw")

    page1["weight"]["takeoffFuel"] = page1["fuel"]["takeoff"]

    page1["weight"]["takeoffWeight"] = fw.get("tow")

    page1["weight"]["estimatedLandingWeight"] = fw.get("elw")

    # ======================================================
    # MISC
    # ======================================================

    page1["misc"]["plannedProfile"] = summary.get("profile")

    flight_rules = first(
        user_input.get("flightRules"),
        user_input.get("rules")
    )

    if flight_rules:
        page1["misc"]["plannedProfile"] = (
            f"{flight_rules} {page1['misc']['plannedProfile']}".strip()
        )

    page1["misc"]["atcRoute"] = first(
        user_input.get("shortFPL"),
        main.get("route")
    )

    # ======================================================
    # OPERATIONAL (ATIS, CLEARANCE, AND AIRPORT INFO)
    # ======================================================

    dep_atis = ""
    arr_atis = ""
    dep_clr = ""

    for row in array(main.get("airportInfo")):
        apt_type = str(row.get("type", "")).upper()
        if apt_type == "DEP":
            dep_atis = row.get("atis", "")
            dep_clr = row.get("clearance", "")
        elif apt_type in ("DEST", "ARR"):
            arr_atis = row.get("atis", "")

    page1["operational"]["departureAtis"] = first(
        user_input.get("departureAtis"),
        dep_atis
    )

    page1["operational"]["arrivalAtis"] = first(
        user_input.get("arrivalAtis"),
        arr_atis
    )

    page1["operational"]["departureClearance"] = first(
        user_input.get("departureClearance"),
        dep_clr
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
            "ete": alt_summary.get("ete", ""),
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

    seen_airports = set()
    airport_rows = []

    for leg in [main, alt1, alt2]:
        for row in array(leg.get("airportInfo")):
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