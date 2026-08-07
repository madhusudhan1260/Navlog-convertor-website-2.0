import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from common import (
    OUTPUT_DIRECTORY,
    PAGE,
    PAGE_OFFSET,
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

    # PIC / F.O. / DATE: search flight, summary, header and the top-level
    # data dict, under every common spelling. This is what was causing
    # PIC to show the wrong value and DATE/F.O. to show blank.
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

    labelled_value(pdf, "FLIGHT", flight_num, 73, 46 + PAGE_OFFSET, 42, 150)
    labelled_value(pdf, "PIC", pic_val, 202, 46 + PAGE_OFFSET, 28, 175)
    labelled_value(pdf, "DATE", date_val, 73, 61 + PAGE_OFFSET, 42, 150)
    labelled_value(pdf, "F/O", fo_val, 202, 61 + PAGE_OFFSET, 28, 175)

    write(
        pdf,
        "COMMANDER SIGN :",
        350,
        61 + PAGE_OFFSET,
        100,
        {"size": 8.5, "lineBreak": False},
    )
    line(pdf, 440, 63 + PAGE_OFFSET, 525, 63 + PAGE_OFFSET)


def draw_flight_info(pdf, data):
    flight = data.get("page1", {}).get("flightInfo", {})
    section_heading(pdf, "FLIGHT INFO", 72, 77 + PAGE_OFFSET, 220)

    flight_rows = [
        ("REG", flight.get("registration")),
        ("FL", flight.get("flightLevel")),
        ("FROM", flight.get("departure")),
        ("TO", flight.get("destination")),
        ("ALT1", flight.get("alternate1")),
    ]

    for index, row in enumerate(flight_rows):
        labelled_value(
            pdf, row[0], row[1], 73, (108 + index * 14) + PAGE_OFFSET, 50, 210
        )


def draw_time_section(pdf, data):
    time = data.get("page1", {}).get("time", {}) or data.get("time", {})
    summary = data.get("main", {}).get("summary", {}) or data.get("summary", {})

    section_heading(pdf, "TIME", 305, 77 + PAGE_OFFSET, 220)

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

    write(pdf, etd_text, 305, 96 + PAGE_OFFSET, 120, {"size": 8.5, "lineBreak": False})
    write(pdf, eta_text, 425, 96 + PAGE_OFFSET, 120, {"size": 8.5, "lineBreak": False})

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

    time_rows = [
        ("STEP CLIMB", step_climb_text),
        ("PLND ROUTE", plnd_route),
        ("AVG WINDS", avg_winds),
        ("AVG.WC", avg_wc),
        ("TAS", tas_val),
    ]

    for index, row in enumerate(time_rows):
        labelled_value(
            pdf, row[0], row[1], 305, (119 + index * 14) + PAGE_OFFSET, 80, 220
        )


def draw_fuel_section(pdf, data):
    fuel = data.get("page1", {}).get("fuel", {})
    section_heading(pdf, "FUEL", 72, 193 + PAGE_OFFSET, 220)

    # NOTE: if TRIP / ALT1 / REQ / EXTRA numbers themselves are wrong
    # (not just the endurance/time next to them), that is almost certainly
    # happening upstream of this file -- wherever `fuel` is built before
    # being passed into generate_pdf(). This section only renders what it
    # is given; it cannot correct a wrong trip-fuel figure. Print the
    # `fuel` dict at the call site of generate_pdf() to verify the values
    # going in are already correct.

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
    ]

    for index, row in enumerate(fuel_rows):
        y = (215 + index * 14) + PAGE_OFFSET
        write(pdf, row[0], 73, y, 85, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 158, y, 8, {"size": 8.5, "lineBreak": False})
        write(pdf, row[1], 175, y, 40, {"size": 8.5, "align": "right", "lineBreak": False})
        write(pdf, row[2], 225, y, 35, {"size": 8.5, "align": "center", "lineBreak": False})
        write(pdf, row[3], 268, y, 50, {"size": 8.5, "align": "left", "lineBreak": False})


