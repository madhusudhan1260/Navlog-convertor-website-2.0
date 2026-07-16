import { useState } from "react";
import axios from "axios";

function Dashboard() {

  const [form, setForm] = useState({

    // ================= HTML LINKS =================

    mainUrl: "",
    alternate1Url: "",
    alternate2Url: "",

    // ================= FLIGHT DETAILS =================

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

    selectedFormat: "Forum Aviation Format"

  });

  const [loading, setLoading] = useState(false);

  const [pdf, setPdf] = useState(null);

  const [json, setJson] = useState(null);



  // ================= UPDATE INPUT =================

  function update(event) {

    const { name, value } = event.target;

    setForm(previous => ({

      ...previous,

      [name]: value

    }));

  }



  // ================= PROCESS =================

  async function processNavlog() {

    if (!form.mainUrl) {

      alert("Please enter Main Route HTML URL");

      return;

    }

    setLoading(true);

    setPdf(null);

    setJson(null);

    try {
            const response = await axios.post(

        "http://localhost:5000/convert",

        {

          links: {

            mainUrl: form.mainUrl,

            alternate1Url: form.alternate1Url,

            alternate2Url: form.alternate2Url

          },

          userInput: {

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

      {/* ================= HEADER ================= */}

      <div className="header">

        <h1>✈ EFLIGHT AI</h1>

        <div>Forum Aviation OPS Generator</div>

      </div>

      <div className="form-card">

        <h1>Generate Forum Aviation OPS FPL</h1>

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
                {/* ================= HTML LINKS ================= */}

        <h2>ForeFlight HTML Links</h2>

        <div className="grid1">

          <input
            type="text"
            name="mainUrl"
            placeholder="Paste Main Route HTML Link"
            value={form.mainUrl}
            onChange={update}
          />

        </div>

        <br />

        <div className="grid1">

          <input
            type="text"
            name="alternate1Url"
            placeholder="Paste Alternate 1 HTML Link (Optional)"
            value={form.alternate1Url}
            onChange={update}
          />

        </div>

        <br />

        <div className="grid1">

          <input
            type="text"
            name="alternate2Url"
            placeholder="Paste Alternate 2 HTML Link (Optional)"
            value={form.alternate2Url}
            onChange={update}
          />

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

          <option value="Forum Aviation Format">
            Forum Aviation Format
          </option>

          <option value="Custom Format">
            Custom Format
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
              ? "✈ Generating Forum Aviation OPS PDF..."
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