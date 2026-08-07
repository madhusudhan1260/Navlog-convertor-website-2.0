import os
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from claude import APPROACH_LANDING_FUEL, APPROACH_LANDING_MINUTES
from common import (
    OUTPUT_DIRECTORY,
    PAGE,
    box,
    draw_navlog_header,
    draw_navlog_rows,
    draw_navlog_title,
    field,
    find_value,
    labelled_value,
    line,
    route_header,
    section_heading,
    set_page_height,
    value,
    write,
)

# --------------------------------------------------
# PAGE ONE SECTIONS
# --------------------------------------------------
# Coordinates in this file were measured directly off VTBBD's own
# reference PDF (a PDF text-bbox extraction), not inherited from the
# MLOVE template - the two documents share a lot of visual DNA but are
# tuned to slightly different columns throughout, and VTBBD is Letter-
# sized where MLOVE is A4.


def draw_page_one(pdf, data):
    draw_header(pdf, data)
    draw_flight_info(pdf, data)
    draw_time_section(pdf, data)
    draw_fuel_section(pdf, data)
    draw_weight_section(pdf, data)
    draw_misc_section(pdf, data)
    draw_operational_section(pdf, data)
    draw_alternates(pdf, data)


def draw_header(pdf, data):
    header = data.get("page1", {}).get("header", {})
    flight = data.get("page1", {}).get("flightInfo", {})
    summary = data.get("main", {}).get("summary", {}) or data.get("summary", {})

    route_title = header.get("routeTitle") or data.get("routeTitle", "")
    reg_val = header.get("registration") or flight.get("registration") or summary.get("registration", "")

    route_header(pdf, route_title, reg_val)
    box(pdf, PAGE["left"], 26, 496, 734)

    flight_num = flight.get("flight") or summary.get("flight") or reg_val

    pic_val = find_value(
        flight, summary, header, data,
        "pic", "picName", "pic_name", "captain", "commander", "commanderName",
    )
    date_val = find_value(
        flight, summary, header, data,
        "date", "flightDate", "flight_date",
    )
    fo_val = find_value(
        flight, summary, header, data,
        "fo", "f_o", "foName", "fo_name", "firstOfficer", "first_officer", "copilot",
    )
    cc_val = find_value(
        flight, summary, header, data,
        "cc", "ccName", "cabinCrew", "cabinCrewName",
    )

    labelled_value(pdf, "FLIGHT", flight_num, 74, 44, 34, 150)
    labelled_value(pdf, "DATE", date_val, 74, 58, 34, 150)
    labelled_value(pdf, "PIC", pic_val, 202, 46, 22, 175)

    # F/O's value is two lines (name, then a "CC:/ <name>" cabin-crew
    # line below it) with the "F/O" label sitting between them - not a
    # single-line labelled_value() row like everything else in the
    # header.
    write(pdf, "F/O", 202, 64, 22, {"size": 8.5, "lineBreak": False})
    write(pdf, ":", 224, 64, 8, {"size": 8.5, "lineBreak": False})
    write(pdf, fo_val, 231, 59, 175, {"size": 8.5, "lineBreak": False})
    if cc_val:
        write(pdf, f"CC:/ {cc_val}", 231, 69, 175, {"size": 8.5, "lineBreak": False})

    write(
        pdf,
        "COMMANDER SIGN :",
        352,
        69,
        100,
        {"size": 8.5, "lineBreak": False},
    )
    line(pdf, 442, 75, 527, 75)


def draw_flight_info(pdf, data):
    flight = data.get("page1", {}).get("flightInfo", {})
    section_heading(pdf, "FLIGHT INFO", 72, 87, 220)

    flight_rows = [
        ("REG", flight.get("registration")),
        ("FL", flight.get("flightLevel")),
        ("FROM", flight.get("departure")),
        ("TO", flight.get("destination")),
        ("ALT1", flight.get("alternate1")),
    ]
    rows_y = [116, 130, 144, 157, 171]

    for row, y in zip(flight_rows, rows_y):
        labelled_value(pdf, row[0], row[1], 74, y, 81, 210)


