import argparse
import sys
import os
from datetime import datetime
from tabulate import tabulate
from .input_preparer import InputPreparer
from .agent_adk import IncidentDetectionAgent
from .models import IncidentSeverity

def main():
    parser = argparse.ArgumentParser(description="Incident Detection Agent (GenAI)")
    parser.add_argument("--date", type=str, required=True, help="Date to process (YYYY-MM-DD)")
    parser.add_argument("--data-dir", type=str, default="data", help="Path to data directory")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of sources to process")
    parser.add_argument("--agent-type", type=str, default="genai", choices=["genai", "adk"], help="Agent implementation to use (genai or adk)")
    args = parser.parse_args()

    # Check API Key
    api_key = os.environ.get("GOOGLE_API_KEY")
    
    # Try loading from .env manually if not set
    if not api_key and os.path.exists(".env"):
        try:
            with open(".env", "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GOOGLE_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip("'").strip('"')
                        break
        except Exception as e:
            print(f"Warning: Could not read .env file: {e}")

    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable not set.")
        print("Please export your Google Gemini API Key: export GOOGLE_API_KEY='your_key'")
        sys.exit(1)

    try:
        current_date = datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print("Invalid date format. Use YYYY-MM-DD")
        sys.exit(1)

    print(f"Starting GenAI Incident Detection Agent for {args.date}...")

    # 1. Prepare Inputs
    preparer = InputPreparer(args.data_dir)
    
    try:
        files_data = preparer.load_files_data(args.date)
        last_week_files_data = preparer.load_last_weekday_files(args.date)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Load CVs
    cvs = {}
    
    # Apply limit if specified
    source_ids = list(files_data.keys())
    if args.limit:
        source_ids = source_ids[:args.limit]
        # Filter files_data to only include selected sources
        files_data = {k: files_data[k] for k in source_ids}
        print(f"Limiting processing to {args.limit} sources.")

    for source_id in source_ids:
        cv = preparer.parse_cv(source_id)
        if cv:
            cvs[source_id] = cv

    # Initialize Agent
    if args.agent_type == "adk":
        from .agent_google_adk import ADKIncidentAgent
        print("Using Google ADK Agent...")
        agent = ADKIncidentAgent(api_key=api_key)
    else:
        from .agent_adk import IncidentDetectionAgent
        print("Using GenAI Direct Agent...")
        agent = IncidentDetectionAgent(api_key=api_key)

    # Load Data
    print(f"Loading data for {args.date}...")
    context = {"date": current_date}
    
    report = agent.generate_global_report(args.date, files_data, last_week_files_data, cvs, context)

    # 3. Print Report
    print("\n" + "="*50)
    print(f"EXECUTIVE REPORT (GenAI) - {args.date}")
    print("="*50 + "\n")

    summary_data = []
    for sr in report.source_reports:
        icon = "🟢"
        if sr.status == IncidentSeverity.URGENT:
            icon = "🔴"
        elif sr.status == IncidentSeverity.ATTENTION_REQUIRED:
            icon = "🟡"
        
        summary_data.append([icon, sr.source_id, sr.status.value, len(sr.incidents)])

    print(tabulate(summary_data, headers=["Status", "Source ID", "Severity", "Incidents"], tablefmt="grid"))

    print("\n" + "="*50)
    print("DETAILED INCIDENTS")
    print("="*50 + "\n")

    for sr in report.source_reports:
        if sr.incidents:
            print(f"\nSource: {sr.source_id} ({sr.status.value})")
            incident_data = []
            for inc in sr.incidents:
                incident_data.append([inc.severity.value, inc.incident_type.value, inc.file_name or "N/A", inc.description])
            
            print(tabulate(incident_data, headers=["Severity", "Type", "File", "Description"], tablefmt="simple"))
            
            if sr.recommendations:
                print("\nRecommendations:")
                for rec in sr.recommendations:
                    print(f"- {rec}")

if __name__ == "__main__":
    main()
