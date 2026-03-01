with open('api/index.py', 'r') as f:
    lines = f.readlines()

with open('api/index.py', 'w') as f:
    for i, line in enumerate(lines):
        if line.strip() == 'from concurrent.futures import ThreadPoolExecutor':
            if i != 14:
                # Need to match indentation of previous line
                prev_indent = len(lines[i-1]) - len(lines[i-1].lstrip())
                f.write(' ' * prev_indent + 'from concurrent.futures import ThreadPoolExecutor\n')
            else:
                f.write('from concurrent.futures import ThreadPoolExecutor\n')
        else:
            f.write(line)
