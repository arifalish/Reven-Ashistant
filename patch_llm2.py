import re

with open('core/llm_router.py', 'r') as f:
    content = f.read()

# Replace the specific syntax errors using raw string replacements or fixing the newlines
content = content.replace('return "# Hook: Did you know 90% of agencies fail?\n\n**Intro:** Here is how to fix it.\n**Body:** 1. Leads. 2. Systems. 3. Sales.\n**Outro:** Subscribe."', 'return "# Hook: Did you know 90% of agencies fail?\\n\\n**Intro:** Here is how to fix it.\\n**Body:** 1. Leads. 2. Systems. 3. Sales.\\n**Outro:** Subscribe."')

with open('core/llm_router.py', 'w') as f:
    f.write(content)
