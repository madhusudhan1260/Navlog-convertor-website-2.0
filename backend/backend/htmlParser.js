const cheerio = require("cheerio");

// =====================================================
// CLEAN TEXT UTILITY
// =====================================================
function clean(value) {
    return String(value || "")
        .replace(/\u00A0/g, " ")
        .replace(/\r/g, "")
        .replace(/\t/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}

// Strip a trailing unit word ("lbs", "NM", "ft") off a numeric-looking value,
// leaving just the number. Returns "" if the input is empty/blank.
function stripUnit(value, unit) {
    const v = clean(value);
    if (!v) return "";
    const regex = new RegExp("\\s*" + unit + "\\s*$", "i");
    return clean(v.replace(regex, ""));
}

// Extract a bare number from a string. Returns "" if none found.
function toNumber(value) {
    const v = clean(value).replace(/,/g, "");
    const match = v.match(/-?\d+(?:\.\d+)?/);
    return match ? match[0] : "";
}

// ForeFlight renders top-level durations like "0h50m" / "1h02m".
// Convert to the "H:MM" style used throughout the rest of the document.
function toHoursMinutes(value) {
    const v = clean(value);
    const match = v.match(/(\d+)h(\d+)m/);
    if (!match) return v;
    return `${parseInt(match[1], 10)}:${match[2].padStart(2, "0")}`;
}

// =====================================================
// INITIALIZE PREDICTABLE DATA STRUCT
// =====================================================
function emptyResult() {
    return {
        title: "",
        summary: {
            pic: "", soulsOnBoard: "", tailRaw: "", registration: "", aircraftType: "",
            profile: "", fuelFlow: "", distance: "", etd: "", ete: "", eta: "",
            route: "", altitude: ""
        },
        fuelWeights: {
            blockFuel: "", taxiFuel: "", flightFuel: "", reserveFuel: "", reserveMin: "",
            alternateFuel: "", extraFuel: "", additional: "", payload: "",
            zfw: "", tow: "", elw: ""
        },
        route: "",
        waypoints: [],
        airportInfo: [],
        enrouteWinds: {
            bands: [],
            rows: []
        },
        flightInformationRegions: []
    };
}

// =====================================================
// SUMMARY & TIMES TABLE  (table.summary-times)
// Rows: PIC | Souls on board | Tail | Profile | Fuel Flow |
//       Distance | ETD | ETE | ETA | Route | Altitude
// =====================================================
function parseSummaryTimes($, result) {
    $("table.summary-times tr.table-data-row").each((_, tr) => {
        const cells = [];
        $(tr).find("td").each((_, td) => cells.push(clean($(td).text())));
        if (cells.length < 2) return;

        const label = cells[0].toLowerCase();
        const value = cells[1];

        if (label === "pic") result.summary.pic = value;
        else if (label === "souls on board") result.summary.soulsOnBoard = value;
        else if (label === "tail") result.summary.tailRaw = value;
        else if (label === "profile") result.summary.profile = value;
        else if (label === "fuel flow") result.summary.fuelFlow = value;
        else if (label === "distance") result.summary.distance = value;
        else if (label === "etd") result.summary.etd = value;
        else if (label === "ete") result.summary.ete = toHoursMinutes(value);
        else if (label === "eta") result.summary.eta = value;
        else if (label === "route") result.summary.route = value;
        else if (label === "altitude") result.summary.altitude = value;
    });

    // Tail looks like "VTCSP (C56X)" -> split registration / aircraft type
    const tailMatch = result.summary.tailRaw.match(/^([A-Z0-9\-]+)\s*\(([^)]+)\)/i);
    if (tailMatch) {
        result.summary.registration = tailMatch[1];
        result.summary.aircraftType = tailMatch[2];
    } else if (result.summary.tailRaw) {
        result.summary.registration = result.summary.tailRaw;
    }
}

