"""
Módulo para lectura de archivos RTPK/RPK (Rapid Pack - formato de empaquetado)
Soporta versiones 0x200 (solo offsets) y 0x300 (sizes + offsets)
"""
import struct
import os

class RTPKReader:
    """Clase para leer archivos RTPK (Rapid Pack - formato de empaquetado)"""
    
    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        self.data = data
        self.filename = filename
        self.parent_iso = parent_iso
        self.parent_path = parent_path
        self.entries = []
        self.version = 0
        self.alignment = 0
        self.file_count = 0
        self.string_table_size = 0
        self.file_tree = {}
        self.load_rtpk()
        
    def load_rtpk(self):
        """Cargar y parsear el archivo RTPK"""
        try:
            if len(self.data) < 0x14:
                print(f"Archivo demasiado pequeño para ser RTPK")
                return
                
            # Verificar firma "RTPK" (52 54 50 4B)
            signature_bytes = self.data[0:4]
            signature_str = signature_bytes.decode('ascii', errors='ignore')
            
            print(f"Firma encontrada: {signature_bytes.hex()} = '{signature_str}'")
            
            if signature_str != "RTPK":
                print(f"Firma RTPK no válida: {signature_bytes.hex()} = '{signature_str}'")
                return
                
            print(f"✅ Firma RTPK válida encontrada: {signature_str}")
            
            # Leer cabecera
            unknown = struct.unpack('<I', self.data[4:8])[0]
            self.version = struct.unpack('<I', self.data[8:12])[0]
            self.alignment = struct.unpack('<H', self.data[12:14])[0]
            self.file_count = struct.unpack('<H', self.data[14:16])[0]
            self.string_table_size = struct.unpack('<I', self.data[16:20])[0]
            
            version_type = (self.version & 0xF00)
            print(f"RTPK Info:")
            print(f"  Version: {hex(self.version)}")
            print(f"  Files: {self.file_count}")
            print(f"  Alignment: {self.alignment}")
            print(f"  String Table Size: {self.string_table_size}")
            print(f"  Type: {'offsets only (0x200)' if version_type == 0x200 else 'sizes+offsets (0x300)'}")
            
            if self.file_count == 0 or self.file_count > 10000:
                print(f"⚠️ Número de archivos sospechoso: {self.file_count}")
                return
            
            # Leer tabla de offsets/tamaños
            offset_table_start = 0x20
            entry_size = 4 if version_type == 0x200 else 8
            
            if version_type == 0x200:
                self._parse_offsets_mode(offset_table_start)
            else:
                self._parse_sizes_offsets_mode(offset_table_start)
            
            # Leer tabla de nombres
            string_table_pos = offset_table_start + (self.file_count * entry_size)
            if string_table_pos < len(self.data):
                self._parse_names(string_table_pos)
            
            # Construir árbol de directorios
            self._build_directory_tree()
            
            print(f"✅ RTPK cargado correctamente con {len(self.entries)} archivos")
            if self.file_tree:
                print(f"✅ Estructura de directorios creada")
                
        except Exception as e:
            print(f"❌ Error cargando RTPK: {e}")
            import traceback
            traceback.print_exc()
    
    def _parse_offsets_mode(self, start_pos):
        """Parsear modo offsets (versión 0x200)"""
        print(f"Modo offsets: leyendo {self.file_count} offsets desde 0x{start_pos:X}")
        offsets = []
        
        for i in range(self.file_count):
            pos = start_pos + i * 4
            if pos + 4 <= len(self.data):
                offset = struct.unpack('<I', self.data[pos:pos+4])[0]
                offsets.append(offset)
                print(f"  Offset[{i}]: 0x{offset:X}")
            else:
                offsets.append(0)
        
        # Calcular tamaños
        for i in range(self.file_count):
            start = offsets[i]
            if i < self.file_count - 1:
                end = offsets[i + 1]
            else:
                end = len(self.data)
            
            size = end - start
            if size > 0:
                self.entries.append({
                    'offset': start,
                    'size': size,
                    'name': f"file_{i:04d}.bin",
                    'index': i,
                    'full_path': f"file_{i:04d}.bin"
                })
    
    def _parse_sizes_offsets_mode(self, start_pos):
        """Parsear modo sizes+offsets (versión 0x300)"""
        print(f"Modo sizes+offsets: leyendo {self.file_count} archivos")
        sizes = []
        offsets = []
        
        # Leer tamaños
        for i in range(self.file_count):
            pos = start_pos + i * 4
            if pos + 4 <= len(self.data):
                size = struct.unpack('<I', self.data[pos:pos+4])[0]
                sizes.append(size)
                print(f"  Size[{i}]: {size} bytes")
            else:
                sizes.append(0)
        
        # Leer offsets
        offset_start = start_pos + self.file_count * 4
        for i in range(self.file_count):
            pos = offset_start + i * 4
            if pos + 4 <= len(self.data):
                offset = struct.unpack('<I', self.data[pos:pos+4])[0]
                offsets.append(offset)
                print(f"  Offset[{i}]: 0x{offset:X}")
            else:
                offsets.append(0)
        
        # Crear entradas
        for i in range(self.file_count):
            if offsets[i] != 0 and sizes[i] > 0:
                self.entries.append({
                    'offset': offsets[i],
                    'size': sizes[i],
                    'name': f"file_{i:04d}.bin",
                    'index': i,
                    'full_path': f"file_{i:04d}.bin"
                })
    
    def _parse_names(self, pos):
        """Parsear nombres de archivos con rutas completas"""
        try:
            print(f"Parseando nombres desde posición 0x{pos:X}")
            remaining = self.data[pos:]
            names_list = []
            current_pos = 0
            
            while len(names_list) < self.file_count and current_pos < len(remaining):
                end = remaining.find(b'\x00', current_pos)
                if end == -1:
                    break
                
                name = remaining[current_pos:end].decode('utf-8', errors='ignore')
                if name:
                    names_list.append(name)
                    print(f"  Nombre encontrado: {name}")
                current_pos = end + 1
            
            print(f"Total nombres encontrados: {len(names_list)}")
            
            # Asignar nombres
            for i, name in enumerate(names_list):
                if i < len(self.entries):
                    if name.startswith('/'):
                        name = name[1:]
                    
                    self.entries[i]['full_path'] = name
                    
                    if '/' in name:
                        base_name = name.split('/')[-1]
                        self.entries[i]['path_dir'] = os.path.dirname(name)
                    else:
                        base_name = name
                        self.entries[i]['path_dir'] = ''
                    
                    self.entries[i]['name'] = base_name
                    
        except Exception as e:
            print(f"Error parseando nombres: {e}")
    
    def _build_directory_tree(self):
        """Construir árbol de directorios a partir de las rutas"""
        self.file_tree = {}
        
        for entry in self.entries:
            full_path = entry.get('full_path', entry['name'])
            
            if '/' not in full_path:
                self.file_tree[full_path] = entry
                continue
            
            path_parts = full_path.split('/')
            current = self.file_tree
            
            for i, part in enumerate(path_parts):
                if i == len(path_parts) - 1:
                    current[part] = entry
                else:
                    if part not in current:
                        current[part] = {}
                    if not isinstance(current[part], dict):
                        current[part] = {}
                    current = current[part]
    
    def get_entries(self):
        """Obtener lista de entradas"""
        return self.entries
        
    def get_directory_structure(self):
        """Obtener estructura de directorios para visualización"""
        return self.file_tree
    
    def extract_file(self, index, output_path):
        """Extraer un archivo específico del RTPK"""
        if index < 0 or index >= len(self.entries):
            return False
            
        entry = self.entries[index]
        start = entry['offset']
        size = entry['size']
        
        if start + size <= len(self.data):
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
