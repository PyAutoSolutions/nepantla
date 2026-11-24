"""Pictogramas a color: Fluent Emoji Flat de Microsoft (licencia MIT).
Reemplaza en pictos.svg solo los pictogramas de contenido; la interfaz no cambia."""
import json, re, sys
# icons.json del paquete npm @iconify-json/fluent-emoji-flat 1.2.6 (ver docs/ATTRIBUTIONS.md).
# Uso: python build_pictos.py RUTA/icons.json frontend/icons/pictos.svg
I = json.load(open(sys.argv[1]))["icons"]

def body(name):
    b = I[name]["body"]
    return re.sub(r"-?\d*\.\d+", lambda m: f"{float(m.group()):.1f}", b)

def place(name, x, y, size):
    s = size / 32
    return f'<g transform="translate({x:g} {y:g}) scale({s:g})">{body(name)}</g>'

def badge(name):
    return '<circle cx="37" cy="37" r="10.5" fill="#fff" stroke="#c9ced8"/>' + place(name, 28, 28, 18)

def compose(main, extra=None, size=None):
    if size:  # figura más chica, centrada abajo
        return place(main, (48 - size) / 2, 47 - size, size)
    if extra is None:
        return place(main, 2, 2, 44)
    return place(main, 1, 1, 40) + badge(extra)

def dosing(times):
    n = len(times); size = 19 if n < 3 else 15; gap = 3 if n < 3 else 1.5
    total = n * size + (n - 1) * gap; x0 = (48 - total) / 2
    out = place("pill", 12, 0, 24)
    for k, t in enumerate(times):
        out += place(t, x0 + k * (size + gap), 47 - size, size)
    return out

MAP = {
    "acuerdo": ("handshake",), "alarma": ("warning",), "alergia": ("pill", "warning"),
    "animal": ("scorpion", "snake"), "bebe-movimiento": ("pregnant-woman-medium", "baby-medium"),
    "beber": ("cup-with-straw", "baby-bottle"), 
    "calendario": ("spiral-calendar",), "cartilla": ("green-book", "syringe"),
    "cita": ("spiral-calendar", "stethoscope"), "con-comida": ("pill", "fork-and-knife-with-plate"),
    "consulta": ("pregnant-woman-medium", "stethoscope"), "convulsion": ("face-with-spiral-eyes", "high-voltage"),
     "decir-no": ("person-gesturing-no-medium",),
    "desmayo": ("knocked-out-face",), "diabetes": ("drop-of-blood", "candy"), "diarrea": ("pile-of-poo", "droplet"),
    "dolor": ("persevering-face",), "dolor-cabeza": ("face-with-head-bandage",), "dormido": ("sleeping-face",),
    "embarazo": ("pregnant-woman-medium",),
    "explicar": ("health-worker-medium", "speech-balloon"), "familia": ("people-hugging",),
    "fiebre": ("face-with-thermometer",), "golpe-cabeza": ("face-with-head-bandage", "collision"),
    "herida": ("adhesive-bandage",),  "inyeccion": ("syringe",),
    "liquido": ("pregnant-woman-medium", "droplet"), "mareo": ("face-with-spiral-eyes",),
    "medicina-hoy": ("pill", "check-mark-button"), "medicina-mal": ("pill", "nauseated-face"),
    "meses": ("pregnant-woman-medium", "spiral-calendar"), "muestra-sangre": ("drop-of-blood", "test-tube"),
    "nino": ("child-medium",), "oido": ("ear-medium", "bell"), "orinar": ("toilet", "droplet"),
    "parto": ("pregnant-woman-medium", "collision"), "pastilla": ("pill",), 
    "planta": ("herb",), "pregunta": ("red-question-mark",), 
      "respirar": ("lungs",),
    "revisar": ("stethoscope",), "saludo": ("waving-hand-medium",), "sangre": ("drop-of-blood",),
    "sangre-excremento": ("pile-of-poo", "drop-of-blood"), "todos-los-dias": ("spiral-calendar", "pill"),
    "tos": ("face-with-medical-mask",),  "vision": ("eye", "sparkles"),
    "vomito": ("face-vomiting",), "edad-bebe": ("baby-medium",), "edad-nino-grande": ("child-medium", "backpack"),
}
SPECIAL = {
    "una-vez": dosing(["sun"]), "dos-veces": dosing(["sun", "crescent-moon"]),
    "tres-veces": dosing(["sunrise", "sun", "crescent-moon"]),
    "no-alcohol": place("beer-mug", 4, 4, 40) + place("prohibited", 2, 2, 44),
    "edad-recien-nacido": compose("baby-medium", size=30), "edad-nino-chico": compose("child-medium", size=36),
}

def symbols():
    out = {}
    for k, v in MAP.items():
        out[k] = compose(*v)
    out.update(SPECIAL)
    return {k: f'<symbol id="{k}" viewBox="0 0 48 48">{v}</symbol>' for k, v in out.items()}

if __name__ == "__main__":
    path = sys.argv[2]
    lines = open(path, encoding="utf-8").read().split("\n")
    syms = symbols(); done = set(); out = []
    for line in lines:
        m = re.match(r'<symbol id="([^"]+)"', line)
        if m and m.group(1) in syms:
            out.append(syms[m.group(1)]); done.add(m.group(1))
        else:
            out.append(line)
    missing = set(syms) - done
    assert not missing, missing
    text = "\n".join(out)
    text = text.replace("<!-- Pictogramas originales de Nepantla. CC BY 4.0. Ver docs/ATTRIBUTIONS.md.",
        "<!-- Pictogramas de interfaz: originales de Nepantla, CC BY 4.0. Pictogramas a color de\n     contenido: Fluent Emoji Flat de Microsoft, licencia MIT. Ver docs/ATTRIBUTIONS.md.", 1)
    open(path, "w", encoding="utf-8").write(text)
    print("reemplazados", len(done))
