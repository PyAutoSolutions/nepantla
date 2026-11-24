"""Carga la malla base de MakeHuman (CC0) y aplica targets."""
import numpy as np, os
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Carpeta "data" de MakeHuman (ver LEEME.md). Se puede cambiar con MAKEHUMAN_DATA.
MH = os.environ.get("MAKEHUMAN_DATA", str(HERE / "trabajo" / "mh" / "makehuman" / "data"))

def load_obj(path=f"{MH}/3dobjs/base.obj"):
    V, VT, F, FT, G = [], [], [], [], []
    group = None
    for line in open(path):
        if line.startswith("v "):
            V.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("vt "):
            VT.append([float(x) for x in line.split()[1:3]])
        elif line.startswith("g "):
            group = line.split(None, 1)[1].strip()
        elif line.startswith("f "):
            idx = [p.split("/") for p in line.split()[1:]]
            F.append([int(p[0]) - 1 for p in idx])
            FT.append([int(p[1]) - 1 if len(p) > 1 and p[1] else -1 for p in idx])
            G.append(group)
    return np.array(V), np.array(VT), F, FT, G

def load_target(name):
    off = {}
    for line in open(f"{MH}/targets/{name}"):
        if line.startswith("#") or not line.strip():
            continue
        p = line.split()
        off[int(p[0])] = [float(x) for x in p[1:4]]
    return off

def morph(V, weights):
    out = V.copy()
    for name, w in weights.items():
        for i, d in load_target(name).items():
            out[i] += w * np.array(d)
    return out

def body_weights(sex):
    w = {}
    for eth in ("african", "asian", "caucasian"):
        w[f"macrodetails/{eth}-{sex}-young.target"] = 1 / 3
    return w

def joints(V, F, G):
    acc = {}
    for f, g in zip(F, G):
        if g and g.startswith("joint-"):
            acc.setdefault(g[6:], set()).update(f)
    return {k: V[list(v)].mean(axis=0) for k, v in acc.items()}
