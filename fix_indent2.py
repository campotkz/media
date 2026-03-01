with open('api/index.py', 'r') as f:
    lines = f.readlines()

with open('api/index.py', 'w') as f:
    for line in lines:
        if line == 'from concurrent.futures import ThreadPoolExecutor\n' and 'import threading' in lines[lines.index(line)-1]:
            f.write('                from concurrent.futures import ThreadPoolExecutor\n')
        else:
            f.write(line)
