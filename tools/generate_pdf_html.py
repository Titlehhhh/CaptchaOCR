import json
with open('image_b64.json') as f:
    b64 = json.load(f)

generators = [
    ("Archy-X / Krypton · map", [
        ("001", "32891", "Белый фон, серые цифры ~6 символов."),
        ("002", "CZKmG", "Буквы C, Z, k, m, G на белом фоне."),
        ("003", "4e6d7", "Цифры/буквы слегка размыты (визуально)."),
        ("004", "MEh7h", "Заглавная M + строчные буквы."),
        ("005", "8v0pN", "Цифра 8, буквы v, o, p, заглавная N."),
    ], "Archy-X/Krypton/map"),
    ("China2B2T / Captcha · wool", [
        ("001", "зелёный квадрат (ряд ~4, кол. 7 справа)", "Сетка красных квадратов; зелёная клетка выделена (визуально)."),
        ("002", "зелёный квадрат (ряд ~6, кол. 3 слева)", "Зелёная клетка в нижней части сетки."),
        ("003", "зелёный квадрат (средний ряд, левее центра)", ""),
        ("004", "зелёный квадрат (нижний ряд, слева)", ""),
        ("005", "зелёный квадрат (справа, средний-высокий ряд)", ""),
    ], "China2B2T/Captcha/wool"),
    ("FeelingAlive0 / AdvancedCaptcha · button", [
        ("001", "PressNow", "Инструкция «Click [PressNow] in black»; кнопка с RGB-сдвигом."),
        ("002", "Click", "Кнопка синего цвета с RGB-сдвигом."),
        ("003", "SelectMe", ""),
        ("004", "ChooseThis", ""),
        ("005", "Tap", ""),
    ], "FeelingAlive0/AdvancedCaptcha/button"),
    ("InstantlyMoist / Captcha · textcaptcha", [
        ("001", "pwvda (визуально) / pwwol (index)", "Цветные буквы с небольшим искажением."),
        ("002", "ocjg8 (визуально) / ocjys (index)", "Чёрные буквы, слегка размыты."),
        ("003", "grisa (визуально) / gjrfa (index)", "Буквы с сеткой линий поверх."),
        ("004", "ne+on (визуально) / noxen (index)", "Зелёные «ne» + красный «ton» с крестом на t."),
        ("005", "ffd* (визуально) / tffdx (index)", "Буквы с цветными звёздочками."),
    ], "InstantlyMoist/Captcha/textcaptcha"),
    ("JSH32 / Minecaptcha · map", [
        ("001", "7d0B", "Чёрный код из 4 символов; Tries left: 2."),
        ("002", "BGwq", "Tries left: 1."),
        ("003", "oYFc", "Tries left: 2."),
        ("004", "EuFD", "Tries left: 1."),
        ("005", "LbFd", "Tries left: 1."),
    ], "JSH32/Minecaptcha/map"),
    ("Joey61021 / captcha · colorgui", [
        ("001", "Red (визуально) / index: Red", "Красный квадрат справа-вверху."),
        ("002", "Orange (визуально) / index: Orange", "Оранжевый квадрат внизу."),
        ("003", "Purple (визуально) / index: Pink", "Фиолетовый квадрат справа."),
        ("004", "Pink (визуально) / index: Pink", "Розовый квадрат справа в середине."),
        ("005", "Green (визуально) / index: Pink", "Зелёный квадрат слева-вверху (визуально)."),
    ], "Joey61021/captcha/colorgui"),
    ("LagBug / XProtect · code", [
        ("001", "bQvHQK", "Красные буквы с чёрными штрихами; точный текст из index."),
        ("002", "3Vd9rD", ""),
        ("003", "7ynZO6", ""),
        ("004", "Jv02Ic", ""),
        ("005", "t9Fqcc", ""),
    ], "LagBug/XProtect/code"),
    ("jonesdevelopment / sonar · complex", [
        ("001", "noy", "Буквы с цветными линиями и точками; визуально noy (или ngy)."),
        ("002", "tobn", "«to bn» / «tobn»; синие, красные, зелёные линии."),
        ("003", "mkrv", "«mkr v» / «mkry» — визуальный ответ mkrv."),
        ("004", "cibp", "Чёткие буквы «cibp»."),
        ("005", "etof", "«etof» / «etafi» — предпочтительно etof."),
    ], "jonesdevelopment/sonar/complex"),
    ("haq / mapcha · map", [
        ("001", "M0Vk", "Тёмный фон, таймеры, белый код с шумом."),
        ("002", "IhzG", ""),
        ("003", "1bDH", ""),
        ("004", "NfB3", ""),
        ("005", "iePG", ""),
    ], "haq/mapcha/map"),
    ("irootdev / AnBot · captcha", [
        ("001", "eth", "Простая текстовая капча с буквами."),
        ("002", "120", "Трёхзначное число."),
        ("003", "4ai", ""),
        ("004", "950", ""),
        ("005", "3v1", ""),
    ], "irootdev/AnBot/captcha"),
]

