# Contrato de API de Centinela (no modificar sin permiso)

Base: `http://localhost:8000`. JSON salvo indicación. Tipos: ver `backend/src/models/schemas.py`.

| Método y ruta | Entrada | Salida |
|---|---|---|
| `POST /reports/audio` | multipart: `file` (audio, máx. 10 MB; webm/m4a/mp3/wav). El backend lo convierte con ffmpeg a WAV mono 24 kHz antes de transcribir (ffmpeg debe estar instalado) | `Report` |
| `GET /reports` | n/a | `[{report: Report, verdict: Verdict}]` |
| `GET /evidence/{id}` | n/a | `Evidence` |
| `GET /zones` | n/a | GeoJSON FeatureCollection; properties = `Zone` |
| `GET /flood-layer` | n/a | GeoJSON (polígonos de agua por NDWI) |
| `GET /stream` | n/a | SSE; cada evento `data:` = `AgentEvent` en JSON |
| `POST /alerts/draft` | `{zone_id}` | `AlertDraft` (approved=false) |
| `POST /alerts/{zone_id}/approve` | n/a | `AlertDraft` (approved=true, solo simulado) |

Idiomas: `Report.text` y los nombres de lugares quedan en español. `Report.summary_en`
(opcional) es un resumen de una frase en inglés. `Verdict.reason` se escribe en inglés.
`AlertDraft.text` = texto en español para la comunidad, una línea en blanco (`\n\n`) y su
traducción al inglés.

Reglas: validar tipo y tamaño de archivos, limitar peticiones por IP (rate limit),
nunca devolver trazas internas ni claves en errores, CORS solo al origen del frontend.
Errores: `{"error": "mensaje corto"}` con código HTTP adecuado.