def draw_time_section(pdf, data):
    time = data.get("page1", {}).get("time", {}) or data.get("time", {})
    summary = data.get("main", {}).get("summary", {}) or data.get("summary", {})

    section_heading(pdf, "TIME", 312, 87, 220)

    etd_str = find_value(time, summary, "etd")
    etd_loc = find_value(
        time, summary,
        "etdLocal", "etd_local", "localEtd", "etdIst", "etd_ist", "istEtd",
    )
    etd_text = f"ETD : {etd_str} (IST: {etd_loc} )" if etd_loc else f"ETD : {etd_str}"

    eta_str = find_value(time, summary, "eta")
    eta_loc = find_value(
        time, summary,
        "etaLocal", "eta_local", "localEta", "etaIst", "eta_ist", "istEta",
    )
    eta_text = f"ETA : {eta_str} (IST: {eta_loc} )" if eta_loc else f"ETA : {eta_str}"

    write(pdf, etd_text, 310, 105, 120, {"size": 8.5, "lineBreak": False})
    write(pdf, eta_text, 426, 105, 120, {"size": 8.5, "lineBreak": False})

    step_climb = find_value(time, summary, "stepClimb", "step_climb")
    isa_val = find_value(time, summary, "isa", "stepClimbIsa", "step_climb_isa")

    if step_climb and isa_val and "(ISA:" not in step_climb:
        step_climb_text = f"{step_climb} (ISA: {isa_val})"
    else:
        step_climb_text = step_climb

    plnd_route = find_value(
        time, summary,
        "plannedRouteDistance", "plndRoute", "plnd_route", "plannedRoute",
    )
    avg_winds = find_value(
        time, summary,
        "averageWinds", "avgWinds", "avg_winds", "averageWind", "avg_wind",
    ).upper()
    avg_wc = find_value(
        time, summary,
        "averageWindComponent", "avgWc", "avg_wc", "averageWc", "average_wc",
    ).upper()
    tas_val = find_value(time, summary, "tas")

    labelled_value(pdf, "STEP CLIMB", step_climb_text, 312, 124, 57, 220)
    labelled_value(pdf, "PLND ROUTE", plnd_route, 312, 141, 89, 220)
    labelled_value(pdf, "AVG WINDS", avg_winds, 312, 155, 89, 220)
    labelled_value(pdf, "AVG.WC", avg_wc, 312, 168, 89, 220)
    labelled_value(pdf, "TAS", tas_val, 312, 181, 89, 220)


def draw_fuel_section(pdf, data):
    fuel = data.get("page1", {}).get("fuel", {})
    section_heading(pdf, "FUEL", 72, 201, 220)

    fuel_rows = [
        ("TAXI", fuel.get("taxi"), "", ""),
        (
            "TRIP",
            fuel.get("trip"),
            find_value(fuel, "tripTime", "trip_time"),
            find_value(fuel, "tripDistance", "trip_distance"),
        ),
        (
            "CONTINGENCY",
            fuel.get("contingency"),
            find_value(fuel, "contingencyTime", "contingency_time"),
            "",
        ),
        (
            "ALT1",
            fuel.get("alternate"),
            find_value(fuel, "alternateTime", "alternate_time"),
            find_value(fuel, "alternateDistance", "alternate_distance"),
        ),
        (
            "FRES",
            fuel.get("finalReserve"),
            find_value(fuel, "finalReserveTime", "final_reserve_time"),
            "",
        ),
        (
            "REQ",
            fuel.get("required"),
            find_value(fuel, "requiredEndurance", "required_endurance"),
            "",
        ),
        (
            "EXTRA",
            fuel.get("extra"),
            find_value(fuel, "extraEndurance", "extra_endurance"),
            "",
        ),
        (
            "T/O FUEL",
            fuel.get("takeoff"),
            find_value(fuel, "takeoffEndurance", "takeoff_endurance"),
            "",
        ),
        (
            "RAMP",
            fuel.get("ramp"),
            find_value(fuel, "rampEndurance", "ramp_endurance"),
            "",
        ),
        (
            "MIN DIV FUEL",
            fuel.get("minDivertFuel"),
            find_value(fuel, "minDivertEndurance", "min_divert_endurance"),
            "",
        ),
    ]
    rows_y = [219, 232, 245, 259, 272, 285, 298, 312, 325, 336]

    for row, y in zip(fuel_rows, rows_y):
        write(pdf, row[0], 74, y, 92, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 166, y, 8, {"size": 8.5, "lineBreak": False})
        write(pdf, row[1], 140, y, 62, {"size": 8.5, "align": "right", "lineBreak": False})
        write(pdf, row[2], 211, y, 35, {"size": 8.5, "lineBreak": False})
        write(pdf, row[3], 240, y, 55, {"size": 8.5, "lineBreak": False})


