import re

with open('app/main.py', 'r') as f:
    content = f.read()

content = content.replace(
    'text="🚀 **Live Mission Control Dashboard**\n\n⏳ Extracting intent and blueprinting strategy..."',
    'text="🚀 **Live Mission Control Dashboard**\\n\\n⏳ Extracting intent and blueprinting strategy..."'
)

with open('app/main.py', 'w') as f:
    f.write(content)
