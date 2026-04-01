"""
Plugin for Ichigo 100% (Strawberry) - NFP2.0 Container
Creditos a Diana Devs por la informacion y ayuda
"""

import struct
import os
from .plugin_base import ContainerPlugin, ContainerReader


NFP_MAGIC = b"NFP2.0 (c)NOBORI"
HEADER_SIZE = 0x40
DIR_ENTRY_SIZE = 0x20
OFF_NUM_FILES = 0x34
OFF_DIR_OFFSET = 0x38
OFF_DATA_OFFSET = 0x3C
EOFF_NAME = 0x00
ENAME_MAX = 0x0C
EOFF_REAL_SIZE = 0x0C
EOFF_FILE_OFFSET = 0x18
EOFF_PAD_SIZE = 0x1C


def parse_nfp_directory(data: bytes):
    if not data.startswith(NFP_MAGIC):
        return []
    
    num_files = struct.unpack_from("<I", data, OFF_NUM_FILES)[0]
    dir_offset = struct.unpack_from("<I", data, OFF_DIR_OFFSET)[0]
    
    if num_files == 0:
        return []
    
    entries = []
    for i in range(num_files):
        base = dir_offset + i * DIR_ENTRY_SIZE
        
        raw_name = data[base + EOFF_NAME:base + EOFF_NAME + ENAME_MAX]
        name = raw_name.split(b"\x00")[0].decode("ascii", errors="replace")
        
        real_size = struct.unpack_from("<I", data, base + EOFF_REAL_SIZE)[0]
        file_offset = struct.unpack_from("<I", data, base + EOFF_FILE_OFFSET)[0]
        pad_size = struct.unpack_from("<I", data, base + EOFF_PAD_SIZE)[0]
        
        entries.append({
            "name": name,
            "real_size": real_size,
            "file_offset": file_offset,
            "pad_size": pad_size
        })
    
    return entries


class NFPReader(ContainerReader):
    
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
            'tim': '🖼️'
        }
        return icons.get(ext, '📄')
    
    def load(self):
        try:
            print(f"[NFP] Cargando archivo: {self.filename}")
            
            if not self.data:
                print("[NFP] ERROR: No hay datos")
                return
            
            if len(self.data) < HEADER_SIZE:
                print("[NFP] ERROR: Archivo demasiado pequeno")
                return
            
            if not self.data.startswith(NFP_MAGIC):
                print(f"[NFP] Magic incorrecto: {self.data[:16]!r}")
                return
            
            print("[NFP] Magic NFP2.0 verificado correctamente")
            
            self.file_entries = parse_nfp_directory(self.data)
            
            if not self.file_entries:
                print("[NFP] ERROR: No se pudieron parsear entradas")
                return
            
            print(f"[NFP] Entradas parseadas: {len(self.file_entries)}")
            
            valid_count = 0
            total_bytes = 0
            nfp_data = self.data
            nfp_size = len(nfp_data)
            
            for idx, entry in enumerate(self.file_entries):
                offset = entry['file_offset']
                size = entry['real_size']
                
                if offset >= nfp_size or size == 0 or offset < 0:
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
                    'pad_size': entry['pad_size'],
                    'ext': ext,
                    'icon': icon,
                    'type': f"NFP File ({ext.upper()})",
                    'valid': valid
                })
                
                if (idx + 1) % 500 == 0:
                    print(f"[NFP] Procesados {idx + 1}/{len(self.file_entries)} archivos...")
            
            self.total_files = valid_count
            print(f"[NFP] Cargados {valid_count}/{len(self.file_entries)} archivos")
            print(f"[NFP] Tamaño total: {total_bytes:,} bytes ({total_bytes/1048576:.2f} MB)")
            
        except Exception as e:
            print(f"[NFP] Error en load: {e}")
            import traceback
            traceback.print_exc()
    
    def get_entries(self):
        return self.entries
    
    def get_file_data(self, index):
        if index < 0 or index >= len(self.entries):
            return None
        
        if not self.entry:
            print("[NFP] ERROR: self.entry is None")
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
            print(f"[NFP] Error get_file_data: {e}")
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
            'type': 'Ichigo 100% NFP2.0 Container'
        }


class NFPPlugin(ContainerPlugin):
    
    plugin_name = "Ichigo 100% NFP2.0"
    plugin_version = "1.0"
    plugin_author = "Huziad"
    plugin_description = "Support for Ichigo 100% (Strawberry) NFP2.0 container files"
    
    file_extensions = ['.nfp', '.NFP']
    file_names = []
    icon = "🍓📦"
    container_type_name = "NFP2.0 Container"
    priority = 85
    
    @classmethod
    def can_handle(cls, filename, data, iso_reader=None, entries=None):
        name_lower = filename.lower()
        
        if name_lower.endswith('.nfp'):
            print(f"[NFP] Verificando archivo: {filename}")
            
            if data and len(data) >= 16:
                if data[:16] == NFP_MAGIC[:16]:
                    print("[NFP] Magic NFP2.0 detectado")
                    return True, 95
                else:
                    print(f"[NFP] Magic incorrecto: {data[:16]!r}")
                    return False, 0
            
            return True, 70
        
        return False, 0
    
    @classmethod
    def create_reader(cls, entry, iso_reader, data=None):
        if data is None:
            data = iso_reader.read_file_data(entry['location'], entry['size'])
        
        reader = NFPReader(data, entry['name'], iso_reader, entry['full_path'])
        
        reader.entry = entry
        
        return reader
