import json
import re
from bs4 import BeautifulSoup


# =====================================================
# CLEAN TEXT UTILITIES
# =====================================================

def clean(value):
    return (
        str(value or "")
        .replace("\u00A0", " ")
        .replace("\r", "")
        .replace("\t", " ")
        .strip()
    )


def clean_route(route_text):
    """
    Cleans raw route strings:
    removes non-breaking spaces, bullet points (■), and the 'Route' prefix.
    """
    rt = str(route_text or "").replace("\xa0", " ").replace("\u00A0", " ")
    rt = rt.replace("■", "").replace("▪", "")
    rt = re.sub(r"^Route\s*", "", rt, flags=re.IGNORECASE)
    return rt.strip()


def strip_unit(value, unit):
    """Strip trailing units like lbs, NM, ft etc."""
    v = clean(value)
    if not v:
        return ""
    regex = re.compile(r"\s*" + re.escape(unit) + r"\s*$", re.IGNORECASE)
    return clean(regex.sub("", v))


def to_hours_minutes(value):
    """Convert 0h50m -> 0:50, 2h03m -> 2:03"""
    v = clean(value)
    match = re.search(r"(\d+)h(\d+)m", v)
    if not match:
        return v
    return f"{int(match.group(1))}:{match.group(2).zfill(2)}"


# =====================================================
# INITIALIZE PREDICTABLE DATA STRUCT
# =====================================================

def empty_result():
    return {
        "title": "",
        "summary": {
            "pic": "",
            "fo": "",
            "soulsOnBoard": "",
            "tailRaw": "",
            "registration": "",
            "aircraftType": "",
            "profile": "",
            "fuelFlow": "",
            "distance": "",
            "track": "",
            "tas": "",
            "averageWinds": "",
            "etd": "",
            "ete": "",
            "eta": "",
            "route": "",
            "altitude": "",
            "date": "",
            "pax": ""
        },
        "fuelWeights": {
            "blockFuel": "",
            "taxiFuel": "",
            "flightFuel": "",
            "reserveFuel": "",
            "reserveMin": "",
            "alternateFuel": "",
            "extraFuel": "",
            "contingencyFuel": "",
            "landingFuel": "",
            "additional": "",
            "payload": "",
            "zfw": "",
            "tow": "",
            "elw": ""
        },
        "route": "",
        "waypoints": [],
        "alternates": [],
        "alternateWaypoints": {
            "alt1": [],
            "alt2": []
        },
        "levelCalculations": [],
        "vSpeeds": {
            "v1": "",
            "vr": "",
            "v2": "",
            "vfto": "",
            "vref": ""
        },
        "airportInfo": [],
        "enrouteWinds": {
            "bands": [],
            "rows": []
        },
        "flightInformationRegions": [],
        "atcFlightPlan": {
            "title": "",
            "rawText": [],
            "fplString": ""
        }
    }


# =====================================================
# SUMMARY & TIMES TABLE
# =====================================================

