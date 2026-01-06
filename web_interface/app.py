"""FastAPI web interface for cPanel Site Checker."""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime
import os

from db_queries import SiteCheckerDB

# Initialize FastAPI app
app = FastAPI(title="cPanel Site Checker Web Interface")

# Mount static files
static_path = Path(__file__).parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Setup templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Initialize database
# Assuming the database is in the parent directory
db_path = os.environ.get("SITE_CHECKER_DB", "../site_checker.db")
output_dir = os.environ.get("SITE_CHECKER_OUTPUT_DIR", "..")
db = SiteCheckerDB(db_path=db_path)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main page with date picker."""
    # Get available dates
    available_dates = db.get_available_dates()
    
    # Use today's date as default if available, otherwise use most recent
    today = datetime.now().strftime('%Y-%m-%d')
    default_date = today if today in available_dates else (available_dates[0] if available_dates else today)
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "available_dates": available_dates,
            "default_date": default_date
        }
    )


@app.get("/api/changes/{date}")
async def get_changes(date: str):
    """Get all changes for a specific date.
    
    Args:
        date: Date in YYYY-MM-DD format
        
    Returns:
        JSON list of changes with screenshot and text file paths
    """
    try:
        # Validate date format
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Get changes from database
    changes = db.get_changes_by_date(date)
    
    # Enhance each change with file paths
    for change in changes:
        # Extract run date serial from timestamp
        current_run = db.extract_run_from_timestamp(change['timestamp'], output_dir)
        
        # Get screenshot paths
        if current_run:
            screenshot_paths = db.get_screenshot_paths(
                domain=change['domain'],
                user=change['user'],
                current_run=current_run,
                previous_run=change['screenshot_previous_run'],
                host=change['host'],
                output_dir=output_dir
            )
            change['screenshots'] = screenshot_paths
            
            # Get text file paths
            text_paths = db.get_text_file_paths(
                domain=change['domain'],
                user=change['user'],
                current_run=current_run,
                previous_run=change['txt_previous_run'],
                host=change['host'],
                output_dir=output_dir
            )
            change['text_files'] = text_paths
        else:
            change['screenshots'] = {'current': None, 'previous': None, 'diff': None}
            change['text_files'] = {'current': None, 'previous': None}
        
        # Add current_run to change info
        change['current_run'] = current_run
    
    return {"changes": changes}


@app.get("/api/screenshot")
async def get_screenshot(path: str):
    """Serve a screenshot image.
    
    Args:
        path: Relative path to screenshot file
        
    Returns:
        PNG image file
    """
    # Resolve the full path
    full_path = Path(output_dir) / path
    
    # Security check: ensure path doesn't escape output directory
    try:
        full_path = full_path.resolve()
        output_path = Path(output_dir).resolve()
        if not str(full_path).startswith(str(output_path)):
            raise HTTPException(status_code=403, detail="Access denied")
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid path")
    
    # Check if file exists
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="Screenshot not found")
    
    return FileResponse(full_path, media_type="image/png")


@app.get("/api/textdiff")
async def get_text_diff(current_path: str, previous_path: str = None):
    """Get text content for comparison.
    
    Args:
        current_path: Path to current text file
        previous_path: Path to previous text file (optional)
        
    Returns:
        JSON with current and previous text content
    """
    result = {}
    
    # Read current file
    current_full_path = Path(output_dir) / current_path
    
    # Security check
    try:
        current_full_path = current_full_path.resolve()
        output_path = Path(output_dir).resolve()
        if not str(current_full_path).startswith(str(output_path)):
            raise HTTPException(status_code=403, detail="Access denied")
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid path")
    
    if current_full_path.exists():
        with open(current_full_path, 'r', encoding='utf-8', errors='replace') as f:
            result['current'] = f.read()
    else:
        result['current'] = None
    
    # Read previous file if provided
    if previous_path:
        previous_full_path = Path(output_dir) / previous_path
        
        # Security check
        try:
            previous_full_path = previous_full_path.resolve()
            if not str(previous_full_path).startswith(str(output_path)):
                raise HTTPException(status_code=403, detail="Access denied")
        except Exception:
            raise HTTPException(status_code=403, detail="Invalid path")
        
        if previous_full_path.exists():
            with open(previous_full_path, 'r', encoding='utf-8', errors='replace') as f:
                result['previous'] = f.read()
        else:
            result['previous'] = None
    else:
        result['previous'] = None
    
    return result


@app.get("/api/dates")
async def get_available_dates():
    """Get list of dates with available changes.
    
    Returns:
        JSON list of dates
    """
    dates = db.get_available_dates()
    return {"dates": dates}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
