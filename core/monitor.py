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

try:
    from core.persistence import PersistenceManager
    from core.soap_client import SOAPClient
    from core.notification import EmailNotifier
    from core.rest_client import RESTClient
except ImportError:
    try:
        # Si no se puede importar desde el paquete, intentar desde el directorio actual
        from persistence import PersistenceManager
        from soap_client import SOAPClient
        from notification import EmailNotifier
        from rest_client import RESTClient
    except ImportError:
        # Último intento: importar desde el directorio padre
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from core.persistence import PersistenceManager
        from core.soap_client import SOAPClient
        from core.notification import EmailNotifier
        from core.rest_client import RESTClient
        
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
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('monitor')
logger.info("=== Script de monitoreo iniciado ===")


def setup_environment():
    """Configura el entorno para garantizar que las importaciones funcionen correctamente"""
    try:
        # Determinar si estamos en un entorno compilado
        is_frozen = getattr(sys, 'frozen', False)
        
        if is_frozen:
            # Estamos en un entorno compilado (exe)
            application_path = os.path.dirname(sys.executable)
            logger.info(f"Ejecutando como aplicación compilada: {application_path}")
            sys.path.insert(0, application_path)
        else:
            # Estamos ejecutando como script
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            logger.info(f"Ejecutando como script Python: {current_dir}")
            logger.info(f"Directorio raíz del proyecto: {project_root}")
            
            # Añadir directorio raíz al path
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            # Añadir directorio core al path si es necesario
            core_dir = os.path.join(project_root, 'core')
            if os.path.exists(core_dir) and core_dir not in sys.path:
                sys.path.insert(0, core_dir)
        
        # Verificar paths para diagnóstico
        logger.info(f"Python path: {sys.path}")
        return True
    except Exception as e:
        logger.error(f"Error al configurar entorno: {str(e)}")
        return False

