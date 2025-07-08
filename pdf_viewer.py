import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font
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

class PDFViewer:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.block_bg = (1, 1, 1)  # Blanco
        self.block_text_color = (0, 0, 0)  # Negro
        self.block_border_color = (0.7, 0.7, 0.7)  # Gris
        self.block_font_size = 12
        self.auto_open_pdf = True  # Auto-abrir PDF después de guardar
        
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
        self.api_key = ""
        
        # Variables para redimensionamiento
        self.resize_handles = []
        self.selected_area_index = None
        self.resize_handle = None
        self.edit_mode = False
        
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        
        self.setup_ui()
        
    def setup_ui(self):
        """Configurar la interfaz de usuario"""
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
        
        self.setup_left_panel(left_panel)
        self.setup_center_panel(center_panel)
        self.setup_right_panel(right_panel)
    
    def setup_left_panel(self, parent):
        """Configurar panel izquierdo"""
        # Grupo: Cargar archivo
        file_group = ttk.LabelFrame(parent, text="Archivo", padding=10)
        file_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(file_group, text="Cargar PDF", command=self.load_pdf).pack(fill=tk.X)
        
        # Grupo: Navegación
        nav_group = ttk.LabelFrame(parent, text="Navegación", padding=10)
        nav_group.pack(fill=tk.X, pady=(0, 10))
        
        nav_frame = ttk.Frame(nav_group)
        nav_frame.pack(fill=tk.X)
        
        ttk.Button(nav_frame, text="◀", command=self.prev_page, width=3).pack(side=tk.LEFT)
        
        self.page_var = tk.StringVar(value="0 / 0")
        ttk.Label(nav_frame, textvariable=self.page_var).pack(side=tk.LEFT, padx=10, expand=True)
        
        ttk.Button(nav_frame, text="▶", command=self.next_page, width=3).pack(side=tk.RIGHT)
        
        # Grupo: Zoom
        zoom_group = ttk.LabelFrame(parent, text="Zoom", padding=10)
        zoom_group.pack(fill=tk.X, pady=(0, 10))
        
        zoom_frame = ttk.Frame(zoom_group)
        zoom_frame.pack(fill=tk.X)
        
        ttk.Button(zoom_frame, text="-", command=self.zoom_out, width=3).pack(side=tk.LEFT)
        
        self.zoom_var = tk.StringVar(value="100%")
        ttk.Label(zoom_frame, textvariable=self.zoom_var).pack(side=tk.LEFT, padx=10, expand=True)
        
        ttk.Button(zoom_frame, text="+", command=self.zoom_in, width=3).pack(side=tk.RIGHT)
        
        # Grupo: Áreas seleccionadas
        areas_group = ttk.LabelFrame(parent, text="Áreas Seleccionadas", padding=10)
        areas_group.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Lista de áreas
        list_frame = ttk.Frame(areas_group)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.selection_listbox = tk.Listbox(list_frame, height=8)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.selection_listbox.yview)
        self.selection_listbox.config(yscrollcommand=scrollbar.set)
        
        self.selection_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind para mostrar texto del área seleccionada
        self.selection_listbox.bind("<Button-1>", self.on_area_selection)  # Para mostrar texto del área seleccionada
        
        # Botones de control de áreas
        area_buttons = ttk.Frame(areas_group)
        area_buttons.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(area_buttons, text="Editar", command=self.toggle_edit_mode, width=8).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(area_buttons, text="Eliminar", command=self.delete_selected_area, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(area_buttons, text="Limpiar", command=self.clear_selections, width=8).pack(side=tk.RIGHT)
        
        # Grupo: Procesamiento
        process_group = ttk.LabelFrame(parent, text="Procesamiento", padding=10)
        process_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(process_group, text="Detectar Texto", command=self.detect_text_in_areas).pack(fill=tk.X, pady=(0, 5))
        ttk.Button(process_group, text="Auto-Detectar Texto", command=self.auto_detect_text_areas).pack(fill=tk.X, pady=(0, 5))
        ttk.Button(process_group, text="Consolidar Bloques", command=self.consolidate_blocks_by_proximity).pack(fill=tk.X, pady=(0, 5))
        ttk.Button(process_group, text="Traducir Todo", command=self.translate_all_texts).pack(fill=tk.X, pady=(0, 5))
        
        # Checkbox para vista previa de traducción
        self.show_translation_preview = tk.BooleanVar(value=True)
        ttk.Checkbutton(process_group, text="Vista previa de traducción", 
                       variable=self.show_translation_preview,
                       command=self.update_page_display).pack(anchor=tk.W, pady=(5, 0))
        
        # Etiqueta informativa
        info_label = ttk.Label(process_group, text="💡 Doble-clic en texto traducido para editar", 
                              font=("Arial", 8), foreground="gray")
        info_label.pack(anchor=tk.W, pady=(2, 5))
        
        ttk.Button(process_group, text="Generar PDF", command=self.generate_output_pdf).pack(fill=tk.X)
    
    def setup_center_panel(self, parent):
        """Configurar panel central"""
        # Frame para el canvas con scrollbars
        canvas_frame = ttk.Frame(parent)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Crear canvas con scrollbars
        self.canvas = tk.Canvas(canvas_frame, bg="white")
        
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        
        self.canvas.config(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack scrollbars y canvas
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bind eventos del canvas
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        
        # Bind para teclas (para eliminar con Delete)
        self.canvas.bind("<KeyPress>", self.on_key_press)
        self.canvas.focus_set()  # Permitir que el canvas reciba eventos de teclado
        
        # Panel de texto detectado
        text_frame = ttk.LabelFrame(parent, text="Texto Detectado", padding=5)
        text_frame.pack(fill=tk.X, pady=(5, 0))
        
        text_container = ttk.Frame(text_frame)
        text_container.pack(fill=tk.BOTH, expand=True)
        
        self.detected_text = tk.Text(text_container, height=6, wrap=tk.WORD, state=tk.DISABLED)
        text_scrollbar = ttk.Scrollbar(text_container, orient=tk.VERTICAL, command=self.detected_text.yview)
        self.detected_text.config(yscrollcommand=text_scrollbar.set)
        
        self.detected_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def setup_right_panel(self, parent):
        """Configurar panel derecho para configuraciones"""
        # Grupo: API Configuration
        api_group = ttk.LabelFrame(parent, text="Configuración API", padding=10)
        api_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(api_group, text="DeepSeek API Key:").pack(anchor=tk.W)
        self.api_key_var = tk.StringVar(value=self.api_key)
        api_entry = ttk.Entry(api_group, textvariable=self.api_key_var, show="*")
        api_entry.pack(fill=tk.X, pady=(2, 5))
        
        ttk.Button(api_group, text="Guardar API Key", command=self.save_api_key).pack(fill=tk.X)
        
        # Estilo de bloque traducido
        style_group = ttk.LabelFrame(parent, text="Estilo de Bloque Traducido", padding=10)
        style_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(style_group, text="Configurar Estilo...", command=self.show_block_style_modal).pack(fill=tk.X)
        
        # Grupo: Guardar Configuración
        save_group = ttk.LabelFrame(parent, text="Guardar Configuración", padding=10)
        save_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(save_group, text="Nombre:").pack(anchor=tk.W)
        self.config_name_var = tk.StringVar()
        ttk.Entry(save_group, textvariable=self.config_name_var).pack(fill=tk.X, pady=(2, 5))
        
        ttk.Button(save_group, text="Guardar", command=self.save_configuration).pack(fill=tk.X)
        
        # Grupo: Configuraciones Guardadas
        configs_group = ttk.LabelFrame(parent, text="Configuraciones Guardadas", padding=10)
        configs_group.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Lista de configuraciones
        config_list_frame = ttk.Frame(configs_group)
        config_list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        self.config_listbox = tk.Listbox(config_list_frame, height=6)
        config_scrollbar = ttk.Scrollbar(config_list_frame, orient=tk.VERTICAL, command=self.config_listbox.yview)
        self.config_listbox.config(yscrollcommand=config_scrollbar.set)
        
        self.config_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        config_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Botones de configuraciones
        config_buttons_frame = ttk.Frame(configs_group)
        config_buttons_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(config_buttons_frame, text="Cargar", command=self.load_selected_configuration, width=10).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(config_buttons_frame, text="Eliminar", command=self.delete_configuration, width=10).pack(side=tk.LEFT, padx=2)
        
        config_buttons_frame2 = ttk.Frame(configs_group)
        config_buttons_frame2.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(config_buttons_frame2, text="Exportar", command=self.export_configuration, width=10).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(config_buttons_frame2, text="Importar", command=self.import_configuration, width=10).pack(side=tk.LEFT, padx=2)
        
        # Información de configuración
        info_group = ttk.LabelFrame(parent, text="Información", padding=10)
        info_group.pack(fill=tk.X)
        
        self.config_info_text = tk.Text(info_group, height=4, wrap=tk.WORD, state=tk.DISABLED)
        info_scrollbar = ttk.Scrollbar(info_group, orient=tk.VERTICAL, command=self.config_info_text.yview)
        self.config_info_text.config(yscrollcommand=info_scrollbar.set)
        
        self.config_info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        info_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Cargar configuraciones guardadas al inicio
        self.load_saved_configurations()
    
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
            
            # Renderizar página con zoom
            mat = fitz.Matrix(self.zoom_factor, self.zoom_factor)
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
        
        # Si estamos en modo edición, verificar si se hizo clic en un área existente
        if self.edit_mode:
            self.check_area_click(canvas_x, canvas_y)
            return
        
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
                    'rect_id': None
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
            
            text = f"Área {i + 1} (Pág. {area['page'] + 1}){status}"
            self.selection_listbox.insert(tk.END, text)
    
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
        # Guardar en .env
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(f'DEEPSEEK_API_KEY={self.api_key}\n')
        messagebox.showinfo("Éxito", "API Key guardada correctamente en .env")
    
    def save_configuration(self):
        """Guardar la configuración actual"""
        config_name = self.config_name_var.get().strip()
        if not config_name:
            messagebox.showwarning("Advertencia", "Introduce un nombre para la configuración")
            return
        
        if not self.selected_areas:
            messagebox.showwarning("Advertencia", "No hay áreas seleccionadas para guardar")
            return
        
        try:
            # Crear directorio si no existe
            config_dir = "configuraciones"
            os.makedirs(config_dir, exist_ok=True)
            
            # Preparar datos de configuración
            config_data = {
                'name': config_name,
                'created_date': datetime.now().isoformat(),
                'pdf_file': getattr(self.pdf_document, 'name', 'unknown') if self.pdf_document else None,
                'total_pages': len(self.pdf_document) if self.pdf_document else 0,
                'areas': []
            }
            
            # Agregar áreas con textos detectados y traducidos
            for i, area in enumerate(self.selected_areas):
                area_data = {
                    'id': i,
                    'page': area['page'],
                    'coords': area['coords']
                }
                
                # Agregar texto detectado si existe
                if i in self.detected_texts:
                    area_data['detected_text'] = self.detected_texts[i]
                
                # Agregar texto traducido si existe
                if i in self.translated_texts:
                    area_data['translated_text'] = self.translated_texts[i]
                
                config_data['areas'].append(area_data)
            
            # Guardar archivo
            config_file = os.path.join(config_dir, f"{config_name}.json")
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            # Actualizar lista de configuraciones
            self.load_saved_configurations()
            
            # Limpiar el campo de nombre
            self.config_name_var.set("")
            
            messagebox.showinfo("Éxito", f"Configuración '{config_name}' guardada correctamente")
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la configuración: {str(e)}")
    
    def load_saved_configurations(self):
        """Cargar lista de configuraciones guardadas"""
        self.config_listbox.delete(0, tk.END)
        
        config_dir = "configuraciones"
        if not os.path.exists(config_dir):
            return
        
        try:
            for filename in os.listdir(config_dir):
                if filename.endswith('.json'):
                    config_name = filename[:-5]  # Remover .json
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
        """Cargar configuración por nombre"""
        try:
            config_file = os.path.join("configuraciones", f"{config_name}.json")
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Limpiar selecciones actuales
            self.selected_areas = []
            self.detected_texts = {}
            self.translated_texts = {}
            
            # Cargar áreas
            for i, area_data in enumerate(config_data['areas']):
                # Convertir coordenadas a coordenadas de canvas según el zoom actual
                x1, y1, x2, y2 = area_data['coords']
                canvas_x1 = x1 * self.zoom_factor
                canvas_y1 = y1 * self.zoom_factor
                canvas_x2 = x2 * self.zoom_factor
                canvas_y2 = y2 * self.zoom_factor
                
                selection_data = {
                    'page': area_data['page'],
                    'coords': (x1, y1, x2, y2),
                    'canvas_coords': (canvas_x1, canvas_y1, canvas_x2, canvas_y2),
                    'rect_id': None
                }
                
                self.selected_areas.append(selection_data)
                
                # Cargar texto detectado y traducido para esta área específica
                if "detected_text" in area_data:
                    self.detected_texts[i] = area_data["detected_text"]
                if "translated_text" in area_data:
                    self.translated_texts[i] = area_data["translated_text"]
            
            # Actualizar visualización
            self.update_selection_list()
            self.update_page_display()
            
            # Mostrar información de la configuración
            self.show_config_info(config_data)
            
            # Ejecutar detección de texto automáticamente si no hay textos guardados
            if not self.detected_texts:
                self.detect_text_in_areas()
            
            messagebox.showinfo("Éxito", f"Configuración '{config_name}' cargada correctamente")
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar la configuración: {str(e)}")
    
    def show_config_info(self, config_data):
        """Mostrar información de la configuración en el panel"""
        self.config_info_text.config(state=tk.NORMAL)
        self.config_info_text.delete(1.0, tk.END)
        
        info = f"Nombre: {config_data['name']}\n"
        info += f"Fecha: {config_data['created_date'][:10]}\n"
        info += f"PDF: {config_data.get('pdf_file', 'N/A')}\n"
        info += f"Páginas: {config_data['total_pages']}\n"
        info += f"Áreas: {len(config_data['areas'])}\n\n"
        
        for area in config_data['areas']:
            info += f"• Área {area['id']} (Pág. {area['page']})\n"
        
        self.config_info_text.insert(1.0, info)
        self.config_info_text.config(state=tk.DISABLED)
    
    def delete_configuration(self):
        """Eliminar la configuración seleccionada"""
        selection = self.config_listbox.curselection()
        if not selection:
            messagebox.showwarning("Advertencia", "Selecciona una configuración para eliminar")
            return
        
        config_name = self.config_listbox.get(selection[0])
        
        if messagebox.askyesno("Confirmar", f"¿Eliminar la configuración '{config_name}'?"):
            try:
                config_file = os.path.join("configuraciones", f"{config_name}.json")
                os.remove(config_file)
                self.load_saved_configurations()
                
                # Limpiar información
                self.config_info_text.config(state=tk.NORMAL)
                self.config_info_text.delete(1.0, tk.END)
                self.config_info_text.config(state=tk.DISABLED)
                
                messagebox.showinfo("Éxito", f"Configuración '{config_name}' eliminada")
                
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo eliminar la configuración: {str(e)}")
    
    def export_configuration(self):
        """Exportar configuración a archivo"""
        selection = self.config_listbox.curselection()
        if not selection:
            messagebox.showwarning("Advertencia", "Selecciona una configuración para exportar")
            return
        
        config_name = self.config_listbox.get(selection[0])
        
        try:
            # Seleccionar ubicación de exportación
            export_path = filedialog.asksaveasfilename(
                title="Exportar configuración",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")],
                initialvalue=f"{config_name}.json"
            )
            
            if export_path:
                config_file = os.path.join("configuraciones", f"{config_name}.json")
                
                # Copiar archivo
                with open(config_file, 'r', encoding='utf-8') as src:
                    with open(export_path, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                
                messagebox.showinfo("Éxito", f"Configuración exportada a: {export_path}")
                
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar la configuración: {str(e)}")
    
    def import_configuration(self):
        """Importar configuración desde archivo"""
        try:
            # Seleccionar archivo a importar
            import_path = filedialog.askopenfilename(
                title="Importar configuración",
                filetypes=[("JSON files", "*.json")]
            )
            
            if import_path:
                # Leer y validar archivo
                with open(import_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # Validar estructura básica
                if 'name' not in config_data or 'areas' not in config_data:
                    messagebox.showerror("Error", "El archivo no tiene el formato correcto")
                    return
                
                # Crear directorio si no existe
                config_dir = "configuraciones"
                os.makedirs(config_dir, exist_ok=True)
                
                # Guardar configuración
                config_name = config_data['name']
                config_file = os.path.join(config_dir, f"{config_name}.json")
                
                # Verificar si ya existe
                if os.path.exists(config_file):
                    if not messagebox.askyesno("Confirmar", f"La configuración '{config_name}' ya existe. ¿Sobrescribir?"):
                        return
                
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
                
                # Actualizar lista
                self.load_saved_configurations()
                
                messagebox.showinfo("Éxito", f"Configuración '{config_name}' importada correctamente")
                
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo importar la configuración: {str(e)}")
    
    # Métodos de procesamiento OCR y traducción
    def detect_text_in_areas(self):
        """Detectar texto en todas las áreas seleccionadas"""
        if not self.pdf_document or not self.selected_areas:
            messagebox.showwarning("Advertencia", "Carga un PDF y selecciona áreas primero")
            return
        
        try:
            detected_count = 0
            
            for i, area in enumerate(self.selected_areas):
                # Obtener página
                page = self.pdf_document[area['page']]
                
                # Renderizar área específica
                x1, y1, x2, y2 = area['coords']
                rect = fitz.Rect(x1, y1, x2, y2)
                
                # Renderizar con alta resolución para mejor OCR
                mat = fitz.Matrix(2.0, 2.0)  # Zoom 2x para mejor calidad
                pix = page.get_pixmap(matrix=mat, clip=rect)
                
                # Convertir a imagen OpenCV
                img_data = pix.tobytes("ppm")
                img_pil = Image.open(io.BytesIO(img_data))
                img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
                
                # Preprocesar imagen para mejor OCR
                gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                
                # Aplicar filtros para mejorar la imagen
                denoised = cv2.fastNlMeansDenoising(gray)
                thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
                
                # Detectar texto con Tesseract
                text = pytesseract.image_to_string(thresh, lang='spa+eng').strip()
                
                if text:
                    self.detected_texts[i] = text
                    detected_count += 1
            
            # Actualizar visualización
            self.update_selection_list()
            self.update_page_display()
            
            # Mostrar resumen en el panel de texto
            if detected_count > 0:
                self.show_detection_summary()
                messagebox.showinfo("Éxito", f"Texto detectado en {detected_count} áreas")
            else:
                messagebox.showwarning("Resultado", "No se detectó texto en ninguna área")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error en la detección de texto: {str(e)}")
    
    def show_detection_summary(self):
        """Mostrar resumen de textos detectados"""
        self.detected_text.config(state=tk.NORMAL)
        self.detected_text.delete(1.0, tk.END)
        
        content = "=== TEXTOS DETECTADOS ===\n\n"
        
        for i in sorted(self.detected_texts.keys()):
            area = self.selected_areas[i]
            content += f"Área {i + 1} (Página {area['page'] + 1}):\n"
            
            # Mostrar texto original con formato preservado
            original_text = self.detected_texts[i]
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
            
            if i in self.translated_texts:
                content += f"Traducción:\n"
                translated_text = self.translated_texts[i]
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
        

        self.detected_text.insert(1.0, content)
        self.detected_text.config(state=tk.DISABLED)

    def translate_all_texts(self):
        """Traducir todos los textos detectados usando DeepSeek API"""
        if not self.api_key:
            messagebox.showwarning("Advertencia", "Configura tu API Key de DeepSeek primero")
            return
        
        if not self.detected_texts:
            messagebox.showwarning("Advertencia", "Detecta texto en las áreas primero")
            return
        
        # Preparar textos para traducir
        texts_to_translate = {}
        for area_index, original_text in self.detected_texts.items():
            if area_index not in self.translated_texts and original_text.strip():
                texts_to_translate[area_index] = original_text
        
        if not texts_to_translate:
            messagebox.showinfo("Información", "Todos los textos ya están traducidos")
            return
        
        # Crear el prompt consolidado
        prompt_content = self.create_translation_prompt(texts_to_translate)
        
        # Mostrar el prompt al usuario
        self.show_translation_prompt(prompt_content, texts_to_translate)
    
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
                            translations[area_index] = translation
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
        """Generar PDF de salida con traducciones sobrepuestas"""
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
                        font_size = min(self.block_font_size, area_height / 3)
                        
                        # Insertar texto traducido con márgenes
                        margin = 3
                        text_rect_width = area_width - (2 * margin)
                        text_rect_height = area_height - (2 * margin)
                        
                        if text_rect_width > 0 and text_rect_height > 0:
                            wrapped_text, adjusted_font_size = self.wrap_text_to_fit(
                                translation, text_rect_width, text_rect_height, font_size
                            )
                            
                            # Crear rectángulo para el texto
                            text_rect = fitz.Rect(x1 + margin, y1 + margin, x2 - margin, y2 - margin)
                            
                            # Insertar texto
                            new_page.insert_textbox(
                                text_rect,
                                wrapped_text,
                                fontsize=adjusted_font_size,
                                color=self.block_text_color,
                                fontname="helv",
                                align=0
                            )
            
            # Guardar documento
            output_doc.save(output_path)
            output_doc.close()
            
            messagebox.showinfo("Éxito", f"PDF traducido guardado en: {output_path}")
            
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
        
        # Calcular tamaño de fuente apropiado
        font_size = min(self.block_font_size, int(area_height / 4))
        font_size = max(8, font_size)  # Mínimo 8pt
        
        # Ajustar texto al área
        margin = 4
        text_width = area_width - (2 * margin)
        text_height = area_height - (2 * margin)
        
        if text_width <= 0 or text_height <= 0:
            return
        
        # Preparar texto ajustado
        wrapped_text, adjusted_font_size = self.wrap_text_for_canvas(
            translated_text, text_width, text_height, font_size
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
            font=("Arial", adjusted_font_size),
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
        """Ajustar texto para el canvas"""
        import tkinter.font as tkFont
        
        # Crear fuente para medición
        font = tkFont.Font(family="Arial", size=font_size)
        
        # Dividir en líneas
        lines = []
        for paragraph in text.split('|||'):
            if not paragraph.strip():
                lines.append('')
                continue
                
            words = paragraph.split()
            current_line = []
            
            for word in words:
                # Probar agregar la palabra
                test_line = current_line + [word]
                test_text = ' '.join(test_line)
                text_width = font.measure(test_text)
                
                if text_width <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        lines.append(word)
            
            if current_line:
                lines.append(' '.join(current_line))
        
        # Verificar altura total
        line_height = font.metrics('linespace')
        total_height = len(lines) * line_height
        
        # Ajustar tamaño de fuente si es necesario
        while total_height > max_height and font_size > 8:
            font_size -= 1
            font = tkFont.Font(family="Arial", size=font_size)
            line_height = font.metrics('linespace')
            total_height = len(lines) * line_height
        
        return '\n'.join(lines), font_size
    
    def edit_translated_text(self, area_index):
        """Abrir editor para texto traducido"""
        if area_index not in self.translated_texts:
            return
        
        # Crear ventana de edición
        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"Editar Traducción - Área {area_index + 1}")
        edit_window.geometry("600x400")
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
        
        # Texto traducido (editable)
        ttk.Label(main_frame, text="Traducción:").pack(anchor=tk.W)
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
        
        def save_changes():
            new_text = text_edit.get(1.0, tk.END).strip()
            if new_text:
                self.translated_texts[area_index] = new_text
                self.update_page_display()
                self.show_detection_summary()
            edit_window.destroy()
        
        def cancel_edit():
            edit_window.destroy()
        
        ttk.Button(button_frame, text="Guardar", command=save_changes).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Cancelar", command=cancel_edit).pack(side=tk.RIGHT)

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
        
        # Asegurar que las coordenadas estén en orden correcto
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1
        
        # Verificar tamaño mínimo
        if abs(x2 - x1) < 20 or abs(y2 - y1) < 20:
            return
        
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
        
        # Primero, verificar si el texto tiene saltos de línea originales
        original_lines = text.split('\n')
        
        # Si el texto original tiene múltiples líneas, preservar la estructura
        if len(original_lines) > 1:
            return self._fit_multiline_text(original_lines, rect_width, rect_height, font_size)
        
        # Si es una sola línea, usar el método de ajuste automático por palabras
        return self._fit_single_line_text(text, rect_width, rect_height, font_size)
    
    def _fit_multiline_text(self, original_lines, rect_width, rect_height, font_size):
        """Ajustar texto que ya tiene múltiples líneas preservando la estructura original"""
        # Limpiar líneas vacías del inicio y final, pero preservar las intermedias
        while original_lines and not original_lines[0].strip():
            original_lines.pop(0)
        while original_lines and not original_lines[-1].strip():
            original_lines.pop()
        
        if not original_lines:
            return "", font_size
        
        # Probar diferentes tamaños de fuente
        for test_font_size in [font_size, font_size * 0.9, font_size * 0.8, font_size * 0.7, font_size * 0.6, font_size * 0.5]:
            char_width = test_font_size * 0.55
            line_height = test_font_size * 1.2
            
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
            
            if total_height <= rect_height - 6:
                return "\n".join(adjusted_lines), test_font_size
        
        # Si nada funciona, usar el tamaño más pequeño
        return "\n".join(original_lines), font_size * 0.4
    
    def _fit_single_line_text(self, text, rect_width, rect_height, font_size):
        """Ajustar texto de una sola línea con saltos automáticos por palabras"""
        words = text.split()
        if not words:
            return text, font_size
        
        # Probar diferentes tamaños de fuente si es necesario
        for test_font_size in [font_size, font_size * 0.9, font_size * 0.8, font_size * 0.7, font_size * 0.6]:
            lines = []
            current_line = []
            
            # Estimar ancho promedio de carácter
            char_width = test_font_size * 0.55
            
            for word in words:
                # Probar agregar la palabra a la línea actual
                test_line = current_line + [word]
                test_text = " ".join(test_line)
                
                # Estimar el ancho del texto
                estimated_width = len(test_text) * char_width
                
                if estimated_width <= rect_width - 6:  # Dejar margen de 3px a cada lado
                    current_line = test_line
                else:
                    # La línea no cabe, guardar la anterior y empezar nueva
                    if current_line:
                        lines.append(" ".join(current_line))
                        current_line = [word]
                    else:
                        # Incluso una palabra sola no cabe, dividirla
                        if len(word) > 15:
                            chars_per_line = max(1, int((rect_width - 6) / char_width))
                            for i in range(0, len(word), chars_per_line):
                                chunk = word[i:i+chars_per_line]
                                if i + chars_per_line < len(word):
                                    chunk += "-"
                                lines.append(chunk)
                        else:
                            lines.append(word)
            
            # Agregar la última línea
            if current_line:
                lines.append(" ".join(current_line))
            
            # Verificar si todas las líneas caben en la altura
            line_height = test_font_size * 1.2  # Factor de espaciado entre líneas reducido
            total_height = len(lines) * line_height
            
            if total_height <= rect_height - 6:  # Dejar margen de 3px arriba y abajo
                return "\n".join(lines), test_font_size
        
        # Si nada funciona, usar el texto original con el tamaño más pequeño y dividir por líneas
        min_font_size = font_size * 0.4
        char_width = min_font_size * 0.55
        chars_per_line = max(1, int((rect_width - 6) / char_width))
        
        # Dividir texto en líneas de longitud fija si no hay otra opción
        lines = []
        remaining_text = text
        while remaining_text:
            if len(remaining_text) <= chars_per_line:
                lines.append(remaining_text)
                break
            else:
                # Buscar un espacio cerca del final de la línea
                cut_point = chars_per_line
                while cut_point > 0 and remaining_text[cut_point] != ' ':
                    cut_point -= 1
                
                if cut_point == 0:  # No se encontró espacio, cortar en seco
                    cut_point = chars_per_line
                
                lines.append(remaining_text[:cut_point])
                remaining_text = remaining_text[cut_point:].lstrip()
        
        return "\n".join(lines), min_font_size


if __name__ == "__main__":
    app = PDFViewer()
    app.root.mainloop()
