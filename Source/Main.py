"""
Huziad Game Explorer - Tool for exploring PS2 game files
Supports formats: ISO9660, AFS, RTPK/RPK, MFA (Silent Hill), FPK (Battle Stadium D.O.N.), 
SPK (Siren 2), ADX (Audio), DBU (DBZ Sagas), MF Pack (Fate/Stay Night), BND (Various Games), 
EFS (Container format), GZIP (Budokai HD Collection), GL6 (Growlanser VI), SARA2 (Critical Bullet 7th Target), 
PAK (Di Gi Charat Fantasy Excellent), MELAN (Suzumiya Haruhi no Tomadoi), BEN10 (Ben 10: Protector of Earth)
"""
import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk
import os
import threading
import tempfile
import subprocess
import struct
import re
from datetime import datetime
from pathlib import Path

# Import modules
from iso9660_reader import ISO9660Reader
from afs_reader import AFSReader
from rtpk_reader import RTPKReader
from mfa_reader import MFAReader
from fpk_reader import FPKReader
from spk_reader import SPKReader
from dbu_reader import DBUReader
from mf_pack_reader import MFPackReader
from bnd_reader import BNDReader
from efs_reader import EFSReader
from gzip_reader import GZIPReader
from melan_reader import MelanReader
from cache_manager import CacheManager
from ben10_pre_wad import Ben10WADReader, parse_dir_to_entries, detect_ben10_wad



#PAK EXTRACTOR (Di Gi Charat Fantasy Excellent)

class PAKReader:
    """Class for reading PAK files (Di Gi Charat Fantasy Excellent)"""
    
    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        self.data = data
        self.filename = filename
        self.parent_iso = parent_iso
        self.parent_path = parent_path
        self.entries = []
        self.file_count = 0
        self.magic = b"PAKFILE\x00"
        self.entry_start = 0x10
        self.entry_size = 0x40
        self.sector_size = 0x800
        self.load_pak()
    
    def load_pak(self):
        """Load and parse PAK file (Di Gi Charat format)"""
        try:
            if len(self.data) < 0x10:
                print(f"File too small to be PAK")
                return
            
            # Check magic "PAKFILE\x00"
            if self.data[:8] != self.magic:
                print(f"Invalid magic: {self.data[:8]}")
                return
            
            print(f"Valid PAK signature found: PAKFILE")
            
            # Read file count (Big-endian at offset 8)
            self.file_count = struct.unpack_from(">I", self.data, 8)[0]
            print(f"PAK Info:")
            print(f"  Files: {self.file_count}")
            
            # Parse directory entries
            self.entries = []
            for i in range(self.file_count):
                off = self.entry_start + i * self.entry_size
                if off + self.entry_size > len(self.data):
                    print(f"Entry {i} out of bounds")
                    break
                
                entry_data = self.data[off:off + self.entry_size]
                
                # Name: first 40 bytes, null-terminated
                name_bytes = entry_data[:40]
                null_pos = name_bytes.find(b"\x00")
                if null_pos != -1:
                    name = name_bytes[:null_pos].decode("ascii", errors="replace")
                else:
                    name = name_bytes.decode("ascii", errors="replace")
                
                # Sector offset (big-endian) at offset 56
                sector_offset = struct.unpack_from(">I", entry_data, 56)[0]
                
                # Size (big-endian) at offset 60
                size = struct.unpack_from(">I", entry_data, 60)[0]
                
                # Byte offset = sector * 2048
                byte_offset = sector_offset * self.sector_size
                
                # Inner magic (first 4 bytes of the file)
                inner_magic = b""
                if byte_offset + 4 <= len(self.data):
                    inner_magic = self.data[byte_offset:byte_offset+4]
                
                inner_magic_str = inner_magic.decode("ascii", errors="replace") if inner_magic else ""
                
                # Determine extension and type
                ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                if ext == "pvr":
                    file_type = "PVR Texture"
                elif ext == "bin":
                    file_type = "Scene/Binary Data"
                elif ext == "txt":
                    file_type = "Text Data"
                elif ext == "fon":
                    file_type = "Bitmap Font"
                elif ext == "ico":
                    file_type = "Icon"
                else:
                    file_type = "Unknown"
                
                # Magic description
                magic_desc = {
                    "GBIX": "PVR Texture (GBIX)",
                    "PVRT": "PVR Texture (PVRT)",
                    "BLF2": "Scene/Layout data",
                    "SK00": "Sega Katana object",
                }.get(inner_magic_str, "Unknown")
                
                self.entries.append({
                    'index': i,
                    'name': name,
                    'ext': ext,
                    'sector': sector_offset,
                    'offset': byte_offset,
                    'size': size,
                    'inner_magic': inner_magic_str,
                    'magic_desc': magic_desc,
                    'type': file_type,
                    'full_path': name
                })
                
                if i < 20:  # Show first 20 entries
                    print(f"  Entry {i:04d}: {name} (sector={sector_offset}, size={size}, magic={inner_magic_str})")
            
            print(f"PAK loaded successfully with {self.file_count} files")
            
        except Exception as e:
            print(f"Error loading PAK: {e}")
            import traceback
            traceback.print_exc()
    
    def get_entries(self):
        """Get list of entries"""
        return self.entries
    
    def extract_file(self, index, output_path):
        """Extract a specific file from PAK"""
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
        """Get data of a specific file"""
        if index < 0 or index >= len(self.entries):
            return None
        
        entry = self.entries[index]
        start = entry['offset']
        size = entry['size']
        
        if start + size <= len(self.data):
            return self.data[start:start+size]
        
        return None


# =========================
# SARA2 EXTRACTOR (Critical Bullet 7th Target)
# =========================
class SARA2Extractor:
    """Extractor for SARA2.IDX + SARA2.PAC files (Critical Bullet 7th Target)"""
    
    def __init__(self, idx_data, pac_data, filename="", parent_iso=None, parent_path=""):
        self.idx_data = idx_data
        self.pac_data = pac_data
        self.filename = filename
        self.parent_iso = parent_iso
        self.parent_path = parent_path
        self.entries = []
        self.file_count = 0
        self.load_sara2()
    
    def load_sara2(self):
        """Load and parse SARA2.IDX file"""
        try:
            # Decode IDX as shift-jis
            text = self.idx_data.decode("shift-jis", errors="ignore")
            
            self.entries = []
            line_num = 0
            
            for line in text.splitlines():
                parts = line.strip().split()
                
                if len(parts) < 3:
                    continue
                
                name = parts[0]
                
                try:
                    
                    if any(c in parts[1].lower() for c in "abcdef"):
                        offset = int(parts[1], 16)
                    else:
                        offset = int(parts[1])
                    
                    
                    size = int(parts[2], 16)
                except:
                    continue
                
               
                safe_name = "".join(c for c in name if c not in '\\/:*?"<>|\n\r')
                
                self.entries.append({
                    'index': line_num,
                    'name': safe_name,
                    'offset': offset,
                    'size': size,
                    'full_path': safe_name
                })
                line_num += 1
            
            self.file_count = len(self.entries)
            print(f"SARA2 loaded successfully with {self.file_count} files")
            
        except Exception as e:
            print(f"Error loading SARA2: {e}")
            import traceback
            traceback.print_exc()
    
    def get_entries(self):
        """Get list of entries"""
        return self.entries
    
    def extract_file(self, index, output_path):
        """Extract a specific file from SARA2.PAC"""
        if index < 0 or index >= len(self.entries):
            return False, "Invalid index"
        
        entry = self.entries[index]
        start = entry['offset']
        size = entry['size']
        
        if start + size <= len(self.pac_data):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(self.pac_data[start:start+size])
            return True, f"Extracted: {entry['name']}"
        
        return False, f"Invalid file data (offset=0x{start:08X}, size={size})"
    
    def get_file_data(self, index):
        """Get data of a specific file"""
        if index < 0 or index >= len(self.entries):
            return None
        
        entry = self.entries[index]
        start = entry['offset']
        size = entry['size']
        
        if start + size <= len(self.pac_data):
            return self.pac_data[start:start+size]
        
        return None



class HexViewer(ctk.CTkToplevel):
    """Hexadecimal viewer for files with search functionality"""
    
    def __init__(self, parent, data, filename):
        super().__init__(parent)
        
        self.title(f"Hex Viewer - {filename}")
        self.geometry("1000x700")
        self.data = data
        self.filename = filename
        self.search_var = ctk.StringVar()
        self.search_type = ctk.StringVar(value="hex")
        self.search_positions = []
        self.current_search_index = 0
        
        self._create_widgets()
        self._display_hex()
        

        self.bind('<Escape>', lambda e: self.destroy())
        self.bind('<Control-f>', lambda e: self.search_entry.focus())
    
    def _create_widgets(self):
        """Create hex viewer widgets"""
        

        top_frame = ctk.CTkFrame(self)
        top_frame.pack(fill="x", padx=10, pady=10)
        
        # File info
        info_label = ctk.CTkLabel(
            top_frame,
            text=f"File: {self.filename} | Size: {len(self.data)} bytes (0x{len(self.data):08X})",
            font=("Consolas", 12)
        )
        info_label.pack(side="left", padx=5)
        
        # Search frame
        search_frame = ctk.CTkFrame(top_frame)
        search_frame.pack(side="right", padx=5)
        
        ctk.CTkLabel(search_frame, text="Search:").pack(side="left", padx=5)
        
        self.search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var, width=200)
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind('<Return>', lambda e: self._search())
        
        ctk.CTkRadioButton(search_frame, text="Hex", variable=self.search_type, value="hex").pack(side="left", padx=2)
        ctk.CTkRadioButton(search_frame, text="ASCII", variable=self.search_type, value="ascii").pack(side="left", padx=2)
        
        ctk.CTkButton(search_frame, text="Search", command=self._search, width=70).pack(side="left", padx=5)
        ctk.CTkButton(search_frame, text="Next", command=self._search_next, width=70).pack(side="left", padx=2)
        
        # Main frame for hex display
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Text widget for hex display
        self.hex_text = ctk.CTkTextbox(main_frame, font=("Consolas", 11), wrap="none")
        self.hex_text.pack(fill="both", expand=True)
        
        # Status bar
        self.status_bar = ctk.CTkLabel(
            self,
            text="Ready - Use Ctrl+F to search, Escape to close",
            font=("Segoe UI", 10),
            anchor="w",
            height=25
        )
        self.status_bar.pack(fill="x", padx=10, pady=5)
    
    def _display_hex(self):
        """Display hex dump"""
        hex_text = ""
        bytes_per_line = 16
        
        for i in range(0, len(self.data), bytes_per_line):
            chunk = self.data[i:i+bytes_per_line]
            hex_part = ' '.join(f'{b:02X}' for b in chunk)
            hex_part = hex_part.ljust(bytes_per_line * 3)
            
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            
            hex_text += f"{i:08X}  {hex_part}  |{ascii_part}|\n"
        
        self.hex_text.delete("1.0", "end")
        self.hex_text.insert("1.0", hex_text)
    
    def _search(self):
        """Search for pattern"""
        search_term = self.search_var.get().strip()
        if not search_term:
            messagebox.showinfo("Search", "Enter search term")
            return
        
        # Convert search term to bytes
        try:
            if self.search_type.get() == "hex":
                # Remove spaces and convert hex string to bytes
                hex_str = search_term.replace(' ', '').replace('0x', '')
                search_bytes = bytes.fromhex(hex_str)
            else:
                # ASCII search
                search_bytes = search_term.encode('latin-1')
        except ValueError as e:
            messagebox.showerror("Search Error", f"Invalid hex string: {e}")
            return
        
        # Find all occurrences
        self.search_positions = []
        pos = 0
        while True:
            pos = self.data.find(search_bytes, pos)
            if pos == -1:
                break
            self.search_positions.append(pos)
            pos += 1
        
        if not self.search_positions:
            messagebox.showinfo("Search", f"Pattern not found")
            self.status_bar.configure(text="Search: Pattern not found")
            return
        
        self.current_search_index = 0
        self._highlight_search()
        self.status_bar.configure(text=f"Search: Found {len(self.search_positions)} matches")
    
    def _search_next(self):
        """Go to next search result"""
        if not self.search_positions:
            self._search()
            return
        
        self.current_search_index = (self.current_search_index + 1) % len(self.search_positions)
        self._highlight_search()
    
    def _highlight_search(self):
        """Highlight search result in hex view"""
        if not self.search_positions:
            return
        
        pos = self.search_positions[self.current_search_index]
        
        # Calculate line number (1-indexed)
        bytes_per_line = 16
        line_num = (pos // bytes_per_line) + 1
        
        # Calculate column position in the hex part
        offset_in_line = pos % bytes_per_line
        hex_char_pos = 10 + (offset_in_line * 3)  # Approximate position in the hex display
        
        # Select and highlight
        self.hex_text.focus()
        self.hex_text.see(f"{line_num}.0")
        
        # Try to highlight by selecting text (approximate)
        try:
            start_idx = f"{line_num}.{hex_char_pos}"
            end_idx = f"{line_num}.{hex_char_pos + 2}"
            self.hex_text.tag_add("sel", start_idx, end_idx)
        except:
            pass
        
        self.status_bar.configure(text=f"Search: Match {self.current_search_index + 1} of {len(self.search_positions)} at offset 0x{pos:08X}")


# =========================
# GL6 EXTRACTOR (Growlanser VI)
# =========================
class GL6Extractor:
    """Extractor for Growlanser VI sound files (gl6_snd.dat)"""
    
    def __init__(self):
        self.data = None
        self.vag_offsets = []
        self.file_count = 0
    
    def parse_vag_header(self, data):
        try:
            size = struct.unpack(">I", data[12:16])[0]
            freq = struct.unpack(">I", data[16:20])[0]
            name = data[36:52].split(b'\x00', 1)[0].decode("ascii", errors="ignore")
            return size, freq, name
        except:
            return None, None, "invalid"
    
    def load_dat(self, data):
        self.data = data
        # Buscar todos los VAG
        self.vag_offsets = [m.start() for m in re.finditer(b"VAGp", self.data)]
        self.file_count = len(self.vag_offsets)
        return self.file_count
    
    def get_entries(self):
        entries = []
        for i, off in enumerate(self.vag_offsets):
            try:
                header = self.data[off:off+48]
                if header[:4] != b"VAGp":
                    continue
                size, freq, name = self.parse_vag_header(header)
                if not name:
                    name = f"sound_{i:04d}"
                entries.append({
                    'index': i,
                    'name': f"{name}.vag",
                    'offset': off,
                    'size': 48 + size if size else 0,
                    'full_path': f"{name}.vag"
                })
            except:
                continue
        return entries
    
    def extract_file(self, index, output_path):
        if index < 0 or index >= len(self.vag_offsets):
            return False, "Invalid index"
        
        off = self.vag_offsets[index]
        try:
            header = self.data[off:off+48]
            if header[:4] != b"VAGp":
                return False, "Not a VAG file"
            
            size, freq, name = self.parse_vag_header(header)
            total_size = 48 + (size if size else 0)
            
            with open(output_path, 'wb') as f:
                f.write(self.data[off:off+total_size])
            
            return True, f"Extracted: {name}.vag"
        except Exception as e:
            return False, f"Error: {str(e)}"


class ADXPlayer:
    """Class for playing ADX audio files"""
    
    def __init__(self):
        self.current_process = None
        self.temp_files = []
        
    def play_adx(self, adx_data, filename="audio.adx"):
        try:
            self.stop()
            
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"huziad_adx_{os.getpid()}_{len(self.temp_files)}.adx")
            
            with open(temp_path, 'wb') as f:
                f.write(adx_data)
            
            self.temp_files.append(temp_path)
            
            # Try to play with system default player
            import platform
            if platform.system() == 'Windows':
                os.startfile(temp_path)
            elif platform.system() == 'Darwin':
                subprocess.Popen(['open', temp_path])
            else:
                subprocess.Popen(['xdg-open', temp_path])
            
            return True
            
        except Exception as e:
            print(f"Error playing ADX: {e}")
            return False
    
    def stop(self):
        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process = None
            except:
                pass
    
    def cleanup(self):
        self.stop()
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
        self.temp_files.clear()