# Llamar a esta función al inicio
setup_result = setup_environment()
if not setup_result:
    logger.error("No se pudo configurar el entorno correctamente")
    
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
        
        # Inicializamos result aquí para evitar el error de referencia
        result = None
        success = False
        
        # Procesar según tipo de servicio
        if service_type == 'SOAP':
            # Extraer datos necesarios para SOAP
            wsdl_url = request_data.get('wsdl_url')
            request_xml = request_data.get('request_xml')
            
            if not wsdl_url or not request_xml:
                error_msg = "WSDL URL o XML del request no encontrados"
                logger.error(f"{error_msg} para {request_name}")
                
                # Preparar detalles del error para notificación
                error_details = {
                    'error': error_msg,
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'type': 'SOAP',
                    'request_xml': request_xml  # Incluir el XML aunque esté incompleto
                }
                
                persistence.update_request_status(request_name, 'error', error_details)
                
                return {
                    'request_name': request_name,
                    'status': 'error',
                    'error': error_msg,
                    'timestamp': datetime.now().isoformat(),
                    'error_details': error_details
                }
            
            # Verificar timeouts y reintentos configurados
            timeout = request_data.get('request_timeout', 30)  # Default: 30 segundos
            max_retries = request_data.get('max_retries', 1)   # Default: 1 reintento
            
            # Enviar request SOAP con timeout y reintentos configurados
            success, result = soap_client.send_raw_request(
                wsdl_url, 
                request_xml,
                timeout=timeout,
                max_retries=max_retries
            )
            
        else:  # REST
            # Importar cliente REST si es necesario
            try:
                from rest_client import RESTClient
                rest_client = RESTClient()
            except ImportError:
                logger.error("Módulo REST no disponible. Imposible verificar servicio REST.")
                
                error_details = {
                    'error': "Módulo REST no disponible",
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'type': 'REST'
                }
                
                persistence.update_request_status(request_name, 'error', error_details)
                
                return {
                    'request_name': request_name,
                    'status': 'error',
                    'error': "Módulo REST no disponible",
                    'timestamp': datetime.now().isoformat(),
                    'error_details': error_details
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
                
                # Preparar detalles para notificación
                error_details = {
                    'error': error_msg,
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'type': 'REST',
                    'url': url,
                    'method': method,
                    'headers': headers,
                    'request_body': json_data
                }
                
                persistence.update_request_status(request_name, 'error', error_details)
                
                return {
                    'request_name': request_name,
                    'status': 'error',
                    'error': error_msg,
                    'timestamp': datetime.now().isoformat(),
                    'error_details': error_details
                }
            
            # Extraer configuración de timeout y reintentos
            timeout = request_data.get('request_timeout', 30)
            max_retries = request_data.get('max_retries', 1)
            
            # Enviar request REST
            logger.info(f"Enviando request REST {method} a {url}")
            success, result = rest_client.send_request(
                url=url,
                method=method,
                headers=headers,
                params=params,
                json_data=json_data,
                timeout=timeout,
                max_retries=max_retries
            )
        
        # El resto del código es igual para ambos tipos
        if not success:
            # Preparar detalles para notificación
            error_details = {
                'error': result.get('error', 'Error desconocido'),
                'status': 'failed',
                'timestamp': datetime.now().isoformat(),
                'type': service_type,
                'group': request_data.get('group', 'General')
            }
            
            # Añadir detalles específicos según tipo de servicio
            if service_type == 'SOAP':
                error_details['request_xml'] = request_xml
                
                # Capturar respuesta XML sin procesar si está disponible
                if 'raw_response_xml' in result:
                    error_details['response_text'] = result['raw_response_xml']
                elif 'response_text' in result:
                    error_details['response_text'] = result['response_text']
                
                # Incluir también respuesta procesada
                if 'response' in result:
                    error_details['response'] = result['response']
            else:  # REST
                # Incluir detalles específicos de REST
                error_details['url'] = url
                error_details['method'] = method
                error_details['headers'] = headers
                error_details['request_body'] = json_data
                
                # Capturar respuesta sin procesar
                if 'response_text' in result:
                    error_details['response_text'] = result['response_text']
                
                # Incluir respuesta procesada y headers
                if 'response' in result:
                    error_details['response'] = result['response']
                if 'headers' in result:
                    error_details['response_headers'] = result['headers']
            
            # Guardar resultado de error
            persistence.update_request_status(request_name, 'failed', error_details)
            
            return {
                'request_name': request_name,
                'status': 'failed',
                'error': result.get('error', 'Error desconocido'),
                'timestamp': datetime.now().isoformat(),
                'error_details': error_details
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
            # Preparar detalles para notificación
            error_details = {
                'status': level,
                'timestamp': datetime.now().isoformat(),
                'type': service_type,
                'group': request_data.get('group', 'General')
            }
            
            # Añadir detalles específicos según nivel y tipo
            if level == "failed":
                error_details['error'] = f"Fallo de validación: {message}"
                
                # Incluir detalles de solicitud y respuesta según tipo
                if service_type == 'SOAP':
                    error_details['request_xml'] = request_xml
                    if 'raw_response_xml' in result:
                        error_details['response_text'] = result['raw_response_xml']
                    error_details['response'] = result.get('response', {})
                else:  # REST
                    error_details['url'] = url
                    error_details['method'] = method
                    error_details['headers'] = headers
                    error_details['request_body'] = json_data
                    error_details['response_text'] = result.get('response_text', '')
                    error_details['response'] = result.get('response', {})
                
                # La respuesta es un fallo conocido
                persistence.update_request_status(request_name, 'failed', error_details)
                
                return {
                    'request_name': request_name,
                    'status': 'failed',
                    'error': f"Fallo de validación: {message}",
                    'timestamp': datetime.now().isoformat(),
                    'error_details': error_details
                }
            else:
                error_details['error'] = f"Error de validación: {message}"
                
                # Incluir detalles de solicitud y respuesta según tipo
                if service_type == 'SOAP':
                    error_details['request_xml'] = request_xml
                    if 'raw_response_xml' in result:
                        error_details['response_text'] = result['raw_response_xml']
                    error_details['response'] = result.get('response', {})
                else:  # REST
                    error_details['url'] = url
                    error_details['method'] = method
                    error_details['headers'] = headers
                    error_details['request_body'] = json_data
                    error_details['response_text'] = result.get('response_text', '')
                    error_details['response'] = result.get('response', {})
                
                # La respuesta no cumple con los patrones esperados
                persistence.update_request_status(request_name, 'invalid', error_details)
                
                return {
                    'request_name': request_name,
                    'status': 'invalid',
                    'error': f"Error de validación: {message}",
                    'timestamp': datetime.now().isoformat(),
                    'error_details': error_details
                }
        elif level == "warning":
            # Preparar detalles para notificación
            warning_details = {
                'status': 'warning',
                'timestamp': datetime.now().isoformat(),
                'type': service_type,
                'group': request_data.get('group', 'General'),
                'validation_message': message
            }
            
            # Incluir detalles de solicitud y respuesta según tipo
            if service_type == 'SOAP':
                warning_details['request_xml'] = request_xml
                if 'raw_response_xml' in result:
                    warning_details['response_text'] = result['raw_response_xml']
                warning_details['response'] = result.get('response', {})
            else:  # REST
                warning_details['url'] = url
                warning_details['method'] = method
                warning_details['headers'] = headers
                warning_details['request_body'] = json_data
                warning_details['response_text'] = result.get('response_text', '')
                warning_details['response'] = result.get('response', {})
            
            # Validación exitosa pero con advertencias
            persistence.update_request_status(request_name, 'warning', warning_details)
            
            return {
                'request_name': request_name,
                'status': 'warning',
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'error_details': warning_details  # Incluir para posibles notificaciones
            }
        else:
            # Éxito - preparar detalles para registro
            success_details = {
                'response': result.get('response', {}),
                'status': 'ok',
                'timestamp': datetime.now().isoformat()
            }
            
            # Incluir respuesta sin procesar para depuración
            if service_type == 'SOAP' and 'raw_response_xml' in result:
                success_details['response_text'] = result['raw_response_xml']
            elif 'response_text' in result:
                success_details['response_text'] = result['response_text']
            
            # Todo está bien, actualizar estado
            persistence.update_request_status(request_name, 'ok', success_details)
            
            return {
                'request_name': request_name,
                'status': 'ok',
                'timestamp': datetime.now().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Error al verificar request {request_name}: {str(e)}", exc_info=True)
        
        # Preparar detalles detallados del error
        error_details = {
            'error': str(e),
            'status': 'error',
            'timestamp': datetime.now().isoformat(),
            'type': request_data.get('type', 'SOAP'),
            'group': request_data.get('group', 'General'),
            'traceback': traceback.format_exc()
        }
        
        # Añadir detalles específicos del servicio
        if request_data.get('type', 'SOAP') == 'SOAP':
            error_details['request_xml'] = request_data.get('request_xml', '')
            error_details['wsdl_url'] = request_data.get('wsdl_url', '')
        else:  # REST
            error_details['url'] = request_data.get('url', '')
            error_details['method'] = request_data.get('method', 'GET')
            error_details['headers'] = request_data.get('headers', {})
            error_details['request_body'] = request_data.get('json_data', None)
        
        # Actualizar estado de error
        persistence.update_request_status(request_name, 'error', error_details)
        
        return {
            'request_name': request_name,
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
            'error_details': error_details
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
        # 1. Cargar configuración SMTP
        smtp_config_path = os.path.join(persistence.base_path, 'smtp_config.json')
        
        if os.path.exists(smtp_config_path):
            try:
                with open(smtp_config_path, 'r', encoding='utf-8') as f:
                    smtp_config = json.load(f)
                
                # Configurar notificador
                notifier.configure(smtp_config)
                logger.info("Configuración SMTP cargada correctamente")
            except Exception as smtp_error:
                logger.error(f"Error al cargar configuración SMTP: {str(smtp_error)}")
                return
        else:
            logger.error("No se encontró archivo de configuración SMTP")
            return
        
        # 2. Cargar política de notificaciones
        notify_config_path = os.path.join(persistence.base_path, 'notification_config.json')
        notify_config = {
            'notify_on_error': True,
            'notify_on_validation': True
        }
        
        if os.path.exists(notify_config_path):
            try:
                with open(notify_config_path, 'r', encoding='utf-8') as f:
                    notify_config = json.load(f)
                logger.info("Configuración de notificaciones cargada correctamente")
            except Exception as e:
                logger.warning(f"Error al cargar configuración de notificaciones: {str(e)}")
                # Usar valores predeterminados
        # Cargar configuración de emails
        email_config = persistence.load_email_config()
        recipients = email_config.get('recipients', [])
        
        if not recipients:
            logger.warning("No hay destinatarios configurados para notificaciones")
            return
        
        # 4. Notificar cada fallo según política configurada
        notifications_sent = 0
        for failure in failed_requests:
            # Determinar tipo de error
            level = "error"
            error_message = failure.get('error', '')
            
            # Clasificar tipo de error
            if 'validation' in failure.get('status', '') or 'validación' in error_message.lower():
                level = "validation"
            
            # Verificar política
            should_notify = False
            if level == "error" and notify_config.get('notify_on_error', True):
                should_notify = True
            elif level == "validation" and notify_config.get('notify_on_validation', True):
                should_notify = True
            
            if should_notify:
                # Obtener detalles completos para la notificación si están disponibles
                error_details = failure.get('error_details', {})
                
                if not error_details:
                    # Si no hay detalles específicos, crear un conjunto básico
                    error_details = {
                        'error': failure.get('error', 'Error desconocido'),
                        'status': failure.get('status', 'unknown'),
                        'timestamp': failure.get('timestamp', datetime.now().isoformat()),
                        'type': failure.get('type', 'SOAP')
                    }
                    
                    # Intentar obtener más detalles del servicio
                    try:
                        service_data = persistence.load_soap_request(failure['request_name'])
                        error_details['type'] = service_data.get('type', 'SOAP')
                        
                        # Obtener datos de solicitud específicos según tipo
                        if error_details['type'] == 'SOAP':
                            error_details['request_xml'] = service_data.get('request_xml', '')
                        else:  # REST
                            error_details['url'] = service_data.get('url', '')
                            error_details['method'] = service_data.get('method', 'GET')
                            error_details['request_body'] = service_data.get('json_data', None)
                    except Exception as service_error:
                        logger.warning(f"No se pudieron obtener detalles adicionales del servicio: {str(service_error)}")
                
                # Enviar notificación con detalles completos
                if notifier.send_service_failure_notification(recipients, failure['request_name'], error_details):
                    notifications_sent += 1
                    logger.info(f"Notificación enviada para {failure['request_name']}")
        
        logger.info(f"Total de notificaciones enviadas: {notifications_sent}/{len(failed_requests)}")
            
    except Exception as e:
        logger.error(f"Error al notificar fallos: {str(e)}", exc_info=True)

def main():
    """Función principal"""
    global logs_dir
    try:
        if getattr(sys, 'frozen', False):
                # Estamos en un entorno compilado (exe)
                application_path = os.path.dirname(sys.executable)
                current_dir = application_path
                logger.info(f"Ejecutando como aplicación compilada: {application_path}")
        else:
            # Estamos ejecutando como script
            current_dir = os.path.dirname(os.path.abspath(__file__))
            logger.info(f"Ejecutando como script Python: {current_dir}")
    
        # Subir un nivel si estamos en el directorio 'core'
        if os.path.basename(current_dir) == 'core':
            project_root = os.path.dirname(current_dir)
        else:
            project_root = current_dir
            
        logger.info(f"Directorio raíz del proyecto: {project_root}")
    except Exception as e:
        logger.error(f"Error al detectar directorios: {str(e)}")
        # Fallback a directorio actual
        current_dir = os.getcwd()
        project_root = current_dir
        logger.info(f"Usando directorio actual como fallback: {project_root}")
        
    logger.info(f"Python path: {sys.executable}")
    logger.info(f"Argumentos: {sys.argv}")
    
    # Verificar acceso a directorios clave
    data_dir = os.path.join(project_root, 'data')
    logs_dir = os.path.join(project_root, 'logs')
    logger.info(f"Directorio data existe: {os.path.exists(data_dir)}")
    logger.info(f"Directorio logs existe: {os.path.exists(logs_dir)}")
    # Crear directorio de logs si no existe
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)
    
    logger.info(f"Directorio data: {data_dir} (existe: {os.path.exists(data_dir)})")
    logger.info(f"Directorio logs: {logs_dir} (existe: {os.path.exists(logs_dir)})")
    
    # Configurar argumentos
    parser = argparse.ArgumentParser(description='Monitor de servicios SOAP')
    parser.add_argument('request_name', nargs='?', help='Nombre del request a verificar')
    parser.add_argument('--notify', action='store_true', help='Forzar envío de notificaciones')
    args = parser.parse_args()
    
     # Inicializar componentes
    persistence = PersistenceManager(base_path=data_dir)
    soap_client = SOAPClient()
    notifier = EmailNotifier()
    
    # Lista para almacenar fallos
    failed_requests = []
    
    if args.request_name:
        # Verificar un solo request
        logger.info(f"Verificando servicio específico: {args.request_name}")
        result = check_request(persistence, soap_client, args.request_name)
        
        if result['status'] != 'ok':
            failed_requests.append(result)
    else:
        # Verificar todos los requests
        requests = persistence.list_all_requests()
        
        logger.info(f"Verificando {len(requests)} servicios")
        active_count = 0
        
        for request_data in requests:
            # Solo verificar requests activos y monitoreo habilitado
            if request_data.get('monitor_enabled', True):
                active_count += 1
                result = check_request(persistence, soap_client, request_data['name'])
                
                if result['status'] != 'ok':
                    failed_requests.append(result)
        
        logger.info(f"Servicios activos verificados: {active_count}")
    
    # Notificar fallos
    if failed_requests or args.notify:
        logger.info(f"Enviando notificaciones para {len(failed_requests)} fallos")
        notify_failures(notifier, persistence, failed_requests)
    else:
        logger.info("Todos los servicios funcionan correctamente")

    # Esperar si es necesario
    if len(sys.argv) > 1 and '--wait' in sys.argv:
        print("\nPresiona Enter para cerrar...")
        input()
        
if __name__ == "__main__":
    main()