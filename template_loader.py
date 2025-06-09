import os
import json

def load_all_templates():
    templates = {}
    for file_name in ["templates/global_templates.json", "templates/user_templates.json"]:
        full_path = os.path.join(file_name)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "templates" in data:
                    templates.update(data["templates"])
    return templates

def get_best_template(df, templates):
    best_score = -1
    best_template_name = None
    best_mapping = {}

    for name, mapping in templates.items():
        score = 0
        matched = {}
        for standard_key, column_name in mapping.items():
            for col in df.columns:
                if col.strip().lower() == column_name.strip().lower():
                    score += 1
                    matched[standard_key] = col
                    break
        if score > best_score:
            best_score = score
            best_template_name = name
            best_mapping = matched

    return best_template_name, best_mapping

def auto_header_index(df):
    max_non_empty = 0
    header_index = 0

    for i in range(min(10, len(df))):
        non_empty_count = df.iloc[i].count()
        if non_empty_count > max_non_empty:
            max_non_empty = non_empty_count
            header_index = i

    return header_index
