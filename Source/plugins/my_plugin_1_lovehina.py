"""
Plugin for Love Hina Gorgeous CH - aphro.idx/aphro.img archive format
Formato: DFI (PS2) - Sector size: 2048 bytes
Soporta ~11,603 archivos en estructura jerárquica de directorios
"""
import struct
import os
import threading
from pathlib import Path
from .plugin_base import ContainerPlugin, ContainerReader

# Constantes del formato
SECTOR_SIZE = 2048
NAME_TABLE_OFFSET = 0x2D540  # Offset absoluto en el .idx donde empiezan los nombres
NUM_RECORDS = 11603
HEADER_SIZE = 16
RECORD_SIZE = 16
MAGIC = b'DFI\x00'


class LoveHinaReader(ContainerReader):
    """Reader for Love Hina Gorgeous CH aphro.idx/aphro.img archives"""
    
    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        super().__init__(data, filename, parent_iso, parent_path)
        self.img_data = None  # Will be set separately
        self.img_path = None  # Path to img file in ISO
        self.total_files = 0
        self.total_dirs = 0
        self.load()
    
    def set_img_data(self, img_data):
        """Set the IMG data (aphro.img)"""
        self.img_data = img_data
    
    def set_img_path(self, img_path):
        """Set the IMG file path within ISO"""
        self.img_path = img_path
    
    def load(self):
        """Load and parse the IDX file"""
        try:
            if len(self.data) < 0x100:
                print(f"File too small to be Love Hina IDX")
                return
            
            # Verificar magic
            if self.data[:4] != MAGIC:
                print(f"Invalid magic: {self.data[:4]}")
                return
            
            print(f"Valid Love Hina IDX signature found")
            
            # Construir tabla de nombres (null-terminated strings)
            names = []
            pos = NAME_TABLE_OFFSET
            while pos < len(self.data):
                try:
                    end = self.data.index(b'\x00', pos)
                except ValueError:
                    end = len(self.data)
                names.append(self.data[pos:end].decode('ascii', errors='replace'))
                pos = end + 1
            
            # Leer los registros
            raw_entries = []
            for i in range(NUM_RECORDS):
                off = HEADER_SIZE + i * RECORD_SIZE
                if off + RECORD_SIZE > len(self.data):
                    break
                w0, w1, w2, w3 = struct.unpack_from('<IIII', self.data, off)
                is_dir = (w0 & 0xFFFF) == 1
                child_count = (w0 >> 16) & 0xFFFF
                name = names[i] if i < len(names) else f'entry_{i}'
                raw_entries.append({
                    'name': name,
                    'is_dir': is_dir,
                    'child_count': child_count,
                    'sector': w2,
                    'size': w3,
                })
            
            # Reconstruir árbol DFS → lista plana con rutas completas
            self.entries = []
            path_stack = []  # [(path_str, remaining_direct_children)]
            
            for i, e in enumerate(raw_entries):
                parent = path_stack[-1][0] if path_stack else ''
                full = (parent + '/' + e['name']).lstrip('/')
                
                if e['is_dir']:
                    self.entries.append({
                        'index': i,
                        'name': e['name'],
                        'full_path': full,
                        'is_directory': True,
                        'size': 0,
                        'sector': 0,
                        'child_count': e['child_count']
                    })
                    self.total_dirs += 1
                    if e['child_count'] > 0:
                        path_stack.append([full, e['child_count']])
                else:
                    # Determinar tipo de archivo por extensión
                    ext = full.rsplit('.', 1)[-1].lower() if '.' in full else ''
                    icon_map = {
                        'bin': '📦', 'dat': '📊', 'txt': '📝',
                        'tm2': '🖼️', 'vag': '🎵', 'adx': '🎵',
                        'pss': '🎬', 'bik': '🎬'
                    }
                    icon = icon_map.get(ext, '📄')
                    
                    self.entries.append({
                        'index': i,
                        'name': e['name'],
                        'full_path': full,
                        'is_directory': False,
                        'size': e['size'],
                        'sector': e['sector'],
                        'offset': e['sector'] * SECTOR_SIZE,
                        'ext': ext,
                        'icon': icon,
                        'type': f"Love Hina File ({ext.upper() if ext else 'BIN'})"
                    })
                    self.total_files += 1
                
                # Decrementar contador de hijos en cada nivel y desapilar si agotados
                if path_stack:
                    path_stack[-1][1] -= 1
                    while path_stack and path_stack[-1][1] <= 0:
                        path_stack.pop()
                        if path_stack:
                            path_stack[-1][1] -= 1
            
            print(f"Love Hina IDX loaded: {self.total_files} files, {self.total_dirs} directories")
            
        except Exception as e:
            print(f"Error loading Love Hina IDX: {e}")
            import traceback
            traceback.print_exc()
    
    def get_entries(self):
        """Get list of entries (for flat display)"""
        return self.entries
    
    def get_hierarchical_entries(self):
        """Get entries organized in hierarchical structure"""
        # Build tree structure
        root = {}
        for entry in self.entries:
            if entry['is_directory']:
                continue  # Skip directories for file tree
            path_parts = entry['full_path'].split('/')
            current = root
            for part in path_parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[path_parts[-1]] = entry
        return root
    
    def extract_file(self, index, output_path):
        """Extract a specific file from IMG"""
        if index < 0 or index >= len(self.entries):
            return False, "Invalid index"
        
        entry = self.entries[index]
        if entry['is_directory']:
            return False, "Cannot extract directory"
        
        start = entry['offset']
        size = entry['size']
        
        # Check if we have IMG data loaded
        if self.img_data is None and self.parent_iso and self.img_path:
            try:
                # Load IMG data from ISO
                img_entry = self._find_img_in_iso()
                if img_entry:
                    self.img_data = self.parent_iso.read_file_data(
                        img_entry['location'], img_entry['size']
                    )
                    print(f"Loaded IMG data: {len(self.img_data)} bytes")
            except Exception as e:
                return False, f"Could not load IMG data: {str(e)}"
        
        if self.img_data and start + size <= len(self.img_data):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(self.img_data[start:start+size])
            return True, f"Extracted: {entry['name']}"
        elif self.parent_iso and self.img_path:
            # Fallback: read directly from ISO
            try:
                img_entry = self._find_img_in_iso()
                if img_entry:
                    data = self.parent_iso.read_file_data_range(
                        img_entry['location'], start, size
                    )
                    if data:
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        with open(output_path, 'wb') as f:
                            f.write(data)
                        return True, f"Extracted: {entry['name']}"
            except Exception as e:
                return False, f"Error reading from ISO: {str(e)}"
        
        return False, f"Invalid file data (offset=0x{start:08X}, size={size})"
    
    def _find_img_in_iso(self):
        """Find the corresponding IMG file in the ISO"""
        if not self.parent_iso:
            return None
        
        # Determine IMG filename (should be same as IDX but with .img)
        img_filename = self.filename.replace('.idx', '.img').replace('.IDX', '.IMG')
        
        # Search in the same directory as the IDX
        parent_path = os.path.dirname(self.parent_path)
        
        # Read directory contents
        entries = self.parent_iso.read_directory(
            self.parent_iso.root_directory['location'],
            self.parent_iso.root_directory['full_path']
        )
        
        # Search for IMG file
        for entry in entries:
            if entry['name'].lower() == img_filename.lower():
                return entry
        
        # If not found, search recursively
        return self._find_file_recursive(img_filename)
    
    def _find_file_recursive(self, filename):
        """Recursively search for a file in the ISO"""
        try:
            stack = [self.parent_iso.root_directory]
            while stack:
                dir_entry = stack.pop()
                entries = self.parent_iso.read_directory(
                    dir_entry['location'], 
                    dir_entry['full_path']
                )
                for entry in entries:
                    if entry['name'].lower() == filename.lower() and not entry['is_directory']:
                        return entry
                    if entry['is_directory'] and entry['name'] not in ['.', '..']:
                        stack.append(entry)
        except Exception as e:
            print(f"Error searching for {filename}: {e}")
        return None
    
    def get_file_data(self, index):
        """Get data of a specific file"""
        if index < 0 or index >= len(self.entries):
            return None
        
        entry = self.entries[index]
        if entry['is_directory']:
            return None
        
        start = entry['offset']
        size = entry['size']
        
        if self.img_data and start + size <= len(self.img_data):
            return self.img_data[start:start+size]
        
        return None
    
    def get_stats(self):
        """Get statistics about the archive"""
        total_size = sum(e['size'] for e in self.entries if not e['is_directory'])
        return {
            'files': self.total_files,
            'directories': self.total_dirs,
            'total_size': total_size,
            'type': 'Love Hina Gorgeous CH (aphro.idx/aphro.img)'
        }


