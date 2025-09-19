import re
import os

def parse_contents(data):
    """
    Extracts the first 'content' value from MessageOutputEntry objects.
    Returns an int if possible, otherwise returns the string.
    """
    # Convert to string if not already
    if not isinstance(data, str):
        data = str(data)

    # Flexible regex: handles single or double quotes
    match = re.search(r"MessageOutputEntry\(content=['\"](.*?)['\"]", data)
    if not match:
        return None

    content = match.group(1).strip()  # remove extra whitespace

    # Try to convert to int
    try:
        return int(content)
    except ValueError:
        print(f"Failed to convert '{content}' to int.")
        return content  # fallback to string if not a number

def write_to_file(data, filename):
    if not isinstance(data, str) or data is None:
        return 

    with open(filename, 'a') as f:
        f.write(data + "\n")  

def manage_log(filename, max_lines=100):
    if not os.path.exists(filename):
        return  

    with open(filename, 'r') as f:
        line_count = sum(1 for _ in f)

    if line_count >= max_lines:
        os.remove(filename)
        print(f"Deleted {filename} (had {line_count} lines).")
        return
    
