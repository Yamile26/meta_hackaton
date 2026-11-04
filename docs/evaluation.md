# Evaluación del verificador

> **DATOS SIMULADOS.** Los 15 casos de `eval/verifier_cases.json` son sintéticos y los escribió el equipo. Esto mide si las reglas deterministas de `backend/src/tools/verify.py` hacen lo que dicen, no la exactitud del sistema con reportes reales. No se llama a ningún modelo.

Generado con `python scripts/eval_verifier.py` el 2026-11-03.

## Resultados

| Métrica | Valor |
|---|---|
| Casos | 15 |
| Exactitud | 100.0% (15/15) |
| Precisión de `confirmado` | 100.0% |
| Falsos confirmados | 0 |

## Matriz de confusión

Filas: respuesta esperada. Columnas: veredicto del código.

| esperado \ código | `confirmado` | `contradicho` | `sin_evidencia` |
|---|---|---|---|
| `confirmado` | 4 | 0 | 0 |
| `contradicho` | 0 | 4 | 0 |
| `sin_evidencia` | 0 | 0 | 7 |

## Casos

| Caso | Grupo | Descripción | Esperado | Código | Revisión humana |
|---|---|---|---|---|---|
| C01 | verdadero | Inundación real en Jirón Progreso: NDWI alto + boletín. | `confirmado` | `confirmado` | no |
| C02 | verdadero | Nuevo Horizonte: NDWI alto + foto con agua. | `confirmado` | `confirmado` | no |
| C03 | verdadero | Sin satélite: foto (3,5 % de agua, caso real de SAM) + boletín, dos fuentes independientes. | `confirmado` | `confirmado` | no |
| C04 | verdadero | Daños materiales con NDWI alto (claim damage). | `confirmado` | `confirmado` | no |
| C05 | contradicho | Avenida Central: NDWI sin cambio, imagen sin nubes. | `contradicho` | `contradicho` | no |
| C06 | contradicho | NDWI baja (suelo más seco que antes). | `contradicho` | `contradicho` | no |
| C07 | contradicho | NDWI seco + foto que no muestra agua: la foto no contradice ni respalda. | `contradicho` | `contradicho` | no |
| C08 | sin_evidencia | Los Cedros: NDWI no concluyente. | `sin_evidencia` | `sin_evidencia` | no |
| C09 | sin_evidencia | Una sola foto con agua: no basta para confirmar. | `sin_evidencia` | `sin_evidencia` | no |
| C10 | sin_evidencia | Pedido de ayuda (need): no verificable con evidencia física aunque haya NDWI alto. | `sin_evidencia` | `sin_evidencia` | no |
| C11 | rumor_dique | Rumor falso: 'se rompió el dique' en Las Palmeras, sin ninguna evidencia. | `sin_evidencia` | `sin_evidencia` | no |
| C12 | rumor_dique | Rumor del dique con el boletín general presente, que solo cubre Jirón Progreso. | `sin_evidencia` | `sin_evidencia` | no |
| C13 | inyeccion | Inyección en el texto del reporte, sin evidencia. | `sin_evidencia` | `sin_evidencia` | no |
| C14 | inyeccion | Inyección en el texto con NDWI seco: debe seguir contradicho. | `contradicho` | `contradicho` | no |
| C15 | inyeccion | Inyección dentro del resumen de una evidencia (texto no confiable) con valor bajo. | `sin_evidencia` | `sin_evidencia` | no |

## Umbrales usados

- NDWI respalda si el cambio es ≥ 0.1; contradice si es < 0.03.
- Foto respalda si el agua cubre ≥ 2% de la imagen entera (SAM 3.1); nunca contradice y nunca confirma sola.
- Boletín respalda si nombra el lugar.
- Confirmado: NDWI respalda, o hay respaldo de al menos 2 tipos de fuente, sin contradicciones.

## Límites

- Los casos se diseñaron conociendo las reglas, así que un 100 % aquí es esperable y no prueba que el sistema funcione en el mundo real.
- No se evalúa la extracción (lugar, tipo, gravedad), que hace el modelo: aquí se dan ya estructurados.
- No se evalúa la opinión ni la explicación del modelo (eso lo cubren los tests de `backend/tests/test_verify.py`).
