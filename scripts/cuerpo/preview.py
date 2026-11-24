import sys, numpy as np, colorsys
from PIL import Image, ImageDraw
from zones import *
from mhload import HERE

OUT = HERE / "trabajo"
OUT.mkdir(exist_ok=True)

def zones_for(sex):
    V, VT, F, FT, G, M, bones, L, body = build(sex)
    cats = face_landmarks(M, F, G, bones, L)
    res = []
    for i in body:
        f = F[i]
        cs = [cats[v] for v in f]
        cat = max(set(cs), key=cs.count)
        c = M[f].mean(axis=0)
        res.append(classify(c, cat, L, sex))
    return M, [F[i] for i in body], res, L

def draw(M, faces, labels, view, path, scale=40, crop=None):
    P = M.copy()
    if view == "e": P[:, 0] *= -1; P[:, 2] *= -1
    xs, ys = P[:, 0], P[:, 1]
    if crop: x0, x1, y0, y1 = crop
    else: x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    Wd, Ht = int((x1 - x0) * scale) + 20, int((y1 - y0) * scale) + 20
    img = Image.new("RGB", (Wd, Ht), "white"); dr = ImageDraw.Draw(img)
    order = np.argsort([P[f][:, 2].mean() for f in faces])
    names = sorted(set(labels)); col = {}
    for k, n in enumerate(names):
        r, g, b = colorsys.hsv_to_rgb((k * 0.618) % 1, 0.55, 0.95); col[n] = (int(r*255), int(g*255), int(b*255))
    pts = {}
    for i in order:
        f = faces[i]
        q = [((P[v, 0] - x0) * scale + 10, (y1 - P[v, 1]) * scale + 10) for v in f]
        dr.polygon(q, fill=col[labels[i]], outline=None)
        pts.setdefault(labels[i], []).append(np.mean(q, axis=0))
    for n, p in pts.items():
        p = np.mean(p, axis=0); dr.text((p[0] - 12, p[1] - 4), n.split("-", 1)[1][:10], fill="black")
    img.save(path)

if __name__ == "__main__":
    for sex in ("male", "female"):
        M, faces, res, L = zones_for(sex)
        draw(M, faces, [r["f"] for r in res], "f", f"{OUT}/prev-{sex}-f.png")
        draw(M, faces, [r["e"] for r in res], "e", f"{OUT}/prev-{sex}-e.png")
        y = L["l-eye"][1]
        draw(M, faces, [r["c"] for r in res], "f", f"{OUT}/prev-{sex}-c.png", scale=160, crop=(-1.1, 1.1, y - 1.6, y + 1.3))
        print(sex, "zones", len(set(r["f"] for r in res)), len(set(r["e"] for r in res)), len(set(r["c"] for r in res)))
