# CETIM · Ejercicio 2

Al consultar documentación técnica, localizar una medida exige identificar el estudio y la etapa a la que corresponde. Un mismo artículo puede dar un rango para el sensor, otro para el preprocesamiento y otros valores al definir índices. El objetivo es responder preguntas en español sobre los cinco artículos facilitados, escritos en inglés, y permitir que el lector compruebe la respuesta en el documento y la página originales.

La generación aumentada por recuperación (RAG) busca primero los pasajes pertinentes y los usa como contexto de la respuesta. Así, la generación recibe evidencia concreta y la API conserva su procedencia. Con cinco PDF y 82 páginas, un índice en memoria, búsqueda exacta y un generador local permiten reconstruir e inspeccionar el recorrido completo con pocos componentes.

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

En la consulta del tomate, `[1]` enlaza con el pasaje recuperado en primer lugar. `excerpt` muestra el contexto completo del pasaje y `quotes` recoge el texto que la API verificó dentro de él. `page` localiza la evidencia en el PDF. El texto conserva los cortes de la extracción y la fragmentación. [Artículo del tomate, p. 6](Papers/sensors-21-05705.pdf#page=6)

<details>
<summary>JSON completo devuelto por la API (HTTP 200)</summary>

```json
{
  "answer": "El espectrómetro usado en el estudio del tomate cubría un rango espectral de 350 a 2500 nanómetros. [1]",
  "sources": [
    {
      "id": 1,
      "document": "sensors-21-05705.pdf",
      "title": "Ground-Based Hyperspectral Remote Sensing for Estimating Water Stress in Tomato Growth in Sandy Loam and Silty Loam Soils",
      "page": 6,
      "excerpt": "into a rectangular sketch of white paper. Leaf area was calculated using grid or graph paper technique, a linear regression model of leaf area (LA) developed [23]. The leaf area of the tomato was related to variable leaf dimensions (LL and LW) using an equation by [23] LA = 0.00409 × 192.68 × LL 100 × LW 100 −1 , (5) where, LA, Leaf area (m2), LL, Leaf length (cm), and LW. Leaf Area Index (LAI) using the equation by [55]. LAI = LAm × N A , (6) where N is the number of leaves on the plant and A the area (cm2) occupied by one plant in the cropped area. 2.6. Hyperspectral Data Acquisition and Processing Hyperspectral remote sensing is the measurement of reflected radiance on the narrow continuous spectral bands over the full visible and solar reflective spectrum. Tomato leave reflectance was measured using Analytical Spectral Device (ASD) Field Spec 4 (FS4), a non-image spectrometer. The spectral range of this highly resolving device covers wavelengths between 350 and 2500 nm, spectral resolution varying from 3 to 700 nm in the very short and 10 to 1400/2100 nm in the",
      "quotes": [
        "The spectral range of this highly resolving device covers wavelengths between 350 and 2500 nm, spectral resolution varying from 3 to 700 nm in the very short and 10 to 1400/2100 nm in the"
      ]
    }
  ]
}
```

</details>

## Decisiones técnicas

| Etapa | Decisión, ventajas y límites |
| --- | --- |
| Extracción | PyMuPDF lee los bloques de texto en el orden almacenado en el PDF. Se normalizan ligaduras y espacios, se filtran bloques en los márgenes y se detiene la ingesta en el encabezado `References` para reducir ruido bibliográfico. Se conserva la página física. Las reglas son simples y dependen del diseño de estos PDF. Una tabla puede perder la asociación entre filas y columnas, una fórmula el orden de sus símbolos y una figura quedar reducida a su pie. Para documentos escaneados o cuya evidencia esté en tablas, evaluaría OCR o extracción sensible al diseño, con revisión contra el original. |
| Fragmentación | Los pasajes quedan dentro de una página y tienen hasta **300 tokens de E5**, con **50 de solapamiento** y preferencia por los finales de párrafo cercanos al límite. Esto facilita asignar páginas y reduce cortes de contexto, a cambio de repetir contenido y separar explicaciones que cruzan páginas. Dividir por secciones podría conservar mejor métodos y resultados, con tamaños irregulares y necesidad de conservar los límites de página. Los valores 300/50 son una elección de diseño. |
| Embeddings | Multilingual E5 Small codifica en CPU pasajes en inglés y preguntas en español. Se usan `passage:` y `query:` y se añade el título al pasaje para identificar el estudio. Una búsqueda por términos sería una alternativa para siglas o identificadores exactos y requeriría resolver la diferencia de idioma. Los ejemplos prueban que la recuperación multilingüe funciona en algunas consultas. La elección del modelo y el uso del título quedan sin una comparación controlada. [Ficha de E5 Small](https://huggingface.co/intfloat/multilingual-e5-small) |
| Búsqueda exacta y `top-k` | Un producto matricial sobre vectores normalizados calcula todos los cosenos. La búsqueda exacta es una referencia fácil de reproducir con 254 vectores. Un índice aproximado añadiría un compromiso entre velocidad y recuperación. Se pasó de **4 a 6 pasajes** porque la evidencia del recorte de Brassica quedó sexta. Ampliar `k` aumenta la cobertura potencial, el ruido y el contexto que procesa el generador. El ajuste se apoya en ese caso concreto. |
| Generación local | Qwen2.5 3B mediante Ollama mantiene los documentos y las preguntas en el equipo con la configuración por defecto. Se pide JSON estructurado con respuesta y evidencia. A cambio, la latencia y la calidad dependen del hardware y el modelo. Un modelo más grande o remoto podría mejorar la síntesis y exigiría medir calidad, latencia, coste y dónde se procesan los pasajes. El código fija **3.072 tokens de contexto** y un máximo de **256 tokens generados**. Títulos, instrucciones y pregunta consumen contexto, y los tokens de Ollama difieren de los de E5. Un contexto lleno puede dejar fuera evidencia y una salida cortada puede producir JSON inválido. [Modelo en Ollama](https://ollama.com/library/qwen2.5:3b) |
| Validación | La API localiza las citas en los pasajes recuperados, deriva de ahí el archivo y la página, y exige que las cifras detectadas en la respuesta aparezcan entre las citas. Devuelve una abstención si falta evidencia o falla alguna comprobación. Estas reglas tienen poco coste. Verificar el significado requeriría revisar cada afirmación contra su evidencia, con revisión humana o un evaluador contrastado con anotaciones humanas. |

[`app/index.py`](app/index.py) · [`app/main.py`](app/main.py)

## Evaluación exploratoria

Se instalaron las dependencias en un entorno nuevo de Python 3.11 en Windows, se comprobó el entorno con `pip check` y se hicieron peticiones a Uvicorn con Ollama local. Los casos se eligieron para inspeccionar el recorrido y diagnosticar fallos. Algunos guiaron ajustes del prototipo, como el cambio de `k`, por lo que estos resultados describen las consultas probadas y carecen de representatividad estadística.

| Caso | Resultado observado |
| --- | --- |
| Rango del espectrómetro del tomate | **350–2500 nm** con la página correcta. [Tomate, p. 6](Papers/sensors-21-05705.pdf#page=6) |
| RVI746/670 ante el daño de seis a ocho ninfas en arroz | El índice no detectó el daño a los dos días. [Arroz, p. 1](Papers/sensors-19-00375.pdf#page=1) |
| Recorte espectral en el preprocesamiento de Brassica | Con cuatro pasajes, el generador confundió las bandas de una fórmula con el recorte. El pasaje pertinente quedó sexto. Con seis pasajes y la instrucción de distinguir medición de procesamiento, la API devolvió **400–950 nm**. El ensayo deja abierta la contribución de cada cambio. [Brassica, pp. 5–6](Papers/sensors-24-01916.pdf#page=5) |
| Densidad de siembra del tomate en Islandia | En una prueba previa, el modelo dio un porcentaje ausente de la cita. Tras añadir la comprobación numérica, la API se abstuvo en esta consulta. |
| Capital de Islandia y pregunta vacía | La primera produjo abstención con `sources: []`. La segunda devolvió HTTP 422 por validación de entrada. |

### Comparación fallida entre tomate y Brassica

La consulta fue «Compara el rango del espectrómetro para el tomate con el rango medido en el artículo sobre mildiu de Brassica». La comparación requiere **350–2500 nm** para el espectrómetro del tomate y **350–1050 nm** para la adquisición en Brassica. Los **400–950 nm** de Brassica corresponden al recorte posterior. Las secciones 2.2 y 2.3 separan esas operaciones. [Tomate, p. 6](Papers/sensors-21-05705.pdf#page=6) · [Brassica, p. 5](Papers/sensors-24-01916.pdf#page=5)

Los **ocho primeros puestos** del diagnóstico quedaron ocupados por pasajes de Brassica. El generador recibió los seis primeros, todos de ese artículo. El ranking global usa un único vector para toda la pregunta y permite que un estudio ocupe todas las posiciones. La coincidencia temática entre «mildiu de Brassica» y el título, añadido a cada pasaje, pudo favorecer esa concentración. Haría falta una prueba con y sin título para estimar su efecto.

Al repetir la consulta, la respuesta dijo que el rango del tomate no se especificaba y mencionó el NDVI 780. La falta de pasajes del tomate explica la comparación incompleta. Citar esa fórmula fue un error de generación y selección de evidencia. La cita era literal y el valor 780 aparecía en ella, así que pasó las dos comprobaciones. Probaría dos búsquedas centradas en adquisición, una por estudio, y mediría si el contexto cubre ambos documentos. Si falta un lado, evaluaría una abstención explícita. [Brassica, p. 7](Papers/sensors-24-01916.pdf#page=7)

### Qué comprueba una cita

La coincidencia textual garantiza que la cita devuelta aparece en un fragmento recuperado tras normalizar el texto. El filtro numérico compara **conjuntos de cifras detectadas** en la respuesta y las citas. Por eso puede rechazar cambios de formato y, a la vez, aceptar unidades incorrectas, relaciones invertidas o negaciones con los mismos números. **Una cita literal no garantiza la corrección semántica.**

Se comprobó directamente con `cite_answer` y la evidencia sintética «Group A reached 350 nm and group B reached 2500 nm». Las tres respuestas erróneas conservaron una fuente en la salida:

- **Unidad:** «El grupo A alcanzó 350 µm y el grupo B 2500 µm».
- **Relación invertida:** «El grupo A alcanzó 2500 nm y el grupo B 350 nm».
- **Contradicción:** «El grupo A no alcanzó 350 nm y el grupo B alcanzó 2500 nm».

Las pruebas de regresión cubren la asignación de página, el rechazo de citas inventadas y la abstención ante cifras sin respaldo.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Cómo mediría la calidad

Prepararía preguntas nuevas con respuestas, afirmaciones y páginas de referencia revisadas manualmente. Mantendría los casos que guiaron ajustes como ejemplos de diagnóstico. Incluiría preguntas numéricas, comparaciones y preguntas sin respuesta dentro y fuera del tema.

| Dimensión | Criterio |
| --- | --- |
| Recuperación | `Recall@6`, proporción de páginas de referencia recuperadas entre los seis pasajes. Deduplicar por PDF y página. En comparaciones, medir también cuántas consultas recuperan evidencia suficiente de todos los estudios. |
| Corrección | Comparar la respuesta con la referencia y revisar exactitud, completitud, unidades y diferencias entre adquisición y procesamiento. |
| Respaldo documental | Medir qué proporción de afirmaciones se deduce de las citas aportadas. Una respuesta puede ser correcta y carecer de respaldo en el pasaje citado. |
| Calidad de las citas | Comprobar archivo, página, pertinencia y cobertura de las afirmaciones. Registrar por separado las citas textualmente válidas que resultan irrelevantes. |
| Abstención | Medir la abstención cuando falta evidencia y los rechazos de preguntas respondibles. Distinguir corpus sin respuesta de recuperación insuficiente. |

Mediría mediana y percentil 95 de recuperación y generación por separado, con el arranque en frío en una medición aparte.

## Con un corpus 100 veces mayor

- **Coste computacional.** La matriz medida tiene 254 × 384 componentes y ocupa 381 KiB. Con una densidad de fragmentos similar, 100 veces más documentos llevarían la matriz a unos 37 MiB. La estimación excluye texto, metadatos y modelos. Crecerían la extracción y la generación de embeddings al arrancar, así como el cálculo de cosenos y la ordenación por consulta. Primero persistiría fragmentos y vectores con huella del PDF y versiones de extracción y modelo, para reindexar solo los cambios. Mediría memoria y latencia antes de evaluar un índice aproximado frente a la búsqueda exacta.
- **Calidad de recuperación.** Más temas, formatos e idiomas aportan candidatos parecidos que pueden desplazar la evidencia pertinente. Versiones de un documento o diferencias de terminología y unidades también pueden hacer relevante el contexto del pasaje. Evaluaría por tipo de documento y pregunta, y probaría filtros por metadatos y recuperación por cada parte de una consulta comparativa. El contexto disponible del generador sigue siendo finito.

## Uso de IA

Utilicé Codex y ChatGPT como apoyo. Aprobé el plan inicial, fijé la consulta del tomate como primer hito, pedí identificar dónde se ejecutan la fragmentación y los embeddings y orienté la revisión hacia el análisis de fallos y la justificación técnica. Codex ayudó a interpretar el enunciado, propuso la arquitectura y las métricas, implementó el prototipo y las pruebas, ejecutó las comprobaciones y redactó y revisó la documentación.

## Fuentes del corpus

Los cinco artículos se distribuyen con licencia CC BY y los PDFs conservan sus avisos originales.

- Feng et al. (2017), *Canopy Vegetation Indices from In situ Hyperspectral Data to Assess Plant Water Status of Winter Wheat under Powdery Mildew Stress*. [DOI](https://doi.org/10.3389/fpls.2017.01219)
- Tan et al. (2019), *Sensitivity of a Ratio Vegetation Index Derived from Hyperspectral Remote Sensing to the Brown Planthopper Stress on Rice Plants*. [DOI](https://doi.org/10.3390/s19020375)
- Alordzinu et al. (2021), *Ground-Based Hyperspectral Remote Sensing for Estimating Water Stress in Tomato Growth in Sandy Loam and Silty Loam Soils*. [DOI](https://doi.org/10.3390/s21175705)
- Liu et al. (2024), *Investigation of Using Hyperspectral Vegetation Indices to Assess Brassica Downy Mildew*. [DOI](https://doi.org/10.3390/s24061916)
- Nitu et al. (2025), *NDVI and Beyond: Vegetation Indices as Features for Crop Recognition and Segmentation in Hyperspectral Data*. [DOI](https://doi.org/10.3390/s25123817)
