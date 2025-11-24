import os
import json
from typing import List, Dict, Any
import google.generativeai as genai
from .models import Incident, SourceReport, GlobalReport, IncidentSeverity, FileData, SourceCV, IncidentType

class IncidentDetectionAgent:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        # Use a model that supports JSON mode or is good at structured output
        self.model = genai.GenerativeModel('gemini-flash-latest') 

    def analyze_source(self, source_id: str, files: List[FileData], cv: SourceCV, context: Dict[str, Any]) -> SourceReport:
        """
        Uses GenAI to analyze the source files against the CV and context.
        """
        
        # 1. Construct the Prompt
        current_date = context.get("date").strftime("%Y-%m-%d")
        last_week_files = context.get("last_week_files", [])
        
        files_json = json.dumps([f.model_dump(mode='json') for f in files], indent=2)
        last_week_json = json.dumps([f.model_dump(mode='json') for f in last_week_files], indent=2)
        cv_json = cv.model_dump_json(indent=2)
        
        prompt = f"""
        You are an expert Data Incident Detection Agent. Your goal is to analyze the daily file uploads for a specific data source and detect anomalies based on its "Curriculum Vitae" (CV) and historical patterns.

        **Current Date**: {current_date}
        **Source ID**: {source_id}

        **Source CV (Patterns & Stats)**:
        {cv_json}

        **Files Uploaded Today**:
        {files_json}

        **Files Uploaded Last Week (Same Weekday)**:
        {last_week_json}

        **Task**:
        Analyze the "Files Uploaded Today" and identify any incidents based on the following detectors:
        1. **Missing File**: Are files missing based on the schedule? (Check "Upload Schedule" in CV).
        2. **Duplicated/Failed File**: Are there files with `is_duplicated=True` or `status="STOPPED"/"FAILED"`? Or duplicate filenames?
        3. **Unexpected Empty File**: Are there files with 0 rows? (Check if 0 rows is expected based on CV patterns/stats).
        4. **Unexpected Volume Variation**: Is the row count significantly different from the CV stats (Mean/Min/Max) or Last Week's files?
        5. **Late Upload**: Were files uploaded significantly later (>4 hours) than the expected schedule in CV?
        6. **Previous File**: Is the file date (in filename) significantly older than today?

        **Output Format**:
        Return a JSON object with the following structure:
        {{
            "incidents": [
                {{
                    "incident_type": "Missing File" | "Duplicated File" | "Unexpected Empty File" | "Unexpected Volume Variation" | "File Upload After Schedule" | "Upload of Previous File" | "Failed File",
                    "severity": "URGENT" | "ATTENTION_REQUIRED" | "ALL_GOOD",
                    "description": "Brief explanation of the incident",
                    "file_name": "Name of the file involved (or null if missing file)"
                }}
            ],
            "status": "URGENT" | "ATTENTION_REQUIRED" | "ALL_GOOD",
            "recommendations": ["Rec 1", "Rec 2"]
        }}

        **Severity Rules**:
        - **URGENT**: >1 urgent incident OR >3 total incidents.
        - **ATTENTION_REQUIRED**: At least 1 incident.
        - **ALL_GOOD**: No incidents.

        **Important**:
        - Be strict but reasonable.
        - Use the provided stats in CV to judge volume variations.
        - Return ONLY valid JSON.
        """

        # 2. Call the Model with Retry
        import time
        max_retries = 5
        base_delay = 10
        
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                response_text = response.text
                break # Success
            except Exception as e:
                if "429" in str(e) or "Resource exhausted" in str(e):
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        print(f"Rate limit hit for source {source_id}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        print(f"Error analyzing source {source_id} with GenAI after retries: {e}")
                        return SourceReport(source_id=source_id, status=IncidentSeverity.ATTENTION_REQUIRED, recommendations=["AI Analysis Failed (Rate Limit)"])
                else:
                    print(f"Error analyzing source {source_id} with GenAI: {e}")
                    return SourceReport(source_id=source_id, status=IncidentSeverity.ATTENTION_REQUIRED, recommendations=[f"AI Analysis Failed: {e}"])
        
        # 3. Parse Response
        try:
            result = json.loads(response_text)
            
            incidents = []
            for inc_data in result.get("incidents", []):
                # Map string to Enum (handle potential mismatches gracefully)
                try:
                    inc_type = IncidentType(inc_data.get("incident_type"))
                except ValueError:
                    # Fallback or map to closest
                    inc_type = IncidentType.FAILED_FILE # Default or log error
                    
                try:
                    severity = IncidentSeverity(inc_data.get("severity"))
                except ValueError:
                    severity = IncidentSeverity.ATTENTION_REQUIRED

                incidents.append(Incident(
                    incident_type=inc_type,
                    severity=severity,
                    description=inc_data.get("description"),
                    file_name=inc_data.get("file_name"),
                    source_id=source_id
                ))
            
            status = IncidentSeverity(result.get("status", "ALL_GOOD"))
            recommendations = result.get("recommendations", [])

            return SourceReport(
                source_id=source_id,
                incidents=incidents,
                status=status,
                recommendations=recommendations
            )

        except Exception as e:
            print(f"Error analyzing source {source_id} with GenAI: {e}")
            # Return empty report or error report
            return SourceReport(source_id=source_id, status=IncidentSeverity.ATTENTION_REQUIRED, recommendations=["AI Analysis Failed"])

    def generate_global_report(self, date_str: str, files_data: Dict[str, List[FileData]], 
                               last_week_files_data: Dict[str, List[FileData]], 
                               cvs: Dict[str, SourceCV], context: Dict[str, Any]) -> GlobalReport:
        
        source_reports = []
        for source_id, files in files_data.items():
            cv = cvs.get(source_id)
            if not cv:
                continue
            
            # Update context
            source_context = context.copy()
            source_context["last_week_files"] = last_week_files_data.get(source_id, [])
            
            report = self.analyze_source(source_id, files, cv, source_context)
            source_reports.append(report)
            import time
            time.sleep(4) # Avoid rate limits
            
        return GlobalReport(date=date_str, source_reports=source_reports)
