import os
import json
import time
from datetime import datetime
from tabulate import tabulate
from .input_preparer import InputPreparer
from .agent_adk import IncidentDetectionAgent
from .models import IncidentSeverity

# Ground Truth for 2025-09-10 based on Feedback
GROUND_TRUTH = {
    "220504": IncidentSeverity.URGENT,
    "220505": IncidentSeverity.URGENT,
    "220506": IncidentSeverity.URGENT,
    "196125": IncidentSeverity.URGENT,
    "195385": IncidentSeverity.URGENT,
}

def evaluate_agent(date_str: str, data_dir: str):
    print(f"Starting Evaluation for {date_str}...")
    
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not set.")
        return

    # 1. Prepare Inputs
    preparer = InputPreparer(data_dir)
    files_data = preparer.load_files_data(date_str)
    last_week_files_data = preparer.load_last_weekday_files(date_str)
    
    # Filter to only run on Ground Truth sources to save time
    target_sources = list(GROUND_TRUTH.keys())
    eval_sources = target_sources 
    
    cvs = {}
    for source_id in eval_sources:
        cv = preparer.parse_cv(source_id)
        if cv:
            cvs[source_id] = cv
            
    # Filter files data
    files_data = {k: files_data[k] for k in eval_sources}
    print(f"Evaluating {len(eval_sources)} sources: {eval_sources}")

    # 2. Run Agent
    agent = IncidentDetectionAgent(api_key=api_key)
    context = {"date": datetime.strptime(date_str, "%Y-%m-%d")}
    
    # We need to run generation manually here to see progress if we want, 
    # but generate_global_report does it all. 
    # Let's trust it will be faster with 5 sources.
    report = agent.generate_global_report(date_str, files_data, last_week_files_data, cvs, context)
    
    # 3. Calculate Metrics
    tp = 0 # True Positive (Predicted Urgent, Actual Urgent)
    fp = 0 # False Positive (Predicted Urgent, Actual Not Urgent)
    fn = 0 # False Negative (Predicted Not Urgent, Actual Urgent)
    tn = 0 # True Negative (Predicted Not Urgent, Actual Not Urgent)
    
    results = []
    
    for sr in report.source_reports:
        predicted = sr.status
        actual = GROUND_TRUTH.get(sr.source_id, IncidentSeverity.ALL_GOOD) # Default to ALL_GOOD/ATTENTION if not in GT
        
        # We treat URGENT as the positive class we care about most
        is_predicted_urgent = (predicted == IncidentSeverity.URGENT)
        is_actual_urgent = (actual == IncidentSeverity.URGENT)
        
        if is_predicted_urgent and is_actual_urgent:
            tp += 1
            res = "TP"
        elif is_predicted_urgent and not is_actual_urgent:
            fp += 1
            res = "FP"
        elif not is_predicted_urgent and is_actual_urgent:
            fn += 1
            res = "FN"
        else:
            tn += 1
            res = "TN"
            
        results.append([sr.source_id, actual.value, predicted.value, res])

    # 4. Print Results
    print("\n" + "="*50)
    print("EVALUATION RESULTS")
    print("="*50 + "\n")
    print(tabulate(results, headers=["Source", "Actual", "Predicted", "Result"], tablefmt="grid"))
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    print(f"\nMetrics (Class: URGENT):")
    print(f"Precision: {precision:.2f}")
    print(f"Recall:    {recall:.2f}")
    print(f"F1 Score:  {f1:.2f}")
    
    return f1

if __name__ == "__main__":
    evaluate_agent("2025-09-10", "data")
