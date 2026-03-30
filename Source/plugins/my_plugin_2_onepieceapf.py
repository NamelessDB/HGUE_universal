"""
Plugin for One Piece APF/FSM containers (PS2 - Ganbarion)
Formato: APF -> FSM_v1.x (subcontenedores)
"""

import struct
import os
from dataclasses import dataclass
from .plugin_base import ContainerPlugin, ContainerReader


# ─────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────

FSM_V12_MAGIC = b'FSM_v1.2'
FSM_V11_MAGIC = b'FSM_v1.1'
NAME_MAGIC    = b'\x12\x07\x01\x04'
EXT_SEP       = b'\xe7\x0a'


# ─────────────────────────────────────────────
# STRUCTS
# ─────────────────────────────────────────────

@dataclass
class SubFSM:
    offset: int
    filename: str
    payload_offset: int
    payload_size: int


# ─────────────────────────────────────────────
# UTILS
# ─────────────────────────────────────────────

def extract_filename(meta: bytes) -> str:
    pos = meta.find(NAME_MAGIC)
    if pos < 0:
        return ""

    name = ""
    for b in meta[pos + 4: pos + 36]:
        if 0x20 <= b < 0x7F and b != 0xE7:
            name += chr(b)
        elif name:
            break

    ext = ""
    ext_pos = meta.find(EXT_SEP, pos)
    if ext_pos >= 0:
        ext_raw = meta[ext_pos + 2: ext_pos + 10]
        ext = "".join(chr(b) for b in ext_raw if 0x20 <= b < 0x7F)

    if name and ext:
        return f"{name}.{ext.strip('.')}"
    return name


def parse_subfsm(data, offset, size):
    if offset < 0 or offset + 0x60 > size:
        return None

    if data[offset+8:offset+16] not in (FSM_V12_MAGIC, FSM_V11_MAGIC):
        return None

    data_rel = struct.unpack_from('<I', data, offset + 0x18)[0]
    data_start = offset + data_rel

    filename = ""
    payload_offset = data_start

    # buscar metadata
    for i in range(4):
        e_off = offset + 0x20 + i * 16
        f0, unc, comp, f3 = struct.unpack_from('<4I', data, e_off)

        if f0 < 0x10000 and comp == 0 and 0 < unc <= 512:
            meta_off = data_start + f0
            meta_end = meta_off + unc

            if meta_end <= size:
                meta = data[meta_off:meta_end]
                name = extract_filename(meta)
                if name:
                    filename = name
                payload_offset = meta_end
            break

    return SubFSM(offset, filename, payload_offset, 0)


# ─────────────────────────────────────────────
# READER
# ─────────────────────────────────────────────

class APFReader(ContainerReader):

    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        super().__init__(data, filename, parent_iso, parent_path)
        self.load()

    def load(self):
        data = self.data
        size = len(data)

        subs = []
        pos = 0

        # escaneo FSMs
        while pos < size - 16:
            if data[pos:pos+8] in (FSM_V12_MAGIC, FSM_V11_MAGIC):
                sub = parse_subfsm(data, pos - 8, size)
                if sub:
                    subs.append(sub)
                pos += 0x10
            else:
                pos += 8

        subs.sort(key=lambda s: s.offset)

        # calcular tamaños reales
        for i, s in enumerate(subs):
            next_off = subs[i+1].offset if i+1 < len(subs) else size
            s.payload_size = max(0, next_off - s.payload_offset)

        # construir entries (ESTILO TUYO)
        self.entries = []

        for i, s in enumerate(subs):
            name = s.filename or f"file_{i:04d}.bin"
            ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''

            icon_map = {
                'tm2': '🖼️',
                'tpl': '🖼️',
                'bin': '📦',
                'dat': '📊'
            }

            self.entries.append({
                'index': i,
                'name': name,
                'full_path': name,
                'is_directory': False,
                'offset': s.payload_offset,
                'size': s.payload_size,
                'ext': ext,
                'icon': icon_map.get(ext, '📄'),
                'type': f"APF File ({ext.upper() if ext else 'BIN'})"
            })

        print(f"[APF] Loaded {len(self.entries)} files")

    def get_entries(self):
        return self.entries

    def get_file_data(self, index):
        e = self.entries[index]
        return self.data[e['offset']: e['offset'] + e['size']]

    def extract_file(self, index, output_path):
        e = self.entries[index]
        data = self.get_file_data(index)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(data)

        return True, f"Extracted: {e['name']}"


# ─────────────────────────────────────────────
# PLUGIN
# ─────────────────────────────────────────────

class APFOnePiecePlugin(ContainerPlugin):

    plugin_name = "One Piece APF"
    plugin_version = "1.0"
    plugin_author = "OGA2 + ChatGPT"
    plugin_description = "Extractor APF/FSM (PS2)"

    file_extensions = ['.apf']
    file_magic_bytes = {b'FSM_v1.': 8}

    icon = "🏴‍☠️"
    container_type_name = "APF Container"
    priority = 90

    @classmethod
    def can_handle(cls, filename, data, iso_reader=None, entries=None):
        name = filename.lower()

        if name.endswith(".apf"):
            return True, 90

        if data and len(data) > 16 and data[8:16].startswith(b'FSM_v1.'):
            return True, 95

        return False, 0

    @classmethod
    def create_reader(cls, entry, iso_reader, data=None):

        if data is None and iso_reader:
            data = iso_reader.read_file_data(
                entry['location'],
                entry['size']
            )

        return APFReader(
            data,
            entry['name'],
            iso_reader,
            entry['full_path']
        )
