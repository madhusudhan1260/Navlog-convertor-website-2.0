import { useState } from "react";
import axios from "axios";

const initialFiles = {
  mainFile: null,
  alternate1File: null,
  alternate2File: null
};

const initialUserInput = {
  callSign: "",
  pilotName: "",
  coPilotName: "",
  departure: "",
  destination: "",
  pax: "",
  paxWeight: "",
  maxTripFuel: "",
  endurance: "",
  flightLevel: "",
  shortFPL: "",
  selectedFormat: "MLOVE"
};

const manualFields = [
  ["callSign", "CALL SIGN"],
  ["pilotName", "PILOT NAME (PIC)"],
  ["coPilotName", "CO PILOT NAME (F/O)"],
  ["departure", "DEPARTURE AIRPORT"],
  ["destination", "DESTINATION AIRPORT"],
  ["pax", "PAX COUNT"],
  ["paxWeight", "PAX WEIGHT"],
  ["maxTripFuel", "MAX TRIP FUEL"],
  ["endurance", "ENDURANCE TIME"],
  ["flightLevel", "FLIGHT LEVEL"]
];

function Dashboard() {
  const [files, setFiles] = useState(initialFiles);
  const [userInput, setUserInput] = useState(initialUserInput);
  const [data, setData] = useState(null);
  const [pdf, setPdf] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function updateFile(event) {
    const { name, files: selectedFiles } = event.target;

    setFiles((previous) => ({
      ...previous,
      [name]: selectedFiles[0]
    }));
  }

  function updateInput(event) {
    const { name, value } = event.target;

    setUserInput((previous) => ({
      ...previous,
      [name]: value
    }));
  }

  async function processNavlog(event) {
    event.preventDefault();

    setLoading(true);
    setError("");
    setPdf("");
    setData(null);

    try {
      const formData = new FormData();

      formData.append("mainFile", files.mainFile);

      if (files.alternate1File) {
        formData.append("alternate1File", files.alternate1File);
      }

      if (files.alternate2File) {
        formData.append("alternate2File", files.alternate2File);
      }

      formData.append("userInput", JSON.stringify(userInput));

      const response = await axios.post(
        "http://localhost:5000/convert",
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data"
          }
        }
      );

      setData(response.data.data);
      setPdf(response.data.pdf);
    } catch (requestError) {
      setError(
        requestError.response?.data?.message || "Navlog conversion failed."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <header className="header">
        <h1>EFLIGHT AI</h1>
        <span>NAVLOG CONVERTER</span>
        <span>OPS FPL</span>
      </header>

      <form className="form-card" onSubmit={processNavlog}>
        <h2>Generate Operational Flight Plan</h2>

        <fieldset>
          <legend>UPLOAD FOREFLIGHT HTML FILES</legend>

          <label>
            MAIN FOREFLIGHT HTML
            <input
              required
              type="file"
              accept=".html,.htm"
              name="mainFile"
              onChange={updateFile}
            />
          </label>

          <label>
            FIRST ALTERNATE HTML
            <input
              type="file"
              accept=".html,.htm"
              name="alternate1File"
              onChange={updateFile}
            />
          </label>

          <label>
            SECOND ALTERNATE HTML
            <input
              type="file"
              accept=".html,.htm"
              name="alternate2File"
              onChange={updateFile}
            />
          </label>
        </fieldset>

        <fieldset className="grid">
          <legend>MANUAL DATA</legend>

          {manualFields.map(([name, label]) => (
            <label key={name}>
              {label}
              <input
                name={name}
                value={userInput[name]}
                onChange={updateInput}
              />
            </label>
          ))}

          <label className="wide">
            SHORT FPL
            <textarea
              name="shortFPL"
              value={userInput.shortFPL}
              onChange={updateInput}
              rows="4"
            />
          </label>

          <label>
            FORMAT
            <select
              name="selectedFormat"
              value={userInput.selectedFormat}
              onChange={updateInput}
            >
              <option value="MLOVE">MLOVE</option>
              <option value="DEFAULT">DEFAULT</option>
            </select>
          </label>
        </fieldset>

        <button className="process" disabled={loading}>
          {loading ? "AI CREATING OPS FPL..." : "PROCESS"}
        </button>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        {pdf && (
          <a
            className="download-btn"
            href={pdf}
            target="_blank"
            rel="noreferrer"
          >
            DOWNLOAD PDF
          </a>
        )}

        {data && (
          <details>
            <summary>VIEW GENERATED JSON</summary>
            <pre>{JSON.stringify(data, null, 2)}</pre>
          </details>
        )}
      </form>
    </main>
  );
}

export default Dashboard;