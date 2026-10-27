import re

with open('core/llm_router.py', 'r') as f:
    content = f.read()

content = content.replace('alert("Action!")', "alert('Action!')")

with open('core/llm_router.py', 'w') as f:
    f.write(content)
