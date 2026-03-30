"""
Plugin for Seigi no Mikata (PS2) - DATA.BIN container
Soporta:
 - DATA.BIN
 - DATA.OFS
 - DATA.FNL
"""

import struct
import os
from .plugin_base import ContainerPlugin, ContainerReader


# ─────────────────────────────────────────────────────────────
# Parsers
# ─────────────────────────────────────────────────────────────

def parse_fnl_data(data: bytes):
    names = []
    i = 0

    while i < len(data):
        length = data[i]

        if length == 0:
            i += 1
            continue

        actual_len = length - 1

        if actual_len <= 0 or i + length > len(data):
            i += 1
            continue

        name_bytes = data[i + 1 : i + length]

        try:
            names.append(name_bytes.decode("ascii"))
        except:
            names.append(name_bytes.decode("latin-1", errors="replace"))

        i += length

    return names


def parse_ofs_data(data: bytes):
    entries = []
    record_size = 16
    count = len(data) // record_size

    for i in range(count):
        chunk = data[i * record_size : (i + 1) * record_size]
        unk, offset, size, _ = struct.unpack_from("<IIII", chunk)

        if size > 0:
            entries.append((unk, offset, size))

    return entries


# ─────────────────────────────────────────────────────────────
# Reader
# ─────────────────────────────────────────────────────────────

class SeigiReader(ContainerReader):

    MAX_PREVIEW_SIZE = 4 * 1024 * 1024  # 4MB

    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        super().__init__(data, filename, parent_iso, parent_path)

        self.entries = []
        self.total_files = 0
        self.entry = None  # referencia al DATA.BIN en ISO

        self.load()

    def load(self):
        try:
            print("[Seigi] Loading DATA.BIN...")

            fnl_entry = self._find_file("DATA.FNL")
            ofs_entry = self._find_file("DATA.OFS")

            if not fnl_entry or not ofs_entry:
                print("[Seigi] ERROR: Missing DATA.FNL or DATA.OFS")
                return

            fnl_data = self.parent_iso.read_file_data(fnl_entry['location'], fnl_entry['size'])
            ofs_data = self.parent_iso.read_file_data(ofs_entry['location'], ofs_entry['size'])

            names = parse_fnl_data(fnl_data)
            ofs_entries = parse_ofs_data(ofs_data)

            count = min(len(names), len(ofs_entries))

            for i in range(count):
                name = names[i].replace("\\", "/").lstrip("/")
                _, offset, size = ofs_entries[i]

                ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''

                self.entries.append({
                    'index': i,
                    'name': os.path.basename(name),
                    'full_path': name,
                    'is_directory': False,
                    'offset': offset,
                    'size': size,
                    'ext': ext,
                    'icon': self._get_icon(ext),
                    'type': f"Seigi File ({ext.upper() if ext else 'BIN'})"
                })

                self.total_files += 1

            print(f"[Seigi] Loaded {self.total_files} files")

        except Exception as e:
            print(f"[Seigi] Load error: {e}")
            import traceback
            traceback.print_exc()

    def _get_icon(self, ext):
        return {
            'bin': '📦',
            'pss': '🎬',
            'adx': '🎵',
            'vag': '🎵',
            'tm2': '🖼️'
        }.get(ext, '📄')

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
                    if e['name'].lower() == filename.lower():
                        return e

                    if e['is_directory'] and e['name'] not in ['.', '..']:
                        stack.append(e)

        except Exception as e:
            print(f"[Seigi] Search error: {e}")

        return None

    # ─────────────────────────────────────────
    # REQUIRED METHODS
    # ─────────────────────────────────────────

    def get_entries(self):
        return self.entries

    def get_hierarchical_entries(self):
        root = {}

        for entry in self.entries:
            path_parts = entry['full_path'].split('/')
            current = root

            for part in path_parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            current[path_parts[-1]] = entry

        return root

    # 🔥 FIX HEX VIEWER
    def get_file_data(self, index):
        if index < 0 or index >= len(self.entries):
            return None

        if not self.entry:
            print("[Seigi] ERROR: self.entry is None")
            return None

        entry = self.entries[index]

        try:
            offset = entry['offset']
            size = entry['size']

            if size <= 0:
                return None

            # Leer TODO el DATA.BIN
            container_data = self.parent_iso.read_file_data(
                self.entry['location'],
                self.entry['size']
            )

            if not container_data:
                return None

            # Extraer slice
            file_data = container_data[offset:offset + size]

            # Limitar preview (hex viewer)
            return file_data[:self.MAX_PREVIEW_SIZE]

        except Exception as e:
            print(f"[Seigi] get_file_data error: {e}")
            return None

    def extract_file(self, index, output_path):
        if not self.entry:
            return False, "Invalid container reference"

        entry = self.entries[index]

        try:
            container_data = self.parent_iso.read_file_data(
                self.entry['location'],
                self.entry['size']
            )

            data = container_data[entry['offset']:entry['offset'] + entry['size']]

            if not data:
                return False, "Failed to read data"

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, 'wb') as f:
                f.write(data)

            return True, f"Extracted: {entry['name']}"

        except Exception as e:
            return False, str(e)

    def get_stats(self):
        total_size = sum(e['size'] for e in self.entries)

        return {
            'files': self.total_files,
            'directories': 0,
            'total_size': total_size,
            'type': 'Seigi no Mikata DATA.BIN'
        }


# ─────────────────────────────────────────────────────────────
# Plugin
# ─────────────────────────────────────────────────────────────

class SeigiPlugin(ContainerPlugin):

    plugin_name = "Seigi no Mikata"
    plugin_version = "1.3"
    plugin_author = "Huziad"
    plugin_description = "Support for Seigi no Mikata DATA.BIN container"

    file_extensions = ['.bin']
    file_names = ['DATA.BIN']
    icon = "⚖️📦"
    container_type_name = "Seigi DATA.BIN"
    priority = 80

    @classmethod
    def can_handle(cls, filename, data, iso_reader=None, entries=None):
        if filename.lower() == "data.bin":
            return True, 100
        return False, 0

    @classmethod
    def create_reader(cls, entry, iso_reader, data=None):
        if data is None:
            data = iso_reader.read_file_data(entry['location'], entry['size'])

        reader = SeigiReader(data, entry['name'], iso_reader, entry['full_path'])

        # 🔥 CLAVE para hex viewer
        reader.entry = entry

        return reader
