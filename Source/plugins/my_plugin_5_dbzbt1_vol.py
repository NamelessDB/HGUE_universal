"""
Plugin for Dragon Ball Z: Budokai Tenkaichi 1 (PS2) - VOL container
Soporta:
 - DBZUS0.VOL (contenedor principal)
 - SLUS_212.27 (tabla de archivos)
Creditos a Diana Devs por la informacion y ayuda
"""

import struct
import os
from .plugin_base import ContainerPlugin, ContainerReader


US_PS = 0xBE300
US_SZ = 0x1364
ENTRY_SIZE = 8


def parse_elf_table(elf_data: bytes):
    entries = []
    
    required_size = US_PS + (US_SZ * ENTRY_SIZE)
    if len(elf_data) < required_size:
        print(f"[DBZ VOL] ELF demasiado pequeno: {len(elf_data)} < {required_size}")
        return entries
    
    offset = US_PS
    
    for i in range(US_SZ):
        try:
            raw_pos, raw_size = struct.unpack_from('<II', elf_data, offset)
            real_offset = raw_pos * 0x800
            real_size = raw_size * 4
            
            entries.append((real_offset, real_size))
            offset += ENTRY_SIZE
            
        except Exception as e:
            print(f"[DBZ VOL] Error parseando entrada {i}: {e}")
            continue
    
    return entries


class DBZVOLReader(ContainerReader):
    
    MAX_PREVIEW_SIZE = 4 * 1024 * 1024
    
    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        super().__init__(data, filename, parent_iso, parent_path)
        
        self.entries = []
        self.total_files = 0
        self.entry = None
        
        self.load()
    
    def _find_file(self, filename):
        try:
            stack = [self.parent_iso.root_directory]
            
            while stack:
                current = stack.pop()
                
                entries = self.parent_iso.read_directory(
                    current['location'],
                    current['full_path']
                )
                
                for e in entries:
                    if e['name'].upper() == filename.upper():
                        return e
                    
                    if e['is_directory'] and e['name'] not in ['.', '..']:
                        stack.append(e)
                        
        except Exception as e:
            print(f"[DBZ VOL] Error buscando archivo: {e}")
        
        return None
    
    def _get_icon(self, ext):
        icons = {
            'bin': '📦',
            'dat': '📊',
            'txt': '📝',
            'tm2': '🖼️',
            'tpl': '🖼️',
            'pss': '🎬',
            'adx': '🎵',
            'vag': '🎵',
            'wav': '🔊',
            'mp3': '🎵',
            'at3': '🎵',
            'png': '🖼️',
            'jpg': '🖼️',
            'gim': '🖼️',
            'tim': '🖼️'
        }
        return icons.get(ext, '📄')
    
    def _detect_type(self, data, offset, size):
        if size < 4:
            return 'bin'
        
        try:
            header = data[offset:min(offset+16, offset+size)]
            
            if header.startswith(b'\x00\x00\x01\x00'):
                return 'txt'
            elif header.startswith(b'RIFF') or header.startswith(b'RIFX'):
                return 'wav'
            elif header.startswith(b'OggS'):
                return 'ogg'
            elif header.startswith(b'\x80\x00\x00\x00'):
                return 'tm2'
            elif header.startswith(b'GIM'):
                return 'gim'
            elif header.startswith(b'\x89PNG'):
                return 'png'
            elif header.startswith(b'\xFF\xD8'):
                return 'jpg'
            elif header.startswith(b'PSS'):
                return 'pss'
            elif header.startswith(b'ADX'):
                return 'adx'
                
        except:
            pass
        
        return 'bin'
    
    def load(self):
        try:
            print("[DBZ VOL] Cargando DBZUS0.VOL...")
            
            elf_entry = self._find_file("SLUS_212.27")
            
            if not elf_entry:
                print("[DBZ VOL] ERROR: No se encontro SLUS_212.27")
                return
            
            print(f"[DBZ VOL] Encontrado SLUS_212.27: {elf_entry['size']} bytes")
            
            elf_data = self.parent_iso.read_file_data(elf_entry['location'], elf_entry['size'])
            
            if not elf_data:
                print("[DBZ VOL] ERROR: No se pudo leer SLUS_212.27")
                return
            
            file_table = parse_elf_table(elf_data)
            
            if not file_table:
                print("[DBZ VOL] ERROR: No se pudieron parsear entradas")
                return
            
            print(f"[DBZ VOL] Tabla parseada: {len(file_table)} entradas")
            
            vol_data = self.data
            vol_size = len(vol_data) if vol_data else 0
            print(f"[DBZ VOL] VOL size: {vol_size:,} bytes ({vol_size/1048576:.2f} MB)")
            
            valid_count = 0
            total_bytes = 0
            
            for idx, (offset, size) in enumerate(file_table):
                if offset >= vol_size or size == 0 or offset < 0:
                    name = f"file_{idx:04d}.bin"
                    ext = 'bin'
                    icon = '📦'
                    valid = False
                else:
                    valid = True
                    valid_count += 1
                    total_bytes += size
                    
                    ext = self._detect_type(vol_data, offset, size)
                    icon = self._get_icon(ext)
                    name = f"file_{idx:04d}.{ext}" if ext != 'bin' else f"file_{idx:04d}.bin"
                
                self.entries.append({
                    'index': idx,
                    'name': name,
                    'full_path': name,
                    'is_directory': False,
                    'offset': offset,
                    'size': size,
                    'ext': ext,
                    'icon': icon,
                    'type': f"DBZ File ({ext.upper()})",
                    'valid': valid
                })
                
                if (idx + 1) % 500 == 0:
                    print(f"[DBZ VOL] Procesados {idx + 1}/{len(file_table)} archivos...")
            
            self.total_files = valid_count
            print(f"[DBZ VOL] Cargados {valid_count}/{len(file_table)} archivos")
            print(f"[DBZ VOL] Tamaño total: {total_bytes:,} bytes ({total_bytes/1048576:.2f} MB)")
            
        except Exception as e:
            print(f"[DBZ VOL] Error en load: {e}")
            import traceback
            traceback.print_exc()
    
    
    def get_entries(self):
        return self.entries
    
    def get_file_data(self, index):
        if index < 0 or index >= len(self.entries):
            return None
        
        if not self.entry:
            print("[DBZ VOL] ERROR: self.entry is None")
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
            print(f"[DBZ VOL] Error get_file_data: {e}")
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
            'type': 'DBZ Budokai Tenkaichi 1 VOL Container'
        }


