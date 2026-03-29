"""
Module for reading GZIP compressed files (Budokai HD Collection)
Detects and decompresses GZIP streams embedded in files
"""
import struct
import gzip
import io
import os

class GZIPReader:
    """Class for reading GZIP compressed files (Budokai HD Collection)"""
    
    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        self.data = data
        self.filename = filename
        self.parent_iso = parent_iso
        self.parent_path = parent_path
        self.entries = []
        self.file_count = 0
        self.decompressed_data = None
        self.is_gzip = False
        self.load_gzip()
    
    def _read_int32_le(self, offset):
        """Read 32-bit little-endian integer"""
        if offset + 4 <= len(self.data):
            return struct.unpack('<I', self.data[offset:offset+4])[0]
        return 0
    
    def _parse_gzip_header(self, offset):
        """Parse GZIP header and return info"""
        if offset + 10 > len(self.data):
            return None
        
        id1, id2, cm, flg, mtime, xfl, os = struct.unpack(
            '<BBBBIBB', self.data[offset:offset+10]
        )
        
        # Check GZIP signature
        if id1 != 0x1F or id2 != 0x8B or cm != 0x08:
            return None
        
        result = {
            'offset': offset,
            'flg': flg,
            'mtime': mtime,
            'header_size': 10,
            'filename': None
        }
        
        pos = offset + 10
        
        # Extract extra fields (FEXTRA flag)
        if flg & 0x04:
            if pos + 2 <= len(self.data):
                xlen = struct.unpack('<H', self.data[pos:pos+2])[0]
                pos += 2 + xlen
        
        # Extract filename (FNAME flag)
        if flg & 0x08:
            name_end = self.data.find(b'\x00', pos)
            if name_end != -1:
                try:
                    result['filename'] = self.data[pos:name_end].decode('ascii', errors='replace')
                except:
                    result['filename'] = self.data[pos:name_end].hex()
                pos = name_end + 1
        
        # Extract comment (FCOMMENT flag)
        if flg & 0x10:
            comment_end = self.data.find(b'\x00', pos)
            if comment_end != -1:
                pos = comment_end + 1
        
        result['end_of_header'] = pos
        return result
    
    def _find_gzip_footer(self, start_offset):
        """Find GZIP footer (CRC32 + ISIZE)"""
        search_end = len(self.data) - 8
        
        for pos in range(search_end, start_offset + 10, -1):
            if pos + 8 > len(self.data):
                continue
            
            try:
                crc, isize = struct.unpack('<II', self.data[pos:pos+8])
            except:
                continue
            
            # Validate: ISIZE should be reasonable (< 100 MB)
            if isize > 0 and isize < 100 * 1024 * 1024:
                # This could be a footer
                total_size = (pos + 8) - start_offset
                if total_size > 18:  # Minimum: header (10) + footer (8)
                    return pos, total_size, crc, isize
        
        return None, None, None, None
    
    def _try_decompress(self, start_offset):
        """Try to decompress GZIP data from start_offset"""
        header = self._parse_gzip_header(start_offset)
        if not header:
            return None, None
        
        # Try to find footer
        footer_offset, total_size, crc, isize = self._find_gzip_footer(start_offset)
        
        if footer_offset:
            block_data = self.data[start_offset:footer_offset + 8]
            
            # Try to decompress
            try:
                decompressed = gzip.decompress(block_data)
                if len(decompressed) == isize or isize == 0:
                    return block_data, decompressed, header
            except:
                pass
        
        return None, None, None
    
    def load_gzip(self):
        """Check if the file is GZIP compressed and decompress"""
        try:
            # First, try to decompress the whole file as GZIP
            try:
                self.decompressed_data = gzip.decompress(self.data)
                self.is_gzip = True
                print(f"File is GZIP compressed, decompressed size: {len(self.decompressed_data)} bytes")
            except:
                pass
            
            # If not, try to find GZIP stream inside the file
            if not self.is_gzip:
                # Search for GZIP header (1F 8B 08)
                gzip_sig = b'\x1F\x8B\x08'
                pos = 0
                
                while True:
                    found = self.data.find(gzip_sig, pos)
                    if found == -1:
                        break
                    
                    # Try to extract GZIP stream from this position
                    block_data, decompressed, header = self._try_decompress(found)
                    
                    if block_data and decompressed:
                        self.is_gzip = True
                        self.decompressed_data = decompressed
                        filename = header.get('filename', self.filename) if header else self.filename
                        print(f"Found GZIP stream at offset 0x{found:08X}")
                        print(f"  Original size: {len(block_data)} bytes")
                        print(f"  Decompressed size: {len(decompressed)} bytes")
                        if header and header.get('filename'):
                            print(f"  Embedded filename: {header['filename']}")
                        break
                    
                    pos = found + 1
            
            # If we have decompressed data, create entries
            if self.is_gzip and self.decompressed_data:
                # Check if decompressed data is a container (AFS, etc.)
                # For now, we treat it as a single file
                self.entries.append({
                    'index': 0,
                    'name': self.filename.replace('.bin', '.out').replace('.gz', ''),
                    'offset': 0,
                    'size': len(self.decompressed_data),
                    'full_path': self.filename.replace('.bin', '.out').replace('.gz', ''),
                    'is_gzip': True,
                    'original_name': self.filename
                })
                self.file_count = 1
                print(f"GZIP file loaded successfully")
            else:
                print(f"File does not appear to be GZIP compressed")
                
        except Exception as e:
            print(f"Error loading GZIP: {e}")
            import traceback
            traceback.print_exc()
    
    def get_entries(self):
        """Return list of entries"""
        return self.entries
    
    def extract_file(self, index, output_path):
        """Extract decompressed file"""
        if index < 0 or index >= len(self.entries):
            return False, "Invalid index"
        
        entry = self.entries[index]
        
        if self.decompressed_data:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(self.decompressed_data)
            return True, f"Extracted decompressed: {entry['name']}"
        
        return False, "No decompressed data available"
    
    def get_file_data(self, index):
        """Return decompressed data"""
        if index < 0 or index >= len(self.entries):
            return None
        return self.decompressed_data
    
    def get_decompressed_data(self):
        """Return decompressed data"""
        return self.decompressed_data
