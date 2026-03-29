"""
Module for reading SPK files (Siren 2 PS2 game format)
Based on the original extractor script
"""
import struct
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

def read_u32_le(buf: bytes, off: int) -> int:
    """Read 32-bit little-endian unsigned integer"""
    return struct.unpack_from("<I", buf, off)[0]

def read_cstring(buf: bytes, start: int) -> str:
    """Read null-terminated string"""
    if start < 0 or start >= len(buf):
        return ""
    end = buf.find(b"\x00", start)
    if end == -1:
        end = len(buf)
    raw = buf[start:end]
    try:
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return raw.decode("latin-1", errors="ignore")

class SPKEntry:
    """Entry for SPK file"""
    __slots__ = ("index", "filename_off", "archive_filename_off", "data_off", "data_size", "filename", "rom_name")
    
    def __init__(self, index: int, filename_off: int, archive_filename_off: int, data_off: int, data_size: int):
        self.index = index
        self.filename_off = filename_off
        self.archive_filename_off = archive_filename_off
        self.data_off = data_off
        self.data_size = data_size
        self.filename: str = ""
        self.rom_name: str = ""

class SPKReader:
    """Class for reading SPK files from Siren 2 PS2 game"""
    
    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        self.data = data
        self.filename = filename
        self.parent_iso = parent_iso
        self.parent_path = parent_path
        self.header = {}
        self.entries: List[SPKEntry] = []
        self.tail_offset = 0
        self.tail: bytes = b""
        self.file_count = 0
        self.load_spk()
    
    def load_spk(self):
        """Load and parse the SPK file - exactly like the original script"""
        try:
            if len(self.data) < 0x20:
                print(f"File too small to be SPK")
                return
            
            # Check magic "SLPK"
            if self.data[:4] != b"SLPK":
                print(f"Invalid magic: {self.data[:4]}")
                return
            
            print(f"Valid SPK signature found: SLPK")
            
            # Read header - exactly like original
            unknown1 = read_u32_le(self.data, 0x04)
            fileCount = read_u32_le(self.data, 0x08)
            filenamesOffset = read_u32_le(self.data, 0x0C)
            empty = read_u32_le(self.data, 0x10)
            unknown2 = read_u32_le(self.data, 0x14)
            unknown3 = read_u32_le(self.data, 0x18)
            unknown4 = read_u32_le(self.data, 0x1C)
            
            self.header = {
                "unknown1": unknown1,
                "fileCount": fileCount,
                "filenamesOffset": filenamesOffset,
                "empty": empty,
                "unknown2": unknown2,
                "unknown3": unknown3,
                "unknown4": unknown4,
                "file_size": len(self.data),
            }
            
            self.file_count = fileCount
            self.tail_offset = filenamesOffset
            
            if self.tail_offset >= len(self.data):
                print(f"filenamesOffset out of bounds: {self.tail_offset}")
                return
            
            # Directory starts at 0x20, 16 bytes per entry
            dir_start = 0x20
            dir_len = fileCount * 16
            dir_end = dir_start + dir_len
            
            if dir_end > len(self.data):
                print(f"Directory exceeds file size: {dir_end} > {len(self.data)}")
                return
            
            print(f"SPK Info:")
            print(f"  Files: {fileCount}")
            print(f"  Filenames Offset: 0x{filenamesOffset:08X}")
            
            # Parse directory entries - exactly like original
            self.entries = []
            for i in range(fileCount):
                off = dir_start + i * 16
                filenameOffset = read_u32_le(self.data, off + 0)
                archiveFilenameOffset = read_u32_le(self.data, off + 4)
                dataOffset = read_u32_le(self.data, off + 8)
                dataSize = read_u32_le(self.data, off + 12)
                
                self.entries.append(SPKEntry(i, filenameOffset, archiveFilenameOffset, dataOffset, dataSize))
            
            # Tail (filename table) - exactly like original
            self.tail = self.data[self.tail_offset:]
            
            # Resolve names from tail (offsets are relative to tail)
            for e in self.entries:
                e.filename = read_cstring(self.tail, e.filename_off)
                e.rom_name = read_cstring(self.tail, e.archive_filename_off)
                
                # Clean up names
                if not e.filename:
                    e.filename = f"file_{e.index:04d}.bin"
                if not e.rom_name:
                    e.rom_name = f"rom.{(e.index % 100):03d}"
                
                # Print first few entries for debugging
                if e.index < 10:
                    print(f"  Entry {e.index:04d}: {e.filename} -> ROM: {e.rom_name} (off={e.data_off}, size={e.data_size})")
            
            print(f"SPK loaded successfully with {len(self.entries)} files")
            
        except Exception as e:
            print(f"Error loading SPK: {e}")
            import traceback
            traceback.print_exc()
    
    def get_entries(self):
        """Get list of entries"""
        return self.entries
    
    def discover_roms(self, folder: str) -> Dict[str, str]:
        """Discover ROM files in folder - like original"""
        mapping: Dict[str, str] = {}
        if not folder or not os.path.exists(folder):
            return mapping
        
        for f in os.listdir(folder):
            filepath = os.path.join(folder, f)
            if not os.path.isfile(filepath):
                continue
            name = f.lower()
            # Look for rom.000, rom.001, etc.
            if name.startswith('rom.') or name.startswith('rom_'):
                mapping[name] = filepath
                print(f"  Found ROM: {name}")
        
        return mapping
    
    def choose_offset_factor(self, rom_map: Dict[str, str]) -> int:
        """Heuristic: return 1 (bytes) or 2048 (sectors) - like original"""
        sample = self.entries[: min(200, len(self.entries))]
        score = {1: 0, 2048: 0}
        rom_sizes = {}
        
        for rom_name, rom_path in rom_map.items():
            try:
                rom_sizes[rom_name] = os.path.getsize(rom_path)
            except:
                pass
        
        for e in sample:
            rom = rom_map.get(e.rom_name.lower())
            if not rom:
                continue
            size = rom_sizes.get(e.rom_name.lower(), 0)
            if size == 0:
                continue
            for factor in (1, 2048):
                off = e.data_off * factor
                if 0 <= off <= size and 0 <= e.data_size <= size and off + e.data_size <= size:
                    score[factor] += 1
        
        # tie -> 1 (like original)
        return 1 if score[1] >= score[2048] else 2048
    
    def extract_file(self, index, output_path, rom_files_dir=None):
        """Extract file from SPK using ROM files - like original extract_one"""
        if index < 0 or index >= len(self.entries):
            return False, "Invalid index"
        
        entry = self.entries[index]
        
        if not rom_files_dir:
            return False, "ROM files directory not provided"
        
        # Discover ROM files
        rom_map = self.discover_roms(rom_files_dir)
        
        # Find ROM file for this entry
        rom_key = entry.rom_name.lower()
        rom_path = rom_map.get(rom_key)
        
        if not rom_path:
            # Try without extension
            for key, path in rom_map.items():
                if rom_key in key:
                    rom_path = path
                    break
        
        if not rom_path or not os.path.exists(rom_path):
            return False, f"ROM file not found: {entry.rom_name}"
        
        # Choose offset factor
        factor = self.choose_offset_factor(rom_map)
        
        # Normalize path - like original
        rel = (entry.filename or f"__unnamed_{entry.index:05d}.bin").lstrip("/\\").replace("\\", "/")
        out_path = Path(output_path)
        if out_path.suffix == '':
            out_path = out_path.parent / rel
        
        try:
            with open(rom_path, 'rb') as rf:
                rf.seek(entry.data_off * factor)
                remaining = entry.data_size
                buf_size = 1024 * 1024
                
                # Create directory if needed
                out_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(out_path, 'wb') as wf:
                    while remaining > 0:
                        chunk = rf.read(min(buf_size, remaining))
                        if not chunk:
                            break
                        wf.write(chunk)
                        remaining -= len(chunk)
            
            return True, f"Extracted: {rel}"
            
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def get_required_roms(self):
        """Get list of ROM files required for extraction"""
        roms = set()
        for e in self.entries:
            if e.rom_name:
                roms.add(e.rom_name)
        return sorted(list(roms))
