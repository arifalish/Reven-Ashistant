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
        if 'return "# Strategy & Unit Economics' in line:
            f.write('                return "# Strategy & Unit Economics\\n\\nBased on your thought, here is the robust go-to-market plan.\\n\\n## Unit Economics\\n- **CAC**: $50\\n- **LTV**: $1500\\n- **Margin**: 85%\\n\\n## Plan\\n1. Scrape leads.\\n2. Cold email sequence.\\n3. Content engine."\n')
            continue
        if 'return "<!DOCTYPE html>' in line:
            f.write('                return "<!DOCTYPE html>\\n<html lang=\'en\'>\\n<head>\\n<title>MVP</title>\\n<style>body{font-family:sans-serif;}</style>\\n</head>\\n<body>\\n<h1>Fully Functional MVP</h1>\\n<button onclick=\'alert(\\"Action!\\")\'>Get Started</button>\\n</body>\\n</html>"\n')
            continue

        # Skip broken lines
        if 'Hi {{name}}, noticed your team is growing' in line or \
           '1/ Find a hungry market' in line or \
           '2/ Build an offer they feel stupid saying no to' in line or \
           '3/ Send 100 DMs a day.' in line or \
           'Based on your thought' in line or \
           '- **CAC**' in line or \
           '- **LTV**' in line or \
           '- **Margin**' in line or \
           '## Plan' in line or \
           '1. Scrape leads.' in line or \
           '2. Cold email sequence.' in line or \
           '3. Content engine.' in line or \
           "<html lang='en'>" in line or \
           "<head>" in line or \
           "<title>MVP</title>" in line or \
           "<style>body{font-family:sans-serif;}</style>" in line or \
           "</head>" in line or \
           "<body>" in line or \
           "<h1>Fully Functional MVP</h1>" in line or \
           "<button onclick='alert(\"Action!\")'>Get Started</button>" in line or \
           "</body>" in line or \
           "</html>" in line or \
           "**Intro:**" in line or \
           "**Body:**" in line or \
           "**Outro:**" in line or \
           'Open to a chat?"' in line:
            continue

        f.write(line)
