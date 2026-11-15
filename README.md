# CETIM · Ejercicio 2

Prototipo RAG para consultar artículos sobre teledetección hiperespectral e índices de vegetación.

## Ejecutar en local

Requiere Python 3.11 y [Ollama](https://ollama.com/download) en ejecución. La primera puesta en marcha descarga los modelos desde Ollama y Hugging Face.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull qwen2.5:3b
.\.venv\Scripts\python.exe -m uvicorn app.main:app
```

En Linux y macOS, usa `.venv/bin/python` en los comandos del entorno virtual. Si Ollama usa otro puerto o modelo, configura `OLLAMA_URL` u `OLLAMA_MODEL` antes de arrancar la API. La API indexa los cinco PDFs de `Papers/` en memoria al iniciar. Espera al mensaje `Application startup complete` antes de consultar.

Abre [Swagger](http://127.0.0.1:8000/docs) o ejecuta desde otra terminal PowerShell:

```powershell
$body = @{ question = '¿Qué rango espectral cubría el espectrómetro usado en el estudio del tomate?' } | ConvertTo-Json
$result = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/query' -ContentType 'application/json; charset=utf-8' -Body $body
$result | ConvertTo-Json -Depth 5
```

La comprobación por HTTP devolvió «El espectrómetro usado en el estudio del tomate cubría un rango espectral de 350 a 2500 nanómetros. [1]» y citó la página **6** de `sensors-21-05705.pdf`. Las etiquetas en `answer`, como `[1]`, coinciden con `sources[].id`. Cada fuente incluye archivo, título, página del PDF y el fragmento original normalizado.

## Decisiones

- Extraemos texto por página en el orden de lectura almacenado en el PDF y excluimos encabezados, pies de página y bibliografía final. Los fragmentos tienen hasta 300 tokens del modelo de embeddings, con 50 de solapamiento y preferencia por los límites de párrafo. Limitar cada fragmento a una página permite citarla con precisión. La extracción de texto tiene cobertura limitada para tablas, fórmulas y figuras.
- Multilingual E5 Small recupera pasajes en inglés para preguntas en español. Aplicamos los prefijos `query:` y `passage:`, añadimos el título a cada pasaje y recuperamos los cuatro más próximos mediante similitud coseno exacta. El corpus cabe en memoria y la búsqueda requiere una multiplicación matricial.
- Qwen2.5 3B en Ollama permite generar respuestas localmente con una descarga de aproximadamente 1,9 GB. El modelo extrae citas textuales y redacta la respuesta. La API localiza cada cita en el texto recuperado para asignarle su PDF y página. La relación entre la evidencia y cada afirmación se evalúa revisando el contenido.
- Con 100 veces más documentos, persistiría el índice y recalcularía solo los PDFs nuevos o modificados. Mediría latencia y memoria antes de pasar a búsqueda aproximada y compararía su recuperación con la búsqueda exacta.
- Para evaluar el sistema, anotaría las páginas de referencia de preguntas directas y comparativas, además de preguntas sin respuesta en el corpus. Mediría `Recall@4` a nivel de página, la proporción de afirmaciones respaldadas por su cita, la tasa de abstención en preguntas sin respuesta y la latencia por etapa.

## Fuentes del corpus

Los cinco artículos se distribuyen con licencia CC BY y los PDFs conservan sus avisos originales.

- Feng et al. (2017), *Canopy Vegetation Indices from In situ Hyperspectral Data to Assess Plant Water Status of Winter Wheat under Powdery Mildew Stress*. [DOI](https://doi.org/10.3389/fpls.2017.01219)
- Tan et al. (2019), *Sensitivity of a Ratio Vegetation Index Derived from Hyperspectral Remote Sensing to the Brown Planthopper Stress on Rice Plants*. [DOI](https://doi.org/10.3390/s19020375)
- Alordzinu et al. (2021), *Ground-Based Hyperspectral Remote Sensing for Estimating Water Stress in Tomato Growth in Sandy Loam and Silty Loam Soils*. [DOI](https://doi.org/10.3390/s21175705)
- Liu et al. (2024), *Investigation of Using Hyperspectral Vegetation Indices to Assess Brassica Downy Mildew*. [DOI](https://doi.org/10.3390/s24061916)
- Nitu et al. (2025), *NDVI and Beyond: Vegetation Indices as Features for Crop Recognition and Segmentation in Hyperspectral Data*. [DOI](https://doi.org/10.3390/s25123817)

## Uso de IA

Codex ayudó a interpretar el enunciado, propuso la arquitectura inicial e implementó la ingesta, la recuperación, la API y la comprobación del primer hito. Duarte aprobó continuar con ese plan y priorizó la consulta del tomate como primer hito.
