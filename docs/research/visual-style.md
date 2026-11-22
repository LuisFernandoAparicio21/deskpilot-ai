# Estilo visual repetido en el perfil de LuisFernandoAparicio21 y sus repos fijados

Consulta: 2026-11-22. Solo se lee el Markdown (raw) y los SVG; no se clonó nada. No se copia contenido, solo estilo.

## Pregunta
¿Qué elementos de estilo visual se repiten en el perfil y en los repos fijados (agentic-spec-driven-development, proyecto-inaoeV2, factufast)?

## Respuesta
**Perfil** ([README](https://github.com/LuisFernandoAparicio21/LuisFernandoAparicio21/blob/main/README.md)):
- Banner: `<picture>` con `<source media="(prefers-color-scheme: dark|light)">` apuntando a `assets/banner-dark.svg` y `assets/banner-light.svg`; `<img width="100%">` fallback al oscuro; todo dentro de `<div align="center">`. Alt: `profile.sh --live`. SVG 1180x610 con `<title>` "system profile" y `<desc>` "Animated terminal profile with a dithered portrait..." => estilo terminal, animado con SMIL (`<animate>`, `<animateTransform>`). Tipografía `ui-monospace,SFMono-Regular,Consolas,monospace`. Paleta del oscuro (conteo de hex en el archivo): rojo `#E53535` dominante, `#FF4D5A`, `#FF6B6B`, texto rosado `#F5E0E0`, apagados `#7A4040`, `#3D1010`, fondo `#150404`. Archivos: [banner-dark.svg](https://raw.githubusercontent.com/LuisFernandoAparicio21/LuisFernandoAparicio21/main/assets/banner-dark.svg) (~868 KB). Del claro solo verifiqué dimensiones (1180x610) y título; su paleta NO verificada (descarga truncada).
- Texto animado readme-typing-svg, dentro de `<p align="center"><a href="https://github.com/DenverCoder1/readme-typing-svg"><img src=...>`:
  `https://readme-typing-svg.demolab.com?font=Fira+Code&center=true&width=650&height=45&color=F5E0E0&lines=Backend+Developer+%C2%B7+DevOps+%C2%B7+Data+Engineering;AI+%26+RAG+Engineer;Integration+Engineer`
  (color del texto coincide con `#F5E0E0` del banner; 3 líneas separadas por `;`, `+` = espacio, `%C2%B7` = punto medio).
- Contador de visitas: `visitor-badge.laobi.icu/badge?page_id=...` y al final `komarev.com/ghpvc/?...&color=58A6FF&style=flat-square`.
- Orden de secciones: banner -> typing -> visitas -> `---` -> `# 💫 About Me` (bloque con `<br>`) -> `## 🌐 Socials` (badges) -> `# 💻 Tech Stack` con subtítulos en negrita con emoji (📝 Languages, ⚙️ Frameworks, 🗄️ Databases, ☁️ Cloud, 🛠️ Tools) -> `# 📊 GitHub Stats` -> `---` -> contador.
- Badges Shields.io: Socials sin `style` (plano por defecto) con color de marca (`%237289DA`, `D14836`...), `logoColor=white`. Tech Stack: `style=for-the-badge`, color de marca por tecnología, logo de simple-icons, una línea por categoría.
- Tarjeta de estadísticas: solo `github-readme-stats.vercel.app/api/top-langs/?username=LuisFernandoAparicio21&theme=dark&hide_border=false&include_all_commits=true&count_private=true&layout=compact`. Tema fijo `dark`, sin variante clara (no usa `<picture>`). No hay tarjeta de stats generales, streak ni trofeos.

**Repos fijados** (README de [agentic-spec-driven-development](https://github.com/LuisFernandoAparicio21/agentic-spec-driven-development/blob/main/README.md), [proyecto-inaoeV2](https://github.com/LuisFernandoAparicio21/proyecto-inaoeV2/blob/main/README.md), [factufast](https://github.com/LuisFernandoAparicio21/factufast/blob/main/README.md)), patrón común:
- Todo el encabezado en `<div align="center">`: `# título` (factufast e inaoeV2 con emoji 🧾/🤖; agentic sin emoji), línea en negrita con la propuesta de valor, `<br>`, fila de badges, y en factufast/agentic una línea `<sub>` (más `</div>`).
- Badges: siempre `style=for-the-badge`, color de marca, `logo=` simple-icons; inaoeV2 y factufast los agrupan por capa (comentarios `<!-- Frontend -->`, etc.); agentic usa badges de metodología con colores propios (`2563EB`, `16A34A`, `D97757`).
- Sin banner SVG, sin typing, sin stats cards, sin `<picture>`: el banner terminal y el typing son exclusivos del perfil.
- Cuerpo: `---` entre bloques; tablas Markdown de 2 columnas (Layer/Technology, Role/Responsibility, Característica/Descripción); emoji en H2 solo en inaoeV2 (📋 📖 🚀 📂 🧩); factufast y agentic usan H2 sin emoji. Imagen de arquitectura con `<img width="800">` (factufast); inaoeV2 usa bloques de código. Tabla de contenidos en inaoeV2 y agentic.
- Cierre: agentic termina con `<div align="center"><sub>...</sub></div>`.

## Qué no pude verificar
Cómo se renderiza visualmente cada cosa (no abrí navegador ni vi capturas); solo lo inferido del Markdown/SVG. Paleta del banner claro. Que el fallback de `<picture>` sea el que GitHub elija en cada tema (comportamiento documentado de GitHub, no probado aquí).

## Decisión recomendada para DeskPilot AI
Reutilizar la receta: `<div align="center">`, banner `<picture>` oscuro/claro, typing SVG, badges `for-the-badge` con color de marca agrupados por capa, tablas 2 columnas, `---` entre bloques; emoji solo en H2 (consistencia con el perfil). Para stats usar variante clara/oscura (el perfil solo tiene dark).

## Disponibilidad de servicios (curl -I, 2026-11-22)
- readme-typing-svg.demolab.com: HTTP 200, `image/svg+xml`.
- img.shields.io (badge for-the-badge python): HTTP 200, `image/svg+xml`.
- github-readme-stats.vercel.app, komarev.com, visitor-badge.laobi.icu: HTTP 200 (solo comprobación, no son fuentes oficiales citadas).

## Parámetros documentados de readme-typing-svg
`lines` (`;` separa líneas, `+` espacio), `height` (50), `width` (400), `size` (20), `font` (monospace; Google Fonts), `color` (36BCF7, hex sin #), `background` (00000000), `center` (false), `vCenter` (false), `multiline` (false), `duration` (5000 ms), `pause` (0), `delay` (0), `repeat` (true), `groups`, `separator` (`;`), `letterSpacing` (normal).

## Fuentes
1. readme-typing-svg README, https://github.com/DenverCoder1/readme-typing-svg (raw leído), consultada 2026-11-22.
2. Shields.io, https://shields.io (endpoint https://img.shields.io/badge/...), consultada 2026-11-22.
3. Repos del usuario (perfil, assets/banner-*.svg y 3 repos fijados), consultados 2026-11-22.