class HuziadGameExplorer(ctk.CTk):
    """Main application for exploring PS2 game files"""
    
    def __init__(self):
        super().__init__()
        
        # Window configuration
        self.title("Huziad Game Explorer")
        self.geometry("1400x800")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # State variables
        self.iso_reader = None
        self.current_path = ""
        self.current_entries = []
        self.item_data = {}
        self.current_iso_path = None
        self.current_selected_item = None
        
        # Containers
        self.current_afs = None
        self.current_rtpk = None
        self.current_mfa = None
        self.current_fpk = None
        self.current_spk = None
        self.current_dbu = None
        self.current_mfpack = None
        self.current_bnd = None
        self.current_efs = None
        self.current_gzip = None
        self.current_gl6 = None
        self.current_sara2 = None
        self.current_pak = None
        self.current_melan = None
        self.current_ben10 = None  # Ben 10 WAD reader
        
        self.afs_mode = False
        self.rtpk_mode = False
        self.mfa_mode = False
        self.fpk_mode = False
        self.spk_mode = False
        self.dbu_mode = False
        self.mfpack_mode = False
        self.bnd_mode = False
        self.efs_mode = False
        self.gzip_mode = False
        self.gl6_mode = False
        self.sara2_mode = False
        self.pak_mode = False
        self.melan_mode = False
        self.ben10_mode = False  # Ben 10 mode flag
        
        self.afs_parent_entry = None
        self.rtpk_parent_entry = None
        self.mfa_parent_entry = None
        self.fpk_parent_entry = None
        self.spk_parent_entry = None
        self.dbu_parent_entry = None
        self.mfpack_parent_entry = None
        self.bnd_parent_entry = None
        self.efs_parent_entry = None
        self.gzip_parent_entry = None
        self.gl6_parent_entry = None
        self.sara2_parent_entry = None
        self.pak_parent_entry = None
        self.melan_parent_entry = None
        self.ben10_parent_entry = None  
        
        self.sara2_pac_data = None
        self.melan_img_data = None
        self.ben10_wad_data = None  
        
        # SPK specific
        self.spk_roms_dir = None
        
        # Budokai HD specific detection
        self.is_budokai_hd_afs = False
        self.budokai_afs_file_count = 3990
        
        # DATA.AFS specific detection for FPK files
        self.data_afs_fpk_count = 135
        
        # Di Gi Charat PAK detection (15 elements + 3 AFS files in root)
        self.digicharat_afs_count = 3
        self.digicharat_root_elements = 15
        
        # GL6 specific threshold
        self.gl6_threshold = 968
        
        # ADX Player
        self.adx_player = ADXPlayer()
        
        # Cache system
        self.cache_manager = CacheManager()
        
        # Setup UI
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._create_widgets()
        
        # Keyboard shortcuts
        self.bind('<Control-o>', lambda e: self.open_iso())
        self.bind('<Control-c>', lambda e: self.clear_cache())
        self.bind('<Control-q>', lambda e: self.quit())
        
        # Cleanup on close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Show cache info at startup
        cache_info = self.cache_manager.get_cache_info()
        self.update_status(f"Ready - Cache: {cache_info['entries']} files ({cache_info['size_mb']:.1f} MB)")
    
    def on_closing(self):
        self.adx_player.cleanup()
        self.destroy()
    
    def _create_widgets(self):
        """Create all UI widgets"""
        
        # Top frame with controls
        top_frame = ctk.CTkFrame(self, height=60)
        top_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        top_frame.grid_columnconfigure(3, weight=1)
        
        # Control buttons
        self.open_btn = ctk.CTkButton(
            top_frame, text="📀 Open ISO", command=self.open_iso,
            width=120, height=40, font=("Segoe UI", 13, "bold"),
            fg_color="#2c7da0", hover_color="#1f5e7a"
        )
        self.open_btn.grid(row=0, column=0, padx=5, pady=10)
        
        self.back_btn = ctk.CTkButton(
            top_frame, text="← Back", command=self.go_back,
            width=80, height=40, state="disabled", font=("Segoe UI", 12)
        )
        self.back_btn.grid(row=0, column=1, padx=5, pady=10)
        
        self.exit_container_btn = ctk.CTkButton(
            top_frame, text="📁 Exit", command=self.exit_container,
            width=100, height=40, state="disabled",
            fg_color="#e67e22", hover_color="#b45f1b"
        )
        self.exit_container_btn.grid(row=0, column=2, padx=5, pady=10)
        
        self.clear_cache_btn = ctk.CTkButton(
            top_frame, text="🗑️ Clear Cache", command=self.clear_cache,
            width=100, height=40, font=("Segoe UI", 11),
            fg_color="#e74c3c", hover_color="#c0392b"
        )
        self.clear_cache_btn.grid(row=0, column=3, padx=5, pady=10)
        
        self.path_label = ctk.CTkLabel(
            top_frame, text="", font=("Segoe UI", 11),
            text_color="#a0a0a0", anchor="w"
        )
        self.path_label.grid(row=0, column=4, padx=10, pady=10, sticky="w")
        
        self.extract_btn = ctk.CTkButton(
            top_frame, text="💾 Extract", command=self.extract_selected,
            width=100, height=40, state="disabled",
            fg_color="#2e8b57", hover_color="#1f5e3a"
        )
        self.extract_btn.grid(row=0, column=5, padx=5, pady=10)
        
        self.info_btn = ctk.CTkButton(
            top_frame, text="ℹ️ Info", command=self.show_iso_info,
            width=80, height=40, state="disabled"
        )
        self.info_btn.grid(row=0, column=6, padx=5, pady=10)
        
        # Main frame
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=3)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)
        
        # Treeview (left panel)
        self._create_treeview(main_frame)
        
        # Details panel (right panel)
        self._create_details_panel(main_frame)
        
        # Status bar
        self.status_bar = ctk.CTkLabel(
            self, text="Ready - Press Ctrl+O to open an ISO file | Right-click on file for Hex Viewer",
            font=("Segoe UI", 11), text_color="#7cb518",
            anchor="w", height=30
        )
        self.status_bar.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
    
    def _create_treeview(self, parent):
        """Create treeview for displaying files"""
        left_frame = ctk.CTkFrame(parent)
        left_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        left_frame.grid_rowconfigure(0, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)
        
        # Configure style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background="#2b2b2b", foreground="white",
                        rowheight=28, fieldbackground="#2b2b2b",
                        font=("Segoe UI", 10))
        style.configure("Treeview.Heading",
                        background="#3c3c3c", foreground="white",
                        font=("Segoe UI", 11, "bold"))
        style.map('Treeview', background=[('selected', '#2c7da0')])
        
        # Treeview
        self.tree = ttk.Treeview(
            left_frame, columns=("size", "type", "date"),
            show="tree headings", selectmode="browse"
        )
        
        # Configure columns
        self.tree.heading("#0", text="Name", anchor="w")
        self.tree.heading("size", text="Size", anchor="e")
        self.tree.heading("type", text="Type", anchor="w")
        self.tree.heading("date", text="Modified Date", anchor="w")
        
        self.tree.column("#0", width=450, minwidth=250)
        self.tree.column("size", width=100, anchor="e")
        self.tree.column("type", width=100, anchor="w")
        self.tree.column("date", width=150, anchor="w")
        
        # Scrollbars
        vsb = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(left_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        # Events
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.show_context_menu)  # Right-click
    
    def show_context_menu(self, event):
        """Show right-click context menu"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.current_selected_item = item
            # Create menu on the fly
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(label="View in Hex", command=self.view_in_hex)
            menu.add_separator()
            menu.add_command(label="Extract", command=self.extract_selected)
            menu.post(event.x_root, event.y_root)
    
    def view_in_hex(self):
        """Open hex viewer for selected file"""
        if not self.current_selected_item:
            return
        
        entry = self.item_data.get(self.current_selected_item)
        if not entry:
            return
        
        if entry.get('is_directory', False):
            messagebox.showinfo("Info", "Cannot view directory in hex")
            return
        
        try:
            if entry.get('is_container_file', False):
                reader = entry.get('container_reader')
                idx = entry.get('container_index')
                if reader and idx is not None:
                    data = reader.get_file_data(idx)
                    if not data:
                        messagebox.showerror("Error", "Could not read file data")
                        return
                else:
                    messagebox.showerror("Error", "Invalid container data")
                    return
            else:
                data = self.iso_reader.read_file_data(entry['location'], entry['size'])
            
            HexViewer(self, data, entry['name'])
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not open hex viewer: {str(e)}")
    
    def _create_details_panel(self, parent):
        """Create details panel"""
        right_frame = ctk.CTkFrame(parent)
        right_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        right_frame.grid_rowconfigure(1, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)
        
        # Title
        details_title = ctk.CTkLabel(
            right_frame, text="File Details",
            font=("Segoe UI", 14, "bold")
        )
        details_title.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        # Text area
        self.details_text = ctk.CTkTextbox(
            right_frame, font=("Consolas", 11), wrap="word"
        )
        self.details_text.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
    
    def update_status(self, message, is_error=False):
        """Update status bar"""
        color = "#e63946" if is_error else "#7cb518"
        self.status_bar.configure(text=f"📌 {message}", text_color=color)
        self.update()
    
    def format_size(self, size):
        """Format file size"""
        if size >= 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"
        elif size >= 1024 * 1024:
            return f"{size / (1024 * 1024):.2f} MB"
        elif size >= 1024:
            return f"{size / 1024:.2f} KB"
        else:
            return f"{size} B"
    
    def clear_cache(self):
        """Clear temporary cache"""
        if messagebox.askyesno("Clear Cache", 
                                "Are you sure you want to clear the cache?\n"
                                "This will delete all temporary files."):
            self.cache_manager.clear_cache()
            cache_info = self.cache_manager.get_cache_info()
            self.update_status(f"🗑️ Cache cleared - {cache_info['entries']} files remaining")
            messagebox.showinfo("Cache Cleared", 
                               f"Cache cleared successfully.\n"
                               f"Freed space: {cache_info['size_mb']:.2f} MB")
    
    def _load_container_with_cache(self, entry, container_type, reader_class):
        """Load container using cache if available"""
        try:
            # Try to load from cache
            cached_data, cached_metadata = self.cache_manager.get_cached_container(
                self.current_iso_path, entry['full_path'], container_type
            )
            
            if cached_data and cached_metadata:
                # Use cached data
                container_reader = reader_class(
                    cached_data, entry['name'], self.iso_reader, entry['full_path']
                )
                container_reader.entries = cached_metadata.get('entries', [])
                container_reader.file_count = len(container_reader.entries)
                
                # Restore specific attributes
                if container_type == 'AFS':
                    container_reader.file_count = container_reader.entries
                elif container_type == 'RTPK':
                    container_reader.version = cached_metadata.get('version', 0)
                    container_reader.alignment = cached_metadata.get('alignment', 0)
                elif container_type == 'MFA':
                    container_reader.blocks = cached_metadata.get('blocks', [])
                elif container_type == 'FPK':
                    container_reader.info_offset = cached_metadata.get('info_offset', 0)
                    container_reader.data_size = cached_metadata.get('data_size', 0)
                elif container_type == 'SPK':
                    container_reader.header = cached_metadata.get('header', {})
                    container_reader.tail = cached_metadata.get('tail', b'')
                elif container_type == 'DBU':
                    pass
                elif container_type == 'MF_PACK':
                    pass
                elif container_type == 'BND':
                    pass
                elif container_type == 'EFS':
                    pass
                elif container_type == 'GZIP':
                    pass
                elif container_type == 'GL6':
                    pass
                elif container_type == 'SARA2':
                    pass
                elif container_type == 'PAK':
                    pass
                elif container_type == 'MELAN':
                    pass
                elif container_type == 'BEN10':
                    pass
                
                self.update_status(f"✅ {container_type} loaded from cache: {entry['name']}")
                return container_reader, True
            
            # Not in cache, load from ISO
            self.update_status(f"📀 Loading {container_type} from ISO: {entry['name']}...")
            data = self.iso_reader.read_file_data(entry['location'], entry['size'])
            
            # Create reader
            container_reader = reader_class(data, entry['name'], self.iso_reader, entry['full_path'])
            
            if len(container_reader.get_entries()) > 0:
                # Save to cache
                metadata = {
                    'entries': container_reader.get_entries(),
                    'type': container_type,
                    'filename': entry['name']
                }
                
                # Add specific metadata
                if container_type == 'RTPK':
                    metadata['version'] = container_reader.version
                    metadata['alignment'] = container_reader.alignment
                elif container_type == 'MFA':
                    metadata['blocks'] = container_reader.blocks
                elif container_type == 'FPK':
                    metadata['info_offset'] = container_reader.info_offset
                    metadata['data_size'] = container_reader.data_size
                elif container_type == 'SPK':
                    metadata['header'] = container_reader.header
                    metadata['tail'] = container_reader.tail
                
                self.cache_manager.save_to_cache(
                    self.current_iso_path, entry['full_path'], 
                    container_type, data, metadata
                )
                
                return container_reader, False
            
            return None, False
            
        except Exception as e:
            self.update_status(f"❌ Error loading {container_type}: {str(e)}", True)
            return None, False
    
    def open_ben10(self, entry):
        """Open Ben 10 game.dir file and load game.wad"""
        try:
            self.update_status(f"Loading Ben 10 WAD: {entry['name']}...")
            
            # Read game.dir data
            dir_data = self.iso_reader.read_file_data(entry['location'], entry['size'])
            
            # Try to find game.wad in the same directory
            wad_entry = None
            current_path = os.path.dirname(entry['full_path'])
            
            # Search in current directory for game.wad
            for current_entry in self.current_entries:
                if current_entry['name'].lower() == 'game.wad':
                    wad_entry = current_entry
                    break
            
            # If not found in current directory, search in parent
            if not wad_entry and current_path:
                # Try to read parent directory
                parent_entries = self.iso_reader.read_directory(
                    self.iso_reader.root_directory['location'],
                    self.iso_reader.root_directory['full_path']
                )
                for root_entry in parent_entries:
                    if root_entry['name'].lower() == 'game.wad':
                        wad_entry = root_entry
                        break
            
            if not wad_entry:
                # Try to find anywhere in ISO
                print(f"[*] Searching for game.wad in ISO...")
                wad_entry = self._find_file_in_iso('game.wad')
            
            if not wad_entry:
                messagebox.showerror("Error", 
                    "game.wad not found!\n\n"
                    "Ben 10: Protector of Earth requires both:\n"
                    "  - game.dir (the file you double-clicked)\n"
                    "  - game.wad (the data file)\n\n"
                    "Make sure both files are in the ISO.")
                return
            
            # Read game.wad data
            self.update_status(f"Reading game.wad ({self.format_size(wad_entry['size'])})...")
            wad_data = self.iso_reader.read_file_data(wad_entry['location'], wad_entry['size'])
            self.ben10_wad_data = wad_data
            
            # Create Ben 10 reader
            container_reader = Ben10WADReader(dir_data, wad_data, entry['name'], self.iso_reader, entry['full_path'])
            
            if container_reader and len(container_reader.get_entries()) > 0:
                self.current_ben10 = container_reader
                self.ben10_mode = True
                self.ben10_parent_entry = entry
                self.exit_container_btn.configure(state="normal")
                
                # Clear and show content
                for item in self.tree.get_children():
                    self.tree.delete(item)
                self.item_data.clear()
                
                ben10_entries = self.current_ben10.get_entries()
                self.current_path = f"{entry['full_path']} [Ben 10 WAD]"
                stats = self.current_ben10.get_stats()
                self.path_label.configure(text=f"🎮 {self.current_path}")
                
                for idx, ben10_entry in enumerate(ben10_entries):
                    size_str = self._format_size_display(ben10_entry['size'])
                    icon = ben10_entry.get('icon', "📄 ")
                    
                    item_id = self.tree.insert(
                        "", "end",
                        text=f"{icon}{ben10_entry['name']}",
                        values=(size_str, ben10_entry['type'], "")
                    )
                    
                    self.item_data[item_id] = {
                        'name': ben10_entry['name'],
                        'full_path': f"{entry['full_path']}/{ben10_entry['name']}",
                        'is_directory': False,
                        'size': ben10_entry['size'],
                        'is_container_file': True,
                        'container_type': 'BEN10',
                        'container_reader': self.current_ben10,
                        'container_index': idx,
                        'date': '',
                        'offset': ben10_entry['offset'],
                        'ext': ben10_entry['ext'],
                        'sector': ben10_entry['sector']
                    }
                
                self.update_status(f"✅ Ben 10 WAD loaded: {entry['name']} + game.wad - {len(ben10_entries)} files")
            else:
                messagebox.showwarning("Warning", "The file does not appear to be a valid game.dir")
                
        except Exception as e:
            self.update_status(f"❌ Error loading Ben 10 WAD: {str(e)}", True)
            messagebox.showerror("Error", f"Could not load Ben 10 WAD:\n{str(e)}")
    
    def _find_file_in_iso(self, filename):
        """Search for a file in the ISO recursively"""
        try:
            stack = [self.iso_reader.root_directory]
            while stack:
                dir_entry = stack.pop()
                entries = self.iso_reader.read_directory(
                    dir_entry['location'], 
                    dir_entry['full_path']
                )
                for entry in entries:
                    if entry['name'].lower() == filename.lower() and not entry['is_directory']:
                        return entry
                    if entry['is_directory'] and entry['name'] not in ['.', '..']:
                        stack.append(entry)
        except Exception as e:
            print(f"Error searching for {filename}: {e}")
        return None
    
    def open_melan(self, entry):
        """Open melan.idx file (Suzumiya Haruhi no Tomadoi) and load corresponding melan.img"""
        try:
            # First, try to find the IMG file in the same directory as the IDX
            img_entry = None
            img_filename = "melan.img"
            
            # Search in the current directory entries for melan.img
            for current_entry in self.current_entries:
                if current_entry['name'].upper() == img_filename.upper():
                    img_entry = current_entry
                    break
            
            if img_entry:
                # Read IMG data from the ISO
                img_data = self.iso_reader.read_file_data(img_entry['location'], img_entry['size'])
                print(f"[*] Found IMG file: {img_entry['name']} at offset 0x{img_entry['location']:08X}")
            else:
                # If not found in current directory, try to find in the root directory
                root_entries = self.iso_reader.read_directory(
                    self.iso_reader.root_directory['location'],
                    self.iso_reader.root_directory['full_path']
                )
                
                for root_entry in root_entries:
                    if root_entry['name'].upper() == img_filename.upper() and not root_entry['is_directory']:
                        img_entry = root_entry
                        break
                
                if img_entry:
                    img_data = self.iso_reader.read_file_data(img_entry['location'], img_entry['size'])
                    print(f"[*] Found IMG file in root: {img_entry['name']} at offset 0x{img_entry['location']:08X}")
                else:
                    messagebox.showerror("Error", f"IMG file not found: {img_filename}\n\nMake sure melan.img is in the same folder as melan.idx within the ISO.")
                    return
            
            # Read IDX data
            idx_data = self.iso_reader.read_file_data(entry['location'], entry['size'])
            
            # Create Melan reader
            container_reader = MelanReader(idx_data, img_data, entry['name'], self.iso_reader, entry['full_path'])
            
            if container_reader and len(container_reader.get_entries()) > 0:
                self.current_melan = container_reader
                self.melan_mode = True
                self.melan_parent_entry = entry
                self.melan_img_data = img_data
                self.exit_container_btn.configure(state="normal")
                
                # Clear and show content
                for item in self.tree.get_children():
                    self.tree.delete(item)
                self.item_data.clear()
                
                # Get root entries to display
                root_entries = self.current_melan.get_root_entries()
                stats = self.current_melan.get_stats()
                
                self.current_path = f"{entry['full_path']} [Melan Archive]"
                self.path_label.configure(text=f"📊 {self.current_path}")
                
                # Recursively add entries to treeview (iterative)
                self._add_melan_entries_to_tree(root_entries, "")
                
                self.update_status(f"✅ Melan archive loaded: {entry['name']} - {stats['files']} files, {stats['directories']} directories")
            else:
                messagebox.showwarning("Warning", "The file does not appear to be a valid melan.idx")
                
        except Exception as e:
            self.update_status(f"❌ Error loading Melan: {str(e)}", True)
            messagebox.showerror("Error", f"Could not load Melan archive:\n{str(e)}")
    
    def _add_melan_entries_to_tree(self, records, parent_iid):
        """Add melan records to treeview (iterative, no recursion)"""
        # Stack of (records_list, parent_iid)
        stack = [(records, parent_iid)]
        
        while stack:
            recs, parent = stack.pop()
            # Process in reverse order for correct display
            for rec in reversed(recs):
                # Icon based on type and extension
                if rec.is_dir:
                    icon = "📁 "
                    type_str = "Directory"
                    size_str = "<DIR>"
                else:
                    ext = rec.name.rsplit(".", 1)[-1].lower() if "." in rec.name else ""
                    icon_map = {
                        "vag": "🔊", "ads": "🔊", "bnk": "🔊", "ses": "🔊",
                        "ebg": "🖼️", "tm2": "🖼️", "ico": "🖼️", "bgo": "🖼️",
                        "bin": "📦", "gzx": "📦", "zlb": "📦",
                        "btl": "⚔️", "prs": "⚔️", "sgs": "🃏",
                        "dat": "📊", "rpt": "📋", "fnt": "🔤",
                        "msg": "💬", "pge": "📄", "rol": "📜",
                        "eff": "✨", "efs": "✨", "pss": "🎬"
                    }
                    icon_char = icon_map.get(ext, "📄")
                    icon = f"{icon_char} "
                    type_str = f"File ({ext.upper() if ext else 'BIN'})"
                    size_str = self._format_size_display(rec.size)
                
                iid = self.tree.insert(
                    parent, "end",
                    text=f"{icon}{rec.name}",
                    values=(size_str, type_str, "")
                )
                
                self.item_data[iid] = {
                    'name': rec.name,
                    'full_path': f"{self.melan_parent_entry['full_path']}/{rec.name}",
                    'is_directory': rec.is_dir,
                    'size': rec.size if not rec.is_dir else 0,
                    'is_container_file': True,
                    'container_type': 'MELAN',
                    'container_reader': self.current_melan,
                    'container_index': rec.idx_offset,  # Use offset as index
                    'date': '',
                    'record': rec
                }
                
                if rec.is_dir and rec.children:
                    stack.append((rec.children, iid))
    
    def open_pak(self, entry):
        """Open PAK file (Di Gi Charat Fantasy Excellent)"""
        try:
            self.update_status(f"Loading PAK archive: {entry['name']}...")
            data = self.iso_reader.read_file_data(entry['location'], entry['size'])
            
            container_reader = PAKReader(data, entry['name'], self.iso_reader, entry['full_path'])
            
            if container_reader and len(container_reader.get_entries()) > 0:
                self.current_pak = container_reader
                self.pak_mode = True
                self.pak_parent_entry = entry
                self.exit_container_btn.configure(state="normal")
                
                # Clear and show content
                for item in self.tree.get_children():
                    self.tree.delete(item)
                self.item_data.clear()
                
                pak_entries = self.current_pak.get_entries()
                self.current_path = f"{entry['full_path']} [PAK Archive]"
                self.path_label.configure(text=f"📦 {self.current_path}")
                
                for idx, pak_entry in enumerate(pak_entries):
                    size_str = self._format_size_display(pak_entry['size'])
                    
                    # Set icon based on file type
                    if pak_entry['ext'] == 'pvr':
                        icon = "🖼️ "
                    elif pak_entry['ext'] == 'bin':
                        icon = "📦 "
                    elif pak_entry['ext'] == 'txt':
                        icon = "📝 "
                    elif pak_entry['ext'] == 'fon':
                        icon = "🔤 "
                    elif pak_entry['ext'] == 'ico':
                        icon = "🖼️ "
                    else:
                        icon = "📄 "
                    
                    item_id = self.tree.insert(
                        "", "end",
                        text=f"{icon}{pak_entry['name']}",
                        values=(size_str, f"PAK File ({pak_entry['type']})", "")
                    )
                    
                    self.item_data[item_id] = {
                        'name': pak_entry['name'],
                        'full_path': f"{entry['full_path']}/{pak_entry['name']}",
                        'is_directory': False,
                        'size': pak_entry['size'],
                        'is_container_file': True,
                        'container_type': 'PAK',
                        'container_reader': self.current_pak,
                        'container_index': idx,
                        'date': '',
                        'offset': pak_entry['offset'],
                        'inner_magic': pak_entry.get('inner_magic', ''),
                        'magic_desc': pak_entry.get('magic_desc', '')
                    }
                
                self.update_status(f"✅ PAK archive loaded: {entry['name']} - {len(pak_entries)} files")
            else:
                messagebox.showwarning("Warning", "The file does not appear to be a valid PAK archive")
                
        except Exception as e:
            self.update_status(f"❌ Error loading PAK: {str(e)}", True)
            messagebox.showerror("Error", f"Could not load PAK archive:\n{str(e)}")
    
    def open_sara2(self, entry):
        """Open SARA2.IDX file (Critical Bullet 7th Target) and load corresponding PAC"""
        try:
            # First, try to find the PAC file in the same directory as the IDX
            pac_entry = None
            pac_filename = "SARA2.PAC"
            
            # Search in the current directory entries for SARA2.PAC
            for current_entry in self.current_entries:
                if current_entry['name'].upper() == pac_filename.upper():
                    pac_entry = current_entry
                    break
            
            if pac_entry:
                # Read PAC data from the ISO
                pac_data = self.iso_reader.read_file_data(pac_entry['location'], pac_entry['size'])
                print(f"[*] Found PAC file: {pac_entry['name']} at offset 0x{pac_entry['location']:08X}")
            else:
                # If not found in current directory, try to find in the root directory
                root_entries = self.iso_reader.read_directory(
                    self.iso_reader.root_directory['location'],
                    self.iso_reader.root_directory['full_path']
                )
                
                for root_entry in root_entries:
                    if root_entry['name'].upper() == pac_filename.upper() and not root_entry['is_directory']:
                        pac_entry = root_entry
                        break
                
                if pac_entry:
                    pac_data = self.iso_reader.read_file_data(pac_entry['location'], pac_entry['size'])
                    print(f"[*] Found PAC file in root: {pac_entry['name']} at offset 0x{pac_entry['location']:08X}")
                else:
                    messagebox.showerror("Error", f"PAC file not found: {pac_filename}\n\nMake sure SARA2.PAC is in the same folder as SARA2.IDX within the ISO.")
                    return
            
            # Read IDX data
            idx_data = self.iso_reader.read_file_data(entry['location'], entry['size'])
            
            # Create SARA2 reader
            container_reader = SARA2Extractor(idx_data, pac_data, entry['name'], self.iso_reader, entry['full_path'])
            
            if container_reader and len(container_reader.get_entries()) > 0:
                self.current_sara2 = container_reader
                self.sara2_mode = True
                self.sara2_parent_entry = entry
                self.sara2_pac_data = pac_data
                self.exit_container_btn.configure(state="normal")
                
                # Clear and show content
                for item in self.tree.get_children():
                    self.tree.delete(item)
                self.item_data.clear()
                
                sara2_entries = self.current_sara2.get_entries()
                self.current_path = f"{entry['full_path']} [SARA2 Archive]"
                self.path_label.configure(text=f"📦 {self.current_path}")
                
                for idx, sara2_entry in enumerate(sara2_entries):
                    size_str = self._format_size_display(sara2_entry['size'])
                    item_id = self.tree.insert(
                        "", "end",
                        text=f"📄 {sara2_entry['name']}",
                        values=(size_str, "SARA2 File", "")
                    )
                    
                    self.item_data[item_id] = {
                        'name': sara2_entry['name'],
                        'full_path': f"{entry['full_path']}/{sara2_entry['name']}",
                        'is_directory': False,
                        'size': sara2_entry['size'],
                        'is_container_file': True,
                        'container_type': 'SARA2',
                        'container_reader': self.current_sara2,
                        'container_index': idx,
                        'date': '',
                        'offset': sara2_entry['offset']
                    }
                
                self.update_status(f"✅ SARA2 archive loaded: {entry['name']} - {len(sara2_entries)} files")
            else:
                messagebox.showwarning("Warning", "The file does not appear to be a valid SARA2 IDX")
                
        except Exception as e:
            self.update_status(f"❌ Error loading SARA2: {str(e)}", True)
            messagebox.showerror("Error", f"Could not load SARA2 archive:\n{str(e)}")
    
    def open_gl6(self, entry):
        """Open GL6 sound DAT file (Growlanser VI)"""
        try:
            self.update_status(f"Loading GL6 sound archive: {entry['name']}...")
            data = self.iso_reader.read_file_data(entry['location'], entry['size'])
            
            container_reader = GL6Extractor()
            vag_count = container_reader.load_dat(data)
            
            print(f"[*] GL6 file: {entry['name']} - VAG files found: {vag_count}")
            
            # Check if this is a valid GL6 file (has many VAG entries)
            if vag_count >= self.gl6_threshold:
                self.current_gl6 = container_reader
                self.gl6_mode = True
                self.gl6_parent_entry = entry
                self.exit_container_btn.configure(state="normal")
                
                # Clear and show content
                for item in self.tree.get_children():
                    self.tree.delete(item)
                self.item_data.clear()
                
                gl6_entries = self.current_gl6.get_entries()
                self.current_path = f"{entry['full_path']} [GL6 Sound Archive]"
                self.path_label.configure(text=f"🎵📦 {self.current_path}")
                
                for idx, gl6_entry in enumerate(gl6_entries):
                    size_str = self._format_size_display(gl6_entry['size'])
                    item_id = self.tree.insert(
                        "", "end",
                        text=f"🎵 {gl6_entry['name']}",
                        values=(size_str, "VAG Audio", "")
                    )
                    
                    self.item_data[item_id] = {
                        'name': gl6_entry['name'],
                        'full_path': f"{entry['full_path']}/{gl6_entry['name']}",
                        'is_directory': False,
                        'size': gl6_entry['size'],
                        'is_container_file': True,
                        'container_type': 'GL6',
                        'container_reader': self.current_gl6,
                        'container_index': idx,
                        'date': '',
                        'offset': gl6_entry['offset']
                    }
                
                self.update_status(f"✅ GL6 sound archive loaded: {entry['name']} - {len(gl6_entries)} VAG files")
            else:
                # Not a valid GL6 file, treat as regular DAT file
                self.update_status(f"File is not a valid GL6 sound archive (found {vag_count} VAG files, need {self.gl6_threshold}+)")
                messagebox.showinfo("Info", f"This file appears to have {vag_count} VAG files.\nGL6 sound archives typically have {self.gl6_threshold}+ files.\n\nYou can still view it in hex viewer (right-click).")
                
        except Exception as e:
            self.update_status(f"❌ Error loading GL6: {str(e)}", True)
            messagebox.showerror("Error", f"Could not load GL6 sound archive:\n{str(e)}")
    
    def open_afs(self, entry):
        """Open AFS file"""
        container_reader, from_cache = self._load_container_with_cache(entry, 'AFS', AFSReader)
        
        # Check if this is the Budokai HD DATA_CMN.AFS
        if container_reader and container_reader.file_count == self.budokai_afs_file_count:
            if 'DATA_CMN' in entry['name'].upper() or 'DATA_CMN' in entry['full_path'].upper():
                self.is_budokai_hd_afs = True
                print(f"[*] Detected Budokai HD DATA_CMN.AFS - {container_reader.file_count} files")
                self.update_status(f"Budokai HD AFS detected! Files will be treated as GZIP compressed data.")
        
        # Check if this is DATA.AFS with 135 files (FPK files)
        is_data_afs_fpk = False
        if container_reader and container_reader.file_count == self.data_afs_fpk_count:
            if 'DATA' in entry['name'].upper() or 'DATA' in entry['full_path'].upper():
                is_data_afs_fpk = True
                print(f"[*] Detected DATA.AFS with FPK files - {container_reader.file_count} files")
                self.update_status(f"DATA.AFS detected! Files are FPK archives.")
        
        # Check for Di Gi Charat detection (root directory with 15 elements + 3 AFS files)
        is_digicharat_pak = False
        if self.current_entries:
            afs_count = sum(1 for e in self.current_entries if e['name'].lower().endswith('.afs'))
            total_elements = len(self.current_entries)
            
            if total_elements == self.digicharat_root_elements and afs_count == self.digicharat_afs_count:
                # This could be Di Gi Charat root directory
                # Check if the current entry is a PAK file
                if entry['name'].upper().endswith('.PAK'):
                    is_digicharat_pak = True
                    print(f"[*] Detected Di Gi Charat PAK file: {entry['name']}")
                    self.update_status(f"Di Gi Charat PAK detected! Opening as PAK archive.")
                    # Open as PAK directly
                    self.open_pak(entry)
                    return
        
        if container_reader and container_reader.file_count > 0:
            self.current_afs = container_reader
            self.afs_mode = True
            self.afs_parent_entry = entry
            self.exit_container_btn.configure(state="normal")
            
            # Clear and show content
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.item_data.clear()
            
            afs_entries = self.current_afs.get_entries()
            self.current_path = f"{entry['full_path']} [AFS]"
            
            if self.is_budokai_hd_afs:
                self.path_label.configure(text=f"📦 {self.current_path} (Budokai HD - GZIP files)")
            elif is_data_afs_fpk:
                self.path_label.configure(text=f"📦 {self.current_path} (FPK Archives)")
            else:
                self.path_label.configure(text=f"📦 {self.current_path}")
            
            for idx, afs_entry in enumerate(afs_entries):
                size_str = self._format_size_display(afs_entry['size'])
                
                if self.is_budokai_hd_afs:
                    icon = "🗜️ "
                    type_str = "GZIP Compressed"
                elif is_data_afs_fpk:
                    icon = "📦 "
                    type_str = "FPK Archive"
                else:
                    icon = "📄 "
                    type_str = "AFS File"
                
                item_id = self.tree.insert(
                    "", "end",
                    text=f"{icon}{afs_entry['name']}",
                    values=(size_str, type_str, "")
                )
                
                self.item_data[item_id] = {
                    'name': afs_entry['name'],
                    'full_path': f"{entry['full_path']}/{afs_entry['name']}",
                    'is_directory': False,
                    'size': afs_entry['size'],
                    'is_container_file': True,
                    'container_type': 'AFS',
                    'container_reader': self.current_afs,
                    'container_index': idx,
                    'date': '',
                    'is_budokai_gzip': self.is_budokai_hd_afs,
                    'is_fpk_archive': is_data_afs_fpk,
                    'original_name': afs_entry['name']
                }
            
            cache_msg = " (from cache)" if from_cache else ""
            self.update_status(f"✅ AFS loaded{cache_msg}: {entry['name']} - {len(afs_entries)} files")
            if self.is_budokai_hd_afs:
                self.update_status(f"🎮 Budokai HD mode: Files are GZIP compressed, double-click to decompress")
            elif is_data_afs_fpk:
                self.update_status(f"🎮 DATA.AFS mode: Files are FPK archives, double-click to open")
        else:
            messagebox.showwarning("Warning", "The file does not appear to be a valid AFS")
    
    def open_fpk_from_afs(self, entry):
        """Open an FPK file from DATA.AFS"""
        try:
            if not entry.get('container_reader') or entry.get('container_index') is None:
                return False
            
            reader = entry.get('container_reader')
            idx = entry.get('container_index')
            
            # Read the raw data from AFS
            raw_data = reader.get_file_data(idx)
            
            if not raw_data:
                messagebox.showerror("Error", "Could not read file data")
                return False
            
            # Create FPK reader from the raw data
            fpk_reader = FPKReader(raw_data, entry['name'], self.iso_reader, entry['full_path'])
            
            if fpk_reader and len(fpk_reader.get_entries()) > 0:
                self.current_fpk = fpk_reader
                self.fpk_mode = True
                self.fpk_parent_entry = entry
                self.exit_container_btn.configure(state="normal")
                
                # Clear and show content
                for item in self.tree.get_children():
                    self.tree.delete(item)
                self.item_data.clear()
                
                fpk_entries = self.current_fpk.get_entries()
                self.current_path = f"{entry['full_path']} [FPK]"
                self.path_label.configure(text=f"📦 {self.current_path}")
                
                for idx, fpk_entry in enumerate(fpk_entries):
                    size_str = self._format_size_display(fpk_entry['size'])
                    comp_indicator = "🔒 " if fpk_entry.get('is_compressed', False) else ""
                    item_id = self.tree.insert(
                        "", "end",
                        text=f"{comp_indicator}📄 {fpk_entry['name']}",
                        values=(size_str, "FPK File", "")
                    )
                    
                    self.item_data[item_id] = {
                        'name': fpk_entry['name'],
                        'full_path': f"{entry['full_path']}/{fpk_entry['name']}",
                        'is_directory': False,
                        'size': fpk_entry['size'],
                        'is_container_file': True,
                        'container_type': 'FPK',
                        'container_reader': self.current_fpk,
                        'container_index': idx,
                        'date': '',
                        'is_compressed': fpk_entry.get('is_compressed', False),
                        'zsize': fpk_entry.get('zsize', 0)
                    }
                
                compressed_count = sum(1 for e in fpk_entries if e.get('is_compressed', False))
                self.update_status(f"✅ FPK loaded: {entry['name']} - {len(fpk_entries)} files ({compressed_count} compressed)")
                return True
            else:
                self.update_status(f"File is not a valid FPK archive")
                return False
                
        except Exception as e:
            self.update_status(f"❌ Error loading FPK: {str(e)}", True)
            return False
    
    def open_gzip_from_afs(self, entry):
        """Open a GZIP compressed file from Budokai HD AFS"""
        try:
            if not entry.get('container_reader') or entry.get('container_index') is None:
                return False
            
            reader = entry.get('container_reader')
            idx = entry.get('container_index')
            
            raw_data = reader.get_file_data(idx)
            
            if not raw_data:
                messagebox.showerror("Error", "Could not read file data")
                return False
            
            gzip_reader = GZIPReader(raw_data, entry['name'], self.iso_reader, entry['full_path'])
            
            if gzip_reader and gzip_reader.is_gzip:
                self.current_gzip = gzip_reader
                self.gzip_mode = True
                self.gzip_parent_entry = entry
                self.exit_container_btn.configure(state="normal")
                
                for item in self.tree.get_children():
                    self.tree.delete(item)
                self.item_data.clear()
                
                gzip_entries = self.current_gzip.get_entries()
                self.current_path = f"{entry['full_path']} [Decompressed]"
                self.path_label.configure(text=f"🗜️ {self.current_path}")
                
                for idx, gzip_entry in enumerate(gzip_entries):
                    size_str = self._format_size_display(gzip_entry['size'])
                    item_id = self.tree.insert(
                        "", "end",
                        text=f"📄 {gzip_entry['name']}",
                        values=(size_str, "Decompressed File", "")
                    )
                    
                    self.item_data[item_id] = {
                        'name': gzip_entry['name'],
                        'full_path': f"{entry['full_path']}/{gzip_entry['name']}",
                        'is_directory': False,
                        'size': gzip_entry['size'],
                        'is_container_file': True,
                        'container_type': 'GZIP',
                        'container_reader': self.current_gzip,
                        'container_index': idx,
                        'date': '',
                        'original_name': entry['name']
                    }
                
                self.update_status(f"✅ GZIP decompressed: {entry['name']} - {len(gzip_entries)} files")
                return True
            else:
                self.update_status(f"File is not GZIP compressed, showing as raw data")
                return False
                
        except Exception as e:
            self.update_status(f"❌ Error decompressing: {str(e)}", True)
            return False
    
    def open_gzip(self, entry):
        """Open GZIP compressed file (Budokai HD Collection)"""
        if entry.get('is_budokai_gzip', False):
            return self.open_gzip_from_afs(entry)
        
        container_reader, from_cache = self._load_container_with_cache(entry, 'GZIP', GZIPReader)
        
        if container_reader and container_reader.is_gzip:
            self.current_gzip = container_reader
            self.gzip_mode = True
            self.gzip_parent_entry = entry
            self.exit_container_btn.configure(state="normal")
            
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.item_data.clear()
            
            gzip_entries = self.current_gzip.get_entries()
            self.current_path = f"{entry['full_path']} [GZIP]"
            self.path_label.configure(text=f"🗜️ {self.current_path}")
            
            for idx, gzip_entry in enumerate(gzip_entries):
                size_str = self._format_size_display(gzip_entry['size'])
                item_id = self.tree.insert(
                    "", "end",
                    text=f"📄 {gzip_entry['name']}",
                    values=(size_str, "Decompressed File", "")
                )
                
                self.item_data[item_id] = {
                    'name': gzip_entry['name'],
                    'full_path': f"{entry['full_path']}/{gzip_entry['name']}",
                    'is_directory': False,
                    'size': gzip_entry['size'],
                    'is_container_file': True,
                    'container_type': 'GZIP',
                    'container_reader': self.current_gzip,
                    'container_index': idx,
                    'date': '',
                    'original_name': entry['name']
                }
            
            cache_msg = " (from cache)" if from_cache else ""
            self.update_status(f"✅ GZIP decompressed{cache_msg}: {entry['name']} - {len(gzip_entries)} files")
        else:
            self.current_gzip = None
            self.gzip_mode = True
            self.gzip_parent_entry = entry
            self.exit_container_btn.configure(state="normal")
            
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.item_data.clear()
            
            self.current_path = f"{entry['full_path']} [RAW DATA]"
            self.path_label.configure(text=f"📄 {self.current_path}")
            
            size_str = self._format_size_display(entry['size'])
            item_id = self.tree.insert(
                "", "end",
                text=f"📄 {entry['name']}",
                values=(size_str, "Raw Data", "")
            )
            
            self.item_data[item_id] = {
                'name': entry['name'],
                'full_path': entry['full_path'],
                'is_directory': False,
                'size': entry['size'],
                'is_container_file': True,
                'container_type': 'RAW',
                'container_reader': None,
                'container_index': 0,
                'date': '',
                'is_raw': True
            }
            
            self.update_status(f"File is not GZIP compressed, showing as raw data")
    
    def open_efs(self, entry):
        """Open EFS file (Container format)"""
        container_reader, from_cache = self._load_container_with_cache(entry, 'EFS', EFSReader)
        
        if container_reader and len(container_reader.get_entries()) > 0:
            self.current_efs = container_reader
            self.efs_mode = True
            self.efs_parent_entry = entry
            self.exit_container_btn.configure(state="normal")
            
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.item_data.clear()
            
            efs_entries = self.current_efs.get_entries()
            self.current_path = f"{entry['full_path']} [EFS]"
            self.path_label.configure(text=f"📦 {self.current_path}")
            
            for idx, efs_entry in enumerate(efs_entries):
                if efs_entry.get('is_header', False):
                    size_str = "<HEADER>"
                    icon = "📄 "
                else:
                    size_str = self._format_size_display(efs_entry['size'])
                    icon = "📄 "
                
                item_id = self.tree.insert(
                    "", "end",
                    text=f"{icon}{efs_entry['name']}",
                    values=(size_str, "EFS File", "")
                )
                
                self.item_data[item_id] = {
                    'name': efs_entry['name'],
                    'full_path': f"{entry['full_path']}/{efs_entry['name']}",
                    'is_directory': False,
                    'size': efs_entry.get('size', 0),
                    'is_container_file': True,
                    'container_type': 'EFS',
                    'container_reader': self.current_efs,
                    'container_index': idx,
                    'date': '',
                    'is_header': efs_entry.get('is_header', False)
                }
            
            cache_msg = " (from cache)" if from_cache else ""
            self.update_status(f"✅ EFS loaded{cache_msg}: {entry['name']} - {len(efs_entries)} files")
        else:
            messagebox.showwarning("Warning", "The file does not appear to be a valid EFS")
    
    def open_spk(self, entry):
        """Open SPK file (Siren 2)"""
        container_reader, from_cache = self._load_container_with_cache(entry, 'SPK', SPKReader)
        
        if container_reader and len(container_reader.get_entries()) > 0:
            iso_dir = os.path.dirname(self.current_iso_path)
            
            rom_files_found = False
            for f in os.listdir(iso_dir):
                if f.upper().startswith('ROM.') and f.upper().endswith('.ROM'):
                    rom_files_found = True
                    break
                elif f.upper().startswith('ROM_'):
                    rom_files_found = True
                    break
            
            if rom_files_found:
                self.spk_roms_dir = iso_dir
                self.update_status(f"Found ROM files in ISO directory")
            else:
                roms_dir = filedialog.askdirectory(
                    title="Select folder containing ROM.* files (rom.000, rom.001, etc.)"
                )
                if roms_dir:
                    self.spk_roms_dir = roms_dir
                else:
                    messagebox.showinfo("Info", "No ROM folder selected. Files cannot be extracted.")
                    self.spk_roms_dir = None
            
            self.current_spk = container_reader
            self.spk_mode = True
            self.spk_parent_entry = entry
            self.exit_container_btn.configure(state="normal")
            
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.item_data.clear()
            
            spk_entries = self.current_spk.get_entries()
            self.current_path = f"{entry['full_path']} [SPK]"
            roms_status = " (ROMs ready)" if self.spk_roms_dir else " (no ROMs)"
            self.path_label.configure(text=f"📀 {self.current_path}{roms_status}")
            
            for idx, spk_entry in enumerate(spk_entries):
                size_str = self._format_size_display(spk_entry.data_size)
                item_id = self.tree.insert(
                    "", "end",
                    text=f"📄 {spk_entry.filename}",
                    values=(size_str, f"SPK ({spk_entry.rom_name})", "")
                )
                
                self.item_data[item_id] = {
                    'name': spk_entry.filename,
                    'full_path': f"{entry['full_path']}/{spk_entry.filename}",
                    'is_directory': False,
                    'size': spk_entry.data_size,
                    'is_container_file': True,
                    'container_type': 'SPK',
                    'container_reader': self.current_spk,
                    'container_index': idx,
                    'date': '',
                    'rom_name': spk_entry.rom_name,
                    'data_off': spk_entry.data_off
                }
            
            cache_msg = " (from cache)" if from_cache else ""
            self.update_status(f"✅ SPK loaded{cache_msg}: {entry['name']} - {len(spk_entries)} files")
        else:
            messagebox.showwarning("Warning", "The file does not appear to be a valid SPK")
    
    def open_dbu(self, entry):
        """Open DBU file (Dragon Ball Z Sagas)"""
        container_reader, from_cache = self._load_container_with_cache(entry, 'DBU', DBUReader)
        
        if container_reader and len(container_reader.get_entries()) > 0:
            self.current_dbu = container_reader
            self.dbu_mode = True
            self.dbu_parent_entry = entry
            self.exit_container_btn.configure(state="normal")
            
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.item_data.clear()
            
            dbu_entries = self.current_dbu.get_entries()
            self.current_path = f"{entry['full_path']} [DBU]"
            self.path_label.configure(text=f"📀 {self.current_path}")
            
            for idx, dbu_entry in enumerate(dbu_entries):
                if dbu_entry.get('is_special', False):
                    size_str = "<SPECIAL>"
                else:
                    size_str = self._format_size_display(dbu_entry['size'])
                
                item_id = self.tree.insert(
                    "", "end",
                    text=f"📄 {dbu_entry['name']}",
                    values=(size_str, "DBU File", "")
                )
                
                self.item_data[item_id] = {
                    'name': dbu_entry['name'],
                    'full_path': f"{entry['full_path']}/{dbu_entry['name']}",
                    'is_directory': False,
                    'size': dbu_entry.get('size', 0),
                    'is_container_file': True,
                    'container_type': 'DBU',
                    'container_reader': self.current_dbu,
                    'container_index': idx,
                    'date': '',
                    'is_special': dbu_entry.get('is_special', False)
                }
            
            cache_msg = " (from cache)" if from_cache else ""
            self.update_status(f"✅ DBU loaded{cache_msg}: {entry['name']} - {len(dbu_entries)} files")
        else:
            messagebox.showwarning("Warning", "The file does not appear to be a valid DBU")
    
    def open_mfpack(self, entry):
        """Open MF Pack file (Fate/Stay Night)"""
        container_reader, from_cache = self._load_container_with_cache(entry, 'MF_PACK', MFPackReader)
        
        if container_reader and len(container_reader.get_entries()) > 0:
            self.current_mfpack = container_reader
            self.mfpack_mode = True
            self.mfpack_parent_entry = entry
            self.exit_container_btn.configure(state="normal")
            
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.item_data.clear()
            
            mf_entries = self.current_mfpack.get_entries()
            self.current_path = f"{entry['full_path']} [MF Pack]"
            self.path_label.configure(text=f"📦 {self.current_path}")
            
            for idx, mf_entry in enumerate(mf_entries):
                size_str = self._format_size_display(mf_entry['size'])
                comp_indicator = "🔒 " if mf_entry.get('is_compressed', False) else ""
                item_id = self.tree.insert(
                    "", "end",
                    text=f"{comp_indicator}📄 {mf_entry['name']}",
                    values=(size_str, "MF Pack File", "")
                )
                
                self.item_data[item_id] = {
                    'name': mf_entry['name'],
                    'full_path': f"{entry['full_path']}/{mf_entry['name']}",
                    'is_directory': False,
                    'size': mf_entry['size'],
                    'is_container_file': True,
                    'container_type': 'MF_PACK',
                    'container_reader': self.current_mfpack,
                    'container_index': idx,
                    'date': '',
                    'is_compressed': mf_entry.get('is_compressed', False)
                }
            
            cache_msg = " (from cache)" if from_cache else ""
            compressed_count = sum(1 for e in mf_entries if e.get('is_compressed', False))
            self.update_status(f"✅ MF Pack loaded{cache_msg}: {entry['name']} - {len(mf_entries)} files ({compressed_count} compressed)")
        else:
            messagebox.showwarning("Warning", "The file does not appear to be a valid MF Pack")
    
    def open_bnd(self, entry):
        """Open BND file (Various Games)"""
        container_reader, from_cache = self._load_container_with_cache(entry, 'BND', BNDReader)
        
        if container_reader and len(container_reader.get_entries()) > 0:
            self.current_bnd = container_reader
            self.bnd_mode = True
            self.bnd_parent_entry = entry
            self.exit_container_btn.configure(state="normal")
            
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.item_data.clear()
            
            bnd_entries = self.current_bnd.get_entries()
            self.current_path = f"{entry['full_path']} [BND]"
            self.path_label.configure(text=f"📦 {self.current_path}")
            
            for idx, bnd_entry in enumerate(bnd_entries):
                size_str = self._format_size_display(bnd_entry['size'])
                item_id = self.tree.insert(
                    "", "end",
                    text=f"📄 {bnd_entry['name']}",
                    values=(size_str, "BND File", "")
                )
                
                self.item_data[item_id] = {
                    'name': bnd_entry['name'],
                    'full_path': f"{entry['full_path']}/{bnd_entry['name']}",
                    'is_directory': False,
                    'size': bnd_entry['size'],
                    'is_container_file': True,
                    'container_type': 'BND',
                    'container_reader': self.current_bnd,
                    'container_index': idx,
                    'date': ''
                }
            
            cache_msg = " (from cache)" if from_cache else ""
            self.update_status(f"✅ BND loaded{cache_msg}: {entry['name']} - {len(bnd_entries)} files")
        else:
            messagebox.showwarning("Warning", "The file does not appear to be a valid BND")
    
    def play_adx_file(self, entry):
        """Play ADX audio file"""
        try:
            self.update_status(f"Playing ADX: {entry['name']}...")
            data = self.iso_reader.read_file_data(entry['location'], entry['size'])
            success = self.adx_player.play_adx(data, entry['name'])
            if success:
                self.update_status(f"🎵 Playing: {entry['name']}")
            else:
                self.update_status(f"⚠️ Could not play. Try extracting and playing with another player.", True)
        except Exception as e:
            self.update_status(f"❌ Error playing ADX: {str(e)}", True)
            messagebox.showerror("Error", f"Could not play ADX:\n{str(e)}")
    
    def open_rtpk(self, entry):
        """Open RTPK file"""
        container_reader, from_cache = self._load_container_with_cache(entry, 'RTPK', RTPKReader)
        
        if container_reader and container_reader.file_count > 0:
            self.current_rtpk = container_reader
            self.rtpk_mode = True
            self.rtpk_parent_entry = entry
            self.exit_container_btn.configure(state="normal")
            
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.item_data.clear()
            
            rtpk_entries = self.current_rtpk.get_entries()
            self.current_path = f"{entry['full_path']} [RTPK]"
            self.path_label.configure(text=f"🗃️ {self.current_path}")
            
            entries_by_dir = {}
            for idx, rtpk_entry in enumerate(rtpk_entries):
                dir_name = rtpk_entry.get('path_dir', '')
                if dir_name not in entries_by_dir:
                    entries_by_dir[dir_name] = []
                entries_by_dir[dir_name].append((idx, rtpk_entry))
            
            for dir_name, dir_entries in sorted(entries_by_dir.items()):
                if dir_name:
                    dir_id = self.tree.insert("", "end", text=f"📁 {dir_name}", values=("<DIR>", "Directory", ""))
                    for idx, rtpk_entry in dir_entries:
                        size_str = self._format_size_display(rtpk_entry['size'])
                        item_id = self.tree.insert(dir_id, "end", text=f"📄 {rtpk_entry['name']}", values=(size_str, "RTPK File", ""))
                        self._add_container_entry(item_id, rtpk_entry, entry, idx, 'RTPK', self.current_rtpk)
                else:
                    for idx, rtpk_entry in dir_entries:
                        size_str = self._format_size_display(rtpk_entry['size'])
                        item_id = self.tree.insert("", "end", text=f"📄 {rtpk_entry['name']}", values=(size_str, "RTPK File", ""))
                        self._add_container_entry(item_id, rtpk_entry, entry, idx, 'RTPK', self.current_rtpk)
            
            cache_msg = " (from cache)" if from_cache else ""
            self.update_status(f"✅ RTPK loaded{cache_msg}: {entry['name']} - {len(rtpk_entries)} files")
        else:
            messagebox.showwarning("Warning", "The file does not appear to be a valid RTPK")
    
    def open_mfa(self, entry):
        """Open MFA file (Silent Hill)"""
        container_reader, from_cache = self._load_container_with_cache(entry, 'MFA', MFAReader)
        
        if container_reader and len(container_reader.get_entries()) > 0:
            self.current_mfa = container_reader
            self.mfa_mode = True
            self.mfa_parent_entry = entry
            self.exit_container_btn.configure(state="normal")
            
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.item_data.clear()
            
            mfa_entries = self.current_mfa.get_entries()
            self.current_path = f"{entry['full_path']} [MFA]"
            self.path_label.configure(text=f"🎮 {self.current_path}")
            
            entries_by_dir = {}
            for idx, mfa_entry in enumerate(mfa_entries):
                if '/' in mfa_entry['name']:
                    dir_name = os.path.dirname(mfa_entry['name'])
                else:
                    dir_name = ''
                
                if dir_name not in entries_by_dir:
                    entries_by_dir[dir_name] = []
                entries_by_dir[dir_name].append((idx, mfa_entry))
            
            for dir_name, dir_entries in sorted(entries_by_dir.items()):
                if dir_name:
                    dir_id = self.tree.insert("", "end", text=f"📁 {dir_name}", values=("<DIR>", "Directory", ""))
                    for idx, mfa_entry in dir_entries:
                        size_str = self._format_size_display(mfa_entry['size'])
                        display_name = os.path.basename(mfa_entry['name'])
                        item_id = self.tree.insert(dir_id, "end", text=f"📄 {display_name}", values=(size_str, "MFA File", ""))
                        self._add_container_entry(item_id, mfa_entry, entry, idx, 'MFA', self.current_mfa)
                else:
                    for idx, mfa_entry in dir_entries:
                        size_str = self._format_size_display(mfa_entry['size'])
                        item_id = self.tree.insert("", "end", text=f"📄 {mfa_entry['name']}", values=(size_str, "MFA File", ""))
                        self._add_container_entry(item_id, mfa_entry, entry, idx, 'MFA', self.current_mfa)
            
            cache_msg = " (from cache)" if from_cache else ""
            self.update_status(f"✅ MFA loaded{cache_msg}: {entry['name']} - {len(mfa_entries)} files")
        else:
            messagebox.showwarning("Warning", "The file does not appear to be a valid MFA")
    
    def open_fpk(self, entry):
        """Open FPK file (Battle Stadium D.O.N.)"""
        container_reader, from_cache = self._load_container_with_cache(entry, 'FPK', FPKReader)
        
        if container_reader and len(container_reader.get_entries()) > 0:
            self.current_fpk = container_reader
            self.fpk_mode = True
            self.fpk_parent_entry = entry
            self.exit_container_btn.configure(state="normal")
            
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.item_data.clear()
            
            fpk_entries = self.current_fpk.get_entries()
            self.current_path = f"{entry['full_path']} [FPK]"
            self.path_label.configure(text=f"📦 {self.current_path}")
            
            for idx, fpk_entry in enumerate(fpk_entries):
                size_str = self._format_size_display(fpk_entry['size'])
                comp_indicator = "🔒 " if fpk_entry.get('is_compressed', False) else ""
                item_id = self.tree.insert(
                    "", "end",
                    text=f"{comp_indicator}📄 {fpk_entry['name']}",
                    values=(size_str, "FPK File", "")
                )
                
                self.item_data[item_id] = {
                    'name': fpk_entry['name'],
                    'full_path': f"{entry['full_path']}/{fpk_entry['name']}",
                    'is_directory': False,
                    'size': fpk_entry['size'],
                    'is_container_file': True,
                    'container_type': 'FPK',
                    'container_reader': self.current_fpk,
                    'container_index': idx,
                    'date': '',
                    'is_compressed': fpk_entry.get('is_compressed', False),
                    'zsize': fpk_entry.get('zsize', 0)
                }
            
            cache_msg = " (from cache)" if from_cache else ""
            compressed_count = sum(1 for e in fpk_entries if e.get('is_compressed', False))
            if compressed_count > 0:
                self.update_status(f"✅ FPK loaded{cache_msg}: {entry['name']} - {len(fpk_entries)} files ({compressed_count} compressed)")
            else:
                self.update_status(f"✅ FPK loaded{cache_msg}: {entry['name']} - {len(fpk_entries)} files")
        else:
            messagebox.showwarning("Warning", "The file does not appear to be a valid FPK")
    
    def _format_size_display(self, size):
        """Format size for display"""
        if size >= 1024 * 1024:
            return f"{size / (1024 * 1024):.2f} MB"
        elif size >= 1024:
            return f"{size / 1024:.2f} KB"
        else:
            return f"{size} B"
    
    def _add_container_entry(self, item_id, container_entry, parent_entry, idx, container_type, reader):
        """Add container entry to dictionary"""
        self.item_data[item_id] = {
            'name': container_entry['name'],
            'full_path': f"{parent_entry['full_path']}/{container_entry['name']}",
            'is_directory': False,
            'size': container_entry['size'],
            'is_container_file': True,
            'container_type': container_type,
            'container_reader': reader,
            'container_index': idx,
            'date': ''
        }
    
    def _get_entry_display(self, entry):
        """Get icon and text for entry display"""
        if entry['is_directory']:
            return "📁 ", "Directory", "<DIR>"
        
        icon = "📄 "
        type_str = "File"
        
        # Detect special formats
        name_lower = entry['name'].lower()
        name_upper = entry['name'].upper()
        
        # Ben 10 detection (game.dir)
        if name_lower == 'game.dir':
            icon = "🎮 "
            type_str = "Ben 10 WAD Index (game.dir)"
        # MELAN IDX detection
        elif name_upper.endswith('.IDX') and 'MELAN' in name_upper:
            icon = "📊 "
            type_str = "Melan Index (Suzumiya Haruhi)"
        # PAK detection (Di Gi Charat)
        elif name_upper.endswith('.PAK'):
            icon = "📦 "
            type_str = "PAK Archive (Di Gi Charat)"
        # SARA2 IDX detection
        elif 'SARA2.IDX' in name_upper or 'sara2.idx' in name_lower:
            icon = "📦 "
            type_str = "SARA2 Index (Critical Bullet)"
        # GL6 Sound Archive detection (by filename)
        elif 'GL6_SND' in name_upper or 'gl6_snd' in name_lower:
            icon = "🎵📦 "
            type_str = "GL6 Sound Archive"
        # FPK detection - check extension FIRST
        elif name_lower.endswith('.fpk'):
            icon = "📦 "
            type_str = "FPK Archive"
        elif name_lower.endswith('.afs'):
            icon = "📦 "
            type_str = "AFS Archive"
        elif name_lower.endswith(('.rtpk', '.rpk')):
            icon = "🗃️ "
            type_str = "RTPK Archive"
        elif name_lower.endswith('.mfa'):
            icon = "🎮 "
            type_str = "MFA Archive"
        elif name_lower.endswith('.spk') or name_lower.endswith('.rom') or name_lower == 'spk.rom':
            icon = "📀 "
            type_str = "SPK Archive (Siren 2)"
        elif name_lower.endswith('.dbu'):
            icon = "📀 "
            type_str = "DBU Archive (DBZ Sagas)"
        elif name_lower.endswith('.mf') or (name_lower.endswith('.bin') and 'data' in name_lower):
            icon = "📦 "
            type_str = "MF Pack Archive (Fate/Stay Night)"
        elif name_lower.endswith('.bnd'):
            icon = "📦 "
            type_str = "BND Archive"
        elif name_lower.endswith('.efs'):
            icon = "📦 "
            type_str = "EFS Container"
        elif name_lower.endswith('.adx'):
            icon = "🎵 "
            type_str = "ADX Audio"
        
        # Format size
        size = entry['size']
        if size >= 1024 * 1024 * 1024:
            size_str = f"{size / (1024 * 1024 * 1024):.2f} GB"
        elif size >= 1024 * 1024:
            size_str = f"{size / (1024 * 1024):.2f} MB"
        elif size >= 1024:
            size_str = f"{size / 1024:.2f} KB"
        else:
            size_str = f"{size} B"
        
        return icon, type_str, size_str
    
    def open_iso(self):
        """Open ISO file"""
        file_path = filedialog.askopenfilename(
            title="Select PS2 ISO",
            filetypes=[("ISO files", "*.iso"), ("BIN files", "*.bin"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
            
        try:
            self.update_status(f"Loading ISO: {os.path.basename(file_path)}...")
            
            if self.iso_reader:
                self.iso_reader.close()
                
            self.iso_reader = ISO9660Reader(file_path)
            self.iso_reader.open()
            self.current_iso_path = file_path
            
            self.is_budokai_hd_afs = False
            
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.item_data.clear()
            
            self.current_path = ""
            self.afs_mode = self.rtpk_mode = self.mfa_mode = self.fpk_mode = self.spk_mode = self.dbu_mode = self.mfpack_mode = self.bnd_mode = self.efs_mode = self.gzip_mode = self.gl6_mode = self.sara2_mode = self.pak_mode = self.melan_mode = self.ben10_mode = False
            self.current_afs = self.current_rtpk = self.current_mfa = self.current_fpk = self.current_spk = self.current_dbu = self.current_mfpack = self.current_bnd = self.current_efs = self.current_gzip = self.current_gl6 = self.current_sara2 = self.current_pak = self.current_melan = self.current_ben10 = None
            self.afs_parent_entry = self.rtpk_parent_entry = self.mfa_parent_entry = self.fpk_parent_entry = self.spk_parent_entry = self.dbu_parent_entry = self.mfpack_parent_entry = self.bnd_parent_entry = self.efs_parent_entry = self.gzip_parent_entry = self.gl6_parent_entry = self.sara2_parent_entry = self.pak_parent_entry = self.melan_parent_entry = self.ben10_parent_entry = None
            self.spk_roms_dir = None
            self.sara2_pac_data = None
            self.melan_img_data = None
            self.ben10_wad_data = None
            self.exit_container_btn.configure(state="disabled")
            
            self._load_directory(self.iso_reader.root_directory)
            self.path_label.configure(text=f"📁 /")
            
            self.extract_btn.configure(state="normal")
            self.info_btn.configure(state="normal")
            self.back_btn.configure(state="normal")
            
            self.update_status(f"✅ ISO loaded: {os.path.basename(file_path)}")
            
        except Exception as e:
            self.update_status(f"❌ Error loading ISO: {str(e)}", True)
            messagebox.showerror("Error", f"Could not load ISO:\n{str(e)}")
    
    def _load_directory(self, directory_entry):
        """Load directory contents"""
        try:
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.item_data.clear()
                
            entries = self.iso_reader.read_directory(
                directory_entry['location'],
                directory_entry['full_path']
            )
            
            self.current_entries = entries
            entries.sort(key=lambda x: (not x['is_directory'], x['name'].lower()))
            
            for entry in entries:
                if entry['name'] in ['.', '..']:
                    continue
                    
                icon, type_str, size_str = self._get_entry_display(entry)
                        
                item_id = self.tree.insert(
                    "", "end",
                    text=f"{icon}{entry['name']}",
                    values=(size_str, type_str, entry['date'])
                )
                
                self.item_data[item_id] = entry
                
        except Exception as e:
            self.update_status(f"Error loading directory: {str(e)}", True)
    
    def exit_container(self):
        """Exit current container"""
        if self.afs_mode and self.iso_reader and self.afs_parent_entry:
            self.afs_mode = False
            self.current_afs = None
            parent_entry = self.afs_parent_entry
            self.afs_parent_entry = None
        elif self.rtpk_mode and self.iso_reader and self.rtpk_parent_entry:
            self.rtpk_mode = False
            self.current_rtpk = None
            parent_entry = self.rtpk_parent_entry
            self.rtpk_parent_entry = None
        elif self.mfa_mode and self.iso_reader and self.mfa_parent_entry:
            self.mfa_mode = False
            self.current_mfa = None
            parent_entry = self.mfa_parent_entry
            self.mfa_parent_entry = None
        elif self.fpk_mode and self.iso_reader and self.fpk_parent_entry:
            self.fpk_mode = False
            self.current_fpk = None
            parent_entry = self.fpk_parent_entry
            self.fpk_parent_entry = None
        elif self.spk_mode and self.iso_reader and self.spk_parent_entry:
            self.spk_mode = False
            self.current_spk = None
            parent_entry = self.spk_parent_entry
            self.spk_parent_entry = None
            self.spk_roms_dir = None
        elif self.dbu_mode and self.iso_reader and self.dbu_parent_entry:
            self.dbu_mode = False
            self.current_dbu = None
            parent_entry = self.dbu_parent_entry
            self.dbu_parent_entry = None
        elif self.mfpack_mode and self.iso_reader and self.mfpack_parent_entry:
            self.mfpack_mode = False
            self.current_mfpack = None
            parent_entry = self.mfpack_parent_entry
            self.mfpack_parent_entry = None
        elif self.bnd_mode and self.iso_reader and self.bnd_parent_entry:
            self.bnd_mode = False
            self.current_bnd = None
            parent_entry = self.bnd_parent_entry
            self.bnd_parent_entry = None
        elif self.efs_mode and self.iso_reader and self.efs_parent_entry:
            self.efs_mode = False
            self.current_efs = None
            parent_entry = self.efs_parent_entry
            self.efs_parent_entry = None
        elif self.gzip_mode and self.iso_reader and self.gzip_parent_entry:
            self.gzip_mode = False
            self.current_gzip = None
            parent_entry = self.gzip_parent_entry
            self.gzip_parent_entry = None
        elif self.gl6_mode and self.iso_reader and self.gl6_parent_entry:
            self.gl6_mode = False
            self.current_gl6 = None
            parent_entry = self.gl6_parent_entry
            self.gl6_parent_entry = None
        elif self.sara2_mode and self.iso_reader and self.sara2_parent_entry:
            self.sara2_mode = False
            self.current_sara2 = None
            parent_entry = self.sara2_parent_entry
            self.sara2_parent_entry = None
            self.sara2_pac_data = None
        elif self.pak_mode and self.iso_reader and self.pak_parent_entry:
            self.pak_mode = False
            self.current_pak = None
            parent_entry = self.pak_parent_entry
            self.pak_parent_entry = None
        elif self.melan_mode and self.iso_reader and self.melan_parent_entry:
            self.melan_mode = False
            self.current_melan = None
            parent_entry = self.melan_parent_entry
            self.melan_parent_entry = None
            self.melan_img_data = None
        elif self.ben10_mode and self.iso_reader and self.ben10_parent_entry:
            self.ben10_mode = False
            self.current_ben10 = None
            parent_entry = self.ben10_parent_entry
            self.ben10_parent_entry = None
            self.ben10_wad_data = None
        else:
            return
            
        if self.afs_mode and self.afs_parent_entry:
            self.is_budokai_hd_afs = False
        
        parent_dir = os.path.dirname(parent_entry['full_path'])
        if parent_dir == '':
            self._load_directory(self.iso_reader.root_directory)
            self.current_path = ""
            self.path_label.configure(text=f"📁 /")
        else:
            self._load_directory(self.iso_reader.root_directory)
            self.current_path = parent_dir
            self.path_label.configure(text=f"📁 {parent_dir}")
        
        self.exit_container_btn.configure(state="disabled")
        self.update_status("✅ Exited container")
    
    def on_select(self, event):
        """Handle file selection"""
        selection = self.tree.selection()
        if not selection:
            return
            
        entry = self.item_data.get(selection[0])
        if not entry:
            return
            
        details = f"""
