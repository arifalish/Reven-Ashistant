with open('core/llm_router.py', 'r') as f:
    lines = f.readlines()

with open('core/llm_router.py', 'w') as f:
    for line in lines:
        if 'return "# Hook: Did you know 90% of agencies fail?' in line:
            f.write('                    return "# Hook: Did you know 90% of agencies fail?\\n\\n**Intro:** Here is how to fix it.\\n**Body:** 1. Leads. 2. Systems. 3. Sales.\\n**Outro:** Subscribe."\n')
            continue
        if 'return "Subject: Quick question about {{company}}' in line:
            f.write('                    return "Subject: Quick question about {{company}}\\n\\nHi {{name}}, noticed your team is growing. We help agencies scale.\\n\\nOpen to a chat?"\n')
            continue
        if 'return "🧵 The ultimate thread on scaling your business to $10k/mo.' in line:
            f.write('                    return "🧵 The ultimate thread on scaling your business to $10k/mo.\\n\\n1/ Find a hungry market...\\n\\n2/ Build an offer they feel stupid saying no to...\\n\\n3/ Send 100 DMs a day."\n')
            continue

        # Skip broken lines
        if 'Hi {{name}}, noticed your team is growing' in line or \
           '1/ Find a hungry market' in line or \
           '2/ Build an offer they feel stupid saying no to' in line or \
           '3/ Send 100 DMs a day.' in line or \
           "**Intro:**" in line or \
           "**Body:**" in line or \
           "**Outro:**" in line or \
           'Open to a chat?"' in line:
            continue

        f.write(line)
