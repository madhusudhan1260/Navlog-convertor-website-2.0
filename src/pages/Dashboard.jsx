import { useState } from "react";
import axios from "axios";

function Dashboard() {

  const [files, setFiles] = useState({

    mainFile: null,
    alternate1File: null,
    alternate2File: null

  });

  const [form, setForm] = useState({

    callSign: "",
    pilotName: "",
    coPilotName: "",

    departure: "",
    destination: "",

    flightLevel: "",

    paxWeight: "",
    maxTripFuel: "",

    endurance: "",

    shortFPL: "",

    selectedFormat: "MLOVE"

  });

  const [loading, setLoading] = useState(false);

  const [pdf, setPdf] = useState(null);

  const [json, setJson] = useState(null);



  // ================= TEXT INPUT =================

  function update(event) {

    const { name, value } = event.target;

    setForm(previous => ({

      ...previous,

      [name]: value

    }));

  }



  // ================= FILE INPUT =================

  function updateFile(event) {

    const { name, files: selectedFiles } = event.target;

    setFiles(previous => ({

      ...previous,

      [name]: selectedFiles[0]

    }));

  }



  // ================= PROCESS =================

  async function processNavlog() {

    if (!files.mainFile) {

      alert("Please select Main Route HTML File");

      return;

    }

    setLoading(true);

    setPdf(null);

    setJson(null);

    try {

      const formData = new FormData();

      formData.append(
        "mainFile",
        files.mainFile
      );

      if (files.alternate1File) {

        formData.append(
          "alternate1File",
          files.alternate1File
        );

      }

      if (files.alternate2File) {

        formData.append(
          "alternate2File",
          files.alternate2File
        );

      }

      formData.append(

        "userInput",

        JSON.stringify({

          callSign: form.callSign,

          pilotName: form.pilotName,

          coPilotName: form.coPilotName,

          departure: form.departure,

          destination: form.destination,

          flightLevel: form.flightLevel,

          paxWeight: form.paxWeight,

          maxTripFuel: form.maxTripFuel,

          endurance: form.endurance,

          shortFPL: form.shortFPL,

          selectedFormat: form.selectedFormat

        })

      );

      const response = await axios.post(

        "http://localhost:5000/convert",

        formData,

        {

          headers: {

            "Content-Type": "multipart/form-data"

          }

        }

      );

      setPdf(response.data.pdf);

      setJson(response.data.data);

      alert("✅ OPS FPL Generated Successfully");

    }

    catch (error) {

      console.error(error);

      alert("Conversion Failed");

    }

    setLoading(false);

  }

  return (

    <div>

      <div className="header">

        <h1>✈ EFLIGHT AI</h1>

        <div>OPS Generator</div>

      </div>

      <div className="form-card">

        <h1>Generate OPS Flight Plan</h1>

        <hr />

        {/* ================= CREW DETAILS ================= */}

        <div className="grid3">

          <input
            name="callSign"
            placeholder="Call Sign"
            value={form.callSign}
            onChange={update}
          />

          <input
            name="pilotName"
            placeholder="Pilot Name"
            value={form.pilotName}
            onChange={update}
          />

          <input
            name="coPilotName"
            placeholder="Co-Pilot Name"
            value={form.coPilotName}
            onChange={update}
          />

        </div>

        {/* ================= ROUTE DETAILS ================= */}

        <div className="grid3">

          <input
            name="departure"
            placeholder="Departure ICAO"
            value={form.departure}
            onChange={update}
          />

          <input
            name="destination"
            placeholder="Destination ICAO"
            value={form.destination}
            onChange={update}
          />

          <input
            name="flightLevel"
            placeholder="Flight Level"
            value={form.flightLevel}
            onChange={update}
          />

        </div>

        {/* ================= WEIGHT DETAILS ================= */}

        <div className="grid3">

          <input
            name="paxWeight"
            placeholder="PAX Weight"
            value={form.paxWeight}
            onChange={update}
          />

          <input
            name="maxTripFuel"
            placeholder="Max Trip Fuel"
            value={form.maxTripFuel}
            onChange={update}
          />

          <input
            name="endurance"
            placeholder="Endurance (HH:MM)"
            value={form.endurance}
            onChange={update}
          />

        </div>

        <br />

        {/* ================= HTML FILES ================= */}

        <h2>ForeFlight HTML Files</h2>

        <div className="grid1">

          <label>
            <strong>Main Route HTML</strong>

            <input
              type="file"
              accept=".html,.htm"
              name="mainFile"
              onChange={updateFile}
            />
          </label>

        </div>

        <br />

        <div className="grid1">

          <label>
            <strong>Alternate 1 HTML (Optional)</strong>

            <input
              type="file"
              accept=".html,.htm"
              name="alternate1File"
              onChange={updateFile}
            />
          </label>

        </div>

        <br />

        <div className="grid1">

          <label>
            <strong>Alternate 2 HTML (Optional)</strong>

            <input
              type="file"
              accept=".html,.htm"
              name="alternate2File"
              onChange={updateFile}
            />
          </label>

        </div>

        <br />

        {/* ================= SHORT FPL ================= */}

        <h2>ATC Short Flight Plan</h2>

        <textarea
          name="shortFPL"
          placeholder="Paste Short Flight Plan"
          value={form.shortFPL}
          onChange={update}
          rows={6}
        />

        <br />
        <br />

        {/* ================= FORMAT ================= */}

        <select
          name="selectedFormat"
          value={form.selectedFormat}
          onChange={update}
        >

          <option value="MLOVE">
            MLOVE
          </option>

          <option value="DEFAULT">
            DEFAULT
          </option>

        </select>

        <br />
        <br />

        {/* ================= PROCESS BUTTON ================= */}

        <button
          className="process"
          onClick={processNavlog}
          disabled={loading}
        >
          {
            loading
              ? `✈ Generating ${form.selectedFormat} OPS PDF...`
              : "🚀 Generate OPS PDF"
          }
        </button>

        <br />
        <br />

        {/* ================= DOWNLOAD PDF ================= */}

        {
          pdf && (

            <div className="download-section">

              <a
                href={pdf}
                target="_blank"
                rel="noreferrer"
                className="download-btn"
              >

                📄 Download Generated PDF

              </a>

            </div>

          )
        }

        <br />

        {/* ================= JSON OUTPUT ================= */}

        {
          json && (

            <>

              <h2>Generated JSON</h2>

              <pre className="json-box">

                {JSON.stringify(json, null, 2)}

              </pre>

            </>

          )
        }

      </div>

    </div>

  );

}

export default Dashboard;