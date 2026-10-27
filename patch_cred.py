with open('core/credential_vault.py', 'r') as f:
    content = f.read()

content = content.replace('f"⚠️ Agent needs API Key for {service_name}. Get it here: {setup_url}\nReply on Telegram to securely inject."', 'f"⚠️ Agent needs API Key for {service_name}. Get it here: {setup_url}\\nReply on Telegram to securely inject."')

with open('core/credential_vault.py', 'w') as f:
    f.write(content)
