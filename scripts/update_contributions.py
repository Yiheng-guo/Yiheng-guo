"""Render a compact contribution calendar from GitHub's actual public data."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
USER = os.environ.get('PROFILE_USER', 'Yiheng-guo')
end = dt.datetime.now(dt.timezone.utc).date()
start = end - dt.timedelta(days=89)
query = '''query($login:String!,$from:DateTime!,$to:DateTime!) {
 user(login:$login) { contributionsCollection(from:$from,to:$to) {
 contributionCalendar { weeks { contributionDays { date contributionCount contributionLevel } } }
 } } }'''
payload = {'query': query, 'variables': {'login': USER,
    'from': f'{start}T00:00:00Z', 'to': f'{end}T23:59:59Z'}}
result = subprocess.run(['gh', 'api', 'graphql', '--input', '-'],
    input=json.dumps(payload), text=True, capture_output=True)
if result.returncode:
    raise RuntimeError('GitHub contribution query failed; previous chart was preserved.')
data = json.loads(result.stdout)
if data.get('errors'):
    raise RuntimeError('GitHub returned GraphQL errors; previous chart was preserved.')
colors = {'NONE': '#161b22', 'FIRST_QUARTILE': '#0e4429',
    'SECOND_QUARTILE': '#006d32', 'THIRD_QUARTILE': '#26a641',
    'FOURTH_QUARTILE': '#39d353'}
days = {}
for week in data['data']['user']['contributionsCollection']['contributionCalendar']['weeks']:
    for item in week['contributionDays']:
        date = dt.date.fromisoformat(item['date'])
        if start <= date <= end:
            assert isinstance(item['contributionCount'], int) and item['contributionCount'] >= 0
            assert item['contributionLevel'] in colors
            assert date not in days
            days[date] = item
assert set(days) == {start + dt.timedelta(days=i) for i in range(90)}, 'Incomplete calendar'
first_sunday = start - dt.timedelta(days=(start.weekday() + 1) % 7)
ns = 'http://www.w3.org/2000/svg'
ET.register_namespace('', ns)
svg = ET.Element(f'{{{ns}}}svg', {'viewBox': '0 0 420 274', 'width': '420',
    'height': '274', 'role': 'img', 'aria-labelledby': 'title desc'})
def add(tag, attributes, text=None):
    node = ET.SubElement(svg, f'{{{ns}}}{tag}', attributes)
    if text is not None:
        node.text = text
    return node
add('title', {'id': 'title'}, f'{USER}: recent 90 days of GitHub contributions')
total = sum(item['contributionCount'] for item in days.values())
add('desc', {'id': 'desc'}, f'{start} to {end}, {total} contributions. Dates use UTC.')
add('rect', {'width':'419', 'height':'273', 'x':'0.5', 'y':'0.5', 'rx':'12',
    'fill':'#0d1117', 'stroke':'#30363d'})
def label(x, y, text, size='12', color='#8b949e'):
    return add('text', {'x':str(x), 'y':str(y), 'fill':color,
        'font-family':'-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif',
        'font-size':size}, text)
label(22, 30, 'Recent Contributions · 最近 90 天', '16', '#e6edf3')
label(22, 50, f'{total} contributions  ·  {start} — {end}', '12')
for row, text in ((1, 'Mon'), (3, 'Wed'), (5, 'Fri')):
    label(15, 88 + row * 24, text, '10')
seen_months = set()
for date, item in sorted(days.items()):
    col = (date - first_sunday).days // 7
    row = (date.weekday() + 1) % 7
    month = (date.year, date.month)
    if month not in seen_months:
        label(52 + col * 24, 72, date.strftime('%b'), '10')
        seen_months.add(month)
    cell = add('rect', {'x':str(52 + col * 24), 'y':str(78 + row * 24),
        'width':'19', 'height':'19', 'rx':'3', 'fill':colors[item['contributionLevel']],
        'data-date':str(date), 'data-count':str(item['contributionCount'])})
    ET.SubElement(cell, f'{{{ns}}}title').text = f'{date}: {item["contributionCount"]} contributions'
label(22, 259, 'GitHub activity · UTC', '10')
label(232, 259, 'Less', '10')
for i, color in enumerate(colors.values()):
    add('rect', {'x':str(260 + i * 19), 'y':'248', 'width':'14', 'height':'14',
        'rx':'2', 'fill':color})
label(360, 259, 'More', '10')
output = ROOT / 'assets/recent-contributions.svg'
content = ET.tostring(svg, encoding='unicode') + '\n'
if not output.exists() or output.read_text() != content:
    temp = output.with_suffix('.tmp')
    temp.write_text(content)
    temp.replace(output)
print(f'Validated 90 calendar days: {start} to {end}; {total} contributions.')
