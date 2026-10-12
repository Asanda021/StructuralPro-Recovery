# P80 — Real 1404 extraction
The workflow downloads the official 1404 SAMA archive, rejects HTML/error payloads,
extracts it, inventories XLS/XLSX/CSV files, and publishes SHA-256 plus inventory
as GitHub Actions evidence. It deliberately does not commit copyrighted raw books.
