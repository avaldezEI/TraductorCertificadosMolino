"""
Módulo de procesamiento OCR para PDFTools
Contiene todas las funciones relacionadas con la detección y extracción de texto
"""

import cv2
import numpy as np
import pytesseract
import fitz
import io
import re
from PIL import Image, ImageEnhance, ImageFilter
from scipy import ndimage
import threading
from concurrent.futures import ThreadPoolExecutor


class OCRProcessor:
    """Clase para manejar todo el procesamiento OCR"""
    
    def __init__(self):
        self.results_cache = {}
        # Configuraciones optimizadas para documentos escaneados
        self.scan_configs = {
            'dpi_threshold': 150,  # DPI mínimo para considerar buena calidad
            'min_text_height': 8,  # Altura mínima de texto en píxeles
            'noise_reduction_strength': 8,  # Fuerza de reducción de ruido
            'contrast_enhancement': 1.5,  # Factor de mejora de contraste
            'sharpening_strength': 1.2  # Fuerza de enfoque
        }
        
        # Pool de threads para procesamiento paralelo
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
    
    def enhanced_ocr_detection(self, area, pdf_document, page_rotations=None):
        """Detección de texto mejorada con múltiples técnicas de preprocesamiento optimizadas para escaneos"""
        try:
            print(f"=== DEBUG OCR DETECTION ===")
            print(f"Area recibida: {area}")
            print(f"PDF Document: {pdf_document}")
            print(f"Página rotaciones: {page_rotations}")
            
            # Validar entrada
            if not pdf_document:
                raise ValueError("pdf_document es None o inválido")
            
            if not area or 'page' not in area or 'coords' not in area:
                raise ValueError(f"Area inválida: {area}")
            
            page_num = area['page']
            print(f"Intentando acceder a página: {page_num}")
            print(f"Número total de páginas en documento: {len(pdf_document)}")
            
            if page_num >= len(pdf_document) or page_num < 0:
                raise ValueError(f"Número de página inválido: {page_num}, documento tiene {len(pdf_document)} páginas")
            
            # Obtener página
            page = pdf_document[page_num]
            print(f"Página obtenida exitosamente: {page}")
            
            # Obtener rotación específica de esta página para la extracción
            page_rotation = 0
            if page_rotations:
                page_rotation = page_rotations.get(page_num, 0)
            print(f"Rotación de página: {page_rotation}")
            
            # Renderizar área específica con resolución adaptativa
            coords = area['coords']
            print(f"Coordenadas del área: {coords}")
            
            if len(coords) != 4:
                raise ValueError(f"Coordenadas inválidas, se esperan 4 valores: {coords}")
            
            x1, y1, x2, y2 = coords
            print(f"Coordenadas procesadas: x1={x1}, y1={y1}, x2={x2}, y2={y2}")
            
            # Validar coordenadas
            if x1 >= x2 or y1 >= y2:
                raise ValueError(f"Coordenadas inválidas: x1={x1}, y1={y1}, x2={x2}, y2={y2}")
            
            rect = fitz.Rect(x1, y1, x2, y2)
            print(f"Rectángulo creado: {rect}")
            
            rect = fitz.Rect(x1, y1, x2, y2)
            print(f"Rectángulo creado: {rect}")
            
            # Calcular resolución óptima basada en el tamaño del área
            area_width = x2 - x1
            area_height = y2 - y1
            print(f"Dimensiones del área: {area_width} x {area_height}")
            
            # Usar resolución adaptativa para documentos escaneados
            if area_width < 100 or area_height < 30:
                # Área pequeña: usar alta resolución
                zoom_factor = 4.0
            elif area_width < 200 or area_height < 50:
                # Área mediana: resolución moderada-alta
                zoom_factor = 3.0
            else:
                # Área grande: resolución estándar optimizada
                zoom_factor = 2.5
            
            print(f"Factor de zoom calculado: {zoom_factor}")
            
            mat = fitz.Matrix(zoom_factor, zoom_factor)
            print(f"Matriz inicial creada: {mat}")
            
            # Aplicar rotación solo durante la extracción si es necesaria
            if page_rotation != 0:
                print(f"Aplicando rotación de {page_rotation} grados")
                mat = mat * fitz.Matrix(page_rotation)
                print(f"Matriz con rotación: {mat}")
            
            print("Renderizando pixmap...")
            pix = page.get_pixmap(matrix=mat, clip=rect)
            print(f"Pixmap creado: {pix.width}x{pix.height}")
            
            # Convertir a imagen con mejor calidad
            print("Convirtiendo a imagen PIL...")
            img_data = pix.tobytes("ppm")
            print(f"Datos de imagen obtenidos: {len(img_data)} bytes")
            
            img_pil = Image.open(io.BytesIO(img_data))
            print(f"Imagen PIL creada: {img_pil.size}, modo: {img_pil.mode}")
            
            # Detectar y corregir problemas comunes en escaneos
            print("Detectando y corrigiendo problemas de escaneo...")
            img_pil = self._detect_and_correct_scan_issues(img_pil)
            print(f"Imagen corregida: {img_pil.size}")
            
            print("Convirtiendo a OpenCV...")
            img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
            
            # Verificar si la imagen es muy pequeña
            height, width = img_cv.shape[:2]
            
            print(f"Tamaño de la imagen OpenCV: {width}x{height}")
            
            if width < 10 or height < 10:
                raise ValueError(f"Imagen demasiado pequeña para procesamiento OCR: {width}x{height}")
            
            # Optimización: detección temprana de calidad de imagen
            print("Evaluando calidad de imagen...")
            image_quality = self._assess_image_quality(img_cv)
            print(f"Calidad de imagen estimada: {image_quality}")
            
            # Seleccionar técnicas de procesamiento basadas en la calidad
            print("Seleccionando métodos de procesamiento...")
            processing_methods = self._select_processing_methods(img_cv, image_quality)
            print(f"Métodos seleccionados: {list(processing_methods.keys())}")
            
            # Aplicar múltiples técnicas de preprocesamiento con procesamiento paralelo
            results = []
            
            # Procesar métodos en paralelo para mejor rendimiento
            future_results = {}
            
            print("Iniciando procesamiento paralelo...")
            for method_name, method_func in processing_methods.items():
                print(f"Enviando método {method_name} al pool de threads...")
                future = self.thread_pool.submit(self._process_method, method_func, img_cv, method_name)
                future_results[method_name] = future
            
            # Recopilar resultados
            print("Recopilando resultados...")
            for method_name, future in future_results.items():
                try:
                    print(f"Esperando resultado de {method_name}...")
                    text, confidence = future.result(timeout=30)  # Timeout para evitar bloqueos
                    print(f"Método {method_name}: texto='{text[:100]}...', confianza={confidence}")
                    if text.strip():
                        results.append((method_name, text, len(text), confidence))
                except Exception as e:
                    print(f"Error en método {method_name}: {e}")
                    import traceback
                    traceback.print_exc()
            
            print(f"Resultados totales obtenidos: {len(results)}")
            
            # Seleccionar el mejor resultado considerando longitud y confianza
            if results:
                # Ordenar por una puntuación combinada de longitud y confianza
                for i, (method, text, length, conf) in enumerate(results):
                    score = (length * 0.7) + (conf * 0.3)
                    print(f"Resultado {i+1}: {method}, longitud={length}, confianza={conf}, score={score}")
                
                best_result = max(results, key=lambda x: (x[2] * 0.7) + (x[3] * 0.3))
                print(f"Mejor resultado seleccionado: {best_result[0]} con score={(best_result[2] * 0.7) + (best_result[3] * 0.3)}")
                print(f"Texto final: '{best_result[1]}'")
                return best_result[1]
            else:
                print("No se obtuvieron resultados válidos")
                return ""
            
        except Exception as e:
            print(f"=== ERROR EN enhanced_ocr_detection ===")
            print(f"Tipo de error: {type(e).__name__}")
            print(f"Mensaje de error: {str(e)}")
            print(f"Argumentos del error: {e.args}")
            
            # Imprimir traceback completo
            import traceback
            print("Traceback completo:")
            traceback.print_exc()
            
            # Información adicional de debug
            try:
                print(f"PDF Document válido: {pdf_document is not None}")
                if pdf_document:
                    print(f"Número de páginas: {len(pdf_document)}")
                print(f"Área recibida: {area}")
                print(f"Rotaciones de página: {page_rotations}")
            except:
                print("Error al obtener información adicional de debug")
            
            return ""
    
    def _detect_and_correct_scan_issues(self, img_pil):
        """Detectar y corregir problemas comunes en documentos escaneados"""
        # Detectar y corregir inclinación
        img_array = np.array(img_pil.convert('L'))
        corrected_angle = self._detect_skew(img_array)
        
        if abs(corrected_angle) > 0.5:  # Solo corregir si la inclinación es significativa
            img_pil = img_pil.rotate(corrected_angle, expand=True, fillcolor='white')
        
        # Mejorar brillo y contraste para escaneos
        enhancer = ImageEnhance.Contrast(img_pil)
        img_pil = enhancer.enhance(self.scan_configs['contrast_enhancement'])
        
        # Reducir ruido de escaneo
        img_pil = img_pil.filter(ImageFilter.MedianFilter(size=3))
        
        return img_pil
    
    def _detect_skew(self, img):
        """Detectar inclinación en documentos escaneados usando transformada de Hough"""
        edges = cv2.Canny(img, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
        
        if lines is not None:
            angles = []
            for line in lines:
                rho, theta = line[0]
                angle = np.degrees(theta) - 90
                if -45 < angle < 45:
                    angles.append(angle)
            
            if angles:
                return np.median(angles)
        
        return 0
    
    def _assess_image_quality(self, img):
        """Evaluar la calidad de la imagen para seleccionar el mejor procesamiento"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Calcular métricas de calidad
        # 1. Varianza de Laplaciano (nitidez)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # 2. Contraste (desviación estándar)
        contrast = gray.std()
        
        # 3. Brillo promedio
        brightness = gray.mean()
        
        # 4. Detección de ruido
        noise_level = self._estimate_noise_level(gray)
        
        # Puntaje de calidad combinado
        quality_score = min(100, (laplacian_var / 500) * 30 + (contrast / 50) * 25 + 
                          (1 - noise_level) * 25 + (1 - abs(brightness - 127) / 127) * 20)
        
        return quality_score
    
    def _estimate_noise_level(self, gray_img):
        """Estimar el nivel de ruido en la imagen"""
        # Usar filtro gaussiano para estimar ruido
        blurred = cv2.GaussianBlur(gray_img, (5, 5), 0)
        noise = cv2.absdiff(gray_img, blurred)
        return np.mean(noise) / 255.0
    
    def _select_processing_methods(self, img, quality_score):
        """Seleccionar métodos de procesamiento basados en la calidad de la imagen"""
        methods = {}
        
        if quality_score < 30:
            # Imagen de baja calidad: usar métodos agresivos
            methods['enhanced_standard'] = self.preprocess_standard_enhanced
            methods['heavy_denoising'] = self.preprocess_complex_background
            methods['super_resolution'] = self.preprocess_small_text
            methods['inverted_check'] = self.preprocess_inverted_text
        elif quality_score < 60:
            # Imagen de calidad media: usar métodos moderados
            methods['standard'] = self.preprocess_standard_enhanced
            methods['adaptive'] = self.preprocess_complex_background
            methods['small_text'] = self.preprocess_small_text
        else:
            # Imagen de buena calidad: usar métodos estándar
            methods['standard'] = self.preprocess_standard_enhanced
            methods['adaptive'] = self.preprocess_complex_background
        
        return methods
    
    def _process_method(self, method_func, img, method_name):
        """Procesar un método específico y devolver texto con confianza"""
        try:
            print(f"=== PROCESANDO MÉTODO: {method_name} ===")
            print(f"Imagen de entrada: {img.shape if hasattr(img, 'shape') else 'Sin información de forma'}")
            
            print(f"Iniciando preprocesamiento con {method_name}...")
            processed_img = method_func(img)
            print(f"Preprocesamiento completado. Imagen procesada: {processed_img.shape if hasattr(processed_img, 'shape') else 'Sin información de forma'}")
            
            print(f"Extrayendo texto con configuración {method_name}...")
            text = self.extract_text_with_config(processed_img, method_name)
            print(f"Texto extraído ({len(text)} caracteres): '{text[:100]}{'...' if len(text) > 100 else ''}'")
            
            # Calcular confianza basada en características del texto
            print(f"Calculando confianza para {method_name}...")
            confidence = self._calculate_text_confidence(text, processed_img)
            print(f"Confianza calculada: {confidence}")
            
            return text, confidence
        except Exception as e:
            print(f"=== ERROR EN _process_method ({method_name}) ===")
            print(f"Tipo de error: {type(e).__name__}")
            print(f"Mensaje: {str(e)}")
            
            import traceback
            print("Traceback:")
            traceback.print_exc()
            
            return "", 0
    
    def _calculate_text_confidence(self, text, processed_img):
        """Calcular confianza del texto extraído"""
        if not text.strip():
            return 0
        
        # Factores de confianza
        confidence = 0
        
        # 1. Longitud del texto (textos más largos tienden a ser más confiables)
        length_factor = min(1.0, len(text) / 100)
        confidence += length_factor * 30
        
        # 2. Proporción de caracteres alfanuméricos
        alphanum_ratio = sum(c.isalnum() for c in text) / max(len(text), 1)
        confidence += alphanum_ratio * 25
        
        # 3. Presencia de palabras reconocibles (español/inglés)
        words = text.split()
        word_factor = min(1.0, len([w for w in words if len(w) > 2]) / max(len(words), 1))
        confidence += word_factor * 25
        
        # 4. Ausencia de caracteres extraños
        strange_chars = sum(1 for c in text if ord(c) > 127 and c not in 'áéíóúñüÁÉÍÓÚÑÜ¿¡')
        strange_factor = max(0, 1 - strange_chars / max(len(text), 1))
        confidence += strange_factor * 20
        
        return min(100, confidence)
    
    def preprocess_standard_enhanced(self, img):
        """Preprocesamiento estándar mejorado optimizado para escaneos"""
        # Convertir a escala de grises
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Reducir ruido específico de escaneos con parámetros optimizados
        denoised = cv2.fastNlMeansDenoising(gray, 
                                          h=self.scan_configs['noise_reduction_strength'], 
                                          templateWindowSize=7, 
                                          searchWindowSize=21)
        
        # Mejorar contraste usando CLAHE adaptativo
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # Aplicar filtro de enfoque específico para documentos escaneados
        kernel_sharpening = np.array([[-1,-1,-1], 
                                     [-1, 9,-1],
                                     [-1,-1,-1]]) * self.scan_configs['sharpening_strength']
        sharpened = cv2.filter2D(enhanced, -1, kernel_sharpening)
        
        # Aplicar filtro gaussiano suave
        blurred = cv2.GaussianBlur(sharpened, (1, 1), 0)
        
        # Binarización adaptativa mejorada
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                     cv2.THRESH_BINARY, 11, 2)
        
        # Operaciones morfológicas optimizadas para texto escaneado
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        # Reducir artefactos de borde
        cleaned = cv2.medianBlur(cleaned, 3)
        
        return cleaned
    
    def preprocess_complex_background(self, img):
        """Preprocesamiento para texto en fondos complejos optimizado para escaneos"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Aplicar filtro bilateral más fuerte para escaneos ruidosos
        bilateral = cv2.bilateralFilter(gray, 11, 80, 80)
        
        # Usar múltiples umbrales optimizados para documentos escaneados
        # Otsu threshold con preprocesamiento
        _, thresh1 = cv2.threshold(bilateral, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Adaptive threshold con parámetros optimizados
        thresh2 = cv2.adaptiveThreshold(bilateral, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                       cv2.THRESH_BINARY, 19, 8)
        
        # Método adicional: Niblack threshold adaptado
        thresh3 = self._niblack_threshold(bilateral, window_size=15, k=0.2)
        
        # Combinar los tres métodos con ponderación
        combined = cv2.bitwise_and(thresh1, thresh2)
        combined = cv2.bitwise_or(combined, thresh3)
        
        # Operaciones morfológicas mejoradas
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
        cleaned = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)
        
        # Eliminar componentes muy pequeños (ruido)
        cleaned = self._remove_small_components(cleaned, min_size=10)
        
        return cleaned
    
    def _niblack_threshold(self, img, window_size=15, k=0.2):
        """Implementar umbralización de Niblack para documentos escaneados"""
        rows, cols = img.shape
        result = np.zeros_like(img)
        
        # Calcular media y desviación estándar locales
        mean = cv2.boxFilter(img.astype(np.float32), -1, (window_size, window_size))
        sqr_mean = cv2.boxFilter((img.astype(np.float32))**2, -1, (window_size, window_size))
        std = np.sqrt(sqr_mean - mean**2)
        
        # Aplicar fórmula de Niblack
        threshold = mean + k * std
        result = np.where(img > threshold, 255, 0).astype(np.uint8)
        
        return result
    
    def _remove_small_components(self, img, min_size=10):
        """Eliminar componentes pequeños (ruido) de la imagen binarizada"""
        # Encontrar componentes conectados
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(img, connectivity=8)
        
        # Crear máscara para componentes grandes
        mask = np.zeros_like(img)
        for i in range(1, num_labels):
            if stats[i, cv2.CC_STAT_AREA] >= min_size:
                mask[labels == i] = 255
        
        return mask
    
    def preprocess_small_text(self, img):
        """Preprocesamiento específico para texto pequeño optimizado para escaneos"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Redimensionar con interpolación mejorada para texto pequeño
        height, width = gray.shape
        
        # Calcular factor de escala adaptativo
        target_height = max(100, height * 2)
        scale_factor = target_height / height
        
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        
        # Usar interpolación Lanczos para mejor calidad con texto pequeño
        resized = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
        
        # Aplicar filtro de enfoque adaptativo
        kernel_sharpening = np.array([[-1,-1,-1], 
                                     [-1, 12,-1],
                                     [-1,-1,-1]]) / 4
        sharpened = cv2.filter2D(resized, -1, kernel_sharpening)
        
        # Reducir ruido manteniendo bordes
        denoised = cv2.bilateralFilter(sharpened, 9, 75, 75)
        
        # Binarización con múltiples métodos
        _, thresh1 = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Método adicional para texto muy pequeño
        thresh2 = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                       cv2.THRESH_BINARY, 7, 3)
        
        # Combinar métodos
        combined = cv2.bitwise_and(thresh1, thresh2)
        
        # Operación de cierre para conectar caracteres fragmentados
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
        
        # Eliminar ruido residual
        closed = cv2.medianBlur(closed, 3)
        
        return closed
    
    def preprocess_inverted_text(self, img):
        """Preprocesamiento para texto invertido optimizado para escaneos"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Detectar automáticamente si es texto invertido usando histograma
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        
        # Calcular picos en histograma
        dark_pixels = np.sum(hist[:128])
        light_pixels = np.sum(hist[128:])
        
        # Si hay más píxeles oscuros, probablemente es texto invertido
        if dark_pixels > light_pixels * 1.2:
            # Invertir la imagen
            inverted = cv2.bitwise_not(gray)
        else:
            inverted = gray
        
        # Aplicar CLAHE más agresivo para texto invertido
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8,8))
        enhanced = clahe.apply(inverted)
        
        # Reducir ruido específico de escaneos invertidos
        denoised = cv2.fastNlMeansDenoising(enhanced, h=10, templateWindowSize=7, searchWindowSize=21)
        
        # Aplicar filtro de enfoque
        kernel_sharpening = np.array([[0,-1,0], [-1,5,-1], [0,-1,0]])
        sharpened = cv2.filter2D(denoised, -1, kernel_sharpening)
        
        # Binarización optimizada
        _, thresh = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Operaciones morfológicas para limpiar
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    
    def extract_text_with_config(self, processed_img, method_type):
        """Extraer texto con configuración específica de Tesseract según el método"""
        try:
            print(f"=== EXTRACCIÓN DE TEXTO: {method_type} ===")
            print(f"Imagen de entrada: {processed_img.shape if hasattr(processed_img, 'shape') else 'Sin información'}")
            print(f"Tipo de imagen: {type(processed_img)}")
            
            # Configuraciones optimizadas para documentos escaneados (sin caracteres problemáticos)
            configs = {
                'standard': '--oem 3 --psm 6',
                'enhanced_standard': '--oem 3 --psm 6',
                'complex': '--oem 3 --psm 8',
                'heavy_denoising': '--oem 3 --psm 6',
                'adaptive': '--oem 3 --psm 8',
                'small': '--oem 3 --psm 8',
                'small_text': '--oem 3 --psm 8',
                'super_resolution': '--oem 3 --psm 7',
                'inverted': '--oem 3 --psm 7',
                'inverted_check': '--oem 3 --psm 7'
            }
            
            config = configs.get(method_type, '--oem 3 --psm 6')
            print(f"Configuración Tesseract: {config}")
            
            # Validar que pytesseract esté disponible
            print("Verificando disponibilidad de Tesseract...")
            try:
                version = pytesseract.get_tesseract_version()
                print(f"Tesseract disponible, versión: {version}")
            except pytesseract.TesseractNotFoundError:
                error_msg = "Tesseract no está instalado o no se encuentra en el PATH del sistema"
                print(f"ERROR: {error_msg}")
                print("Por favor instala Tesseract OCR desde: https://github.com/UB-Mannheim/tesseract/wiki")
                raise Exception(error_msg)
            except Exception as tess_error:
                print(f"ERROR verificando Tesseract: {tess_error}")
                # Continuar de todas formas, puede que funcione
                pass
            
            # Extraer texto con manejo de errores mejorado
            print("Ejecutando OCR con pytesseract...")
            
            # Usar el método de fallbacks más robusto
            text = self._try_ocr_with_fallbacks(processed_img, method_type)
            
            print(f"Texto extraído en bruto ({len(text)} caracteres): '{text[:200]}{'...' if len(text) > 200 else ''}'")
            
            # Post-procesamiento del texto optimizado para escaneos
            print("Post-procesando texto...")
            cleaned_text = self.post_process_text(text)
            print(f"Texto limpio ({len(cleaned_text)} caracteres): '{cleaned_text[:200]}{'...' if len(cleaned_text) > 200 else ''}'")
            
            return cleaned_text
            
        except Exception as e:
            print(f"=== ERROR EN extract_text_with_config ===")
            print(f"Método: {method_type}")
            print(f"Tipo de error: {type(e).__name__}")
            print(f"Mensaje: {str(e)}")
            
            import traceback
            print("Traceback:")
            traceback.print_exc()
            
            return ""
    
    def post_process_text(self, text):
        """Post-procesamiento del texto extraído optimizado para documentos escaneados"""
        if not text:
            return ""
        
        # Limpiar líneas vacías y espacios extra
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:  # Solo agregar líneas no vacías
                # Eliminar espacios múltiples
                line = re.sub(r'\s+', ' ', line)
                
                # Correcciones específicas para errores comunes de OCR en escaneos
                # Reemplazos contextuales más inteligentes
                line = re.sub(r'(?<=[A-Za-z])0(?=[A-Za-z])', 'O', line)
                line = re.sub(r'(?<=[A-Za-z])1(?=[A-ZaZ])', 'l', line)
                line = re.sub(r'(?<=[A-Za-z])5(?=[A-Za-z])', 'S', line)
                line = re.sub(r'(?<=[A-Za-z])8(?=[A-Za-z])', 'B', line)
                
                # Correcciones para caracteres especiales mal reconocidos
                line = line.replace('|', 'I')
                line = line.replace('¡', 'i')
                line = line.replace('¦', 'I')
                
                # Eliminar caracteres de ruido comunes en escaneos
                line = re.sub(r'[«»""''‚„‹›]', '"', line)
                line = re.sub(r'[–—]', '-', line)
                
                cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines)
        
        # Eliminar caracteres de control y caracteres especiales problemáticos
        result = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]', '', result)
        
        # Eliminar líneas que son principalmente ruido
        lines = result.split('\n')
        filtered_lines = []
        
        for line in lines:
            # Filtrar líneas que son principalmente caracteres especiales o muy cortas
            if len(line) > 1 and sum(c.isalnum() for c in line) / len(line) > 0.3:
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines).strip()
    
    def _get_safe_tesseract_config(self, method_type):
        """Crear configuraciones de Tesseract sin caracteres problemáticos"""
        base_configs = {
            'standard': '--oem 3 --psm 6',
            'enhanced_standard': '--oem 3 --psm 6',
            'complex': '--oem 3 --psm 8',
            'heavy_denoising': '--oem 3 --psm 6',
            'adaptive': '--oem 3 --psm 8',
            'small': '--oem 3 --psm 8',
            'small_text': '--oem 3 --psm 8',
            'super_resolution': '--oem 3 --psm 7',
            'inverted': '--oem 3 --psm 7',
            'inverted_check': '--oem 3 --psm 7'
        }
        
        return base_configs.get(method_type, '--oem 3 --psm 6')
    
    def _try_ocr_with_fallbacks(self, processed_img, method_type):
        """Intentar OCR con múltiples configuraciones como fallback"""
        
        # Lista de configuraciones a probar en orden de preferencia
        fallback_configs = [
            ('configuración específica', self._get_safe_tesseract_config(method_type)),
            ('configuración estándar', '--oem 3 --psm 6'),
            ('configuración automática', '--oem 3 --psm 3'),
            ('configuración básica', '')
        ]
        
        # Lista de idiomas a probar
        language_options = ['spa+eng', 'spa', 'eng', None]
        
        for lang in language_options:
            for config_name, config in fallback_configs:
                try:
                    print(f"Intentando OCR con {config_name} e idioma: {lang or 'auto'}")
                    
                    if lang:
                        text = pytesseract.image_to_string(processed_img, lang=lang, config=config)
                    else:
                        text = pytesseract.image_to_string(processed_img, config=config)
                    
                    if text.strip():  # Si obtenemos algún texto
                        print(f"OCR exitoso con {config_name} e idioma {lang or 'auto'}")
                        return text
                    else:
                        print(f"OCR sin texto con {config_name} e idioma {lang or 'auto'}")
                        
                except Exception as e:
                    print(f"Error con {config_name} e idioma {lang or 'auto'}: {e}")
                    continue
        
        print("Todos los métodos de OCR fallaron")
        return ""
    
    def __del__(self):
        """Cleanup del pool de threads"""
        if hasattr(self, 'thread_pool'):
            self.thread_pool.shutdown(wait=True)