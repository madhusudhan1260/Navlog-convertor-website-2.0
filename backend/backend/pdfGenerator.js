const PDFDocument = require("pdfkit");
const fs = require("fs");
const path = require("path");

const OUTPUT_DIRECTORY = path.join(
  __dirname,
  "generated"
);

const PAGE = {
  left: 58,
  right: 554,
  top: 32,
  bottom: 760
};

function value(input) {
  if (input === null || input === undefined) {
    return "";
  }

  return String(input);
}

function field(object, key) {
  return value(object?.[key]);
}

function write(
  doc,
  text,
  x,
  y,
  width,
  options = {}
) {
  doc
    .font(options.bold ? "Times-Bold" : "Times-Roman")
    .fontSize(options.size || 8)
    .text(value(text), x, y, {
      width,
      align: options.align || "left",
      lineBreak: options.lineBreak !== false
    });
}

function line(doc, x1, y1, x2, y2, width = 0.5) {
  doc
    .lineWidth(width)
    .moveTo(x1, y1)
    .lineTo(x2, y2)
    .stroke();
}

function box(doc, x, y, width, height) {
  doc
    .lineWidth(0.5)
    .rect(x, y, width, height)
    .stroke();
}

function routeHeader(doc, title, registration) {
  write(
    doc,
    `${value(title)}   ${value(registration)}`,
    330,
    19,
    220,
    {
      size: 8,
      align: "right"
    }
  );
}

function sectionHeading(
  doc,
  title,
  x,
  y,
  width
) {
  write(
    doc,
    `--------------- ${title} ---------------`,
    x,
    y,
    width,
    {
      size: 8,
      align: "center"
    }
  );
}

function labelledValue(
  doc,
  label,
  data,
  x,
  y,
  labelWidth = 76,
  totalWidth = 220
) {
  write(doc, label, x, y, labelWidth, {
    size: 8
  });

  write(
    doc,
    ":",
    x + labelWidth,
    y,
    8,
    { size: 8 }
  );

  write(
    doc,
    data,
    x + labelWidth + 14,
    y,
    totalWidth - labelWidth - 14,
    { size: 8 }
  );
}

