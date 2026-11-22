# URL HTTPS pública para la API local (demo con Copilot Studio)

Consulta: 2026-11-22. Rama chore/t25-manual-steps.

## Pregunta
¿Qué opciones oficiales y gratuitas/baratas exponen la API FastAPI local (puerto 8000, Docker) por HTTPS público para que Copilot Studio la llame durante la demo?

## Respuesta
1. **Microsoft Dev Tunnels** (recomendada: oficial Microsoft, HTTPS forzado, TLS 1.2+). Instalar: `winget install Microsoft.devtunnel`. Login (obligatorio incluso para hospedar; cuenta Microsoft, Entra o GitHub): `devtunnel user login`. Hospedar: `devtunnel host -p 8000 --allow-anonymous`. URL: `https://<tunnel_id>-8000.<region>.devtunnels.ms/`. Por defecto el túnel es privado (solo el creador); Copilot Studio no puede iniciar sesión con tu cuenta, así que hace falta acceso anónimo. La página anti-phishing solo aparece en GET con `Accept: text/html`; no afecta a POST/JSON (o enviar el header `X-Tunnel-Skip-AntiPhishing-Page`). Límites de tiempo, ancho de banda y túneles por usuario: ⚠ verificar en pantalla (no confirmados en las fuentes consultadas). `--allow-anonymous` está confirmado como opción de acceso; que `host` lo acepte directamente: ⚠ verificar con `devtunnel host -h` (si no, `devtunnel access create <id> -p 8000 --anonymous`, ⚠ verificar).
2. **Cloudflare quick tunnel**: `cloudflared tunnel --url http://localhost:8000`. Sin cuenta ni dominio; URL `*.trycloudflare.com` aleatoria que cambia en cada ejecución y deja de funcionar al cerrar el proceso. Límites: 200 peticiones en vuelo (429 al exceder), sin SSE, sin garantía de uptime; "solo pruebas y desarrollo". Instalación de `cloudflared` en Windows: ⚠ verificar en pantalla (no consultada).
3. **ngrok free**: `ngrok http 8000` (requiere cuenta y authtoken, ⚠ verificar comando de token). Cuota mensual: 1 GB, 20,000 peticiones HTTP, 4,000 req/min; hasta 3 endpoints; 1 dominio de desarrollo asignado; sin timeout. Muestra página intersticial en tráfico HTML (se evita con el header `ngrok-skip-browser-warning`).
4. **Alternativa Azure Container Apps / App Service**: no investigada en esta consulta (límite de 3 fuentes). ⚠ verificar. Implica publicar la imagen en un registro y costo; solo si hace falta URL estable fuera de la demo.

## Riesgos de seguridad
- Con acceso anónimo cualquiera con la URL llega a la API: la **API key es la única barrera**. Viaja cifrada por HTTPS, pero el TLS termina en el ingreso del proveedor (en Dev Tunnels se reescriben cabeceras tras terminar TLS).
- Exponer solo los endpoints necesarios; desactivar `/docs`, `/redoc` y `/openapi.json` públicos durante la demo (la importación a Copilot Studio usa el archivo exportado, no la URL).
- Usar una API key solo para la demo, aleatoria y larga; rotarla al terminar y cerrar el túnel (Ctrl+C; borrar con `devtunnel delete`, ⚠ verificar comando).
- Datos 100% sintéticos; no exponer `.env` ni logs.
- Tras abrir el túnel, actualizar `host` en `integrations/copilot_studio/openapi.json` con el host del túnel.

## Decisión recomendada
Dev Tunnels con acceso anónimo + API key de demo rotable; Cloudflare quick tunnel como plan B (sin cuenta); ngrok como tercera opción.

## Fuentes (3 proveedores; Dev Tunnels usa 2 páginas)
- Create and host a tunnel - Microsoft dev tunnels. https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/get-started (consulta 2026-11-22)
- Dev tunnels security. https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/security (2026-11-22)
- Quick Tunnels - Cloudflare. https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/ (2026-11-22)
- ngrok free plan limits. https://ngrok.com/docs/pricing-limits/free-plan-limits (2026-11-22)
