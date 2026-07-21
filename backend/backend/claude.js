// ======================================================
// FOREFLIGHT -> FORUM AVIATION OPS FPL TRANSFORMER
// ======================================================
// NOTE: This file is intentionally NOT calling the Anthropic API anymore.
//
// Why: the old version sent the whole parsed navlog (including every
// waypoint row) to Claude and asked it to retype the entire structure as
// JSON. That's a real risk for a flight-planning document - an LLM can
// drop, merge, or subtly reformat a row in a 20+ row table, and there is
// no way to catch that from the output alone. Now that htmlParser.js pulls
// data from ForeFlight's real, labeled DOM structure, there's no more
// ambiguous "which field is this" guessing for an LLM to resolve - it's a
// deterministic field-by-field copy. Doing it in plain JS is faster, free,
// and can't hallucinate a fuel or weight number.
//
// The exported function name/signature (`convertWithClaude(masterJson)`)
// is kept the same so server.js doesn't need to change.
// ======================================================

// ======================================================
// HELPERS
// ======================================================

function object(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function array(value) {
  return Array.isArray(value) ? value : [];
}

function first(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      return value;
    }
  }
  return "";
}

// Returns "" unless every argument is a valid number, otherwise the sum,
// rounded to the nearest whole unit (fuel/weight are always whole lbs/kg).
function sumIfComplete(...values) {
  const nums = [];
  for (const v of values) {
    if (v === undefined || v === null || String(v).trim() === "") continue;
    const n = Number(v);
    if (Number.isNaN(n)) return "";
    nums.push(n);
  }
  if (nums.length === 0) return "";
  return String(Math.round(nums.reduce((a, b) => a + b, 0)));
}

function subtractIfComplete(a, b) {
  if (a === undefined || a === null || String(a).trim() === "") return "";
  if (b === undefined || b === null || String(b).trim() === "") return "";
  const na = Number(a);
  const nb = Number(b);
  if (Number.isNaN(na) || Number.isNaN(nb)) return "";
  return String(Math.round(na - nb));
}

// ======================================================
// VALIDATE / SHAPE OUTPUT
// ======================================================

function validate(data) {
  data = object(data);

  data.page1 = object(data.page1);
  data.page1.header = object(data.page1.header);
  data.page1.flightInfo = object(data.page1.flightInfo);
  data.page1.time = object(data.page1.time);
  data.page1.fuel = object(data.page1.fuel);
  data.page1.weight = object(data.page1.weight);
  data.page1.misc = object(data.page1.misc);
  data.page1.operational = object(data.page1.operational);
  data.page1.alternates = array(data.page1.alternates);

  data.routes = object(data.routes);
  data.atcFlightPlan = object(data.atcFlightPlan);

  data.mainNavlog = array(data.mainNavlog);
  data.alternate1Navlog = array(data.alternate1Navlog);
  data.alternate2Navlog = array(data.alternate2Navlog);

  data.airportInformation = array(data.airportInformation);
  data.enrouteWindBands = array(data.enrouteWindBands);
  data.enrouteWinds = array(data.enrouteWinds);

  return data;
}

// ======================================================
// WAYPOINT ROW MAPPING (parser field names -> PDF field names)
// These are already aligned 1:1 with htmlParser.js output, so this is a
// pure passthrough - but it's an explicit copy so a future parser field
// rename can't silently break the PDF without a clear error here.
// ======================================================

function mapWaypointRow(row) {
  return {
    waypoint: row.waypoint || "",
    waypointDetail: row.waypointDetail || "",
    airway: row.airway || "",
    heading: row.heading || "",
    course: row.course || "",
    flightLevel: row.flightLevel || "",
    windComponent: row.windComponent || "",
    windDirectionSpeed: row.windDirectionSpeed || "",
    isa: row.isa || "",
    tas: row.tas || "",
    gs: row.gs || "",
    legDistance: row.legDistance || "",
    remainingDistance: row.remainingDistance || "",
    fuelUsed: row.fuelUsed || "",
    fuelRemaining: row.fuelRemaining || "",
    actualFuel: row.actualFuel || "",
    legTime: row.legTime || "",
    remainingTime: row.remainingTime || "",
    ete: row.ete || "",
    eta: row.eta || "",
    ata: row.ata || ""
  };
}

