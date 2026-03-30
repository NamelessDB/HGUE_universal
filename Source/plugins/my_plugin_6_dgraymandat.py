"""
Plugin for D.Gray-man: Sousha no Shikaku (PS2) - DAT Container
"""

import struct
import os
from .plugin_base import ContainerPlugin, ContainerReader


BLOCK_SIZE = 2048
DIR_ENTRY_SIZE = 64


def parse_dat_directory(data: bytes):
    entries = []
    pos = 0
    size = len(data)
    
    while pos + DIR_ENTRY_SIZE <= size:
        raw = data[pos:pos + DIR_ENTRY_SIZE]
        block_idx = struct.unpack_from("<I", raw, 0)[0]
        file_size = struct.unpack_from("<I", raw, 4)[0]
        name_bytes = raw[8:]
        name = name_bytes.split(b"\x00")[0].decode("ascii", errors="replace")
        
        if not name and block_idx == 0 and file_size == 0:
            break
        
        entries.append((block_idx, file_size, name))
        pos += DIR_ENTRY_SIZE
    
    return entries


class DGrayManDATReader(ContainerReader):
    
    MAX_PREVIEW_SIZE = 4 * 1024 * 1024
    
    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        super().__init__(data, filename, parent_iso, parent_path)
        
        self.entries = []
        self.total_files = 0
        self.entry = None
        self.file_table = []
        
        self.load()
    
    def _get_icon(self, ext):
        icons = {
            'bin': '📦',
            'dat': '📊',
            'txt': '📝',
            'bmp': '🖼️',
            'png': '🖼️',
            'jpg': '🖼️',
            'tips': '📋',
            'csv': '📊',
            'ico': '🖼️',
            'lzh': '🗜️',
            'zip': '🗜️',
            'xls': '📊'
        }
        return icons.get(ext, '📄')
    
    def load(self):
        try:
            print("[DGM] Cargando archivo DAT...")
            
            if not self.data:
                print("[DGM] ERROR: No hay datos")
                return
            
            self.file_table = parse_dat_directory(self.data)
            
            if not self.file_table:
                print("[DGM] ERROR: No se pudieron parsear entradas")
                return
            
            print(f"[DGM] Tabla parseada: {len(self.file_table)} entradas")
            
            valid_count = 0
            total_bytes = 0
            vol_data = self.data
            vol_size = len(vol_data)
            
            for idx, (block_idx, size, name) in enumerate(self.file_table):
                offset = block_idx * BLOCK_SIZE
                
                if offset >= vol_size or size == 0 or offset < 0:
                    name = f"file_{idx:04d}.bin"
                    ext = 'bin'
                    icon = '📦'
                    valid = False
                else:
                    valid = True
                    valid_count += 1
                    total_bytes += size
                    
                    ext = name.rsplit(".", 1)[-1].lower() if "." in name else "bin"
                    icon = self._get_icon(ext)
                
                self.entries.append({
                    'index': idx,
                    'name': os.path.basename(name),
                    'full_path': name,
                    'is_directory': False,
                    'offset': offset,
                    'size': size,
                    'ext': ext,
                    'icon': icon,
                    'type': f"DGM File ({ext.upper()})",
                    'valid': valid,
                    'block_idx': block_idx
                })
                
                if (idx + 1) % 500 == 0:
                    print(f"[DGM] Procesados {idx + 1}/{len(self.file_table)} archivos...")
            
            self.total_files = valid_count
            print(f"[DGM] Cargados {valid_count}/{len(self.file_table)} archivos")
            print(f"[DGM] Tamaño total: {total_bytes:,} bytes ({total_bytes/1048576:.2f} MB)")
            
        except Exception as e:
            print(f"[DGM] Error en load: {e}")
            import traceback
            traceback.print_exc()
    
    def get_entries(self):
        return self.entries
    
    def get_file_data(self, index):
        if index < 0 or index >= len(self.entries):
            return None
        
        if not self.entry:
            print("[DGM] ERROR: self.entry is None")
            return None
        
        entry = self.entries[index]
        
        if not entry.get('valid', True):
            return None
        
        try:
            offset = entry['offset']
            size = entry['size']
            
            if size <= 0:
                return None
            
            container_data = self.parent_iso.read_file_data(
                self.entry['location'],
                self.entry['size']
            )
            
            if not container_data:
                return None
            
            file_data = container_data[offset:offset + size]
            
            return file_data[:self.MAX_PREVIEW_SIZE]
            
        except Exception as e:
            print(f"[DGM] Error get_file_data: {e}")
            return None
    
    def extract_file(self, index, output_path):
        if not self.entry:
            return False, "Invalid container reference"
        
        if index >= len(self.entries):
            return False, "Index out of range"
        
        entry = self.entries[index]
        
        if not entry.get('valid', True):
            return False, "Invalid file entry"
        
        try:
            container_data = self.parent_iso.read_file_data(
                self.entry['location'],
                self.entry['size']
            )
            
            if not container_data:
                return False, "Failed to read container data"
            
            data = container_data[entry['offset']:entry['offset'] + entry['size']]
            
            if not data:
                return False, "Failed to extract file data"
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as f:
                f.write(data)
            
            return True, f"Extracted: {entry['name']} ({len(data)} bytes)"
            
        except Exception as e:
            return False, str(e)
    
    def get_stats(self):
        total_size = sum(e['size'] for e in self.entries if e.get('valid', True))
        
        return {
            'files': self.total_files,
            'directories': 0,
            'total_size': total_size,
            'type': 'D.Gray-man DAT Container'
        }


class DGrayManDATPlugin(ContainerPlugin):
    
    plugin_name = "D.Gray-man Sousha no Shikaku DAT"
    plugin_version = "1.0"
    plugin_author = "Huziad"
    plugin_description = "Support for D.Gray-man DAT container (DATA0.DAT, DATA1.DAT, DATA2.DAT, DATA3.DAT)"
    
    file_extensions = ['.dat']
    file_names = ['DATA0.DAT', 'DATA1.DAT', 'DATA2.DAT', 'DATA3.DAT', 'data0.dat', 'data1.dat', 'data2.dat', 'data3.dat']
    icon = "📀"
    container_type_name = "DGM DAT Container"
    priority = 85
    
    @classmethod
    def can_handle(cls, filename, data, iso_reader=None, entries=None):
        name_upper = filename.upper()
        
        if name_upper.endswith('.DAT'):
            if name_upper.startswith('DATA0') or name_upper.startswith('DATA1') or \
               name_upper.startswith('DATA2') or name_upper.startswith('DATA3'):
                print(f"[DGM] Detectado archivo DAT: {filename}")
                return True, 95
        
        return False, 0
    
    @classmethod
    def create_reader(cls, entry, iso_reader, data=None):
        if data is None:
            data = iso_reader.read_file_data(entry['location'], entry['size'])
        
        reader = DGrayManDATReader(data, entry['name'], iso_reader, entry['full_path'])
        
        reader.entry = entry
        
        return reader
