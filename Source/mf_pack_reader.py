"""
Module for reading MF Pack files (UFFA format - Fate/Stay Night PS2)
Based on the original MF Pack unpacker
"""
import struct
import os
import zlib

class LZSSDecoder:
    """LZSS decoder for MF Pack files"""
    
    # Constants
    RING_BUFF = 4096
    LONGEST_MATCH = 18
    TREE_NIL = RING_BUFF
    
    def __init__(self):
        self.mText = bytearray(self.LONGEST_MATCH + self.RING_BUFF - 1)
        self.mDad = [0] * (self.RING_BUFF + 1)
        self.mLSon = [0] * (self.RING_BUFF + 1)
        self.mRSon = [0] * (self.RING_BUFF + 257)
        self.mMatchPos = 0
        self.mMatchLen = 0
    
    def decode(self, data, expected_size):
        """Decode LZSS compressed data"""
        # Simple LZSS decoding
        output = bytearray()
        r = self.RING_BUFF - self.LONGEST_MATCH
        
        # Clear buffer
        for i in range(len(self.mText)):
            self.mText[i] = 0
        
        aFlag = 0
        i = 0
        data_len = len(data)
        
        while len(output) < expected_size and i < data_len:
            aFlag >>= 1
            if (aFlag & 256) == 0:
                if i >= data_len:
                    break
                c = data[i]
                i += 1
                aFlag = c | 0xFF00
            
            if (aFlag & 1) == 1:
                # Literal byte
                if i >= data_len:
                    break
                c = data[i]
                i += 1
                output.append(c)
                self.mText[r] = c
                r = (r + 1) & (self.RING_BUFF - 1)
            else:
                # Compressed block
                if i + 1 >= data_len:
                    break
                pos = data[i]
                i += 1
                flags = data[i]
                i += 1
                
                pos = pos | ((flags & 0xF0) << 4)
                length = (flags & 0x0F) + 2
                
                for k in range(length):
                    c = self.mText[(pos + k) & (self.RING_BUFF - 1)]
                    output.append(c)
                    self.mText[r] = c
                    r = (r + 1) & (self.RING_BUFF - 1)
        
        return bytes(output)