class DBZTenkaichiVOLPlugin(ContainerPlugin):
    
    plugin_name = "DBZ Budokai Tenkaichi 1 VOL"
    plugin_version = "1.0"
    plugin_author = "Huziad"
    plugin_description = "Support for DBZ Budokai Tenkaichi 1 VOL container"
    
    file_extensions = ['.vol']
    file_names = ['DBZUS0.VOL', 'dbzus0.vol', 'DBZUS1.VOL', 'dbzus1.vol']
    icon = "⚡📦"
    container_type_name = "DBZ VOL Container"
    priority = 85
    
    @classmethod
    def can_handle(cls, filename, data, iso_reader=None, entries=None):
        name_lower = filename.lower()
        
        if name_lower.endswith('.vol'):
            print(f"[DBZ VOL] Verificando archivo: {filename}")
            
            if iso_reader:
                try:
                    if hasattr(iso_reader, 'root_directory'):
                        stack = [iso_reader.root_directory]
                        
                        while stack:
                            current = stack.pop()
                            dir_entries = iso_reader.read_directory(
                                current['location'],
                                current['full_path']
                            )
                            
                            for e in dir_entries:
                                if e['name'].upper() == 'SLUS_212.27':
                                    print("[DBZ VOL] ¡Encontrado SLUS_212.27 en ISO!")
                                    return True, 95
                                    
                                if e['is_directory'] and e['name'] not in ['.', '..']:
                                    stack.append(e)
                except Exception as e:
                    print(f"[DBZ VOL] Error verificando ISO: {e}")
            
            return True, 70
        
        return False, 0
    
    @classmethod
    def create_reader(cls, entry, iso_reader, data=None):
        if data is None:
            data = iso_reader.read_file_data(entry['location'], entry['size'])
        
        reader = DBZVOLReader(data, entry['name'], iso_reader, entry['full_path'])
        
        reader.entry = entry
        
        return reader
