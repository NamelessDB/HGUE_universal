"""
Módulo para lectura de archivos MFA (Silent Hill 2/3 PS2)
Formato usado en juegos de Silent Hill
"""
import struct
import os

class MFAReader:
    """Clase para leer archivos MFA de Silent Hill 2/3"""
    
    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        self.data = data
        self.filename = filename
        self.parent_iso = parent_iso
        self.parent_path = parent_path
        self.entries = []
        self.blocks = []
        self.load_mfa()
        
    def load_mfa(self):
        """Cargar y parsear el archivo MFA"""
        try:
            if len(self.data) < 0x100:
                print(f"Archivo demasiado pequeño para ser MFA")
                return
            
            # Determinar offset inicial (0xB8 o 0xD8 según la estructura)
            # Similar al script Python original
            offs = 0xB8 if self.data[0x60] == 0x4E else 0xD8
            
            print(f"Iniciando parseo MFA en offset 0x{offs:X}")
            
            block_index = -1
            block_offs = 0
            total_files = 0
            
            while offs < len(self.data):
                block_index += 1
                
                # Leer número de archivos en este bloque
                if offs + 4 > len(self.data):
                    break
                    
                num_files = struct.unpack('<i', self.data[offs:offs+4])[0]
                
                if num_files < 0:
                    print(f"  Número de archivos negativo en bloque {block_index}")
                    break
                
                if num_files == 0:
                    break
                    
                # Leer tamaño total del bloque
                total_bytesize = struct.unpack('<I', self.data[offs+4:offs+8])[0]
                
                print(f"\nBloque {block_index}: {num_files} archivos, tamaño total: {total_bytesize} bytes")
                
                # Leer cada archivo en el bloque
                for i in range(num_files):
                    entry_offs = offs + i * 0x10 + 0x8
                    
                    if entry_offs + 0x10 > len(self.data):
                        break
                    
                    # Leer offset del nombre
                    name_offs = struct.unpack('<I', self.data[entry_offs:entry_offs+4])[0] + block_offs
                    
                    # Leer offset de datos
                    data_offs = struct.unpack('<I', self.data[entry_offs+4:entry_offs+8])[0] + block_offs + 0x800
                    
                    # Leer flags (opcional)
                    # flags = struct.unpack('<I', self.data[entry_offs+8:entry_offs+12])[0]
                    
                    # Leer tamaño de datos
                    data_size = struct.unpack('<I', self.data[entry_offs+12:entry_offs+16])[0]
                    
                    # Leer nombre del archivo
                    filename = self._read_filename(name_offs)
                    
                    if not filename:
                        filename = f"_unnamed_{i:04d}_{block_index:04d}.bin"
                    
                    # Asegurar que data_offs y data_size sean válidos
                    if data_offs + data_size <= len(self.data):
                        self.entries.append({
                            'offset': data_offs,
                            'size': data_size,
                            'name': filename,
                            'index': total_files,
                            'block': block_index,
                            'full_path': filename,
                            'relative_path': filename
                        })
                        total_files += 1
                        print(f"  Archivo {i:04d}: {filename} ({data_size} bytes)")
                    else:
                        print(f"  Archivo {i:04d}: {filename} - TAMAÑO INVÁLIDO (ignorado)")
                
                # Avanzar al siguiente bloque
                block_offs += total_bytesize + 0x800
                offs = block_offs + 0x8
                
                # Seguridad: evitar loop infinito
                if offs >= len(self.data) or block_offs >= len(self.data):
                    break
            
            print(f"\n✅ MFA cargado correctamente con {len(self.entries)} archivos en {block_index + 1} bloques")
            
        except Exception as e:
            print(f"Error cargando archivo MFA: {e}")
            import traceback
            traceback.print_exc()
    
    def _read_filename(self, offset):
        """Leer nombre de archivo desde offset"""
        if offset >= len(self.data):
            return None
            
        # Buscar byte nulo
        end = offset
        while end < len(self.data) and self.data[end] != 0:
            end += 1
            if end - offset > 256:  # Límite de seguridad
                break
        
        if end > offset:
            try:
                name = self.data[offset:end].decode('ascii', errors='replace').strip()
                return name
            except:
                return None
        return None
    
    def get_entries(self):
        """Obtener lista de entradas"""
        return self.entries
        
    def extract_file(self, index, output_path):
        """Extraer un archivo específico del MFA"""
        if index < 0 or index >= len(self.entries):
            return False
            
        entry = self.entries[index]
        start = entry['offset']
        size = entry['size']
        
        if start + size <= len(self.data):
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as f:
                f.write(self.data[start:start + size])
            return True
            
        return False
        
    def get_file_data(self, index):
        """Obtener datos de un archivo específico"""
        if index < 0 or index >= len(self.entries):
            return None
            
        entry = self.entries[index]
        start = entry['offset']
        size = entry['size']
        
        if start + size <= len(self.data):
            return self.data[start:start + size]
            
        return None
