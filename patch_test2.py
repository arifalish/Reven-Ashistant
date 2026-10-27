with open('tests/test_smoke.py', 'r') as f:
    content = f.read()

content = content.replace('print("\n[Test]', 'print("\\n[Test]')

with open('tests/test_smoke.py', 'w') as f:
    f.write(content)
