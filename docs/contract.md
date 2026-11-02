# Contrato de API de Centinela (no modificar sin permiso)

Base: `http://localhost:8000`. JSON salvo indicación. Tipos: ver `backend/src/models/schemas.py`.

| Método y ruta | Entrada | Salida |
|---|---|---|
| `POST /reports/audio` | multipart: `file` (audio, máx. 10 MB, mp3/wav/m4a/webm) | `Report` |
| `GET /reports` | n/a | `[{report: Report, verdict: Verdict}]` |
| `GET /evidence/{id}` | n/a | `Evidence` |
| `GET /zones` | n/a | GeoJSON FeatureCollection; properties = `Zone` |
| `GET /flood-layer` | n/a | GeoJSON (polígonos de agua por NDWI) |
| `GET /stream` | n/a | SSE; cada evento `data:` = `AgentEvent` en JSON |
| `POST /alerts/draft` | `{zone_id}` | `AlertDraft` (approved=false) |
| `POST /alerts/{zone_id}/approve` | n/a | `AlertDraft` (approved=true, solo simulado) |

Reglas: validar tipo y tamaño de archivos, limitar peticiones por IP (rate limit),
nunca devolver trazas internas ni claves en errores, CORS solo al origen del frontend.
Errores: `{"error": "mensaje corto"}` con código HTTP adecuado.
