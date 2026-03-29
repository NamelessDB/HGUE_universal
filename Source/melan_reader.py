"""
Melan Reader for Suzumiya Haruhi no Tomadoi (PS2)
Format: DFI (Data File Index) - melan.idx + melan.img
"""
import struct
import os

SECTOR_SIZE = 2048


class DFIRecord:
    __slots__ = ("flags", "name", "img_offset", "size", "idx_offset", "is_dir", "children")

    def __init__(self, flags, name, img_offset, size, idx_offset):
        self.flags = flags
        self.name = name
        self.img_offset = img_offset
        self.size = size
        self.idx_offset = idx_offset
        self.is_dir = (flags & 0xFFFF) == 0x0001
        self.children = []

    @property
    def child_count(self):
        return (self.flags >> 16) & 0xFFFF

    def __repr__(self):
        return f"<{'DIR' if self.is_dir else 'FILE'} '{self.name}' off={self.img_offset} sz={self.size}>"


class MelanReader:
    """Class for reading melan.idx + melan.img files (Suzumiya Haruhi no Tomadoi)"""
    
    def __init__(self, idx_data, img_data, filename="", parent_iso=None, parent_path=""):
        self.idx_data = idx_data
        self.img_data = img_data
        self.filename = filename
        self.parent_iso = parent_iso
        self.parent_path = parent_path
        self.records = []
        self.roots = []
        self.file_count = 0
        self.load_melan()
    
    def load_melan(self):
        """Load and parse melan.idx file"""
        try:
            if len(self.idx_data) < 4:
                print(f"IDX file too small")
                return
            
            # Check magic "DFI\x00"
            magic = self.idx_data[:4]
            if magic != b"DFI\x00":
                print(f"Invalid magic: {magic!r} (expected b'DFI\\x00')")
                return
            
            print(f"Valid DFI signature found")
            
            # String table offset at offset 20
            str_table_off = struct.unpack_from("<I", self.idx_data, 20)[0]
            print(f"String table offset: 0x{str_table_off:08X}")
            
            # Parse records
            self.records = []
            for i in range(48, str_table_off, 16):
                if i + 16 > len(self.idx_data):
                    break
                
                flags, b, c, d = struct.unpack_from("<4I", self.idx_data, i)
                
                # Name: data[b + i] until null
                name_pos = b + i
                name = ""
                if 0 < name_pos < len(self.idx_data):
                    end = self.idx_data.find(b"\x00", name_pos)
                    if end > name_pos:
                        name = self.idx_data[name_pos:end].decode("latin-1", errors="replace")
                
                self.records.append(DFIRecord(flags, name, c, d, i))
            
            print(f"Parsed {len(self.records)} records")
            
            # Build tree structure
            self._build_tree()
            
            self.file_count = len(self.records)
            print(f"Melan loaded successfully with {len(self.records)} records")
            
        except Exception as e:
            print(f"Error loading Melan: {e}")
            import traceback
            traceback.print_exc()
    
    def _build_tree(self):
        """Build directory tree from flat records (iterative)"""
        stack = []
        self.roots = []
        
        for rec in self.records:
            if stack:
                parent, remaining = stack[-1]
                parent.children.append(rec)
                remaining -= 1
                if remaining <= 0:
                    stack.pop()
                else:
                    stack[-1] = (parent, remaining)
            else:
                self.roots.append(rec)
            
            if rec.is_dir and rec.child_count > 0:
                stack.append((rec, rec.child_count))
    
    def get_entries(self):
        """Get list of all entries (flat)"""
        return self.records
    
    def get_root_entries(self):
        """Get root directory entries"""
        return self.roots
    
    def collect_files(self, records=None):
        """Collect all file records (iterative)"""
        if records is None:
            records = self.roots
        
        files = []
        stack = list(records)
        while stack:
            r = stack.pop()
            if r.is_dir:
                stack.extend(reversed(r.children))
            else:
                files.append(r)
        return files
    
    def extract_file(self, index, output_path):
        """Extract a specific file from melan.img"""
        if index < 0 or index >= len(self.records):
            return False, "Invalid index"
        
        record = self.records[index]
        if record.is_dir:
            return False, "Cannot extract directory"
        
        start = record.img_offset * SECTOR_SIZE
        size = record.size
        
        if start + size <= len(self.img_data):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(self.img_data[start:start+size])
            return True, f"Extracted: {record.name}"
        
        return False, f"Invalid file data (offset=0x{start:08X}, size={size})"
    
    def extract_file_by_record(self, record, output_path):
        """Extract a file by record object"""
        if record.is_dir:
            return False, "Cannot extract directory"
        
        start = record.img_offset * SECTOR_SIZE
        size = record.size
        
        if start + size <= len(self.img_data):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(self.img_data[start:start+size])
            return True, f"Extracted: {record.name}"
        
        return False, f"Invalid file data"
    
    def get_file_data(self, index):
        """Get data of a specific file"""
        if index < 0 or index >= len(self.records):
            return None
        
        record = self.records[index]
        if record.is_dir:
            return None
        
        start = record.img_offset * SECTOR_SIZE
        size = record.size
        
        if start + size <= len(self.img_data):
            return self.img_data[start:start+size]
        
        return None
    
    def get_record_by_index(self, index):
        """Get record by index"""
        if 0 <= index < len(self.records):
            return self.records[index]
        return None
    
    def get_stats(self):
        """Get statistics about the archive"""
        files = [r for r in self.records if not r.is_dir]
        dirs = [r for r in self.records if r.is_dir]
        total_size = sum(r.size for r in files)
        
        # Count extensions
        exts = {}
        for r in files:
            ext = r.name.rsplit(".", 1)[-1].lower() if "." in r.name else "?"
            exts[ext] = exts.get(ext, 0) + 1
        
        return {
            'total_records': len(self.records),
            'files': len(files),
            'directories': len(dirs),
            'total_size': total_size,
            'extensions': exts
        }
