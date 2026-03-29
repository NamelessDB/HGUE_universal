"""
Ben 10: Protector of Earth (PS2) - WAD Extractor
=======================================================
Parsea game.dir para extraer archivos de game.wad.

Estructura de game.dir:
  Cada entrada = 72 bytes (0x48):
    +0x00  uint32 LE  -> número de sector en game.wad (offset_bytes = sector * 2048)
    +0x04  char[60]   -> nombre de archivo (null-padded)
    +0x40  uint32 LE  -> siempre 0 (reservado)
    +0x44  uint32 LE  -> tamaño del archivo en bytes

Total: 423 archivos (.bik, .psm, .pss, .txt)
"""

import struct
import os
from pathlib import Path

# Constantes
ENTRY_SIZE = 0x48          # 72 bytes por entrada
SECTOR_SIZE = 2048         # tamaño de sector PS2


class Ben10WADReader:
    """Class for reading Ben 10: Protector of Earth WAD files (game.dir + game.wad)"""
    
    def __init__(self, dir_data, wad_data, filename="", parent_iso=None, parent_path=""):
        self.dir_data = dir_data
        self.wad_data = wad_data
        self.filename = filename
        self.parent_iso = parent_iso
        self.parent_path = parent_path
        self.entries = []
        self.file_count = 0
        self.load_wad()
    
    def load_wad(self):
        """Load and parse game.dir to get file entries"""
        try:
            if len(self.dir_data) < ENTRY_SIZE:
                print(f"DIR file too small")
                return
            
            self.entries = []
            num_entries = len(self.dir_data) // ENTRY_SIZE
            
            for i in range(num_entries):
                base = i * ENTRY_SIZE
                if base + ENTRY_SIZE > len(self.dir_data):
                    break
                
                chunk = self.dir_data[base:base + ENTRY_SIZE]
                
                # Leer sector (uint32 LE)
                sector = struct.unpack_from("<I", chunk, 0x00)[0]
                
                # Leer nombre (60 bytes null-padded)
                raw_name = chunk[0x04:0x04 + 60]
                name = raw_name.rstrip(b"\x00").decode("latin-1", errors="replace")
                
                # Leer tamaño (uint32 LE) en offset 0x44
                size = struct.unpack_from("<I", chunk, 0x44)[0]
                
                if name:  # ignorar entradas vacías
                    # Determinar extensión y tipo
                    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                    
                    # Mapeo de extensiones a tipos
                    type_map = {
                        "bik": "Bink Video",
                        "pss": "PSS Video",
                        "psm": "PSM Texture",
                        "txt": "Text File"
                    }
                    
                    # Ícono según extensión
                    icon_map = {
                        "bik": "🎬 ",
                        "pss": "🎬 ",
                        "psm": "🖼️ ",
                        "txt": "📝 "
                    }
                    
                    self.entries.append({
                        'index': i,
                        'name': name,
                        'ext': ext,
                        'sector': sector,
                        'offset': sector * SECTOR_SIZE,
                        'size': size,
                        'type': type_map.get(ext, "Unknown"),
                        'icon': icon_map.get(ext, "📄 "),
                        'full_path': name
                    })
            
            self.file_count = len(self.entries)
            print(f"Ben 10 WAD loaded successfully with {self.file_count} files")
            print(f"  File types: {self._get_extensions_summary()}")
            
        except Exception as e:
            print(f"Error loading Ben 10 WAD: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_extensions_summary(self):
        """Get summary of file types"""
        ext_counts = {}
        for entry in self.entries:
            ext_counts[entry['ext']] = ext_counts.get(entry['ext'], 0) + 1
        return ", ".join(f"{k}:{v}" for k, v in ext_counts.items())
    
    def get_entries(self):
        """Get list of all entries"""
        return self.entries
    
    def get_entry(self, index):
        """Get a specific entry by index"""
        if 0 <= index < len(self.entries):
            return self.entries[index]
        return None
    
    def extract_file(self, index, output_path):
        """Extract a specific file from game.wad"""
        if index < 0 or index >= len(self.entries):
            return False, "Invalid index"
        
        entry = self.entries[index]
        start = entry['offset']
        size = entry['size']
        
        if start + size <= len(self.wad_data):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(self.wad_data[start:start+size])
            return True, f"Extracted: {entry['name']}"
        
        return False, f"Invalid file data (offset=0x{start:08X}, size={size})"
    
    def get_file_data(self, index):
        """Get data of a specific file"""
        if index < 0 or index >= len(self.entries):
            return None
        
        entry = self.entries[index]
        start = entry['offset']
        size = entry['size']
        
        if start + size <= len(self.wad_data):
            return self.wad_data[start:start+size]
        
        return None
    
    def get_stats(self):
        """Get statistics about the archive"""
        total_size = sum(e['size'] for e in self.entries)
        
        # Contar por extensión
        ext_counts = {}
        for entry in self.entries:
            ext = entry['ext'] if entry['ext'] else "unknown"
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
        
        return {
            'total_files': len(self.entries),
            'total_size': total_size,
            'extensions': ext_counts,
            'format': 'Ben 10 WAD (game.dir + game.wad)'
        }
    
    def get_file_type_info(self):
        """Get detailed information about file types"""
        types = {}
        for entry in self.entries:
            t = entry['type']
            if t not in types:
                types[t] = []
            types[t].append(entry['name'])
        
        return types


def parse_dir_to_entries(dir_data):
    """
    Parse game.dir data and return list of entries without WAD data.
    Useful for preview before loading full WAD.
    """
    entries = []
    
    if len(dir_data) < ENTRY_SIZE:
        return entries
    
    num_entries = len(dir_data) // ENTRY_SIZE
    
    for i in range(num_entries):
        base = i * ENTRY_SIZE
        if base + ENTRY_SIZE > len(dir_data):
            break
        
        chunk = dir_data[base:base + ENTRY_SIZE]
        sector = struct.unpack_from("<I", chunk, 0x00)[0]
        size = struct.unpack_from("<I", chunk, 0x44)[0]
        raw_name = chunk[0x04:0x04 + 60]
        name = raw_name.rstrip(b"\x00").decode("latin-1", errors="replace")
        
        if name:
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            
            icon_map = {
                "bik": "🎬 ",
                "pss": "🎬 ",
                "psm": "🖼️ ",
                "txt": "📝 "
            }
            
            entries.append({
                'index': i,
                'name': name,
                'ext': ext,
                'sector': sector,
                'offset': sector * SECTOR_SIZE,
                'size': size,
                'icon': icon_map.get(ext, "📄 "),
                'type': "Video" if ext in ("bik", "pss") else "Texture" if ext == "psm" else "Text" if ext == "txt" else "Unknown"
            })
    
    return entries


def detect_ben10_wad(wad_data, dir_data=None):
    """
    Detect if the data appears to be a Ben 10 WAD file.
    This is a heuristic detection based on structure.
    """
    # If we have dir_data, check if it has valid structure
    if dir_data and len(dir_data) >= ENTRY_SIZE:
        # Check if first entry has reasonable sector and size
        try:
            first_entry = dir_data[:ENTRY_SIZE]
            sector = struct.unpack_from("<I", first_entry, 0x00)[0]
            size = struct.unpack_from("<I", first_entry, 0x44)[0]
            
            # Check if sector and size are plausible
            # game.wad is usually around 1-2GB, so max sector ~ 1M
            if 0 <= sector < 1000000 and 0 <= size < 100 * 1024 * 1024:
                # Check if name is printable
                raw_name = first_entry[0x04:0x04 + 60]
                name = raw_name.rstrip(b"\x00")
                if name and all(32 <= b < 127 or b == 0 for b in name[:20]):
                    return True
        except:
            pass
    
    # If we have wad_data, check for common patterns
    if wad_data and len(wad_data) > 0:
        # Check first few bytes for known signatures
        # .bik files start with "BIK"
        # .pss files have specific header
        # .psm files start with "PSM"
        
        if len(wad_data) > 4:
            first_bytes = wad_data[:4]
            if first_bytes == b"BIKf" or first_bytes == b"BIKd":
                return True
            if first_bytes == b"PSS\x00":
                return True
            if first_bytes == b"PSM\x00":
                return True
    
    return False


def get_wad_info(wad_data):
    """Get basic information about the WAD file"""
    info = {
        'size': len(wad_data),
        'size_mb': len(wad_data) / (1024 * 1024),
        'sector_count': len(wad_data) // SECTOR_SIZE if len(wad_data) >= SECTOR_SIZE else 0
    }
    
    # Try to detect file types at common offsets
    info['detected_types'] = []
    
    # Check first sector for BIK files
    if len(wad_data) > 0x800:
        for offset in [0, 0x800, 0x1000, 0x1800, 0x2000]:
            if offset + 4 <= len(wad_data):
                magic = wad_data[offset:offset+4]
                if magic == b"BIKf" or magic == b"BIKd":
                    info['detected_types'].append(f"BIK Video at sector {offset // SECTOR_SIZE}")
                elif magic == b"PSS\x00":
                    info['detected_types'].append(f"PSS Video at sector {offset // SECTOR_SIZE}")
                elif magic == b"PSM\x00":
                    info['detected_types'].append(f"PSM Texture at sector {offset // SECTOR_SIZE}")
    
    return info
