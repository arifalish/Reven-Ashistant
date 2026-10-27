import re

with open('app/main.py', 'r') as f:
    content = f.read()

# Replace send_message to make sure it sends reply_markup if needed
content = content.replace(
    'message_id = await telegram_bot.send_message(\n                chat_id=chat_id, \n                text="🚀 **Live Mission Control Dashboard**\\n\\n⏳ Extracting intent and blueprinting strategy..."\n            )',
    'message_id = await telegram_bot.send_message(\n                chat_id=chat_id, \n                text="🚀 **Live Mission Control Dashboard**\\n\\n⏳ Extracting intent and blueprinting strategy..."\n            )'
)

with open('app/main.py', 'w') as f:
    f.write(content)
