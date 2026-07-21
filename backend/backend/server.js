require("dotenv").config();

const express = require("express");
const cors = require("cors");
const path = require("path");
const fs = require("fs");
const multer = require("multer");

const parseHTML = require("./htmlParser");
const convertWithClaude = require("./claude");
const generatePDF = require("./pdfGenerator");

const app = express();

const PORT =
  Number(process.env.PORT) || 5000;

const PUBLIC_URL =
  process.env.PUBLIC_BASE_URL ||
  `http://localhost:${PORT}`;

// =====================================
// Middleware
// =====================================

app.use(cors());

app.use(express.json({ limit: "10mb" }));

app.use(
  express.urlencoded({
    extended: true
  })
);

app.use(
  "/generated",
  express.static(
    path.join(__dirname, "generated")
  )
);

// =====================================
// Upload Folder
// =====================================

const upload = multer({
  dest: "uploads/"
});

// =====================================

app.get("/", (req, res) => {
  res.send("🚀 EFLIGHT AI Backend Running");
});

// =====================================

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

// =====================================

app.post(
  "/convert",
  upload.fields([
    { name: "mainFile", maxCount: 1 },
    { name: "alternate1File", maxCount: 1 },
    { name: "alternate2File", maxCount: 1 }
  ]),

  async (req, res) => {
    try {

      console.log(
        "\n========== NEW CONVERSION ==========\n"
      );

      if (!req.files.mainFile) {

        return res.status(400).json({
          success: false,
          message: "Main HTML file missing."
        });

      }

      const userInput = JSON.parse(
        req.body.userInput
      );

      console.log(userInput);

      // =====================================
      // MAIN ROUTE
      // =====================================

      const mainHtml =
        fs.readFileSync(
          req.files.mainFile[0].path,
          "utf8"
        );

      const mainRoute =
        parseHTML(mainHtml);

      // =====================================
      // ALT 1
      // =====================================

      let alternate1 = emptyRoute();

      if (req.files.alternate1File) {

        const html =
          fs.readFileSync(
            req.files.alternate1File[0].path,
            "utf8"
          );

        alternate1 =
          parseHTML(html);

      }

      // =====================================
      // ALT 2
      // =====================================

      let alternate2 = emptyRoute();

      if (req.files.alternate2File) {

        const html =
          fs.readFileSync(
            req.files.alternate2File[0].path,
            "utf8"
          );

        alternate2 =
          parseHTML(html);

      }

      // =====================================

      const masterJson = {

        userInput,

        mainRoute,

        alternate1,

        alternate2

      };

      console.log(
        JSON.stringify(
          masterJson,
          null,
          2
        )
      );

      const finalJson =
        await convertWithClaude(
          masterJson
        );

      const pdfPath =
        await generatePDF(
          finalJson
        );

      // =====================================
      // Delete uploaded temp files
      // =====================================

      Object.values(req.files)
        .flat()
        .forEach(file => {

          fs.unlinkSync(file.path);

        });

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

      console.log(error);

      res.status(500).json({

        success: false,

        message: error.message

      });

    }

  }
);

app.listen(PORT, () => {

  console.log(
    `🚀 Backend Running on ${PUBLIC_URL}`
  );

});

module.exports = app;