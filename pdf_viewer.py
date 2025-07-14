import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font
import tkinter.font as tkFont
import fitz  # PyMuPDF
import cv2
import numpy as np
import pytesseract
import requests
import json
import os
import io
import re
import threading
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(): pass
from datetime import datetime
from PIL import Image, ImageTk

# Importar módulos especializados
from ocr_processor import OCRProcessor
from config_manager import ConfigManager
from translation_service import TranslationService
from ui_components import UIComponents

class PDFViewer:
    def __init__(self):
        load_dotenv()
        
        # Configuración por defecto
        self.block_bg = (1, 1, 1)  # Blanco
        self.block_text_color = (0, 0, 0)  # Negro
        self.block_border_color = (0.7, 0.7, 0.7)  # Gris
        self.block_font_size = 12
        self.auto_open_pdf = True  # Auto-abrir PDF después de guardar
        self.global_font_size = 12  # Tamaño de fuente global por defecto
        
        self.root = tk.Tk()
        self.root.title("PDF Viewer with OCR and Translation")
        self.root.geometry("1400x900")
        
        # Variables principales
        self.pdf_document = None
        self.current_page = 0
        self.zoom_factor = 1.0
        self.selected_areas = []
        self.start_x = None
        self.start_y = None
        self.current_rect = None
        self.detected_texts = {}  # {area_index: detected_text}
        self.translated_texts = {}  # {area_index: translated_text}
        self.page_rotations = {}  # Rotación independiente por página {page_number: rotation_degrees}
        
        # Variables para redimensionamiento
        self.resize_handles = []
        self.selected_area_index = None
        self.resize_handle = None
        self.edit_mode = False
        
        # Inicializar módulos especializados
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.ocr_processor = OCRProcessor()
        self.config_manager = ConfigManager()
        self.translation_service = TranslationService(self.api_key)
        self.ui_components = UIComponents()
        
        self.setup_ui()
        
    def setup_ui(self):
        """Configurar la interfaz de usuario usando el módulo UI"""
        # Crear frame principal con tres paneles
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Panel izquierdo para controles
        left_panel = ttk.Frame(main_frame, width=250)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_panel.pack_propagate(False)
        
        # Panel central para el PDF
        center_panel = ttk.Frame(main_frame)
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # Panel derecho para configuraciones
        right_panel = ttk.Frame(main_frame, width=300)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right_panel.pack_propagate(False)
        
        # Configurar paneles usando el módulo UI
        self.ui_components.setup_left_panel(left_panel, self)
        self.ui_components.setup_center_panel(center_panel, self)
        self.ui_components.setup_right_panel(right_panel, self)
    
    def load_pdf(self):
        """Cargar un archivo PDF"""
        file_path = filedialog.askopenfilename(
            title="Seleccionar PDF",
            filetypes=[("PDF files", "*.pdf")]
        )
        
        if file_path:
            try:
                self.pdf_document = fitz.open(file_path)
                self.current_page = 0
                self.selected_areas = []
                self.detected_texts = {}
                self.translated_texts = {}
                self.page_rotations = {}  # Limpiar rotaciones al cargar nuevo PDF
                self.update_page_display()
                self.update_selection_list()
                self.clear_resize_handles()
                messagebox.showinfo("Éxito", f"PDF cargado: {len(self.pdf_document)} páginas")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cargar el PDF: {str(e)}")
    
    def update_page_display(self):
        """Actualizar la visualización de la página actual"""
        if not self.pdf_document:
            return
        
        try:
            page = self.pdf_document[self.current_page]
            
            # Obtener rotación específica de esta página
            current_page_rotation = self.page_rotations.get(self.current_page, 0)
            
            # Renderizar página con zoom y rotación
            mat = fitz.Matrix(self.zoom_factor, self.zoom_factor)
            if current_page_rotation != 0:
                # Aplicar rotación si es necesaria
                mat = mat * fitz.Matrix(current_page_rotation)
            pix = page.get_pixmap(matrix=mat)
            
            # Convertir a imagen PIL
            img_data = pix.tobytes("ppm")
            img = Image.open(io.BytesIO(img_data))
            
            # Convertir a PhotoImage para tkinter
            self.photo = ImageTk.PhotoImage(img)
            
            # Limpiar canvas y mostrar imagen
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
            
            # Configurar región de scroll
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            
            # Actualizar coordenadas canvas antes de dibujar las áreas
            self.update_canvas_coords_for_areas()
            
            # Dibujar áreas seleccionadas para esta página
            self.draw_selected_areas()
            
            # Actualizar información de página
            self.page_var.set(f"{self.current_page + 1} / {len(self.pdf_document)}")
            self.zoom_var.set(f"{int(self.zoom_factor * 100)}%")
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo mostrar la página: {str(e)}")
    
    def draw_selected_areas(self):
        """Dibujar las áreas seleccionadas en la página actual"""
        for i, area in enumerate(self.selected_areas):
            if area['page'] == self.current_page:
                # Verificar si existen canvas_coords, si no, calcularlas
                if 'canvas_coords' not in area:
                    x1, y1, x2, y2 = area['coords']
                    # Aplicar zoom para obtener coordenadas canvas
                    canvas_x1 = x1 * self.zoom_factor
                    canvas_y1 = y1 * self.zoom_factor
                    canvas_x2 = x2 * self.zoom_factor
                    canvas_y2 = y2 * self.zoom_factor
                    area['canvas_coords'] = (canvas_x1, canvas_y1, canvas_x2, canvas_y2)
                
                x1, y1, x2, y2 = area['canvas_coords']
                
                # Determinar el color del rectángulo según el estado
                if i in self.translated_texts and self.show_translation_preview.get():
                    # Área traducida - mostrar en verde con fondo de traducción
                    outline_color = "green"
                    fill_color = self._rgb_to_hex(self.block_bg)
                    width = 2
                    
                    # Dibujar rectángulo con fondo de traducción
                    rect_id = self.canvas.create_rectangle(
                        x1, y1, x2, y2,
                        outline=outline_color, 
                        fill=fill_color,
                        width=width,
                        stipple=""  # Relleno sólido
                    )
                    
                    # Agregar texto traducido superpuesto
                    self.draw_translated_text(i, x1, y1, x2, y2)
                    
                elif i in self.detected_texts:
                    # Área con texto detectado pero no traducido - azul
                    outline_color = "blue" if i not in self.translated_texts else "green"
                    width = 2
                    
                    rect_id = self.canvas.create_rectangle(
                        x1, y1, x2, y2,
                        outline=outline_color, 
                        fill="",
                        width=width,
                        stipple="gray25"
                    )
                else:
                    # Área sin procesar - rojo
                    outline_color = "red"
                    width = 1
                    
                    rect_id = self.canvas.create_rectangle(
                        x1, y1, x2, y2,
                        outline=outline_color, 
                        fill="",
                        width=width,
                        stipple="gray25"
                    )
                
                # Guardar referencia del rectángulo
                area['rect_id'] = rect_id
                
                # Agregar número de área
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                
                # Ajustar color del número según el estado
                if i in self.translated_texts and self.show_translation_preview.get():
                    text_color = "white"
                    # Posicionar el número en la esquina superior izquierda para no interferir con el texto
                    number_x = x1 + 15
                    number_y = y1 + 15
                else:
                    text_color = outline_color
                    number_x = center_x
                    number_y = center_y
                
                self.canvas.create_text(
                    number_x, number_y,
                    text=str(i + 1),
                    fill=text_color,
                    font=("Arial", 12, "bold")
                )
    
    def on_canvas_click(self, event):
        """Manejar clic en el canvas"""
        if not self.pdf_document:
            return
        
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        # Si estamos en modo edición, verificar si se hizo clic en un handle
        if self.edit_mode and self.resize_handles:
            handle_direction = self.check_handle_click(canvas_x, canvas_y)
            if handle_direction:
                self.resize_handle = handle_direction
                return
        
        # Verificar si se hizo clic en un área existente (esto activa automáticamente el modo edición)
        area_clicked = self.check_area_click(canvas_x, canvas_y)
        if area_clicked:
            # Activar modo edición automáticamente
            if not self.edit_mode:
                self.toggle_edit_mode()
            return
        
        # Si no se hizo click en un área y estamos en modo edición, salir del modo edición
        if self.edit_mode:
            self.toggle_edit_mode()
        
        # Modo selección normal - iniciar nueva selección
        self.start_x = canvas_x
        self.start_y = canvas_y
        self.current_rect = None
    
    def on_canvas_drag(self, event):
        """Manejar arrastre en el canvas"""
        if not self.pdf_document:
            return
        
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        # Si estamos redimensionando
        if self.edit_mode and self.resize_handle:
            self.update_resize(event)
            return
        
        # Si estamos en modo edición pero no redimensionando, no hacer nada
        if self.edit_mode:
            return
        
        # Modo selección normal
        if self.start_x is not None and self.start_y is not None:
            if self.current_rect:
                self.canvas.delete(self.current_rect)
            
            self.current_rect = self.canvas.create_rectangle(
                self.start_x, self.start_y, canvas_x, canvas_y,
                outline="red", width=2, fill="", stipple="gray25"
            )
    
    def on_canvas_release(self, event):
        """Manejar liberación del botón en el canvas"""
        if not self.pdf_document:
            return
        
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        # Si estábamos redimensionando, terminar
        if self.edit_mode and self.resize_handle:
            self.resize_handle = None
            return
        
        # Si estamos en modo edición, no crear nuevas áreas
        if self.edit_mode:
            return
        
        # Completar selección de área
        if self.start_x is not None and self.start_y is not None:
            # Calcular coordenadas normalizadas
            x1 = min(self.start_x, canvas_x) / self.zoom_factor
            y1 = min(self.start_y, canvas_y) / self.zoom_factor
            x2 = max(self.start_x, canvas_x) / self.zoom_factor
            y2 = max(self.start_y, canvas_y) / self.zoom_factor
            
            # Verificar que el área tenga un tamaño mínimo
            if abs(x2 - x1) > 10 and abs(y2 - y1) > 5:
                # Guardar área seleccionada
                selection_data = {
                    'page': self.current_page,
                    'coords': (x1, y1, x2, y2),  # Coordenadas en PDF
                    'canvas_coords': (self.start_x, self.start_y, canvas_x, canvas_y),  # Coordenadas en canvas
                    'rect_id': None,
                    'font_size': self.global_font_size  # Usar tamaño de fuente global por defecto
                }
                
                self.selected_areas.append(selection_data)
                self.update_selection_list()
                
                # Redibujar para actualizar colores
                self.update_page_display()
            
            # Limpiar selección temporal
            if self.current_rect:
                self.canvas.delete(self.current_rect)
            self.start_x = None
            self.start_y = None
            self.current_rect = None
    
    def update_selection_list(self):
        """Actualizar la lista de áreas seleccionadas"""
        self.selection_listbox.delete(0, tk.END)
        
        for i, area in enumerate(self.selected_areas):
            status = ""
            if i in self.detected_texts:
                status += " [T]"  # Texto detectado
            if i in self.translated_texts:
                status += " [TR]"  # Traducido
            
            # Mostrar rotación si existe
            rot = area.get('rotation', 0)
            rot_str = f" (Rot: {rot}°)" if rot else ""
            
            # Mostrar tamaño de fuente si difiere del global
            area_font_size = area.get('font_size')
            font_str = ""
            if area_font_size and area_font_size != self.global_font_size:
                font_str = f" (Font: {area_font_size}pt)"
            
            self.selection_listbox.insert(tk.END, f"Área {i+1}{status}{rot_str}{font_str}")
    
    def prev_page(self):
        """Ir a la página anterior"""
        if self.pdf_document and self.current_page > 0:
            self.current_page -= 1
            self.update_page_display()
            self.clear_resize_handles()
    
    def next_page(self):
        """Ir a la página siguiente"""
        if self.pdf_document and self.current_page < len(self.pdf_document) - 1:
            self.current_page += 1
            self.update_page_display()
            self.clear_resize_handles()
    
    def zoom_in(self):
        """Aumentar zoom"""
        if self.zoom_factor < 3.0:
            self.zoom_factor += 0.2
            self.update_page_display()
    
    def zoom_out(self):
        """Disminuir zoom"""
        if self.zoom_factor > 0.4:
            self.zoom_factor -= 0.2
            self.update_page_display()
    
    def toggle_edit_mode(self):
        """Alternar modo de edición"""
        self.edit_mode = not self.edit_mode
        
        if self.edit_mode:
            messagebox.showinfo("Modo Edición", "Haz clic en un área para editarla")
        else:
            self.clear_resize_handles()
            self.selected_area_index = None
    
    def delete_selected_area(self):
        """Eliminar el área seleccionada en la lista"""
        selection = self.selection_listbox.curselection()
        if selection:
            area_index = selection[0]
            
            if messagebox.askyesno("Confirmar", f"¿Eliminar área {area_index + 1}?"):
                # Eliminar área y reindexar
                del self.selected_areas[area_index]
                
                # Reindexar textos detectados y traducidos
                new_detected_texts = {}
                new_translated_texts = {}
                
                for old_index in sorted(self.detected_texts.keys()):
                    if old_index < area_index:
                        new_detected_texts[old_index] = self.detected_texts[old_index]
                    elif old_index > area_index:
                        new_detected_texts[old_index - 1] = self.detected_texts[old_index]
                
                for old_index in sorted(self.translated_texts.keys()):
                    if old_index < area_index:
                        new_translated_texts[old_index] = self.translated_texts[old_index]
                    elif old_index > area_index:
                        new_translated_texts[old_index - 1] = self.translated_texts[old_index]
                
                self.detected_texts = new_detected_texts
                self.translated_texts = new_translated_texts
                
                self.update_selection_list()
                self.update_page_display()
                self.clear_resize_handles()
    
    def clear_selections(self):
        """Limpiar todas las selecciones"""
        if messagebox.askyesno("Confirmar", "¿Limpiar todas las áreas seleccionadas?"):
            self.selected_areas = []
            self.detected_texts = {}
            self.translated_texts = {}
            self.update_selection_list()
            self.update_page_display()
            self.clear_resize_handles()
            
            # Limpiar texto detectado
            self.detected_text.config(state=tk.NORMAL)
            self.detected_text.delete(1.0, tk.END)
            self.detected_text.config(state=tk.DISABLED)
    
    def rotate_left(self):
        """Rotar la página actual 90 grados a la izquierda"""
        current_rotation = self.page_rotations.get(self.current_page, 0)
        self.page_rotations[self.current_page] = (current_rotation - 90) % 360
        self.update_page_display()
    
    def rotate_right(self):
        """Rotar la página actual 90 grados a la derecha"""
        current_rotation = self.page_rotations.get(self.current_page, 0)
        self.page_rotations[self.current_page] = (current_rotation + 90) % 360
        self.update_page_display()
    
    def reset_rotation(self):
        """Resetear la rotación de la página actual a 0 grados"""
        if self.current_page in self.page_rotations:
            del self.page_rotations[self.current_page]
        self.update_page_display()
    
    def show_block_style_modal(self):
        modal = tk.Toplevel(self.root)
        modal.title("Configurar Estilo de Bloque Traducido")
        modal.geometry("350x380")
        modal.transient(self.root)
        modal.grab_set()
        frm = ttk.Frame(modal, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="Color de fondo (RGB 0-255):").pack(anchor=tk.W)
        bg_r = tk.IntVar(value=int(self.block_bg[0]*255))
        bg_g = tk.IntVar(value=int(self.block_bg[1]*255))
        bg_b = tk.IntVar(value=int(self.block_bg[2]*255))
        bg_frame = ttk.Frame(frm)
        bg_frame.pack(fill=tk.X, pady=2)
        ttk.Entry(bg_frame, textvariable=bg_r, width=4).pack(side=tk.LEFT)
        ttk.Entry(bg_frame, textvariable=bg_g, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Entry(bg_frame, textvariable=bg_b, width=4).pack(side=tk.LEFT)
        ttk.Label(frm, text="Color de texto (RGB 0-255):").pack(anchor=tk.W, pady=(10,0))
        txt_r = tk.IntVar(value=int(self.block_text_color[0]*255))
        txt_g = tk.IntVar(value=int(self.block_text_color[1]*255))
        txt_b = tk.IntVar(value=int(self.block_text_color[2]*255))
        txt_frame = ttk.Frame(frm)
        txt_frame.pack(fill=tk.X, pady=2)
        ttk.Entry(txt_frame, textvariable=txt_r, width=4).pack(side=tk.LEFT)
        ttk.Entry(txt_frame, textvariable=txt_g, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Entry(txt_frame, textvariable=txt_b, width=4).pack(side=tk.LEFT)
        ttk.Label(frm, text="Color de borde (RGB 0-255):").pack(anchor=tk.W, pady=(10,0))
        border_r = tk.IntVar(value=int(self.block_border_color[0]*255))
        border_g = tk.IntVar(value=int(self.block_border_color[1]*255))
        border_b = tk.IntVar(value=int(self.block_border_color[2]*255))
        border_frame = ttk.Frame(frm)
        border_frame.pack(fill=tk.X, pady=2)
        ttk.Entry(border_frame, textvariable=border_r, width=4).pack(side=tk.LEFT)
        ttk.Entry(border_frame, textvariable=border_g, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Entry(border_frame, textvariable=border_b, width=4).pack(side=tk.LEFT)
        ttk.Label(frm, text="Tamaño de fuente:").pack(anchor=tk.W, pady=(10,0))
        font_size_var = tk.IntVar(value=self.block_font_size)
        ttk.Entry(frm, textvariable=font_size_var, width=6).pack(anchor=tk.W, pady=2)
        
        # Opción de auto apertura
        ttk.Label(frm, text="Opciones:").pack(anchor=tk.W, pady=(15,5))
        auto_open_var = tk.BooleanVar(value=self.auto_open_pdf)
        ttk.Checkbutton(frm, text="Preguntar para abrir PDF después de guardar", 
                       variable=auto_open_var).pack(anchor=tk.W, pady=2)
        
        def save_style():
            self.block_bg = (bg_r.get()/255, bg_g.get()/255, bg_b.get()/255)
            self.block_text_color = (txt_r.get()/255, txt_g.get()/255, txt_b.get()/255)
            self.block_border_color = (border_r.get()/255, border_g.get()/255, border_b.get()/255)
            self.block_font_size = font_size_var.get()
            self.auto_open_pdf = auto_open_var.get()
            modal.destroy()
        ttk.Button(frm, text="Guardar", command=save_style).pack(pady=10)
        ttk.Button(frm, text="Cancelar", command=modal.destroy).pack()

    # Métodos de configuración
    def save_api_key(self):
        self.api_key = self.api_key_var.get().strip()
        self.translation_service.update_api_key(self.api_key)
        self.config_manager.save_api_key(self.api_key)
        messagebox.showinfo("Éxito", "API Key guardada correctamente en .env")
    
    def save_configuration(self):
        """Guardar la configuración actual usando el config manager"""
        config_name = self.config_name_var.get().strip()
        if not config_name:
            messagebox.showwarning("Advertencia", "Introduce un nombre para la configuración")
            return
        
        if not self.selected_areas:
            messagebox.showwarning("Advertencia", "No hay áreas seleccionadas para guardar")
            return
        
        try:
            # Preparar configuración de estilo
            style_config = {
                'block_bg': self.block_bg,
                'block_text_color': self.block_text_color,
                'block_border_color': self.block_border_color,
                'block_font_size': self.block_font_size,
                'auto_open_pdf': self.auto_open_pdf
            }
            
            # Usar el config manager para guardar
            self.config_manager.save_configuration(
                config_name, 
                self.pdf_document, 
                self.selected_areas, 
                self.detected_texts, 
                self.translated_texts, 
                self.page_rotations, 
                style_config
            )
            
            # Actualizar lista de configuraciones
            self.load_saved_configurations()
            
            # Limpiar el campo de nombre
            self.config_name_var.set("")
            
            messagebox.showinfo("Éxito", f"Configuración '{config_name}' guardada correctamente")
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la configuración: {str(e)}")
    
    def load_saved_configurations(self):
        """Cargar lista de configuraciones guardadas usando el config manager"""
        self.config_listbox.delete(0, tk.END)
        
        try:
            configs = self.config_manager.load_saved_configurations()
            for config_name in configs:
                self.config_listbox.insert(tk.END, config_name)
        except Exception as e:
            print(f"Error al cargar configuraciones: {e}")
    
    def load_selected_configuration(self):
        """Cargar la configuración seleccionada en la lista"""
        selection = self.config_listbox.curselection()
        if not selection:
            messagebox.showwarning("Advertencia", "Selecciona una configuración para cargar")
            return
        
        config_name = self.config_listbox.get(selection[0])
        self.load_configuration_by_name(config_name)
    
    def load_configuration_by_name(self, config_name):
        """Cargar configuración por nombre usando el config manager"""
        try:
            config_data, message = self.config_manager.load_configuration_by_name(config_name)
            
            if not config_data:
                messagebox.showerror("Error", f"No se encontró la configuración '{config_name}': {message}")
                return
            
            # Limpiar datos actuales
            self.selected_areas = []
            self.detected_texts = {}
            self.translated_texts = {}
            
            # Cargar datos básicos
            self.page_rotations = config_data.get('page_rotations', {})
            
            # Cargar configuración de estilo
            style_config = config_data.get('style_config', {})
            self.block_bg = tuple(style_config.get('block_bg', (1, 1, 1)))
            self.block_text_color = tuple(style_config.get('block_text_color', (0, 0, 0)))
            self.block_border_color = tuple(style_config.get('block_border_color', (0.7, 0.7, 0.7)))
            self.block_font_size = style_config.get('block_font_size', 12)
            self.auto_open_pdf = style_config.get('auto_open_pdf', True)
            
            # Cargar áreas - SOLO las áreas, NO los textos detectados ni traducidos
            for i, area_data in enumerate(config_data.get('areas', [])):
                # Manejar formato de configuración antigua (tuplas) y nueva (diccionarios)
                if isinstance(area_data, (list, tuple)):
                    # Formato antiguo: [page, coords] o (page, coords)
                    if len(area_data) >= 2:
                        area_dict = {
                            'page': area_data[0],
                            'coords': area_data[1],
                            'font_size': self.global_font_size  # Usar global para formato antiguo
                        }
                    else:
                        continue  # Saltar datos malformados
                elif isinstance(area_data, dict):
                    # Formato nuevo: diccionario con claves
                    area_dict = {
                        'page': area_data.get('page', 0),
                        'coords': area_data.get('coords', (0, 0, 100, 100))
                    }
                    
                    # Validar que las coordenadas sean válidas
                    coords = area_dict['coords']
                    if not isinstance(coords, (list, tuple)) or len(coords) != 4:
                        continue  # Saltar área con coordenadas inválidas
                    
                    # Preservar font_size si existe en la configuración, sino usar el global
                    if 'font_size' in area_data:
                        area_dict['font_size'] = area_data['font_size']
                    else:
                        area_dict['font_size'] = self.global_font_size
                    
                    # Preservar rotación si existe
                    if 'rotation' in area_data:
                        area_dict['rotation'] = area_data['rotation']
                    
                    # NO cargar textos detectados ni traducidos - solo las áreas
                    # Esto fuerza la extracción y traducción para el nuevo documento
                    
                else:
                    # Formato desconocido, saltar
                    continue
                
                self.selected_areas.append(area_dict)
            
            # Actualizar interfaz
            if self.pdf_document:  # Solo actualizar si hay un PDF cargado
                try:
                    self.update_canvas_coords_for_areas()  # Actualizar coordenadas canvas
                    self.update_page_display()
                except Exception as e:
                    print(f"Error al actualizar coordenadas canvas: {e}")
                    # Intentar actualizar solo la página sin coordenadas canvas
                    self.update_page_display()
            self.update_selection_list()
            
            # Mostrar información de la configuración
            self.show_config_info(config_data)
            
            # No mostrar resumen de textos ya que no se cargan
            
            areas_loaded = len(self.selected_areas)
            
            messagebox.showinfo("Éxito", 
                f"Configuración '{config_name}' cargada correctamente\n\n"
                f"• Áreas cargadas: {areas_loaded}\n"
                f"• Textos detectados: 0 (se detectarán automáticamente)\n"
                f"• Traducciones: 0 (se traducirán automáticamente)\n\n"
                f"Usa 'Detectar Texto' y 'Traducir Todo' para procesar el documento con estas áreas.")
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar la configuración: {str(e)}")
            # En caso de error, limpiar datos parciales
            self.selected_areas = []
            self.detected_texts = {}
            self.translated_texts = {}
            self.update_selection_list()
            if self.pdf_document:
                self.update_page_display()
    
    def update_canvas_coords_for_areas(self):
        """Actualizar las coordenadas canvas para todas las áreas después de cargar una configuración"""
        if not self.pdf_document:
            return
            
        for area in self.selected_areas:
            # Verificar que el área tenga coordenadas PDF válidas
            if 'coords' not in area:
                continue
                
            # Convertir coordenadas PDF a coordenadas canvas
            x1, y1, x2, y2 = area['coords']
            
            # Aplicar zoom
            canvas_x1 = x1 * self.zoom_factor
            canvas_y1 = y1 * self.zoom_factor
            canvas_x2 = x2 * self.zoom_factor
            canvas_y2 = y2 * self.zoom_factor
            
            # Guardar coordenadas canvas
            area['canvas_coords'] = (canvas_x1, canvas_y1, canvas_x2, canvas_y2)
    
    def clear_detected_and_translated_texts(self):
        """Limpiar textos detectados y traducidos para forzar nueva detección"""
        if not self.selected_areas:
            messagebox.showwarning("Advertencia", "No hay áreas cargadas")
            return
        
        if messagebox.askyesno("Confirmar", 
            "¿Estás seguro de que quieres limpiar todos los textos detectados y traducidos?\n\n"
            "Esto te permitirá detectar texto fresco en las áreas cargadas para el nuevo documento."):
            
            # Limpiar textos pero mantener las áreas
            self.detected_texts = {}
            self.translated_texts = {}
            
            # Actualizar interfaz
            self.update_selection_list()
            self.update_page_display()
            self.show_detection_summary()
            
            areas_count = len(self.selected_areas)
            messagebox.showinfo("Limpieza completada", 
                f"Se limpiaron los textos de {areas_count} área(s).\n\n"
                f"Ahora puedes usar 'Detectar Texto' para extraer texto del nuevo documento.")

    def show_config_info(self, config_data):
        """Mostrar información de la configuración usando el config manager"""
        try:
            info_text = self.config_manager.format_config_info(config_data)
            
            self.config_info_text.config(state=tk.NORMAL)
            self.config_info_text.delete(1.0, tk.END)
            self.config_info_text.insert(1.0, info_text)
            self.config_info_text.config(state=tk.DISABLED)
        except Exception as e:
            print(f"Error al mostrar información de configuración: {e}")
    
    def delete_configuration(self):
        """Eliminar configuración seleccionada usando el config manager"""
        selection = self.config_listbox.curselection()
        if not selection:
            messagebox.showwarning("Advertencia", "Selecciona una configuración para eliminar")
            return
        
        config_name = self.config_listbox.get(selection[0])
        
        if messagebox.askyesno("Confirmar", f"¿Estás seguro de que quieres eliminar la configuración '{config_name}'?"):
            try:
                self.config_manager.delete_configuration(config_name)
                self.load_saved_configurations()
                
                # Limpiar información
                self.config_info_text.config(state=tk.NORMAL)
                self.config_info_text.delete(1.0, tk.END)
                self.config_info_text.config(state=tk.DISABLED)
                
                messagebox.showinfo("Éxito", f"Configuración '{config_name}' eliminada correctamente")
                
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo eliminar la configuración: {str(e)}")
    
    def export_configuration(self):
        """Exportar configuración usando el config manager"""
        selection = self.config_listbox.curselection()
        if not selection:
            messagebox.showwarning("Advertencia", "Selecciona una configuración para exportar")
            return
        
        config_name = self.config_listbox.get(selection[0])
        
        try:
            self.config_manager.export_configuration(config_name)
            messagebox.showinfo("Éxito", f"Configuración '{config_name}' exportada correctamente")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar la configuración: {str(e)}")
    
    def import_configuration(self):
        """Importar configuración usando el config manager"""
        try:
            config_name = self.config_manager.import_configuration()
            if config_name:
                self.load_saved_configurations()
                messagebox.showinfo("Éxito", f"Configuración '{config_name}' importada correctamente")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo importar la configuración: {str(e)}")
    
    # Métodos de procesamiento OCR y traducción
    def detect_text_in_areas(self):
        """Detectar texto en todas las áreas seleccionadas usando el procesador OCR"""
        if not self.pdf_document or not self.selected_areas:
            messagebox.showwarning("Advertencia", "Carga un PDF y selecciona áreas primero")
            return
        
        try:
            detected_count = 0
            
            # Crear ventana de progreso
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Detectando texto...")
            progress_window.geometry("400x120")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            progress_frame = ttk.Frame(progress_window)
            progress_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            progress_label = ttk.Label(progress_frame, text="Procesando áreas...")
            progress_label.pack(pady=(0, 10))
            
            progress_bar = ttk.Progressbar(progress_frame, maximum=len(self.selected_areas))
            progress_bar.pack(fill=tk.X)
            
            progress_window.update()
            
            for i, area in enumerate(self.selected_areas):
                # Actualizar progreso
                progress_label.config(text=f"Procesando área {i+1} de {len(self.selected_areas)}...")
                progress_bar['value'] = i + 1
                progress_window.update()
                
                # Detectar texto usando el procesador OCR (siempre forzar detección)
                detected_text = self.ocr_processor.enhanced_ocr_detection(
                    area, self.pdf_document, self.page_rotations
                )
                
                if detected_text and detected_text.strip():
                    self.detected_texts[i] = detected_text.strip()
                    detected_count += 1
                else:
                    # Si no se detecta texto, limpiar entrada existente
                    if i in self.detected_texts:
                        del self.detected_texts[i]
            
            # Cerrar ventana de progreso
            progress_window.destroy()
            
            # Actualizar visualización
            self.update_selection_list()
            self.update_page_display()
            
            # Mostrar resumen en el panel de texto
            if detected_count > 0:
                self.show_detection_summary()
                messagebox.showinfo("Éxito", f"Texto detectado en {detected_count} de {len(self.selected_areas)} áreas")
            else:
                messagebox.showwarning("Resultado", "No se detectó texto en ninguna área")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error en la detección de texto: {str(e)}")
    
    def show_detection_summary(self):
        """Mostrar resumen de textos detectados usando el servicio de traducción"""
        self.detected_text.config(state=tk.NORMAL)
        self.detected_text.delete(1.0, tk.END)
        
        # Usar el servicio de traducción para generar el resumen
        content = self.translation_service.get_translation_summary(self.detected_texts, self.translated_texts)
        
        self.detected_text.insert(1.0, content)
        self.detected_text.config(state=tk.DISABLED)

    def translate_all_texts(self):
        """Traducir todos los textos detectados usando el servicio de traducción"""
        if not self.api_key:
            messagebox.showwarning("Advertencia", "Configura tu API Key de DeepSeek primero")
            return
        
        if not self.detected_texts:
            messagebox.showwarning("Advertencia", "Detecta texto en las áreas primero")
            return
        
        # Preparar textos para traducir (forzar traducción de todos los textos detectados)
        texts_to_translate = {}
        for area_index, original_text in self.detected_texts.items():
            if original_text.strip():
                texts_to_translate[area_index] = original_text
        
        if not texts_to_translate:
            messagebox.showinfo("Información", "No hay textos detectados para traducir")
            return
        
        try:
            # Mostrar ventana de progreso
            self.progress_window = tk.Toplevel(self.root)
            self.progress_window.title("Traduciendo...")
            self.progress_window.geometry("400x150")
            self.progress_window.transient(self.root)
            self.progress_window.grab_set()
            
            progress_frame = ttk.Frame(self.progress_window)
            progress_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            self.progress_label = ttk.Label(progress_frame, text="Enviando solicitud a DeepSeek...")
            self.progress_label.pack(pady=(0, 10))
            
            self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
            self.progress_bar.pack(fill=tk.X, pady=(0, 10))
            self.progress_bar.start()
            
            self.progress_window.update()
            
            # Usar el servicio de traducción de forma asíncrona
            self.translation_service.translate_texts_async(
                texts_to_translate,
                callback_success=self._on_translation_success,
                callback_error=self._on_translation_error,
                progress_callback=self._on_translation_progress
            )
                
        except Exception as e:
            if hasattr(self, 'progress_window'):
                self.progress_window.destroy()
            messagebox.showerror("Error", f"Error en la traducción: {str(e)}")
    
    def _on_translation_success(self, translations):
        """Callback cuando la traducción es exitosa"""
        try:
            # Actualizar textos traducidos
            for area_index, translated_text in translations.items():
                self.translated_texts[area_index] = translated_text
            
            # Actualizar interfaz
            self.update_selection_list()
            self.update_page_display()
            self.show_detection_summary()
            
            # Cerrar ventana de progreso
            if hasattr(self, 'progress_window'):
                self.progress_window.destroy()
            
            messagebox.showinfo("Éxito", f"Se tradujeron {len(translations)} textos correctamente")
            
        except Exception as e:
            print(f"Error en callback de éxito: {e}")
    
    def _on_translation_error(self, error_message):
        """Callback cuando hay error en la traducción"""
        try:
            if hasattr(self, 'progress_window'):
                self.progress_window.destroy()
            
            messagebox.showerror("Error de Traducción", error_message)
            
        except Exception as e:
            print(f"Error en callback de error: {e}")
    
    def _on_translation_progress(self, message):
        """Callback para actualizar progreso de traducción"""
        try:
            if hasattr(self, 'progress_label'):
                self.progress_label.config(text=message)
                self.progress_window.update()
        except Exception as e:
            print(f"Error en callback de progreso: {e}")
    
    def create_translation_prompt(self, texts_to_translate):
        """Crear el prompt para la traducción"""
        prompt_parts = []
        prompt_parts.append("Traduce los siguientes textos del inglés al español. Mantén el formato 'Área X:' para cada sección:")
        prompt_parts.append("")
        
        for area_index, text in texts_to_translate.items():
            #text replace break lines with |||
            text = text.replace("\n", "|||")
            prompt_parts.append(f"Área {area_index + 1}: {text}")
        
        prompt_parts.append("")
        prompt_parts.append("Instrucciones:")
        prompt_parts.append("- Traduce cada texto preservando el número de área")
        prompt_parts.append("- Mantén el formato técnico si es aplicable")
        prompt_parts.append("- Si hay términos técnicos, úsalos apropiadamente en español")
        prompt_parts.append("- Los caracteres ||| representan saltos de línea, mantenlos en la traducción")
        prompt_parts.append("- Responde SOLO con las traducciones, manteniendo el formato 'Área X: [traducción]'")
        
        return "\n".join(prompt_parts)
    
    def show_translation_prompt(self, prompt_content, texts_to_translate):
        """Mostrar el prompt que se enviará a DeepSeek"""
        # Crear ventana para mostrar el prompt
        prompt_window = tk.Toplevel(self.root)
        prompt_window.title("Prompt para DeepSeek")
        prompt_window.geometry("800x600")
        prompt_window.transient(self.root)
        prompt_window.grab_set()
        
        # Frame principal
        main_frame = ttk.Frame(prompt_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Label de información
        info_label = ttk.Label(main_frame, text="El siguiente prompt se enviará a DeepSeek API:")
        info_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Frame para el texto con scrollbar
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        prompt_text = tk.Text(text_frame, wrap=tk.WORD, state=tk.NORMAL)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=prompt_text.yview)
        prompt_text.config(yscrollcommand=scrollbar.set)
        
        prompt_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Insertar el prompt
        prompt_text.insert(1.0, prompt_content)
        prompt_text.config(state=tk.DISABLED)
        
        # Frame para botones
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Botones
        ttk.Button(button_frame, text="Cancelar", 
                  command=prompt_window.destroy).pack(side=tk.RIGHT, padx=(5, 0))
        
        ttk.Button(button_frame, text="Enviar Traducción", 
                  command=lambda: self.start_translation_thread(prompt_window, prompt_content, texts_to_translate)).pack(side=tk.RIGHT)
        
        # Label de estado
        self.status_label = ttk.Label(main_frame, text="", foreground="blue")
        self.status_label.pack(anchor=tk.W)
    
    def start_translation_thread(self, prompt_window, prompt_content, texts_to_translate):
        """Iniciar la traducción en un hilo separado"""
        # Cerrar la ventana del prompt
        prompt_window.destroy()
        
        # Crear ventana de progreso
        self.progress_window = tk.Toplevel(self.root)
        self.progress_window.title("Traduciendo...")
        self.progress_window.geometry("400x150")
        self.progress_window.transient(self.root)
        self.progress_window.grab_set()
        
        # Contenido de la ventana de progreso
        progress_frame = ttk.Frame(self.progress_window)
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        self.progress_label = ttk.Label(progress_frame, text="Enviando solicitud a DeepSeek...")
        self.progress_label.pack(pady=(0, 10))
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))
        self.progress_bar.start()
        
        # Botón para cancelar (aunque no implementaremos la cancelación real)
        ttk.Button(progress_frame, text="Ejecutando...", state=tk.DISABLED).pack()
        
        # Iniciar el hilo de traducción
        translation_thread = threading.Thread(
            target=self.translation_worker,
            args=(prompt_content, texts_to_translate)
        )
        translation_thread.daemon = True
        translation_thread.start()
    
    def translation_worker(self, prompt_content, texts_to_translate):
        """Worker que ejecuta la traducción en un hilo separado"""
        try:
            # Preparar la solicitud
            url = "https://api.deepseek.com/v1/chat/completions"
            
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
            
            # Actualizar UI en el hilo principal
            self.root.after(0, lambda: self.progress_label.config(text="Esperando respuesta de DeepSeek..."))
            
            # Realizar la solicitud
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            translated_response = result['choices'][0]['message']['content'].strip()
            
            # Parsear las traducciones
            translations = self.parse_translation_response(translated_response, texts_to_translate)
            
            # Actualizar UI en el hilo principal
            self.root.after(0, lambda: self.translation_completed(translations))
            
        except Exception as e:
            error_msg = f"Error en traducción: {str(e)}"
            self.root.after(0, lambda: self.translation_failed(error_msg))
    
    def parse_translation_response(self, response_text, original_texts):
        """Parsear la respuesta de traducción"""
        translations = {}
        lines = response_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if 'Área' in line and ':' in line:
                try:
                    # Extraer número de área y traducción
                    parts = line.split(':', 1)
                    area_part = parts[0].strip()
                    translation = parts[1].strip()
                    
                    # Extraer número de área
                    area_match = re.search(r'Área\s+(\d+)', area_part)
                    if area_match:
                        area_num = int(area_match.group(1))
                        area_index = area_num - 1  # Convertir a índice base 0
                        
                        if area_index in original_texts:
                            # Restaurar saltos de línea si es necesario (la IA podría haber usado ||| en su respuesta)
                            restored_translation = translation.replace('|||', '\n')
                            translations[area_index] = restored_translation
                except (ValueError, IndexError):
                    continue
        
        return translations
    
    def translation_completed(self, translations):
        """Callback cuando la traducción se completa exitosamente"""
        # Cerrar ventana de progreso
        if hasattr(self, 'progress_window'):
            self.progress_window.destroy()
        
        # Guardar traducciones
        for area_index, translation in translations.items():
            self.translated_texts[area_index] = translation
        
        # Actualizar visualización con vista previa de traducción
        self.update_selection_list()
        self.update_page_display()
        self.show_detection_summary()
        
        # Mostrar resultado
        translated_count = len(translations)
        if translated_count > 0:
            messagebox.showinfo("Éxito", f"Se tradujeron {translated_count} textos correctamente")
        else:
            messagebox.showwarning("Advertencia", "No se pudieron traducir los textos.")
    
    def translation_failed(self, error_message):
        """Callback cuando la traducción falla"""
        # Cerrar ventana de progreso
        if hasattr(self, 'progress_window'):
            self.progress_window.destroy()
        
        messagebox.showerror("Error en Traducción", f"La traducción falló:\n\n{error_message}")
    
    def generate_output_pdf(self):
        """Generar PDF de salida con traducciones sobrepuestas
        
        MEJORAS DE RENDERIZADO:
        - Usa el mismo método de cálculo de fuente que la visualización
        - Optimiza el tamaño de fuente para aprovechar al máximo el área disponible
        - Ajusta las métricas de fuente específicamente para PDF (Helvetica)
        - Mantiene consistencia entre lo que se ve en pantalla y lo que se exporta
        """
        if not self.pdf_document or not self.translated_texts:
            messagebox.showwarning("Advertencia", "Carga un PDF y traduce texto primero")
            return
        
        try:
            # Seleccionar ubicación de guardado
            output_path = filedialog.asksaveasfilename(
                title="Guardar PDF traducido",
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")]
            )
            
            if not output_path:
                return
            
            # Crear copia del documento original
            output_doc = fitz.open()
            
            for page_num in range(len(self.pdf_document)):
                # Copiar página original
                original_page = self.pdf_document[page_num]
                new_page = output_doc.new_page(width=original_page.rect.width, height=original_page.rect.height)
                
                # Insertar contenido de la página original
                new_page.show_pdf_page(new_page.rect, self.pdf_document, page_num)
                
                # Agregar traducciones para esta página
                for area_index, area in enumerate(self.selected_areas):
                    if area['page'] == page_num and area_index in self.translated_texts:
                        # Coordenadas del área
                        x1, y1, x2, y2 = area['coords']
                        translation = self.translated_texts[area_index]
                        
                        # Crear rectángulo semi-transparente
                        rect = fitz.Rect(x1, y1, x2, y2)
                        
                        # Agregar rectángulo de fondo
                        new_page.draw_rect(rect, color=self.block_border_color, fill=self.block_bg, width=1)
                        
                        # Calcular tamaño de fuente apropiado para el área
                        area_width = x2 - x1
                        area_height = y2 - y1
                        
                        # Usar tamaño de fuente específico del área o el global
                        area_font_size = area.get('font_size', self.global_font_size)
                        
                        # Insertar texto traducido con márgenes consistentes
                        margin = 4  # Margen ligeramente mayor para mejor legibilidad
                        text_rect_width = area_width - (2 * margin)
                        text_rect_height = area_height - (2 * margin)
                        
                        if text_rect_width > 0 and text_rect_height > 0:
                            # CLAVE: Usar el mismo método de cálculo que en la visualización, pero para PDF
                            optimal_font_size = self.calculate_optimal_font_size(
                                translation, text_rect_width, text_rect_height, area_font_size, for_pdf=True
                            )
                            
                            # Ajustar texto con algoritmo mejorado para PDF
                            wrapped_text, adjusted_font_size = self.wrap_text_to_fit(
                                translation, text_rect_width, text_rect_height, optimal_font_size
                            )
                            
                            # Crear rectángulo para el texto
                            text_rect = fitz.Rect(x1 + margin, y1 + margin, x2 - margin, y2 - margin)
                            
                            # Insertar texto con parámetros optimizados
                            new_page.insert_textbox(
                                text_rect,
                                wrapped_text,
                                fontsize=adjusted_font_size,
                                color=self.block_text_color,
                                fontname="helv",  # Helvetica - fuente consistente
                                align=0  # Alineación izquierda
                            )
            
            # Guardar documento
            output_doc.save(output_path)
            output_doc.close()
            
            # Mostrar mensaje de éxito con información adicional
            areas_count = len([i for i in self.translated_texts.keys() if i < len(self.selected_areas)])
            messagebox.showinfo("Éxito", 
                f"PDF traducido guardado en: {output_path}\n\n"
                f"• Áreas exportadas: {areas_count}\n"
                f"• Optimización de fuente: Activada\n"
                f"• Consistencia visual: Mejorada")
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el PDF: {str(e)}")
    
    def on_area_selection(self, event):
        """Manejar selección de área desde la lista"""
        selection = self.selection_listbox.curselection()
        if selection:
            area_index = selection[0]
            self.selected_area_index = area_index
            
            # Mostrar texto del área
            self.show_area_text(area_index)
            
            # Ir a la página del área si es necesario
            area = self.selected_areas[area_index]
            if area['page'] != self.current_page:
                self.current_page = area['page']
                self.update_page_display()
            
            # Crear handles si estamos en modo edición
            if self.edit_mode:
                self.clear_resize_handles()
                self.create_resize_handles(area_index)

    def auto_detect_text_areas(self):
        """Función placeholder para auto-detectar áreas de texto"""
        messagebox.showinfo("Info", "Función de auto-detección aún no implementada")
    
    def consolidate_blocks_by_proximity(self):
        """Función placeholder para consolidar bloques"""
        messagebox.showinfo("Info", "Función de consolidación aún no implementada")

    def on_key_press(self, event):
        """Manejar eventos de teclado"""
        if event.keysym == "Delete":
            self.delete_selected_area_key()
        elif event.keysym == "Escape":
            if self.edit_mode:
                self.edit_mode = False
                self.clear_resize_handles()
                self.selected_area_index = None

    def delete_selected_area_key(self):
        """Eliminar área seleccionada usando la tecla Delete"""
        if self.selected_area_index is not None:
            area_index = self.selected_area_index
            
            if messagebox.askyesno("Confirmar", f"¿Eliminar área {area_index + 1}?"):
                # Eliminar área y reindexar
                del self.selected_areas[area_index]
                
                # Reindexar textos detectados y traducidos
                new_detected_texts = {}
                new_translated_texts = {}
                
                for old_index in sorted(self.detected_texts.keys()):
                    if old_index < area_index:
                        new_detected_texts[old_index] = self.detected_texts[old_index]
                    elif old_index > area_index:
                        new_detected_texts[old_index - 1] = self.detected_texts[old_index]
                
                for old_index in sorted(self.translated_texts.keys()):
                    if old_index < area_index:
                        new_translated_texts[old_index] = self.translated_texts[old_index]
                    elif old_index > area_index:
                        new_translated_texts[old_index - 1] = self.translated_texts[old_index]
                
                self.detected_texts = new_detected_texts
                self.translated_texts = new_translated_texts
                
                self.update_selection_list()
                self.update_page_display()
                self.clear_resize_handles()
        else:
            messagebox.showinfo("Info", "Selecciona un área de la lista primero")

    def _rgb_to_hex(self, rgb_tuple):
        """Convertir tupla RGB (0-1) a formato hexadecimal"""
        r, g, b = rgb_tuple
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
    
    def _rgb_to_hex_text_color(self, rgb_tuple):
        """Convertir tupla RGB (0-1) a formato hexadecimal para texto"""
        r, g, b = rgb_tuple
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
    
    def draw_translated_text(self, area_index, x1, y1, x2, y2):
        """Dibujar texto traducido superpuesto en el área"""
        if area_index not in self.translated_texts:
            return
        
        translated_text = self.translated_texts[area_index]
        if not translated_text.strip():
            return
        
        # Calcular dimensiones del área
        area_width = x2 - x1
        area_height = y2 - y1
        
        # Obtener tamaño de fuente específico del área o usar el global
        area = self.selected_areas[area_index] if area_index < len(self.selected_areas) else {}
        area_font_size = area.get('font_size', self.global_font_size)
        
        # Calcular tamaño de fuente óptimo usando la función mejorada
        optimal_font_size = self.calculate_optimal_font_size(
            translated_text, area_width, area_height, area_font_size
        )
        
        # Ajustar texto al área
        margin = 4
        text_width = area_width - (2 * margin)
        text_height = area_height - (2 * margin)
        
        if text_width <= 0 or text_height <= 0:
            return
        
        # Preparar texto ajustado
        wrapped_text, final_font_size = self.wrap_text_for_canvas(
            translated_text, text_width, text_height, optimal_font_size
        )
        
        # Calcular posición del texto
        text_x = x1 + margin
        text_y = y1 + margin
        
        # Color del texto
        text_color = self._rgb_to_hex_text_color(self.block_text_color)
        
        # Crear texto editable en el canvas
        text_id = self.canvas.create_text(
            text_x, text_y,
            text=wrapped_text,
            fill=text_color,
            font=("Arial", final_font_size),
            anchor="nw",
            width=text_width
        )
        
        # Hacer el texto clickeable para edición
        self.canvas.tag_bind(text_id, "<Double-Button-1>", 
                           lambda e, idx=area_index: self.edit_translated_text(idx))
        
        # Agregar cursor pointer para indicar que es clickeable
        self.canvas.tag_bind(text_id, "<Enter>", 
                           lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(text_id, "<Leave>", 
                           lambda e: self.canvas.config(cursor=""))
    
    def wrap_text_for_canvas(self, text, max_width, max_height, font_size):
        """Ajustar texto para el canvas aprovechando al máximo el alto del área"""
        import tkinter.font as tkFont
        
        if not text.strip():
            return "", font_size
        
        # Normalizar saltos de línea: convertir ||| a \n y manejar ambos
        normalized_text = text.replace('|||', '\n')
        
        # Intentar usar el tamaño de fuente óptimo calculado primero
        optimal_size = self.calculate_optimal_font_size(text, max_width, max_height, font_size)
        
        # Probar con el tamaño óptimo y algunos ligeramente menores por seguridad
        test_sizes = [optimal_size, max(4, optimal_size - 1), max(4, optimal_size - 2)]
        
        for test_font_size in test_sizes:
            try:
                font = tkFont.Font(family="Arial", size=test_font_size)
                line_height = font.metrics('linespace')
                
                lines = []
                fits_area = True
                
                paragraphs = normalized_text.split('\n')
                for paragraph in paragraphs:
                    if not paragraph.strip():
                        lines.append('')
                        continue
                    words = paragraph.split()
                    if not words:
                        lines.append('')
                        continue
                    
                    current_line = []
                    for word in words:
                        test_line = current_line + [word]
                        test_text = ' '.join(test_line)
                        text_width = font.measure(test_text)
                        if text_width <= max_width - 8:
                            current_line = test_line
                        else:
                            if current_line:
                                lines.append(' '.join(current_line))
                                current_line = [word]
                                # Verificar si la palabra sola cabe
                                word_width = font.measure(word)
                                if word_width > max_width - 8:
                                    # Dividir palabra larga
                                    best_fit = ""
                                    for i in range(1, len(word) + 1):
                                        test_word = word[:i]
                                        if font.measure(test_word + "-") <= max_width - 8:
                                            best_fit = test_word
                                        else:
                                            break
                                    if len(best_fit) > 0 and len(best_fit) < len(word):
                                        lines.append(best_fit + "-")
                                        remaining = word[len(best_fit):]
                                        current_line = [remaining] if remaining else []
                                    else:
                                        fits_area = False
                                        break
                            else:
                                # Primera palabra en la línea es muy larga
                                word_width = font.measure(word)
                                if word_width > max_width - 8:
                                    # Forzar división de palabra
                                    best_fit = ""
                                    for i in range(1, len(word) + 1):
                                        test_word = word[:i]
                                        if font.measure(test_word) <= max_width - 8:
                                            best_fit = test_word
                                        else:
                                            break
                                    if best_fit:
                                        lines.append(best_fit)
                                        remaining = word[len(best_fit):]
                                        if remaining:
                                            current_line = [remaining]
                                    else:
                                        fits_area = False
                                        break
                                else:
                                    current_line = [word]
                    
                    if current_line:
                        lines.append(' '.join(current_line))
                    if not fits_area:
                        break
                
                # Verificar si las líneas caben en la altura
                total_height = len(lines) * line_height
                if fits_area and total_height <= max_height - 8:
                    return '\n'.join(lines), test_font_size
                    
            except Exception as e:
                continue
        
        # Fallback: usar tamaño mínimo con truncamiento inteligente
        min_font_size = 4
        try:
            font = tkFont.Font(family="Arial", size=min_font_size)
            line_height = font.metrics('linespace')
            max_lines = max(1, int((max_height - 8) / line_height))
            
            lines = []
            paragraphs = normalized_text.split('\n')
            
            for paragraph in paragraphs:
                if len(lines) >= max_lines:
                    break
                    
                if not paragraph.strip():
                    lines.append("")
                    continue
                
                words = paragraph.split()
                current_line = []
                
                for word in words:
                    if len(lines) >= max_lines:
                        break
                        
                    test_line = current_line + [word]
                    test_text = ' '.join(test_line)
                    text_width = font.measure(test_text)
                    
                    if text_width <= max_width - 8:
                        current_line = test_line
                    else:
                        if current_line:
                            lines.append(' '.join(current_line))
                            current_line = [word]
                        else:
                            # Palabra muy larga, truncar
                            chars_per_line = max(1, int((max_width - 8) / (min_font_size * 0.6)))
                            lines.append(word[:chars_per_line])
                            current_line = []
                
                if current_line and len(lines) < max_lines:
                    lines.append(' '.join(current_line))
            
            # Si hay más texto que líneas disponibles, agregar "..." al final
            if len(lines) == max_lines and (len(paragraphs) > len(lines) or 
                any(len(p.split()) > 10 for p in paragraphs[len(lines):])):
                if lines:
                    lines[-1] = lines[-1][:max(0, len(lines[-1]) - 3)] + "..."
            
            return '\n'.join(lines), min_font_size
            
        except Exception as e:
            # Fallback de emergencia - usar parámetros del método
            max_chars = max(10, int((max_width * max_height) / (4 * 8)))
            truncated = text[:max_chars] + "..." if len(text) > max_chars else text
            return truncated, 4

    def calculate_optimal_font_size(self, text, rect_width, rect_height, max_font_size=24, for_pdf=False):
        """Calcular el tamaño de fuente óptimo para aprovechar al máximo el ancho y alto del área"""
        import tkinter.font as tkFont
        if not text.strip():
            return max_font_size
        
        normalized_text = text.replace('|||', '\n')
        paragraphs = normalized_text.split('\n')
        
        def calculate_text_metrics(font_size):
            """Calcular métricas del texto para un tamaño de fuente dado"""
            try:
                if for_pdf:
                    # Usar estimación más precisa para PDF
                    char_width_factor = 0.55  # Helvetica promedio
                    line_height_factor = 1.15  # Espaciado entre líneas
                    char_width = font_size * char_width_factor
                    line_height = font_size * line_height_factor
                    
                    total_lines = 0
                    max_line_width = 0
                    
                    for paragraph in paragraphs:
                        if not paragraph.strip():
                            total_lines += 1
                            continue
                        
                        words = paragraph.split()
                        if not words:
                            total_lines += 1
                            continue
                        
                        current_line_width = 0
                        lines_needed = 1
                        
                        for word in words:
                            word_width = len(word + " ") * char_width
                            
                            if current_line_width + word_width <= rect_width - 8:
                                current_line_width += word_width
                                max_line_width = max(max_line_width, current_line_width)
                            else:
                                lines_needed += 1
                                current_line_width = word_width
                                max_line_width = max(max_line_width, current_line_width)
                                
                                if word_width > rect_width - 8:
                                    chars_per_line = max(1, int((rect_width - 8) / char_width))
                                    extra_lines = max(0, (len(word) - 1) // chars_per_line)
                                    lines_needed += extra_lines
                        
                        total_lines += lines_needed
                    
                    total_height = total_lines * line_height
                    width_utilization = max_line_width / (rect_width - 8) if rect_width > 8 else 0
                    height_utilization = total_height / (rect_height - 8) if rect_height > 8 else 0
                    
                    return {
                        'total_lines': total_lines,
                        'total_height': total_height,
                        'max_line_width': max_line_width,
                        'width_utilization': width_utilization,
                        'height_utilization': height_utilization,
                        'fits': total_height <= rect_height - 8
                    }
                else:
                    # Usar fuente tkinter para canvas
                    font = tkFont.Font(family="Arial", size=font_size)
                    line_height = font.metrics('linespace')
                    total_lines = 0
                    max_line_width = 0  # Ancho máximo de línea
                    
                    for paragraph in paragraphs:
                        if not paragraph.strip():
                            total_lines += 1
                            continue
                        
                        words = paragraph.split()
                        if not words:
                            total_lines += 1
                            continue
                        
                        current_line_width = 0
                        lines_needed = 1
                        
                        for word in words:
                            word_width = font.measure(word + " ")
                            
                            # Verificar si la palabra cabe en la línea actual
                            if current_line_width + word_width <= rect_width - 8:
                                current_line_width += word_width
                                max_line_width = max(max_line_width, current_line_width)
                            else:
                                # Nueva línea necesaria
                                lines_needed += 1
                                current_line_width = word_width
                                max_line_width = max(max_line_width, current_line_width)
                                
                                # Manejar palabras muy largas
                                if word_width > rect_width - 8:
                                    chars_per_line = max(1, int((rect_width - 8) / (font_size * 0.6)))
                                    extra_lines = max(0, (len(word) - 1) // chars_per_line)
                                    lines_needed += extra_lines
                        
                        total_lines += lines_needed
                    
                    total_height = total_lines * line_height
                    width_utilization = max_line_width / (rect_width - 8) if rect_width > 8 else 0
                    height_utilization = total_height / (rect_height - 8) if rect_height > 8 else 0
                    
                    return {
                        'total_lines': total_lines,
                        'total_height': total_height,
                        'max_line_width': max_line_width,
                        'width_utilization': width_utilization,
                        'height_utilization': height_utilization,
                        'fits': total_height <= rect_height - 8
                    }
            except Exception:
                return None
        
        best_font_size = 4
        best_score = 0
        target_area = (rect_width - 8) * (rect_height - 8)
        
        # Buscar el tamaño de fuente que mejor aproveche el área disponible
        for font_size in range(int(max_font_size), 3, -1):
            metrics = calculate_text_metrics(font_size)
            
            if metrics is None or not metrics['fits']:
                continue
            
            # Calcular puntuación basada en el aprovechamiento del área
            # Priorizar el uso del ancho y alto de manera equilibrada
            width_score = min(1.0, metrics['width_utilization'])
            height_score = min(1.0, metrics['height_utilization'])
            
            # Puntuación combinada: favorece el equilibrio entre ancho y alto
            # Bonus por usar más del 80% del ancho
            width_bonus = 1.2 if width_score > 0.8 else 1.0
            # Bonus por usar más del 80% del alto
            height_bonus = 1.2 if height_score > 0.8 else 1.0
            
            # Puntuación final: combina utilización de ancho y alto, con bonus por usar ambos bien
            combined_score = (width_score * width_bonus + height_score * height_bonus) / 2
            
            # Bonus adicional por tamaño de fuente más grande (mejor legibilidad)
            size_bonus = font_size / max_font_size * 0.1
            final_score = combined_score + size_bonus
            
            if final_score > best_score:
                best_score = final_score
                best_font_size = font_size
        
        # Refinamiento: intentar tamaños intermedios si el mejor es significativamente pequeño
        if best_font_size < max_font_size * 0.7:
            # Probar tamaños intermedios con incrementos de 0.5
            for font_size_float in [best_font_size + 0.5, best_font_size + 1, best_font_size + 1.5]:
                if font_size_float > max_font_size:
                    break
                    
                metrics = calculate_text_metrics(int(font_size_float))
                if metrics and metrics['fits']:
                    width_score = min(1.0, metrics['width_utilization'])
                    height_score = min(1.0, metrics['height_utilization'])
                    width_bonus = 1.2 if width_score > 0.8 else 1.0
                    height_bonus = 1.2 if height_score > 0.8 else 1.0
                    combined_score = (width_score * width_bonus + height_score * height_bonus) / 2
                    size_bonus = int(font_size_float) / max_font_size * 0.1
                    final_score = combined_score + size_bonus
                    
                    if final_score > best_score:
                        best_score = final_score
                        best_font_size = int(font_size_float)
        
        return max(4, best_font_size)
    
    def edit_translated_text(self, area_index):
        """Abrir editor para texto traducido"""
        if area_index not in self.translated_texts:
            return
        
        # Crear ventana de edición
        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"Editar Traducción - Área {area_index + 1}")
        edit_window.geometry("700x500")
        edit_window.transient(self.root)
        edit_window.grab_set()
        
        # Frame principal
        main_frame = ttk.Frame(edit_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Label de información
        ttk.Label(main_frame, text=f"Editando traducción del Área {area_index + 1}:").pack(anchor=tk.W, pady=(0, 5))
        
        # Texto original (solo lectura)
        if area_index in self.detected_texts:
            ttk.Label(main_frame, text="Texto original:").pack(anchor=tk.W)
            original_frame = ttk.Frame(main_frame)
            original_frame.pack(fill=tk.X, pady=(0, 10))
            
            original_text = tk.Text(original_frame, height=3, wrap=tk.WORD, state=tk.DISABLED)
            original_text.pack(fill=tk.X)
            
            original_text.config(state=tk.NORMAL)
            original_text.insert(1.0, self.detected_texts[area_index])
            original_text.config(state=tk.DISABLED)
        
        # Frame para configuración de renderizado
        config_frame = ttk.LabelFrame(main_frame, text="Configuración de Renderizado", padding=5)
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Información sobre saltos de línea
        info_frame = ttk.Frame(config_frame)
        info_frame.pack(fill=tk.X, pady=(0, 5))
        
        info_text = "💡 Tip: Usa Enter, Ctrl+Enter o el botón 'Salto' para crear nuevas líneas en el texto. El botón 'Aplicar Cambios' guarda los cambios permanentemente."
        ttk.Label(info_frame, text=info_text, font=("Arial", 8), foreground="blue").pack(anchor=tk.W)
        
        # Control de tamaño de fuente y utilidades
        font_frame = ttk.Frame(config_frame)
        font_frame.pack(fill=tk.X, pady=2)
        ttk.Label(font_frame, text="Tamaño de fuente:").pack(side=tk.LEFT)
        
        # Variable para el tamaño de fuente del área específica
        area = self.selected_areas[area_index] if area_index < len(self.selected_areas) else {}
        current_font_size = area.get('font_size', self.global_font_size)
        font_size_var = tk.IntVar(value=current_font_size)
        font_size_spinbox = ttk.Spinbox(font_frame, from_=8, to=24, width=5, textvariable=font_size_var)
        font_size_spinbox.pack(side=tk.LEFT, padx=(5, 10))
        
        # Botón para insertar salto de línea
        def insert_line_break():
            """Insertar salto de línea en la posición del cursor"""
            try:
                cursor_pos = text_edit.index(tk.INSERT)
                text_edit.insert(cursor_pos, '\n')
            except:
                pass
        
        ttk.Button(font_frame, text="↵ Salto", 
                  command=insert_line_break).pack(side=tk.LEFT, padx=(10, 0))
        
        # Vista previa del área
        preview_frame = ttk.LabelFrame(main_frame, text="Vista Previa del Área", padding=5)
        preview_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Canvas para vista previa
        preview_canvas = tk.Canvas(preview_frame, height=120, bg="white")
        preview_canvas.pack(fill=tk.X, pady=2)
        
        def update_render():
            """Actualizar renderizado con nueva configuración"""
            # Verificar si text_edit existe antes de usarlo
            try:
                current_text = text_edit.get(1.0, tk.END).strip()
            except:
                messagebox.showwarning("Advertencia", "Editor de texto no disponible")
                return
                
            if not current_text:
                messagebox.showwarning("Advertencia", "No hay texto para actualizar")
                return
                
            # Actualizar el texto traducido
            self.translated_texts[area_index] = current_text
            
            # Guardar permanentemente el tamaño de fuente en el área
            area = self.selected_areas[area_index]
            area['font_size'] = font_size_var.get()
            
            # Actualizar vista en el canvas principal
            self.update_page_display()
            self.show_detection_summary()
            
            # Actualizar vista previa inmediatamente
            try:
                update_preview()
            except:
                pass  # update_preview podría no estar definida aún
            
            # Mostrar mensaje de confirmación más discreto
            def show_temp_message():
                try:
                    temp_label = ttk.Label(button_frame, text="✅ Cambios aplicados", foreground="green")
                    temp_label.pack(side=tk.LEFT, padx=(5, 0))
                    edit_window.after(2000, temp_label.destroy)  # Desaparece después de 2 segundos
                except:
                    pass  # button_frame podría no estar definido aún
            
            show_temp_message()
        
        # Ahora agregar el botón después de definir la función
        ttk.Button(font_frame, text="🔄 Actualizar", 
                  command=update_render).pack(side=tk.LEFT, padx=(20, 0))
        
        def update_preview():
            """Actualizar vista previa del área con el texto actual"""
            preview_canvas.delete("all")
            
            # Obtener texto actual del editor
            current_text = text_edit.get(1.0, tk.END).strip()
            if not current_text:
                return
            
            # Simular el área del PDF (escalada para la vista previa)
            area = self.selected_areas[area_index]
            x1, y1, x2, y2 = area['coords']
            area_width = x2 - x1
            area_height = y2 - y1
            
            # Escalar para que quepa en la vista previa
            canvas_width = preview_canvas.winfo_width() or 400
            canvas_height = 100
            
            scale_x = min(canvas_width / area_width, canvas_height / area_height) * 0.8
            preview_width = area_width * scale_x
            preview_height = area_height * scale_x
            
            # Centrar en el canvas
            start_x = (canvas_width - preview_width) / 2
            start_y = (canvas_height - preview_height) / 2
            
            # Dibujar rectángulo del área
            preview_canvas.create_rectangle(
                start_x, start_y, start_x + preview_width, start_y + preview_height,
                fill=self._rgb_to_hex(self.block_bg),
                outline=self._rgb_to_hex(self.block_border_color),
                width=2
            )
            
            # Calcular tamaño de fuente para la vista previa
            preview_font_size = max(8, int(font_size_var.get() * scale_x))
            
            # Ajustar texto para la vista previa
            margin = 2
            text_width = preview_width - (2 * margin)
            text_height = preview_height - (2 * margin)
            
            if text_width > 0 and text_height > 0:
                wrapped_text, adjusted_font_size = self.wrap_text_for_canvas(
                    current_text, text_width, text_height, preview_font_size
                )
                
                # Mostrar texto en la vista previa
                preview_canvas.create_text(
                    start_x + margin, start_y + margin,
                    text=wrapped_text,
                    fill=self._rgb_to_hex_text_color(self.block_text_color),
                    font=("Arial", max(6, adjusted_font_size)),
                    anchor="nw",
                    width=text_width
                )
        
        # Texto traducido (editable)
        translation_header_frame = ttk.Frame(main_frame)
        translation_header_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(translation_header_frame, text="Traducción:").pack(side=tk.LEFT)
        
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        text_edit = tk.Text(text_frame, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_edit.yview)
        text_edit.config(yscrollcommand=scrollbar.set)
        
        text_edit.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Insertar texto actual
        text_edit.insert(1.0, self.translated_texts[area_index])
        
        # Frame para botones
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        def save_and_close():
            """Guardar cambios, aplicar configuración y cerrar ventana"""
            current_text = text_edit.get(1.0, tk.END).strip()
            if current_text:
                # Actualizar el texto traducido
                self.translated_texts[area_index] = current_text
                
                # Guardar el tamaño de fuente específico para esta área
                area = self.selected_areas[area_index]
                area['font_size'] = font_size_var.get()
                
                # Actualizar vista en el canvas principal
                self.update_page_display()
                self.show_detection_summary()
                
                edit_window.destroy()
                messagebox.showinfo("Guardado", f"Traducción del Área {area_index + 1} guardada correctamente\nTamaño de fuente específico: {font_size_var.get()}pt")
            else:
                messagebox.showwarning("Advertencia", "No hay texto para guardar")
        
        def cancel_edit():
            edit_window.destroy()
        
        # Botones simplificados
        button_left = ttk.Frame(button_frame)
        button_left.pack(side=tk.LEFT)
        
        # Vista previa temporal sin guardar
        ttk.Button(button_left, text="🔄 Aplicar Cambios", 
                  command=lambda: update_render()).pack(side=tk.LEFT, padx=(0, 10))
        
        button_right = ttk.Frame(button_frame)
        button_right.pack(side=tk.RIGHT)
        
        ttk.Button(button_right, text="❌ Cancelar", 
                  command=cancel_edit).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_right, text="💾 Guardar y Cerrar", 
                  command=save_and_close).pack(side=tk.LEFT)
        
        # Vincular eventos para actualización automática de vista previa
        def on_text_change(*args):
            edit_window.after_idle(update_preview)
        
        def on_font_change(*args):
            edit_window.after_idle(update_preview)
        
        def on_key_press(event):
            # Atajo F5 para actualizar
            if event.keysym == 'F5':
                update_render()
                return 'break'
            # Atajo Ctrl+Enter para insertar salto de línea
            elif event.keysym == 'Return' and event.state & 0x4:  # Ctrl está presionado
                cursor_pos = text_edit.index(tk.INSERT)
                text_edit.insert(cursor_pos, '\n')
                return 'break'
        
        # Vincular cambios en el texto
        text_edit.bind('<KeyRelease>', on_text_change)
        text_edit.bind('<Button-1>', lambda e: edit_window.after(50, update_preview))
        text_edit.bind('<Key>', on_key_press)
        
        # Vincular cambios en el tamaño de fuente
        font_size_var.trace('w', on_font_change)
        
        # Vincular F5 a la ventana también
        edit_window.bind('<F5>', lambda e: update_render())
        
        # Actualizar vista previa inicial después de que la ventana se muestre
        edit_window.after(200, update_preview)

    def on_global_font_change(self):
        """Callback cuando cambia el tamaño de fuente global"""
        try:
            new_size = self.global_font_var.get()
            if new_size != self.global_font_size:
                self.global_font_size = new_size
                # Solo actualizar el valor, sin aplicar automáticamente a todas las áreas
                # El usuario debe usar "Aplicar a Todo" para cambiar áreas existentes
        except tk.TclError:
            # Error en la conversión, mantener valor actual
            pass
    
    def apply_global_font_to_all(self):
        """Aplicar el tamaño de fuente global a todas las áreas y actualizar renderizado"""
        try:
            font_size = self.global_font_var.get()
            
            if not self.selected_areas:
                messagebox.showinfo("Información", "No hay áreas seleccionadas para aplicar el tamaño de fuente.")
                return
            
            # Aplicar a todas las áreas existentes
            for i, area in enumerate(self.selected_areas):
                area['font_size'] = font_size
            
            # Actualizar tamaño global también
            self.global_font_size = font_size
            
            # Actualizar renderizado del canvas y la lista de áreas
            self.update_page_display()
            self.update_selection_list()
            
                       
            messagebox.showinfo("Aplicado", f"Tamaño de fuente {font_size}pt aplicado a {len(self.selected_areas)} área(s).\nCanvas actualizado automáticamente.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al aplicar tamaño de fuente: {str(e)}")

    def show_area_text(self, area_index):
        """Mostrar el texto del área seleccionada"""
        self.detected_text.config(state=tk.NORMAL)
        self.detected_text.delete(1.0, tk.END)
        
        content = f"=== ÁREA {area_index + 1} ===\n\n"
        
        if area_index in self.detected_texts:
            content += f"Texto detectado:\n{self.detected_texts[area_index]}\n\n"
        else:
            content += "Texto detectado: (ninguno)\n\n"
        
        if area_index in self.translated_texts:
            content += f"Traducción:\n{self.translated_texts[area_index]}\n\n"
        else:
            content += "Traducción: (ninguna)\n\n"
        
        self.detected_text.insert(1.0, content)
        self.detected_text.config(state=tk.DISABLED)

    def clear_resize_handles(self):
        """Limpiar handles de redimensionamiento"""
        for handle_id, _ in self.resize_handles:
            self.canvas.delete(handle_id)
        self.resize_handles = []

    def check_area_click(self, canvas_x, canvas_y):
        """Verificar si se hizo clic en un área existente"""
        for i, area in enumerate(self.selected_areas):
            if area['page'] == self.current_page:
                x1, y1, x2, y2 = area['canvas_coords']
                if x1 <= canvas_x <= x2 and y1 <= canvas_y <= y2:
                    # Área seleccionada
                    self.selected_area_index = i
                    self.clear_resize_handles()
                    self.create_resize_handles(i)
                    
                    # Actualizar selección en la lista
                    self.selection_listbox.selection_clear(0, tk.END)
                    self.selection_listbox.selection_set(i)
                    
                    # Mostrar texto del área seleccionada
                    self.show_area_text(i)
                    return True
        return False

    def create_resize_handles(self, area_index):
        """Crear handles de redimensionamiento para un área"""
        if area_index >= len(self.selected_areas):
            return
        
        area = self.selected_areas[area_index]
        if area['page'] != self.current_page:
            return
        
        x1, y1, x2, y2 = area['canvas_coords']
        handle_size = 8
        
        # Crear handles en las esquinas y bordes
        handles = [
            ('nw', x1 - handle_size//2, y1 - handle_size//2),  # Noroeste
            ('ne', x2 - handle_size//2, y1 - handle_size//2),  # Noreste
            ('sw', x1 - handle_size//2, y2 - handle_size//2),  # Suroeste
            ('se', x2 - handle_size//2, y2 - handle_size//2),  # Sureste
            ('n', (x1 + x2)//2 - handle_size//2, y1 - handle_size//2),  # Norte
            ('s', (x1 + x2)//2 - handle_size//2, y2 - handle_size//2),  # Sur
            ('w', x1 - handle_size//2, (y1 + y2)//2 - handle_size//2),  # Oeste
            ('e', x2 - handle_size//2, (y1 + y2)//2 - handle_size//2),  # Este
        ]
        
        for direction, hx, hy in handles:
            handle_id = self.canvas.create_rectangle(
                hx, hy, hx + handle_size, hy + handle_size,
                fill="blue", outline="darkblue", width=2
            )
            self.resize_handles.append((handle_id, direction))

    def check_handle_click(self, x, y):
        """Verificar si se hizo clic en un handle"""
        for handle_id, direction in self.resize_handles:
            coords = self.canvas.coords(handle_id)
            if coords[0] <= x <= coords[2] and coords[1] <= y <= coords[3]:
                return direction
        return None

    def update_resize(self, event):
        """Actualizar redimensionamiento"""
        if self.selected_area_index is None or not self.resize_handle:
            return
            
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        area = self.selected_areas[self.selected_area_index]
        x1, y1, x2, y2 = area['canvas_coords']
        
        # Actualizar coordenadas según el handle seleccionado
        if 'n' in self.resize_handle:
            y1 = canvas_y
        if 's' in self.resize_handle:
            y2 = canvas_y
        if 'w' in self.resize_handle:
            x1 = canvas_x
        if 'e' in self.resize_handle:
            x2 = canvas_x
        
        # Asegurarse de que no se salga de los límites de la página
        page = self.pdf_document[self.current_page]
        page_width = page.rect.width
        page_height = page.rect.height
        
        if x1 < 0:
            offset = -x1
            x1 += offset
            x2 += offset
        elif x2 > page_width:
            offset = x2 - page_width
            x1 -= offset
            x2 -= offset
        
        # Actualizar coordenadas del área
        area['canvas_coords'] = (x1, y1, x2, y2)
        
        # Actualizar coordenadas en PDF
        pdf_coords = (
            x1 / self.zoom_factor,
            y1 / self.zoom_factor,
            x2 / self.zoom_factor,
            y2 / self.zoom_factor
        )
        area['coords'] = pdf_coords
        
        # Redibujar
        self.update_page_display()
        self.create_resize_handles(self.selected_area_index)

    def wrap_text_to_fit(self, text, rect_width, rect_height, font_size, fontname="helv"):
        """Ajustar texto para que quepa en el rectángulo preservando saltos de línea originales"""
        
        if not text.strip():
            return text, font_size
        
        # Normalizar saltos de línea: convertir ||| a \n
        normalized_text = text.replace('|||', '\n')
        
        # Verificar si el texto tiene saltos de línea
        original_lines = normalized_text.split('\n')
        
        # Si el texto tiene múltiples líneas, preservar la estructura
        if len(original_lines) > 1:
            return self._fit_multiline_text_pdf(original_lines, rect_width, rect_height, font_size, fontname)
        
        # Si es una sola línea, usar el método de ajuste automático por palabras
        return self._fit_single_line_text_pdf(normalized_text, rect_width, rect_height, font_size, fontname)
    def _fit_multiline_text_pdf(self, original_lines, rect_width, rect_height, font_size, fontname="helv"):
        """Ajustar texto que ya tiene múltiples líneas preservando la estructura original para PDF"""
        import tkinter.font as tkFont
        
        # Limpiar líneas vacías del inicio y final, pero preservar las intermedias
        while original_lines and not original_lines[0].strip():
            original_lines.pop(0)
        while original_lines and not original_lines[-1].strip():
            original_lines.pop()
        
        if not original_lines:
            return "", font_size
        
        # Factores de ajuste para fuentes PDF (más precisos que la estimación simple)
        # Helvetica (helv) tiene un factor de ancho promedio de ~0.5-0.6
        char_width_factor = 0.55  # Ajustado para helvetica
        line_height_factor = 1.15  # Espaciado entre líneas más realista
        
        # Probar diferentes tamaños de fuente, empezando por el deseado
        for test_font_size in [font_size, font_size * 0.95, font_size * 0.9, font_size * 0.85, font_size * 0.8, font_size * 0.7, font_size * 0.6]:
            char_width = test_font_size * char_width_factor
            line_height = test_font_size * line_height_factor
            
            # Verificar si todas las líneas caben en ancho y altura
            adjusted_lines = []
            
            for line in original_lines:
                line = line.strip()
                if not line:  # Línea vacía
                    adjusted_lines.append("")
                    continue
                
                # Verificar si la línea cabe en el ancho
                estimated_width = len(line) * char_width
                
                if estimated_width <= rect_width - 6:
                    adjusted_lines.append(line)
                else:
                    # Si la línea es muy larga, intentar dividirla por palabras
                    words = line.split()
                    if len(words) == 1:
                        # Es una sola palabra muy larga, cortarla si es necesario
                        chars_per_line = max(1, int((rect_width - 6) / char_width))
                        if len(line) > chars_per_line:
                            # Cortar la palabra
                            for i in range(0, len(line), chars_per_line):
                                chunk = line[i:i+chars_per_line]
                                if i + chars_per_line < len(line):
                                    chunk += "-"
                                adjusted_lines.append(chunk)
                        else:
                            adjusted_lines.append(line)
                    else:
                        # Múltiples palabras, ajustar automáticamente
                        current_line = []
                        for word in words:
                            test_line = current_line + [word]
                            test_text = " ".join(test_line)
                            estimated_width = len(test_text) * char_width
                            
                            if estimated_width <= rect_width - 6:
                                current_line = test_line
                            else:
                                if current_line:
                                    adjusted_lines.append(" ".join(current_line))
                                    current_line = [word]
                                else:
                                    adjusted_lines.append(word)
                        
                        if current_line:
                            adjusted_lines.append(" ".join(current_line))
            
            # Verificar si todas las líneas caben en la altura
            total_height = len(adjusted_lines) * line_height
            
            if total_height <= rect_height - 6:  # Margen de 3px arriba y abajo
                return "\n".join(adjusted_lines), test_font_size
        
        # Si nada funciona, usar el tamaño más pequeño con texto truncado
        min_font_size = max(4, font_size * 0.4)
        char_width = min_font_size * char_width_factor
        line_height = min_font_size * line_height_factor
        max_lines = max(1, int((rect_height - 6) / line_height))
        
        # Tomar solo las primeras líneas que caben
        final_lines = []
        for i, line in enumerate(original_lines):
            if i >= max_lines:
                break
            line = line.strip()
            if not line:
                final_lines.append("")
                continue
                
            # Truncar línea si es muy larga
            chars_per_line = max(1, int((rect_width - 6) / char_width))
            if len(line) > chars_per_line:
                line = line[:chars_per_line-3] + "..."
            final_lines.append(line)
        
        return "\n".join(final_lines), min_font_size

    def adjust_selected_area(self, direction):
        """Ajustar horizontalmente el área seleccionada"""
        if self.selected_area_index is None or not self.edit_mode:
            messagebox.showwarning("Advertencia", "Primero seleccione un área en modo edición")
            return
        
        area = self.selected_areas[self.selected_area_index]
        if area['page'] != self.current_page:
            return
        
        # Obtener coordenadas actuales
        x1, y1, x2, y2 = area['coords']
        
        # Ajuste en píxeles (convertido a coordenadas PDF)
        adjustment = 5 / self.zoom_factor
        
        if direction == 'left':
            # Mover área hacia la izquierda
            x1 -= adjustment
            x2 -= adjustment
        elif direction == 'right':
            # Mover área hacia la derecha
            x1 += adjustment
            x2 += adjustment
        
        # Asegurarse de que no se salga de los límites de la página
        page = self.pdf_document[self.current_page]
        page_width = page.rect.width
        page_height = page.rect.height
        
        if x1 < 0:
            offset = -x1
            x1 += offset
            x2 += offset
        elif x2 > page_width:
            offset = x2 - page_width
            x1 -= offset
            x2 -= offset
        
        # Actualizar coordenadas
        area['coords'] = (x1, y1, x2, y2)
        
        # Actualizar coordenadas del canvas
        canvas_x1 = x1 * self.zoom_factor
        canvas_y1 = y1 * self.zoom_factor
        canvas_x2 = x2 * self.zoom_factor
        canvas_y2 = y2 * self.zoom_factor
        area['canvas_coords'] = (canvas_x1, canvas_y1, canvas_x2, canvas_y2)
        
        # Actualizar visualización
        self.update_page_display()
        self.create_resize_handles(self.selected_area_index)
    
    def rotate_selected_area(self, degrees):
        """Rotar el área seleccionada (visual, para referencia de texto)"""
        if self.selected_area_index is None or not self.edit_mode:
            messagebox.showwarning("Advertencia", "Primero seleccione un área en modo edición")
            return
        
        area = self.selected_areas[self.selected_area_index]
        if area['page'] != self.current_page:
            return
        
        # Agregar o actualizar rotación del área
        if 'rotation' not in area:
            area['rotation'] = 0
        
        area['rotation'] = (area['rotation'] + degrees) % 360
        
        # Si el área tiene texto traducido, agregar indicador visual de rotación
        if self.selected_area_index in self.translated_texts:
            rotation_indicator = f" [↻{area['rotation']}°]" if area['rotation'] != 0 else ""
            
            # Actualizar lista de selecciones para mostrar rotación
            self.update_selection_list()
            
            # Mostrar mensaje informativo
            messagebox.showinfo("Rotación aplicada", 
                              f"Área {self.selected_area_index + 1} rotada {degrees}° (Total: {area['rotation']}°)\n"
                              f"Esta rotación se aplicará al texto al renderizar en el PDF final.")
        else:
            messagebox.showinfo("Rotación aplicada", 
                              f"Área {self.selected_area_index + 1} rotada {degrees}° (Total: {area['rotation']}°)\n"
                              f"Agregue texto traducido para ver el efecto de la rotación.")
        
        # Actualizar visualización para mostrar indicador
        self.update_page_display()
        self.create_resize_handles(self.selected_area_index)
    
    def on_canvas_double_click(self, event):
        """Manejar doble clic en el canvas para abrir editor de texto"""
        if not self.pdf_document:
            return
        
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        # Buscar el área en la que se hizo doble click
        for i, area in enumerate(self.selected_areas):
            if area['page'] == self.current_page:
                x1, y1, x2, y2 = area['canvas_coords']
                if x1 <= canvas_x <= x2 and y1 <= canvas_y <= y2:
                    # Abrir editor de texto traducido si ya existe traducción
                    if i in self.translated_texts:
                        self.edit_translated_text(i)
                    else:
                        # Si no hay traducción pero hay texto detectado, sugerir traducir primero
                        if i in self.detected_texts:
                            result = messagebox.askyesno(
                                "Traducir primero",
                                f"El Área {i + 1} tiene texto detectado pero no traducido.\n¿Desea traducir el texto primero?"
                            )
                            if result:
                                # Mostrar mensaje informativo
                                messagebox.showinfo("Traducir área", "Use el botón 'Traducir Todo' para traducir las áreas y luego haga doble click nuevamente.")
                        else:
                            messagebox.showinfo("Sin texto", f"El Área {i + 1} no tiene texto detectado.\nPrimero realice OCR en esta área.")
                    return
        return False
    

if __name__ == "__main__":
    app = PDFViewer()
    app.root.mainloop()

