# meta_hackaton

## Configuración

Copia `.env.example` a `.env` (ignorado por git) y rellena las variables. Nunca subas claves al repo.

| Variable | Por defecto | Para qué sirve |
|---|---|---|
| `MODEL_API_KEY` | (vacía) | Clave de la API de Meta. Obligatoria para llamar a los modelos. |
| `ASR_MODEL` | `muse-voice-transcribe-1.0` | Modelo de transcripción de voz. |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Único origen que admite CORS en la API. |
| `LATENCY_TUNING` | `on` | Ajuste de latencia de las llamadas a Muse Spark (ver abajo). |

### `LATENCY_TUNING`

- `on` (por defecto): las llamadas a Muse Spark (extracción, verificación, alerta, boletín,
  visión y orquestación) usan `reasoning_effort="low"` y un tope de `max_tokens`. Si una llamada
  falla por una causa que el ajuste puede provocar (respuesta truncada con
  `finish_reason=length`, parámetro rechazado con HTTP 400/422 o JSON inválido), se hace **un
  único** reintento con los parámetros por defecto de la API. Si la API rechaza el parámetro, el
  ajuste se desactiva para ese tipo de llamada hasta reiniciar el proceso.
- `off` (también `0`, `false`, `no`): todas las llamadas usan los parámetros que había antes del
  ajuste (sin `reasoning_effort` ni `max_tokens`) y no hay reintento.

Cuando una llamada falla, su causa (tipo de excepción, código HTTP, `request_id`,
`finish_reason` y tokens usados, sin la clave) queda en el log del servidor y en la salida de
`scripts/smoke_pipeline.py` y `scripts/smoke_evidence.py`. Las respuestas de la API solo
devuelven un mensaje corto (`{"error": "..."}`).