function drawPageOne(doc, data) {
  const page = data.page1 || {};
  const header = page.header || {};
  const flight = page.flightInfo || {};
  const time = page.time || {};
  const fuel = page.fuel || {};
  const weight = page.weight || {};
  const misc = page.misc || {};
  const operational = page.operational || {};
  const alternates = page.alternates || [];

  routeHeader(
    doc,
    header.routeTitle,
    header.registration
  );

  box(doc, PAGE.left, 32, 496, 728);

  labelledValue(
    doc,
    "FLIGHT",
    flight.flight,
    73,
    46,
    52,
    150
  );

  labelledValue(
    doc,
    "PIC",
    flight.pic,
    202,
    46,
    28,
    175
  );

  labelledValue(
    doc,
    "DATE",
    flight.date,
    73,
    61,
    52,
    150
  );

  labelledValue(
    doc,
    "F/O",
    flight.fo,
    202,
    61,
    28,
    175
  );

  write(
    doc,
    "COMMANDER SIGN :",
    350,
    61,
    100,
    { size: 8 }
  );

  line(doc, 437, 69, 520, 69);

  sectionHeading(
    doc,
    "FLIGHT INFO",
    72,
    78,
    230
  );

  sectionHeading(
    doc,
    "TIME",
    305,
    78,
    230
  );

  const flightRows = [
    ["REG", flight.registration],
    ["FL", flight.flightLevel],
    ["FROM", flight.departure],
    ["TO", flight.destination],
    ["ALT1", flight.alternate1]
  ];

  flightRows.forEach((row, index) => {
    labelledValue(
      doc,
      row[0],
      row[1],
      73,
      108 + index * 14,
      70,
      210
    );
  });

  write(
    doc,
    `ETD : ${field(time, "etd")} (IST: ${field(time, "etdLocal")})`,
    310,
    96,
    120,
    { size: 8 }
  );

  write(
    doc,
    `ETA : ${field(time, "eta")} (IST: ${field(time, "etaLocal")})`,
    425,
    96,
    120,
    { size: 8 }
  );

  const timeRows = [
    ["STEP CLIMB", time.stepClimb],
    [
      "PLND ROUTE",
      time.plannedRouteDistance
    ],
    ["AVG WINDS", time.averageWinds],
    [
      "AVG.WC",
      time.averageWindComponent
    ],
    ["TAS", time.tas]
  ];

  timeRows.forEach((row, index) => {
    labelledValue(
      doc,
      row[0],
      row[1],
      310,
      119 + index * 14,
      88,
      220
    );
  });

  sectionHeading(
    doc,
    "FUEL",
    72,
    194,
    230
  );

  sectionHeading(
    doc,
    "WEIGHT",
    305,
    194,
    230
  );

  const fuelRows = [
    ["TAXI", fuel.taxi, "", ""],
    [
      "TRIP",
      fuel.trip,
      fuel.tripTime,
      fuel.tripDistance
    ],
    [
      "CONTINGENCY",
      fuel.contingency,
      fuel.contingencyTime,
      ""
    ],
    [
      "ALT1",
      fuel.alternate,
      fuel.alternateTime,
      fuel.alternateDistance
    ],
    [
      "FRES",
      fuel.finalReserve,
      fuel.finalReserveTime,
      ""
    ],
    [
      "REQ",
      fuel.required,
      fuel.requiredEndurance,
      ""
    ],
    [
      "EXTRA",
      fuel.extra,
      fuel.extraEndurance,
      ""
    ],
    [
      "T/O FUEL",
      fuel.takeoff,
      fuel.takeoffEndurance,
      ""
    ],
    [
      "RAMP",
      fuel.ramp,
      fuel.rampEndurance,
      ""
    ]
  ];

  fuelRows.forEach((row, index) => {
    const y = 215 + index * 14;

    labelledValue(
      doc,
      row[0],
      row[1],
      73,
      y,
      85,
      150
    );

    write(doc, row[2], 184, y, 35, {
      size: 8
    });

    write(doc, row[3], 225, y, 55, {
      size: 8
    });
  });

  const weightRows = [
    [
      "BOW",
      weight.basicOperatingWeight
    ],
    ["PAX", weight.pax],
    ["LOAD", weight.load],
    ["ZFW", weight.zeroFuelWeight],
    ["T/O FUEL", weight.takeoffFuel],
    ["TOW", weight.takeoffWeight],
    [
      "ELW",
      weight.estimatedLandingWeight
    ]
  ];

  weightRows.forEach((row, index) => {
    const y = 215 + index * 14;

    labelledValue(
      doc,
      row[0],
      row[1],
      310,
      y,
      55,
      145
    );

    line(doc, 455, y + 9, 505, y + 9);
  });

  sectionHeading(
    doc,
    "MISC",
    72,
    332,
    230
  );

  labelledValue(
    doc,
    "PLN PROFILE",
    misc.plannedProfile,
    73,
    351,
    86,
    455
  );

  line(doc, 70, 374, 542, 374, 1);

  labelledValue(
    doc,
    "ATC ROUTE",
    misc.atcRoute,
    73,
    378,
    70,
    455
  );

  line(doc, 70, 400, 542, 400, 1);

  labelledValue(
    doc,
    "DEPARTURE ATIS",
    operational.departureAtis,
    73,
    404,
    95,
    455
  );

  line(doc, 70, 449, 542, 449, 1);

  labelledValue(
    doc,
    "DEP CLEARANCE",
    operational.departureClearance,
    73,
    454,
    95,
    455
  );

  line(doc, 70, 497, 542, 497, 1);

  labelledValue(
    doc,
    "ARRIVAL ATIS",
    operational.arrivalAtis,
    73,
    502,
    95,
    455
  );

  line(doc, 70, 545, 542, 545, 1);

  const operationColumns = [
    [
      ["CHOCKS ON", operational.chocksOn],
      ["CHOCKS OFF", operational.chocksOff],
      ["BLOCK TIME", operational.blockTime]
    ],
    [
      ["TAKE OFF", operational.takeoff],
      ["LANDING", operational.landing],
      ["AIR TIME", operational.airTime]
    ],
    [
      ["T/O FUEL", operational.takeoffFuel],
      ["LDG FUEL", operational.landingFuel],
      ["F USED", operational.fuelUsed]
    ],
    [
      ["LDWGT", operational.landingWeight],
      ["LDA", operational.lda],
      ["BFLD", operational.bfld]
    ]
  ];

  operationColumns.forEach(
    (column, columnIndex) => {
      const x = 73 + columnIndex * 118;

      column.forEach((row, rowIndex) => {
        const y = 551 + rowIndex * 15;

        write(doc, row[0], x, y, 62, {
          size: 8
        });

        line(
          doc,
          x + 58,
          y + 9,
          x + 106,
          y + 9
        );

        if (row[1]) {
          write(
            doc,
            row[1],
            x + 61,
            y,
            44,
            { size: 8 }
          );
        }
      });
    }
  );

  write(doc, "RVSM CHECKS", 73, 608, 80, {
    size: 8
  });

  write(doc, "TIME (UTC)", 160, 608, 80, {
    size: 8
  });

  write(doc, "ALT1", 232, 608, 50, {
    size: 8
  });

  write(doc, "ALT2", 298, 608, 50, {
    size: 8
  });

  ["GROUND", "PRE-RVSM CHECK", "LEVEL OFF"].forEach(
    (label, index) => {
      const y = 624 + index * 14;

      write(doc, label, 73, y, 90, {
        size: 8
      });

      line(doc, 160, y + 9, 210, y + 9);
      line(doc, 232, y + 9, 282, y + 9);
      line(doc, 298, y + 9, 348, y + 9);
    }
  );

  alternates.slice(0, 2).forEach(
    (alternate, index) => {
      const y = 678 + index * 28;

      write(
        doc,
        alternate.name || `ALT${index + 1}`,
        73,
        y,
        42,
        { size: 8 }
      );

      labelledValue(
        doc,
        "",
        alternate.airport,
        115,
        y,
        1,
        85
      );

      write(
        doc,
        "Route",
        187,
        y,
        35,
        { size: 8 }
      );

      labelledValue(
        doc,
        "",
        alternate.route,
        221,
        y,
        1,
        115
      );

      write(
        doc,
        "FL",
        73,
        y + 14,
        20,
        { size: 8 }
      );

      labelledValue(
        doc,
        "",
        alternate.flightLevel,
        93,
        y + 14,
        1,
        70
      );

      write(
        doc,
        "DIST",
        187,
        y + 14,
        30,
        { size: 8 }
      );

      labelledValue(
        doc,
        "",
        alternate.distance,
        221,
        y + 14,
        1,
        75
      );

      write(
        doc,
        `ETE : ${field(alternate, "ete")}`,
        302,
        y + 14,
        100,
        { size: 8 }
      );

      write(
        doc,
        `FUEL : ${field(alternate, "fuel")}`,
        410,
        y + 14,
        120,
        { size: 8 }
      );
    }
  );
}

