require("dotenv").config();

const express = require("express");
const cors = require("cors");
const axios = require("axios");
const path = require("path");

const parseHTML = require("./htmlParser");
const convertWithClaude = require("./claude");
const generatePDF = require("./pdfGenerator");

// ===========================================
// APP
// ===========================================

const app = express();

const PORT =
Number(process.env.PORT) || 5000;

const PUBLIC_URL =
process.env.PUBLIC_BASE_URL ||
`http://localhost:${PORT}`;


// ===========================================
// MIDDLEWARE
// ===========================================

app.use(cors());

app.use(express.json({
  limit: "10mb"
}));

app.use(express.urlencoded({
  extended: true
}));

app.use(
  "/generated",
  express.static(
    path.join(__dirname, "generated")
  )
);


// ===========================================
// TEST ROUTE
// ===========================================

app.get("/", (req, res) => {

  res.send(
    "🚀 EFLIGHT AI Backend Running"
  );

});


// ===========================================
// EMPTY ROUTE
// ===========================================

function emptyRoute() {

  return {

    header: "",

    performance: {},

    fuel: {},

    weight: {},

    route: "",

    waypoints: [],

    airportInfo: {}

  };

}
// ===========================================
// VALIDATE REQUEST
// ===========================================

function validateBody(body) {

  if (!body)
    return "Request body missing";

  if (!body.links)
    return "Links missing";

  if (!body.links.mainUrl)
    return "Main Route URL missing";

  if (!body.userInput)
    return "User Input missing";

  return null;

}


// ===========================================
// DOWNLOAD HTML
// ===========================================

async function downloadHtml(url, label, required = false) {

  if (!url) {

    if (required) {

      throw new Error(`${label} URL missing`);

    }

    console.log(`${label} not provided`);

    return emptyRoute();

  }

  console.log(`\n🌍 Downloading ${label}...`);

  const response = await axios.get(url, {

    responseType: "text",

    timeout: 60000,

    maxContentLength: 50 * 1024 * 1024,

    headers: {

      "User-Agent": "Mozilla/5.0 EFLIGHT-AI"

    }

  });

  console.log(`✅ ${label} downloaded`);

  console.log(`${label} HTML Size:`, response.data.length);

  const parsed = parseHTML(response.data);

  console.log(`\n========== ${label} PARSED ==========`);

  console.log(JSON.stringify(parsed, null, 2));

  return parsed;

}
// ===========================================
// CONVERT API
// ===========================================

app.post("/convert", async (req, res) => {

  try {

    console.log("\n================ NEW CONVERSION ================\n");

    // ===========================================
    // VALIDATE REQUEST
    // ===========================================

    const validation = validateBody(req.body);

    if (validation) {

      return res.status(400).json({

        success: false,

        message: validation

      });

    }

    // ===========================================
    // REQUEST DATA
    // ===========================================

    const { links, userInput } = req.body;

    console.log("========= USER INPUT =========");

    console.log(
      JSON.stringify(userInput, null, 2)
    );

    console.log("\n========= LINKS =========");

    console.log(
      JSON.stringify(links, null, 2)
    );

    // ===========================================
    // DOWNLOAD HTML FILES
    // ===========================================

    const mainRoute =
      await downloadHtml(
        links.mainUrl,
        "MAIN ROUTE",
        true
      );

    const alternate1 =
      await downloadHtml(
        links.alternate1Url,
        "ALTERNATE 1"
      );

    const alternate2 =
      await downloadHtml(
        links.alternate2Url,
        "ALTERNATE 2"
      );

    // ===========================================
    // MASTER JSON
    // ===========================================

    const masterJson = {

      userInput,

      mainRoute,

      alternate1,

      alternate2

    };

    console.log("\n========= MASTER JSON =========");

    console.log(
      JSON.stringify(masterJson, null, 2)
    );
        // ===========================================
    // CLAUDE CONVERSION
    // ===========================================

    console.log("\n🤖 Sending MASTER JSON to Claude...\n");

    const finalJson =
      await convertWithClaude(masterJson);

    console.log(
      "\n========= CLAUDE OUTPUT ========="
    );

    console.log(
      JSON.stringify(finalJson, null, 2)
    );


    // ===========================================
    // GENERATE PDF
    // ===========================================

    console.log(
      "\n📄 Generating PDF..."
    );

    const pdfPath =
      await generatePDF(finalJson);

    console.log(
      "✅ PDF Generated Successfully"
    );

    console.log(
      pdfPath
    );


    // ===========================================
    // RESPONSE
    // ===========================================

    res.json({

      success: true,

      pdf:
        `${PUBLIC_URL}/` +
        pdfPath.replaceAll(
          path.sep,
          "/"
        ),

      data: finalJson

    });

  }

  catch (error) {

    console.log(
      "\n❌ SERVER ERROR"
    );

    console.log(error);

    res.status(500).json({

      success: false,

      message: error.message

    });

  }

});


// ===========================================
// START SERVER
// ===========================================

app.listen(PORT, () => {

  console.log(
    `🚀 Backend running at ${PUBLIC_URL}`
  );

});


module.exports = app;