def draw_weight_section(pdf, data):
    weight = data.get("page1", {}).get("weight", {})
    section_heading(pdf, "WEIGHT", 305, 193 + PAGE_OFFSET, 220)

    weight_rows = [
        ("BOW", weight.get("basicOperatingWeight")),
        ("PAX", weight.get("pax")),
        ("LOAD", weight.get("load")),
        ("ZFW", weight.get("zeroFuelWeight")),
        ("T/O FUEL", weight.get("takeoffFuel")),
        ("TOW", weight.get("takeoffWeight")),
        ("ELW", weight.get("estimatedLandingWeight")),
    ]

    for index, row in enumerate(weight_rows):
        y = (215 + index * 14) + PAGE_OFFSET
        labelled_value(pdf, row[0], row[1], 305, y, 55, 145)
        line(pdf, 452, y + 2, 510, y + 2)


def draw_misc_section(pdf, data):
    misc = data.get("page1", {}).get("misc", {})
    section_heading(pdf, "MISC", 72, 344 + PAGE_OFFSET, 220)

    pln_profile = value(misc.get("plannedProfile")).upper()

    # Correct output prefixes the profile with the flight rules (IFR/VFR).
    # Prepend it if it isn't already baked into plannedProfile.
    flight_rules = find_value(misc, "flightRules", "flight_rules", "rules").upper()
    if flight_rules and not pln_profile.startswith(flight_rules):
        pln_profile = f"{flight_rules} {pln_profile}".strip()

    labelled_value(pdf, "PLN PROFILE", pln_profile, 73, 364 + PAGE_OFFSET, 86, 470)
    line(pdf, 70, 387 + PAGE_OFFSET, 542, 387 + PAGE_OFFSET, 0.7)

    raw_route = value(misc.get("atcRoute")).upper()
    clean_route = raw_route.replace("ROUTE", "").strip() if raw_route.startswith("ROUTE") else raw_route
    labelled_value(pdf, "ATC ROUTE", clean_route, 73, 398 + PAGE_OFFSET, 70, 470)
    line(pdf, 70, 420 + PAGE_OFFSET, 542, 420 + PAGE_OFFSET, 0.4)


def draw_operational_section(pdf, data):
    operational = data.get("page1", {}).get("operational", {})

    labelled_value(pdf, "DEPARTURE ATIS", operational.get("departureAtis"), 73, 431 + PAGE_OFFSET, 95, 455)
    line(pdf, 70, 460 + PAGE_OFFSET, 542, 460 + PAGE_OFFSET, 0.4)

    labelled_value(pdf, "DEP CLEARANCE", operational.get("departureClearance"), 73, 471 + PAGE_OFFSET, 95, 455)
    line(pdf, 70, 500 + PAGE_OFFSET, 542, 500 + PAGE_OFFSET, 0.4)

    labelled_value(pdf, "ARRIVAL ATIS", operational.get("arrivalAtis"), 73, 511 + PAGE_OFFSET, 95, 455)
    line(pdf, 70, 540 + PAGE_OFFSET, 542, 540 + PAGE_OFFSET, 0.4)

    operation_columns = [
        [("CHOCKS ON", operational.get("chocksOn")), ("CHOCKS OFF", operational.get("chocksOff")), ("BLOCK TIME", operational.get("blockTime"))],
        [("TAKE OFF", operational.get("takeoff")), ("LANDING", operational.get("landing")), ("AIR TIME", operational.get("airTime"))],
        [("T/O FUEL", operational.get("takeoffFuel")), ("LDG FUEL", operational.get("landingFuel")), ("F USED", operational.get("fuelUsed"))],
        [("LDWGT", operational.get("landingWeight")), ("LDA", operational.get("lda")), ("BFLD", operational.get("bfld"))],
    ]

    for column_index, column in enumerate(operation_columns):
        x = 73 + column_index * 118
        for row_index, row in enumerate(column):
            y = (551 + row_index * 15) + PAGE_OFFSET
            write(pdf, row[0], x, y, 62, {"size": 8.5, "lineBreak": False})
            line(pdf, x + 58, y + 2, x + 106, y + 2)
            if row[1]:
                write(pdf, row[1], x + 61, y, 44, {"size": 8.5, "lineBreak": False})

    write(pdf, "RVSM CHECKS", 73, 608 + PAGE_OFFSET, 80, {"size": 8.5, "lineBreak": False})
    write(pdf, "TIME (UTC)", 160, 608 + PAGE_OFFSET, 80, {"size": 8.5, "lineBreak": False})
    write(pdf, "ALT1", 232, 608 + PAGE_OFFSET, 60, {"size": 8.5, "lineBreak": False})
    write(pdf, "ALT2", 298, 608 + PAGE_OFFSET, 60, {"size": 8.5, "lineBreak": False})

    for index, label_text in enumerate(["GROUND", "PRE-RVSM CHECK", "LEVEL OFF"]):
        y = (624 + index * 15) + PAGE_OFFSET
        write(pdf, label_text, 73, y, 90, {"size": 8.5, "lineBreak": False})
        line(pdf, 160, y + 2, 214, y + 2)
        line(pdf, 232, y + 2, 286, y + 2)
        line(pdf, 298, y + 2, 352, y + 2)


