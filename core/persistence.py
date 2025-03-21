# Añadir importación de date al inicio del archivo
import os
import json
import logging
from datetime import datetime, date  # Añadir 'date' aquí
from typing import Dict, List, Any, Optional

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('persistence')

class PersistenceManager:
    """Gestor de persistencia para archivos JSON de la aplicación"""
    
    def __init__(self, base_path: str = './data'):
        """
        Inicializa el gestor de persistencia.
        
        Args:
            base_path (str): Ruta base para almacenar los archivos
        """
        self.base_path = base_path
        self.requests_path = os.path.join(base_path, 'requests')
        self.email_config_path = os.path.join(base_path, 'email_config.json')
        
        # Crear directorios si no existen
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Crea los directorios necesarios si no existen"""
        os.makedirs(self.requests_path, exist_ok=True)
        
        # Crear archivo de configuración de emails si no existe
        if not os.path.exists(self.email_config_path):
            self.save_email_config({'recipients': []})
    
    def save_soap_request(self, request_data: Dict[str, Any]) -> str:
        """
        Guarda un SOAP request en un archivo JSON con preservación mejorada de campos.
        
        Args:
            request_data (Dict[str, Any]): Datos del request a guardar
            
        Returns:
            str: Ruta del archivo guardado
        """
        # Validar datos mínimos requeridos
        required_fields = ['name', 'description', 'wsdl_url', 'request_xml']
        for field in required_fields:
            if field not in request_data:
                raise ValueError(f"Campo requerido faltante: {field}")
        
        # Sanear el nombre para usarlo como nombre de archivo
        safe_name = request_data['name'].lower().replace(' ', '_')
        file_path = os.path.join(self.requests_path, f"{safe_name}.json")
        
        # Log para diagnóstico detallado
        logger.info(f"Guardando request en: {file_path}")
        logger.info(f"Existe directorio: {os.path.exists(self.requests_path)}")
        
        # MEJORA: Cargar datos existentes si ya existe el archivo
        existing_data = {}
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                logger.info(f"Archivo existente cargado correctamente: {file_path}")
            except Exception as e:
                logger.warning(f"No se pudo cargar archivo existente: {str(e)}")
        
        # Preservar campos importantes del registro existente
        for key in ['created_at', 'last_checked', 'last_response']:
            if key in existing_data and key not in request_data:
                request_data[key] = existing_data[key]
        
        # Agregar metadatos
        if 'created_at' not in request_data:
            request_data['created_at'] = datetime.now().isoformat()
        request_data['updated_at'] = datetime.now().isoformat()
        if 'status' not in request_data:
            request_data['status'] = 'active'
        
        # Función serializadora correcta
        def json_serializer(obj):
            """Serializador seguro para objetos JSON con manejo de fechas"""
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            return str(obj)
        
        # Guardar en archivo con manejo robusto de errores
        try:
            # Primero escribir a un archivo temporal
            temp_file_path = f"{file_path}.tmp"
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                json.dump(request_data, f, indent=2, ensure_ascii=False, default=json_serializer)
            
            # Si el archivo temporal se escribió correctamente, reemplazar el original
            if os.path.exists(file_path):
                # Crear copia de seguridad primero
                backup_path = f"{file_path}.bak"
                try:
                    import shutil
                    shutil.copy2(file_path, backup_path)
                except Exception as e:
                    logger.warning(f"No se pudo crear backup: {str(e)}")
            
            # Reemplazar archivo original con el temporal
            os.replace(temp_file_path, file_path)
            
            # Verificación de integridad - confirmar que el archivo existe
            if os.path.exists(file_path):
                logger.info(f"SOAP request guardado exitosamente: {file_path}")
            else:
                logger.error(f"ERROR CRÍTICO: Archivo no encontrado después de guardar: {file_path}")
            
            return file_path
        except Exception as e:
            logger.error(f"Error al guardar SOAP request: {str(e)}", exc_info=True)
            
            # Intento de recuperación desde archivo temporal o backup
            if os.path.exists(f"{file_path}.tmp"):
                try:
                    os.rename(f"{file_path}.tmp", file_path)
                    logger.info(f"Recuperación desde archivo temporal exitosa")
                except Exception:
                    pass
            
            raise
    
    def load_soap_request(self, request_name: str) -> Dict[str, Any]:
        """
        Carga un SOAP request desde un archivo JSON.
        
        Args:
            request_name (str): Nombre del request a cargar
            
        Returns:
            Dict[str, Any]: Datos del request
        """
        safe_name = request_name.lower().replace(' ', '_')
        file_path = os.path.join(self.requests_path, f"{safe_name}.json")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Request no encontrado: {request_name}")
            raise ValueError(f"Request no encontrado: {request_name}")
        except json.JSONDecodeError:
            logger.error(f"Error de formato en el archivo: {file_path}")
            raise ValueError(f"Error de formato en el archivo: {file_path}")
    
    def list_all_requests(self) -> List[Dict[str, Any]]:
        """
        Lista todos los SOAP requests disponibles con validación mejorada.
        
        Returns:
            List[Dict[str, Any]]: Lista de requests
        """
        requests = []
        
        if not os.path.exists(self.requests_path):
            logger.warning(f"Directorio de requests no encontrado: {self.requests_path}")
            return requests
        
        logger.info(f"Buscando requests en {self.requests_path}")
        
        # Contar archivos para diagnóstico
        all_files = os.listdir(self.requests_path)
        json_files = [f for f in all_files if f.endswith('.json')]
        logger.info(f"Total de archivos: {len(all_files)}, Archivos JSON: {len(json_files)}")
        
        for filename in json_files:
            file_path = os.path.join(self.requests_path, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    request_data = json.load(f)
                    
                # Validar datos mínimos
                if 'name' not in request_data or not request_data['name']:
                    logger.warning(f"Archivo {filename} sin nombre válido, agregando nombre desde archivo")
                    # Extraer nombre del archivo como fallback
                    base_name = os.path.splitext(filename)[0]
                    request_data['name'] = base_name.replace('_', ' ').title()
                
                # Asegurar campos mínimos
                for field in ['description', 'wsdl_url', 'request_xml']:
                    if field not in request_data:
                        request_data[field] = ""
                        
                if 'status' not in request_data:
                    request_data['status'] = 'sin verificar'
                        
                # Añadir a la lista
                requests.append(request_data)
                logger.debug(f"Request cargado: {request_data['name']}")
            except json.JSONDecodeError:
                logger.error(f"Error de formato JSON en {file_path}")
            except Exception as e:
                logger.error(f"Error al cargar {filename}: {str(e)}")
        
        # Verificación final
        logger.info(f"Requests encontrados: {len(requests)}")
        return requests
    
    # En persistence.py, localizar el método update_request_status
    def update_request_status(self, request_name: str, status: str, 
                         response_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Actualiza el estado de un request después de su verificación con preservación de datos.
        
        Args:
            request_name (str): Nombre del request
            status (str): Nuevo estado ('ok', 'failed', 'error', 'invalid')
            response_data (Dict[str, Any], optional): Datos de la respuesta
        """
        try:
            # Asegurar que usamos la ruta de archivo correcta
            safe_name = request_name.lower().replace(' ', '_')
            file_path = os.path.join(self.requests_path, f"{safe_name}.json")
            
            # Logging detallado para diagnóstico
            logger.info(f"Actualizando estado para: {request_name} -> {status}")
            logger.info(f"Archivo: {file_path}")
            logger.info(f"Existe archivo: {os.path.exists(file_path)}")
            
            # VERIFICACIÓN: Comprobar existencia del archivo
            if not os.path.exists(file_path):
                logger.error(f"Archivo no encontrado para actualizar estado: {file_path}")
                return
            
            # Cargar datos existentes con manejo de errores
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    request_data = json.load(f)
                    logger.debug(f"Datos originales cargados: {list(request_data.keys())}")
            except json.JSONDecodeError as je:
                logger.error(f"Error de formato JSON en {file_path}: {str(je)}")
                return
            except Exception as e:
                logger.error(f"Error al leer archivo {file_path}: {str(e)}")
                return
                
            # CRÍTICO: Preservar todos los campos originales
            original_data = request_data.copy()
            
            # Actualizar solo los campos de estado
            request_data['status'] = status
            request_data['last_checked'] = datetime.now().isoformat()
            request_data['updated_at'] = datetime.now().isoformat()
            
            # Almacenar datos de respuesta si se proporcionan
            if response_data is not None:
                request_data['last_response'] = response_data
                
            # RESTAURACIÓN: Asegurar que los campos críticos se mantengan
            critical_fields = [
                'name', 'description', 'wsdl_url', 'request_xml', 
                'validation_pattern', 'monitor_interval', 'monitor_enabled', 
                'add_to_system', 'created_at'
            ]
            
            for field in critical_fields:
                if field in original_data and field not in request_data:
                    request_data[field] = original_data[field]
                    logger.debug(f"Restaurado campo: {field}")
            
            # VERIFICACIÓN FINAL: Comprobar integridad antes de guardar
            if 'name' not in request_data or request_data['name'] != request_name:
                logger.warning(f"Inconsistencia detectada: nombre original '{request_name}' no coincide con datos")
                request_data['name'] = request_name  # Forzar consistencia
            
            # Guardar cambios con manejo seguro de errores y serialización de fechas correcta
            try:
                # Definir serializador para fechas
                def date_serializer(obj):
                    if isinstance(obj, (datetime, date)):
                        return obj.isoformat()
                    return str(obj)
                
                # Usar archivo temporal para escritura segura
                temp_file = f"{file_path}.tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(request_data, f, indent=2, ensure_ascii=False, default=date_serializer)
                
                # Si la escritura temporal fue exitosa, reemplazar el archivo original
                os.replace(temp_file, file_path)
                    
                logger.info(f"Estado actualizado correctamente para {request_name}: {status}")
                
                # Verificación final - confirmar que el archivo existe
                if os.path.exists(file_path):
                    logger.info(f"✅ Verificación final: Archivo preservado tras actualización: {file_path}")
                else:
                    logger.error(f"❌ ERROR CRÍTICO: Archivo desapareció tras actualización: {file_path}")
                    
            except Exception as write_error:
                logger.error(f"Error al escribir archivo {file_path}: {str(write_error)}")
                    
        except Exception as e:
            logger.error(f"Error general al actualizar estado de {request_name}: {str(e)}", exc_info=True)
            
    def _backup_corrupted_file(self, file_path: str) -> None:
        """
        Crea una copia de seguridad de un archivo corrupto para diagnóstico.
        
        Args:
            file_path (str): Ruta al archivo corrupto
        """
        try:
            import shutil
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            backup_path = f"{file_path}.corrupted.{timestamp}"
            shutil.copy2(file_path, backup_path)
            logger.info(f"Copia de seguridad de archivo corrupto creada: {backup_path}")
        except Exception as e:
            logger.error(f"Error al crear copia de seguridad: {str(e)}")
    
    def save_email_config(self, config: Dict[str, Any]) -> None:
        """
        Guarda la configuración de emails.
        
        Args:
            config (Dict[str, Any]): Configuración de emails
        """
        try:
            with open(self.email_config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info("Configuración de emails guardada")
        except Exception as e:
            logger.error(f"Error al guardar configuración de emails: {str(e)}")
            raise
    
    def load_email_config(self) -> Dict[str, Any]:
        """
        Carga la configuración de emails.
        
        Returns:
            Dict[str, Any]: Configuración de emails
        """
        try:
            with open(self.email_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("Archivo de configuración de emails no encontrado, creando uno nuevo")
            default_config = {'recipients': []}
            self.save_email_config(default_config)
            return default_config
        except json.JSONDecodeError:
            logger.error(f"Error de formato en el archivo de configuración de emails")
            raise ValueError(f"Error de formato en el archivo de configuración de emails")
        
    # Añadir al final del archivo persistence.py

    def verify_file_integrity(self, file_path: str) -> bool:
        """
        Verifica la integridad de un archivo JSON.
        
        Args:
            file_path (str): Ruta al archivo
            
        Returns:
            bool: True si el archivo es válido y contiene campos críticos
        """
        if not os.path.exists(file_path):
            logger.error(f"Archivo no encontrado: {file_path}")
            return False
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Verificar campos críticos
            required_fields = ['name', 'wsdl_url', 'request_xml']
            for field in required_fields:
                if field not in data:
                    logger.error(f"Campo crítico faltante en {file_path}: {field}")
                    return False
                    
            return True
        except json.JSONDecodeError:
            logger.error(f"Archivo corrupto: {file_path}")
            return False
        except Exception as e:
            logger.error(f"Error al verificar archivo {file_path}: {str(e)}")
            return False

    def repair_requests_directory(self) -> Dict[str, Any]:
        """
        Escanea y repara archivos corruptos en el directorio de requests.
        
        Returns:
            Dict[str, Any]: Informe de reparación
        """
        report = {
            "scanned": 0,
            "valid": 0,
            "repaired": 0,
            "corrupted": 0,
            "details": []
        }
        
        if not os.path.exists(self.requests_path):
            logger.error(f"Directorio de requests no existe: {self.requests_path}")
            return report
            
        # Escanear directorio
        for filename in os.listdir(self.requests_path):
            if not filename.endswith('.json'):
                continue
                
            file_path = os.path.join(self.requests_path, filename)
            report["scanned"] += 1
            
            # Verificar integridad
            if self.verify_file_integrity(file_path):
                report["valid"] += 1
                report["details"].append({"file": filename, "status": "valid"})
                continue
                
            # Intentar reparar desde backup
            backup_path = f"{file_path}.bak"
            if os.path.exists(backup_path) and self.verify_file_integrity(backup_path):
                import shutil
                try:
                    shutil.copy2(backup_path, file_path)
                    report["repaired"] += 1
                    report["details"].append({"file": filename, "status": "repaired", "source": "backup"})
                    continue
                except Exception as e:
                    logger.error(f"Error al restaurar backup: {str(e)}")
                    
            # Marcar como corrupto
            report["corrupted"] += 1
            report["details"].append({"file": filename, "status": "corrupted"})
            
        return report