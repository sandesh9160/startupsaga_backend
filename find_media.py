import re

with open(r'd:\Tech Sprout\StartupSaga2\startupsaga-stag\Backend\cms\api_views.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'media_list' in line:
        start = max(0, i - 15)
        end = min(len(lines), i + 50)
        print(f"--- MATCH AROUND LINE {i+1} ---")
        for j in range(start, end):
            print(f"{j+1}: {lines[j].strip()}")
        break
