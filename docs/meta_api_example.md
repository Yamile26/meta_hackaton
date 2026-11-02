# Ejemplos verificados de la API de Meta
(Tomados de https://dev.meta.ai/docs/quickstart , /docs/structured-output y /docs/speech-to-text.)

## Cliente (OpenAI SDK)
```python
import os
from openai import OpenAI
client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])
```

## JSON fiable con Pydantic (Chat Completions)
```python
resp = client.beta.chat.completions.parse(
    model="muse-spark-1.3",
    messages=[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
    response_format=MiModeloPydantic,
    temperature=0,
)
obj = resp.choices[0].message.parsed
```

## Voz: transcribir un WAV
```python
req = {"mode": "PUSH_TO_TALK", "model": "muse-voice-transcribe-1.0",
       "audioEncoding": "WAV", "languageBias": ["Spanish"],
       "keywords": ["Jirón Progreso", "Las Palmeras", "Ucayali"]}
r = requests.post("https://api.meta.ai/v1/asr/transcribe",
    headers={"Authorization": f"Bearer {os.environ['MODEL_API_KEY']}"},
    files={"request": (None, json.dumps(req), "application/json"),
           "audio": ("a.wav", open("a.wav", "rb"), "audio/wav")}, timeout=120)
texto = r.json()["transcript"]
```
Pendiente de implementar tras leer la doc: imagen y PDF con Spark, y SAM 3.1.
