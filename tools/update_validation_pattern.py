#!/usr/bin/env python
"""
Utilidad para actualizar el patrón de validación de un servicio específico.
Uso: python update_validation_pattern.py <nombre_servicio>
"""

import os
import sys
import json
import logging
from datetime import datetime

# Configurar directorio raíz
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# Importar módulos de la aplicación
from core.persistence import PersistenceManager

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('update_pattern')

def update_validation_pattern(service_name, new_pattern=None):
    """
    Actualiza el patrón de validación para un servicio específico.
    
    Args:
        service_name (str): Nombre del servicio
        new_pattern (dict): Nuevo patrón de validación
        
    Returns:
        bool: True si se actualizó correctamente
    """
    try:
        # Inicializar gestor de persistencia con ruta absoluta
        persistence = PersistenceManager(base_path=os.path.join(project_root, 'data'))
        
        # Eliminar la extensión .json si fue incluida
        if service_name.endswith('.json'):
            service_name = service_name[:-5]
            
        logger.info(f"Buscando servicio: {service_name}")
        
        # Cargar datos actuales del servicio
        try:
            service_data = persistence.load_soap_request(service_name)
        except ValueError:
            # Intentar también con variantes del nombre
            alternatives = [
                service_name.lower(),
                service_name.lower().replace(' ', '_'),
                service_name.upper(),
                service_name.capitalize()
            ]
            
            service_data = None
            for alt_name in alternatives:
                try:
                    logger.info(f"Intentando alternativa: {alt_name}")
                    service_data = persistence.load_soap_request(alt_name)
                    if service_data:
                        service_name = alt_name
                        break
                except:
                    continue
            
            if not service_data:
                logger.error(f"Servicio '{service_name}' no encontrado después de probar alternativas")
                return False
        
        # Guardar los datos originales como respaldo
        backup_dir = os.path.join(project_root, 'backup')
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_file = os.path.join(backup_dir, f"{service_name}_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(service_data, f, indent=2)
        logger.info(f"Backup guardado en {backup_file}")
        
        # Si no se proporciona un nuevo patrón, usar un patrón estándar según el tipo
        if new_pattern is None:
            service_type = service_data.get('type', 'SOAP')
            
            if service_type == 'SOAP':
                new_pattern = {
                    "success_field": "codMensaje",
                    "success_values": ["00000", "0", "OK"],
                    "warning_values": ["2001", "2002", "WARN"],
                    "failed_values": ["5000", "9999", "ERROR"],
                    "validation_strategy": "flexible",
                    "alternative_paths": [
                        {
                            "field": "estadoRespuesta",
                            "success_values": ["OK", "SUCCESS"]
                        }
                    ],
                    "expected_fields": {
                        "resultado": None
                    }
                }
            else:  # REST
                new_pattern = {
                    "success_field": "status",
                    "success_values": ["success", "OK", "200"],
                    "warning_values": ["PENDING", "IN_PROGRESS", "WARNING"],
                    "failed_values": ["ERROR", "FAILED", "INVALID"],
                    "validation_strategy": "flexible",
                    "alternative_paths": [
                        {
                            "field": "code",
                            "success_values": ["200", "201", "OK"]
                        }
                    ],
                    "expected_fields": {
                        "data": None
                    }
                }
            
            logger.info(f"Usando patrón estándar para tipo {service_type}")
            
        # Actualizar el patrón de validación
        service_data['validation_pattern'] = new_pattern
        
        # Guardar los cambios
        persistence.save_service_request(service_data)
        
        logger.info(f"Patrón de validación actualizado para '{service_name}'")
        return True
    
    except Exception as e:
        logger.error(f"Error al actualizar patrón: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python update_validation_pattern.py <nombre_servicio>")
        sys.exit(1)
    
    service_name = sys.argv[1]
    
    # Permitir especificar un patrón personalizado a través de un archivo
    custom_pattern = None
    if len(sys.argv) > 2 and os.path.exists(sys.argv[2]):
        try:
            with open(sys.argv[2], 'r', encoding='utf-8') as f:
                custom_pattern = json.load(f)
            print(f"Usando patrón personalizado desde archivo: {sys.argv[2]}")
        except Exception as e:
            print(f"Error al cargar patrón desde archivo: {str(e)}")
            sys.exit(1)
    
    if update_validation_pattern(service_name, custom_pattern):
        print(f"Patrón de validación actualizado correctamente para '{service_name}'")
    else:
        print(f"Error al actualizar patrón para '{service_name}'")
        sys.exit(1)