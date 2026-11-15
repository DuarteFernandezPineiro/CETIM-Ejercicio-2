# CETIM · Ejercicio 2

API que responde preguntas sobre los cinco artículos facilitados de teledetección hiperespectral e índices de vegetación, con 82 páginas en total. Cada respuesta incluye el documento, la página y el texto que se usó como evidencia. Cuando el sistema carece de una cita comprobable, devuelve una abstención.

El caso de uso es localizar resultados y métodos dentro de documentación técnica. Los artículos están en inglés, por lo que la búsqueda y la generación admiten preguntas en español. Se conserva el corpus facilitado para que la consulta se pueda contrastar con los mismos documentos.

## Ejecutar en local

Requiere **Python 3.11**, Ollama y conexión a internet para instalar las dependencias y descargar los modelos por primera vez. El modelo de generación ocupa aproximadamente 1,9 GB. Los comandos se ejecutan desde la raíz del repositorio, donde están `requirements.txt` y `Papers/`. [Descargar Ollama](https://ollama.com/download)

Abre Ollama. Si instalaste solo su CLI, ejecuta `ollama serve` en una terminal aparte y mantenla abierta. Después, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull qwen2.5:3b
.\.venv\Scripts\python.exe -m uvicorn app.main:app
```

En Linux y macOS, usa `python3.11` para crear el entorno y `.venv/bin/python` para instalar las dependencias y arrancar la API. Por defecto, la API escucha en `127.0.0.1:8000` y se conecta a Ollama en `127.0.0.1:11434`. Puedes cambiar la dirección y el modelo de Ollama con `OLLAMA_URL` y `OLLAMA_MODEL`.

La API carga el modelo de embeddings e indexa los PDFs en memoria en cada arranque. Espera a `Application startup complete` antes de abrir Swagger o ejecutar la consulta desde otra terminal. La primera consulta puede tardar más porque Ollama carga el modelo en memoria. [Swagger](http://127.0.0.1:8000/docs)

```powershell
$body = @{ question = '¿Qué rango espectral cubría el espectrómetro usado en el estudio del tomate?' } | ConvertTo-Json
$result = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/query' -ContentType 'application/json; charset=utf-8' -Body $body
$result | ConvertTo-Json -Depth 5
```

## Contrato de `POST /query`

Envía un JSON con `question` de entre 1 y 500 caracteres, después de quitar espacios al inicio y al final. La respuesta incluye `answer` y `sources`. Las etiquetas como `[1]` apuntan a `sources[].id`. Cada fuente incluye el nombre del PDF, el título, la página física contando desde 1, el fragmento de contexto (`excerpt`) y las citas textuales verificadas dentro del fragmento (`quotes`).

| HTTP | Resultado |
| --- | --- |
| 200 | Respuesta con fuentes o abstención con `sources: []` |
| 422 | Pregunta vacía, demasiado larga o JSON incompatible |
| 503 | Ollama no es accesible o expira la consulta |
| 502 | Ollama rechaza la petición o devuelve una respuesta con formato inválido |

## Cómo funciona y por qué

1. **Extracción.** [`app/index.py`](app/index.py) lee el texto de cada página con PyMuPDF y conserva el nombre, el título y la página. Se limpian espacios, ligaduras, encabezados y pies de página. La ingesta se detiene al encontrar el encabezado de bibliografía para que una referencia a otro trabajo no compita con el método o el resultado del propio artículo. Esta limpieza se ajustó a los PDFs facilitados. La extracción tiene cobertura limitada para figuras, fórmulas y tablas complejas.
2. **Fragmentación.** Cada fragmento tiene hasta 300 tokens de E5, con 50 de solapamiento y preferencia por finales de párrafo cercanos al límite. Se usan tokens para controlar el tamaño que recibe el modelo. El solapamiento reduce los cortes entre una afirmación y sus condiciones. Los fragmentos terminan dentro de su página para poder citarla directamente, a costa de que una explicación que cruza página pueda requerir dos pasajes. Los tamaños son valores de partida.
3. **Recuperación.** Multilingual E5 Small coloca preguntas en español y pasajes en inglés en el mismo espacio vectorial. Se aplican los prefijos `query:` y `passage:` que espera el modelo y se añade el título al pasaje para aportar el contexto del estudio. La búsqueda ordena por similitud coseno y pasa hasta seis fragmentos al generador. La comparación exacta en memoria basta para cinco artículos y evita mantener un servicio adicional. Se amplió el límite de cuatro a seis al comprobar que el pasaje sobre el recorte espectral de Brassica quedaba sexto. Es un ajuste de prototipo que habría que contrastar con más preguntas. [Ficha de E5 Small](https://huggingface.co/intfloat/multilingual-e5-small)
4. **Generación y citas.** [`app/main.py`](app/main.py) pide a Qwen2.5 3B mediante Ollama una respuesta y citas textuales en el idioma del documento. El modelo se ejecuta localmente y cabe en el equipo utilizado. Se pide una salida estructurada para validar ambos campos. La API obtiene el PDF y la página a partir de la coincidencia textual. Se abstiene si falta evidencia, si alguna cita carece de coincidencia o si las citas omiten una cifra explícita de la respuesta. La comprobación de cifras es literal y puede rechazar conversiones o cambios de formato. La pertinencia de las citas y el respaldo de cada afirmación se revisan por separado. [Modelo en Ollama](https://ollama.com/library/qwen2.5:3b)

## Con un corpus 100 veces mayor

El índice actual tiene 254 vectores de 384 componentes y su matriz ocupa unos 381 KiB. Si se mantiene la misma densidad de fragmentos, con 100 veces más documentos la matriz ocuparía unos 37 MiB. La estimación cubre solo los vectores.

El primer cambio sería persistir los fragmentos y sus vectores, con una huella de cada PDF y la versión de la extracción y los embeddings. Así se podrían añadir, actualizar y retirar documentos sin recalcular todo el corpus en cada arranque. Mantendría la búsqueda exacta como referencia y mediría latencia y memoria antes de incorporar un índice aproximado. Si lo incorporase, comprobaría cuántas páginas relevantes se pierden respecto de la búsqueda exacta. Si los resultados muestran fallos frecuentes con siglas, códigos o unidades, compararía la recuperación actual con una búsqueda híbrida de vectores y palabras clave.

## Cómo mediría la calidad

Prepararía preguntas con respuesta y páginas de referencia revisadas manualmente. Incluiría consultas numéricas, comparaciones entre artículos y preguntas sin respuesta, también del mismo tema. En una comparación anotaría todas las páginas necesarias para dar una respuesta completa.

| Qué medir | Cómo y para qué |
| --- | --- |
| Recuperación | `Recall@6` a nivel de página sobre preguntas con respuesta, deduplicando páginas recuperadas. Mostraría también cuántas comparaciones recuperan todas las páginas necesarias. Un resultado bajo apunta a la extracción, los fragmentos o la búsqueda. |
| Respuesta y citas | Revisar si la respuesta es correcta y completa, conserva cifras y unidades y si las citas respaldan cada afirmación. Una página recuperada correctamente puede acabar citada con un extracto que omita el dato. |
| Abstención | Medir qué proporción de preguntas sin evidencia acaba en abstención y cuántas preguntas respondibles también se rechazan. |
| Latencia | Registrar mediana y percentil 95 de recuperación y generación por separado. Medir el arranque en frío aparte porque incluye la indexación y la carga del modelo. |

## Comprobaciones realizadas

Instalé `requirements.txt` en un entorno de Python 3.11 nuevo en Windows, comprobé las dependencias con `pip check` y ejecuté las consultas contra Uvicorn con los pesos descargados y Ollama local. Revisé los resultados y sus citas contra los PDFs.

| Pregunta | Resultado observado |
| --- | --- |
| ¿Qué rango espectral cubría el espectrómetro usado en el estudio del tomate? | **350–2500 nm**. [Tomate, p. 6](Papers/sensors-21-05705.pdf#page=6) |
| ¿Pudo el índice RVI746/670 identificar a los dos días el daño de seis a ocho ninfas de BPH por planta de arroz? | El índice no detectó ese daño a los dos días. [Arroz, p. 1](Papers/sensors-19-00375.pdf#page=1) |
| ¿A qué intervalo de longitudes de onda se recortaron los espectros de Brassica en el preprocesamiento para reducir ruido? | **400–950 nm**. [Brassica, p. 5](Papers/sensors-24-01916.pdf#page=5) |
| Compara el rango del espectrómetro para el tomate con el rango medido en el artículo sobre mildiu de Brassica. | **Comparación fallida.** Los primeros ocho pasajes de la búsqueda eran de Brassica. La respuesta omitió la comparación y citó una fórmula ajena al rango medido. |
| ¿Qué densidad de siembra recomendaron los artículos para cultivar tomate en un invernadero de Islandia? | Abstención. Antes de comprobar las cifras, la API devolvió un porcentaje que no aparecía en la cita. |
| ¿Cuál es la capital de Islandia? | Abstención con `sources: []`. |
| Pregunta compuesta solo por espacios | HTTP 422. |

En la comparación, la fórmula citada existe en el documento y su texto es verificable. La revisión manual detectó que era irrelevante. Con más tiempo probaría recuperar cada estudio por separado y reunir sus pasajes antes de generar la comparación.

Las pruebas de regresión comprueban la asignación de una cita a su página y la abstención cuando el modelo inventa una cita o introduce una cifra ausente de la evidencia. Se ejecutan con las dependencias de Python instaladas:

```powershell
python -m unittest discover -s tests -v
```

## Uso de IA

Codex ayudó a interpretar el enunciado, propuso la arquitectura y las métricas, escribió el prototipo y las pruebas, ejecutó las comprobaciones y redactó la documentación técnica. Duarte aprobó continuar con el plan, priorizó la consulta del tomate como primer hito y pidió dar especial peso a la claridad y a la justificación de las decisiones.

## Fuentes del corpus

Los cinco artículos se distribuyen con licencia CC BY y los PDFs conservan sus avisos originales.

- Feng et al. (2017), *Canopy Vegetation Indices from In situ Hyperspectral Data to Assess Plant Water Status of Winter Wheat under Powdery Mildew Stress*. [DOI](https://doi.org/10.3389/fpls.2017.01219)
- Tan et al. (2019), *Sensitivity of a Ratio Vegetation Index Derived from Hyperspectral Remote Sensing to the Brown Planthopper Stress on Rice Plants*. [DOI](https://doi.org/10.3390/s19020375)
- Alordzinu et al. (2021), *Ground-Based Hyperspectral Remote Sensing for Estimating Water Stress in Tomato Growth in Sandy Loam and Silty Loam Soils*. [DOI](https://doi.org/10.3390/s21175705)
- Liu et al. (2024), *Investigation of Using Hyperspectral Vegetation Indices to Assess Brassica Downy Mildew*. [DOI](https://doi.org/10.3390/s24061916)
- Nitu et al. (2025), *NDVI and Beyond: Vegetation Indices as Features for Crop Recognition and Segmentation in Hyperspectral Data*. [DOI](https://doi.org/10.3390/s25123817)
