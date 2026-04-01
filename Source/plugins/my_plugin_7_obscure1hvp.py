"""
Plugin for Obscure (PS2) - HVP Container
Creditos a Diana Devs por la informacion y ayuda
"""

import struct
import zlib
import os
from .plugin_base import ContainerPlugin, ContainerReader


class HVPEntry:
    def __init__(self, name, path, is_dir=False, compressed=0, decompressed=0, crc=0, offset=0, children=None):
        self.name = name
        self.path = path
        self.is_dir = is_dir
        self.compressed = compressed
        self.decompressed = decompressed
        self.crc = crc
        self.offset = offset
        self.children = children or []


def parse_hvp_directory(data: bytes):
    if data[:12] != b'HV PackFile\x00':
        return []
    
    root_count = data[52]
    pos = 53
    
    def read_entries(pos, count, vpath=""):
        entries = []
        for _ in range(count):
            name_len = struct.unpack_from('>I', data, pos)[0]
            pos += 4
            name = data[pos:pos+name_len].decode('latin-1', errors='replace')
            pos += name_len
            pos += 1
            
            c0 = struct.unpack_from('>I', data, pos)[0]
            c1 = struct.unpack_from('>I', data, pos+4)[0]
            c2 = struct.unpack_from('>I', data, pos+8)[0]
            
            entry_path = f"{vpath}/{name}" if vpath else name
            
            if c1 == 0:
                pos += 12
                child_count = c2
                children, pos = read_entries(pos, child_count, entry_path)
                entries.append(HVPEntry(
                    name=name, path=entry_path, is_dir=True, children=children
                ))
            else:
                compressed = c2
                decompressed = struct.unpack_from('>I', data, pos+12)[0]
                crc = struct.unpack_from('>I', data, pos+16)[0]
                offset = struct.unpack_from('>I', data, pos+20)[0]
                pos += 24
                entries.append(HVPEntry(
                    name=name, path=entry_path, is_dir=False,
                    compressed=compressed, decompressed=decompressed,
                    crc=crc, offset=offset
                ))
        return entries, pos
    
    root_entries, _ = read_entries(pos, root_count)
    return root_entries


def flatten_entries(entries):
    result = []
    for e in entries:
        if e.is_dir:
            result.extend(flatten_entries(e.children))
        else:
            result.append(e)
    return result


