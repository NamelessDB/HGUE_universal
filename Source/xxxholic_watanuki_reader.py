"""
XXXHOLiC Watanuki no Izayoi Souwa (PS2) - Archive Extractor
============================================================
Clase para leer y extraer archivos de los pares .HD / .BIN

Formato del archivo:
  - data##.bin : Archivo contenedor principal
      • Bytes 0..N-1  : Tabla de nombres en texto ASCII, separados por \r\n
      • Bytes N..2047 : Padding con 0xFF hasta la frontera de sector (2048 bytes)
      • Bytes 2048+   : Datos de los archivos
  - data##.hd  : Tabla de offsets — uint32 LE, uno por archivo
"""

import struct
import os
from pathlib import Path


class XXXHolicReader:
    """Class for reading XXXHOLiC Watanuki no Izayoi Souwa HD/BIN archives"""
    
    def __init__(self, hd_data, bin_data, filename="", parent_iso=None, parent_path=""):
        self.hd_data = hd_data
        self.bin_data = bin_data
        self.filename = filename
        self.parent_iso = parent_iso
        self.parent_path = parent_path
        self.entries = []
        self.file_count = 0
        self.bin_size = len(bin_data)
        self.load_archive()
    
    def _read_name_table(self) -> list[str]:
        """Lee la tabla de nombres del inicio del .bin"""
        end = min(2048, len(self.bin_data))
        text_region = self.bin_data[:end]
        ff_pos = text_region.find(b'\xff')
        if ff_pos != -1:
            text_region = text_region[:ff_pos]
        lines = text_region.split(b'\r\n')
        return [line.decode('ascii', errors='replace') for line in lines if line]
    
    def _parse_hd(self) -> list[int]:
        """Parsea el archivo .hd como una lista de uint32 LE"""
        count = len(self.hd_data) // 4
        return list(struct.unpack(f'<{count}I', self.hd_data[:count * 4]))
    
    def _build_file_table(self, names: list[str], offsets: list[int]) -> list[dict]:
        """Construye la tabla de archivos combinando nombres y offsets"""
        if len(names) != len(offsets):
            n = min(len(names), len(offsets))
            names = names[:n]
            offsets = offsets[:n]
        
        indexed = sorted(enumerate(offsets), key=lambda x: x[1])
        
        table = []
        for pos, (file_idx, offset) in enumerate(indexed):
            if pos + 1 < len(indexed):
                next_offset = indexed[pos + 1][1]
            else:
                next_offset = self.bin_size
            size = max(0, next_offset - offset)
            
            name = names[file_idx] if file_idx < len(names) else f'file_{file_idx}'
            ext = Path(name).suffix.upper().lstrip('.') if '.' in name else ''
            
            type_map = {
                'PAK': 'PAK Archive',
                'FAC': 'FAC Data', 
                'TM2': 'TM2 Texture',
                'LST': 'List File',
                'BIN': 'Binary Data',
            }
            
            icon_map = {
                'PAK': '📦 ',
                'FAC': '📊 ',
                'TM2': '🖼️ ',
                'LST': '📋 ',
                'BIN': '📄 ',
            }
            
            table.append({
                'index': file_idx,
                'name': name,
                'ext': ext,
                'offset': offset,
                'size': size,
                'type': type_map.get(ext, 'Data File'),
                'icon': icon_map.get(ext, '📄 '),
                'full_path': name
            })
        
        table.sort(key=lambda e: e['index'])
        return table
    
    def load_archive(self):
        """Load and parse HD/BIN archive"""
        try:
            if len(self.hd_data) < 4:
                print(f"HD file too small")
                return
            
            names = self._read_name_table()
            offsets = self._parse_hd()
            self.entries = self._build_file_table(names, offsets)
            self.file_count = len(self.entries)
            
            print(f"XXXHOLiC archive loaded successfully with {self.file_count} files")
            
        except Exception as e:
            print(f"Error loading XXXHOLiC archive: {e}")
            import traceback
            traceback.print_exc()
    
    def get_entries(self):
        """Get list of all entries"""
        return self.entries
    
    def get_entry(self, index):
        """Get a specific entry by index"""
        if 0 <= index < len(self.entries):
            return self.entries[index]
        return None
    
    def extract_file(self, index, output_path):
        """Extract a specific file from the BIN archive"""
        if index < 0 or index >= len(self.entries):
            return False, "Invalid index"
        
        entry = self.entries[index]
        start = entry['offset']
        size = entry['size']
        
        if start + size <= len(self.bin_data):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(self.bin_data[start:start+size])
            return True, f"Extracted: {entry['name']}"
        
        return False, f"Invalid file data (offset=0x{start:08X}, size={size})"
    
    def get_file_data(self, index):
        """Get data of a specific file"""
        if index < 0 or index >= len(self.entries):
            return None
        
        entry = self.entries[index]
        start = entry['offset']
        size = entry['size']
        
        if start + size <= len(self.bin_data):
            return self.bin_data[start:start+size]
        
        return None
    
    def get_stats(self):
        """Get statistics about the archive"""
        total_size = sum(e['size'] for e in self.entries)
        
        ext_counts = {}
        for entry in self.entries:
            ext = entry['ext'] if entry['ext'] else 'unknown'
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
        
        return {
            'total_files': len(self.entries),
            'total_size': total_size,
            'extensions': ext_counts,
            'format': 'XXXHOLiC HD/BIN Archive',
            'bin_size': self.bin_size
        }


def find_matching_hd_bin_pairs(entries):
    """Encuentra pares de archivos .HD y .BIN en una lista de entradas"""
    pairs = []
    hd_files = {}
    bin_files = {}
    
    for entry in entries:
        name_lower = entry['name'].lower()
        if name_lower.endswith('.hd'):
            base = name_lower[:-3]
            hd_files[base] = entry
        elif name_lower.endswith('.bin'):
            base = name_lower[:-4]
            bin_files[base] = entry
    
    for base, hd_entry in hd_files.items():
        if base in bin_files:
            pairs.append((hd_entry, bin_files[base]))
    
    return sorted(pairs, key=lambda x: x[0]['name'])
