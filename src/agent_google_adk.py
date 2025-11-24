import os
import json
import time
import warnings
from typing import List, Dict, Any
from google.adk.agents.llm_agent import Agent
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from .models import Incident, SourceReport, GlobalReport, IncidentSeverity, FileData, SourceCV, IncidentType

# Suppress ADK deprecation warnings (Logger)
import logging
logging.getLogger("google_adk").setLevel(logging.ERROR)


class ADKIncidentAgent:
    def __init__(self, api_key: str):
        # Ensure API key is set for ADK
        if "GOOGLE_API_KEY" not in os.environ:
            os.environ["GOOGLE_API_KEY"] = api_key
            
        self.agent = Agent(
            model='gemini-flash-latest',
            name='incident_detector',
            description="Analyzes data for incidents.",
            instruction="You are an expert Data Incident Detection Agent. Your goal is to analyze the daily file uploads for a specific data source and detect anomalies based on its 'Curriculum Vitae' (CV) and historical patterns. Return ONLY valid JSON."
        )
        
        self.session_service = InMemorySessionService()
        # Create a session for the agent
        self.session_id = "incident_session"
        self.user_id = "incident_user"
        self.app_name = "agents" # Must match directory or be explicit
        
        self.session_service.create_session_sync(
            session_id=self.session_id, 
            app_name=self.app_name, 
            user_id=self.user_id
        )
        
        self.runner = Runner(
            agent=self.agent, 
            session_service=self.session_service, 
            app_name=self.app_name
        )

    def analyze_source(self, source_id: str, files: List[FileData], cv: SourceCV, context: Dict[str, Any]) -> SourceReport:
        """
        Uses Google ADK Agent to analyze the source files.
        """
        
        # 1. Construct the Prompt (Same as before)
        current_date = context.get("date").strftime("%Y-%m-%d")
        last_week_files = context.get("last_week_files", [])
        
        files_json = json.dumps([f.model_dump(mode='json') for f in files], indent=2)
        last_week_json = json.dumps([f.model_dump(mode='json') for f in last_week_files], indent=2)
        cv_json = cv.model_dump_json(indent=2)
        
        prompt = f"""
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
        - **URGENT**: 
            - >1 urgent incident OR >3 total incidents.
            - **CRITICAL**: If volume drops by > 50% compared to expected (CV/Last Week), this is URGENT.
            - **CRITICAL**: If multiple expected file categories are missing, this is URGENT.
            - **CRITICAL**: If NO files are received (Total Outage) when expected, this is URGENT.
        - **ATTENTION_REQUIRED**: At least 1 incident.
        - **ALL_GOOD**: No incidents.

        **Important**:
        - Be strict but reasonable.
        - **Volume Drops**: A drop from ~40 files to ~7 files is a MAJOR incident (URGENT).
        - **Total Outage**: 0 files = URGENT.
        - Use the provided stats in CV to judge volume variations.
        - Return ONLY valid JSON.
        """

        # 2. Call the Agent with Retry
        max_retries = 5
        base_delay = 10
        response_text = ""
        
        for attempt in range(max_retries):
            try:
                # Create Content object
                content = types.Content(role="user", parts=[types.Part(text=prompt)])
                
                # Run agent
                # We use a unique session ID per source to avoid context pollution, or clear it?
                # ADK sessions persist state. If we reuse the session, the agent remembers previous sources.
                # We want stateless analysis per source.
                # So we should create a new session for each analysis or clear history.
                # Creating a new session is cleaner.
                
                temp_session_id = f"session_{source_id}_{int(time.time())}"
                self.session_service.create_session_sync(
                    session_id=temp_session_id, 
                    app_name=self.app_name, 
                    user_id=self.user_id
                )
                
                events = self.runner.run(
                    user_id=self.user_id,
                    session_id=temp_session_id,
                    new_message=content
                )
                
                for event in events:
                    # Look for model response
                    if hasattr(event, 'content') and event.content and event.content.parts:
                        for part in event.content.parts:
                            if part.text:
                                response_text += part.text
                
                # Cleanup session (optional, but good for memory)
                # self.session_service.delete_session_sync(temp_session_id)
                
                if response_text:
                    break # Success
                else:
                    raise Exception("No response text received from ADK Agent")
                    
            except Exception as e:
                if "429" in str(e) or "Resource exhausted" in str(e):
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        print(f"Rate limit hit for source {source_id}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        print(f"Error analyzing source {source_id} with ADK Agent after retries: {e}")
                        return SourceReport(source_id=source_id, status=IncidentSeverity.ATTENTION_REQUIRED, recommendations=["AI Analysis Failed (Rate Limit)"])
                else:
                    print(f"Error analyzing source {source_id} with ADK Agent: {e}")
                    return SourceReport(source_id=source_id, status=IncidentSeverity.ATTENTION_REQUIRED, recommendations=[f"AI Analysis Failed: {e}"])
        
        # 3. Parse Response
        try:
            # Clean up potential markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
                
            result = json.loads(response_text)
            
            incidents = []
            for inc_data in result.get("incidents", []):
                try:
                    inc_type = IncidentType(inc_data.get("incident_type"))
                except ValueError:
                    inc_type = IncidentType.FAILED_FILE
                    
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
            print(f"Error parsing ADK response for source {source_id}: {e}")
            print(f"Response text: {response_text}")
            return SourceReport(source_id=source_id, status=IncidentSeverity.ATTENTION_REQUIRED, recommendations=["AI Analysis Failed (Parsing Error)"])

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
