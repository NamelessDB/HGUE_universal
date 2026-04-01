"""
Plugin for Koihime Musou DODnSE (PS2) - BIN/TAG Container
Creditos a Diana Devs por la informacion y ayuda
"""

import struct
import os
from .plugin_base import ContainerPlugin, ContainerReader


TAG_MAGIC = b'****TAG_DATA****'
BIN_MAGIC = b'****BIN_DATA****'
SIMPLE_ENTRY_SIZE = 8
SIMPLE_COUNT = 255
NAMED_SECTION_OFF = 0x810
NAMED_ENTRY_SIZE = 32
BLOCK_SIZE = 32


class TagEntry:
    __slots__ = ('name', 'bin_offset', 'comp_size', 'padded_size', 'cflag', 'is_named')
    
    def __init__(self, name, bin_offset, comp_size, padded_size, cflag=0, is_named=True):
        self.name = name
        self.bin_offset = bin_offset
        self.comp_size = comp_size
        self.padded_size = padded_size
        self.cflag = cflag
        self.is_named = is_named


def parse_tag_data(data: bytes):
    entries = []
    
    if not data.startswith(TAG_MAGIC):
        return entries
    
    total = len(data)
    
    for i in range(SIMPLE_COUNT):
        pos = 0x10 + i * SIMPLE_ENTRY_SIZE
        if pos + SIMPLE_ENTRY_SIZE > total:
            break
        sz_blocks, offset = struct.unpack_from('<II', data, pos)
        if sz_blocks == 0 and offset == 0:
            break
        real_size = sz_blocks * BLOCK_SIZE
        name = f"__anon_{i:04d}"
        entries.append(TagEntry(name, offset, real_size, real_size, cflag=0, is_named=False))
    
    if total < NAMED_SECTION_OFF:
        return entries
    
    pos = NAMED_SECTION_OFF
    while pos + NAMED_ENTRY_SIZE <= total:
        chunk = data[pos:pos + NAMED_ENTRY_SIZE]
        raw_name = chunk[0:16]
        name = raw_name.rstrip(b'\x00').decode('ascii', errors='replace')
        if not name:
            pos += NAMED_ENTRY_SIZE
            continue
        
        cflag = struct.unpack_from('<I', chunk, 16)[0]
        bin_offset = struct.unpack_from('<I', chunk, 20)[0]
        comp_size = struct.unpack_from('<I', chunk, 24)[0]
        padded_sz = struct.unpack_from('<I', chunk, 28)[0]
        
        entries.append(TagEntry(name, bin_offset, comp_size, padded_sz, cflag=cflag, is_named=True))
        pos += NAMED_ENTRY_SIZE
    
    return entries


def find_tag_file(iso_reader, bin_filename):
    try:
        stack = [iso_reader.root_directory]
        
        while stack:
            current = stack.pop()
            entries = iso_reader.read_directory(current['location'], current['full_path'])
            
            for e in entries:
                name_upper = e['name'].upper()
                if bin_filename.upper() == 'DATA.BIN' and name_upper == 'DATA.TAG':
                    return e
                elif bin_filename.upper() == 'VOICE.BIN' and name_upper == 'VOICE.TAG':
                    return e
                
                if e['is_directory'] and e['name'] not in ['.', '..']:
                    stack.append(e)
    except Exception as e:
        print(f"[Koihime] Error buscando TAG: {e}")
    
    return None


