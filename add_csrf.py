import os
import re

templates_dir = 'templates'
form_tag_pattern = re.compile(r'(<form[^>]*>)', re.IGNORECASE)
csrf_input = '\n    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>'

for filename in os.listdir(templates_dir):
    if filename.endswith('.html'):
        filepath = os.path.join(templates_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'csrf_token()' not in content:
            new_content = form_tag_pattern.sub(r'\1' + csrf_input, content)
            if new_content != content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Added CSRF to {filename}")

print("CSRF Injection complete!")
