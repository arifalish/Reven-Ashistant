with open('core/llm_router.py', 'r') as f:
    lines = f.readlines()

with open('core/llm_router.py', 'w') as f:
    for line in lines:
        if 'return "Subject: Quick question about {{company}}' in line:
            f.write('                    return "Subject: Quick question about {{company}}\\n\\nHi {{name}}, noticed your team is growing. We help agencies scale.\\n\\nOpen to a chat?"\n')
        elif 'return "🧵 The ultimate thread on scaling your business to $10k/mo.' in line:
            f.write('                    return "🧵 The ultimate thread on scaling your business to $10k/mo.\\n\\n1/ Find a hungry market...\\n\\n2/ Build an offer they feel stupid saying no to...\\n\\n3/ Send 100 DMs a day."\n')
        elif 'return "# Strategy & Unit Economics' in line:
             f.write('                return "# Strategy & Unit Economics\\n\\nBased on your thought, here is the robust go-to-market plan.\\n\\n## Unit Economics\\n- **CAC**: $50\\n- **LTV**: $1500\\n- **Margin**: 85%\\n\\n## Plan\\n1. Scrape leads.\\n2. Cold email sequence.\\n3. Content engine."\n')
        elif 'return "<!DOCTYPE html>' in line:
             f.write('                return "<!DOCTYPE html>\\n<html lang=\'en\'>\\n<head>\\n<title>MVP</title>\\n<style>body{font-family:sans-serif;}</style>\\n</head>\\n<body>\\n<h1>Fully Functional MVP</h1>\\n<button onclick=\'alert(\\"Action!\\")\'>Get Started</button>\\n</body>\\n</html>"\n')
        elif 'Hi {{name}}, noticed your team is growing' in line:
            pass # Skip the broken lines
        elif '1/ Find a hungry market' in line:
            pass
        elif '2/ Build an offer they feel stupid saying no to' in line:
            pass
        elif '3/ Send 100 DMs a day.' in line:
            pass
        elif 'Based on your thought' in line:
            pass
        elif '- **CAC**' in line:
            pass
        elif '- **LTV**' in line:
            pass
        elif '- **Margin**' in line:
            pass
        elif '## Plan' in line:
            pass
        elif '1. Scrape leads.' in line:
            pass
        elif '2. Cold email sequence.' in line:
            pass
        elif '3. Content engine.' in line:
            pass
        elif "<html lang='en'>" in line:
            pass
        elif "<head>" in line:
            pass
        elif "<title>MVP</title>" in line:
            pass
        elif "<style>body{font-family:sans-serif;}</style>" in line:
            pass
        elif "</head>" in line:
            pass
        elif "<body>" in line:
            pass
        elif "<h1>Fully Functional MVP</h1>" in line:
            pass
        elif "<button onclick='alert(\"Action!\")'>Get Started</button>" in line:
            pass
        elif "</body>" in line:
            pass
        elif "</html>" in line:
            pass
        elif "**Intro:**" in line:
            pass
        elif "**Body:**" in line:
            pass
        elif "**Outro:**" in line:
            pass
        else:
            f.write(line)