// =====================================================
// FUEL & WEIGHTS TABLE  (table.fuel-weights)
// Rows: Block Fuel | Taxi Fuel | Flight Fuel | Reserve Fuel (+Min) |
//       Alternate Fuel | Extra Fuel | Additional | Payload | ZFW | TOW | ELW
// =====================================================
function parseFuelWeights($, result) {
    $("table.fuel-weights tbody").each((_, tbody) => {
        const tr = $(tbody).find("tr").first();
        const labelTd = tr.find("td").first();
        const valueTd = tr.find("td").eq(1);
        if (!labelTd.length || !valueTd.length) return;

        // Reserve Fuel row has a nested "Min: 625 lbs" span inside the label cell
        const minSpan = labelTd.find("span.small");
        const reserveMin = minSpan.length ? clean(minSpan.text()) : "";

        const labelClone = labelTd.clone();
        labelClone.find("span").remove();
        const label = clean(labelClone.text()).toLowerCase();
        const value = stripUnit(clean(valueTd.text()), "lbs");

        if (label === "block fuel") result.fuelWeights.blockFuel = value;
        else if (label === "taxi fuel") result.fuelWeights.taxiFuel = value;
        else if (label === "flight fuel") result.fuelWeights.flightFuel = value;
        else if (label === "reserve fuel") {
            result.fuelWeights.reserveFuel = value;
            result.fuelWeights.reserveMin = stripUnit(reserveMin.replace(/^min:?\s*/i, ""), "lbs");
        }
        else if (label === "alternate fuel") result.fuelWeights.alternateFuel = value;
        else if (label === "extra fuel") result.fuelWeights.extraFuel = value;
        else if (label === "additional") result.fuelWeights.additional = value;
        else if (label === "payload") result.fuelWeights.payload = value;
        else if (label === "zfw") result.fuelWeights.zfw = value;
        else if (label === "tow") result.fuelWeights.tow = value;
        else if (label === "elw") result.fuelWeights.elw = value;
    });
}

// =====================================================
// ROUTE  (section.route)
// =====================================================
function parseRoute($, result) {
    const routeText = clean($("section.route div").first().text());
    result.route = routeText || result.summary.route;
}

// =====================================================
// WAYPOINT TABLE  (table.waypoint)
// Verified 19-column layout (0-indexed):
// 0 Waypoint | 1 Airway | 2 HDG | 3 CRS | 4 ALT | 5 CMP | 6 DIR/SPD |
// 7 ISA | 8 TAS | 9 GS | 10 LEG(dist) | 11 REM(dist) | 12 USED(fuel) |
// 13 REM(fuel) | 14 ACT(fuel) | 15 LEG(time) | 16 REM(time) | 17 ETE | 18 ACT(time/ATA)
// =====================================================
function parseWaypoints($, result) {
    const waypoints = [];

    $("table.waypoint tbody tr").each((_, tr) => {
        const tds = $(tr).find("td");
        if (tds.length < 19) return;

        // Waypoint cell can contain a nav-aid subtitle in <span class="small">
        const waypointTd = tds.eq(0).clone();
        const subtitle = clean(waypointTd.find("span.small").text());
        waypointTd.find("span").remove();
        const waypointName = clean(waypointTd.text());

        const cell = (i) => clean(tds.eq(i).text());

        waypoints.push({
            waypoint: waypointName,
            waypointDetail: subtitle,
            airway: cell(1),
            heading: cell(2),
            course: cell(3),
            flightLevel: cell(4),
            windComponent: cell(5),
            windDirectionSpeed: cell(6),
            isa: cell(7),
            tas: cell(8),
            gs: cell(9),
            legDistance: cell(10),
            remainingDistance: cell(11),
            fuelUsed: cell(12),
            fuelRemaining: cell(13),
            actualFuel: cell(14),
            legTime: cell(15),
            remainingTime: cell(16),
            ete: cell(17),
            eta: "",
            ata: cell(18)
        });
    });

    result.waypoints = waypoints;
}

// =====================================================
// AIRPORT INFORMATION  (table.airport-frequencies)
// Columns: (DEP/DEST) | Airport | ETA | WX | TWR/CTAF | CLR | GND | ELEV | RWY | RWY LENGTH
// =====================================================
function parseAirportInfo($, result) {
    const airports = [];

    $("table.airport-frequencies tbody tr").each((_, tr) => {
        const tds = $(tr).find("td");
        if (tds.length < 10) return;

        const cell = (i) => clean(tds.eq(i).text());

        airports.push({
            type: cell(0),
            airport: cell(1),
            eta: cell(2),
            atis: cell(3),   // ForeFlight labels this column "WX" (weather freq)
            tower: cell(4),
            clearance: cell(5),
            ground: cell(6),
            elevation: cell(7),
            runway: cell(8),
            runwayLength: cell(9)
        });
    });

    result.airportInfo = airports;
}

