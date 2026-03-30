"""
HOG Plugin - Hannah Montana: Spotlight World
"""

import struct
import os
from .plugin_base import ContainerPlugin, ContainerReader

# ─────────────────────────────────────────
# 📦 READER
# ─────────────────────────────────────────

class HogReader(ContainerReader):

    ENTRY_SIZE = 16

    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        super().__init__(data, filename, parent_iso, parent_path)

        self.entries = []
        self.total_files = 0

        self.load()  



    def load(self):
        try:
            print("[HOG] Loading...")

            data = self.data

            version  = struct.unpack_from("<H", data, 0)[0]
            unk1     = struct.unpack_from("<H", data, 2)[0]
            table_off= struct.unpack_from("<I", data, 4)[0]
            num_files= struct.unpack_from("<I", data, 16)[0]
            names_sz = struct.unpack_from("<I", data, 20)[0]

            print(f"[HOG] Version: {version} | Files: {num_files}")

            if num_files == 0 or num_files > 100000:
                print("[HOG] Invalid file count")
                return

            # ───────────────────────── tabla
            entry_table_size = num_files * self.ENTRY_SIZE
            table_raw = data[table_off:table_off + entry_table_size]

            entries_raw = []
            for i in range(num_files):
                off = i * self.ENTRY_SIZE
                name_off, file_off, file_size, checksum = struct.unpack_from("<IIII", table_raw, off)
                entries_raw.append((name_off, file_off, file_size, checksum))

            # ───────────────────────── nombres
            names_start = table_off + entry_table_size
            names_raw = data[names_start:names_start + names_sz + 64]

            def read_cstring(offset):
                rel = offset - names_start
                if rel < 0 or rel >= len(names_raw):
                    return f"<offset_{offset:#x}>"

                end = names_raw.find(b"\x00", rel)
                if end == -1:
                    return names_raw[rel:rel+64].decode("ascii", errors="replace")

                return names_raw[rel:end].decode("ascii", errors="replace")

            # ───────────────────────── entries

            for i, (name_off, file_off, file_size, checksum) in enumerate(entries_raw):
                name = read_cstring(name_off)

                self.entries.append({
                    "index": i,
                    "name": os.path.basename(name),
                    "full_path": name.replace("\\", "/"),
                    "offset": file_off,
                    "size": file_size,
                    "checksum": checksum,
                    "is_directory": False,
                    "type": "HOG File",
                    "icon": "🎤"
                })

            self.total_files = len(self.entries)

            print(f"[HOG] Loaded {self.total_files} files")

        except Exception as e:
            print(f"[HOG] Load error: {e}")

    # ─────────────────────────────────────

    def get_entries(self):
        return self.entries

    def get_hierarchical_entries(self):
        root = {}

        for entry in self.entries:
            parts = entry["full_path"].split("/")
            current = root

            for p in parts[:-1]:
                current = current.setdefault(p, {})

            current[parts[-1]] = entry

        return root

    def get_file_data(self, index):
        if index < 0 or index >= len(self.entries):
            return None

        entry = self.entries[index]

        try:
            start = entry["offset"]
            end = start + entry["size"]

            return self.data[start:end]

        except Exception as e:
            print(f"[HOG] Read error: {e}")
            return None

    def extract_file(self, index, output_path):
        data = self.get_file_data(index)

        if not data:
            return False, "Failed"

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, "wb") as f:
                f.write(data)

            return True, "OK"

        except Exception as e:
            return False, str(e)

    def get_stats(self):
        return {
            "files": self.total_files,
            "type": "HOG (Hannah Montana)"
        }

# ─────────────────────────────────────────
# 🔌 PLUGIN
# ─────────────────────────────────────────

class HogPlugin(ContainerPlugin):

    plugin_name = "HOG Hannah Montana"
    plugin_version = "1.1 (fixed load)"
    plugin_author = "ChatGPT"

    file_extensions = [".hog"]
    icon = "🎤📦"
    container_type_name = "HOG Archive"
    priority = 90

    @classmethod
    def can_handle(cls, filename, data, iso_reader=None, entries=None):
        if len(data) < 4:
            return False, 0

        if data[0:4] == b"\x01\x00\x02\x00":
            return True, 100

        return False, 0

    @classmethod
    def create_reader(cls, entry, iso_reader, data=None):
        if data is None:
            data = iso_reader.read_file_data(entry["location"], entry["size"])

        return HogReader(data, entry["name"], iso_reader, entry["full_path"])
