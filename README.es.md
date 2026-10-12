# Echo's Hoard

Todo lo que copias, guardado en tu propio ordenador, buscable, con lo que copias a menudo fijado. La aplicación vigila tu portapapeles en segundo plano; un asistente accede al mismo historial por MCP, así que puede responder «qué era esa URL que copié hace una hora», volver a pegar lo último que copiaste, o poner texto nuevo en tu portapapeles.

Todo se queda en la máquina: SQLite para el historial, ficheros PNG para las imágenes, sin cuentas y sin red.

## Qué hace

- **Copias** = lo que copias: texto, o una imagen guardada como PNG. Con el OCR local opcional, el texto de la imagen se puede buscar y consultar desde Faustus, marcado como texto derivado; sin OCR se conserva un marcador como «[imagen 1254×1254]». Cada copia guarda su tipo, vista previa, aplicación/ventana de origen, fechas, repeticiones, fijado, etiqueta y tags.
- **Sin duplicados**: copiar lo mismo otra vez actualiza `last_seen_at`/`times` de la copia existente en vez de crear una nueva.
- **Detección de tipo**: URL, correo, ruta, código, número, imagen o texto — a partir solo del contenido (`echo/detect.py`).
- **Contenido sensible** (la privacidad ante todo): una copia que parece una contraseña, una clave de API, un número de tarjeta (verificado con Luhn) o un IBAN se marca `sensitive` y su contenido real se sustituye por un texto como `[oculto: contraseña]` **antes de llegar a la base de datos** — no se oculta solo en la interfaz, nunca se guarda. El asistente no lo recibe nunca, ni siquiera parcialmente. Una lista de exclusión por aplicación (`ECHO_EXCLUDE_APPS`, por defecto `KeePass,1Password,Bitwarden,keepassxc`) evita capturar nada de los gestores de contraseñas. Un interruptor de pausa detiene la captura (interfaz + herramienta).
- **Retención**: se conserva todo `ECHO_RETENTION_DAYS` días (30 por defecto) salvo lo fijado; máximo `ECHO_MAX_CLIPS` copias (5000 por defecto), se eliminan antes las más antiguas sin fijar; las imágenes se limitan a `ECHO_MAX_IMAGE_MB` en total (200 por defecto). Un borrado suave deja una ventana de 24 horas para deshacer antes de que se purgue de verdad. La limpieza se ejecuta al arrancar y cada 10 minutos.
- **Búsqueda**: FTS5 sobre texto/etiqueta/tags/título de la ventana de origen, sin distinguir tildes, con coincidencia de prefijo, filtrable por tipo/fijado/fecha/aplicación.
- **Backend de captura** (`echo/backends/`): una interfaz pequeña (`read()`, `write()`, `foreground()`) con tres implementaciones — Windows (`ctypes` contra user32/kernel32, sin pywin32, sondea `GetClipboardSequenceNumber` de forma barata y solo lee cuando cambia; si el portapapeles está bloqueado reintenta unas pocas veces y luego se salta ese cambio en vez de fallar), genérica/multiplataforma (`pyperclip`, sondeando el texto comparando su sha256; sin imágenes ni aplicación de origen), y una implementación falsa usada por las pruebas. Se elige con `ECHO_BACKEND` (`auto`/`windows`/`generic`/`fake`).

## Requisitos

- Windows 10/11 (también funciona en Linux/macOS con el backend genérico, sin imágenes ni detección de aplicación de origen), Python 3.11 o superior (3.13 va bien), Node 22 solo para construir el cliente.
- El `sqlite3` de Python debe tener FTS5. Si falta, la aplicación avisa al arrancar.

## Instalar y arrancar (Windows)

```bat
git clone <este repositorio> echo-hoard
cd echo-hoard
python -m venv venv
venv\Scripts\pip install -r requirements.txt
npm install
npm run build
venv\Scripts\python -m echo
```

Abre http://127.0.0.1:5188, entra en **Historial** para ver y buscar lo que has copiado, **Fijados** para tus copias fijadas, y **Estado** para pausar/reanudar la vigilancia y purgar copias antiguas.

- `python scripts/launch.py` arranca en un puerto libre y abre el navegador.
- `python scripts/dev.py` lanza uvicorn con recarga y el servidor de Vite.

## Configuración (variables de entorno)

