"""
Módulo para gestionar caché temporal de archivos
Permite acceso rápido a contenedores previamente abiertos
"""
import os
import pickle
import hashlib
import json
from datetime import datetime
import threading

class CacheManager:
    """Gestor de caché temporal para archivos de contenedor"""
    
    def __init__(self, cache_dir=None):
        if cache_dir is None:
            # Crear carpeta temporal en el sistema
            import tempfile
            self.cache_dir = os.path.join(tempfile.gettempdir(), "PS2_ISO_Explorer_Cache")
        else:
            self.cache_dir = cache_dir
        
        self.metadata_dir = os.path.join(self.cache_dir, "metadata")
        self.data_dir = os.path.join(self.cache_dir, "data")
        self.lock = threading.Lock()
        
        # Crear directorios si no existen
        os.makedirs(self.metadata_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.cache_info = {}
        self._load_cache_info()
    
    def _get_cache_key(self, iso_path, container_path, container_type):
        """Generar clave única para el caché"""
        # Combinar ISO + ruta del contenedor + tipo
        key_str = f"{iso_path}|{container_path}|{container_type}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _load_cache_info(self):
        """Cargar información del caché"""
        info_path = os.path.join(self.cache_dir, "cache_info.json")
        if os.path.exists(info_path):
            try:
                with open(info_path, 'r', encoding='utf-8') as f:
                    self.cache_info = json.load(f)
            except:
                self.cache_info = {}
    
    def _save_cache_info(self):
        """Guardar información del caché"""
        info_path = os.path.join(self.cache_dir, "cache_info.json")
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(self.cache_info, f, indent=2)
    
    def get_cached_container(self, iso_path, container_path, container_type):
        """Obtener contenedor del caché si existe"""
        cache_key = self._get_cache_key(iso_path, container_path, container_type)
        
        if cache_key in self.cache_info:
            cache_entry = self.cache_info[cache_key]
            data_path = os.path.join(self.data_dir, f"{cache_key}.dat")
            metadata_path = os.path.join(self.metadata_dir, f"{cache_key}.pkl")
            
            # Verificar que los archivos existen
            if os.path.exists(data_path) and os.path.exists(metadata_path):
                # Verificar fecha de modificación del ISO
                iso_mtime = os.path.getmtime(iso_path)
                if cache_entry.get('iso_mtime', 0) == iso_mtime:
                    # Cargar metadatos
                    with open(metadata_path, 'rb') as f:
                        metadata = pickle.load(f)
                    
                    # Cargar datos
                    with open(data_path, 'rb') as f:
                        data = f.read()
                    
                    print(f"✅ Contenedor cargado desde caché: {container_path}")
                    return data, metadata
            
            # Si los archivos no existen o están corruptos, eliminar entrada
            del self.cache_info[cache_key]
            self._save_cache_info()
        
        return None, None
    
    def save_to_cache(self, iso_path, container_path, container_type, data, metadata):
        """Guardar contenedor en caché"""
        cache_key = self._get_cache_key(iso_path, container_path, container_type)
        
        with self.lock:
            # Guardar datos
            data_path = os.path.join(self.data_dir, f"{cache_key}.dat")
            with open(data_path, 'wb') as f:
                f.write(data)
            
            # Guardar metadatos
            metadata_path = os.path.join(self.metadata_dir, f"{cache_key}.pkl")
            with open(metadata_path, 'wb') as f:
                pickle.dump(metadata, f)
            
            # Guardar información
            self.cache_info[cache_key] = {
                'iso_path': iso_path,
                'container_path': container_path,
                'container_type': container_type,
                'iso_mtime': os.path.getmtime(iso_path),
                'cached_date': datetime.now().isoformat(),
                'size': len(data)
            }
            
            self._save_cache_info()
            print(f"✅ Contenedor guardado en caché: {container_path}")
    
    def clear_cache(self, older_than_days=None):
        """Limpiar caché"""
        with self.lock:
            if older_than_days:
                # Eliminar archivos más antiguos que X días
                import time
                current_time = time.time()
                threshold = older_than_days * 24 * 3600
                
                to_delete = []
                for key, info in self.cache_info.items():
                    cached_time = datetime.fromisoformat(info['cached_date']).timestamp()
                    if current_time - cached_time > threshold:
                        to_delete.append(key)
                
                for key in to_delete:
                    self._delete_cache_entry(key)
            else:
                # Eliminar todo
                for key in list(self.cache_info.keys()):
                    self._delete_cache_entry(key)
    
    def _delete_cache_entry(self, key):
        """Eliminar una entrada del caché"""
        data_path = os.path.join(self.data_dir, f"{key}.dat")
        metadata_path = os.path.join(self.metadata_dir, f"{key}.pkl")
        
        if os.path.exists(data_path):
            os.remove(data_path)
        if os.path.exists(metadata_path):
            os.remove(metadata_path)
        
        if key in self.cache_info:
            del self.cache_info[key]
        
        self._save_cache_info()
    
    def get_cache_size(self):
        """Obtener tamaño total del caché en bytes"""
        total_size = 0
        for key in self.cache_info:
            data_path = os.path.join(self.data_dir, f"{key}.dat")
            if os.path.exists(data_path):
                total_size += os.path.getsize(data_path)
        return total_size
    
    def get_cache_info(self):
        """Obtener información del caché"""
        return {
            'entries': len(self.cache_info),
            'size': self.get_cache_size(),
            'size_mb': self.get_cache_size() / (1024 * 1024)
        }
