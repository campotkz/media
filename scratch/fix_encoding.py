
import sys

def fix_mojibake(text):
    # The mojibake is: UTF-8 -> interpreted as IBM866 -> saved as UTF-8
    # We need to go back: text (UTF-8) -> encode to IBM866 -> decode as UTF-8
    try:
        # First, try to encode back to the raw bytes that were interpreted as IBM866
        # The characters like '╨' are in the IBM866/CP866 range.
        raw_bytes = text.encode('cp866', errors='ignore')
        # Now decode those bytes as UTF-8
        return raw_bytes.decode('utf-8', errors='replace')
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python fix.py input.html output.html")
        sys.exit(1)
        
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        content = f.read()
        
    # We need to be careful. Some characters might not be part of the mojibake.
    # But usually, the whole file is affected.
    # Actually, let's try a simpler approach if the above doesn't work.
    # The '╨' character is U+2568.
    
    # Let's try the direct byte conversion if possible.
    # If the file was saved as UTF-8 but the content was already mojibaked:
    # ╨Р (U+2568, U+0420) 
    
    fixed = fix_mojibake(content)
    
    with open(sys.argv[2], 'w', encoding='utf-8') as f:
        f.write(fixed)
    print("Done")