def draw_weight_section(pdf, data):
    weight = data.get("page1", {}).get("weight", {})
    section_heading(pdf, "WEIGHT", 312, 201, 220)

    weight_rows = [
        ("BOW", weight.get("basicOperatingWeight")),
        ("PAX", weight.get("pax")),
        ("CC", weight.get("cc")),
        ("LOAD", weight.get("load")),
        ("ZFW", weight.get("zeroFuelWeight")),
        ("T/O FUEL", weight.get("takeoffFuel")),
        ("TOW", weight.get("takeoffWeight")),
        ("ELW", weight.get("estimatedLandingWeight")),
    ]
    rows_y = [222, 236, 247, 259, 272, 285, 298, 311]

    for row, y in zip(weight_rows, rows_y):
        write(pdf, row[0], 312, y, 53, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 365, y, 8, {"size": 8.5, "lineBreak": False})
        write(pdf, row[1], 350, y, 64, {"size": 8.5, "align": "right", "lineBreak": False})
        line(pdf, 452, y + 2, 510, y + 2)


def draw_misc_section(pdf, data):
    misc = data.get("page1", {}).get("misc", {})
    section_heading(pdf, "MISC", 72, 347, 220)

    pln_profile = value(misc.get("plannedProfile")).upper()

    flight_rules = find_value(misc, "flightRules", "flight_rules", "rules").upper()
    if flight_rules and not pln_profile.startswith(flight_rules):
        pln_profile = f"{flight_rules} {pln_profile}".strip()

    # Divider lines sit ~5pt clear of the cap-height of the label below
    # them. Text drawn at baseline Y occupies roughly Y-6 upwards, so a
    # rule any closer than that cuts straight through the lettering.
    labelled_value(pdf, "PLN PROFILE", pln_profile, 74, 360, 90, 470)
    line(pdf, 70, 373, 542, 373, 0.7)

    raw_route = value(misc.get("atcRoute")).upper()
    clean_route = raw_route.replace("ROUTE", "").strip() if raw_route.startswith("ROUTE") else raw_route
    labelled_value(pdf, "ATC ROUTE", clean_route, 72, 384, 56, 470)
    line(pdf, 70, 399, 542, 399, 0.4)


