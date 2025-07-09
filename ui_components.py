"""
Módulo de componentes de interfaz gráfica para PDFTools
Contiene todas las funciones de configuración de UI
"""

import tkinter as tk
from tkinter import ttk, messagebox


class UIComponents:
    """Clase para manejar componentes de la interfaz gráfica"""
    
    def __init__(self):
        self.app = None
    
    def setup_left_panel(self, parent, app):
        """Configurar panel izquierdo"""
        # Grupo: Cargar archivo
        file_group = ttk.LabelFrame(parent, text="Archivo", padding=10)
        file_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(file_group, text="Cargar PDF", command=app.load_pdf).pack(fill=tk.X)
        
        # Grupo: Navegación
        nav_group = ttk.LabelFrame(parent, text="Navegación", padding=10)
        nav_group.pack(fill=tk.X, pady=(0, 10))
        
        nav_frame = ttk.Frame(nav_group)
        nav_frame.pack(fill=tk.X)
        
        ttk.Button(nav_frame, text="◀", command=app.prev_page, width=3).pack(side=tk.LEFT)
        
        app.page_var = tk.StringVar(value="0 / 0")
        ttk.Label(nav_frame, textvariable=app.page_var).pack(side=tk.LEFT, padx=10, expand=True)
        
        ttk.Button(nav_frame, text="▶", command=app.next_page, width=3).pack(side=tk.RIGHT)
        
        # Controles de rotación
        rotation_frame = ttk.Frame(nav_group)
        rotation_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(rotation_frame, text="Rotar:").pack(side=tk.LEFT)
        ttk.Button(rotation_frame, text="↶", command=app.rotate_left, width=3).pack(side=tk.LEFT, padx=(5, 2))
        ttk.Button(rotation_frame, text="↷", command=app.rotate_right, width=3).pack(side=tk.LEFT, padx=2)
        ttk.Button(rotation_frame, text="↺", command=app.reset_rotation, width=3).pack(side=tk.LEFT, padx=(2, 0))
        
        # Grupo: Zoom
        zoom_group = ttk.LabelFrame(parent, text="Zoom", padding=10)
        zoom_group.pack(fill=tk.X, pady=(0, 10))
        
        zoom_frame = ttk.Frame(zoom_group)
        zoom_frame.pack(fill=tk.X)
        
        ttk.Button(zoom_frame, text="-", command=app.zoom_out, width=3).pack(side=tk.LEFT)
        
        app.zoom_var = tk.StringVar(value="100%")
        ttk.Label(zoom_frame, textvariable=app.zoom_var).pack(side=tk.LEFT, padx=10, expand=True)
        
        ttk.Button(zoom_frame, text="+", command=app.zoom_in, width=3).pack(side=tk.RIGHT)
        
        # Grupo: Áreas seleccionadas
        areas_group = ttk.LabelFrame(parent, text="Áreas Seleccionadas", padding=10)
        areas_group.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Lista de áreas
        list_frame = ttk.Frame(areas_group)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        app.selection_listbox = tk.Listbox(list_frame, height=8)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=app.selection_listbox.yview)
        app.selection_listbox.config(yscrollcommand=scrollbar.set)
        
        app.selection_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind para mostrar texto del área seleccionada
        app.selection_listbox.bind("<Button-1>", app.on_area_selection)
        
        # Botones de control de áreas
        area_buttons = ttk.Frame(areas_group)
        area_buttons.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(area_buttons, text="Editar", command=app.toggle_edit_mode, width=8).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(area_buttons, text="Eliminar", command=app.delete_selected_area, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(area_buttons, text="Limpiar", command=app.clear_selections, width=8).pack(side=tk.RIGHT)
        
        # Controles de ajuste en modo edición
        edit_controls = ttk.LabelFrame(areas_group, text="Ajustes de Área (Modo Edición)", padding=5)
        edit_controls.pack(fill=tk.X, pady=(5, 0))
        
        # Ajustes horizontales
        h_adjust_frame = ttk.Frame(edit_controls)
        h_adjust_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(h_adjust_frame, text="Ajuste H:").pack(side=tk.LEFT)
        ttk.Button(h_adjust_frame, text="◀", command=lambda: app.adjust_selected_area('left'), width=3).pack(side=tk.LEFT, padx=2)
        ttk.Button(h_adjust_frame, text="▶", command=lambda: app.adjust_selected_area('right'), width=3).pack(side=tk.LEFT, padx=2)
        
        # Rotación
        ttk.Label(h_adjust_frame, text="Rotar:").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(h_adjust_frame, text="↺", command=lambda: app.rotate_selected_area(-90), width=3).pack(side=tk.LEFT, padx=2)
        ttk.Button(h_adjust_frame, text="↻", command=lambda: app.rotate_selected_area(90), width=3).pack(side=tk.LEFT, padx=2)
        
        # Grupo: Procesamiento
        process_group = ttk.LabelFrame(parent, text="Procesamiento", padding=10)
        process_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(process_group, text="Detectar Texto", command=app.detect_text_in_areas).pack(fill=tk.X, pady=(0, 5))
        ttk.Button(process_group, text="Auto-Detectar Texto", command=app.auto_detect_text_areas).pack(fill=tk.X, pady=(0, 5))
        ttk.Button(process_group, text="Consolidar Bloques", command=app.consolidate_blocks_by_proximity).pack(fill=tk.X, pady=(0, 5))
        ttk.Button(process_group, text="Traducir Todo", command=app.translate_all_texts).pack(fill=tk.X, pady=(0, 5))
        
        # Checkbox para vista previa de traducción
        app.show_translation_preview = tk.BooleanVar(value=True)
        ttk.Checkbutton(process_group, text="Vista previa de traducción", 
                       variable=app.show_translation_preview,
                       command=app.update_page_display).pack(anchor=tk.W, pady=(5, 0))
        
        # Etiqueta informativa
        info_label = ttk.Label(process_group, text="💡 Doble-clic en texto traducido para editar", 
                              font=("Arial", 8), foreground="gray")
        info_label.pack(anchor=tk.W, pady=(2, 5))
        
        ttk.Button(process_group, text="Generar PDF", command=app.generate_output_pdf).pack(fill=tk.X)
    
    def setup_center_panel(self, parent, app):
        """Configurar panel central"""
        # Frame para el canvas con scrollbars
        canvas_frame = ttk.Frame(parent)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Crear canvas con scrollbars
        app.canvas = tk.Canvas(canvas_frame, bg="white")
        
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=app.canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=app.canvas.xview)
        
        app.canvas.config(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack scrollbars y canvas
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        app.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bind eventos del canvas
        app.canvas.bind("<Button-1>", app.on_canvas_click)
        app.canvas.bind("<B1-Motion>", app.on_canvas_drag)
        app.canvas.bind("<ButtonRelease-1>", app.on_canvas_release)
        app.canvas.bind("<Double-Button-1>", app.on_canvas_double_click)
        
        # Bind para teclas (para eliminar con Delete)
        app.canvas.bind("<KeyPress>", app.on_key_press)
        app.canvas.focus_set()  # Permitir que el canvas reciba eventos de teclado
        
        # Panel de texto detectado
        text_frame = ttk.LabelFrame(parent, text="Texto Detectado", padding=5)
        text_frame.pack(fill=tk.X, pady=(5, 0))
        
        text_container = ttk.Frame(text_frame)
        text_container.pack(fill=tk.BOTH, expand=True)
        
        app.detected_text = tk.Text(text_container, height=6, wrap=tk.WORD, state=tk.DISABLED)
        text_scrollbar = ttk.Scrollbar(text_container, orient=tk.VERTICAL, command=app.detected_text.yview)
        app.detected_text.config(yscrollcommand=text_scrollbar.set)
        
        app.detected_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def setup_right_panel(self, parent, app):
        """Configurar panel derecho para configuraciones"""
        # Grupo: Control Global de Fuente
        font_group = ttk.LabelFrame(parent, text="Tamaño de Fuente Global", padding=10)
        font_group.pack(fill=tk.X, pady=(0, 10))
        
        font_frame = ttk.Frame(font_group)
        font_frame.pack(fill=tk.X)
        
        ttk.Label(font_frame, text="Tamaño:").pack(side=tk.LEFT)
        
        app.global_font_var = tk.IntVar(value=app.global_font_size)
        font_spinbox = ttk.Spinbox(font_frame, from_=8, to=72, width=6, textvariable=app.global_font_var,
                                   command=lambda: app.on_global_font_change())
        font_spinbox.pack(side=tk.LEFT, padx=(5, 10))
        
        # Bind para detectar cambios manuales en el Spinbox
        font_spinbox.bind('<KeyRelease>', lambda e: app.root.after(100, app.on_global_font_change))
        font_spinbox.bind('<FocusOut>', lambda e: app.on_global_font_change())
        
        ttk.Button(font_frame, text="Aplicar a Todo", 
                  command=app.apply_global_font_to_all,
                  style="Accent.TButton").pack(side=tk.RIGHT)
        
        # Información del control
        info_label = ttk.Label(font_group, text="Cambia el tamaño de fuente por defecto.\n'Aplicar a Todo' actualiza todas las áreas existentes.", 
                              font=("Segoe UI", 8), foreground="gray")
        info_label.pack(pady=(5, 0))
        
        # Grupo: API Configuration
        api_group = ttk.LabelFrame(parent, text="Configuración API", padding=10)
        api_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(api_group, text="DeepSeek API Key:").pack(anchor=tk.W)
        app.api_key_var = tk.StringVar(value=app.api_key)
        api_entry = ttk.Entry(api_group, textvariable=app.api_key_var, show="*")
        api_entry.pack(fill=tk.X, pady=(2, 5))
        
        ttk.Button(api_group, text="Guardar API Key", command=app.save_api_key).pack(fill=tk.X)
        
        # Estilo de bloque traducido
        style_group = ttk.LabelFrame(parent, text="Estilo de Bloque Traducido", padding=10)
        style_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(style_group, text="Configurar Estilo...", command=app.show_block_style_modal).pack(fill=tk.X)
        
        # Grupo: Guardar Configuración
        save_group = ttk.LabelFrame(parent, text="Guardar Configuración", padding=10)
        save_group.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(save_group, text="Nombre:").pack(anchor=tk.W)
        app.config_name_var = tk.StringVar()
        ttk.Entry(save_group, textvariable=app.config_name_var).pack(fill=tk.X, pady=(2, 5))
        
        ttk.Button(save_group, text="Guardar", command=app.save_configuration).pack(fill=tk.X)
        
        # Grupo: Configuraciones Guardadas
        configs_group = ttk.LabelFrame(parent, text="Configuraciones Guardadas", padding=10)
        configs_group.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Lista de configuraciones
        config_list_frame = ttk.Frame(configs_group)
        config_list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        app.config_listbox = tk.Listbox(config_list_frame, height=6)
        config_scrollbar = ttk.Scrollbar(config_list_frame, orient=tk.VERTICAL, command=app.config_listbox.yview)
        app.config_listbox.config(yscrollcommand=config_scrollbar.set)
        
        app.config_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        config_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Botones de configuraciones
        config_buttons_frame = ttk.Frame(configs_group)
        config_buttons_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(config_buttons_frame, text="Cargar", command=app.load_selected_configuration, width=10).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(config_buttons_frame, text="Eliminar", command=app.delete_configuration, width=10).pack(side=tk.LEFT, padx=2)
        
        config_buttons_frame2 = ttk.Frame(configs_group)
        config_buttons_frame2.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(config_buttons_frame2, text="Exportar", command=app.export_configuration, width=10).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(config_buttons_frame2, text="Importar", command=app.import_configuration, width=10).pack(side=tk.LEFT, padx=2)
        
        # Información de configuración
        info_group = ttk.LabelFrame(parent, text="Información", padding=10)
        info_group.pack(fill=tk.X)
        
        app.config_info_text = tk.Text(info_group, height=4, wrap=tk.WORD, state=tk.DISABLED)
        info_scrollbar = ttk.Scrollbar(info_group, orient=tk.VERTICAL, command=app.config_info_text.yview)
        app.config_info_text.config(yscrollcommand=info_scrollbar.set)
        
        app.config_info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        info_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Cargar configuraciones guardadas al inicializar
        app.load_saved_configurations()