╔══════════════════════════════════════╗
║           FILE INFORMATION            ║
╚══════════════════════════════════════╝

📄 Name: {entry['name']}
📁 Path: {entry.get('full_path', 'N/A')}
{'📂 Type: Directory' if entry.get('is_directory', False) else '📄 Type: File'}
💾 Size: {self.format_size(entry.get('size', 0))}
📅 Date: {entry.get('date', 'Not available')}
"""
        
        if entry.get('is_container_file', False):
            details += f"""
🔧 Container: {entry.get('container_type', 'Unknown')}
"""
            if entry.get('is_compressed', False):
                details += f"🔒 Compressed: {entry.get('zsize', 0)} -> {entry.get('size', 0)} bytes\n"
            if entry.get('container_type') == 'SPK':
                details += f"📀 ROM: {entry.get('rom_name', 'Unknown')}\n"
                details += f"📍 Data Offset: {entry.get('data_off', 'N/A')}\n"
            elif entry.get('container_type') == 'MF_PACK':
                details += f"📦 Format: MF Pack (UFFA)\n"
                details += f"🔧 Compression: {'Yes (LZSS)' if entry.get('is_compressed', False) else 'No'}\n"
            elif entry.get('container_type') == 'EFS':
                if entry.get('is_header', False):
                    details += f"📄 Type: Header file (empty)\n"
                else:
                    details += f"📄 Type: Data file\n"
            elif entry.get('container_type') == 'GZIP':
                details += f"🗜️ Type: GZIP compressed data (Budokai HD)\n"
                details += f"📦 Original file: {entry.get('original_name', 'Unknown')}\n"
            elif entry.get('container_type') == 'GL6':
                details += f"🎵 Type: VAG audio (Growlanser VI)\n"
                details += f"📍 Offset: 0x{entry.get('offset', 0):08X}\n"
            elif entry.get('container_type') == 'SARA2':
                details += f"📦 Type: SARA2 Archive (Critical Bullet)\n"
                details += f"📍 Offset: 0x{entry.get('offset', 0):08X}\n"
            elif entry.get('container_type') == 'PAK':
                details += f"📦 Type: PAK Archive (Di Gi Charat)\n"
                details += f"📍 Offset: 0x{entry.get('offset', 0):08X}\n"
                if entry.get('inner_magic'):
                    details += f"🔮 Magic: {entry.get('inner_magic')} - {entry.get('magic_desc', '')}\n"
            elif entry.get('container_type') == 'MELAN':
                details += f"📊 Type: Melan Archive (Suzumiya Haruhi)\n"
                if not entry.get('is_directory'):
                    details += f"📍 Offset: {entry.get('record').img_offset * 2048} bytes (sector {entry.get('record').img_offset})\n"
            elif entry.get('container_type') == 'BEN10':
                details += f"🎮 Type: Ben 10: Protector of Earth WAD\n"
                details += f"📍 Offset: 0x{entry.get('offset', 0):08X}\n"
                details += f"📀 Sector: {entry.get('sector', 0)}\n"
                details += f"🎬 Format: {entry.get('type', 'Unknown')}\n"
                details += f"💡 Files: .bik (Bink Video), .pss (PSS Video), .psm (PSM Texture), .txt (Text)\n"
            elif entry.get('is_budokai_gzip', False):
                details += f"🗜️ Type: GZIP compressed data (Budokai HD Collection)\n"
                details += f"💡 Double-click to decompress and view contents\n"
            details += """