class KoihimeReader(ContainerReader):
    
    MAX_PREVIEW_SIZE = 4 * 1024 * 1024
    
    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        super().__init__(data, filename, parent_iso, parent_path)
        
        self.entries = []
        self.total_files = 0
        self.entry = None
        self.tag_entries = []
        
        self.load()
    
    def _get_icon(self, ext):
        icons = {
            'prs': '🗜️',
            'sn': '📊',
            'pf': '📦',
            'bin': '📦',
            'tm2': '🖼️',
            'ico': '🖼️',
            'ahx': '🎵',
            'wav': '🔊',
            'ogg': '🎵',
            'txt': '📝',
            'dat': '📊'
        }
        return icons.get(ext, '📄')
    
    def load(self):
        try:
            print(f"[Koihime] Cargando archivo: {self.filename}")
            
            if not self.data:
                print("[Koihime] ERROR: No hay datos")
                return
            
            if len(self.data) < 16:
                print("[Koihime] ERROR: Archivo demasiado pequeno")
                return
            
            if self.data[:16] != BIN_MAGIC:
                print(f"[Koihime] Magic incorrecto: {self.data[:16]!r}")
                print("[Koihime] Este no es un archivo BIN de Koihime Musou")
                return
            
            print("[Koihime] Magic BIN verificado correctamente")
            
            if not self.parent_iso:
                print("[Koihime] ERROR: No hay ISO cargada")
                return
            
            tag_entry = find_tag_file(self.parent_iso, self.filename)
            
            if not tag_entry:
                print(f"[Koihime] ERROR: No se encontro archivo TAG para {self.filename}")
                return
            
            print(f"[Koihime] Encontrado TAG: {tag_entry['name']}")
            
            tag_data = self.parent_iso.read_file_data(tag_entry['location'], tag_entry['size'])
            
            if not tag_data:
                print("[Koihime] ERROR: No se pudo leer el archivo TAG")
                return
            
            if len(tag_data) < 16 or tag_data[:16] != TAG_MAGIC:
                print("[Koihime] ERROR: Magic TAG incorrecto")
                return
            
            self.tag_entries = parse_tag_data(tag_data)
            
            if not self.tag_entries:
                print("[Koihime] ERROR: No se pudieron parsear entradas del TAG")
                return
            
            print(f"[Koihime] Entradas parseadas: {len(self.tag_entries)}")
            
            valid_count = 0
            total_bytes = 0
            bin_data = self.data
            bin_size = len(bin_data)
            
            for idx, entry in enumerate(self.tag_entries):
                if entry.bin_offset >= bin_size or entry.comp_size == 0 or entry.bin_offset < 0:
                    name = f"file_{idx:04d}.bin"
                    ext = 'bin'
                    icon = '📦'
                    valid = False
                else:
                    valid = True
                    valid_count += 1
                    total_bytes += entry.comp_size
                    
                    ext = entry.name.rsplit(".", 1)[-1].lower() if "." in entry.name else 'bin'
                    icon = self._get_icon(ext)
                    name = entry.name
                
                self.entries.append({
                    'index': idx,
                    'name': name,
                    'full_path': entry.name if entry.is_named else f"__anonymous/{name}",
                    'is_directory': False,
                    'offset': entry.bin_offset,
                    'size': entry.comp_size,
                    'ext': ext,
                    'icon': icon,
                    'type': f"Koihime File ({ext.upper()})",
                    'valid': valid,
                    'cflag': entry.cflag,
                    'is_named': entry.is_named
                })
                
                if (idx + 1) % 500 == 0:
                    print(f"[Koihime] Procesados {idx + 1}/{len(self.tag_entries)} archivos...")
            
            self.total_files = valid_count
            print(f"[Koihime] Cargados {valid_count}/{len(self.tag_entries)} archivos")
            print(f"[Koihime] Tamaño total: {total_bytes:,} bytes ({total_bytes/1048576:.2f} MB)")
            
        except Exception as e:
            print(f"[Koihime] Error en load: {e}")
            import traceback
            traceback.print_exc()
    
    def get_entries(self):
        return self.entries
    
    def get_file_data(self, index):
        if index < 0 or index >= len(self.entries):
            return None
        
        if not self.entry:
            print("[Koihime] ERROR: self.entry is None")
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
            print(f"[Koihime] Error get_file_data: {e}")
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
        named = sum(1 for e in self.entries if e.get('is_named', False) and e.get('valid', True))
        anon = sum(1 for e in self.entries if not e.get('is_named', True) and e.get('valid', True))
        
        return {
            'files': self.total_files,
            'named_files': named,
            'anonymous_files': anon,
            'directories': 0,
            'total_size': total_size,
            'type': 'Koihime Musou BIN/TAG Container'
        }


class KoihimePlugin(ContainerPlugin):
    
    plugin_name = "Koihime Musou DODnSE"
    plugin_version = "1.0"
    plugin_author = "Huziad"
    plugin_description = "Support for Koihime Musou DATA.BIN and VOICE.BIN containers"
    
    file_extensions = ['.bin']
    file_names = ['DATA.BIN', 'VOICE.BIN', 'data.bin', 'voice.bin']
    icon = "⚔️📦"
    container_type_name = "Koihime BIN Container"
    priority = 100
    
    @classmethod
    def can_handle(cls, filename, data, iso_reader=None, entries=None):
        name_upper = filename.upper()
        
        if name_upper.endswith('.BIN') and (name_upper.startswith('DATA') or name_upper.startswith('VOICE')):
            print(f"[Koihime] Verificando archivo: {filename}")
            
            if data and len(data) >= 16:
                if data[:16] == BIN_MAGIC:
                    print("[Koihime] Magic BIN de Koihime detectado - aceptando")
                    return True, 100
                else:
                    print(f"[Koihime] Magic incorrecto ({data[:16]!r}) - no es Koihime")
                    return False, 0
            
            return False, 0
        
        return False, 0
    
    @classmethod
    def create_reader(cls, entry, iso_reader, data=None):
        if data is None:
            data = iso_reader.read_file_data(entry['location'], entry['size'])
        
        reader = KoihimeReader(data, entry['name'], iso_reader, entry['full_path'])
        
        reader.entry = entry
        
        return reader