def draw_operational_section(pdf, data):
    operational = data.get("page1", {}).get("operational", {})

    labelled_value(pdf, "DEPARTURE ATIS", operational.get("departureAtis"), 72, 411, 81, 455)

    tofl = operational.get("tofl")
    v_speeds = operational.get("vSpeeds") or operational.get("v1v2v2vt")
    to_wt = operational.get("takeoffWeight") or operational.get("toWeight")
    write(
        pdf,
        f"T/O DATA: TOFL{('_' * 10) if not tofl else value(tofl)}   "
        f"V1/VR/V2/VT {('_' * 13) if not v_speeds else value(v_speeds)}   "
        f"T/O WT {('_' * 16) if not to_wt else value(to_wt)}",
        72,
        442,
        480,
        {"size": 8.5, "lineBreak": False},
    )
    line(pdf, 70, 453, 542, 453, 0.4)

    labelled_value(pdf, "DEP CLEARANCE", operational.get("departureClearance"), 72, 464, 78, 455)
    line(pdf, 70, 501, 542, 501, 0.4)

    labelled_value(pdf, "ARRIVAL ATIS", operational.get("arrivalAtis"), 72, 512, 68, 455)

    vref_vac = operational.get("vrefVac")
    flaps = operational.get("flaps")
    write(
        pdf,
        f"LDG DATA: VREF/VAC {('_' * 12) if not vref_vac else value(vref_vac)}   "
        f"FLAPS{('_' * 18) if not flaps else value(flaps)}",
        72,
        537,
        480,
        {"size": 8.5, "lineBreak": False},
    )
    line(pdf, 70, 547, 542, 547, 0.4)

    operation_columns = [
        [("CHOCKS ON", operational.get("chocksOn")), ("CHOCKS OFF", operational.get("chocksOff")), ("BLOCK TIME", operational.get("blockTime"))],
        [("TAKE OFF", operational.get("takeoff")), ("LANDING", operational.get("landing")), ("AIR TIME", operational.get("airTime"))],
        [("T/O FUEL", operational.get("takeoffFuel")), ("LDG FUEL", operational.get("landingFuel")), ("F USED", operational.get("fuelUsed"))],
        [("LDWGT", operational.get("landingWeight")), ("LDA", operational.get("lda")), ("BFLD", operational.get("bfld"))],
    ]
    columns_x = [72, 198, 311, 425]

    for x, column in zip(columns_x, operation_columns):
        for row_index, row in enumerate(column):
            y = 558 + row_index * 13.3
            write(pdf, row[0], x, y, 62, {"size": 8.5, "lineBreak": False})
            line(pdf, x + 58, y + 2, x + 106, y + 2)
            if row[1]:
                write(pdf, row[1], x + 61, y, 44, {"size": 8.5, "lineBreak": False})

    write(pdf, "RVSM CHECKS", 72, 613, 80, {"size": 8.5, "lineBreak": False})
    write(pdf, "TIME (UTC)", 158, 613, 80, {"size": 8.5, "lineBreak": False})
    write(pdf, "ALT1", 230, 613, 60, {"size": 8.5, "lineBreak": False})
    write(pdf, "ALT2", 296, 613, 60, {"size": 8.5, "lineBreak": False})

    for index, label_text in enumerate(["GROUND", "PRE-RVSM CHECK", "LEVEL OFF"]):
        y = 626 + index * 13.2
        write(pdf, label_text, 72, y, 90, {"size": 8.5, "lineBreak": False})
        line(pdf, 158, y + 2, 212, y + 2)
        line(pdf, 230, y + 2, 284, y + 2)
        line(pdf, 297, y + 2, 351, y + 2)

    # VTBBD-only: boxed ALT ATIS note, to the right of the RVSM block.
    box(pdf, 360, 598, 194, 57)
    write(pdf, "ALT ATIS :", 366, 615, 100, {"size": 8.5, "lineBreak": False})
    alt_atis = operational.get("altAtis")
    if alt_atis:
        write(pdf, alt_atis, 366, 630, 180, {"size": 8})


def draw_alternates(pdf, data):
    alternates = data.get("page1", {}).get("alternates", [])

    for index, alternate in enumerate(alternates[:2]):
        y = 672 + index * 27
        raw_route = value(alternate.get("route")).replace("Route", "").strip()

        alt_label = alternate.get("name", f"ALT{index + 1}")
        write(pdf, alt_label, 72, y, 35, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 117, y, 8, {"size": 8.5, "lineBreak": False})
        write(pdf, field(alternate, "airport"), 130, y, 50, {"size": 8.5, "lineBreak": False})

        write(pdf, "Route", 190, y, 35, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 235, y, 8, {"size": 8.5, "lineBreak": False})
        write(pdf, raw_route, 248, y, 220, {"size": 8.5, "lineBreak": False})

        write(pdf, "FL", 72, y + 14, 20, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 117, y + 14, 8, {"size": 8.5, "lineBreak": False})
        write(pdf, field(alternate, "flightLevel"), 130, y + 14, 50, {"size": 8.5, "lineBreak": False})

        write(pdf, "DIST", 190, y + 14, 30, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 235, y + 14, 8, {"size": 8.5, "lineBreak": False})
        write(pdf, field(alternate, "distance"), 248, y + 14, 55, {"size": 8.5, "lineBreak": False})

        write(pdf, "ETE", 312, y + 14, 25, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 351, y + 14, 8, {"size": 8.5, "lineBreak": False})
        write(pdf, field(alternate, "ete"), 379, y + 14, 55, {"size": 8.5, "lineBreak": False})

        fuel_val = field(alternate, "fuel")
        if fuel_val and not fuel_val.endswith("lbs"):
            fuel_val = f"{fuel_val} lbs"

        write(pdf, "FUEL", 431, y + 14, 30, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 476, y + 14, 8, {"size": 8.5, "lineBreak": False})
        write(pdf, fuel_val, 502, y + 14, 60, {"size": 8.5, "lineBreak": False})


# --------------------------------------------------
# DRAW PAGES TWO AND THREE
# --------------------------------------------------


