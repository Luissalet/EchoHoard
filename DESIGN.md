---
name: Echo's Hoard
description: Historial del portapapeles del usuario, capturado en segundo plano, buscable y con favoritos fijados.
colors:
  accent: "#5b2d6e"
  accent-hover: "#472357"
  accent-soft: "#f0e4f4"
  accent-light: "#b06fc9"
  ink: "#241f27"
  muted: "#695f6e"
  paper: "#faf7fb"
  white: "#ffffff"
  line: "#e6dbe9"
  soft: "#f4eef6"
  sidebar: "#f6f1f8"
  nav-active: "#ecdcf1"
  nav-active-ink: "#472357"
  nav-hover: "#f1e6f4"
  field-line: "#ddc9e3"
  field-ink: "#2c2231"
  placeholder: "#9a8ea0"
  supporting-ink: "#5f5566"
  focus: "#7a3d90"
  button-line: "#ddc9e3"
  panel: "#f4eef6"
  ok-bg: "#e5efe4"
  ok-ink: "#2f5f3a"
  warn-bg: "#f8ecd2"
  warn-ink: "#7a5a17"
  danger-bg: "#f9e8e6"
  danger-ink: "#8a2f26"
  danger-line: "#eac6c1"
  bar-bg: "#e6dbe9"
  highlight: "#f7e7a7"
typography:
  headline:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.015em"
  title:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.35
  body:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    lineHeight: 1.65
  button:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: "18px"
  label:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 600
  code:
    fontFamily: "Consolas, monospace"
    fontSize: "12px"
rounded:
  badge: "5px"
  field: "6px"
  control: "7px"
  panel: "8px"
spacing:
  control-gap: "8px"
  action-gap: "10px"
  page-gutter: "40px"
  page-gutter-mobile: "16px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.white}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "8px 15px"
  button-secondary:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "8px 15px"
  field:
    backgroundColor: "{colors.white}"
    textColor: "{colors.field-ink}"
    rounded: "{rounded.field}"
    padding: "8px 11px"
  clip-row:
    backgroundColor: "{colors.white}"
    padding: "10px 12px"
  chip:
    typography: "10px / 600 / uppercase"
    rounded: "{rounded.badge}"
    padding: "2px 6px"
---

# Design System: Echo's Hoard

## Overview

**Creative North Star: "Eco silencioso"**

Lo que copias vuelve a aparecer, sin esfuerzo, ordenado por cuándo lo copiaste. Papel muy claro, tinta oscura casi negra y un acento ciruela reservado a la acción principal, el elemento fijado y el estado activo de navegación. Sin distracciones: una lista, un buscador y un clic para volver a copiar. Interfaz en español de España.

**Key Characteristics:**

- Una lista cronológica agrupada por día, sin paginación aparente (scroll continuo).
- Un clic en cualquier fila copia de nuevo al portapapeles — la acción más frecuente es la más barata.
- Un candado y "contenido oculto" en vez de cualquier vista previa para lo sensible: nunca se muestra ni parcialmente.
- Chips de tipo (URL, correo, ruta, código, número, imagen) en vez de iconos, para que se lean de un vistazo.

## Colors

### Primary

- `accent` #5b2d6e (ciruela oscuro) para el botón primario, la fila fijada y el estado activo de navegación.
- `accent-hover` #472357 y `accent-soft` #f0e4f4 (chips, fondos suaves).
- `accent-light` #b06fc9 como acento claro para detalles secundarios y estados de progreso.

### Neutral

- `paper` #faf7fb fondo; `white` paneles y filas; `sidebar` #f6f1f8; `panel` #f4eef6 formularios.
- `ink` #241f27 texto; `supporting-ink` #5f5566 ayudas; `line` #e6dbe9 bordes.
- Semánticos: `ok` verde apagado, `warn` ámbar, `danger` rojo suave (eliminar, purgar) — iguales en toda la familia Hoard.

## Typography

**Body Font:** Segoe UI (system-ui de respaldo) en toda la interfaz, incluidas las vistas previas de las copias — el portapapeles no necesita una tipografía distinta para "lo guardado" frente a "la interfaz".

- **Headline:** título de página 30px (26px en móvil).
- **Title:** títulos de sección 16px seminegrita.
- **Body:** 14px; ayudas y metadatos 12px; chips 10px mayúsculas.

## Layout

Escritorio: índice fijo de 224px + contenido flexible (`min-width: 0`), márgenes de 40px. Historial usa una lista de filas agrupadas por día con un buscador y filtros por tipo arriba. Fijados usa la misma fila sin agrupar, ordenada por etiqueta. Estado usa una cuadrícula de contadores + paneles de configuración.

- Hasta 768px: el índice pasa a barra superior con navegación horizontal desplazable; márgenes de 16px; los filtros de tipo envuelven en varias líneas.
- No hay desplazamiento horizontal de página a 390px: todo contenedor de cuadrícula lleva `min-width: 0`.

## Elevation & Depth

Plano por defecto. Sombra solo en el aviso flotante (toast). Ninguna fila ni panel usa sombra: la jerarquía viene del color de fondo y el borde de 1px.

## Shapes

Campos 6px, controles 7px, paneles 8px, chips 5px. Bordes de 1px. Iconos SVG de línea (candado, chincheta). Sin imágenes raster salvo las miniaturas de las copias de imagen y los iconos de instalación (PWA).

## Components

### Buttons

Primario (ciruela), secundario (blanco con borde), peligro (rojo suave: "Eliminar", "Purgar"). Altura mínima 38px; variante `btn-sm` de 30px para las acciones de cada fila (Etiquetar, Fijar, Eliminar).

### Inputs / Fields

Etiqueta encima, ayuda debajo. El filtro de tipo es un grupo de botones segmentado (`seg`), no un `<select>`, porque son pocas opciones y se cambian a menudo.

### Navigation

Tres secciones: Historial, Fijados, Estado. Rutas por hash (`#/historial`). La activa usa `aria-current` con fondo `nav-active`.

### Clip row

Fila blanca con vista previa de una línea, chip de tipo, aplicación de origen, hora y contador de veces copiada; una miniatura de 40×40 cuando es una imagen. Toda la fila (menos los botones de acción) es un único botón: pulsarla copia. Una fila sensible se sustituye por un candado y "Contenido oculto", con solo el botón Eliminar disponible.

### Chips

Tipo de copia (texto/URL/correo/ruta/código/número/imagen), etiqueta. Texto en mayúsculas de 10px.

### Empty states

Un título, una frase y ninguna acción forzada — copiar algo es la única forma natural de llenar el historial.

## Do's and Don'ts

### Do:

- **Do** sustituir el contenido sensible por "Contenido oculto" en la interfaz Y en la base de datos — nunca solo ocultarlo visualmente.
- **Do** dejar que un solo clic en la fila copie de nuevo; es la acción que más se repite.
- **Do** mostrar cuántas veces se ha copiado lo mismo (`×N`) en vez de crear filas duplicadas.
- **Do** ofrecer "Deshacer" justo después de eliminar (ventana de 24 horas antes de purgar de verdad).

### Don't:

- **Don't** mostrar nunca una vista previa, ni parcial, de una copia marcada como sensible.
- **Don't** usar el acento para texto largo; reservarlo al botón primario, la fila fijada y el estado activo.
- **Don't** paginar el historial con números de página; el scroll continuo agrupado por día basta.
