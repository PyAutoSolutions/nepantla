"""Zonas del mapa corporal calculadas sobre la malla 3D (MakeHuman, CC0).
Derecha/izquierda son las del paciente: su derecha es x < 0."""
import json, numpy as np
from mhload import MH, load_obj, morph, body_weights, joints

HEAD = ("head", "jaw", "eye", "levator", "oculi", "orbicularis", "oris", "risorius", "special", "tongue")

def category(bone):
    b = bone.split(".")[0]
    if b.startswith(HEAD): return "head"
    if b.startswith("neck"): return "neck"
    if b in ("clavicle", "shoulder01"): return "shoulder"
    if b == "breast": return "breast"
    if b.startswith("spine") or b == "root": return "spine"
    if b == "pelvis": return "pelvis"
    if b.startswith("upperarm"): return "uparm"
    if b.startswith("lowerarm"): return "loarm"
    if b.startswith(("wrist", "metacarpal", "finger")): return "hand"
    if b.startswith("upperleg"): return "thigh"
    if b.startswith("lowerleg"): return "shin"
    if b.startswith(("foot", "toe")): return "foot"
    return "spine"

def dominant_bones(nverts):
    W = json.load(open(f"{MH}/rigs/default_weights.mhw"))["weights"]
    best = [("root", 0.0)] * nverts
    for bone, lst in W.items():
        for vi, w in lst:
            if w > best[vi][1]:
                best[vi] = (bone, w)
    return [b for b, _ in best]

def landmarks(M, F, G, sex):
    J = joints(M, F, G)
    L = {k: J[k] for k in J}
    if sex == "male":
        L.update(navel=2.6, crotch=0.13, breast=4.52)
    else:
        L.update(navel=1.6, crotch=-0.84, breast=3.48)
    L["clav"] = J["l-clavicle"][1]
    L["xiph"] = L["navel"] + 0.62 * (L["breast"] - L["navel"])
    L["pubis"] = J["l-upper-leg"][1] - 0.1
    return L

def build(sex):
    V, VT, F, FT, G = load_obj()
    M = morph(V, body_weights(sex))
    bones = dominant_bones(len(M))
    L = landmarks(M, F, G, sex)
    body = [i for i, g in enumerate(G) if g == "body"]
    return V, VT, F, FT, G, M, bones, L, body

def face_landmarks(M, F, G, bones, L):
    """Nariz, boca y orejas medidos en la malla."""
    cats = np.array([category(b) for b in bones])
    head = np.where(cats == "head")[0]
    P = M[head]
    mid = P[np.abs(P[:, 0]) < 0.08]
    L["nose"] = mid[np.argmax(mid[:, 2])]
    teeth = set()
    for f, g in zip(F, G):
        if g in ("helper-upper-teeth", "helper-lower-teeth"):
            teeth.update(f)
    L["mouth"] = M[list(teeth)].mean(axis=0)
    ye = L["l-eye"][1]
    band = P[(P[:, 1] > ye - 0.75) & (P[:, 1] < ye + 0.15)]
    L["head_half"] = np.abs(band[:, 0]).max()
    return cats

R_ELBOW, R_KNEE = 0.55, 0.75

