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

// =====================================================
// INITIALIZE PREDICTABLE DATA STRUCT
// =====================================================
function emptyResult() {
    return {
        header: "",
        flightSummary: {
            registration: "", flightLevel: "", date: "", departure: "",
            destination: "", alternate: "", ETD: "", ETA: "", ETE: "",
            distance: "", averageWind: "", averageWC: "", TAS: "", stepClimb: ""
        },
        plannedProfile: "",
        performance: {
            registration: "", flightLevel: "", date: "", departure: "",
            destination: "", alternate: "", ETD: "", ETA: "", ETE: "",
            distance: "", averageWind: "", averageWC: "", TAS: "", stepClimb: "",
            isa: "", gs: "", trueCourse: "", magneticCourse: ""
        },
        fuel: {
            taxi: "", trip: "", contingency: "", alternate: "",
            reserve: "", required: "", extra: "", takeoff: "", ramp: ""
        },
        weight: {
            BOW: "", PAX: "", LOAD: "", ZFW: "", TOW: "", ELW: ""
        },
        route: "",
        waypoints: [],
        airportInfo: [],
        atcFlightPlan: {
            aircraft: "", equipment: "", ssr: "", departure: "",
            destination: "", alternate: "", route: "", remarks: ""
        },
        enrouteWinds: [],
        alternates: [],
        misc: {
            isa: "", gs: "", trueCourse: "", magneticCourse: ""
        }
    };
}

// =====================================================
// TEXT SEARCH VALUE LOOKUP (For unstructured text targets)
// =====================================================
function extractTextLabelValue($, labels) {
    let foundValue = "";
    const targetLabels = (Array.isArray(labels) ? labels : [labels]).map(l => l.toUpperCase());
    const bodyText = clean($("body").text());

    for (const label of targetLabels) {
        const escaped = label.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
        const regex = new RegExp("(?:^|\\s)" + escaped + "\\s*[:\\-]?\\s*([^\\n\\r]{1,50})", "i");
        const match = bodyText.match(regex);
        if (match) {
            foundValue = clean(match[1]);
            break;
        }
    }
    return foundValue;
}

