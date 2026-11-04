# Contrato de API de Centinela (no modificar sin permiso)

Base: `http://localhost:8000`. JSON salvo indicación. Tipos: ver `backend/src/models/schemas.py`.

| Método y ruta | Entrada | Salida |
|---|---|---|
| `POST /reports/audio` | multipart: `file` (audio, máx. 10 MB; webm/m4a/mp3/wav). El backend lo convierte con ffmpeg a WAV mono 24 kHz antes de transcribir (ffmpeg debe estar instalado) | `Report` |
| `GET /reports` | n/a | `[{report: Report, verdict: Verdict}]` |
| `POST /reports/{id}/photo` | multipart: `file` (foto, máx. 8 MB; jpeg/png/webp, tipo validado por contenido). 404 si el reporte no existe | `{evidence: Evidence, verdict: Verdict, has_mask: bool}`; `evidence.type = "photo"`, `verdict` = veredicto re-calculado del reporte |
| `GET /evidence/{id}` | n/a | `Evidence` |
| `GET /evidence/{id}/mask` | n/a | `image/png` (RGBA). 404 si la evidencia no tiene máscara |
| `GET /zones` | n/a | GeoJSON FeatureCollection; properties = `Zone` |
| `GET /flood-layer` | n/a | GeoJSON (polígonos de agua por NDWI) |
| `GET /stream` | n/a | SSE; cada evento `data:` = `AgentEvent` en JSON |
| `POST /alerts/draft` | `{zone_id}` | `AlertDraft` (approved=false) |
| `POST /alerts/{zone_id}/approve` | n/a | `AlertDraft` (approved=true, solo simulado) |

Idiomas: `Report.text` y los nombres de lugares quedan en español. `Report.summary_en`
(opcional) es un resumen de una frase en inglés. `Verdict.reason` se escribe en inglés.
`AlertDraft.text` = texto en español para la comunidad, una línea en blanco (`\n\n`) y su
traducción al inglés.

Máscara de foto: PNG RGBA al tamaño completo de la foto (w×h que reporta SAM), fondo
transparente; el frontend la superpone escalada al tamaño de la foto. Colores por clase:
agua `rgba(56,152,236,140)`, casas `rgba(163,163,163,150)`, vehículos
`rgba(250,204,21,170)`, personas `rgba(242,107,29,190)` (de abajo arriba en ese orden).
En evidencia de foto, `value` = fracción de la imagen segmentada como agua (0-1),
calculada en código; `null` si no se midió o si Spark y SAM se contradicen.

Reglas: validar tipo y tamaño de archivos, limitar peticiones por IP (rate limit),
nunca devolver trazas internas ni claves en errores, CORS solo al origen del frontend.
Errores: `{"error": "mensaje corto"}` con código HTTP adecuado.
