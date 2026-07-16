require("dotenv").config();

const Anthropic = require("@anthropic-ai/sdk");


// ======================================================
// CLAUDE CLIENT
// ======================================================

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY
});


// ======================================================
// EXTRACT JSON FROM CLAUDE
// ======================================================

function extractJSON(output) {

  const cleaned = String(output)
    .replace(/```json/gi, "")
    .replace(/```/g, "")
    .trim();

  const start = cleaned.indexOf("{");
  const end = cleaned.lastIndexOf("}");

  if (start === -1 || end === -1) {
    throw new Error("Claude did not return JSON.");
  }

  return JSON.parse(
    cleaned.substring(start, end + 1)
  );

}



// ======================================================
// ENSURE OBJECT
// ======================================================

function object(value) {

  if (
    value &&
    typeof value === "object" &&
    !Array.isArray(value)
  ) {
    return value;
  }

  return {};

}



// ======================================================
// ENSURE ARRAY
// ======================================================

function array(value) {

  return Array.isArray(value)
    ? value
    : [];

}



// ======================================================
// RETURN FIRST NON EMPTY VALUE
// ======================================================

function first(...values) {

  for (const value of values) {

    if (
      value !== undefined &&
      value !== null &&
      String(value).trim() !== ""
    ) {
      return value;
    }

  }

  return "";

}



// ======================================================
// VALIDATE CLAUDE OUTPUT
// ======================================================

function validate(data) {

  data = object(data);

  data.page1 = object(data.page1);

  data.page1.header =
    object(data.page1.header);

  data.page1.flightInfo =
    object(data.page1.flightInfo);

  data.page1.time =
    object(data.page1.time);

  data.page1.fuel =
    object(data.page1.fuel);

  data.page1.weight =
    object(data.page1.weight);

  data.page1.misc =
    object(data.page1.misc);

  data.page1.operational =
    object(data.page1.operational);

  data.page1.alternates =
    array(data.page1.alternates);

  data.routes =
    object(data.routes);

  data.atcFlightPlan =
    object(data.atcFlightPlan);

  data.mainNavlog =
    array(data.mainNavlog);

  data.alternate1Navlog =
    array(data.alternate1Navlog);

  data.alternate2Navlog =
    array(data.alternate2Navlog);

  data.airportInformation =
    array(data.airportInformation);

  data.enrouteWinds =
    array(data.enrouteWinds);

  return data;

}
// ======================================================
// MAIN CONVERSION FUNCTION
// ======================================================