class ObscureHVPReader(ContainerReader):
    
    MAX_PREVIEW_SIZE = 4 * 1024 * 1024
    
    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        super().__init__(data, filename, parent_iso, parent_path)
        
        self.entries = []
        self.total_files = 0
        self.entry = None
        self.root_entries = []
        
        self.load()
    
    def _get_icon(self, ext):
        icons = {
            'bin': '📦',
            'dat': '📊',
            'txt': '📝',
            'bmp': '🖼️',
            'png': '🖼️',
            'jpg': '🖼️',
            'dds': '🖼️',
            'tga': '🖼️',
            'wav': '🔊',
            'ogg': '🎵',
            'mp3': '🎵',
            'adx': '🎵',
            'vag': '🎵',
            'pss': '🎬',
            'sfd': '🎬',
            'lua': '📜',
            'xml': '📄',
            'ini': '⚙️'
        }
        return icons.get(ext, '📄')
    
    def load(self):
        try:
            print("[Obscure] Cargando archivo HVP...")
            
            if not self.data:
                print("[Obscure] ERROR: No hay datos")
                return
            
            if self.data[:12] != b'HV PackFile\x00':
                print("[Obscure] ERROR: Magic HVP no encontrado")
                return
            
            self.root_entries = parse_hvp_directory(self.data)
            
            if not self.root_entries:
                print("[Obscure] ERROR: No se pudieron parsear entradas")
                return
            
            all_files = flatten_entries(self.root_entries)
            print(f"[Obscure] Entradas parseadas: {len(all_files)} archivos")
            
            valid_count = 0
            total_bytes = 0
            hvp_data = self.data
            hvp_size = len(hvp_data)
            
            for idx, entry in enumerate(all_files):
                if entry.offset >= hvp_size or entry.compressed == 0 or entry.offset < 0:
                    name = f"file_{idx:04d}.bin"
                    ext = 'bin'
                    icon = '📦'
                    valid = False
                else:
                    valid = True
                    valid_count += 1
                    total_bytes += entry.decompressed
                    
                    ext = entry.name.rsplit(".", 1)[-1].lower() if "." in entry.name else 'bin'
                    icon = self._get_icon(ext)
                    name = entry.name
                
                self.entries.append({
                    'index': idx,
                    'name': name,
                    'full_path': entry.path,
                    'is_directory': False,
                    'offset': entry.offset,
                    'size': entry.compressed,
                    'decompressed_size': entry.decompressed,
                    'ext': ext,
                    'icon': icon,
                    'type': f"Obscure File ({ext.upper()})",
                    'valid': valid,
                    'crc': entry.crc
                })
                
                if (idx + 1) % 500 == 0:
                    print(f"[Obscure] Procesados {idx + 1}/{len(all_files)} archivos...")
            
            self.total_files = valid_count
            print(f"[Obscure] Cargados {valid_count}/{len(all_files)} archivos")
            print(f"[Obscure] Tamaño total: {total_bytes:,} bytes ({total_bytes/1048576:.2f} MB)")
            
        except Exception as e:
            print(f"[Obscure] Error en load: {e}")
            import traceback
            traceback.print_exc()
    
    def _decompress_zlib(self, data):
        try:
            return zlib.decompress(data)
        except:
            return None
    
    def get_entries(self):
        return self.entries
    
    def get_file_data(self, index):
        if index < 0 or index >= len(self.entries):
            return None
        
        if not self.entry:
            print("[Obscure] ERROR: self.entry is None")
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
            
            compressed_data = container_data[offset:offset + size]
            
            decompressed = self._decompress_zlib(compressed_data)
            
            if decompressed is None:
                return compressed_data[:self.MAX_PREVIEW_SIZE]
            
            return decompressed[:self.MAX_PREVIEW_SIZE]
            
        except Exception as e:
            print(f"[Obscure] Error get_file_data: {e}")
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
            
            compressed_data = container_data[entry['offset']:entry['offset'] + entry['size']]
            
            decompressed = self._decompress_zlib(compressed_data)
            
            if decompressed is None:
                data = compressed_data
                size_msg = f"{len(data)} bytes (sin comprimir)"
            else:
                data = decompressed
                size_msg = f"{len(data)} bytes (descomprimido)"
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as f:
                f.write(data)
            
            return True, f"Extracted: {entry['name']} ({size_msg})"
            
        except Exception as e:
            return False, str(e)
    
    def get_stats(self):
        total_comp = sum(e['size'] for e in self.entries if e.get('valid', True))
        total_decomp = sum(e.get('decompressed_size', 0) for e in self.entries if e.get('valid', True))
        
        return {
            'files': self.total_files,
            'directories': 0,
            'total_size': total_comp,
            'total_decompressed': total_decomp,
            'type': 'Obscure HVP Container'
        }


class ObscureHVPPlugin(ContainerPlugin):
    
    plugin_name = "Obscure HVP"
    plugin_version = "1.0"
    plugin_author = "Huziad"
    plugin_description = "Support for Obscure HVP container files"
    
    file_extensions = ['.hvp', '.HVP']
    file_names = []
    icon = "📦"
    container_type_name = "Obscure HVP Container"
    priority = 85
    
    @classmethod
    def can_handle(cls, filename, data, iso_reader=None, entries=None):
        name_lower = filename.lower()
        
        if name_lower.endswith('.hvp'):
            print(f"[Obscure] Verificando archivo: {filename}")
            
            if data and len(data) >= 12:
                if data[:12] == b'HV PackFile\x00':
                    print("[Obscure] Magic HVP detectado")
                    return True, 95
            
            return True, 70
        
        return False, 0
    
    @classmethod
    def create_reader(cls, entry, iso_reader, data=None):
        if data is None:
            data = iso_reader.read_file_data(entry['location'], entry['size'])
        
        reader = ObscureHVPReader(data, entry['name'], iso_reader, entry['full_path'])
        
        reader.entry = entry
        
        return reader
