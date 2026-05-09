"""生成成绩核算系统图标 — 夏日清凉风"""
from PIL import Image, ImageDraw, ImageFont
import math

SIZE = 256
MARGIN = 16
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# --- 圆角矩形背景：海洋青 → 薄荷绿 渐变 ---
def rounded_rect(draw, xy, radius, fill):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)

# 渐变背景
for y in range(SIZE):
    ratio = y / SIZE
    r = int(8 + (45 - 8) * ratio)      # #0891b2 → #2dd4bf
    g = int(145 + (212 - 145) * ratio)
    b = int(178 + (191 - 178) * ratio)
    draw.line([(MARGIN, y), (SIZE - MARGIN, y)], fill=(r, g, b, 255))

# 圆角遮罩
mask = Image.new("L", (SIZE, SIZE), 0)
mask_draw = ImageDraw.Draw(mask)
mask_draw.rounded_rectangle((MARGIN, MARGIN, SIZE - MARGIN, SIZE - MARGIN), radius=36, fill=255)
img.putalpha(mask)

# 重新获取 draw（alpha 已更新）
draw = ImageDraw.Draw(img)

# --- 中央图案：打开的书本 + 上升的折线图 ---
cx, cy = SIZE // 2, SIZE // 2 + 8

# 书本 — 两页翻开的书
book_top = cy - 48
book_bot = cy + 20
book_left = cx - 60
book_right = cx + 60
book_cx = cx

# 左页
draw.polygon([
    (book_cx, book_top),
    (book_left + 8, book_top - 6),
    (book_left, book_bot),
    (book_cx, book_bot + 4),
], fill=(255, 255, 255, 230))

# 右页
draw.polygon([
    (book_cx, book_top),
    (book_right - 8, book_top - 6),
    (book_right, book_bot),
    (book_cx, book_bot + 4),
], fill=(255, 255, 255, 200))

# 书脊中线
draw.line([(book_cx, book_top - 2), (book_cx, book_bot + 4)], fill=(8, 145, 178, 180), width=2)

# 书页线条（横线）
for i in range(4):
    y_line = book_top + 16 + i * 10
    # 左页
    x_left = book_cx - 50 + i * 4
    draw.line([(x_left, y_line), (book_cx - 6, y_line)], fill=(8, 145, 178, 100), width=1)
    # 右页
    x_right = book_cx + 6
    draw.line([(x_right, y_line), (book_cx + 50 - i * 4, y_line)], fill=(8, 145, 178, 100), width=1)

# --- 上升折线图（在书本上方）---
chart_pts = [
    (cx - 40, cy - 56),
    (cx - 20, cy - 68),
    (cx, cy - 62),
    (cx + 20, cy - 76),
    (cx + 40, cy - 84),
]

# 折线下方填充（半透明白色）
fill_pts = list(chart_pts) + [(chart_pts[-1][0], chart_pts[0][1] + 10), (chart_pts[0][0], chart_pts[0][1] + 10)]
draw.polygon(fill_pts, fill=(255, 255, 255, 60))

# 折线
for i in range(len(chart_pts) - 1):
    draw.line([chart_pts[i], chart_pts[i + 1]], fill=(255, 255, 255, 240), width=3)

# 数据点圆圈
for pt in chart_pts:
    draw.ellipse((pt[0] - 4, pt[1] - 4, pt[0] + 4, pt[1] + 4), fill=(255, 255, 255, 255))

# 箭头（上升趋势）
ax, ay = chart_pts[-1]
draw.polygon([(ax + 2, ay - 2), (ax + 12, ay - 8), (ax + 4, ay + 6)], fill=(255, 255, 255, 240))

# --- 底部文字区域的微妙分隔线 ---
draw.line([(cx - 40, cy + 34), (cx + 40, cy + 34)], fill=(255, 255, 255, 80), width=1)

# --- 底部文字：成绩 ---
try:
    font = ImageFont.truetype("msyh.ttc", 28)
except:
    font = ImageFont.load_default()

text = "成绩"
bbox = draw.textbbox((0, 0), text, font=font)
tw = bbox[2] - bbox[0]
draw.text(((SIZE - tw) / 2, cy + 40), text, fill=(255, 255, 255, 240), font=font)

# 保存
img.save("icon.png", "PNG")

# 生成多尺寸 ico
sizes = [16, 32, 48, 64, 128, 256]
icons = []
for s in sizes:
    icons.append(img.resize((s, s), Image.LANCZOS))

icons[0].save("icon.ico", format="ICO", sizes=[(s, s) for s in sizes], append_images=icons[1:])
print("icon.ico + icon.png 已生成")