class LoveHinaPlugin(ContainerPlugin):
    """Plugin for Love Hina Gorgeous CH aphro.idx files"""
    
    plugin_name = "Love Hina Gorgeous CH"
    plugin_version = "1.0"
    plugin_author = "Huziad"
    plugin_description = "Support for Love Hina Gorgeous CH aphro.idx/aphro.img archives"
    
    # File detection
    file_extensions = ['.idx']
    file_magic_bytes = {b'DFI\x00': 0}
    file_names = ['aphro.idx', 'APHRO.IDX']
    
    # UI settings
    icon = "💕📦"  # Heart + package icon
    container_type_name = "Love Hina Archive (aphro.idx)"
    priority = 90  # High priority for specific detection
    
    @classmethod
    def can_handle(cls, filename, data, iso_reader=None, entries=None):
        """
        Check if this plugin can handle the given file
        """
        name_lower = filename.lower()
        
        # Check by exact filename first (highest priority)
        if name_lower == 'aphro.idx':
            # Verify magic bytes
            if data and len(data) >= 4:
                magic = data[:4]
                if magic == b'DFI\x00':
                    return True, 100  # Highest priority for exact match + magic
            return True, 90  # Still high priority even without magic check
        
        # Check by extension
        if name_lower.endswith('.idx'):
            # Verify magic bytes
            if data and len(data) >= 4:
                magic = data[:4]
                if magic == b'DFI\x00':
                    return True, 85  # High priority for magic match
        
        return False, 0
    
    @classmethod
    def create_reader(cls, entry, iso_reader, data=None):
        """
        Create a reader instance for this container
        """
        if data is None and iso_reader:
            data = iso_reader.read_file_data(entry['location'], entry['size'])
        
        reader = LoveHinaReader(data, entry['name'], iso_reader, entry['full_path'])
        
        # Try to find and load the corresponding IMG file
        try:
            # Determine IMG filename
            img_filename = entry['name'].replace('.idx', '.img').replace('.IDX', '.IMG')
            
            # Search for IMG in the same directory
            parent_path = os.path.dirname(entry['full_path'])
            entries = iso_reader.read_directory(
                iso_reader.root_directory['location'],
                iso_reader.root_directory['full_path']
            )
            
            for e in entries:
                if e['name'].lower() == img_filename.lower() and not e['is_directory']:
                    # Load IMG data into memory for fast access
                    print(f"[LoveHina] Loading IMG file: {e['name']} ({e['size']} bytes)")
                    img_data = iso_reader.read_file_data(e['location'], e['size'])
                    reader.set_img_data(img_data)
                    reader.set_img_path(e['full_path'])
                    break
            else:
                print(f"[LoveHina] Warning: Could not find IMG file: {img_filename}")
                
        except Exception as e:
            print(f"[LoveHina] Error loading IMG: {e}")
        
        return reader
