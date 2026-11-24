"""Render realista del cuerpo (MakeHuman CC0) con Blender/Cycles + mapa de zonas.
Uso: bpyenv/bin/python render.py SEX VIEW ALTO MUESTRAS SALIDA [beauty|id|both]"""
import sys, math, json, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from zones import build, face_landmarks, classify, category


sex, view, height_px, samples, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
mode = sys.argv[6] if len(sys.argv) > 6 else "both"

V, VT, F, FT, G, M, bones, L, body = build(sex)
cats = face_landmarks(M, F, G, bones, L)
ZONES = json.load(open(Path(__file__).resolve().parent / "zone_ids.json"))
zindex = {z: i + 1 for i, z in enumerate(ZONES)}

faces, fz, ez, cz = [], [], [], []
for i in body:
    f = F[i]
    cs = [cats[v] for v in f]
    cat = max(set(cs), key=cs.count)
    c = M[f].mean(axis=0)
    r = classify(c, cat, L, sex)
    faces.append(f); fz.append(zindex[r["f"]]); ez.append(zindex[r["e"]]); cz.append(zindex[r["c"]])

def smooth01(t):
    t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)

def masks(P, vcat):
    """Valores por vértice: >0 dentro de la ropa, el cabello, las cejas o los labios."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]; ax = np.abs(x)
    n = len(P)
    cloth = np.full(n, -1.0); hair = np.full(n, -1.0); brow = np.full(n, -1.0); lip = np.full(n, -1.0)
    lower = np.isin(vcat, ["pelvis", "spine", "thigh"])
    top = L["pubis"] + (0.85 if sex == "male" else 0.8)
    hip = 1.45 if sex == "male" else 1.4
    wf = smooth01((z - (-0.35)) / 0.7)              # 1 de frente, 0 por detrás
    y_med = wf * (L["crotch"] - 0.02) + (1 - wf) * (L["crotch"] - 0.3)
    y_lat = wf * (L["pubis"] + 0.3) + (1 - wf) * (L["pubis"] + 0.05)
    t = np.clip((ax - 0.22) / (hip - 0.22), 0, 1) ** 0.85
    y_open = y_med + t * (y_lat - y_med)
    cloth = np.where(lower, np.minimum(top - y, y - y_open), -1.0)
    if sex == "female":
        up = np.isin(vcat, ["breast", "spine", "shoulder"])
        yb = L["breast"]
        band = np.minimum(np.minimum(y - (yb - 0.62), (yb + 0.42) - y), 1.5 - ax)
        cloth = np.where(up, np.maximum(cloth, band), cloth)
    head = vcat == "head"
    ye, ym, hh = L["l-eye"][1], L["mouth"][1], L["head_half"]
    zl = np.clip(z, -0.4, 1.2)
    level = np.interp(zl, [-0.4, -0.1, 0.35, 0.75, 1.2], [ym + 0.05, ym + 0.15, ye + 0.3, ye + 0.52, ye + 0.6])
    level = level - 0.12 * np.clip(ax / hh, 0, 1) ** 2 * (z > 0.5)
    ear = (ax > hh - 0.34) & (y > ye - 0.8) & (y < ye + 0.2)
    hair = np.where(head & ~ear, y - level, -1.0)
    neck = vcat == "neck"
    hair = np.where(neck & (z < -0.2), np.minimum(y - (ym + 0.05), -0.2 - z), hair)
    xb = np.clip((ax - 0.1) / 0.5, 0, 1)
    yb_line = ye + 0.17 + 0.07 * np.sin(np.pi * np.clip(xb * 0.9 + 0.1, 0, 1))
    thick = (0.04 if sex == "male" else 0.032) * np.sqrt(np.clip(1 - ((ax - 0.34) / 0.25) ** 2, 0, 1))
    brow = np.where(head & (z > L["l-eye"][2] - 0.45) & (ax > 0.1) & (ax < 0.58) & (thick > 0.012), thick - np.abs(y - yb_line), -1.0)
    ym_l = ym + 0.0
    lip = np.where(head & (z > L["l-eye"][2] - 0.1), 1 - np.sqrt((ax / 0.23) ** 2 + ((y - ym_l) / 0.09) ** 2), -1.0)
    return cloth, hair, brow, lip

used = np.unique(np.concatenate([np.array(f) for f in faces]))
remap = -np.ones(len(M), int); remap[used] = np.arange(len(used))
verts = M[used]
verts = np.stack([verts[:, 0], -verts[:, 2], verts[:, 1]], axis=1)  # MH (x,y,z) -> Blender (x,-z,y)
faces_r = [[int(remap[v]) for v in f] for f in faces]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
me = bpy.data.meshes.new("cuerpo")
me.from_pydata(verts.tolist(), [], faces_r)
me.update()
for name, arr in (("zf", fz), ("zb", ez), ("zc", cz)):
    a = me.attributes.new(name, "FLOAT", "FACE"); a.data.foreach_set("value", np.array(arr, dtype=np.float32))
me.polygons.foreach_set("use_smooth", np.ones(len(faces_r), dtype=bool))
vcat = np.array([cats[v] for v in used])
for name, arr in zip(("ropa", "cabello", "ceja", "labio"), masks(M[used], vcat)):
    a = me.attributes.new(name, "FLOAT", "POINT"); a.data.foreach_set("value", arr.astype(np.float32))
obj = bpy.data.objects.new("cuerpo", me); scene.collection.objects.link(obj)
sub = obj.modifiers.new("sub", "SUBSURF"); sub.levels = 2; sub.render_levels = 2

# volumen del cabello: se empujan hacia afuera los vértices con cabello
hair_v = masks(M[used], vcat)[1]
me.update()
nrm = np.zeros(len(me.vertices) * 3, dtype=np.float32); me.vertex_normals.foreach_get("vector", nrm); nrm = nrm.reshape(-1, 3)
thick_max = 0.07 if sex == "male" else 0.12
w = np.clip(hair_v / 0.25, 0, 1); w = w * w * (3 - 2 * w)
co = verts + nrm * (thick_max * w)[:, None]
me.vertices.foreach_set("co", co.astype(np.float32).ravel()); me.update()
extra_objs = []
if sex == "female":
    ye = L["l-eye"][1]
    head_pts = M[used][vcat == "head"]
    back_z = head_pts[:, 2].min()
    bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=20, radius=1, location=(0, -(back_z - 0.22), ye + 0.05))
    bun = bpy.context.active_object; bun.scale = (0.42, 0.34, 0.38)
    for p in bun.data.polygons: p.use_smooth = True
    for name, val in (("zf", zindex["f-cabeza"]), ("zb", zindex["e-cabeza"]), ("zc", zindex["c-frente"])):
        a = bun.data.attributes.new(name, "FLOAT", "FACE"); a.data.foreach_set("value", np.full(len(bun.data.polygons), val, dtype=np.float32))
    extra_objs.append(bun)

def principled(name, color, rough=0.5, sss=0.0, sss_r=(1, 0.4, 0.25), spec=0.5, sheen=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Subsurface Weight"].default_value = sss
    b.inputs["Subsurface Radius"].default_value = sss_r
    b.inputs["Subsurface Scale"].default_value = 0.08
    b.inputs["Specular IOR Level"].default_value = spec
    if sheen: b.inputs["Sheen Weight"].default_value = sheen
    return m

def srgb(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)

def layered():
    m = bpy.data.materials.new("cuerpo"); m.use_nodes = True
    t = m.node_tree; t.nodes.clear()
    out = t.nodes.new("ShaderNodeOutputMaterial")
    def bsdf(color, rough, sss=0.0, spec=0.4, sheen=0.0):
        b = t.nodes.new("ShaderNodeBsdfPrincipled")
        b.inputs["Base Color"].default_value = (*srgb(color), 1); b.inputs["Roughness"].default_value = rough
        b.inputs["Subsurface Weight"].default_value = sss; b.inputs["Subsurface Radius"].default_value = (1, 0.4, 0.25)
        b.inputs["Subsurface Scale"].default_value = 0.08; b.inputs["Specular IOR Level"].default_value = spec
        if sheen: b.inputs["Sheen Weight"].default_value = sheen
        return b
    def fac(name, soft):
        a = t.nodes.new("ShaderNodeAttribute"); a.attribute_type = "GEOMETRY"; a.attribute_name = name
        r = t.nodes.new("ShaderNodeMapRange"); r.inputs["From Min"].default_value = -soft; r.inputs["From Max"].default_value = soft
        r.interpolation_type = "SMOOTHSTEP"
        t.links.new(a.outputs["Fac"], r.inputs["Value"]); return r.outputs["Result"]
    shader = bsdf(SKIN, 0.48, 0.25, 0.35).outputs[0]
    for name, color, rough, soft, extra in (("labio", "#91574A", 0.4, 0.3, {}), ("ceja", "#33251C", 0.7, 0.015, {}),
                                            ("cabello", "#1C1511", 0.55, 0.05, {}), ("ropa", "#B4C3D3", 0.85, 0.012, {"sheen": 0.4, "spec": 0.2})):
        mix = t.nodes.new("ShaderNodeMixShader")
        t.links.new(fac(name, soft), mix.inputs[0]); t.links.new(shader, mix.inputs[1])
        b = bsdf(color, rough, 0.2 if name == "labio" else 0.0, extra.get("spec", 0.35), extra.get("sheen", 0.0))
        t.links.new(b.outputs[0], mix.inputs[2]); shader = mix.outputs[0]
    t.links.new(shader, out.inputs["Surface"])
    return m

SKIN = "#A36D4E"
obj.data.materials.append(layered())
hair_mat = bpy.data.materials.new("cabello_vol"); hair_mat.use_nodes = True
hb = hair_mat.node_tree.nodes["Principled BSDF"]; hb.inputs["Base Color"].default_value = (*srgb("#1C1511"), 1)
hb.inputs["Roughness"].default_value = 0.5; hb.inputs["Specular IOR Level"].default_value = 0.35
for o in extra_objs: o.data.materials.append(hair_mat)

# ojos: esferas en el centro de los ojos de ayuda de MakeHuman
eye_mat = bpy.data.materials.new("ojo"); eye_mat.use_nodes = True
nt = eye_mat.node_tree; bsdf = nt.nodes["Principled BSDF"]
tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
ramp = nt.nodes.new("ShaderNodeValToRGB")
nt.links.new(tc.outputs["Object"], sep.inputs[0]); nt.links.new(sep.outputs["Y"], ramp.inputs[0])
ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (0.005, 0.004, 0.003, 1)
ramp.color_ramp.elements[1].position = 0.06; ramp.color_ramp.elements[1].color = (0.05, 0.025, 0.012, 1)
e = ramp.color_ramp.elements.new(0.16); e.color = (0.07, 0.035, 0.015, 1)
e = ramp.color_ramp.elements.new(0.19); e.color = (0.72, 0.68, 0.64, 1)
# Y del objeto va de -1 (frente) a 1: se remapea a 0..1 antes de la rampa
mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = -1; mr.inputs["From Max"].default_value = 1
nt.links.new(sep.outputs["Y"], mr.inputs["Value"]); nt.links.new(mr.outputs["Result"], ramp.inputs[0])
nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"]); bsdf.inputs["Roughness"].default_value = 0.08
eye_objs = []
for side in ("l", "r"):
    idx = set()
    for f, g in zip(F, G):
        if g == f"helper-{side}-eye": idx.update(f)
    P = M[list(idx)]; c = P.mean(axis=0); r = np.linalg.norm(P - c, axis=1).mean()
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1, location=(c[0], -c[2], c[1]))
    eo = bpy.context.active_object; eo.scale = (r * 0.98,) * 3; eo.data.materials.append(eye_mat)
    for p in eo.data.polygons: p.use_smooth = True
    zid = zindex[f"c-ojo-{'izq' if side == 'l' else 'der'}"]
    for name, val in (("zf", zindex["f-cabeza"]), ("zb", zindex["e-cabeza"]), ("zc", zid)):
        a = eo.data.attributes.new(name, "FLOAT", "FACE"); a.data.foreach_set("value", np.full(len(eo.data.polygons), val, dtype=np.float32))
    eye_objs.append(eo)

# cámara ortográfica
bb = verts
if view == "face":
    ye = L["l-eye"][1]
    x0, x1, z0, z1 = -1.25, 1.25, ye - 1.75, ye + 1.3
else:
    x0, x1 = bb[:, 0].min(), bb[:, 0].max(); z0, z1 = bb[:, 2].min(), bb[:, 2].max()
pad = 0.035 * (z1 - z0)
x0 -= pad; x1 += pad; z0 -= pad; z1 += pad
aspect = (x1 - x0) / (z1 - z0)
cam_d = bpy.data.cameras.new("cam"); cam_d.type = "ORTHO"; cam_d.ortho_scale = z1 - z0
cam = bpy.data.objects.new("cam", cam_d); scene.collection.objects.link(cam); scene.camera = cam
cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
if view == "back":
    cam.location = (-cx, 60, cz); cam.rotation_euler = (math.radians(90), 0, math.radians(180))
    cx = -cx
else:
    cam.location = (cx, -60, cz); cam.rotation_euler = (math.radians(90), 0, 0)
cam_d.clip_end = 200
scene.render.resolution_y = height_px
scene.render.resolution_x = int(round(height_px * aspect))
scene.render.resolution_percentage = 100

# luces suaves que siguen a la cámara
def sun(name, direction, strength, angle):
    d = bpy.data.lights.new(name, "SUN"); d.energy = strength; d.angle = math.radians(angle)
    o = bpy.data.objects.new(name, d); scene.collection.objects.link(o)
    v = Vector(direction).normalized()
    o.rotation_euler = (-v).to_track_quat("Z", "Y").to_euler()
    return o
flip = -1 if view == "back" else 1
sun("clave", (0.45 * flip, 1.0 * flip, -0.55), 3.2, 35)
sun("relleno", (-0.6 * flip, 0.8 * flip, -0.2), 1.1, 60)
sun("borde", (0.2 * flip, -1.0 * flip, -0.35), 1.6, 25)
world = bpy.data.worlds.new("mundo"); scene.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.57, 0.6, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.55

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"

if mode in ("beauty", "both"):
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "AgX"
    scene.render.image_settings.color_mode = "RGBA"; scene.render.image_settings.color_depth = "8"
    scene.render.filepath = f"{out}-beauty.png"
    bpy.ops.render.render(write_still=True)

if mode in ("id", "both"):
    attr = {"front": "zf", "back": "zb", "face": "zc"}[view]
    idm = bpy.data.materials.new("id"); idm.use_nodes = True
    t = idm.node_tree; t.nodes.clear()
    at = t.nodes.new("ShaderNodeAttribute"); at.attribute_type = "GEOMETRY"; at.attribute_name = attr
    mth = t.nodes.new("ShaderNodeMath"); mth.operation = "DIVIDE"; mth.inputs[1].default_value = 255.0
    em = t.nodes.new("ShaderNodeEmission"); outn = t.nodes.new("ShaderNodeOutputMaterial")
    t.links.new(at.outputs["Fac"], mth.inputs[0]); t.links.new(mth.outputs[0], em.inputs["Color"]); t.links.new(em.outputs[0], outn.inputs["Surface"])
    scene.view_layers[0].material_override = idm
    for o in list(scene.objects):
        if o.type == "LIGHT": o.hide_render = True
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    scene.cycles.samples = 1; scene.cycles.use_denoising = False
    scene.cycles.filter_width = 0.01
    scene.cycles.max_bounces = 0
    scene.view_settings.view_transform = "Raw"; scene.view_settings.look = "None"
    scene.render.image_settings.color_mode = "RGBA"; scene.render.image_settings.color_depth = "16"
    scene.render.filepath = f"{out}-id.png"
    bpy.ops.render.render(write_still=True)
print("LISTO", scene.render.resolution_x, scene.render.resolution_y)