html_parts = []
html_parts.append('''<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Captcha Dataset — PDF-версия с встроенными изображениями</title>
<style>
@page { size: A4 portrait; margin: 10mm; @bottom-right { content: "Стр. " counter(page); font-size: 8pt; color: #666; } }
body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; color: #222; line-height: 1.35; font-size: 9pt; }
h1 { font-size: 16pt; color: #1a2e3a; border-bottom: 2px solid #8cf; padding-bottom: 6pt; margin-top: 0; letter-spacing: -0.02em; }
h2 { font-size: 11pt; color: #1a5a8a; margin-top: 14pt; margin-bottom: 4pt; border-left: 3px solid #8cf; padding-left: 6pt; }
.subtitle { color: #555; font-size: 8pt; margin-bottom: 10pt; }
.grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6pt; margin-top: 4pt; }
.card { border: 1px solid #bbb; border-radius: 5pt; padding: 5pt; text-align: center; background: #fdfdfd; page-break-inside: avoid; }
.card img { max-width: 100%; height: 60pt; object-fit: contain; display: block; margin: 0 auto 3pt; border: 1px solid #ddd; border-radius: 3pt; }
.card .id { font-family: monospace; font-size: 6pt; color: #777; }
.card .solved { font-weight: 700; color: #1a6; font-size: 8pt; }
.card .desc { font-size: 6pt; color: #555; line-height: 1.2; margin-top: 1pt; }
footer { margin-top: 14pt; padding-top: 4pt; border-top: 1pt solid #ccc; font-size: 7pt; color: #888; text-align: center; }
</style>
</head><body>
<h1>Captcha Dataset — 10 генераторов × 5 капч</h1>
<div class="subtitle">PDF с встроенными изображениями (base64) · 50 капч · решения из визуального анализа и index.html</div>
''')

for title, items, folder in generators:
    html_parts.append(f'<h2>{title}</h2>\n<div class="grid">\n')
    for item_id, solved, desc in items:
        # Find matching image in base64 by normalizing paths
        b64_key = None
        target_path = f"out/{folder}/{item_id.zfill(3)}.png".replace('\\', '/')
        target_path_2 = target_path.replace('/', '\\')
        for k in b64:
            k_norm = k.replace('\\', '/')
            k_norm_back = k.replace('/', '\\')
            if k_norm == target_path or k_norm_back == target_path_2 or k == target_path or k == target_path_2:
                b64_key = k
                break
        if b64_key is None:
            for k in b64:
                k_norm = k.replace('\\', '/')
                if folder.replace('\\', '/') in k_norm and item_id.zfill(3) in k_norm and k_norm.endswith('.png'):
                    b64_key = k
                    break
        if b64_key:
            img_src = f"data:image/png;base64,{b64[b64_key]}"
            img_tag = f'<img src="{img_src}" alt="{item_id}" />'
        else:
            img_tag = '<div style="width:50pt;height:50pt;background:#eee;border:1px dashed #aaa;line-height:50pt;text-align:center;font-size:6pt;color:#aaa;margin:0 auto;">нет</div>'
        html_parts.append(
            f'<div class="card">\n{img_tag}\n<div class="id">{item_id}</div>\n<div class="solved">{solved}</div>\n<div class="desc">{desc}</div>\n</div>\n'
        )
    html_parts.append('</div>\n')

html_parts.append('<footer>Создано в рамках CaptchaOCR · 10 генераторов × 5 капч · данные из out/index.html + визуальная интерпретация субагентами</footer>\n</body></html>')

with open('captcha_pdf_embedded.html', 'w', encoding='utf-8') as f:
    f.write(''.join(html_parts))
print('captcha_pdf_embedded.html written, chars:', len(''.join(html_parts)))