def parse_summary_times(soup, result):
    rows = soup.select("table.summary-times tr.table-data-row, table.summary-times tr")
    for tr in rows:
        cells = [clean(td.get_text()) for td in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue

        label = cells[0].lower()
        value = cells[1]

        if label in ("pic", "captain"):
            result["summary"]["pic"] = value
        # FIX: "SIC" (Second In Command) is a common label for the FO/
        # co-pilot row in operator-side flight plans, but was never in
        # this alias list even though default.py's own find_value() alias
        # list for FO already anticipated "sic" as a possible key name.
        # That downstream alias is useless if the raw HTML label is never
        # captured here in the first place - this was the actual point
        # where "SIC"-labelled FO rows were being silently dropped.
        elif label in ("fo", "f/o", "copilot", "first officer", "sic"):
            result["summary"]["fo"] = value
        elif label == "souls on board":
            result["summary"]["soulsOnBoard"] = value
        elif label in ("tail", "registration"):
            result["summary"]["tailRaw"] = value
        elif label == "profile":
            result["summary"]["profile"] = value
        elif label == "fuel flow":
            result["summary"]["fuelFlow"] = value
        elif label == "distance":
            result["summary"]["distance"] = value
        elif label in ("track", "trk", "mag track"):
            result["summary"]["track"] = value
        elif label in ("tas", "planned tas"):
            result["summary"]["tas"] = value
        elif label in ("avg wind", "average wind", "avg winds", "average winds", "wind"):
            result["summary"]["averageWinds"] = value
        elif label == "etd":
            result["summary"]["etd"] = value
        elif label == "ete":
            result["summary"]["ete"] = to_hours_minutes(value)
        elif label == "eta":
            result["summary"]["eta"] = value
        elif label == "route":
            result["summary"]["route"] = clean_route(value)
        elif label in ("altitude", "fl"):
            result["summary"]["altitude"] = value
        elif label in ("date", "flight date"):
            result["summary"]["date"] = value
        elif label in ("pax", "passengers"):
            result["summary"]["pax"] = value

    # Extract Registration & Aircraft Type
    tail_match = re.match(
        r"^([A-Z0-9\-]+)\s*\(([^)]+)\)",
        result["summary"]["tailRaw"],
        re.IGNORECASE
    )
    if tail_match:
        result["summary"]["registration"] = tail_match.group(1)
        result["summary"]["aircraftType"] = tail_match.group(2)
    elif result["summary"]["tailRaw"]:
        result["summary"]["registration"] = result["summary"]["tailRaw"]


# =====================================================
# PERFORMANCE SUMMARY STRIP (TOP OF PAGE)
# =====================================================
# FIX: ForeFlight's navlog HTML has a second, completely separate summary
# block at the very top of the page:
#
#   <section class="performance-summary"><table><tbody>
#     <td class="performance-metric avg-wind"><strong>Avg Wind</strong>
#       <span>0kt tail (282°/020)</span></td>
#     ...
#
# This table has no class of its own (only the wrapping <section> does),
# and it is NOT the same table as table.summary-times. Some fields (ETE,
# Distance, ETD, ETA, TOW, ELW, Block/Taxi/Flight/Reserve/Alternate/Extra/
# Landing Fuel) are duplicated in both places, but "Avg Wind" ONLY appears
# here - table.summary-times has no wind row at all in ForeFlight's export.
# parse_summary_times() only ever selects table.summary-times, so this
# entire block, and Avg Wind specifically, was previously never read,
# which is why WIND always rendered blank regardless of the source HTML.
def parse_performance_summary(soup, result):
    metrics = soup.select("section.performance-summary td.performance-metric")

    for td in metrics:
        strong = td.find("strong")
        label = clean(strong.get_text()).lower() if strong else ""

        span = td.find("span")
        val = clean(span.get_text()) if span else ""

        if not val:
            continue

        # Only fill fields that table.summary-times never provides.
        # (Guarded with "if not already set" so this never clobbers a
        # value parse_summary_times already found elsewhere.)
        if label == "avg wind" and not result["summary"]["averageWinds"]:
            result["summary"]["averageWinds"] = val


# =====================================================
# FUEL & WEIGHTS TABLE
# =====================================================

def parse_fuel_weights(soup, result):
    for tbody in soup.select("table.fuel-weights tbody"):
        tr = tbody.find("tr")
        if tr is None:
            continue

        tds = tr.find_all("td")
        if len(tds) < 2:
            continue

        label_td, value_td = tds[0], tds[1]

        min_span = label_td.find("span", class_="small")
        reserve_min = clean(min_span.get_text()) if min_span else ""

        label_clone = BeautifulSoup(str(label_td), "html.parser")
        for span in label_clone.find_all("span"):
            span.decompose()

        label = clean(label_clone.get_text()).lower()
        value = strip_unit(clean(value_td.get_text()), "lbs")

        if label == "block fuel":
            result["fuelWeights"]["blockFuel"] = value
        elif label == "taxi fuel":
            result["fuelWeights"]["taxiFuel"] = value
        elif label == "flight fuel":
            result["fuelWeights"]["flightFuel"] = value
        elif label in ("contingency fuel", "contingency"):
            result["fuelWeights"]["contingencyFuel"] = value
        elif label in ("landing fuel", "landing", "est landing fuel"):
            result["fuelWeights"]["landingFuel"] = value
        elif label == "reserve fuel":
            result["fuelWeights"]["reserveFuel"] = value
            reserve_min = re.sub(r"^min:?\s*", "", reserve_min, flags=re.IGNORECASE)
            result["fuelWeights"]["reserveMin"] = strip_unit(reserve_min, "lbs")
        elif label == "alternate fuel":
            result["fuelWeights"]["alternateFuel"] = value
        elif label == "extra fuel":
            result["fuelWeights"]["extraFuel"] = value
        elif label == "additional":
            result["fuelWeights"]["additional"] = value
        elif label == "payload":
            result["fuelWeights"]["payload"] = value
        elif label == "zfw":
            result["fuelWeights"]["zfw"] = value
        elif label == "tow":
            result["fuelWeights"]["tow"] = value
        elif label == "elw":
            result["fuelWeights"]["elw"] = value


# =====================================================
# ROUTE
# =====================================================

def parse_route(soup, result):
    section = soup.select_one("section.route div, div.route-text")
    route_text = clean(section.get_text()) if section else ""

    # Route cleaning applied here
    cleaned_route = clean_route(route_text)

    result["route"] = cleaned_route if cleaned_route else result["summary"]["route"]


# =====================================================
# WAYPOINT TABLE
# =====================================================

def parse_waypoints(soup, result):
    waypoints = []
    rows = soup.select("table.waypoint tbody tr, table.navlog-table tbody tr")

    for tr in rows:
        tds = tr.find_all("td")
        if len(tds) < 15:
            continue

        waypoint_clone = BeautifulSoup(str(tds[0]), "html.parser")
        subtitle_span = waypoint_clone.find("span", class_="small")
        subtitle = clean(subtitle_span.get_text()) if subtitle_span else ""

        for span in waypoint_clone.find_all("span"):
            span.decompose()

        waypoint_name = clean(waypoint_clone.get_text())

        def cell(i):
            return clean(tds[i].get_text()) if i < len(tds) else ""

        waypoints.append({
            "waypoint": waypoint_name,
            "waypointDetail": subtitle,
            "airway": cell(1),
            "heading": cell(2),
            "course": cell(3),
            "flightLevel": cell(4),
            "windComponent": cell(5),
            "windDirectionSpeed": cell(6),
            "isa": cell(7),
            "tas": cell(8),
            "gs": cell(9),
            "legDistance": cell(10),
            "remainingDistance": cell(11),
            "fuelUsed": cell(12),
            "fuelRemaining": cell(13),
            "actualFuel": cell(14),
            "legTime": cell(15) if len(tds) > 15 else "",
            "remainingTime": cell(16) if len(tds) > 16 else "",
            "ete": cell(17) if len(tds) > 17 else "",
            "ata": cell(18) if len(tds) > 18 else ""
        })

    result["waypoints"] = waypoints


# =====================================================
# LEVEL CALCULATIONS / V-SPEEDS
# =====================================================

def parse_level_calculations(soup, result):
    levels = []

    # Primary path: a dedicated level-calculation table, in case some
    # ForeFlight export variant ever includes one directly.
    rows = soup.select("table.level-calculations tbody tr, table.different-levels tbody tr")

    for tr in rows:
        tds = [clean(td.get_text()) for td in tr.find_all("td")]
        if len(tds) >= 4:
            levels.append({
                "fl": tds[0],
                "wc": tds[1],
                "time": tds[2],
                "trip": tds[3]
            })

    # FIX: In practice ForeFlight never emits table.level-calculations /
    # table.different-levels at all - the "different level" figures are
    # instead the BOLD FOOTER ROW of table.winds-aloft, one cell per FL
    # band, e.g.:
    #
    #   <tr class="border-bottom text-centered bold table-data-row">
    #     <td></td>
    #     <td class="winds-aloft-footer-cell">
    #       <div><span class="no-wrap">1h12m (+0:05)</span>,
    #            <span class="no-wrap">1739 lbs</span></div>
    #       <div class="no-wrap">Avg wind comp: H3</div>
    #     </td>
    #     ... (one such cell per FL band)
    #
    # parse_enroute_winds() correctly SKIPS this row (it isn't a per-
    # waypoint wind row), but nothing else ever captured it, so the
    # DIFFERENT LEVEL CALCULATION table always rendered empty. Extract it
    # here as a fallback whenever no dedicated table was found above.
    if not levels:
        winds_table = soup.select_one("table.winds-aloft, table.enroute-winds")

        if winds_table:
            bands = []
            header_row = winds_table.select_one("thead tr")
            if header_row:
                for i, th in enumerate(header_row.find_all(["th", "td"])):
                    if i == 0:
                        continue
                    label = clean(th.get_text())
                    if label:
                        bands.append(label)

            footer_row = None
            for tr in winds_table.select("tbody tr"):
                row_class = (
                    " ".join(tr.get("class", []))
                    if isinstance(tr.get("class"), list)
                    else str(tr.get("class", ""))
                )
                if re.search(r"bold", row_class, re.IGNORECASE):
                    footer_row = tr
                    break

            if footer_row:
                footer_cells = footer_row.find_all("td", class_="winds-aloft-footer-cell")

                for i, cell in enumerate(footer_cells):
                    band_label = bands[i] if i < len(bands) else ""
                    fl_label = band_label.split("(")[0].strip()

                    # The time/trip pair sits in two "no-wrap" <span>s
                    # inside the cell's first <div>, e.g.
                    # "1h12m (+0:05)" and "1739 lbs".
                    spans = cell.find_all("span", class_="no-wrap")
                    time_text = clean(spans[0].get_text()) if len(spans) > 0 else ""
                    trip_text = clean(spans[1].get_text()) if len(spans) > 1 else ""
                    trip_text = strip_unit(trip_text, "lbs")

                    delta_match = re.search(r"\(([^)]+)\)", time_text)
                    delta = delta_match.group(1).strip() if delta_match else ""
                    # Suppress the baseline row's own "(0:00)" delta so it
                    # prints blank, same as every other zero-delta figure
                    # elsewhere in this pipeline.
                    if delta and re.match(r"^[+-]?0:00$", delta):
                        delta = ""
                    time_val = f"({delta})" if delta else ""

                    wc_match = re.search(
                        r"Avg wind comp:\s*(\S+)", clean(cell.get_text()), re.IGNORECASE
                    )
                    wc_val = wc_match.group(1) if wc_match else ""

                    levels.append({
                        "fl": fl_label,
                        "wc": wc_val,
                        "time": time_val,
                        "trip": trip_text
                    })

    result["levelCalculations"] = levels

    # V-Speeds Extraction
    vspeed_table = soup.select_one("table.v-speeds, div.v-speeds")
    if vspeed_table:
        v_text = clean(vspeed_table.get_text())
        for vspeed in ["v1", "vr", "v2", "vfto", "vref"]:
            match = re.search(rf"{vspeed}\s*:\s*([0-9a-z_]+)", v_text, re.IGNORECASE)
            if match:
                result["vSpeeds"][vspeed] = match.group(1)


# =====================================================
# ALTERNATES & ALTERNATE WAYPOINTS
# =====================================================

def parse_alternates(soup, result):
    alternates = []
    rows = soup.select("table.alternates tbody tr, div.alternate-summary tr")

    for tr in rows:
        tds = [clean(td.get_text()) for td in tr.find_all("td")]
        if len(tds) >= 4:
            alternates.append({
                "airport": tds[0],
                "route": clean_route(tds[1]),
                "distance": tds[2],
                "fuel": tds[3]
            })

    result["alternates"] = alternates


# =====================================================
# AIRPORT INFORMATION
# =====================================================

def parse_airport_info(soup, result):
    airports = []
    rows = soup.select("table.airport-frequencies tbody tr, table.airport-info tbody tr")

    for tr in rows:
        tds = tr.find_all("td")
        if len(tds) < 8:
            continue

        def cell(i):
            return clean(tds[i].get_text()) if i < len(tds) else ""

        airports.append({
            "type": cell(0),
            "airport": cell(1),
            "eta": cell(2),
            "atis": cell(3),
            "tower": cell(4),
            "clearance": cell(5),
            "ground": cell(6),
            "elevation": cell(7),
            "runway": cell(8),
            "runwayLength": cell(9)
        })

    result["airportInfo"] = airports


# =====================================================
# ENROUTE WINDS
# =====================================================

def parse_enroute_winds(soup, result):
    table = soup.select_one("table.winds-aloft, table.enroute-winds")
    if table is None:
        return

    bands = []
    header_row = table.select_one("thead tr")
    if header_row:
        headers = header_row.find_all(["th", "td"])
        for i, th in enumerate(headers):
            if i == 0:
                continue
            label = clean(th.get_text())
            if label:
                bands.append(label)

    rows = []
    body_rows = table.select("tbody tr")

    for tr in body_rows:
        row_class = " ".join(tr.get("class", [])) if isinstance(tr.get("class"), list) else str(tr.get("class", ""))
        if re.search(r"bold", row_class, re.IGNORECASE):
            continue

        tds = tr.find_all("td")
        if len(tds) < 1:
            continue

        identifier = clean(tds[0].get_text())
        if not identifier:
            continue

        values = []
        for i in range(len(bands)):
            wind_idx = 1 + i * 2
            isa_idx = 2 + i * 2

            wind = clean(tds[wind_idx].get_text()) if wind_idx < len(tds) else ""
            isa = clean(tds[isa_idx].get_text()) if isa_idx < len(tds) else ""

            values.append({"wind": wind, "isa": isa})

        rows.append({"identifier": identifier, "values": values})

    result["enrouteWinds"] = {"bands": bands, "rows": rows}


# =====================================================
# ATC FLIGHT PLAN (ICAO FPL)
# =====================================================

def parse_atc_flight_plan(soup, result):
    atc_elem = soup.select_one("div.atc-flight-plan, table.atc-plan, section.atc-fpl")
    if not atc_elem:
        return

    raw_lines = [clean(line) for line in atc_elem.get_text().split("\n") if clean(line)]
    fpl_text = " ".join(raw_lines)

    result["atcFlightPlan"] = {
        "title": f"ATC FLIGHT PLAN {result.get('departure', '')} to {result.get('destination', '')}",
        "rawText": raw_lines,
        "fplString": fpl_text
    }


# =====================================================
# FLIGHT INFORMATION REGIONS
# =====================================================

def parse_flight_information_regions(soup, result):
    regions = []
    rows = soup.select("table.flight-information-region tbody tr")

    for tr in rows:
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue

        regions.append({
            "fir": clean(tds[0].get_text()),
            "eet": clean(tds[1].get_text()),
            "entry": clean(tds[2].get_text()),
            "exit": clean(tds[3].get_text()),
            "distance": clean(tds[4].get_text())
        })

    result["flightInformationRegions"] = regions


# =====================================================
# CORE PARSER RUNTIME
# =====================================================

def parse_html(html):
    if not html:
        raise Exception("HTML EMPTY")

    soup = BeautifulSoup(html, "html.parser")
    result = empty_result()

    title = soup.title.get_text() if soup.title else ""
    result["title"] = clean(title) or "ForeFlight Navlog"

    # Run all extraction modules
    parse_summary_times(soup, result)
    parse_performance_summary(soup, result)
    parse_fuel_weights(soup, result)
    parse_route(soup, result)
    parse_waypoints(soup, result)
    parse_level_calculations(soup, result)
    parse_alternates(soup, result)
    parse_airport_info(soup, result)
    parse_enroute_winds(soup, result)
    parse_flight_information_regions(soup, result)

    # Derive Departure & Destination Aerodromes
    dep, dest = None, None
    for airport in result["airportInfo"]:
        airport_type = airport["type"].upper()
        if airport_type == "DEP":
            dep = airport
        elif airport_type == "DEST":
            dest = airport

    if dep:
        result["departure"] = dep["airport"]
    else:
        route_parts = result["route"].split()
        result["departure"] = route_parts[0] if route_parts else ""

    if dest:
        result["destination"] = dest["airport"]
    else:
        route_parts = result["route"].split()
        result["destination"] = route_parts[-1] if route_parts else ""

    parse_atc_flight_plan(soup, result)

    # Summary Console Output
    print("\n========================================")
    print("FOREFLIGHT PARSER SUMMARY")
    print("========================================")
    print("Title:              ", result["title"])
    print("Departure/Dest:     ", result["departure"], "->", result["destination"])
    print("Registration/Type:  ", result["summary"]["registration"], result["summary"]["aircraftType"])
    print("Route:              ", result["route"])
    print("Avg Wind:           ", result["summary"]["averageWinds"])
    print("Waypoints parsed:   ", len(result["waypoints"]))
    print("Level Calc Rows:    ", len(result["levelCalculations"]))
    print("Airport info rows:  ", len(result["airportInfo"]))
    print("Enroute wind bands: ", len(result["enrouteWinds"]["bands"]))
    print("Enroute wind rows:  ", len(result["enrouteWinds"]["rows"]))
    print("========================================\n")

    return result


if __name__ == "__main__":
    with open("navlog.html", "r", encoding="utf-8") as f:
        html = f.read()

    result = parse_html(html)
    print(json.dumps(result, indent=4))