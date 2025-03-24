#!/usr/bin/env python
"""
Script de monitoreo para SOAP Monitor.
Este script se ejecuta como tarea programada para verificar los servicios SOAP.

Uso: python core/monitor.py [nombre_request]

Si se especifica un nombre de request, solo se verifica ese request.
Si no se especifica, se verifican todos los requests activos.
"""

import os
import sys
import json
import logging
import tempfile
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional

# Obtener la ruta del directorio core
core_dir = os.path.dirname(os.path.abspath(__file__))
# Obtener el directorio raíz del proyecto (un nivel arriba)
project_root = os.path.dirname(core_dir)
# Añadir directorio raíz al sys.path
sys.path.append(project_root)

# Ahora podemos importar sin el prefijo 'core.'
from persistence import PersistenceManager
from soap_client import SOAPClient
from notification import EmailNotifier
from rest_client import RESTClient

# Configuración de logging
logs_dir = os.path.join(project_root, 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Usar el archivo de log en la ubicación correcta
log_file = os.path.join(logs_dir, 'soap_monitor.log')

# Añadir un handler para consola además del archivo
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # Esto mostrará logs en la consola
    ]
)

logger = logging.getLogger('monitor')
logger.info("=== Script de monitoreo iniciado ===")

def check_request(persistence: PersistenceManager, soap_client: SOAPClient, 
                 request_name: str) -> Dict[str, Any]:
    """
    Verifica un request SOAP o REST.
    
    Args:
        persistence (PersistenceManager): Gestor de persistencia
        soap_client (SOAPClient): Cliente SOAP
        request_name (str): Nombre del request a verificar
        
    Returns:
        Dict[str, Any]: Resultado de la verificación
    """
    logger.info(f"Verificando request: {request_name}")
    
    try:
        # Cargar datos del request
        request_data = persistence.load_soap_request(request_name)
        
        # Determinar tipo de servicio
        service_type = request_data.get('type', 'SOAP')
        logger.info(f"Tipo de servicio: {service_type}")
        
        # Procesar según tipo de servicio
        if service_type == 'SOAP':
            # Extraer datos necesarios para SOAP
            wsdl_url = request_data.get('wsdl_url')
            request_xml = request_data.get('request_xml')
            
            if not wsdl_url or not request_xml:
                error_msg = "WSDL URL o XML del request no encontrados"
                logger.error(f"{error_msg} para {request_name}")
                return {
                    'request_name': request_name,
                    'status': 'error',
                    'error': error_msg,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Enviar request SOAP con timeout y reintentos configurados
            success, result = soap_client.send_raw_request(
                wsdl_url, 
                request_xml,
                timeout=timeout,
                max_retries=max_retries
            )
            
        else:  # REST
            # Importar cliente REST si es necesario
            # Si no tienes módulo rest_client, deberás implementarlo o importarlo
            try:
                from rest_client import RESTClient
                rest_client = RESTClient()
            except ImportError:
                logger.error("Módulo REST no disponible. Imposible verificar servicio REST.")
                return {
                    'request_name': request_name,
                    'status': 'error',
                    'error': "Módulo REST no disponible",
                    'timestamp': datetime.now().isoformat()
                }
            
            # Extraer datos necesarios para REST
            url = request_data.get('url')
            method = request_data.get('method', 'GET')
            headers = request_data.get('headers', {})
            params = request_data.get('params', {})
            json_data = request_data.get('json_data')
            
            if not url:
                error_msg = "URL del servicio REST no encontrada"
                logger.error(f"{error_msg} para {request_name}")
                return {
                    'request_name': request_name,
                    'status': 'error',
                    'error': error_msg,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Enviar request REST
            logger.info(f"Enviando request REST {method} a {url}")
            success, result = rest_client.send_request(
                url=url,
                method=method,
                headers=headers,
                params=params,
                json_data=json_data,
                timeout=request_data.get('request_timeout', 30),
                max_retries=request_data.get('max_retries', 1)
            )
        
        # El resto del código es igual para ambos tipos
        if not success:
            # Guardar resultado de error
            persistence.update_request_status(request_name, 'failed', result)
            
            return {
                'request_name': request_name,
                'status': 'failed',
                'error': result.get('error', 'Error desconocido'),
                'timestamp': datetime.now().isoformat()
            }
        
        # Extraer esquema de validación avanzado
        validation_schema = request_data.get('validation_pattern', {})
        
        # Convertir strings JSON a diccionarios si es necesario
        if isinstance(validation_schema, str) and validation_schema.strip():
            try:
                validation_schema = json.loads(validation_schema)
            except json.JSONDecodeError:
                logger.warning(f"Esquema de validación inválido para {request_name}, tratando como texto plano")
        
        # Usar validación avanzada
        valid, message, level = soap_client.validate_response_advanced(
            result.get('response', {}), validation_schema
        )
        
        if not valid:
            if level == "failed":
                # La respuesta es un fallo conocido
                persistence.update_request_status(request_name, 'failed', {
                    'response': result.get('response', {}),
                    'validation_message': message
                })
                
                return {
                    'request_name': request_name,
                    'status': 'failed',
                    'error': f"Fallo de validación: {message}",
                    'timestamp': datetime.now().isoformat()
                }
            else:
                # La respuesta no cumple con los patrones esperados
                persistence.update_request_status(request_name, 'invalid', {
                    'response': result.get('response', {}),
                    'validation_error': message
                })
                
                return {
                    'request_name': request_name,
                    'status': 'invalid',
                    'error': f"Error de validación: {message}",
                    'timestamp': datetime.now().isoformat()
                }
        elif level == "warning":
            # Validación exitosa pero con advertencias
            persistence.update_request_status(request_name, 'warning', {
                'response': result.get('response', {}),
                'validation_message': message
            })
            
            return {
                'request_name': request_name,
                'status': 'warning',
                'message': message,
                'timestamp': datetime.now().isoformat()
            }
        else:
            # Todo está bien, actualizar estado
            persistence.update_request_status(request_name, 'ok', {
                'response': result.get('response', {})
            })
            
            return {
                'request_name': request_name,
                'status': 'ok',
                'timestamp': datetime.now().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Error al verificar request {request_name}: {str(e)}")
        
        # Actualizar estado de error
        persistence.update_request_status(request_name, 'error', {
            'error': str(e)
        })
        
        return {
            'request_name': request_name,
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

def notify_failures(notifier: EmailNotifier, persistence: PersistenceManager, 
                   failed_requests: List[Dict[str, Any]]) -> None:
    """
    Notifica los fallos por correo electrónico.
    
    Args:
        notifier (EmailNotifier): Notificador por email
        persistence (PersistenceManager): Gestor de persistencia
        failed_requests (List[Dict[str, Any]]): Lista de requests fallidos
    """
    if not failed_requests:
        return
    
    try:
        # Cargar configuración de emails
        email_config = persistence.load_email_config()
        recipients = email_config.get('recipients', [])
        
        if not recipients:
            logger.warning("No hay destinatarios configurados para notificaciones")
            return
        
        # Notificar cada fallo
        for failure in failed_requests:
            notifier.send_service_failure_notification(
                recipients, 
                failure['request_name'], 
                failure
            )
            logger.info(f"Notificación enviada para {failure['request_name']}")
            
    except Exception as e:
        logger.error(f"Error al notificar fallos: {str(e)}")

def main():
    """Función principal"""
    global logs_dir
    logger.info(f"Directorio actual: {os.getcwd()}")
    logger.info(f"Directorio raíz del proyecto: {project_root}")
    logger.info(f"Python path: {sys.executable}")
    logger.info(f"Argumentos: {sys.argv}")
    
    # Verificar acceso a directorios clave
    data_dir = os.path.join(project_root, 'data')
    logger.info(f"Directorio data existe: {os.path.exists(data_dir)}")
    logger.info(f"Directorio logs existe: {os.path.exists(logs_dir)}")
    # Crear directorio de logs si no existe
    logs_dir = os.path.join(project_root, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Configurar argumentos
    parser = argparse.ArgumentParser(description='Monitor de servicios SOAP')
    parser.add_argument('request_name', nargs='?', help='Nombre del request a verificar')
    args = parser.parse_args()
    
    # Inicializar componentes
    data_path = os.path.join(project_root, 'data')
    persistence = PersistenceManager(base_path=data_path)
    soap_client = SOAPClient()
    notifier = EmailNotifier()
    
    # Cargar configuración de notificaciones
    # TODO: Cargar configuración SMTP desde archivo
    
    # Lista para almacenar fallos
    failed_requests = []
    
    # Verificar un request específico o todos
    if args.request_name:
        # Verificar un solo request
        result = check_request(persistence, soap_client, args.request_name)
        
        if result['status'] != 'ok':
            failed_requests.append(result)
    else:
        # Verificar todos los requests
        requests = persistence.list_all_requests()
        
        for request_data in requests:
            # Solo verificar requests activos
            if request_data.get('status') == 'active':
                result = check_request(persistence, soap_client, request_data['name'])
                
                if result['status'] != 'ok':
                    failed_requests.append(result)
    
    # Notificar fallos
    if failed_requests:
        notify_failures(notifier, persistence, failed_requests)
        logger.info(f"Notificados {len(failed_requests)} fallos")
    else:
        logger.info("Todos los servicios funcionan correctamente")

    if len(sys.argv) > 1 and '--wait' in sys.argv:
        print("\nPresiona Enter para cerrar...")
        input()
        
if __name__ == "__main__":
    main()