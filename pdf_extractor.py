import tkinter as tk
from tkinter import messagebox
import fitz  # PyMuPDF
from pdf_viewer import PDFViewer

class PDFExtractor(PDFViewer):
    """Extensión del visor de PDF que permite extraer contenido de las áreas seleccionadas"""
    
    def __init__(self, root):
        super().__init__(root)
        self.root.title("PDF Viewer - Extractor de Contenido")
        self.add_extraction_controls()
    
    def add_extraction_controls(self):
        """Agregar controles para extracción de contenido"""
        # Frame para controles de extracción
        extract_frame = tk.Frame(self.root)
        extract_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Button(extract_frame, text="Extraer Texto", 
                 command=self.extract_text_from_selections,
                 bg="#4CAF50", fg="white").pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Button(extract_frame, text="Extraer Imágenes", 
                 command=self.extract_images_from_selections,
                 bg="#2196F3", fg="white").pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Button(extract_frame, text="Guardar Coordenadas", 
                 command=self.save_coordinates,
                 bg="#FF9800", fg="white").pack(side=tk.LEFT, padx=(0, 5))
        
        # Área de texto para mostrar resultados
        self.result_text = tk.Text(self.root, height=8, wrap=tk.WORD)
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Scrollbar para el área de texto
        scrollbar = tk.Scrollbar(self.result_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.result_text.yview)
    
    def extract_text_from_selections(self):
        """Extraer texto de las áreas seleccionadas"""
        if not self.pdf_document or not self.selected_areas:
            messagebox.showwarning("Advertencia", "No hay PDF cargado o áreas seleccionadas")
            return
        
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, "=== TEXTO EXTRAÍDO ===\n\n")
        
        for i, selection in enumerate(self.selected_areas):
            page_num = selection['page']
            pdf_coords = selection['pdf_coords']
            
            # Obtener la página
            page = self.pdf_document[page_num]
            
            # Crear rectángulo para la extracción
            rect = fitz.Rect(pdf_coords[0], pdf_coords[1], pdf_coords[2], pdf_coords[3])
            
            # Extraer texto del área
            text = page.get_text("text", clip=rect)
            
            self.result_text.insert(tk.END, f"--- Área {i+1} (Página {page_num + 1}) ---\n")
            self.result_text.insert(tk.END, f"{text}\n\n")
        
        messagebox.showinfo("Éxito", "Texto extraído y mostrado en el área de resultados")
    
    def extract_images_from_selections(self):
        """Extraer información de imágenes de las áreas seleccionadas"""
        if not self.pdf_document or not self.selected_areas:
            messagebox.showwarning("Advertencia", "No hay PDF cargado o áreas seleccionadas")
            return
        
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, "=== IMÁGENES ENCONTRADAS ===\n\n")
        
        total_images = 0
        
        for i, selection in enumerate(self.selected_areas):
            page_num = selection['page']
            pdf_coords = selection['pdf_coords']
            
            # Obtener la página
            page = self.pdf_document[page_num]
            
            # Crear rectángulo para la búsqueda
            rect = fitz.Rect(pdf_coords[0], pdf_coords[1], pdf_coords[2], pdf_coords[3])
            
            # Obtener imágenes en el área
            image_list = page.get_images()
            
            self.result_text.insert(tk.END, f"--- Área {i+1} (Página {page_num + 1}) ---\n")
            
            area_images = 0
            for img_index, img in enumerate(image_list):
                # Obtener la matriz de transformación de la imagen
                try:
                    img_rect = page.get_image_bbox(img)
                    # Verificar si la imagen intersecta con el área seleccionada
                    if rect.intersects(img_rect):
                        area_images += 1
                        total_images += 1
                        xref = img[0]
                        pix = fitz.Pixmap(self.pdf_document, xref)
                        
                        if pix.n - pix.alpha < 4:  # GRAY o RGB
                            self.result_text.insert(tk.END, 
                                f"  Imagen {area_images}: {pix.width}x{pix.height} pixels, "
                                f"{'RGB' if pix.n == 4 else 'GRAY'}\n")
                        else:
                            self.result_text.insert(tk.END, 
                                f"  Imagen {area_images}: {pix.width}x{pix.height} pixels, CMYK\n")
                        
                        pix = None  # Liberar memoria
                except:
                    continue
            
            if area_images == 0:
                self.result_text.insert(tk.END, "  No se encontraron imágenes en esta área\n")
            
            self.result_text.insert(tk.END, "\n")
        
        self.result_text.insert(tk.END, f"Total de imágenes encontradas: {total_images}\n")
        messagebox.showinfo("Éxito", f"Se encontraron {total_images} imágenes en las áreas seleccionadas")
    
    def save_coordinates(self):
        """Guardar las coordenadas de las áreas seleccionadas en un archivo"""
        if not self.selected_areas:
            messagebox.showwarning("Advertencia", "No hay áreas seleccionadas")
            return
        
        from tkinter import filedialog
        
        file_path = filedialog.asksaveasfilename(
            title="Guardar coordenadas",
            defaultextension=".txt",
            filetypes=[("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("=== COORDENADAS DE ÁREAS SELECCIONADAS ===\n\n")
                    
                    for i, selection in enumerate(self.selected_areas):
                        page_num = selection['page']
                        pdf_coords = selection['pdf_coords']
                        
                        f.write(f"Área {i+1}:\n")
                        f.write(f"  Página: {page_num + 1}\n")
                        f.write(f"  Coordenadas PDF (x1, y1, x2, y2): {pdf_coords}\n")
                        f.write(f"  Ancho: {pdf_coords[2] - pdf_coords[0]:.2f} puntos\n")
                        f.write(f"  Alto: {pdf_coords[3] - pdf_coords[1]:.2f} puntos\n")
                        f.write("\n")
                
                messagebox.showinfo("Éxito", f"Coordenadas guardadas en {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar el archivo: {str(e)}")

def main():
    root = tk.Tk()
    app = PDFExtractor(root)
    root.mainloop()

if __name__ == "__main__":
    main()