def draw_alternates(pdf, data):
    alternates = data.get("page1", {}).get("alternates", [])

    for index, alternate in enumerate(alternates[:2]):
        y = (678 + index * 32) + PAGE_OFFSET
        raw_route = value(alternate.get("route")).replace("Route", "").strip()

        alt_label = alternate.get("name", f"ALT{index + 1}")
        write(pdf, alt_label, 73, y, 35, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 112, y, 8, {"size": 8.5, "lineBreak": False})
        write(pdf, field(alternate, "airport"), 125, y, 50, {"size": 8.5, "lineBreak": False})

        write(pdf, "Route", 185, y, 35, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 225, y, 8, {"size": 8.5, "lineBreak": False})
        write(pdf, raw_route, 238, y, 220, {"size": 8.5, "lineBreak": False})

        write(pdf, "FL", 73, y + 14, 20, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 112, y + 14, 8, {"size": 8.5, "lineBreak": False})
        write(pdf, field(alternate, "flightLevel"), 125, y + 14, 50, {"size": 8.5, "lineBreak": False})

        write(pdf, "DIST", 185, y + 14, 30, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 225, y + 14, 8, {"size": 8.5, "lineBreak": False})
        write(pdf, field(alternate, "distance"), 238, y + 14, 55, {"size": 8.5, "lineBreak": False})

        write(pdf, "ETE", 305, y + 14, 25, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 335, y + 14, 8, {"size": 8.5, "lineBreak": False})
        write(pdf, field(alternate, "ete"), 348, y + 14, 55, {"size": 8.5, "lineBreak": False})

        fuel_val = field(alternate, "fuel")
        if fuel_val and not fuel_val.endswith("lbs"):
            fuel_val = f"{fuel_val} lbs"

        write(pdf, "FUEL", 415, y + 14, 30, {"size": 8.5, "lineBreak": False})
        write(pdf, ":", 450, y + 14, 8, {"size": 8.5, "lineBreak": False})
        write(pdf, fuel_val, 463, y + 14, 60, {"size": 8.5, "lineBreak": False})


# --------------------------------------------------
# DRAW PAGES TWO AND THREE
# --------------------------------------------------


def draw_pages_two_and_three(pdf, data):
    title = data.get("page1", {}).get("header", {}).get("routeTitle", "")
    registration = data.get("page1", {}).get("header", {}).get("registration", "")

    pdf.showPage()
    route_header(pdf, title, registration)
    box(pdf, PAGE["left"], 32, 496, 728)

    y = draw_navlog_header(pdf, 32)
    main_result = draw_navlog_rows(pdf, data.get("mainNavlog", []), y, 680)

    y = main_result["y"]

    alternate_name = data.get("page1", {}).get("flightInfo", {}).get("alternate1", "")
    alternate_route = data.get("routes", {}).get("alternate1Route", "")
    clean_alt_route = value(alternate_route).replace("Route", "").strip()

    title_left = f"Alternate route for {alternate_name}"
    title_right = f"Route {clean_alt_route}" if clean_alt_route else ""

    y = draw_navlog_title(pdf, title_left, title_right, y)
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

    y = continuation["y"] + 22
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


