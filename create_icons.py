from PIL import Image, ImageDraw, ImageFont
import os

os.makedirs('static/icons', exist_ok=True)

for size in [192, 512]:
    img = Image.new('RGB', (size, size), '#0a0a0f')
    draw = ImageDraw.Draw(img)

    # Hintergrund-Gradient simulieren (orangener Kreis)
    center = size // 2
    radius = size // 2 - size // 10

    # Äußerer Glow
    for i in range(20):
        r = radius + 20 - i
        alpha = int(255 * (i / 20))
        draw.ellipse([center-r, center-r, center+r, center+r],
                     fill=None,
                     outline=(255, 107, 53, alpha))

    # Hauptkreis (Gradient-Effekt durch zwei Kreise)
    draw.ellipse([center-radius, center-radius, center+radius, center+radius],
                 fill='#FF6B35')

    # Innerer Kreis etwas dunkler für Tiefe
    inner_r = int(radius * 0.85)
    draw.ellipse([center-inner_r, center-inner_r+size//15, center+inner_r, center+inner_r+size//15],
                 fill='#e03e00')

    # Hauptkreis nochmal drüber
    draw.ellipse([center-radius, center-radius, center+radius, center+radius],
                 fill='#FF6B35')

    # Text "TT"
    font_size = size // 3
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            font = ImageFont.load_default()

    draw.text((center, center), "TT", fill='white', font=font, anchor='mm')

    # Kleine Hantel/Fitness-Symbol Linie unter dem Text
    bar_y = center + font_size // 2 + size // 20
    bar_width = size // 4
    bar_height = size // 40
    draw.rounded_rectangle(
        [center - bar_width, bar_y, center + bar_width, bar_y + bar_height],
        radius=bar_height // 2,
        fill='white'
    )

    img.save(f'static/icons/icon-{size}x{size}.png')
    print(f'Icon {size}x{size} erstellt')

# Auch als apple-touch-icon
img_apple = Image.open('static/icons/icon-192x192.png')
img_apple.save('static/icons/apple-touch-icon.png')
print('Apple Touch Icon erstellt')