# cPanel Site Checker - Web Interface

This is a separate web application for viewing the results from the cPanel Site Checker.

## Features

- View all site changes by date using a date picker
- Display side-by-side screenshots showing:
  - Previous screenshot
  - Current screenshot
  - Diff image highlighting changes
- View text content differences between runs
- No authentication required (suitable for internal use)

## Installation

1. Navigate to the web_interface directory:
   ```bash
   cd web_interface
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

The web interface uses environment variables for configuration:

- `SITE_CHECKER_DB`: Path to the SQLite database file (default: `../site_checker.db`)
- `SITE_CHECKER_OUTPUT_DIR`: Path to the directory containing screenshots and text files (default: `..`)

## Running the Web Interface

### Development Mode

Run the application using uvicorn:

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Or simply:

```bash
python app.py
```

Then open your browser and navigate to: `http://localhost:8000`

### Production Mode

For production deployment, use uvicorn with appropriate workers:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

Or use gunicorn with uvicorn workers:

```bash
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Usage

1. Select a date from the dropdown to view changes for that day
2. The page will display all sites that had changes on the selected date
3. For each changed site, you can view:
   - Screenshot comparisons (previous, current, and diff)
   - Text content differences by clicking "Show Text Diff"

## Architecture

The web interface is designed as a separate application that:

- Does **not** share code directly with the checker process
- Only reads from the SQLite database (no writes)
- Serves static files (screenshots and text files) from the output directory
- Uses FastAPI for the backend
- Uses vanilla JavaScript for the frontend (no heavy frameworks)

## API Endpoints

- `GET /` - Main HTML page with date picker
- `GET /api/changes/{date}` - Get all changes for a specific date (JSON)
- `GET /api/screenshot?path={path}` - Serve a screenshot image
- `GET /api/textdiff?current_path={path}&previous_path={path}` - Get text content for comparison
- `GET /api/dates` - Get list of available dates with changes

## Security Considerations

This application is designed for internal use without authentication. If exposing to the internet:

1. Add authentication (e.g., using FastAPI's OAuth2 or basic auth)
2. Use HTTPS (configure with a reverse proxy like nginx)
3. Restrict access using firewall rules or IP whitelisting
4. Consider implementing rate limiting

## Directory Structure

```
web_interface/
├── app.py                 # FastAPI application
├── db_queries.py          # Database query functions
├── requirements.txt       # Python dependencies
├── static/
│   └── style.css         # CSS styling
├── templates/
│   └── index.html        # Main HTML template
└── README.md             # This file
```
