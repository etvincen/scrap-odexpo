import json
import pandas as pd

def export_json_to_csv(json_file_path: str, csv_file_path: str):
    "Export non null csv columns to json"
    df = pd.read_csv(json_file_path)
    df = df.dropna(axis=1)
    df.to_json(csv_file_path, orient='records', indent=4)


csv_path = "wappalyzer_fabienne-vincent-odexpo.com.csv"
json_path = "wappalyzer_fabienne-vincent-odexpo.com.json"

export_json_to_csv(csv_path, json_path)