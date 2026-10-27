import re
with open('core/llm_router.py', 'r') as f:
    content = f.read()

content = content.replace('return "# Strategy & Unit Economics\n\nBased on your thought, here is the robust go-to-market plan.\n\n## Unit Economics\n- **CAC**: $50\n- **LTV**: $1500\n- **Margin**: 85%\n\n## Plan\n1. Scrape leads.\n2. Cold email sequence.\n3. Content engine."', 'return "# Strategy & Unit Economics\\n\\nBased on your thought, here is the robust go-to-market plan.\\n\\n## Unit Economics\\n- **CAC**: $50\\n- **LTV**: $1500\\n- **Margin**: 85%\\n\\n## Plan\\n1. Scrape leads.\\n2. Cold email sequence.\\n3. Content engine."')

with open('core/llm_router.py', 'w') as f:
    f.write(content)
