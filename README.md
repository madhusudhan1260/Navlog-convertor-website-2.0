# ✈️ Navlog Convertor Website 2.0

A full-stack web application that converts aviation navigation logs (Navlogs) into custom company-specific formats automatically. The application eliminates manual editing by parsing uploaded Navlogs and generating standardized PDF outputs in seconds.

---

## 🌐 Deploy

Two services, because the frontend is static and the PDF generation is Python.
**Deploy the backend first** — the frontend needs its URL.

### 1. Backend → Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/madhusudhan1260/Navlog-convertor-website-2.0)

Reads `render.yaml` and creates the `eflightops-api` service with no further
configuration. You end up at `https://eflightops-api.onrender.com`.

### 2. Frontend → Vercel

[Import the repo on Vercel →](https://vercel.com/new/import?s=https://github.com/madhusudhan1260/Navlog-convertor-website-2.0)

Two things to set on the import screen:

| Field | Value |
| --- | --- |
| Project Name | `eflightops` |
| Environment Variable | `VITE_API_URL` = `https://eflightops-api.onrender.com` |

Framework detection picks Vite on its own. Result: `https://eflightops.vercel.app`.

> Render's free tier sleeps after inactivity, so the first PDF generated
> after an idle period waits ~30s for the backend to wake.

---

## 🚀 Features

- 📄 Upload Navlog files
- 🔄 Automatic Navlog parsing
- 📝 Convert to custom company formats
- 📑 Generate downloadable PDF reports
- ⚡ Fast and user-friendly interface
- 🔒 Secure file handling
- 📱 Responsive design for desktop and mobile

---

## 🛠️ Tech Stack

### Frontend
- React.js
- Vite
- JavaScript
- HTML5
- CSS3

### Backend
- Python
- Flask
- PDF Generation Libraries

### Other Tools
- Git
- GitHub

---

## 📂 Project Structure

```
navlog-converter/
│
├── backend/
│   ├── server.py
│   ├── htmlParser.py
│   ├── pdfGenerator.py
│   └── generated/
│
├── public/
│
├── src/
│   ├── pages/
│   ├── components/
│   ├── assets/
│   └── App.jsx
│
├── package.json
├── vite.config.js
└── README.md
```

---

## ⚙️ Installation

### Clone the repository

```bash
git clone https://github.com/madhusudhan1260/Navlog-convertor-website-2.0.git
```

### Navigate to the project

```bash
cd Navlog-convertor-website-2.0
```

### Install frontend dependencies

```bash
npm install
```

### Start the React application

```bash
npm run dev
```

### Start the backend

```bash
cd backend
python server.py
```

---

## 📸 Screenshots

Add screenshots of:

- Login Page
- Dashboard
- Upload Page
- Converted PDF
- Output Preview

---

## 🎯 Future Improvements

- Support additional Navlog formats
- User authentication
- Cloud storage
- Conversion history
- Batch conversion
- Export to Excel
- Dark mode

---

## 👨‍💻 Author

**Madhusudhan Ramshetty**

- GitHub: https://github.com/madhusudhan1260

---

## ⭐ Support

If you found this project useful, please consider giving it a ⭐ on GitHub.
