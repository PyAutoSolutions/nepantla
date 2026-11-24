import json, re, sys
from PIL import Image, ImageDraw
prefix, out = sys.argv[1], sys.argv[2]
d = json.load(open(f"{prefix}-zonas.json"))
img = Image.open(f"{prefix}-beauty.png").convert("RGBA")
bg = Image.new("RGBA", img.size, (255, 255, 255, 255)); bg.alpha_composite(img)
s = img.width / d["w"]
dr = ImageDraw.Draw(bg)
for zid, path, cx, cy, area in d["zonas"]:
    for sub in path.split("z"):
        if not sub: continue
        nums = list(map(int, re.findall(r"-?\d+", sub)))
        x, y = nums[0], nums[1]; pts = [(x * s, y * s)]
        for i in range(2, len(nums), 2):
            x += nums[i]; y += nums[i + 1]; pts.append((x * s, y * s))
        dr.line(pts + [pts[0]], fill=(255, 255, 255, 255), width=2)
    dr.text((cx * s - 15, cy * s - 5), zid.split("-", 1)[1][:9], fill=(0, 0, 0, 255))
bg.convert("RGB").save(out, quality=88)
