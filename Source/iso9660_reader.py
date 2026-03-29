"""
Módulo para lectura de archivos ISO9660 (PS2)
Implementa el parsing básico de la estructura ISO9660
"""
import struct
import os

class ISO9660Reader:
    """Clase para leer archivos ISO9660 (PS2)"""
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.file = None
        self.block_size = 2048
        self.reserved_blocks = 16
        self.volume_descriptor = None
        self.root_directory = None
        self.encoding = 'utf-8'
        
    def open(self):
        """Abrir el archivo ISO"""
        self.file = open(self.filepath, 'rb')
        self.load_volume_descriptors()
        
    def close(self):
        """Cerrar el archivo"""
        if self.file:
            self.file.close()
            self.file = None
            
    def seek(self, pos):
        """Posicionarse en el archivo"""
        self.file.seek(pos)
        
    def read(self, size):
        """Leer bytes del archivo"""
        return self.file.read(size)
        
    def read_block(self, block_num):
        """Leer un bloque completo"""
        self.seek(block_num * self.block_size)
        return self.file.read(self.block_size)
        
    def load_volume_descriptors(self):
        """Cargar los descriptores de volumen"""
        for block in range(self.reserved_blocks, 100):
            data = self.read_block(block)
            if len(data) < 6:
                continue
                
            if data[1:6].decode('ascii', errors='ignore') != 'CD001':
                continue
                
            descriptor_type = data[0]
            
            if descriptor_type == 1:
                self.parse_primary_volume_descriptor(data)
                break
            elif descriptor_type == 255:
                break
                
        if not self.volume_descriptor:
            raise Exception("No se encontró Primary Volume Descriptor")
            
    def parse_primary_volume_descriptor(self, data):
        """Parsear el descriptor de volumen primario"""
        self.volume_descriptor = {
            'type': data[0],
            'standard_id': data[1:6].decode('ascii'),
            'version': data[6],
            'system_id': data[8:40].decode('ascii', errors='ignore').strip(),
            'volume_id': data[40:72].decode('ascii', errors='ignore').strip(),
            'volume_space_size': struct.unpack('<I', data[80:84])[0],
            'volume_set_size': struct.unpack('<H', data[120:122])[0],
            'volume_sequence_number': struct.unpack('<H', data[124:126])[0],
            'logical_block_size': struct.unpack('<H', data[128:130])[0],
            'path_table_size': struct.unpack('<I', data[132:136])[0],
            'l_path_table_location': struct.unpack('<I', data[140:144])[0],
            'opt_l_path_table_location': struct.unpack('<I', data[144:148])[0],
            'm_path_table_location': struct.unpack('>I', data[148:152])[0],
            'opt_m_path_table_location': struct.unpack('>I', data[152:156])[0],
        }
        
        self.root_directory = self.parse_directory_entry(data, 156, '')
        
    def parse_directory_entry(self, data, offset, parent_path):
        """Parsear una entrada de directorio"""
        try:
            if offset >= len(data):
                return None
                
            entry_length = data[offset]
            if entry_length == 0:
                return None
                
            if offset + entry_length > len(data):
                return None
                
            location = struct.unpack('<I', data[offset + 2:offset + 6])[0] if offset + 6 <= len(data) else 0
            data_length = struct.unpack('<I', data[offset + 10:offset + 14])[0] if offset + 14 <= len(data) else 0
            
            year = data[offset + 18] + 1900 if offset + 19 <= len(data) else 0
            month = data[offset + 19] if offset + 20 <= len(data) else 0
            day = data[offset + 20] if offset + 21 <= len(data) else 0
            hour = data[offset + 21] if offset + 22 <= len(data) else 0
            minute = data[offset + 22] if offset + 23 <= len(data) else 0
            second = data[offset + 23] if offset + 24 <= len(data) else 0
            
            flags = data[offset + 25] if offset + 26 <= len(data) else 0
            
            name_length = data[offset + 32] if offset + 33 <= len(data) else 0
            name_start = offset + 33
            
            if name_start + name_length <= len(data):
                name = data[name_start:name_start + name_length].decode(self.encoding, errors='ignore')
                if ';' in name:
                    name = name.split(';')[0]
            else:
                name = ""
                
            is_directory = (flags & 0x02) != 0
            
            if name == '.':
                full_path = parent_path
            elif name == '..':
                full_path = os.path.dirname(parent_path.rstrip('/'))
            else:
                if parent_path:
                    full_path = f"{parent_path}/{name}"
                else:
                    full_path = name
                    
            if is_directory and name not in ['.', '..']:
                full_path += '/'
                
            date_str = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}" if year > 1900 else ""
                
            return {
                'name': name,
                'full_path': full_path,
                'is_directory': is_directory,
                'location': location,
                'size': data_length,
                'date': date_str,
                'entry_length': entry_length
            }
            
        except Exception as e:
            print(f"Error parsing entry at offset {offset}: {e}")
            return None
            
    def read_directory(self, location, parent_path=''):
        """Leer el contenido de un directorio"""
        entries = []
        
        try:
            data = self.read_block(location)
            offset = 0
            
            while offset < len(data):
                entry = self.parse_directory_entry(data, offset, parent_path)
                if entry:
                    entries.append(entry)
                    offset += entry['entry_length']
                else:
                    if offset < len(data) and data[offset] == 0:
                        break
                    offset += 1
                    
        except Exception as e:
            print(f"Error reading directory at location {location}: {e}")
            
        return entries
        
    def read_file_data(self, location, size):
        """Leer datos de un archivo"""
        self.seek(location * self.block_size)
        return self.file.read(size)