def classify(c, cat, L, sex):
    x, y, z = c
    s = "der" if x < 0 else "izq"
    ax = abs(x)
    J = lambda name: L[("l-" if x > 0 else "r-") + name]
    d = lambda p: np.linalg.norm(np.asarray(c) - p)
    xc = 0.6 if sex == "male" else 0.55
    out = {}
    # --- extremidades (iguales en todas las vistas, con nombre propio de frente y de espalda)
    if cat == "uparm" and d(J("shoulder")) < 0.9:
        out["f"], out["e"] = f"f-hombro-{s}", f"e-hombro-{s}"
    elif cat in ("uparm", "loarm"):
        if d(J("elbow")) < R_ELBOW:
            out["f"], out["e"] = f"f-codo-{s}", f"e-codo-{s}"
        elif cat == "uparm":
            out["f"], out["e"] = f"f-brazo-{s}", f"e-brazo-{s}"
        else:
            out["f"], out["e"] = f"f-antebrazo-{s}", f"e-antebrazo-{s}"
    elif cat == "hand":
        out["f"], out["e"] = f"f-mano-{s}", f"e-mano-{s}"
    elif cat in ("thigh", "shin"):
        if d(J("knee")) < R_KNEE:
            out["f"], out["e"] = f"f-rodilla-{s}", f"e-corva-{s}"
        elif cat == "thigh":
            out["f"], out["e"] = f"f-muslo-{s}", f"e-muslo-{s}"
            if y > L["crotch"] - 0.2:
                out["e"] = f"e-nalga-{s}"
        else:
            out["f"], out["e"] = f"f-espinilla-{s}", f"e-pantorrilla-{s}"
    elif cat == "foot":
        out["f"], out["e"] = f"f-pie-{s}", f"e-talon-{s}"
    elif cat == "head":
        out["f"], out["e"] = "f-cabeza", "e-cabeza"
    elif cat == "neck":
        out["f"], out["e"] = "f-cuello", "e-nuca"
    else:
        if cat == "shoulder" and ax > 1.2:
            out["f"], out["e"] = f"f-hombro-{s}", f"e-hombro-{s}"
        else:
            # frente
            if y > L["xiph"]:
                out["f"] = "f-pecho" if ax < 0.35 else f"f-pecho-{s}"
            elif y > L["navel"] + 0.5:
                out["f"] = "f-abdomen-alto" if ax < xc else f"f-hipocondrio-{s}"
            elif y > L["navel"] - 0.5:
                out["f"] = "f-ombligo" if ax < xc else f"f-flanco-{s}"
            elif y > L["pubis"]:
                out["f"] = "f-abdomen-bajo" if ax < xc else f"f-fosa-iliaca-{s}"
            else:
                out["f"] = "f-genitales" if ax < (0.45 if sex == "male" else 0.4) else f"f-ingle-{s}"
            # espalda
            glut = L["pubis"] + 0.8
            if y > L["xiph"]:
                out["e"] = "e-espalda-alta" if ax < 0.45 else f"e-paleta-{s}"
            elif y > L["navel"]:
                out["e"] = "e-espalda-media" if ax < 0.45 else f"e-rinon-{s}"
            elif y > glut:
                out["e"] = "e-espalda-baja"
            elif ax < 0.3 and y > glut - 0.55:
                out["e"] = "e-coxis"
            else:
                out["e"] = f"e-nalga-{s}"
    # --- cara de cerca
    out["c"] = out["f"].replace("f-brazo-", "f-hombro-")
    if cat == "neck":
        out["c"] = "c-garganta" if ax < 0.5 else f"c-cuello-{s}"
    if cat == "head":
        ye, ex = L["l-eye"][1], abs(L["l-eye"][0])
        yn, ym = L["nose"][1], L["mouth"][1]
        hh = L["head_half"]
        if ax > hh - 0.32 and ye - 0.75 < y < ye + 0.15:
            out["c"] = f"c-oido-{s}"
        elif np.hypot(ax - ex, (y - ye) * 1.3) < 0.24 and z > L["l-eye"][2] - 0.45:
            out["c"] = f"c-ojo-{s}"
        elif y > ye + 0.28:
            out["c"] = "c-frente"
        elif y > ye - 0.12 and ax > ex + 0.2:
            out["c"] = f"c-sien-{s}"
        elif ax < 0.17 and y > yn - 0.12 and y < ye + 0.28:
            out["c"] = "c-nariz"
        elif ax < 0.33 and y > ym - 0.35 and y < yn - 0.12:
            out["c"] = "c-boca"
        elif y < ym + 0.05:
            out["c"] = f"c-quijada-{s}"
        else:
            out["c"] = f"c-cachete-{s}"
    return out