const NAV_COLUMNS = [
  ["waypoint", "WAYPOINT\nAIRWAY", 94],
  ["heading", "HDG\nCRS", 30],
  ["flightLevel", "FL", 37],
  [
    "windDirectionSpeed",
    "WIND\nDIR/SPD\nCMP",
    49
  ],
  ["isa", "ISA", 25],
  ["tas", "SPD KT\nTAS\nGS", 32],
  ["legDistance", "DIST NM\nLEG\nREM", 37],
  ["fuelUsed", "FUEL LB\nUSED\nREM", 39],
  ["ete", "TIME\nETE", 28],
  [
    "legTimeRemaining",
    "LEG\nREM",
    30
  ],
  ["eta", "ETA\nATA", 36],
  ["actualFuel", "ACTUAL FUEL", 61]
];

function combinedRowValue(row, key) {
  const mappings = {
    waypoint: [
      row.waypoint,
      row.airway
    ],
    heading: [
      row.heading,
      row.course
    ],
    windDirectionSpeed: [
      row.windDirectionSpeed,
      row.windComponent
    ],
    tas: [row.tas, row.gs],
    legDistance: [
      row.legDistance,
      row.remainingDistance
    ],
    fuelUsed: [
      row.fuelUsed,
      row.fuelRemaining
    ],
    // LEG/REM *time* columns (distinct from the LEG/REM *distance* columns above)
    legTimeRemaining: [
      row.legTime,
      row.remainingTime
    ],
    eta: [row.eta, row.ata]
  };

  if (mappings[key]) {
    return mappings[key]
      .map(value)
      .filter(Boolean)
      .join("\n");
  }

  return value(row[key]);
}

