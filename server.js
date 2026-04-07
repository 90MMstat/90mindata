// server.js — Allsvenskan Analytics
// Kör: node server.js  →  http://localhost:3001

const express = require("express");
const cors    = require("cors");
const path    = require("path");
const fs      = require("fs");

const app  = express();
const PORT = 3001;

app.use(cors());
app.use(express.static(__dirname));

// Serve data.json
app.get("/api/data", (req, res) => {
  const p = path.join(__dirname, "data.json");
  if (!fs.existsSync(p)) {
    return res.status(404).json({ error: "data.json saknas — kör python process_data.py" });
  }
  res.setHeader("Content-Type", "application/json");
  res.setHeader("Cache-Control", "public, max-age=300");
  res.sendFile(p);
});

app.listen(PORT, () => {
  console.log(`\n✓  Allsvenskan Analytics: http://localhost:${PORT}\n`);
  if (!fs.existsSync(path.join(__dirname, "data.json"))) {
    console.log("⚠  Kör 'python process_data.py' för att generera data.json!\n");
  }
});