// =====================================================
// CORE PARSER RUNTIME
// =====================================================
function parseHTML(html) {
    if (!html) throw new Error("HTML EMPTY");

    const $ = cheerio.load(html);
    const result = emptyResult();

    // 1️⃣ PARSE THE STRUCTURAL HEADER FOR META LOGS
    const rawTitleText = clean($("title").text()) || clean($("h1").first().text()) || "";
    result.header = rawTitleText || "ForeFlight Navlog";

    console.log("\n========================================");
    console.log("FOREFLIGHT SPECIFIC PARSER RUNNING");
    console.log("========================================");

    if (rawTitleText) {
        // Extract Departure & Destination: VABB — VOBG
        const routeMatch = rawTitleText.match(/^([A-Z]{4})\s*[\u2014\-]\s*([A-Z]{4})/i);
        if (routeMatch) {
            result.performance.departure = routeMatch[1];
            result.performance.destination = routeMatch[2];
        }

        // Extract Date: (Jul 16, 2026)
        const dateMatch = rawTitleText.match(/\(([^)]+\d{4})\)/);
        if (dateMatch) {
            result.performance.date = dateMatch[1];
        }

        // Extract Registration: in VTBNB
        const regMatch = rawTitleText.match(/in\s+([A-Z0-9\-]+)/i);
        if (regMatch) {
            result.performance.registration = regMatch[1];
        }

        // Extract Aircraft Type: (PRM1)
        const acMatch = rawTitleText.match(/\b([A-Z0-9]{4})\b(?!\s*IFR|\s*VFR)/i) || rawTitleText.match(/\(([A-Z0-9]{3,4})\)/g);
        if (acMatch) {
            // Pick the secondary matching parameter safely
            const potentialType = Array.isArray(acMatch) ? acMatch[acMatch.length - 1] : acMatch[1];
            result.atcFlightPlan.aircraft = potentialType.replace(/[()]/g, "").trim();
        }
    }

    // =====================================================
    // PERFORMANCE / TIME (Using verified native classes)
    // =====================================================
    result.performance.ETE         = clean($(".performance-metric.ete span").text() || $(".performance-metric.ete").text().replace(/ETE/i, ""));
    result.performance.distance    = clean($(".performance-metric.distance span").text() || $(".performance-metric.distance").text().replace(/DIST/i, ""));
    result.performance.averageWind = clean($(".performance-metric.avg-wind span").text() || $(".performance-metric.avg-wind").text().replace(/AVG WIND/i, ""));
    result.performance.ETD         = clean($(".performance-metric.etd span").text() || $(".performance-metric.etd").text().replace(/ETD/i, ""));
    result.performance.ETA         = clean($(".performance-metric.eta span").text() || $(".performance-metric.eta").text().replace(/ETA/i, ""));
    result.performance.flightLevel = clean($(".performance-metric.fl span").text() || $(".performance-metric.flight-level span").text());
    result.performance.averageWC   = clean($(".performance-metric.avg-wc span").text());
    result.performance.TAS         = clean($(".performance-metric.tas span").text());
    result.performance.stepClimb   = clean($(".performance-metric.step-climb span").text());

    // Fallback lookups for missing layout blocks
    if (!result.performance.flightLevel) result.performance.flightLevel = extractTextLabelValue($, ["FL", "Flight Level"]);
    if (!result.performance.TAS) result.performance.TAS = extractTextLabelValue($, ["TAS"]);
    if (!result.performance.stepClimb) result.performance.stepClimb = extractTextLabelValue($, ["STEP CLIMB", "Step Climb"]);
    if (!result.performance.averageWC) result.performance.averageWC = extractTextLabelValue($, ["AVG WC", "Average WC"]);
    
    // Map Alternate
    result.performance.alternate = extractTextLabelValue($, ["ALT1", "Alternate"]);

    // Synchronize flightSummary clone layout directly
    Object.keys(result.flightSummary).forEach(key => {
        if (result.performance[key] !== undefined) {
            result.flightSummary[key] = result.performance[key];
        }
    });

    // =====================================================
    // FUEL PARSER (Direct Target Matrix + Structural Text Fallback)
    // =====================================================
    result.fuel.ramp    = clean($(".performance-metric.block-fuel span").text() || $(".performance-metric.ramp-fuel span").text());
    result.fuel.taxi    = clean($(".performance-metric.taxi-fuel span").text());
    result.fuel.trip    = clean($(".performance-metric.flight-fuel span").text() || $(".performance-metric.trip-fuel span").text());
    result.fuel.reserve = clean($(".performance-metric.reserve-fuel span").text());
    
    // Fallback extraction for classes missing from individual raw HTML schemas
    if (!result.fuel.ramp) result.fuel.ramp = extractTextLabelValue($, ["Ramp Fuel", "Ramp", "Block Fuel"]);
    if (!result.fuel.taxi) result.fuel.taxi = extractTextLabelValue($, ["Taxi Fuel", "Taxi"]);
    if (!result.fuel.trip) result.fuel.trip = extractTextLabelValue($, ["Trip Fuel", "Flight Fuel", "Trip"]);
    if (!result.fuel.reserve) result.fuel.reserve = extractTextLabelValue($, ["Reserve Fuel", "Final Reserve", "Reserve"]);
    
    result.fuel.contingency = extractTextLabelValue($, ["Contingency Fuel", "Contingency"]);
    result.fuel.alternate   = extractTextLabelValue($, ["Alternate Fuel", "Alternate"]);
    result.fuel.required    = extractTextLabelValue($, ["Required Fuel", "Required"]);
    result.fuel.takeoff     = extractTextLabelValue($, ["Takeoff Fuel", "T/O Fuel", "Takeoff"]);
    result.fuel.extra       = extractTextLabelValue($, ["Extra Fuel", "Extra"]);

    // =====================================================
    // WEIGHT PARSER (Direct Class Target Matrix)
    // =====================================================
    result.weight.TOW = clean($(".performance-metric.tow span").text() || $(".performance-metric.takeoff-weight span").text());
    result.weight.ELW = clean($(".performance-metric.elw span").text() || $(".performance-metric.landing-weight span").text());
    
    if (!result.weight.TOW) result.weight.TOW = extractTextLabelValue($, ["TOW", "Takeoff Weight"]);
    if (!result.weight.ELW) result.weight.ELW = extractTextLabelValue($, ["ELW", "Landing Weight", "Estimated Landing Weight"]);
    
    result.weight.BOW  = extractTextLabelValue($, ["BOW", "Basic Operating Weight"]);
    result.weight.PAX  = extractTextLabelValue($, ["PAX", "Passengers"]);
    result.weight.LOAD = extractTextLabelValue($, ["LOAD"]);
    result.weight.ZFW  = extractTextLabelValue($, ["ZFW", "Zero Fuel Weight"]);

    if (result.fuel.takeoff) result.weight["T/O Fuel"] = result.fuel.takeoff;

    // =====================================================
    // ROUTE PARSER (Section Selector Blueprint Match)
    // =====================================================
    result.route = clean($("section.route div").text());
    if (!result.route) {
        result.route = extractTextLabelValue($, ["ATC ROUTE", "PLANNED ROUTE", "ROUTE"]);
    }
    result.plannedProfile = result.route;

    // Map ATC Base Block
    result.atcFlightPlan = {
        aircraft:    result.atcFlightPlan.aircraft || extractTextLabelValue($, ["Aircraft"]),
        equipment:   extractTextLabelValue($, ["Equipment"]),
        ssr:         extractTextLabelValue($, ["SSR"]),
        departure:   result.performance.departure,
        destination: result.performance.destination,
        alternate:   result.performance.alternate,
        route:       result.route,
        remarks:     clean($(".atc-remarks, section.remarks div, .remarks-block").text()) || extractTextLabelValue($, ["RMK/", "RMK", "Remarks"])
    };

    // =====================================================
    // 2️⃣ WAYPOINT PARSER (Fixed Class & 19-Column Index Matrix)
    // =====================================================
    const targetWaypoints = [];
    $("table.waypoint, .waypoint-table table, table").each((_, table) => {
        // Verify we are dealing with the correct structural tracking log matrix
        const sampleText = clean($(table).text()).toUpperCase();
        if (!sampleText.includes("WAYPOINT") || !sampleText.includes("REM FUEL")) return;

        $(table).find("tr").each((_, tr) => {
            const cells = [];
            $(tr).find("td, th").each((_, cell) => { cells.push(clean($(cell).text())); });

            if (cells.length < 12) return; // Discard partial block wrappers

            const flagText = cells.join(" ").toUpperCase();
            if (flagText.includes("WAYPOINT") || flagText.includes("IDENT") || flagText.includes("AIRWAY")) return;

            // Map data items using ForeFlight's strict 19-column table indices
            targetWaypoints.push({
                waypoint:           cells[0] || "",
                airway:             cells[1] || "",
                heading:            cells[2] || "", // HDG
                course:             cells[3] || "", // CRS
                flightLevel:        cells[4] || "", // ALT
                windDirectionSpeed: cells[6] || "", // DIR/SPD
                isa:                cells[7] || "", // ISA
                tas:                cells[8] || "", // TAS
                gs:                 cells[9] || "", // GS
                legDistance:        cells[10] || "", // LEG
                remainingDistance:  cells[11] || "", // REM
                fuelUsed:           cells[12] || "", // USED
                fuelRemaining:      cells[13] || "", // REM Fuel
                actualFuel:         cells[14] || "", // ACT Fuel
                legTimeRemaining:   cells[15] || "", // LEG Time
                ete:                cells[17] || "", // ETE
                eta:                cells[16] || "", // REM Time / ETA Cross link
                ata:                "",
            });
        });
    });
    result.waypoints = targetWaypoints.filter(row => row.waypoint !== "");

    // =====================================================
    // 3️⃣ AIRPORT PARSER (Dynamic Section Table Sniffer)
    // =====================================================
    const targetAirports = [];
    $("table").each((_, table) => {
        const headerText = clean($(table).find("tr").first().text()).toUpperCase();
        // Look for typical airport tracking frequency labels inside rows
        if (headerText.includes("ATIS") || headerText.includes("TOWER") || headerText.includes("ELEV")) {
            $(table).find("tr").each((_, tr) => {
                const cells = [];
                $(tr).find("td, th").each((_, td) => { cells.push(clean($(td).text())); });

                if (cells.length >= 4) {
                    const headingCheck = cells.join(" ").toUpperCase();
                    if (headingCheck.includes("ATIS") || headingCheck.includes("TOWER") || headingCheck.includes("FREQ")) return;

                    targetAirports.push({
                        airport:   cells[0] || "",
                        eta:       cells[1] || "",
                        atis:      cells[2] || "",
                        tower:     cells[3] || "",
                        clearance: cells[4] || "",
                        ground:    cells[5] || "",
                        elevation: cells[6] || "",
                        runway:    cells[7] || ""
                    });
                }
            });
        }
    });
    result.airportInfo = targetAirports.filter(row => row.airport !== "");

    // =====================================================
    // 4️⃣ WINDS PARSER (Dynamic Section Table Sniffer)
    // =====================================================
    const targetWinds = [];
    $("table").each((_, table) => {
        const headerText = clean($(table).text()).toUpperCase();
        // Sniff out altitude profile matrix maps
        if (headerText.includes("FL380") || headerText.includes("FL340") || headerText.includes("ENROUTE WINDS")) {
            $(table).find("tr").each((_, tr) => {
                const cells = [];
                $(tr).find("td, th").each((_, cell) => { cells.push(clean($(cell).text())); });

                if (cells.length >= 2) {
                    const headingCheck = cells.join(" ").toUpperCase();
                    if (headingCheck.includes("IDENT") || headingCheck.includes("FL380") || headingCheck.includes("ENROUTE")) return;

                    targetWinds.push({
                        ident: cells[0] || "",
                        fl380: cells[1] || "",
                        fl360: cells[2] || "",
                        fl340: cells[3] || "",
                        fl320: cells[4] || "",
                        fl300: cells[5] || ""
                    });
                }
            });
        }
    });
    result.enrouteWinds = targetWinds.filter(row => row.ident !== "" && row.ident.toUpperCase() !== "IDENT");

    // =====================================================
    // MISCELLANEOUS / LINKAGES
    // =====================================================
    result.misc.isa            = extractTextLabelValue($, ["ISA"]);
    result.misc.gs             = result.performance.gs || extractTextLabelValue($, ["GS", "Ground Speed"]);
    result.misc.trueCourse     = extractTextLabelValue($, ["True Course", "TC"]);
    result.misc.magneticCourse = extractTextLabelValue($, ["Magnetic Course", "MC"]);
    
    result.performance.isa = result.misc.isa;
    result.performance.gs = result.misc.gs;
    result.performance.trueCourse = result.misc.trueCourse;
    result.performance.magneticCourse = result.misc.magneticCourse;

    // Extract Alternate Routes
    $(".alternate-route, section.alternates div").each((_, el) => {
        const txt = clean($(el).text());
        if (txt) result.alternates.push({ route: txt });
    });

    // =====================================================
    // MANDATORY DIAGNOSTIC TELEMETRY DEBUG PRINT
    // =====================================================
    console.log("\n--- DEBUG: PERFORMANCE OBJECT ---");
    console.log(result.performance);
    console.log("\n--- DEBUG: FUEL OBJECT ---");
    console.log(result.fuel);
    console.log("\n--- DEBUG: WEIGHT OBJECT ---");
    console.log(result.weight);
    console.log("\n--- DEBUG: ROUTE EXTRACTION ---");
    console.log("Route:", result.route);
    console.log("\n--- DEBUG: RECORD MATRIX METRICS ---");
    console.log("Waypoints Parsed:   ", result.waypoints.length);
    console.log("Airport Info Rows:  ", result.airportInfo.length);
    console.log("Enroute Winds Rows: ", result.enrouteWinds.length);
    console.log("========================================");

    return result;
}

module.exports = parseHTML;