function drawNavlogHeader(doc, y) {
  let x = PAGE.left;

  NAV_COLUMNS.forEach(
    ([, title, width]) => {
      box(doc, x, y, width, 52);

      write(doc, title, x + 2, y + 12, width - 4, {
        size: 6.5,
        align: "center"
      });

      x += width;
    }
  );

  return y + 52;
}

function drawNavlogRows(
  doc,
  rows,
  startY,
  maximumY
) {
  let y = startY;

  for (const row of rows || []) {
    const height = 31;

    if (y + height > maximumY) {
      return {
        y,
        remaining: rows.slice(
          rows.indexOf(row)
        )
      };
    }

    let x = PAGE.left;

    NAV_COLUMNS.forEach(
      ([key, , width]) => {
        box(doc, x, y, width, height);

        write(
          doc,
          combinedRowValue(row, key),
          x + 2,
          y + 5,
          width - 4,
          {
            size: 6.5,
            align:
              key === "waypoint"
                ? "left"
                : "center"
          }
        );

        x += width;
      }
    );

    y += height;
  }

  return {
    y,
    remaining: []
  };
}

function drawNavlogTitle(doc, title, y) {
  write(doc, title, PAGE.left, y, 496, {
    size: 8
  });

  line(doc, PAGE.left, y + 17, PAGE.right, y + 17);

  return y + 22;
}

function drawPagesTwoAndThree(doc, data) {
  const title =
    data.page1?.header?.routeTitle || "";

  const registration =
    data.page1?.header?.registration || "";

  doc.addPage();
  routeHeader(doc, title, registration);
  box(doc, PAGE.left, 32, 496, 728);

  let y = drawNavlogHeader(doc, 32);

  const mainResult = drawNavlogRows(
    doc,
    data.mainNavlog || [],
    y,
    430
  );

  y = mainResult.y + 12;

  y = drawNavlogTitle(
    doc,
    `Alternate route for ${
      data.page1?.flightInfo?.alternate1 || ""
    }     Route ${
      data.routes?.alternate1Route || ""
    }`,
    y
  );

  const alternateResult = drawNavlogRows(
    doc,
    data.alternate1Navlog || [],
    y,
    744
  );

  doc.addPage();
  routeHeader(doc, title, registration);
  box(doc, PAGE.left, 32, 496, 728);

  y = drawNavlogHeader(doc, 32);

  const remainingRows = [
    ...mainResult.remaining,
    ...alternateResult.remaining,
    ...(data.alternate2Navlog || [])
  ];

  const continuation = drawNavlogRows(
    doc,
    remainingRows,
    y,
    250
  );

  y = continuation.y + 34;

  write(
    doc,
    "AIRPORT INFO",
    PAGE.left,
    y,
    150,
    { size: 8 }
  );

  y += 17;

  const airportColumns = [
    ["type", "", 44],
    ["airport", "Airport", 50],
    ["eta", "ETA", 44],
    ["atis", "WX", 47],
    ["tower", "TWR/CTAF", 83],
    ["clearance", "CLR", 63],
    ["ground", "GND", 45],
    ["elevation", "ELEV", 46],
    ["longestRunway", "LONGEST RWY", 99]
  ];

  let x = PAGE.left;

  airportColumns.forEach(
    ([, heading, width]) => {
      box(doc, x, y, width, 21);

      write(
        doc,
        heading,
        x + 2,
        y + 7,
        width - 4,
        {
          size: 6.5,
          align: "center"
        }
      );

      x += width;
    }
  );

  y += 21;

  (data.airportInformation || []).forEach(
    (airport) => {
      x = PAGE.left;

      airportColumns.forEach(
        ([key, , width]) => {
          box(doc, x, y, width, 21);

          let airportValue = airport[key];

          if (key === "longestRunway") {
            airportValue = [
              airport.longestRunway,
              airport.runwayLength
            ]
              .filter(Boolean)
              .join("  ");
          }

          write(
            doc,
            airportValue,
            x + 2,
            y + 7,
            width - 4,
            {
              size: 6.5,
              align: "center"
            }
          );

          x += width;
        }
      );

      y += 21;
    }
  );
}

