"""
Plugin manager for Huziad Game Explorer
"""
import os
import importlib
import inspect
from pathlib import Path

class PluginManager:
    """Manages loading and discovery of plugins"""
    
    def __init__(self, plugins_dir="plugins"):
        self.plugins_dir = plugins_dir
        self.plugins = []  # List of plugin classes
        self.readers = {}  # filename -> (plugin, reader_instance)
        self._loaded = False
    
    def discover_plugins(self):
        """Discover and load all plugins from plugins directory"""
        if self._loaded:
            return self.plugins
        
        plugins_path = Path(self.plugins_dir)
        if not plugins_path.exists():
            print(f"[PluginManager] Plugins directory not found: {self.plugins_dir}")
            return []
        
        # Add plugins directory to Python path
        import sys
        if str(plugins_path.parent) not in sys.path:
            sys.path.insert(0, str(plugins_path.parent))
        
        # Find all Python files in plugins directory
        for py_file in plugins_path.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            
            module_name = f"plugins.{py_file.stem}"
            try:
                # Import the module
                module = importlib.import_module(module_name)
                
                # Find all classes that inherit from ContainerPlugin
                from .plugin_base import ContainerPlugin  # Cambiado a importación relativa
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, ContainerPlugin) and obj != ContainerPlugin:
                        self.plugins.append(obj)
                        print(f"[PluginManager] Loaded plugin: {obj.plugin_name} v{obj.plugin_version}")
                        
            except Exception as e:
                print(f"[PluginManager] Error loading plugin {py_file.name}: {e}")
                import traceback
                traceback.print_exc()
        
        # Sort plugins by priority (can be defined by plugin)
        self.plugins.sort(key=lambda p: getattr(p, 'priority', 50), reverse=True)
        self._loaded = True
        return self.plugins
    
    def get_plugin_for_file(self, filename, data, iso_reader=None, entries=None):
        """Find the best plugin for a given file"""
        best_plugin = None
        best_priority = -1
        
        for plugin_class in self.plugins:
            try:
                can_handle, priority = plugin_class.can_handle(
                    filename, data, iso_reader, entries
                )
                if can_handle and priority > best_priority:
                    best_plugin = plugin_class
                    best_priority = priority
            except Exception as e:
                print(f"[PluginManager] Error checking plugin {plugin_class.plugin_name}: {e}")
        
        return best_plugin
    
    def create_reader(self, plugin_class, entry, iso_reader, data=None):
        """Create a reader instance using the plugin"""
        return plugin_class.create_reader(entry, iso_reader, data)
