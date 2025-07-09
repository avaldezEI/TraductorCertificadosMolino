"""
Módulo de gestión de configuraciones para PDFTools
Maneja el guardado, carga, exportación e importación de configuraciones
"""

import json
import os
from datetime import datetime
from tkinter import messagebox


class ConfigManager:
    """Clase para manejar configuraciones del proyecto"""
    
    def __init__(self):
        self.config_dir = "configuraciones"
        self.ensure_config_directory()
    
    def ensure_config_directory(self):
        """Crear directorio de configuraciones si no existe"""
        os.makedirs(self.config_dir, exist_ok=True)
    
    def save_configuration(self, config_name, pdf_document, selected_areas, detected_texts, 
                          translated_texts, page_rotations, style_config):
        """Guardar configuración actual"""
        if not config_name:
            return False, "Introduce un nombre para la configuración"
        
        if not selected_areas:
            return False, "No hay áreas seleccionadas para guardar"
        
        try:
            # Preparar datos de configuración
            config_data = {
                'name': config_name,
                'created_date': datetime.now().isoformat(),
                'pdf_file': getattr(pdf_document, 'name', 'unknown') if pdf_document else None,
                'total_pages': len(pdf_document) if pdf_document else 0,
                'page_rotations': page_rotations.copy(),  # Rotaciones independientes por página
                'style_config': style_config,  # Configuración de estilo
                'areas': []
            }
            
            # Agregar áreas con textos detectados y traducidos
            for i, area in enumerate(selected_areas):
                area_data = {
                    'id': i,
                    'page': area['page'],
                    'coords': area['coords']
                }
                
                # Agregar font_size si existe en el área
                if 'font_size' in area:
                    area_data['font_size'] = area['font_size']
                
                # Agregar rotación si existe en el área
                if 'rotation' in area:
                    area_data['rotation'] = area['rotation']
                
                # Agregar texto detectado si existe
                if i in detected_texts:
                    area_data['detected_text'] = detected_texts[i]
                
                # Agregar texto traducido si existe
                if i in translated_texts:
                    area_data['translated_text'] = translated_texts[i]
                
                config_data['areas'].append(area_data)
            
            # Guardar archivo
            config_file = os.path.join(self.config_dir, f"{config_name}.json")
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            return True, f"Configuración '{config_name}' guardada correctamente"
            
        except Exception as e:
            return False, f"No se pudo guardar la configuración: {str(e)}"
    
    def load_configuration(self, config_name):
        """Cargar configuración por nombre"""
        try:
            config_file = os.path.join(self.config_dir, f"{config_name}.json")
            
            if not os.path.exists(config_file):
                return None, f"La configuración '{config_name}' no existe"
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            return config_data, "Configuración cargada correctamente"
            
        except Exception as e:
            return None, f"No se pudo cargar la configuración: {str(e)}"
    
    def get_saved_configurations(self):
        """Obtener lista de configuraciones guardadas"""
        try:
            if not os.path.exists(self.config_dir):
                return []
            
            configs = []
            for filename in os.listdir(self.config_dir):
                if filename.endswith('.json'):
                    config_name = filename[:-5]  # Remover .json
                    configs.append(config_name)
            return configs
        except Exception as e:
            print(f"Error al cargar configuraciones: {e}")
            return []
    
    def delete_configuration(self, config_name):
        """Eliminar configuración"""
        try:
            config_file = os.path.join(self.config_dir, f"{config_name}.json")
            if os.path.exists(config_file):
                os.remove(config_file)
                return True, f"Configuración '{config_name}' eliminada"
            else:
                return False, f"La configuración '{config_name}' no existe"
        except Exception as e:
            return False, f"No se pudo eliminar la configuración: {str(e)}"
    
    def export_configuration(self, config_name, export_path):
        """Exportar configuración a archivo"""
        try:
            config_file = os.path.join(self.config_dir, f"{config_name}.json")
            
            if not os.path.exists(config_file):
                return False, f"La configuración '{config_name}' no existe"
            
            # Copiar archivo
            with open(config_file, 'r', encoding='utf-8') as src:
                with open(export_path, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
            
            return True, f"Configuración exportada a: {export_path}"
            
        except Exception as e:
            return False, f"No se pudo exportar la configuración: {str(e)}"
    
    def import_configuration(self, import_path):
        """Importar configuración desde archivo"""
        try:
            # Leer y validar archivo
            with open(import_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Validar estructura básica
            if 'name' not in config_data or 'areas' not in config_data:
                return False, "El archivo no tiene el formato correcto"
            
            config_name = config_data['name']
            config_file = os.path.join(self.config_dir, f"{config_name}.json")
            
            # Verificar si ya existe
            if os.path.exists(config_file):
                return None, f"La configuración '{config_name}' ya existe. ¿Sobrescribir?"
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            return True, f"Configuración '{config_name}' importada correctamente"
            
        except Exception as e:
            return False, f"No se pudo importar la configuración: {str(e)}"
    
    def get_config_info(self, config_data):
        """Generar información detallada de una configuración"""
        info = f"Nombre: {config_data['name']}\n"
        info += f"Fecha: {config_data['created_date'][:10]}\n"
        info += f"PDF: {config_data.get('pdf_file', 'N/A')}\n"
        info += f"Páginas: {config_data['total_pages']}\n"
        info += f"Áreas: {len(config_data['areas'])}\n"
        
        # Mostrar información de rotaciones si existen
        if 'page_rotations' in config_data and config_data['page_rotations']:
            info += f"Páginas rotadas: {len(config_data['page_rotations'])}\n"
            for page, rotation in config_data['page_rotations'].items():
                info += f"  • Pág. {int(page)+1}: {rotation}°\n"
        
        # Mostrar información de estilo si existe
        if 'style_config' in config_data:
            style = config_data['style_config']
            info += f"Estilo personalizado: Sí\n"
            if 'block_font_size' in style:
                info += f"  • Tamaño fuente: {style['block_font_size']}\n"
        
        info += "\nÁreas:\n"
        for area in config_data['areas']:
            info += f"• Área {area['id']+1} (Pág. {area['page']+1})\n"
        
        return info

    def save_api_key(self, api_key):
        """Guardar API key en archivo .env"""
        try:
            env_file = ".env"
            
            # Leer archivo existente
            lines = []
            if os.path.exists(env_file):
                with open(env_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            
            # Buscar y actualizar la línea de API key
            found = False
            for i, line in enumerate(lines):
                if line.startswith('DEEPSEEK_API_KEY='):
                    lines[i] = f'DEEPSEEK_API_KEY={api_key}\n'
                    found = True
                    break
            
            # Si no se encontró, agregar al final
            if not found:
                lines.append(f'DEEPSEEK_API_KEY={api_key}\n')
            
            # Escribir archivo
            with open(env_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                
            return True, "API Key guardada correctamente"
            
        except Exception as e:
            return False, f"Error al guardar API Key: {str(e)}"

    # Métodos de compatibilidad con PDF viewer
    def load_saved_configurations(self):
        """Alias para get_saved_configurations - compatibilidad con PDF viewer"""
        return self.get_saved_configurations()

    def load_configuration_by_name(self, config_name):
        """Cargar configuración por nombre - compatibilidad con PDF viewer"""
        return self.load_configuration(config_name)

    def format_config_info(self, config_data):
        """Formatear información de configuración - compatibilidad con PDF viewer"""
        return self.get_config_info(config_data)