function drawPageFour(doc, data) {
  const title =
    data.page1?.header?.routeTitle || "";

  const registration =
    data.page1?.header?.registration || "";

  const atc = data.atcFlightPlan || {};

  doc.addPage();

  routeHeader(doc, title, registration);
  box(doc, PAGE.left, 32, 496, 728);

  write(
    doc,
    atc.title ||
      `ATC FLIGHT PLAN ${field(atc, "departure")} to ${field(atc, "destination")}`,
    120,
    48,
    380,
    {
      size: 9,
      align: "center"
    }
  );

  write(
    doc,
    ".................................",
    160,
    62,
    300,
    {
      size: 8,
      align: "center"
    }
  );

  write(
    doc,
    atc.flightPlanText,
    69,
    80,
    474,
    {
      size: 7
    }
  );

  write(
    doc,
    "ENROUTE WINDS",
    180,
    182,
    250,
    {
      size: 8,
      align: "center"
    }
  );

  // -----------------------------------------------------
  // Enroute winds table - DYNAMIC band count.
  // ForeFlight's altitude/FL bands depend on the aircraft profile
  // (e.g. FL70-150 for a turboprop climbing to FL110, vs FL300-380
  // for a jet), so this is no longer hardcoded to a fixed FL range.
  // -----------------------------------------------------

  const bands = data.enrouteWindBands || [];
  const windRows = data.enrouteWinds || [];

  const tableLeft = 69;
  const tableWidth = 474;
  const identWidth = 70;
  const bandCount = Math.max(bands.length, 1);
  const subColWidth = Math.max(
    26,
    Math.floor((tableWidth - identWidth) / (bandCount * 2))
  );

  // Shorten "FL 70 (ISA: 1°C)" -> "FL 70" for the column header
  const shortBandLabel = (label) =>
    (String(label || "").match(/^[^(]+/) || [""])[0].trim();

  let x = tableLeft;
  let y = 200;

  write(doc, "IDENT", x, y, identWidth, {
    size: 6.5,
    align: "left"
  });
  x += identWidth;

  bands.forEach((band) => {
    write(doc, `${shortBandLabel(band)}\nW/V`, x, y, subColWidth, {
      size: 6.5,
      align: "center"
    });
    write(doc, "TMP", x + subColWidth, y, subColWidth, {
      size: 6.5,
      align: "center"
    });
    x += subColWidth * 2;
  });

  y += 27;

  windRows.forEach((row) => {
    x = tableLeft;

    write(doc, row.identifier, x, y, identWidth, {
      size: 6.5,
      align: "left"
    });
    x += identWidth;

    (row.values || []).forEach((cell) => {
      write(doc, cell.wind, x, y, subColWidth, {
        size: 6.5,
        align: "center"
      });
      write(doc, cell.isa, x + subColWidth, y, subColWidth, {
        size: 6.5,
        align: "center"
      });
      x += subColWidth * 2;
    });

    y += 14;
  });

  write(
    doc,
    "**************   END OF THE REPORT   **************",
    150,
    719,
    320,
    {
      size: 8,
      bold: true,
      align: "center"
    }
  );

  write(
    doc,
    `COMPUTED DATE : ${new Date().toLocaleDateString("en-GB")}`,
    61,
    748,
    220,
    { size: 7 }
  );

  write(
    doc,
    `TIME : ${new Date().toLocaleTimeString("en-GB")} Asia/Kolkata`,
    350,
    748,
    195,
    {
      size: 7,
      align: "right"
    }
  );
}

function generatePDF(navlog) {
  return new Promise((resolve, reject) => {
    fs.mkdirSync(OUTPUT_DIRECTORY, {
      recursive: true
    });

    const fileName =
      `Forum_Aviation_OPS_FPL_${Date.now()}.pdf`;

    const absolutePath = path.join(
      OUTPUT_DIRECTORY,
      fileName
    );

    const relativePath = path.join(
      "generated",
      fileName
    );

    const document = new PDFDocument({
      size: "LETTER",
      margin: 0,
      autoFirstPage: true
    });

    const stream =
      fs.createWriteStream(absolutePath);

    stream.on("finish", () => {
      resolve(relativePath);
    });

    stream.on("error", reject);
    document.on("error", reject);

    document.pipe(stream);

    drawPageOne(document, navlog);
    drawPagesTwoAndThree(document, navlog);
    drawPageFour(document, navlog);

    document.end();
  });
}

module.exports = generatePDF;