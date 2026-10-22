import base64, os, json, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import OUT, results

gen_folders = [
    'Archy-X/Krypton/map',
    'China2B2T/Captcha/wool',
    'FeelingAlive0/AdvancedCaptcha/button',
    'InstantlyMoist/Captcha/textcaptcha',
    'JSH32/Minecaptcha/map',
    'Joey61021/captcha/colorgui',
    'LagBug/XProtect/code',
    'jonesdevelopment/sonar/complex',
    'haq/mapcha/map',
    'irootdev/AnBot/captcha',
]

mapping = {}
for rel in gen_folders:
    folder = os.path.join(OUT, rel.replace('/', os.sep))
    png_files = sorted([f for f in os.listdir(folder) if f.endswith('.png')])[:5]
    for png in png_files:
        path = os.path.join(folder, png)
        rel_path = os.path.join('dataset', 'out', rel.replace('/', os.sep), png).replace('\\', '/')
        with open(path, 'rb') as img:
            mapping[rel_path] = base64.b64encode(img.read()).decode('ascii')
        print(rel_path)

with open(results('image_b64.json'), 'w') as f:
    json.dump(mapping, f)
print('Total:', len(mapping))
