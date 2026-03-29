"""
Base classes for Huziad Game Explorer plugins
"""
from abc import ABC, abstractmethod

class ContainerPlugin(ABC):
    """Base class for container format plugins"""
    
    # Plugin metadata
    plugin_name = "Base Plugin"
    plugin_version = "1.0"
    plugin_author = "Unknown"
    plugin_description = "Base plugin for container formats"
    
    # File detection
    file_extensions = []  # e.g., ['.vol', '.pak']
    file_magic_bytes = {}  # e.g., {b'VOL\x00': 0}
    file_names = []  # e.g., ['game.vol', 'data.vol']
    
    # UI settings
    icon = "📦"  # Default icon for files of this type
    container_type_name = "Container"  # Display name
    priority = 50  # Default priority
    
    @classmethod
    @abstractmethod
    def can_handle(cls, filename, data, iso_reader=None, entries=None):
        """
        Check if this plugin can handle the given file
        Returns: (can_handle, priority)
        priority: 0-100, higher means more specific
        """
        pass
    
    @classmethod
    @abstractmethod
    def create_reader(cls, entry, iso_reader, data=None):
        """
        Create a reader instance for this container
        Returns: ContainerReader instance
        """
        pass


class ContainerReader(ABC):
    """Base class for container readers"""
    
    def __init__(self, data, filename="", parent_iso=None, parent_path=""):
        self.data = data
        self.filename = filename
        self.parent_iso = parent_iso
        self.parent_path = parent_path
        self.entries = []
        
    @abstractmethod
    def load(self):
        """Load and parse the container format"""
        pass
    
    @abstractmethod
    def get_entries(self):
        """Get list of entries in the container"""
        pass
    
    @abstractmethod
    def extract_file(self, index, output_path):
        """Extract a specific file from the container"""
        pass
    
    @abstractmethod
    def get_file_data(self, index):
        """Get data of a specific file"""
        pass
    
    def get_stats(self):
        """Get statistics about the container"""
        return {
            'files': len(self.entries),
            'type': self.__class__.__name__
        }
