"""Convierte los renders (imagen + mapa de zonas) en WebP + trazos SVG por zona."""
import json, sys, cv2, numpy as np
from scipy import ndimage
from PIL import Image

from pathlib import Path
ZONES = json.load(open(Path(__file__).resolve().parent / "zone_ids.json"))
SCALE = 0.5  # coordenadas del viewBox = píxeles del render * SCALE

def labels(prefix):
    im = cv2.imread(f"{prefix}-id.png", cv2.IMREAD_UNCHANGED)
    ids = np.rint(im[..., 2].astype(np.float64) / 257.0).astype(np.int32)
    ids[im[..., 3] < 32768] = 0
    beauty = np.array(Image.open(f"{prefix}-beauty.png"))
    sil = beauty[..., 3] > 110
    # 1) cada píxel del cuerpo recibe la zona más cercana
    missing = sil & (ids == 0)
    if missing.any():
        idx = ndimage.distance_transform_edt(ids == 0, return_distances=False, return_indices=True)
        ids = np.where(missing, ids[idx[0], idx[1]], ids)
    ids[~sil] = 0
    # 2) bordes suaves: voto por mayoría con desenfoque
    present = [z for z in np.unique(ids) if z]
    best = np.full(ids.shape, -1.0, np.float32); out = np.zeros_like(ids)
    for z in present:
        m = cv2.GaussianBlur((ids == z).astype(np.float32), (0, 0), 5.0)
        better = m > best; best[better] = m[better]; out[better] = z
    out[~sil] = 0
    # 3) sin islitas: las piezas chicas pasan a la zona vecina
    for _ in range(2):
        changed = False
        for z in present:
            n, comp, stats, _c = cv2.connectedComponentsWithStats((out == z).astype(np.uint8), 8)
            if n <= 2: continue
            keep = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
            for k in range(1, n):
                if k != keep and stats[k, cv2.CC_STAT_AREA] < 4000:
                    out[comp == k] = 0; changed = True
        hole = sil & (out == 0)
        if hole.any():
            idx = ndimage.distance_transform_edt(out == 0, return_distances=False, return_indices=True)
            out = np.where(hole, out[idx[0], idx[1]], out)
        if not changed: break
    return out, beauty

def paths(out):
    res = []
    for z in [z for z in np.unique(out) if z]:
        mask = (out == z).astype(np.uint8)
        cs, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        parts = []
        for c in cs:
            if cv2.contourArea(c) < 20: continue
            a = cv2.approxPolyDP(c, 1.3, True)[:, 0, :] * SCALE
            pts = np.rint(a).astype(int)
            d = f"M{pts[0][0]} {pts[0][1]}" + "".join(f"l{dx} {dy}" for dx, dy in np.diff(pts, axis=0) if dx or dy) + "z"
            parts.append(d)
        dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
        y, x = np.unravel_index(np.argmax(dist), dist.shape)
        res.append([ZONES[z - 1], "".join(parts), int(round(x * SCALE)), int(round(y * SCALE)), int(mask.sum())])
    return res

if __name__ == "__main__":
    prefix, webp = sys.argv[1], sys.argv[2]
    out, beauty = labels(prefix)
    zs = paths(out)
    h, w = out.shape
    img = Image.fromarray(beauty)
    img.save(webp, "WEBP", quality=int(sys.argv[3]) if len(sys.argv) > 3 else 80, method=6)
    cv2.imwrite(f"{prefix}-zonas.png", (np.array([[0]]) if False else (out * 37 % 256).astype(np.uint8)))
    json.dump({"w": int(round(w * SCALE)), "h": int(round(h * SCALE)), "zonas": zs}, open(f"{prefix}-zonas.json", "w"))
    print(prefix, w, h, "zonas", len(zs), "bytes paths", sum(len(z[1]) for z in zs))