| Variable | Por defecto | Significado |
| --- | --- | --- |
| `ECHO_PORT` / `PORT` | `5188` | Puerto preferido; `PORT_STRICT=1` lo fija, si no se usa el primero libre. |
| `ECHO_DATA_DIR` | `<repo>/data` | Base de datos, `images/`, `mcp-token`. |
| `ECHO_BACKEND` | `auto` | `auto` \| `windows` \| `generic` \| `fake`. |
| `ECHO_AUTOSTART` | `1` | `0` desactiva el arranque automático de la vigilancia. |
| `ECHO_RETENTION_DAYS` | `30` | Las copias sin fijar más antiguas se purgan; `0` las conserva para siempre. |
| `ECHO_MAX_CLIPS` | `5000` | Límite de copias sin fijar; se eliminan antes las más antiguas. |
| `ECHO_MAX_IMAGE_MB` | `200` | Límite de espacio total en imágenes; se eliminan antes las más antiguas. |
| `ECHO_OCR_ENABLED` | `0` | Pon `1` para reconocer el texto de las imágenes nuevas. Se usa el motor de OCR de la familia (Kafka's Hoard, a través del hub: `fam_docs.ocr_image` de Hoard Link) si está en marcha y, si no, un Tesseract local (PATH, `ECHO_TESSERACT` o las carpetas de instalación habituales de Windows). Las imágenes se guardan aunque ninguno esté disponible o falle. |
| `ECHO_OCR_LANG` | `spa+eng` | Idioma(s) como los escribe Tesseract, por ejemplo `eng+spa`; el primero es el que se pide al servicio de la familia. Si falta el paquete, el motor local reintenta con `eng`. |
| `ECHO_EXCLUDE_APPS` | `KeePass,1Password,Bitwarden,keepassxc` | Nombres de proceso, separados por comas, que nunca se capturan. |
| `ECHO_ALLOWED_HOSTS` | | Nombres de host adicionales aceptados detrás de un túnel. |

### Acceso desde el móvil (a través de un túnel)

El servidor escucha en 127.0.0.1 y solo responde a peticiones cuyo `Host` sea `localhost`, `127.0.0.1` o `[::1]`. Para entrar desde el móvil, indicad los nombres de host adicionales en `ECHO_ALLOWED_HOSTS`, separados por comas, exactos o `*.sufijo`: `ECHO_ALLOWED_HOSTS=mi-pc.example,*.ts.net`. Una vez abierta a través del túnel, el navegador ofrece instalarla (PWA).

## Asistente de Faustus

Con el lanzador compartido de Hoard Link instalado, la app muestra el panel de Faustus de la familia (un botón flotante). La conversación, el modelo y las herramientas viven en Faustus; esta app solo le dice al panel qué hay abierto.

- **Contexto por vista.** La vista indica la página (`history`, `pinned`, `status`), los filtros activos (`kind`, texto de búsqueda) y los ids de los clips en pantalla (hasta 20). Un clip cuya etiqueta se está editando se envía como `clip` con su id real, tipo, aplicación de origen, última vez visto, veces, fijado, etiqueta, etiquetas, tamaño y una vista previa de 200 caracteres como máximo. El texto completo del clip nunca se envía, y los clips sensibles o borrados quedan fuera por completo, también de los ids visibles. Si no se edita ningún clip, no se envía ningún objeto.
- **Campos sin guardar.** El panel los pide con el evento de ventana `echo:context-request`. El editor de etiqueta abierto (`clip-label`) responde con la etiqueta escrita hasta ahora y una marca `dirty`.
- **Refresco.** Cuando el asistente termina un turno, la vista abierta se recarga en el sitio (`hoard:copilot-turn-end` / `window.hoardCopilot.onTurnEnd`, unidos en una sola recarga). Una etiqueta que estás escribiendo conserva tu texto; una sin tocar sigue al valor nuevo.
- **Guardado.** El editor de etiqueta envía solo el campo cambiado en `PATCH /api/clips/{id}`, que fusiona solo los campos que lleva (`null` y los campos desconocidos se ignoran; una etiqueta vacía la borra).
- **Pruebas.** `node --test client/copilot-context.test.mjs` y `venv\Scripts\python -m pytest -q tests/test_api.py`.

## Conectar el asistente (MCP)

El guardia de peticiones, el formato de errores, los ficheros PWA, el servidor de la SPA (sin caché para `index.html`), las rutas del agente, el puente MCP, la clase de base de datos y el constructor de consultas de búsqueda son los comunes de Hoard Link (`echo/hoard_link/`). Un segundo `python -m echo` avisa de que ya está en marcha y sale sin tocar el token ni la base de datos; el token de `data/mcp-token` se crea una vez y no cambia.

`mcp_server.py` es un puente stdio: pide la lista de herramientas a la aplicación en marcha y reenvía cada llamada a `POST /api/agent/call` con el token de `data/mcp-token`. Nunca abre la base de datos. Faustus detecta la aplicación por `/api/health` y rellena la conexión con `faustus-plugin.json`.

Herramientas: `clip_recent`, `clip_search`, `clip_get`, `clip_set`, `clip_copy`, `clip_pin`, `clip_delete`, `clip_status` y `clip_capture`. Las instrucciones obligan al asistente a tratar el historial como datos del propio usuario, a no leer nunca una copia marcada como sensible ni pedir al usuario que la revele, a decir siempre qué ha puesto en el portapapeles con `clip_set`, y a no tocar nunca la base de datos directamente.

## Pruebas

```bat
venv\Scripts\python -m pytest -q
```

## Límites (v1)

- El backend genérico (Linux/macOS) no detecta la aplicación de origen ni captura imágenes.
- La búsqueda es solo por palabras (FTS5); no hay búsqueda semántica.
- No hay sincronización entre dispositivos: los datos viven en el ordenador donde corre la aplicación.

## Licencia

MIT — Luissalet.