💡 You can extract this file using the Extract button
"""
        elif entry['name'].lower() == 'game.dir':
            details += """
🎮 Ben 10: Protector of Earth - game.dir
💡 Double-click to open the game.wad archive

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This file is the index for game.wad. It contains:
  - .bik (Bink Video) - FMV cutscenes
  - .pss (PSS Video) - In-game videos
  - .psm (PSM Texture) - Textures and images
  - .txt (Text File) - Game text data

💡 Double-click to view all files inside game.wad
"""
        elif entry['name'].lower().endswith('.adx'):
            details += """
🎵 ADX Audio
💡 Double-click to play this audio

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 You can also extract it with the Extract button
"""
        elif entry.get('name', '').lower().endswith('.rom') or entry.get('name', '').lower() == 'spk.rom':
            details += """
📀 SPK Archive (Siren 2)
💡 Double-click to open and extract files

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 This is the main index file for Siren 2
💡 ROM.* files must be in the same folder as the ISO
"""
        elif entry.get('name', '').lower().endswith('.dbu'):
            details += """
📀 DBU Archive (Dragon Ball Z Sagas)
💡 Double-click to open and extract files

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 Contains game data files
"""
        elif entry.get('name', '').lower().endswith('.bin') and 'data' in entry.get('name', '').lower():
            details += """
