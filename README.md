# PDFTools - Visor y Selector de Áreas en PDF

Este proyecto contiene una aplicación de Python con interfaz gráfica que permite cargar archivos PDF, visualizarlos y seleccionar áreas específicas sobre ellos.

## Características

- **Visualización de PDF**: Cargar y visualizar archivos PDF página por página
- **Navegación**: Navegar entre páginas con botones anterior/siguiente
- **Rotación independiente por página**: Rotar cada página individualmente en incrementos de 90 grados (↶ ↷ ↺)
- **Zoom**: Ampliar y reducir la vista del PDF
- **Selección de áreas**: Seleccionar áreas rectangulares arrastrando el mouse
- **Gestión de selecciones**: Ver, eliminar y limpiar todas las selecciones
- **OCR Avanzado**: Detección de texto mejorada con múltiples algoritmos de preprocesamiento
- **Extracción de contenido**: Extraer texto respetando la rotación específica de cada página
- **Traducción automática**: Traducir texto detectado usando DeepSeek API
- **Configuraciones avanzadas**: Guardar y cargar configuraciones con estilos personalizados y rotaciones

## Instalación

1. **Instalar Python** (versión 3.7 o superior)

2. **Instalar las dependencias**:
   ```powershell
   pip install -r requirements.txt
   ```

   O manualmente:
   ```powershell
   pip install PyMuPDF Pillow
   ```

## Uso

### Visor Básico de PDF

Ejecutar el visor básico:
```powershell
python pdf_viewer.py
```

### Extractor de Contenido

Para la versión avanzada con extracción de contenido:
```powershell
python pdf_extractor.py
```

## Instrucciones de Uso

1. **Cargar PDF**: Haz clic en "Cargar PDF" y selecciona tu archivo
2. **Navegar**: Usa los botones "◀ Anterior" y "Siguiente ▶" para moverte entre páginas
3. **Zoom**: Usa los botones "+" y "−" para ampliar o reducir la vista
4. **Seleccionar áreas**: 
   - Mantén presionado el botón izquierdo del mouse
   - Arrastra para crear un rectángulo sobre el área deseada
   - Suelta el botón para finalizar la selección
5. **Gestionar selecciones**:
   - Las áreas aparecen listadas en la parte inferior
   - Doble clic en la lista para eliminar una selección
   - Usa "Limpiar Selecciones" para eliminar todas

### Funciones Avanzadas (pdf_extractor.py)

- **Extraer Texto**: Extrae el texto de todas las áreas seleccionadas
- **Extraer Imágenes**: Obtiene información sobre imágenes en las áreas
- **Guardar Coordenadas**: Exporta las coordenadas a un archivo de texto

## Archivos del Proyecto

- `pdf_viewer.py`: Visor básico de PDF con selección de áreas
- `pdf_extractor.py`: Versión avanzada con extracción de contenido
- `requirements.txt`: Dependencias del proyecto
- `README.md`: Este archivo de documentación

## Dependencias

- **PyMuPDF (fitz)**: Para manejar archivos PDF
- **Pillow (PIL)**: Para procesamiento de imágenes
- **OpenCV (cv2)**: Para procesamiento avanzado de imágenes en OCR
- **pytesseract**: Para reconocimiento óptico de caracteres (OCR)
- **numpy**: Para operaciones matemáticas en matrices de imágenes
- **requests**: Para comunicación con APIs de traducción
- **tkinter**: Para la interfaz gráfica (incluido con Python)

## Sistema OCR Mejorado

El sistema de OCR ha sido significativamente mejorado con las siguientes características:

### Múltiples Algoritmos de Preprocesamiento

1. **Preprocesamiento Estándar Mejorado**:
   - Reducción de ruido con `fastNlMeansDenoising`
   - Mejora de contraste con CLAHE (Contrast Limited Adaptive Histogram Equalization)
   - Binarización adaptativa
   - Operaciones morfológicas para limpieza

2. **Procesamiento para Fondos Complejos**:
   - Filtro bilateral para preservar bordes
   - Combinación de múltiples métodos de umbralización (Otsu + Adaptativo)
   - Operaciones morfológicas específicas

3. **Optimización para Texto Pequeño**:
   - Escalado inteligente de imagen (interpolación cúbica)
   - Filtros de enfoque (sharpening)
   - Conexión de caracteres fragmentados

4. **Detección de Texto Invertido**:
   - Detección automática de texto blanco sobre fondo oscuro
   - Inversión inteligente de imagen
   - Mejora de contraste específica

### Configuraciones Tesseract Optimizadas

- Configuraciones específicas según el tipo de contenido detectado
- Whitelist de caracteres optimizada para español e inglés
- Diferentes modos PSM (Page Segmentation Mode) según el contexto

### Post-procesamiento Inteligente

- Corrección de caracteres comúnmente mal reconocidos
- Eliminación de caracteres de control problemáticos
- Limpieza contextual de espacios y líneas vacías
- Reemplazos contextuales (ej: '0' → 'O' solo entre letras)

### Selección Automática del Mejor Resultado

El sistema prueba múltiples técnicas y selecciona automáticamente el resultado con mayor cantidad de texto detectado, mejorando significativamente la precisión de la detección.

## Controles de Rotación de Página

- **Rotar Izquierda (↶)**: Rota la página actual 90° en sentido antihorario
- **Rotar Derecha (↷)**: Rota la página actual 90° en sentido horario  
- **Reset Rotación (↺)**: Restaura la orientación original de la página actual

### Características de Rotación Mejorada:
- **Rotación independiente**: Cada página mantiene su propia rotación
- **Preservación de selecciones**: Las áreas seleccionadas no se pierden al rotar
- **OCR con rotación**: La extracción de texto respeta la rotación específica de cada página
- **Guardado en configuraciones**: Las rotaciones se guardan y cargan con las configuraciones

## Configuraciones Avanzadas

### Elementos Guardados en Configuraciones:
- **Áreas seleccionadas**: Coordenadas y contenido de cada área
- **Textos detectados y traducidos**: Resultados de OCR y traducción
- **Rotaciones por página**: Estado de rotación independiente de cada página
- **Configuración de estilo**: Colores de fondo, texto, borde y tamaño de fuente
- **Preferencias**: Configuraciones de auto-apertura y otros ajustes

### Gestión de Configuraciones:
- **Guardar**: Exportar configuración actual con nombre personalizado
- **Cargar**: Importar configuración guardada
- **Exportar/Importar**: Compartir configuraciones entre proyectos
- **Vista previa**: Información detallada de cada configuración

## Formato de Coordenadas

Las coordenadas se manejan en el sistema de puntos PDF (1/72 pulgadas):
- `(x1, y1)`: Esquina superior izquierda
- `(x2, y2)`: Esquina inferior derecha
- Origen `(0, 0)` en la esquina superior izquierda de la página

## Notas Técnicas

- El zoom afecta solo la visualización, las coordenadas se mantienen en el sistema PDF
- Las selecciones se almacenan por página
- Los rectángulos rojos indican las áreas seleccionadas
- Mínimo tamaño de selección: 10x10 píxeles en pantalla

## Solución de Problemas

1. **Error al cargar PDF**: Verifica que el archivo no esté corrupto o protegido
2. **Dependencias faltantes**: Ejecuta `pip install -r requirements.txt`
3. **Problemas de zoom**: Reinicia la aplicación si el zoom se comporta incorrectamente
4. **Selecciones no aparecen**: Asegúrate de arrastrar un área suficientemente grande

## Licencia

Este proyecto es de uso libre para fines educativos y de desarrollo.