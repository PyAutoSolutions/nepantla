# Fuentes de las frases clínicas

## Estado: sin revisión clínica

Las 83 frases de `frontend/data/phrases.es.json` son un **borrador**. Las
redactó el equipo de Nepantla, no personal de salud. El archivo lo dice en su
campo `clinical_review: "pendiente"` y la app lo repite en «Acerca de» y en
cada resumen.

**No deben usarse con pacientes** hasta que personal de salud las revise,
las corrija y firme esa revisión.

## Cómo se redactaron

- Preguntas cerradas (sí o no, tocar un dibujo, tocar el cuerpo) o
  indicaciones simples.
- Una sola idea por frase, sin tecnicismos, de 80 caracteres o menos.
- Ninguna frase sugiere un diagnóstico ni un tratamiento. Las indicaciones
  de medicina («dos veces al día») las elige el personal de salud; la app
  solo las reproduce.
- Para embarazo, niñez y señales de alarma se partió de listas oficiales
  mexicanas. Las frases son redacción propia a partir de esas listas.

## Listas oficiales consultadas

Consultadas el 13 de noviembre de 2026.

### Embarazo

| Fuente | Qué aporta |
|--------|------------|
| [NOM-007-SSA2-2016](https://www.gob.mx/cms/uploads/attachment/file/512098/NOM-007-SSA2-2016.pdf), numeral 5.3.1.3 | Signos y síntomas de urgencia obstétrica: presión alta, pérdida de la conciencia, convulsiones, dolor en la boca del estómago, dolor de cabeza intenso, sangrado, palidez, dolor abdominal, fiebre y salida de líquido |
| [IMSS, Maternidad: signos de alarma](https://www.imss.gob.mx/_maternidad2/estas-embarazada/signos-alarma) | Lista para la embarazada sobre cuándo acudir de urgencia |
| [Servicios de Salud de Veracruz, folleto 2024](https://www.ssaver.gob.mx/proteccioncontrariesgossanitarios/wp-content/uploads/sites/10/2024/07/2024-SIGNOS-DE-ALARMA-EMBARAZO.pdf) | Signos de alarma en lenguaje para la población |

La misma NOM-007, en su numeral 5.11.1.3.15, pide promover en los hospitales
de regiones indígenas la presencia de facilitadoras interculturales
(traductoras indígenas) que apoyen a las gestantes. Nepantla no sustituye a
esas personas: ayuda mientras llegan.

### Niño enfermo

| Fuente | Qué aporta |
|--------|------------|
| [NOM-031-SSA2-1999](https://platiica.economia.gob.mx/normalizacion/wp-content/uploads/sites/2/PDF_Normas_Publicas/031ssa2.pdf), numerales 7.2.6.1.3 y 8.2.5.1.3.1 | Signos de alarma por diarrea (sed intensa, come o bebe poco, muchas evacuaciones, fiebre, vómito, sangre) y por infección respiratoria (respiración rápida, hundimiento de costillas, dificultad para respirar, beber o amamantarse, empeoramiento) |
| [OPS/OMS, AIEPI: ayudas de trabajo](https://paho.org/sites/default/files/IM-JobAids-2005-06spa.pdf) | Signos generales de peligro: no puede beber o tomar pecho, vomita todo, convulsiones, muy dormido o inconsciente |
| [Servicios de Salud de Puebla, Día del Niño y la Niña](https://ss.puebla.gob.mx/images/areas/informate/Dia%20del%20Ni%C3%B1o%20y%20la%20Ni%C3%B1a%202025.pdf) | Las mismas señales en lenguaje para madres, padres y cuidadores |

### Señales de alarma (para regresar)

Combina las fuentes anteriores. Son indicaciones de cuándo volver, no
valoraciones clínicas.

### Urgencias, medicinas y consentimiento

No parten de una lista oficial: son preguntas e indicaciones generales de
redacción propia. Son las que más necesitan la mirada de personal de salud.

El escenario de **consentimiento** tiene además un límite que la app
recuerda en pantalla: sirve para explicar pasos sencillos (sacar sangre,
poner suero). **No sustituye el consentimiento informado** de una cirugía o
de un procedimiento de riesgo, que necesita intérprete.

## Qué debe hacer la revisión clínica

1. Leer las 83 frases y marcar las que sobran, faltan o están mal dichas.
2. Confirmar que las cinco preguntas del modo emergencia son las correctas
   y están en el orden correcto.
3. Revisar que cada pregunta tenga el tipo de respuesta adecuado.
4. Revisar con una persona intérprete que cada frase se pueda decir de
   forma natural en la lengua (hay conceptos que no se traducen palabra por
   palabra).
5. Firmar la revisión: nombre, cédula o cargo y fecha. Con eso se cambia
   `clinical_review` en `phrases.es.json`.

Si cambia el texto de una frase que ya tiene grabaciones, esas grabaciones
deben volver a grabarse y revisarse.
