"""
Module for reading EFS files (Encrypted File System / Container format)
Based on extraction script provided
"""
import struct
import os
import re
from pathlib import Path

class EFSReader:
    """Class for reading EFS files"""
    
    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        self.data = data
        self.filename = filename
        self.parent_iso = parent_iso
        self.parent_path = parent_path
        self.entries = []
        self.file_count = 0
        self.load_efs()
    
    def load_efs(self):
        """Load and parse the EFS file"""
        try:
            if len(self.data) < 0x20:
                print(f"File too small to be EFS")
                return
            
            # Read header values
            h1 = struct.unpack_from('<I', self.data, 4)[0]
            offs1 = struct.unpack_from('<I', self.data, 0x10)[0]
            offs2 = struct.unpack_from('<I', self.data, 0x14)[0]
            
            print(f"EFS Info:")
            print(f"  H1: 0x{h1:08X}")
            print(f"  Name1 Offset: 0x{offs1:08X}")
            print(f"  Name2 Offset: 0x{offs2:08X}")
            
            # Get name1 (ASCII, null-terminated)
            name1 = ""
            if offs1 < len(self.data):
                end = self.data.find(b'\x00', offs1)
                if end == -1:
                    end = len(self.data)
                name1 = self.data[offs1:end].decode('ascii', errors='ignore')
            
            # Get name2 (ASCII, cleaned)
            name2 = ""
            if offs2 < len(self.data):
                end = self.data.find(b'\x00', offs2)
                if end == -1:
                    end = len(self.data)
                raw2 = self.data[offs2:end]
                # Remove non-alphanumeric characters except . and _
                name2 = re.sub(rb'[^A-Za-z0-9._]', b'', raw2).decode('ascii', errors='ignore')
            
            full_name = name1 + name2
            print(f"  Name1: '{name1}'")
            print(f"  Name2: '{name2}'")
            print(f"  Full Name: '{full_name}'")
            
            # Calculate data offset and size
            data_offset = h1 + 0x20
            data_size = len(self.data) - data_offset
            
            print(f"  Data Offset: 0x{data_offset:08X}")
            print(f"  Data Size: {data_size} bytes")
            
            # Create entries
            # Entry 1: main data file (.DIM or name1)
            if name1:
                entry1_name = name1
            else:
                entry1_name = f"{self.filename}.dat"
            
            self.entries.append({
                'index': 0,
                'name': entry1_name,
                'offset': data_offset,
                'size': data_size,
                'full_path': entry1_name,
                'is_header': False
            })
            
            # Entry 2: header file (.HDR or full_name)
            if full_name:
                entry2_name = full_name
            else:
                entry2_name = f"{self.filename}.hdr"
            
            self.entries.append({
                'index': 1,
                'name': entry2_name,
                'offset': 0,
                'size': 0,
                'full_path': entry2_name,
                'is_header': True
            })
            
            self.file_count = len(self.entries)
            print(f"EFS loaded successfully with {self.file_count} files")
            
        except Exception as e:
            print(f"Error loading EFS: {e}")
            import traceback
            traceback.print_exc()
    
    def get_entries(self):
        """Return list of entries"""
        return self.entries
    
    def extract_file(self, index, output_path):
        """Extract a specific file from EFS"""
        if index < 0 or index >= len(self.entries):
            return False, "Invalid index"
        
        entry = self.entries[index]
        
        if entry.get('is_header', False):
            # Header file is empty
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(b'')
            return True, f"Extracted (empty header): {entry['name']}"
        
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
        if entry.get('is_header', False):
            return b''
        
        start = entry['offset']
        size = entry['size']
        if start + size <= len(self.data):
            return self.data[start:start+size]
        return None