async function convertWithClaude(masterJson) {

  console.log("🤖 Claude processing...");

  const prompt = `

You are a senior airline dispatcher and operational flight planner.

You will receive a MASTER JSON extracted from ForeFlight Navlog HTML.

Your job is to convert it into COMPLETE Forum Aviation OPS FPL JSON.

==================================================
IMPORTANT RULES
==================================================

1. Return ONLY VALID JSON.
2. No markdown.
3. No explanation.
4. Never invent aviation values.
5. Preserve every waypoint.
6. Never summarize tables.
7. Copy every value that exists.
8. If information is missing, return an empty string.
9. Match fields by MEANING, not exact key names.
10. Keep aviation units exactly as given.

==================================================
USER INPUT
==================================================

Always use these values from userInput whenever available.

callSign

pilotName

coPilotName

departure

destination

flightLevel

paxWeight

maxTripFuel

endurance

shortFPL

Map them to

page1.flightInfo.flight

page1.flightInfo.pic

page1.flightInfo.fo

page1.flightInfo.departure

page1.flightInfo.destination

page1.flightInfo.flightLevel

page1.weight.pax

page1.fuel.extra

page1.fuel.extraEndurance

page1.misc.atcRoute

==================================================
FORELIGHT DATA
==================================================

Search ALL keys inside

mainRoute.performance

mainRoute.fuel

mainRoute.weight

mainRoute.airportInfo

mainRoute.header

mainRoute.route

Never depend on one exact key name.

Examples

Taxi Fuel

Taxi

Taxi Burn

TX Fuel

→ page1.fuel.taxi

Trip Fuel

Flight Fuel

Enroute Fuel

→ page1.fuel.trip

Ramp Fuel

Block Fuel

→ page1.fuel.ramp

Reserve Fuel

Final Reserve

→ page1.fuel.finalReserve

Alternate Fuel

→ page1.fuel.alternate

Extra Fuel

→ page1.fuel.extra

Distance

Route Distance

Planned Distance

→ page1.time.plannedRouteDistance

Average Wind

Avg Wind

→ page1.time.averageWinds

ETD

Departure Time

→ page1.time.etd

ETA

Arrival Time

→ page1.time.eta

Registration

Aircraft Registration

Tail Number

→ page1.header.registration

→ page1.flightInfo.registration

TOW

Takeoff Weight

→ page1.weight.takeoffWeight

ELW

Landing Weight

LAW

→ page1.weight.estimatedLandingWeight

==================================================
WAYPOINTS
==================================================

Convert EVERY waypoint.

Never delete rows.

Never merge rows.

Copy exactly.

Map

Waypoint

Fix

Identifier

→ waypoint

Airway

→ airway

Heading

HDG

→ heading

Course

CRS

→ course

Flight Level

Altitude

FL

→ flightLevel

Wind

→ windDirectionSpeed

Temperature

ISA

→ isa

TAS

→ tas

Ground Speed

GS

→ gs

Leg Distance

→ legDistance

Remaining Distance

→ remainingDistance

Fuel Used

→ fuelUsed

Fuel Remaining

→ fuelRemaining

ETE

→ ete

Time Remaining

→ legTimeRemaining

ETA

→ eta

ATA

→ ata

Actual Fuel

→ actualFuel

Main Route

→ mainNavlog

Alternate 1

→ alternate1Navlog

Alternate 2

→ alternate2Navlog

==================================================
==================================================
FUEL CALCULATIONS
==================================================

Only calculate when enough information exists.

Never guess.

Calculate if possible

Taxi Fuel

Trip Fuel

Contingency Fuel

Alternate Fuel

Final Reserve Fuel

Required Fuel

Takeoff Fuel

Ramp Fuel

Extra Fuel

Remaining Fuel

Required Endurance

Takeoff Endurance

Ramp Endurance

==================================================
WEIGHT CALCULATIONS
==================================================

Calculate only if source values exist.

Basic Operating Weight

Payload

Zero Fuel Weight

Takeoff Weight

Estimated Landing Weight

==================================================
AIRPORT INFORMATION
==================================================

Extract airport information whenever available.

Airport

ETA

ATIS

Ground

Tower

Clearance

Elevation

Longest Runway

Runway Length

Populate

airportInformation[]

==================================================
ATC FLIGHT PLAN
==================================================

Populate

title

flightPlanText

flightRules

flightType

aircraftNumber

aircraftType

wakeTurbulence

equipment

surveillance

departure

departureTime

speed

level

route

destination

totalEET

alternate1

alternate2

otherInformation

==================================================
ENROUTE WINDS
==================================================

Populate

identifier

FL300

FL320

FL340

FL360

FL380

Wind

Temperature

==================================================
RETURN THIS JSON STRUCTURE

{

"page1":{

"header":{},

"flightInfo":{},

"time":{},

"fuel":{},

"weight":{},

"misc":{},

"operational":{},

"alternates":[]

},

"routes":{},

"mainNavlog":[],

"alternate1Navlog":[],

"alternate2Navlog":[],

"airportInformation":[],

"atcFlightPlan":{},

"enrouteWinds":[]

}

MASTER JSON

${JSON.stringify(masterJson)}

`;
// ======================================================
// SEND TO CLAUDE
// ======================================================

  let output = "";

  const stream = anthropic.messages.stream({

    model:
      process.env.CLAUDE_MODEL ||
      "claude-sonnet-4-5",

    max_tokens: 24000,

    temperature: 0,

    messages: [
      {
        role: "user",
        content: prompt
      }
    ]

  });

  for await (const event of stream) {

    if (
      event.type === "content_block_delta"
    ) {

      output +=
        event.delta.text || "";

    }

  }

  console.log("✅ Claude completed");

  const finalJson =
    extractJSON(output);

  const data =
    validate(finalJson);
    // ======================================================
// AUTO COMPLETE MISSING VALUES
// ======================================================

const page1 = data.page1;

page1.header ||= {};
page1.flightInfo ||= {};
page1.time ||= {};
page1.fuel ||= {};
page1.weight ||= {};
page1.misc ||= {};
page1.operational ||= {};
page1.alternates ||= [];

const perf = masterJson.mainRoute?.performance || {};
const fuel = masterJson.mainRoute?.fuel || {};
const weight = masterJson.mainRoute?.weight || {};

page1.flightInfo.flight =
  first(
    page1.flightInfo.flight,
    masterJson.userInput.callSign
  );

page1.flightInfo.pic =
  first(
    page1.flightInfo.pic,
    masterJson.userInput.pilotName
  );

page1.flightInfo.fo =
  first(
    page1.flightInfo.fo,
    masterJson.userInput.coPilotName
  );

page1.flightInfo.departure =
  first(
    page1.flightInfo.departure,
    masterJson.userInput.departure
  );

page1.flightInfo.destination =
  first(
    page1.flightInfo.destination,
    masterJson.userInput.destination
  );

page1.flightInfo.flightLevel =
  first(
    page1.flightInfo.flightLevel,
    masterJson.userInput.flightLevel
  );

page1.header.routeTitle =
  first(
    page1.header.routeTitle,
    masterJson.mainRoute.route,
    masterJson.mainRoute.header
  );

page1.routes ||= {};

data.routes.mainRoute =
  first(
    data.routes.mainRoute,
    masterJson.mainRoute.route
  );

page1.weight.pax =
  first(
    page1.weight.pax,
    masterJson.userInput.paxWeight
  );

page1.fuel.extra =
  first(
    page1.fuel.extra,
    masterJson.userInput.maxTripFuel
  );

page1.fuel.extraEndurance =
  first(
    page1.fuel.extraEndurance,
    masterJson.userInput.endurance
  );

page1.misc.atcRoute =
  first(
    page1.misc.atcRoute,
    masterJson.userInput.shortFPL,
    masterJson.mainRoute.route
  );

page1.time.etd =
  first(
    page1.time.etd,
    perf.ETD,
    perf.etd
  );

page1.time.eta =
  first(
    page1.time.eta,
    perf.ETA,
    perf.eta
  );

page1.time.plannedRouteDistance =
  first(
    page1.time.plannedRouteDistance,
    perf.Distance,
    perf.distance
  );

page1.fuel.trip =
  first(
    page1.fuel.trip,
    fuel.trip,
    perf["Trip Fuel"],
    perf["Flight Fuel"]
  );

page1.fuel.taxi =
  first(
    page1.fuel.taxi,
    fuel.taxi,
    perf["Taxi Fuel"]
  );

page1.fuel.ramp =
  first(
    page1.fuel.ramp,
    fuel.ramp,
    perf["Block Fuel"]
  );

page1.fuel.finalReserve =
  first(
    page1.fuel.finalReserve,
    perf["Reserve Fuel"]
  );

page1.weight.takeoffWeight =
  first(
    page1.weight.takeoffWeight,
    weight.TOW,
    perf.TOW
  );

page1.weight.estimatedLandingWeight =
  first(
    page1.weight.estimatedLandingWeight,
    weight.ELW,
    perf.ELW
  );

// ======================================================
// RETURN
// ======================================================

return data;

}

// ======================================================
// EXPORT
// ======================================================

module.exports = convertWithClaude;