# Approach & landing allowance. Derived from VTBBD's own reference
# document, where it holds on BOTH legs: the APPROCH AND LAND row prints
# the final waypoint's REMAINING fuel less exactly 220 lbs, over a fixed
# 0:06 - main leg 5549 -> 5329, alternate leg 4150 -> 3930. It's an
# aircraft constant (~2200 lbs/hr at approach power), not something the
# ForeFlight export carries. The same pair is added onto page 1's TRIP
# figure, so it is owned by claude.py and imported here rather than
# being spelled out twice.
APPROACH_LANDING_TIME = f"0:{APPROACH_LANDING_MINUTES:02d}"


def approach_and_land_fuel(rows):
    """Fuel remaining once the approach and landing at the end of a leg
    is flown: the last waypoint's REM figure minus the allowance."""
    for row in reversed(rows or []):
        remaining = value(row.get("fuelRemaining")).replace(",", "").strip()
        try:
            return str(round(float(remaining) - APPROACH_LANDING_FUEL))
        except (TypeError, ValueError):
            continue
    return ""


def draw_summary_row(pdf, label, fuel_val, time_val, y):
    """The bold "APPROCH AND LAND" / "MISSED APPROACH" divider rows that
    VTBBD inserts between the main navlog and each alternate's navlog -
    not present in MLOVE's simpler table. Spans the full table width
    with the running fuel/time totals dropped under the FUEL LB / TIME
    columns, matching where those numbers sit in a normal waypoint row."""
    height = 20
    box(pdf, PAGE["left"], y, 496, height)
    text_y = y + height / 2 + 3
    write(pdf, label, PAGE["left"] + 6, text_y, 300, {"size": 8, "lineBreak": False})
    write(pdf, value(fuel_val), 361, text_y, 39, {"size": 8, "align": "center", "lineBreak": False})
    write(pdf, value(time_val), 400, text_y, 28, {"size": 8, "align": "center", "lineBreak": False})
    return y + height


def draw_pages_two_and_three(pdf, data):
    title = data.get("page1", {}).get("header", {}).get("routeTitle", "")
    registration = data.get("page1", {}).get("header", {}).get("registration", "")
    fuel = data.get("page1", {}).get("fuel", {})

    pdf.showPage()
    route_header(pdf, title, registration)
    box(pdf, PAGE["left"], 32, 496, 728)

    y = draw_navlog_header(pdf, 32)
    main_result = draw_navlog_rows(pdf, data.get("mainNavlog", []), y, 660)
    y = main_result["y"]

    # Fuel state after the arrival at the destination: the main leg's
    # final REM figure less the approach & landing allowance. The MISSED
    # APPROACH row below repeats it - in the reference both rows carry
    # the same figure, since a go-around starts from that same state.
    approach_fuel = approach_and_land_fuel(data.get("mainNavlog", []))
    y = draw_summary_row(pdf, "APPROCH AND LAND", approach_fuel, APPROACH_LANDING_TIME, y)

    alternate_name = data.get("page1", {}).get("flightInfo", {}).get("alternate1", "")
    alternate_route = data.get("routes", {}).get("alternate1Route", "")
    clean_alt_route = value(alternate_route).replace("Route", "").strip()

    title_left = f"Alternate route for {alternate_name}"
    title_right = f"Route {clean_alt_route}" if clean_alt_route else ""

    y = draw_navlog_title(pdf, title_left, title_right, y)
    y = draw_summary_row(pdf, "MISSED APPROACH", approach_fuel, APPROACH_LANDING_TIME, y)

    alternate_result = draw_navlog_rows(pdf, data.get("alternate1Navlog", []), y, 744)

    pdf.showPage()
    route_header(pdf, title, registration)
    box(pdf, PAGE["left"], 32, 496, 728)

    y = draw_navlog_header(pdf, 32)

    remaining_rows = (
        main_result["remaining"]
        + alternate_result["remaining"]
        + data.get("alternate2Navlog", [])
    )

    continuation = draw_navlog_rows(pdf, remaining_rows, y, 250)
    y = continuation["y"]

    # Same again for the diversion leg: alternate 1's final REM figure
    # less the approach & landing allowance.
    alt1_approach_fuel = approach_and_land_fuel(data.get("alternate1Navlog", []))
    y = draw_summary_row(pdf, "APPROCH AND LAND", alt1_approach_fuel, APPROACH_LANDING_TIME, y)

    y += 22
    write(pdf, "AIRPORT INFO", PAGE["left"], y, 150, {"size": 8.5, "bold": False, "lineBreak": False})

    y += 20

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

    x = PAGE["left"]
    for _, heading, width in airport_columns:
        box(pdf, x, y, width, 22)
        write(pdf, heading, x + 2, y + 8, width - 4, {"size": 7.5, "align": "center"})
        x += width

    y += 22

    for airport in data.get("airportInformation", []):
        x = PAGE["left"]
        for key, _, width in airport_columns:
            box(pdf, x, y, width, 22)
            airport_value = airport.get(key)
            if key == "longestRunway":
                r_num = value(airport.get("longestRunway") or airport.get("runway"))
                r_len = value(airport.get("runwayLength"))
                airport_value = f"{r_num} {r_len}".strip()

            write(pdf, airport_value, x + 2, y + 8, width - 4, {"size": 7.5, "align": "center"})
            x += width
        y += 22

    y += 20
    footnote_lines = [
        "*",
        "TRIP FUEL     :  A TO B + APCH & LDG AT B",
        "CONTINGENCY:  5% OF TRIP FUEL OR 5 MIN FLYING AT 1500FT (WHICHEVER IS MORE)",
        "ALT1 FUEL      :  MISSED APCH AT B + CLIMB + B TO C + APCH & LDG AT C",
        "MIN DIV FUEL :  ALT1 + FRES",
        "FINAL RESERVE 30 MINTS HOLD @1500 FT",
    ]
    for line_text in footnote_lines:
        write(pdf, line_text, PAGE["left"], y, 496, {"size": 8.5, "lineBreak": False})
        y += 12