// =====================================================
// ENROUTE WINDS  (table.winds-aloft)
// Header row 1 gives dynamic altitude/FL bands (colspan=2 each).
// Data rows: ident, then (wind, isa) pairs, one pair per band.
// The bold "border-bottom" row is the block-fuel summary footer - skip it.
// =====================================================
function parseEnrouteWinds($, result) {
    const table = $("table.winds-aloft").first();
    if (!table.length) return;

    const bands = [];
    table.find("thead tr").first().find("th").each((i, th) => {
        if (i === 0) return; // first th is the blank corner cell
        const label = clean($(th).text());
        if (label) bands.push(label);
    });

    const rows = [];
    table.find("tbody tr").each((_, tr) => {
        const rowClass = $(tr).attr("class") || "";
        if (/bold/i.test(rowClass)) return; // footer summary row, not a waypoint

        const tds = $(tr).find("td");
        if (tds.length < 1) return;

        const identifier = clean(tds.eq(0).text());
        if (!identifier) return;

        const values = [];
        for (let i = 0; i < bands.length; i++) {
            const windIdx = 1 + i * 2;
            const isaIdx = 2 + i * 2;
            values.push({
                wind: tds.eq(windIdx).length ? clean(tds.eq(windIdx).text()) : "",
                isa: tds.eq(isaIdx).length ? clean(tds.eq(isaIdx).text()) : ""
            });
        }

        rows.push({ identifier, values });
    });

    result.enrouteWinds = { bands, rows };
}

// =====================================================
// FLIGHT INFORMATION REGION  (table.flight-information-region)
// =====================================================
function parseFlightInformationRegions($, result) {
    const regions = [];

    $("table.flight-information-region tbody tr").each((_, tr) => {
        const tds = $(tr).find("td");
        if (tds.length < 5) return;

        regions.push({
            fir: clean(tds.eq(0).text()),
            eet: clean(tds.eq(1).text()),
            entry: clean(tds.eq(2).text()),
            exit: clean(tds.eq(3).text()),
            distance: clean(tds.eq(4).text())
        });
    });

    result.flightInformationRegions = regions;
}

// =====================================================
// CORE PARSER RUNTIME
// =====================================================
function parseHTML(html) {
    if (!html) throw new Error("HTML EMPTY");

    const $ = cheerio.load(html);
    const result = emptyResult();

    result.title = clean($("title").text()) || "ForeFlight Navlog";

    parseSummaryTimes($, result);
    parseFuelWeights($, result);
    parseRoute($, result);
    parseWaypoints($, result);
    parseAirportInfo($, result);
    parseEnrouteWinds($, result);
    parseFlightInformationRegions($, result);

    // Derive departure/destination from the airport-frequencies table (most reliable),
    // falling back to the first/last token of the route string.
    const dep = result.airportInfo.find(a => a.type.toUpperCase() === "DEP");
    const dest = result.airportInfo.find(a => a.type.toUpperCase() === "DEST");
    result.departure = dep ? dep.airport : (result.route.split(" ")[0] || "");
    result.destination = dest ? dest.airport : (result.route.split(" ").slice(-1)[0] || "");

    console.log("\n========================================");
    console.log("FOREFLIGHT PARSER SUMMARY");
    console.log("========================================");
    console.log("Title:              ", result.title);
    console.log("Departure/Dest:      ", result.departure, "->", result.destination);
    console.log("Registration/Type:   ", result.summary.registration, result.summary.aircraftType);
    console.log("Waypoints parsed:    ", result.waypoints.length);
    console.log("Airport info rows:   ", result.airportInfo.length);
    console.log("Enroute wind bands:  ", result.enrouteWinds.bands.length);
    console.log("Enroute wind rows:   ", result.enrouteWinds.rows.length);
    console.log("========================================");

    return result;
}

module.exports = parseHTML;