📦 MF Pack Archive (Fate/Stay Night)
💡 Double-click to open and extract files

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 Contains game data files (UFFA format)
💡 Files may be compressed with LZSS
"""
        elif entry.get('name', '').lower().endswith('.bnd'):
            details += """
📦 BND Archive
💡 Double-click to open and extract files

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 Contains game data files
"""
        elif entry.get('name', '').lower().endswith('.efs'):
            details += """
📦 EFS Container
💡 Double-click to open and extract files

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 Contains data file and header file
"""
        elif not entry.get('is_directory', False):
            details += f"""
📍 Sector: {entry.get('location', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 To extract this file, select it and press the Extract button
💡 Right-click and select 'View in Hex' for hex viewer
"""
        else:
            details += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 Directory - Double-click to enter
"""
        
        self.details_text.delete("1.0", "end")
        self.details_text.insert("1.0", details)
    
    def on_double_click(self, event):
        """Handle double click"""
        selection = self.tree.selection()
        if not selection:
            return
            
        entry = self.item_data.get(selection[0])
        if not entry:
            return
        
        name_lower = entry['name'].lower()
        name_upper = entry['name'].upper()
        
        # Ben 10 detection - check for game.dir
        if name_lower == 'game.dir':
            self.open_ben10(entry)
        elif entry.get('container_type') == 'BEN10':
            messagebox.showinfo("Info", f"Ben 10 File: {entry['name']}\n\nYou can extract it with the Extract button.")
        elif entry.get('container_type') == 'GL6':
            messagebox.showinfo("Info", f"VAG Audio File: {entry['name']}\n\nYou can extract it with the Extract button.")
        elif entry.get('is_budokai_gzip', False):
            self.open_gzip_from_afs(entry)
        # Check for FPK archive from DATA.AFS
        elif entry.get('is_fpk_archive', False):
            self.open_fpk_from_afs(entry)
        # Check for PAK files (Di Gi Charat)
        elif name_upper.endswith('.PAK'):
            self.open_pak(entry)
        # Check for MELAN IDX files
        elif name_upper.endswith('.IDX') and 'MELAN' in name_upper:
            self.open_melan(entry)
        elif entry.get('is_container_file', False):
            messagebox.showinfo("Info", f"Cannot open files inside a {entry.get('container_type', 'container')}")
        elif entry.get('is_directory', False):
            self.current_path = entry['full_path']
            self.path_label.configure(text=f"📁 {self.current_path}")
            self._load_directory(entry)
        # SARA2 IDX detection
        elif 'SARA2.IDX' in name_upper or 'sara2.idx' in name_lower:
            self.open_sara2(entry)
        # FPK must be checked BEFORE AFS
        elif name_lower.endswith('.fpk'):
            self.open_fpk(entry)
        elif name_lower.endswith('.adx'):
            self.play_adx_file(entry)
        elif name_lower.endswith('.afs'):
            self.open_afs(entry)
        elif name_lower.endswith(('.rtpk', '.rpk')):
            self.open_rtpk(entry)
        elif name_lower.endswith('.mfa'):
            self.open_mfa(entry)
        elif name_lower.endswith('.spk') or name_lower.endswith('.rom') or name_lower == 'spk.rom':
            self.open_spk(entry)
        elif name_lower.endswith('.dbu'):
            self.open_dbu(entry)
        elif name_lower.endswith('.bin') and 'data' in name_lower:
            if 'gl6_snd' in name_lower or 'gl6_snd' in entry['full_path'].lower():
                self.open_gl6(entry)
            else:
                self.open_mfpack(entry)
        elif name_lower.endswith('.dat') and 'gl6_snd' in name_lower:
            self.open_gl6(entry)
        elif name_lower.endswith('.mf'):
            self.open_mfpack(entry)
        elif name_lower.endswith('.bnd'):
            self.open_bnd(entry)
        elif name_lower.endswith('.efs'):
            self.open_efs(entry)
        elif name_lower.endswith('.bin'):
            self.open_gzip(entry)
    
    def go_back(self):
        """Go back to previous directory"""
        if self.afs_mode or self.rtpk_mode or self.mfa_mode or self.fpk_mode or self.spk_mode or self.dbu_mode or self.mfpack_mode or self.bnd_mode or self.efs_mode or self.gzip_mode or self.gl6_mode or self.sara2_mode or self.pak_mode or self.melan_mode or self.ben10_mode:
            self.exit_container()
            return
            
        if not self.iso_reader or not self.current_path:
            return
            
        parent_path = os.path.dirname(self.current_path.rstrip('/'))
        
        if parent_path == '':
            self.current_path = ''
            self.path_label.configure(text="📁 /")
            self._load_directory(self.iso_reader.root_directory)
        else:
            self.current_path = parent_path
            self.path_label.configure(text=f"📁 {self.current_path}")
            self._load_directory(self.iso_reader.root_directory)
    
    def extract_selected(self):
        """Extract selected file"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Select a file to extract")
            return
            
        entry = self.item_data.get(selection[0])
        if not entry:
            messagebox.showwarning("Warning", "No file data found")
            return
            
        if entry.get('is_directory', False):
            messagebox.showinfo("Info", "Directory extraction not implemented\nSelect an individual file")
            return
            
        dest_path = filedialog.asksaveasfilename(
            title="Save file as",
            defaultextension=".bin",
            initialfile=entry['name']
        )
        
        if not dest_path:
            return
            
        try:
            self.update_status(f"Extracting {entry['name']}...")
            
            if entry.get('container_type') == 'BEN10':
                reader = entry.get('container_reader')
                idx = entry.get('container_index')
                if reader and idx is not None:
                    success, msg = reader.extract_file(idx, dest_path)
                    if success:
                        self.update_status(f"✅ File extracted from Ben 10 WAD: {os.path.basename(dest_path)}")
                        messagebox.showinfo("Success", f"File extracted successfully:\n{dest_path}")
                    else:
                        raise Exception(msg)
                else:
                    raise Exception("Error extracting from Ben 10 WAD")
            
            elif entry.get('container_type') == 'MELAN':
                reader = entry.get('container_reader')
                record = entry.get('record')
                if reader and record:
                    success, msg = reader.extract_file_by_record(record, dest_path)
                    if success:
                        self.update_status(f"✅ File extracted from Melan: {os.path.basename(dest_path)}")
                        messagebox.showinfo("Success", f"File extracted successfully:\n{dest_path}")
                    else:
                        raise Exception(msg)
                else:
                    raise Exception("Error extracting from Melan")
            
            elif entry.get('container_type') == 'GL6':
                reader = entry.get('container_reader')
                idx = entry.get('container_index')
                if reader and idx is not None:
                    success, msg = reader.extract_file(idx, dest_path)
                    if success:
                        self.update_status(f"✅ VAG audio extracted: {os.path.basename(dest_path)}")
                        messagebox.showinfo("Success", f"VAG audio extracted successfully:\n{dest_path}")
                    else:
                        raise Exception(msg)
                else:
                    raise Exception("Error extracting")
            
            elif entry.get('container_type') == 'PAK':
                reader = entry.get('container_reader')
                idx = entry.get('container_index')
                if reader and idx is not None:
                    success, msg = reader.extract_file(idx, dest_path)
                    if success:
                        self.update_status(f"✅ File extracted from PAK: {os.path.basename(dest_path)}")
                        messagebox.showinfo("Success", f"File extracted successfully:\n{dest_path}")
                    else:
                        raise Exception(msg)
                else:
                    raise Exception("Error extracting")
            
            elif entry.get('container_type') == 'SARA2':
                reader = entry.get('container_reader')
                idx = entry.get('container_index')
                if reader and idx is not None:
                    success, msg = reader.extract_file(idx, dest_path)
                    if success:
                        self.update_status(f"✅ File extracted from SARA2: {os.path.basename(dest_path)}")
                        messagebox.showinfo("Success", f"File extracted successfully:\n{dest_path}")
                    else:
                        raise Exception(msg)
                else:
                    raise Exception("Error extracting")
            
            elif entry.get('is_fpk_archive', False):
                # Extract from FPK in DATA.AFS
                reader = entry.get('container_reader')
                idx = entry.get('container_index')
                if reader and idx is not None:
                    raw_data = reader.get_file_data(idx)
                    if raw_data:
                        fpk_reader = FPKReader(raw_data, entry['name'], self.iso_reader, entry['full_path'])
                        if fpk_reader and len(fpk_reader.get_entries()) > 0:
                            # Extract all files from FPK? For now, extract the raw FPK
                            with open(dest_path, 'wb') as f:
                                f.write(raw_data)
                            self.update_status(f"✅ FPK file extracted: {os.path.basename(dest_path)}")
                            messagebox.showinfo("Success", f"FPK file extracted successfully:\n{dest_path}")
                        else:
                            with open(dest_path, 'wb') as f:
                                f.write(raw_data)
                            self.update_status(f"✅ Raw file extracted: {os.path.basename(dest_path)}")
                            messagebox.showinfo("Success", f"File extracted successfully:\n{dest_path}")
                    else:
                        raise Exception("Could not read file data")
            
            elif entry.get('is_budokai_gzip', False):
                reader = entry.get('container_reader')
                idx = entry.get('container_index')
                if reader and idx is not None:
                    raw_data = reader.get_file_data(idx)
                    if raw_data:
                        gzip_reader = GZIPReader(raw_data, entry['name'], self.iso_reader, entry['full_path'])
                        if gzip_reader and gzip_reader.is_gzip:
                            decompressed_data = gzip_reader.get_decompressed_data()
                            if decompressed_data:
                                with open(dest_path, 'wb') as f:
                                    f.write(decompressed_data)
                                self.update_status(f"✅ File extracted (decompressed): {os.path.basename(dest_path)}")
                                messagebox.showinfo("Success", f"File extracted successfully:\n{dest_path}")
                                return
                    
                    raw_data = reader.get_file_data(idx)
                    if raw_data:
                        with open(dest_path, 'wb') as f:
                            f.write(raw_data)
                        self.update_status(f"✅ Raw file extracted: {os.path.basename(dest_path)}")
                        messagebox.showinfo("Success", f"File extracted successfully:\n{dest_path}")
                        return
                    else:
                        raise Exception("Could not read file data")
            
            elif entry.get('container_type') == 'SPK':
                if not self.spk_roms_dir:
                    iso_dir = os.path.dirname(self.current_iso_path)
                    rom_files_found = False
                    for f in os.listdir(iso_dir):
                        if f.upper().startswith('ROM.') and f.upper().endswith('.ROM'):
                            rom_files_found = True
                            break
                        elif f.upper().startswith('ROM_'):
                            rom_files_found = True
                            break
                    
                    if rom_files_found:
                        self.spk_roms_dir = iso_dir
                        self.update_status(f"Found ROM files in ISO directory")
                    else:
                        roms_dir = filedialog.askdirectory(
                            title="Select folder containing ROM.* files"
                        )
                        if not roms_dir:
                            messagebox.showinfo("Info", "ROM files are needed for extraction")
                            return
                        self.spk_roms_dir = roms_dir
                
                reader = entry.get('container_reader')
                idx = entry.get('container_index')
                if reader and idx is not None:
                    success, msg = reader.extract_file(idx, dest_path, self.spk_roms_dir)
                    if success:
                        self.update_status(f"✅ File extracted: {os.path.basename(dest_path)}")
                        messagebox.showinfo("Success", f"File extracted successfully:\n{dest_path}")
                    else:
                        raise Exception(msg)
                else:
                    raise Exception("Error extracting")
            
            elif entry.get('container_type') == 'DBU':
                reader = entry.get('container_reader')
                idx = entry.get('container_index')
                if reader and idx is not None:
                    success, msg = reader.extract_file(idx, dest_path)
                    if success:
                        self.update_status(f"✅ File extracted: {os.path.basename(dest_path)}")
                        messagebox.showinfo("Success", f"File extracted successfully:\n{dest_path}")
                    else:
                        raise Exception(msg)
                else:
                    raise Exception("Error extracting")
            
            elif entry.get('container_type') == 'MF_PACK':
                reader = entry.get('container_reader')
                idx = entry.get('container_index')
                if reader and idx is not None:
                    success, msg = reader.extract_file(idx, dest_path)
                    if success:
                        self.update_status(f"✅ File extracted: {os.path.basename(dest_path)}")
                        messagebox.showinfo("Success", f"File extracted successfully:\n{dest_path}")
                    else:
                        raise Exception(msg)
                else:
                    raise Exception("Error extracting")
            
            elif entry.get('container_type') == 'BND':
                reader = entry.get('container_reader')
                idx = entry.get('container_index')
                if reader and idx is not None:
                    success, msg = reader.extract_file(idx, dest_path)
                    if success:
                        self.update_status(f"✅ File extracted: {os.path.basename(dest_path)}")
                        messagebox.showinfo("Success", f"File extracted successfully:\n{dest_path}")
                    else:
                        raise Exception(msg)
                else:
                    raise Exception("Error extracting")
            
            elif entry.get('container_type') == 'EFS':
                reader = entry.get('container_reader')
                idx = entry.get('container_index')
                if reader and idx is not None:
                    success, msg = reader.extract_file(idx, dest_path)
                    if success:
                        self.update_status(f"✅ File extracted: {os.path.basename(dest_path)}")
                        messagebox.showinfo("Success", f"File extracted successfully:\n{dest_path}")
                    else:
                        raise Exception(msg)
                else:
                    raise Exception("Error extracting")
            
            elif entry.get('container_type') == 'GZIP':
                reader = entry.get('container_reader')
                idx = entry.get('container_index')
                if reader and idx is not None:
                    success, msg = reader.extract_file(idx, dest_path)
                    if success:
                        self.update_status(f"✅ File extracted (decompressed): {os.path.basename(dest_path)}")
                        messagebox.showinfo("Success", f"File extracted successfully:\n{dest_path}")
                    else:
                        raise Exception(msg)
                else:
                    raise Exception("Error extracting")
                    
            elif entry.get('is_container_file', False):
                reader = entry.get('container_reader')
                idx = entry.get('container_index')
                if reader and idx is not None:
                    if reader.extract_file(idx, dest_path):
                        self.update_status(f"✅ File extracted: {os.path.basename(dest_path)}")
                        messagebox.showinfo("Success", f"File extracted successfully:\n{dest_path}")
                    else:
                        raise Exception("Error extracting")
            else:
                data = self.iso_reader.read_file_data(entry['location'], entry['size'])
                with open(dest_path, 'wb') as f:
                    f.write(data)
                self.update_status(f"✅ File extracted: {os.path.basename(dest_path)}")
                messagebox.showinfo("Success", f"File extracted successfully:\n{dest_path}")
            
        except Exception as e:
            self.update_status(f"❌ Error extracting: {str(e)}", True)
            messagebox.showerror("Error", f"Error extracting file:\n{str(e)}")
    
    def show_iso_info(self):
        """Show ISO information"""
        if not self.iso_reader or not self.iso_reader.volume_descriptor:
            messagebox.showinfo("Info", "No ISO loaded")
            return
            
        vd = self.iso_reader.volume_descriptor
        cache_info = self.cache_manager.get_cache_info()
        
        info = f"""
╔══════════════════════════════════════════════╗
║           ISO VOLUME INFORMATION             ║
╚══════════════════════════════════════════════╝

📀 Identifier: {vd.get('standard_id', 'N/A')}
💿 Volume ID: {vd.get('volume_id', 'N/A')}
🖥️ System ID: {vd.get('system_id', 'N/A')}
📦 Volume Size: {vd.get('volume_space_size', 0)} sectors
📏 Block Size: {vd.get('logical_block_size', 2048)} bytes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 Root Directory: Sector {self.iso_reader.root_directory['location'] if self.iso_reader.root_directory else 'N/A'}

✨ Supported Formats:
   • ISO9660 - Standard structure
   • AFS - Data archives
   • RTPK/RPK - Rapid Pack
   • MFA - Silent Hill 2/3
   • FPK - Battle Stadium D.O.N.
   • SPK - Siren 2 (requires ROM.* files)
   • DBU - Dragon Ball Z Sagas
   • MF Pack - Fate/Stay Night (UFFA format)
   • BND - Various games archive
   • EFS - Container format (data + header)
   • GZIP - Compressed data (Budokai HD Collection)
   • GL6 - Growlanser VI sound archive (VAG audio)
   • SARA2 - Critical Bullet 7th Target (IDX + PAC)
   • PAK - Di Gi Charat Fantasy Excellent
   • MELAN - Suzumiya Haruhi no Tomadoi (IDX + IMG)
   • BEN10 - Ben 10: Protector of Earth (game.dir + game.wad)
   • ADX - Audio (double-click to play)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💾 Temporary Cache:
   • Files: {cache_info['entries']}
   • Size: {cache_info['size_mb']:.2f} MB
   • Location: {self.cache_manager.cache_dir}

💡 Ben 10: Double-click game.dir to view game.wad contents
💡 Budokai HD: When opening DATA_CMN.AFS (3990 files), all files are GZIP compressed
💡 DATA.AFS (135 files): Contains FPK archives - double-click to open
💡 Critical Bullet: Double-click SARA2.IDX to extract files from SARA2.PAC
💡 Di Gi Charat: Double-click EFFECT.PAK or ETC.PAK to extract files
💡 Suzumiya Haruhi: Double-click melan.idx to extract files from melan.img
💡 Right-click any file and select 'View in Hex' for hex viewer
"""
        
        messagebox.showinfo("ISO Information", info)
    
    def __del__(self):
        """Cleanup resources"""
        self.adx_player.cleanup()
        if hasattr(self, 'iso_reader') and self.iso_reader:
            try:
                self.iso_reader.close()
            except:
                pass


# Need to import tkinter for Menu
import tkinter as tk

if __name__ == "__main__":
    # pip install customtkinter
    app = HuziadGameExplorer()
    app.mainloop()
