with open('core/llm_router.py', 'r') as f:
    content = f.read()

import re
content = re.sub(r'Open to a chat\?"\n', '', content)

with open('core/llm_router.py', 'w') as f:
    f.write(content)
