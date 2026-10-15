<p align="center">
  <img src="assets/banner.png" alt="lazysort: AI file organizer that renames and groups images with Gemini Vision" width="100%">
</p>

<p align="center">
  <b>English</b> · <a href="README.ko.md"><b>한국어</b></a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/github/license/kks0488/lazysort?color=60a5fa" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/Python-FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-19%20%2B%20Vite-61dafb?logo=react&logoColor=black" alt="React 19 + Vite">
  <img src="https://img.shields.io/badge/Gemini-2.5%20Flash-8e75ff?logo=googlegemini&logoColor=white" alt="Gemini 2.5 Flash">
  <a href="https://github.com/kks0488/lazysort/stargazers"><img src="https://img.shields.io/github/stars/kks0488/lazysort?style=flat&color=a855f7" alt="GitHub stars"></a>
  <img src="https://img.shields.io/github/last-commit/kks0488/lazysort?color=64748b" alt="Last commit">
</p>

<h2 align="center">A folder full of <code>IMG_2041.jpg</code> and <code>final(2).png</code>?<br>lazysort looks at each image and gives it a name you can search.</h2>

<p align="center">
  A local web app for designers and e-commerce teams with messy asset folders.<br>
  Gemini Vision reads every image, proposes a structured filename, and every move can be undone.
</p>

<table>
<tr>
<td width="50%" valign="top">

### Rename by what's in the image
Gemini 2.5 Flash sorts each image into a category (product, banner, screenshot, document, label, photo), detects the brand and adds tags. The new name follows `category_brand_tags_resolution.ext`.

</td>
<td width="50%" valign="top">

### Keep what you already typed
Words in the old filename are parsed and merged with the AI tags, so your own hints (brand, season, color) stay in the new name.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### Clean up before sorting
MD5 duplicate detection, low-resolution and screenshot flags, and clustering of similar images (Gemini image descriptions → embeddings → DBSCAN, each cluster named by AI).

</td>
<td width="50%" valign="top">

### Safe by design
Renames are logged to a history file and moves are written to a journal first, so the last batch can be undone or rolled back. You review every proposal before it runs.

</td>
</tr>
</table>

<p align="center">
  <img src="assets/screenshot.png" alt="lazysort web app: folder picker with drag and drop" width="90%">
</p>

## Three ways to organize

| Tab | What it does | Endpoint |
| --- | --- | --- |
| **Renamer** | Scan a folder, preview AI names, apply in one batch, undo | `/scan-folder`, `/batch-rename`, `/undo` |
| **Organizer** | Find duplicates and low-res files, cluster similar images, move with rollback | `/organize/scan`, `/organize/cluster`, `/organize/execute`, `/organize/rollback` |
| **Smart (one-click)** | Group files into work sessions by time gap, read brand names with Apple Vision OCR, optionally classify with MobileCLIP2 | `/session-analyze`, `/session-organize`, `/smart-organize` |

## Quick start

```bash
git clone https://github.com/kks0488/lazysort.git
cd lazysort

# backend (http://127.0.0.1:2424)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY="your-key"       # https://aistudio.google.com/apikey
python main.py

# frontend (in another terminal)
cd frontend
npm install
npm run dev
```

Optional local models (MobileCLIP2, Apple Vision OCR on macOS):

```bash
pip install -r requirements-local-models.txt
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | — | Required for AI naming and clustering |
| `LAZYSORT_HOST` / `LAZYSORT_PORT` | `127.0.0.1` / `2424` | Server bind address |
| `LAZYSORT_MODEL_DIR` | `backend/models` | Where the MobileCLIP2 weights are stored |

## Stack

FastAPI · google-generativeai · Pillow · scikit-learn (DBSCAN) · React 19 · Vite · Tailwind CSS · optional PyTorch / MobileCLIP2 / Apple Vision.

## FAQ

**Are my files uploaded anywhere?** Image content is sent to the Gemini API for analysis. Files themselves stay on your disk; renames and moves happen locally.

**Can I undo?** Yes. Renames are recorded in `history.json`, moves in `move_journal.json`; use Undo / Rollback in the app.

**Status?** A working prototype built for real e-commerce asset folders. The server binds to localhost by default; do not expose it to a network.

## License

MIT © Kyoungsoo Kim — see [LICENSE](LICENSE).
