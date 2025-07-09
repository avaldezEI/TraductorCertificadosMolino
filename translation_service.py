"""
Módulo de servicio de traducción para PDFTools
Maneja la comunicación con APIs de traducción y procesamiento de texto
"""

import requests
import threading
import re


class TranslationService:
    """Clase para manejar servicios de traducción"""
    
    def __init__(self, api_key=""):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
    
    def set_api_key(self, api_key):
        """Establecer API key"""
        self.api_key = api_key
    
    def update_api_key(self, api_key):
        """Actualizar API key"""
        self.api_key = api_key
    
    def create_translation_prompt(self, texts_to_translate):
        """Crear el prompt para la traducción"""
        prompt_parts = []
        prompt_parts.append("Traduce los siguientes textos del inglés al español. Mantén el formato 'Área X:' para cada sección:")
        prompt_parts.append("")
        
        for area_index, text in texts_to_translate.items():
            # Reemplazar saltos de línea con |||
            text = text.replace("\n", "|||")
            prompt_parts.append(f"Área {area_index + 1}: {text}")
        
        prompt_parts.append("")
        prompt_parts.append("Instrucciones:")
        prompt_parts.append("- Traduce cada texto preservando el número de área")
        prompt_parts.append("- Mantén el formato técnico si es aplicable")
        prompt_parts.append("- Si hay términos técnicos, úsalos apropiadamente en español")
        prompt_parts.append("- Responde SOLO con las traducciones, manteniendo el formato 'Área X: [traducción]'")
        
        return "\n".join(prompt_parts)
    
    def translate_texts_async(self, texts_to_translate, callback_success, callback_error, progress_callback=None):
        """Traducir textos de forma asíncrona"""
        if not self.api_key:
            callback_error("No se ha configurado la API Key de DeepSeek")
            return
        
        prompt_content = self.create_translation_prompt(texts_to_translate)
        
        # Iniciar traducción en hilo separado
        translation_thread = threading.Thread(
            target=self._translation_worker,
            args=(prompt_content, texts_to_translate, callback_success, callback_error, progress_callback)
        )
        translation_thread.daemon = True
        translation_thread.start()
    
    def _translation_worker(self, prompt_content, texts_to_translate, callback_success, callback_error, progress_callback):
        """Worker que ejecuta la traducción en un hilo separado"""
        try:
            if progress_callback:
                progress_callback("Enviando solicitud a DeepSeek...")
            
            # Preparar la solicitud
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt_content
                    }
                ],
                "stream": False,
                "temperature": 0.3,
                "max_tokens": 2000
            }
            
            if progress_callback:
                progress_callback("Esperando respuesta de DeepSeek...")
            
            # Realizar la solicitud
            response = requests.post(self.base_url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            translated_response = result['choices'][0]['message']['content'].strip()
            
            # Parsear las traducciones
            translations = self._parse_translation_response(translated_response, texts_to_translate)
            
            # Llamar callback de éxito
            callback_success(translations)
            
        except Exception as e:
            error_msg = f"Error en traducción: {str(e)}"
            callback_error(error_msg)
    
    def _parse_translation_response(self, response_text, original_texts):
        """Parsear la respuesta de traducción"""
        translations = {}
        lines = response_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if 'Área' in line and ':' in line:
                try:
                    # Extraer número de área y texto traducido
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        area_part = parts[0].strip()
                        translation = parts[1].strip()
                        
                        # Extraer número de área
                        area_match = re.search(r'Área\s+(\d+)', area_part)
                        if area_match:
                            area_number = int(area_match.group(1)) - 1  # Convertir a índice base 0
                            
                            # Restaurar saltos de línea
                            translation = translation.replace('|||', '\n')
                            
                            if area_number in original_texts:
                                translations[area_number] = translation
                                
                except (ValueError, IndexError):
                    continue
        
        return translations
    
    def get_translation_summary(self, detected_texts, translated_texts):
        """Generar resumen de textos detectados y traducidos"""
        content = "=== TEXTOS DETECTADOS ===\n\n"
        
        for i in sorted(detected_texts.keys()):
            content += f"Área {i + 1}:\n"
            
            # Mostrar texto original con formato preservado
            original_text = detected_texts[i]
            if '\n' in original_text:
                # Texto multilínea - mostrar cada línea con indentación
                lines = original_text.split('\n')
                for line in lines:
                    if line.strip():  # Solo líneas con contenido
                        content += f"  {line}\n"
                    else:
                        content += "\n"  # Línea vacía
            else:
                # Texto de una línea
                content += f"  {original_text}\n"
            
            if i in translated_texts:
                content += f"Traducción:\n"
                translated_text = translated_texts[i]
                if '\n' in translated_text:
                    # Traducción multilínea
                    lines = translated_text.split('\n')
                    for line in lines:
                        if line.strip():
                            content += f"  {line}\n"
                        else:
                            content += "\n"
                else:
                    # Traducción de una línea
                    content += f"  {translated_text}\n"
            
            content += "-" * 50 + "\n\n"
        
        return content
