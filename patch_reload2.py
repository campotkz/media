with open('api/index.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Fix the bug with sorting by "created_at", if created_at is missing, sort by empty string
old_sort_0 = "clean_apps = sorted(unique_map.values(), key=lambda x: x.get('created_at'))"
new_sort_0 = "clean_apps = sorted(unique_map.values(), key=lambda x: x.get('created_at') or '')"

code = code.replace(old_sort_0, new_sort_0)

with open('api/index.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Fixed created_at sorting in reload")
