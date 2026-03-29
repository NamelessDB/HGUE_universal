"""
Module for reading DBU files (Dragon Ball Z Sagas)
Based on working extraction script provided by user.
"""
import os
import struct

class DBUReader:
    """Class for reading DBU files from Dragon Ball Z Sagas"""

    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        self.data = data
        self.filename = filename
        self.parent_iso = parent_iso
        self.parent_path = parent_path
        self.entries = []
        self.file_count = 0
        self._parse_dbu()

    def _parse_dbu(self):
        """Parse DBU using the exact logic from the working script"""
        try:
            if len(self.data) < 0x20:
                print("File too small to be DBU")
                return

            # Use a BytesIO to mimic file pointer
            from io import BytesIO
            f = BytesIO(self.data)

            # Leer y descartar primera línea (size line)
            first_line = f.readline().decode('ascii', errors='ignore').strip()
            try:
                header_size = int(first_line)
            except ValueError:
                header_size = 0

            # Leer el texto DBLMerge (header_size bytes)
            dbmerge_text = f.read(header_size).decode('ascii', errors='ignore')
            # Obtener lista de rutas originales (desde "-PARAMLIST" hasta ".dbu")
            paths = []
            parts = dbmerge_text.split()
            if "-PARAMLIST" in parts:
                idx = parts.index("-PARAMLIST") + 1
                for p in parts[idx:]:
                    if p.lower().endswith(".dbu"):
                        break
                    # Normalizar separadores de ruta
                    paths.append(p.replace('\\', os.sep))

            print(f"Extracted {len(paths)} file paths from header")

            # Saltar metadatos binarios (8+4+4+4+4 bytes)
            f.read(8)   # ID string (8 bytes)
            f.read(4)   # DUMMY
            f.read(4)   # ZERO
            f.read(4)   # DUMMY
            f.read(4)   # DUMMY

            # Leer ARCHIVE_SIZE (4 bytes little-endian)
            arch_size_bytes = f.read(4)
            archive_size = struct.unpack('<I', arch_size_bytes)[0] if len(arch_size_bytes) == 4 else 0
            if archive_size == 0:
                archive_size = len(self.data)  # fallback

            # Recorrer bloques internos
            extracted = []
            entry_index = 0
            offset = f.tell()
            while offset < archive_size:
                f.seek(offset)
                header = f.read(4 + 4 + 2 + 0x36)   # DUMMY(4), SIZE(4), FLAGS(2), DUMMY(0x36)
                if len(header) < 0x3E:
                    break

                size = struct.unpack('<I', header[4:8])[0]
                flags = struct.unpack('<H', header[8:10])[0]
                marker = header[10:14]   # first 4 bytes of the 0x36 dummy

                if marker != b'1000':
                    offset += 1
                    continue

                content_offset = offset + 0x40   # 64 bytes ahead (header size = 4+4+2+0x36 = 0x40)

                if flags == 1 and size == 0x100:
                    # Name block – skip it
                    offset = content_offset + size
                    continue

                # Normal file entry
                if entry_index < len(paths):
                    name = paths[entry_index]
                else:
                    name = f"file_{entry_index:04d}.bin"

                # Sanitize path (remove leading slashes)
                name = name.lstrip(os.sep)

                self.entries.append({
                    'index': entry_index,
                    'name': name,
                    'offset': content_offset,
                    'size': size,
                    'full_path': name,
                    'is_special': False
                })
                entry_index += 1
                offset = content_offset + size

            self.file_count = len(self.entries)
            print(f"DBU loaded successfully with {self.file_count} files")

        except Exception as e:
            print(f"Error loading DBU: {e}")
            import traceback
            traceback.print_exc()

    def get_entries(self):
        """Return list of file entries (real files, not name entries)"""
        return self.entries

    def extract_file(self, index, output_path):
        """Extract a specific file from DBU"""
        if index < 0 or index >= len(self.entries):
            return False, "Invalid index"

        entry = self.entries[index]
        start = entry['offset']
        size = entry['size']

        if start + size <= len(self.data):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(self.data[start:start+size])
            return True, f"Extracted: {entry['name']}"
        return False, f"Invalid file data"

    def get_file_data(self, index):
        """Return raw data of a specific file"""
        if index < 0 or index >= len(self.entries):
            return None
        entry = self.entries[index]
        start = entry['offset']
        size = entry['size']
        if start + size <= len(self.data):
            return self.data[start:start+size]
        return None
