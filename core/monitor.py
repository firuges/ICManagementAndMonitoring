#!/usr/bin/env python
"""
Script de monitoreo para SOAP Monitor.
Este script se ejecuta como tarea programada para verificar los servicios SOAP.

Uso: python monitor.py [nombre_request]

Si se especifica un nombre de request, solo se verifica ese request.
Si no se especifica, se verifican todos los requests activos.
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional

# Configurar directorio raíz
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Importar módulos de la aplicación
from core.persistence import PersistenceManager
from core.soap_client import SOAPClient
from core.notification import EmailNotifier

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=os.path.join(current_dir, 'logs', 'monitor.log'),
    filemode='a'
)
logger = logging.getLogger('monitor')

def check_request(persistence: PersistenceManager, soap_client: SOAPClient, 
                 request_name: str) -> Dict[str, Any]:
    """
    Verifica un request SOAP.
    
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
        
        # Extraer datos necesarios
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
        
        # Enviar request
        success, result = soap_client.send_raw_request(wsdl_url, request_xml)
        
        if not success:
            # Guardar resultado de error
            persistence.update_request_status(request_name, 'failed', result)
            
            return {
                'request_name': request_name,
                'status': 'failed',
                'error': result.get('error', 'Error desconocido'),
                'timestamp': datetime.now().isoformat()
            }
        
        # Extraer patrones de validación
        validation_patterns = soap_client.extract_validation_patterns(request_data)
        
        # Validar la respuesta si hay patrones definidos
        if validation_patterns:
            valid, validation_msg = soap_client.validate_response(result['response'], validation_patterns)
            
            if not valid:
                # La respuesta no cumple con los patrones esperados
                persistence.update_request_status(request_name, 'invalid', {
                    'response': result['response'],
                    'validation_error': validation_msg
                })
                
                return {
                    'request_name': request_name,
                    'status': 'invalid',
                    'error': f"Error de validación: {validation_msg}",
                    'timestamp': datetime.now().isoformat()
                }
        
        # Todo está bien, actualizar estado
        persistence.update_request_status(request_name, 'ok', {
            'response': result['response']
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
    # Crear directorio de logs si no existe
    logs_dir = os.path.join(current_dir, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Configurar argumentos
    parser = argparse.ArgumentParser(description='Monitor de servicios SOAP')
    parser.add_argument('request_name', nargs='?', help='Nombre del request a verificar')
    args = parser.parse_args()
    
    # Inicializar componentes
    persistence = PersistenceManager()
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

if __name__ == "__main__":
    main()