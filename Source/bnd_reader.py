"""
Module for reading BND files (various games)
Based on QuickBMS script structure
"""
import struct
import os

class BNDReader:
    """Class for reading BND files (various games)"""
    
    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        self.data = data
        self.filename = filename
        self.parent_iso = parent_iso
        self.parent_path = parent_path
        self.entries = []
        self.file_count = 0
        self.load_bnd()
    
    def _read_string(self, f, pos):
        """Read null-terminated string from data at position"""
        if pos >= len(self.data):
            return ""
        end = self.data.find(b'\x00', pos)
        if end == -1:
            end = len(self.data)
        return self.data[pos:end].decode('utf-8', errors='ignore')
    
    def load_bnd(self):
        """Load and parse the BND file"""
        try:
            if len(self.data) < 0x10:
                print(f"File too small to be BND")
                return
            
            pos = 0xC
            if pos + 4 > len(self.data):
                print("Cannot read file count")
                return
            
            self.file_count = struct.unpack('<I', self.data[pos:pos+4])[0]
            pos += 4
            print(f"BND file count: {self.file_count}")
            
            temp_pos = pos
            
            for i in range(self.file_count):
                if temp_pos + 16 > len(self.data):
                    break
                
                file_id = struct.unpack('<I', self.data[temp_pos:temp_pos+4])[0]
                offset = struct.unpack('<I', self.data[temp_pos+4:temp_pos+8])[0]
                size = struct.unpack('<I', self.data[temp_pos+8:temp_pos+12])[0]
                name_offset = struct.unpack('<I', self.data[temp_pos+12:temp_pos+16])[0]
                
                temp_pos += 16
                
                # Get filename from name_offset
                name = f"file_{i:04d}.bin"
                if name_offset > 0 and name_offset < len(self.data):
                    name_str = self._read_string(self.data, name_offset)
                    if name_str:
                        name = name_str
                
                # Check if offset and size are valid
                if offset + size <= len(self.data):
                    self.entries.append({
                        'index': i,
                        'offset': offset,
                        'size': size,
                        'name': name,
                        'full_path': name,
                        'is_special': False
                    })
                    print(f"  Entry {i:04d}: {name} (offset=0x{offset:08X}, size={size})")
                else:
                    print(f"  Entry {i:04d}: {name} - INVALID (offset=0x{offset:08X}, size={size})")
            
            self.file_count = len(self.entries)
            print(f"BND loaded successfully with {self.file_count} files")
            
        except Exception as e:
            print(f"Error loading BND: {e}")
            import traceback
            traceback.print_exc()
    
    def get_entries(self):
        """Return list of entries"""
        return self.entries
    
    def extract_file(self, index, output_path):
        """Extract a specific file from BND"""
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
        return False, f"Invalid file data (offset=0x{start:08X}, size={size})"
    
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