class MFPackReader:
    """Class for reading MF Pack files (UFFA format - Fate/Stay Night PS2)"""
    
    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        self.data = data
        self.filename = filename
        self.parent_iso = parent_iso
        self.parent_path = parent_path
        self.entries = []
        self.file_count = 0
        self.data_start = 0
        self.load_mf_pack()
    
    def load_mf_pack(self):
        """Load and parse the MF Pack file"""
        try:
            if len(self.data) < 0x10:
                print(f"File too small to be MF Pack")
                return
            
            # Check magic "MF" (0x464D)
            magic = struct.unpack('<H', self.data[0:2])[0]
            if magic != 0x464D:
                print(f"Invalid magic: 0x{magic:04X} (expected 0x464D)")
                return
            
            print(f"Valid MF Pack signature found: MF")
            
            # Read number of files
            self.file_count = struct.unpack('<I', self.data[4:8])[0]
            
            # Read data start offset
            self.data_start = struct.unpack('<I', self.data[8:12])[0]
            
            print(f"MF Pack Info:")
            print(f"  Files: {self.file_count}")
            print(f"  Data Start: 0x{self.data_start:08X}")
            
            # Read file entries (each entry is 16 bytes)
            entry_table = self.data[0x10:0x10 + self.file_count * 0x10]
            
            # Check for padding flag
            has_padding = False
            if self.data_start != self.file_count * 0x10 + 0x10:
                has_padding = True
                print(f"  Has padding: Yes")
            else:
                print(f"  Has padding: No")
            
            pos = 0
            self.entries = []
            
            for i in range(self.file_count):
                entry_pos = i * 0x10
                
                # Read entry data
                if entry_pos + 0x10 > len(entry_table):
                    break
                
                comp_size = struct.unpack('<I', entry_table[entry_pos:entry_pos+4])[0]
                data_pos = struct.unpack('<I', entry_table[entry_pos+4:entry_pos+8])[0]
                comp_flag = struct.unpack('<I', entry_table[entry_pos+8:entry_pos+12])[0]
                unc_size = struct.unpack('<I', entry_table[entry_pos+12:entry_pos+16])[0]
                
                # Calculate actual data position (data_start + offset)
                actual_data_pos = self.data_start + data_pos
                
                is_compressed = (comp_flag == 1)
                
                # Determine file extension based on content
                file_ext = self._determine_extension(actual_data_pos, comp_flag, unc_size)
                
                # Generate name
                name = f"file_{i+1:04d}{file_ext}"
                
                print(f"  Entry {i+1:04d}: {name} (comp={is_compressed}, offset=0x{actual_data_pos:08X}, size={unc_size})")
                
                self.entries.append({
                    'index': i,
                    'offset': actual_data_pos,
                    'size': unc_size,
                    'comp_size': comp_size,
                    'comp_flag': comp_flag,
                    'is_compressed': is_compressed,
                    'name': name,
                    'full_path': name
                })
            
            print(f"MF Pack loaded successfully with {len(self.entries)} files")
            
        except Exception as e:
            print(f"Error loading MF Pack: {e}")
            import traceback
            traceback.print_exc()
    
    def _determine_extension(self, offset, comp_flag, size):
        """Determine file extension by checking content"""
        try:
            if offset + 4 > len(self.data):
                return ".dat"
            
            if comp_flag == 1:
                # Compressed file - check after decompression
                # We'll check the uncompressed data
                return ".mf"  # Often .mf for MF Pack files
            else:
                # Check magic bytes
                magic = struct.unpack('<I', self.data[offset:offset+4])[0]
                if magic == 0x464D:  # "MF"
                    return ".mf"
                elif magic == 0x4D464D46:  # "MFMF"
                    return ".mf"
                else:
                    return ".dat"
        except:
            return ".dat"
    
    def get_entries(self):
        """Get list of entries"""
        return self.entries
    
    def extract_file(self, index, output_path):
        """Extract a specific file from MF Pack"""
        if index < 0 or index >= len(self.entries):
            return False, "Invalid index"
        
        entry = self.entries[index]
        start = entry['offset']
        comp_size = entry.get('comp_size', 0)
        size = entry['size']
        is_compressed = entry['is_compressed']
        
        # Determine where the data is
        if is_compressed:
            # Read compressed data
            if start + 0x10 > len(self.data):
                return False, "Invalid compressed data offset"
            
            # Skip header (UFFA magic + zero + size + zero)
            data_start = start + 0x10
            compressed_data = self.data[data_start:data_start + comp_size]
            
            # Decompress using LZSS
            try:
                decoder = LZSSDecoder()
                decompressed_data = decoder.decode(compressed_data, size)
                
                if len(decompressed_data) != size:
                    print(f"  Warning: Decompressed size mismatch: {len(decompressed_data)} vs {size}")
                
                # Create directory if needed
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                with open(output_path, 'wb') as f:
                    f.write(decompressed_data)
                
                return True, f"Extracted (decompressed): {entry['name']}"
                
            except Exception as e:
                return False, f"Decompression error: {str(e)}"
        else:
            # Uncompressed file
            if start + size > len(self.data):
                return False, "Invalid file data"
            
            # Create directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as f:
                f.write(self.data[start:start + size])
            
            return True, f"Extracted: {entry['name']}"
    
    def get_file_data(self, index):
        """Get data of a specific file"""
        if index < 0 or index >= len(self.entries):
            return None
        
        entry = self.entries[index]
        start = entry['offset']
        comp_size = entry.get('comp_size', 0)
        size = entry['size']
        is_compressed = entry['is_compressed']
        
        if is_compressed:
            if start + 0x10 > len(self.data):
                return None
            data_start = start + 0x10
            compressed_data = self.data[data_start:data_start + comp_size]
            try:
                decoder = LZSSDecoder()
                return decoder.decode(compressed_data, size)
            except:
                return compressed_data
        else:
            if start + size <= len(self.data):
                return self.data[start:start + size]
        
        return None