function mapAirportRow(row) {
  return {
    type: row.type || "",
    airport: row.airport || "",
    eta: row.eta || "",
    atis: row.atis || "",
    tower: row.tower || "",
    clearance: row.clearance || "",
    ground: row.ground || "",
    elevation: row.elevation || "",
    longestRunway: row.runway || "",
    runwayLength: row.runwayLength || ""
  };
}

// ======================================================
// MAIN CONVERSION FUNCTION
// ======================================================

async function convertWithClaude(masterJson) {
  console.log("🔧 Building Forum Aviation OPS FPL JSON (deterministic transform)...");

  const userInput = object(masterJson.userInput);
  const main = object(masterJson.mainRoute);
  const alt1 = object(masterJson.alternate1);
  const alt2 = object(masterJson.alternate2);

  const summary = object(main.summary);
  const fw = object(main.fuelWeights);

  const data = validate({});
  const page1 = data.page1;

  // -------------------- FLIGHT INFO --------------------

  page1.flightInfo.flight = first(userInput.callSign, summary.registration);
  page1.flightInfo.pic = first(userInput.pilotName, summary.pic);
  page1.flightInfo.fo = first(userInput.coPilotName);
  page1.flightInfo.registration = first(summary.registration, userInput.callSign);
  page1.flightInfo.departure = first(userInput.departure, main.departure);
  page1.flightInfo.destination = first(userInput.destination, main.destination);
  page1.flightInfo.flightLevel = first(userInput.flightLevel, summary.altitude);
  page1.flightInfo.date = ""; // ForeFlight navlog HTML does not include a flight date

  // ALT1 field lists the alternate airports (destinations of the alternate routes)
  const alt1Dest = first(alt1.destination, "");
  const alt2Dest = first(alt2.destination, "");
  page1.flightInfo.alternate1 = [alt1Dest, alt2Dest].filter(Boolean).join(",");

  // -------------------- HEADER --------------------

  page1.header.registration = first(summary.registration, userInput.callSign);
  page1.header.routeTitle = first(
    main.departure && main.destination ? `${main.departure} - ${main.destination}` : "",
    main.route
  );

  // -------------------- TIME --------------------

  page1.time.etd = first(summary.etd);
  page1.time.eta = first(summary.eta);
  page1.time.etdLocal = "";
  page1.time.etaLocal = "";
  page1.time.stepClimb = ""; // not present in this ForeFlight export
  page1.time.plannedRouteDistance = summary.distance ? `${summary.distance}` : "";
  page1.time.averageWinds = ""; // not provided per-leg in this export
  page1.time.averageWindComponent = "";
  page1.time.tas = "";

  // -------------------- FUEL --------------------

  page1.fuel.taxi = fw.taxiFuel;
  page1.fuel.trip = fw.flightFuel;
  page1.fuel.tripTime = summary.ete;
  page1.fuel.tripDistance = summary.distance ? `${summary.distance}` : "";
  page1.fuel.contingency = ""; // ForeFlight does not break this out separately
  page1.fuel.alternate = fw.alternateFuel;
  page1.fuel.finalReserve = fw.reserveFuel;
  page1.fuel.required = sumIfComplete(fw.taxiFuel, fw.flightFuel, fw.alternateFuel, fw.reserveFuel);
  page1.fuel.extra = first(userInput.maxTripFuel, fw.extraFuel);
  page1.fuel.extraEndurance = first(userInput.endurance);
  page1.fuel.takeoff = subtractIfComplete(fw.blockFuel, fw.taxiFuel);
  page1.fuel.ramp = fw.blockFuel;

  // -------------------- WEIGHT --------------------

  page1.weight.basicOperatingWeight = subtractIfComplete(fw.zfw, fw.payload);
  page1.weight.pax = first(userInput.paxWeight, summary.soulsOnBoard);
  page1.weight.load = fw.payload;
  page1.weight.zeroFuelWeight = fw.zfw;
  page1.weight.takeoffFuel = page1.fuel.takeoff;
  page1.weight.takeoffWeight = fw.tow;
  page1.weight.estimatedLandingWeight = fw.elw;

  // -------------------- MISC --------------------

  page1.misc.plannedProfile = summary.profile;
  page1.misc.atcRoute = first(userInput.shortFPL, main.route);

  // -------------------- OPERATIONAL (left blank - filled in by hand in-flight) --------------------
  // page1.operational.* fields intentionally left empty; ForeFlight's export
  // has no post-flight actuals and we never invent them.

  // -------------------- ALTERNATES --------------------

  const buildAlternate = (name, alt) => {
    if (!alt || !alt.destination) return null;
    return {
      name,
      airport: alt.destination,
      route: alt.route || "",
      flightLevel: object(alt.summary).altitude || "",
      distance: object(alt.summary).distance ? `${object(alt.summary).distance}` : "",
      ete: object(alt.summary).ete || "",
      fuel: object(alt.fuelWeights).flightFuel || ""
    };
  };

  data.page1.alternates = [
    buildAlternate("ALT1", alt1),
    buildAlternate("ALT2", alt2)
  ].filter(Boolean);

  // -------------------- ROUTES --------------------

  data.routes.mainRoute = main.route || "";
  data.routes.alternate1Route = alt1.route || "";
  data.routes.alternate2Route = alt2.route || "";

  // -------------------- ATC FLIGHT PLAN --------------------
  // No raw ICAO FPL string exists in the ForeFlight export. We populate the
  // fields we can genuinely derive and leave equipment/SSR/PBN blank rather
  // than invent aviation values that could end up in a real flight plan.

  data.atcFlightPlan = {
    title: `ATC FLIGHT PLAN ${first(main.departure)} to ${first(main.destination)}`,
    flightPlanText: first(userInput.shortFPL, ""),
    flightRules: "",
    flightType: "",
    aircraftNumber: first(summary.registration),
    aircraftType: first(summary.aircraftType),
    wakeTurbulence: "",
    equipment: "",
    surveillance: "",
    departure: first(main.departure),
    departureTime: first(summary.etd),
    speed: "",
    level: first(userInput.flightLevel, summary.altitude),
    route: first(main.route),
    destination: first(main.destination),
    totalEET: first(summary.ete),
    alternate1: alt1Dest,
    alternate2: alt2Dest,
    otherInformation: ""
  };

  // -------------------- NAVLOGS --------------------

  data.mainNavlog = array(main.waypoints).map(mapWaypointRow);
  data.alternate1Navlog = array(alt1.waypoints).map(mapWaypointRow);
  data.alternate2Navlog = array(alt2.waypoints).map(mapWaypointRow);

  // -------------------- AIRPORT INFORMATION --------------------
  // Combine main + alternates, de-duplicating by airport code so the same
  // field (e.g. shared destination/alternate) isn't listed twice.

  const seenAirports = new Set();
  const airportRows = [];
  [main, alt1, alt2].forEach((leg) => {
    array(leg.airportInfo).forEach((row) => {
      const key = `${row.type}-${row.airport}`;
      if (seenAirports.has(key)) return;
      seenAirports.add(key);
      airportRows.push(mapAirportRow(row));
    });
  });
  data.airportInformation = airportRows;

  // -------------------- ENROUTE WINDS --------------------
  // Direct passthrough from the parser - band count is dynamic per aircraft
  // profile (e.g. FL70-150 for a turboprop vs FL300-380 for a jet), so the
  // PDF generator renders whatever bands are actually present.

  data.enrouteWindBands = array(object(main.enrouteWinds).bands);
  data.enrouteWinds = array(object(main.enrouteWinds).rows);

  console.log("✅ Transform complete");
  console.log(`   Main navlog: ${data.mainNavlog.length} waypoints`);
  console.log(`   Alt1 navlog: ${data.alternate1Navlog.length} waypoints`);
  console.log(`   Alt2 navlog: ${data.alternate2Navlog.length} waypoints`);
  console.log(`   Airports: ${data.airportInformation.length}`);
  console.log(`   Wind bands: ${data.enrouteWindBands.length}, rows: ${data.enrouteWinds.length}`);

  return data;
}

module.exports = convertWithClaude;