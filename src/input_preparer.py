import json
import os
import re
from typing import Dict, List, Optional
from datetime import datetime
from .models import FileData, SourceCV

class InputPreparer:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.cv_dir = os.path.join(data_dir, "Files", "datasource_cvs")

    def load_files_data(self, date_str: str) -> Dict[str, List[FileData]]:
        """
        Loads files.json for a specific date.
        date_str format: YYYY-MM-DD
        """
        # The directory naming convention is {date}_20_00_UTC
        dir_name = f"{date_str}_20_00_UTC"
        file_path = os.path.join(self.data_dir, "Files", dir_name, "files.json")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Files data not found for {date_str} at {file_path}")

        with open(file_path, 'r') as f:
            raw_data = json.load(f)

        parsed_data = {}
        for source_id, files in raw_data.items():
            parsed_files = []
            for file_item in files:
                # Handle potential parsing errors or format differences
                try:
                    parsed_files.append(FileData(**file_item))
                except Exception as e:
                    print(f"Error parsing file item in source {source_id}: {e}")
            parsed_data[source_id] = parsed_files
        
        return parsed_data

    def load_last_weekday_files(self, date_str: str) -> Dict[str, List[FileData]]:
        """
        Loads files_last_weekday.json for a specific date.
        """
        dir_name = f"{date_str}_20_00_UTC"
        file_path = os.path.join(self.data_dir, "Files", dir_name, "files_last_weekday.json")
        
        if not os.path.exists(file_path):
            # It's possible this file doesn't exist for all days, return empty or handle gracefully
            print(f"Warning: files_last_weekday.json not found for {date_str}")
            return {}

        with open(file_path, 'r') as f:
            raw_data = json.load(f)

        parsed_data = {}
        for source_id, files in raw_data.items():
            parsed_files = []
            for file_item in files:
                try:
                    parsed_files.append(FileData(**file_item))
                except Exception as e:
                    print(f"Error parsing file item in source {source_id}: {e}")
            parsed_data[source_id] = parsed_files
        
        return parsed_data

    def parse_cv(self, source_id: str) -> Optional[SourceCV]:
        """
        Parses the markdown CV for a given source ID.
        """
        cv_path = os.path.join(self.cv_dir, f"{source_id}_native.md")
        if not os.path.exists(cv_path):
            print(f"CV not found for source {source_id}")
            return None

        with open(cv_path, 'r') as f:
            content = f.read()

        # Extract Metadata
        workspace_match = re.search(r"Workspace ID\*\*: (\d+)", content)
        workspace_id = workspace_match.group(1) if workspace_match else "Unknown"

        # Extract Filename Pattern
        # Looking for "Common structure: `...`"
        pattern_match = re.search(r"Common structure: `([^`]+)`", content)
        filename_pattern = pattern_match.group(1) if pattern_match else ""

        # Extract Upload Schedule
        # We need to parse the markdown table for "Upload Schedule Patterns by Day"
        # | Day | Upload Hour Slot Mean (UTC) | ...
        # This is a bit complex with regex, but let's try to find the table rows.
        upload_schedule = {}
        
        # Regex to find table rows starting with | Mon | ...
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for day in days:
            # Regex to capture the time in the second column (Upload Hour Slot Mean)
            # Example: | Mon | 15:00 | ...
            # Be careful with spaces
            day_regex = r"\|\s*" + day + r"\s*\|\s*(\d{2}:\d{2})\s*\|"
            match = re.search(day_regex, content)
            if match:
                upload_schedule[day] = match.group(1)

        # Extract Volume Stats
        # Table: | Day | Row Statistics | ...
        # Content in cell: • Min: 1<br>• Max: 10,762<br>• Mean: 5,953.54<br>• Median: 5,477.00
        volume_stats = {}
        for day in days:
            # We look for the row starting with the day
            # Then capture the content of the "Row Statistics" column
            # The table might be formatted differently, let's look for the specific section
            # "## **4. Day-of-Week Summary"
            
            # A more robust way might be to split the file by lines and process statefully, 
            # but regex is faster for now if the format is strict.
            
            # Let's try to capture the whole row for the day in the Day-of-Week Summary table
            # | Mon | • Min: 1<br>• Max: ... |
            
            row_regex = r"\|\s*" + day + r"\s*\|\s*([^|]+)\|"
            match = re.search(row_regex, content)
            if match:
                stats_str = match.group(1)
                stats = {}
                
                # Extract Mean
                mean_match = re.search(r"Mean: ([\d,.]+)", stats_str)
                if mean_match:
                    stats["mean"] = float(mean_match.group(1).replace(",", ""))
                
                # Extract StdDev (might not be in this table, let's check "File Processing Statistics by Day" table if needed)
                # Actually, the "File Processing Statistics by Day" table has Mean Files, not rows.
                # The "Day-of-Week Summary" has Row Statistics.
                # Let's stick to Row Statistics for volume variation.
                
                # Extract Min
                min_match = re.search(r"Min: ([\d,.]+)", stats_str)
                if min_match:
                    stats["min"] = float(min_match.group(1).replace(",", ""))
                
                # Extract Max
                max_match = re.search(r"Max: ([\d,.]+)", stats_str)
                if max_match:
                    stats["max"] = float(max_match.group(1).replace(",", ""))
                
                volume_stats[day] = stats

        return SourceCV(
            resource_id=source_id,
            workspace_id=workspace_id,
            filename_pattern=filename_pattern,
            upload_schedule=upload_schedule,
            volume_stats=volume_stats
        )
