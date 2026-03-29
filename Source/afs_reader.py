"""
Módulo para lectura de archivos AFS (formato usado en juegos de PS2)
Soporta firmas: 0x41465300 y 0x534641
"""
import struct
import os

class AFSReader:
    """Clase para leer archivos AFS (formato usado en juegos de PS2)"""
    
    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        self.data = data
        self.filename = filename
        self.parent_iso = parent_iso
        self.parent_path = parent_path
        self.entries = []
        self.name_table_offset = 0
        self.file_count = 0
        self.load_afs()
        
    def load_afs(self):
        """Cargar y parsear el archivo AFS"""
        try:
            # Verificar firma AFS
            if len(self.data) < 4:
                print(f"Archivo demasiado pequeño para ser AFS")
                return
                
            # Leer firma (puede ser 0x41465300 o 0x534641)
            signature = struct.unpack('<I', self.data[0:4])[0]
            signature_hex = hex(signature)
            
            # AFS puede tener dos firmas diferentes
            if signature != 0x41465300 and signature != 0x534641:
                print(f"Firma AFS no válida: {signature_hex}")
                return
                
            print(f"Firma AFS válida encontrada: {signature_hex}")
                
            # Leer número de archivos
            self.file_count = struct.unpack('<I', self.data[4:8])[0]
            print(f"Número de archivos en AFS: {self.file_count}")
            
            # Leer tabla de offsets y tamaños
            offset_table_start = 8
            self.entries = []
            
            for i in range(self.file_count):
                offset_pos = offset_table_start + i * 8
                size_pos = offset_table_start + i * 8 + 4
                
                if offset_pos + 8 > len(self.data):
                    print(f"Tabla de offsets incompleta en índice {i}")
                    break
                    
                offset = struct.unpack('<I', self.data[offset_pos:offset_pos + 4])[0]
                size = struct.unpack('<I', self.data[size_pos:size_pos + 4])[0]
                
                self.entries.append({
                    'offset': offset,
                    'size': size,
                    'name': f"file_{i:04d}.bin",
                    'index': i
                })
            
            # Leer tabla de nombres (si existe)
            name_table_pos = offset_table_start + self.file_count * 8
            if name_table_pos + 8 <= len(self.data):
                self.name_table_offset = struct.unpack('<I', self.data[name_table_pos:name_table_pos + 4])[0]
                name_table_size = struct.unpack('<I', self.data[name_table_pos + 4:name_table_pos + 8])[0]
                
                if self.name_table_offset > 0 and self.name_table_offset + name_table_size <= len(self.data):
                    print(f"Tabla de nombres encontrada en offset {self.name_table_offset}")
                    # Leer nombres (cada nombre tiene 0x30 bytes = 48 caracteres)
                    for i in range(min(self.file_count, len(self.entries))):
                        name_offset = self.name_table_offset + i * 0x30
                        if name_offset + 0x30 <= len(self.data):
                            name_data = self.data[name_offset:name_offset + 0x30]
                            # Buscar el primer byte nulo
                            name_end = name_data.find(b'\x00')
                            if name_end > 0:
                                name = name_data[:name_end].decode('shift-jis', errors='ignore')
                            else:
                                name = name_data.decode('shift-jis', errors='ignore').strip('\x00')
                            
                            if name:
                                self.entries[i]['name'] = name
                                
            print(f"AFS cargado correctamente con {len(self.entries)} archivos")
                                
        except Exception as e:
            print(f"Error cargando archivo AFS: {e}")
            import traceback
            traceback.print_exc()
            
    def get_entries(self):
        """Obtener lista de entradas"""
        return self.entries
        
    def extract_file(self, index, output_path):
        """Extraer un archivo específico del AFS"""
        if index < 0 or index >= len(self.entries):
            return False
            
        entry = self.entries[index]
        start = entry['offset']
        size = entry['size']
        
        if start + size <= len(self.data):
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