# --------------------------------------------------
# DRAW PAGE FOUR (LAST PAGE) - FULL WINDS TABLE
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
        48 + PAGE_OFFSET,
        380,
        {"size": 9, "align": "center", "lineBreak": False},
    )

    write(
        pdf,
        ". . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .",
        160,
        60 + PAGE_OFFSET,
        300,
        {"size": 8, "align": "center", "lineBreak": False},
    )

    # This was rendering blank because "flightPlanText" was the only key
    # ever tried. Search several likely spellings before giving up.
    flight_plan_text = find_value(
        atc,
        "flightPlanText", "flight_plan_text", "fplText", "fpl_text",
        "flightPlan", "flight_plan", "text", "planText", "plan_text",
        "icaoText", "icao_text", "fpl",
    )
    if flight_plan_text:
        write(pdf, flight_plan_text, 68, 76 + PAGE_OFFSET, 476, {"size": 8})

    table_left = 68
    table_width = 476

    write(
        pdf,
        "ENROUTE WINDS",
        table_left,
        180 + PAGE_OFFSET,
        table_width,
        {"size": 8.5, "align": "center", "lineBreak": False},
    )

    # Safely assemble all wind sections (main flight + alternates).
    # Instead of guessing specific key names for the alternate-route wind
    # rows, treat ANY list-valued key in enrouteWinds (besides "bands" and
    # "rows") as an additional block of rows to append, in the order the
    # keys appear. This means it no longer matters what the upstream data
    # calls the alternate wind blocks -- if it's a list of row dicts, it
    # gets included.
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

    y = 205 + PAGE_OFFSET
    row_height = 11.0  # Compact spacing to fit long wind tables comfortably

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
    pdf.drawCentredString(PAGE["left"] + 496 / 2, page_height - (728 + PAGE_OFFSET), end_report_text)

    computed_date = datetime.now().strftime("%d-%m-%Y")
    computed_time = datetime.now().strftime("%H:%M:%S")

    write(pdf, f"COMPUTED DATE : {computed_date}", PAGE["left"], 756, 220, {"size": 8.5, "lineBreak": False, "padding": 0})
    write(pdf, f"TIME : {computed_time} Asia/Kolkata", PAGE["right"] - 220, 756, 220, {"size": 8.5, "align": "right", "lineBreak": False, "padding": 0})


# --------------------------------------------------
# GENERATE PDF ENTRYPOINT (MLOVE)
# --------------------------------------------------


def generate_mlove_pdf(navlog):
    """Generate the MLOVE-formatted flight-plan PDF and return its
    relative path under OUTPUT_DIRECTORY."""
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)

    file_name = f"MLOVE{int(datetime.now().timestamp() * 1000)}.pdf"
    absolute_path = os.path.join(OUTPUT_DIRECTORY, file_name)
    relative_path = os.path.join("generated", file_name)

    # common.py's drawing primitives share one active page height across
    # every template (MLOVE/A4, VTBBD/Letter) - always set it explicitly
    # rather than relying on whatever the previous request left behind.
    set_page_height(A4[1])
    pdf = canvas.Canvas(absolute_path, pagesize=A4)

    draw_page_one(pdf, navlog)
    draw_pages_two_and_three(pdf, navlog)
    draw_page_four(pdf, navlog)

    pdf.save()

    return relative_path


def generate_pdf(navlog, file_prefix="MLOVE"):
    """Dispatch to the right template based on file_prefix.

    "MLOVE" (default) is handled locally in this file.
    "DEFAULT" and "VTBBD" are delegated to their own modules so this
    file doesn't keep growing.
    """
    prefix = str(file_prefix).upper()

    if prefix == "DEFAULT":
        from default import generate_default_pdf
        return generate_default_pdf(navlog)

    if prefix == "VTBBD":
        from vtbbd import generate_vtbbd_pdf
        return generate_vtbbd_pdf(navlog)

    if prefix == "VTVIK":
        from vtvik import generate_vtvik_pdf
        return generate_vtvik_pdf(navlog)

    return generate_mlove_pdf(navlog)