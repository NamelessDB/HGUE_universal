"""
Módulo para lectura de archivos FPK (Battle Stadium D.O.N.)
Basado en script QuickBMS:
comtype PRS_8ING
get ZERO long
get FILES long
get INFO_OFF long
get DAT_SIZE long
for i = 0 < FILES
    getdstring NAME 0x24
    get OFFSET long
    get ZSIZE long
    get SIZE long
    clog NAME OFFSET ZSIZE SIZE
next i
"""
import struct
import os
import zlib

class FPKReader:
    """Clase para leer archivos FPK (Battle Stadium D.O.N.)"""
    
    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        self.data = data
        self.filename = filename
        self.parent_iso = parent_iso
        self.parent_path = parent_path
        self.entries = []
        self.zero = 0
        self.file_count = 0
        self.info_offset = 0
        self.data_size = 0
        self.load_fpk()
        
    def load_fpk(self):
        """Cargar y parsear el archivo FPK según script QuickBMS"""
        try:
            if len(self.data) < 16:
                print(f"Archivo demasiado pequeño para ser FPK")
                return
            
            # get ZERO long
            self.zero = struct.unpack('<I', self.data[0:4])[0]
            
            # get FILES long
            self.file_count = struct.unpack('<I', self.data[4:8])[0]
            
            # get INFO_OFF long
            self.info_offset = struct.unpack('<I', self.data[8:12])[0]
            
            # get DAT_SIZE long
            self.data_size = struct.unpack('<I', self.data[12:16])[0]
            
            print(f"FPK Info:")
            print(f"  Zero: 0x{self.zero:08X}")
            print(f"  Files: {self.file_count}")
            print(f"  Info Offset: 0x{self.info_offset:08X}")
            print(f"  Data Size: {self.data_size} bytes")
            
            # Verificar que el número de archivos sea razonable
            if self.file_count == 0 or self.file_count > 50000:
                print(f"⚠️ Número de archivos sospechoso: {self.file_count}")
                return
            
            # Leer entradas desde INFO_OFF
            # Cada entrada: NAME (0x24 bytes), OFFSET, ZSIZE, SIZE
            entry_size = 0x24 + 4 + 4 + 4  # 0x30 = 48 bytes
            
            if self.info_offset + (self.file_count * entry_size) > len(self.data):
                print(f"Tabla de entradas excede tamaño del archivo")
                return
            
            print(f"\nParseando {self.file_count} archivos...")
            
            for i in range(self.file_count):
                entry_offs = self.info_offset + i * entry_size
                
                # getdstring NAME 0x24 (36 bytes)
                name_data = self.data[entry_offs:entry_offs + 0x24]
                # Buscar byte nulo
                name_end = name_data.find(b'\x00')
                if name_end > 0:
                    name = name_data[:name_end].decode('shift-jis', errors='ignore')
                else:
                    name = name_data.decode('shift-jis', errors='ignore').strip('\x00')
                
                if not name or name == '':
                    name = f"file_{i:04d}.bin"
                
                # get OFFSET long
                offset = struct.unpack('<I', self.data[entry_offs + 0x24:entry_offs + 0x28])[0]
                
                # get ZSIZE long
                zsize = struct.unpack('<I', self.data[entry_offs + 0x28:entry_offs + 0x2C])[0]
                
                # get SIZE long
                size = struct.unpack('<I', self.data[entry_offs + 0x2C:entry_offs + 0x30])[0]
                
                # Verificar que los offsets sean válidos
                if offset + zsize > len(self.data):
                    print(f"  Archivo {i}: {name} - OFFSET INVÁLIDO (offset=0x{offset:X}, zsize={zsize})")
                    continue
                
                self.entries.append({
                    'offset': offset,
                    'zsize': zsize,
                    'size': size,
                    'name': name,
                    'index': i,
                    'full_path': name,
                    'is_compressed': zsize > 0 and zsize != size
                })
                
                comp_msg = f" (comprimido {zsize} -> {size})" if self.entries[-1]['is_compressed'] else ""
                if i < 10 or i % 100 == 0:  # Mostrar primeros 10 y luego cada 100
                    print(f"  Archivo {i:04d}: {name} - offset=0x{offset:08X}, size={size}{comp_msg}")
            
            compressed_count = sum(1 for e in self.entries if e['is_compressed'])
            print(f"\n✅ FPK cargado correctamente con {len(self.entries)} archivos ({compressed_count} comprimidos)")
            
        except Exception as e:
            print(f"Error cargando archivo FPK: {e}")
            import traceback
            traceback.print_exc()
    
    def _decompress_prs(self, data, expected_size):
        """Descomprimir datos PRS (8-ing) según el comtype PRS_8ING de QuickBMS"""
        output = bytearray()
        i = 0
        data_len = len(data)
        
        while i < data_len and len(output) < expected_size:
            if i >= data_len:
                break
                
            control = data[i]
            i += 1
            
            if control & 0x80:
                # Modo comprimido (referencia)
                count = (control & 0x7F) + 3
                
                if i >= data_len:
                    break
                    
                if i + 1 >= data_len:
                    break
                    
                offset = struct.unpack('<H', data[i:i+2])[0]
                i += 2
                
                src_pos = len(output) - offset - 1
                if src_pos < 0:
                    src_pos = 0
                    
                for _ in range(count):
                    if src_pos < len(output) and len(output) < expected_size:
                        output.append(output[src_pos])
                        src_pos += 1
                    else:
                        break
            else:
                # Modo sin comprimir (literal)
                count = (control & 0x7F) + 1
                
                if i + count > data_len:
                    count = data_len - i
                    
                output.extend(data[i:i+count])
                i += count
        
        return bytes(output)
    
    def extract_file(self, index, output_path):
        """Extraer un archivo específico del FPK (con descompresión PRS)"""
        if index < 0 or index >= len(self.entries):
            return False
            
        entry = self.entries[index]
        start = entry['offset']
        zsize = entry['zsize']
        size = entry['size']
        
        if start + zsize <= len(self.data):
            compressed_data = self.data[start:start + zsize]
            
            if entry['is_compressed']:
                print(f"  Descomprimiendo {entry['name']} ({zsize} -> {size} bytes)")
                try:
                    data = self._decompress_prs(compressed_data, size)
                    if len(data) != size:
                        try:
                            data = zlib.decompress(compressed_data)
                        except:
                            data = compressed_data
                except Exception as e:
                    try:
                        data = zlib.decompress(compressed_data)
                    except:
                        data = compressed_data
            else:
                data = compressed_data
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as f:
                f.write(data)
            return True
            
        return False
    
    def get_entries(self):
        """Obtener lista de entradas"""
        return self.entries
    
    def get_file_data(self, index):
        """Obtener datos de un archivo específico (descomprimidos)"""
        if index < 0 or index >= len(self.entries):
            return None
            
        entry = self.entries[index]
        start = entry['offset']
        zsize = entry['zsize']
        
        if start + zsize <= len(self.data):
            compressed_data = self.data[start:start + zsize]
            
            if entry['is_compressed']:
                try:
                    return self._decompress_prs(compressed_data, entry['size'])
                except:
                    try:
                        return zlib.decompress(compressed_data)
                    except:
                        return compressed_data
            else:
                return compressed_data
            
        return None
