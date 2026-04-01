"""
Plugin for Nana (PS2) - NKP Container
Creditos a Diana Devs por la informacion y ayuda
"""

import struct
import os
from .plugin_base import ContainerPlugin, ContainerReader


NKP_MAGIC = b"NKP\x1a"
HEADER_SIZE = 16
ENTRY_SIZE = 8


def parse_nkp_directory(data: bytes):
    if len(data) < 4 or data[:4] != NKP_MAGIC:
        return []
    
    num_files = struct.unpack_from("<I", data, 12)[0]
    
    if num_files == 0:
        return []
    
    raw_entries = []
    for i in range(num_files):
        base = HEADER_SIZE + i * ENTRY_SIZE
        if base + ENTRY_SIZE > len(data):
            break
        name_off = struct.unpack_from("<I", data, base)[0]
        data_off = struct.unpack_from("<I", data, base + 4)[0]
        raw_entries.append((name_off, data_off))
    
    entries = []
    for i, (name_off, data_off) in enumerate(raw_entries):
        try:
            end = data.index(b"\x00", name_off)
            name = data[name_off:end].decode("latin-1", errors="replace")
        except (ValueError, UnicodeDecodeError):
            name = f"file_{i:04d}.bin"
        
        if i + 1 < len(raw_entries):
            next_data_off = raw_entries[i + 1][1]
            size = next_data_off - data_off
        else:
            size = len(data) - data_off
        
        if size < 0:
            size = 0
        
        entries.append({
            "name": name,
            "data_offset": data_off,
            "data_size": size
        })
    
    return entries


class NKPReader(ContainerReader):
    
    MAX_PREVIEW_SIZE = 4 * 1024 * 1024
    
    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        super().__init__(data, filename, parent_iso, parent_path)
        
        self.entries = []
        self.total_files = 0
        self.entry = None
        self.file_entries = []
        
        self.load()
    
    def _get_icon(self, ext):
        icons = {
            'bin': '📦',
            'dat': '📊',
            'txt': '📝',
            'bmp': '🖼️',
            'png': '🖼️',
            'jpg': '🖼️',
            'wav': '🔊',
            'ogg': '🎵',
            'mp3': '🎵',
            'adx': '🎵',
            'vag': '🎵',
            'pss': '🎬',
            'tm2': '🖼️',
            'tim': '🖼️',
            'lua': '📜',
            'xml': '📄'
        }
        return icons.get(ext, '📄')
    
    def load(self):
        try:
            print(f"[NKP] Cargando archivo: {self.filename}")
            
            if not self.data:
                print("[NKP] ERROR: No hay datos")
                return
            
            if len(self.data) < 4:
                print("[NKP] ERROR: Archivo demasiado pequeno")
                return
            
            if self.data[:4] != NKP_MAGIC:
                print(f"[NKP] Magic incorrecto: {self.data[:4]!r}")
                return
            
            print("[NKP] Magic NKP verificado correctamente")
            
            self.file_entries = parse_nkp_directory(self.data)
            
            if not self.file_entries:
                print("[NKP] ERROR: No se pudieron parsear entradas")
                return
            
            print(f"[NKP] Entradas parseadas: {len(self.file_entries)}")
            
            valid_count = 0
            total_bytes = 0
            nkp_data = self.data
            nkp_size = len(nkp_data)
            
            for idx, entry in enumerate(self.file_entries):
                offset = entry['data_offset']
                size = entry['data_size']
                
                if offset >= nkp_size or size == 0 or offset < 0:
                    name = f"file_{idx:04d}.bin"
                    ext = 'bin'
                    icon = '📦'
                    valid = False
                else:
                    valid = True
                    valid_count += 1
                    total_bytes += size
                    
                    ext = entry['name'].rsplit(".", 1)[-1].lower() if "." in entry['name'] else 'bin'
                    icon = self._get_icon(ext)
                    name = entry['name']
                
                self.entries.append({
                    'index': idx,
                    'name': name,
                    'full_path': name,
                    'is_directory': False,
                    'offset': offset,
                    'size': size,
                    'ext': ext,
                    'icon': icon,
                    'type': f"NKP File ({ext.upper()})",
                    'valid': valid
                })
                
                if (idx + 1) % 500 == 0:
                    print(f"[NKP] Procesados {idx + 1}/{len(self.file_entries)} archivos...")
            
            self.total_files = valid_count
            print(f"[NKP] Cargados {valid_count}/{len(self.file_entries)} archivos")
            print(f"[NKP] Tamaño total: {total_bytes:,} bytes ({total_bytes/1048576:.2f} MB)")
            
        except Exception as e:
            print(f"[NKP] Error en load: {e}")
            import traceback
            traceback.print_exc()
    
    def get_entries(self):
        return self.entries
    
    def get_file_data(self, index):
        if index < 0 or index >= len(self.entries):
            return None
        
        if not self.entry:
            print("[NKP] ERROR: self.entry is None")
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
            print(f"[NKP] Error get_file_data: {e}")
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
            'type': 'Nana NKP Container'
        }


class NKPPlugin(ContainerPlugin):
    
    plugin_name = "Nana NKP"
    plugin_version = "1.0"
    plugin_author = "Huziad"
    plugin_description = "Support for Nana (PS2) NKP container files"
    
    file_extensions = ['.nkp', '.NKP']
    file_names = []
    icon = "🎵📦"
    container_type_name = "NKP Container"
    priority = 85
    
    @classmethod
    def can_handle(cls, filename, data, iso_reader=None, entries=None):
        name_lower = filename.lower()
        
        if name_lower.endswith('.nkp'):
            print(f"[NKP] Verificando archivo: {filename}")
            
            if data and len(data) >= 4:
                if data[:4] == NKP_MAGIC:
                    print("[NKP] Magic NKP detectado")
                    return True, 95
                else:
                    print(f"[NKP] Magic incorrecto: {data[:4]!r}")
                    return False, 0
            
            return True, 70
        
        return False, 0
    
    @classmethod
    def create_reader(cls, entry, iso_reader, data=None):
        if data is None:
            data = iso_reader.read_file_data(entry['location'], entry['size'])
        
        reader = NKPReader(data, entry['name'], iso_reader, entry['full_path'])
        
        reader.entry = entry
        
        return reader
