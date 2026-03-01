with open('api/index.py', 'r') as f:
    lines = f.readlines()

with open('api/index.py', 'w') as f:
    for i, line in enumerate(lines):
        if i == 14:  # line 15 is index 14
            f.write('from concurrent.futures import ThreadPoolExecutor\n')
        else:
            f.write(line)