# --------------------------------------------------
# DRAW PAGE FOUR (LAST PAGE) -- FULL WINDS TABLE
# --------------------------------------------------


def draw_page_four(pdf, data):
    title = data.get("page1", {}).get("header", {}).get("routeTitle", "")
    registration = data.get("page1", {}).get("header", {}).get("registration", "")
    atc = data.get("atcFlightPlan", {})

    pdf.showPage()

    route_header(pdf, title, registration)
    box(pdf, PAGE["left"], 26, 496, 734)

    write(
        pdf,
        atc.get("title", f"ATC FLIGHT PLAN {field(atc, 'departure')} to {field(atc, 'destination')}"),
        120,
        48,
        380,
        {"size": 9, "align": "center", "lineBreak": False},
    )

    write(
        pdf,
        ". . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .",
        160,
        60,
        300,
        {"size": 8, "align": "center", "lineBreak": False},
    )

    flight_plan_text = find_value(
        atc,
        "flightPlanText", "flight_plan_text", "fplText", "fpl_text",
        "flightPlan", "flight_plan", "text", "planText", "plan_text",
        "icaoText", "icao_text", "fpl",
    )
    if flight_plan_text:
        write(pdf, flight_plan_text, 68, 76, 476, {"size": 8})

    table_left = 68
    table_width = 476

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

    page_height = letter[1]
    pdf.setFont("Courier-Bold", 8.5)
    end_report_text = "**************     END OF THE REPORT    **************"
    pdf.drawCentredString(PAGE["left"] + 496 / 2, page_height - 728, end_report_text)

    computed_date = datetime.now().strftime("%d-%m-%Y")
    computed_time = datetime.now().strftime("%H:%M:%S")

    write(pdf, f"COMPUTED DATE : {computed_date}", PAGE["left"], 756, 220, {"size": 8.5, "lineBreak": False, "padding": 0})
    write(pdf, f"TIME : {computed_time} Asia/Kolkata", PAGE["right"] - 220, 756, 220, {"size": 8.5, "align": "right", "lineBreak": False, "padding": 0})


# --------------------------------------------------
# GENERATE PDF ENTRYPOINT (VTBBD)
# --------------------------------------------------


def generate_vtbbd_pdf(navlog):
    """Generate the VTBBD-formatted flight-plan PDF and return its
    relative path under OUTPUT_DIRECTORY."""
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)

    file_name = f"VTBBD{int(datetime.now().timestamp() * 1000)}.pdf"
    absolute_path = os.path.join(OUTPUT_DIRECTORY, file_name)
    relative_path = os.path.join("generated", file_name)

    set_page_height(letter[1])
    pdf = canvas.Canvas(absolute_path, pagesize=letter)

    draw_page_one(pdf, navlog)
    draw_pages_two_and_three(pdf, navlog)
    draw_page_four(pdf, navlog)

    pdf.save()

    return relative_path
