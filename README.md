# Incident Detection Agent (GenAI Edition)

## Overview
This project implements an AI-powered Agent designed to automate the detection of data processing incidents. It uses **Google's Generative AI (Gemini)** via the **Agent Development Kit (ADK)** concepts to analyze daily file uploads against historical patterns and "Curriculum Vitae" (CV) of data sources.

The agent identifies anomalies such as:
- Missing files
- Unexpected volume variations
- Schedule deviations (late uploads)
- Empty files
- Duplicated or failed files

## Prerequisites
- Python 3.10+
- Google Gemini API Key

## Installation

1. **Clone the repository** (if applicable) or navigate to the project folder.
2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   # Or manually:
   pip install google-generativeai pydantic pandas openpyxl tabulate
   ```

## Configuration

You must provide a Google Gemini API Key. You can do this by creating a `.env` file in the root directory:

```bash
GOOGLE_API_KEY=your_api_key_here
```

Or by exporting it in your terminal:
```bash
export GOOGLE_API_KEY='your_api_key_here'
```

## Usage

Run the agent using the command line interface:

```bash
python3 -m src.main --date YYYY-MM-DD [OPTIONS]
```

### Arguments
- `--date`: The date to analyze in `YYYY-MM-DD` format (Required).
- `--data-dir`: Path to the data directory (Default: `data`).
- `--limit`: Limit the number of sources to process (Optional, useful for testing or avoiding rate limits).

### Example
```bash
# Run for September 12, 2025, limiting to 5 sources
python3 -m src.main --date 2025-09-12 --limit 5
```

## Inputs
The agent expects a `data` directory with the following structure:
- `Files/datasource_cvs/`: Markdown files (`*_native.md`) containing patterns and stats for each source.
- `Files/{YYYY-MM-DD}_20_00_UTC/files.json`: JSON file listing files uploaded on that date.
- `Files/{YYYY-MM-DD}_20_00_UTC/files_last_weekday.json`: JSON file listing files from the same weekday of the previous week.

## Outputs
The agent outputs an **Executive Report** to the console, including:
1. **Summary Table**: Status (Green/Yellow/Red) for each source.
2. **Detailed Incidents**: List of detected issues with severity and descriptions.
3. **Recommendations**: AI-generated actions for critical issues.

## Architecture
- **`src/agent_adk.py`**: Core logic using Google Gemini to analyze data.
- **`src/input_preparer.py`**: Parses raw JSON and Markdown data into structured objects.
- **`src/models.py`**: Pydantic models for type safety.
- **`src/main.py`**: CLI entry point.
