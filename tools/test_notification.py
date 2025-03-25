#!/usr/bin/env python
"""
Script de prueba para el sistema de notificaciones por correo electrónico.
Permite verificar que las notificaciones funcionan correctamente desde el 
entorno del sistema operativo, incluso cuando la aplicación está compilada.

Uso: python test_notification.py [--config=ruta/config.json] [--recipient=email@example.com]
"""

import os
import sys
import json  # Importando json globalmente
import argparse
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('test_notification')

# Función para determinar directorio base (funciona en modo script y compilado)
def get_application_path():
    """Obtiene el directorio base de la aplicación, compatible con .exe"""
    if getattr(sys, 'frozen', False):
        # Estamos ejecutando en aplicación compilada
        return os.path.dirname(sys.executable)
    else:
        # Estamos ejecutando en modo script
        return os.path.dirname(os.path.abspath(__file__))

def find_config_file(config_path: Optional[str] = None) -> Optional[str]:
    """
    Busca el archivo de configuración SMTP.
    
    Args:
        config_path (str, optional): Ruta personalizada al archivo de configuración
        
    Returns:
        Optional[str]: Ruta al archivo encontrado o None si no se encuentra
    """
    # Si se especifica una ruta, verificar si existe
    if config_path and os.path.exists(config_path):
        return config_path
    
    # Buscar en la ubicación estándar del proyecto
    app_dir = get_application_path()
    # Subir un nivel si estamos en subdirectorio
    if os.path.basename(app_dir) in ['core', 'tools', 'gui']:
        app_dir = os.path.dirname(app_dir)
        
    # Priorizar la estructura estándar del proyecto
    config_file = os.path.join(app_dir, 'data', 'smtp_config.json')
    
    if os.path.exists(config_file):
        logger.info(f"Archivo de configuración encontrado en ubicación estándar: {config_file}")
        return config_file
    
    # Si no se encuentra en la ubicación estándar, buscar en ubicaciones alternativas
    possible_paths = [
        os.path.join(app_dir, 'smtp_config.json'),
        os.path.join(os.getcwd(), 'data', 'smtp_config.json'),
        os.path.join(os.getcwd(), 'smtp_config.json')
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            logger.info(f"Archivo de configuración encontrado en ubicación alternativa: {path}")
            return path
    
    logger.error("No se encontró el archivo de configuración SMTP")
    return None

def load_email_config(config_file: str) -> Optional[Dict[str, Any]]:
    """
    Carga la configuración SMTP desde un archivo.
    
    Args:
        config_file (str): Ruta al archivo de configuración
        
    Returns:
        Optional[Dict[str, Any]]: Configuración SMTP o None si hay error
    """
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Verificar campos mínimos
        required_fields = ['server', 'username', 'password']
        for field in required_fields:
            if field not in config:
                logger.error(f"Campo requerido faltante en la configuración: {field}")
                return None
        
        return config
    except Exception as e:
        logger.error(f"Error al cargar configuración: {str(e)}")
        return None

def find_recipients(email_path: Optional[str] = None, extra_recipient: Optional[str] = None) -> List[str]:
    """
    Busca la lista de destinatarios de correo.
    
    Args:
        email_path (str, optional): Ruta al archivo de configuración de emails
        extra_recipient (str, optional): Destinatario adicional
        
    Returns:
        List[str]: Lista de destinatarios
    """
    recipients = []
    
    # Añadir destinatario extra si se especifica
    if extra_recipient:
        recipients.append(extra_recipient)
        logger.info(f"Usando destinatario proporcionado: {extra_recipient}")
    
    # Si se proporciona una ruta específica, usarla
    if email_path and os.path.exists(email_path):
        # Usar la ruta proporcionada
        pass
    else:
        # Buscar en la ubicación estándar del proyecto
        app_dir = get_application_path()
        # Subir un nivel si estamos en subdirectorio
        if os.path.basename(app_dir) in ['core', 'tools', 'gui']:
            app_dir = os.path.dirname(app_dir)
            
        # Priorizar la estructura estándar del proyecto
        email_path = os.path.join(app_dir, 'data', 'email_config.json')
        
        if not os.path.exists(email_path):
            # Si no existe, buscar en ubicaciones alternativas
            possible_paths = [
                os.path.join(app_dir, 'email_config.json'),
                os.path.join(os.getcwd(), 'data', 'email_config.json'),
                os.path.join(os.getcwd(), 'email_config.json')
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    email_path = path
                    break
    
    # Cargar destinatarios desde archivo
    if email_path and os.path.exists(email_path):
        logger.info(f"Usando archivo de configuración de emails: {email_path}")
        try:
            with open(email_path, 'r', encoding='utf-8') as f:
                email_config = json.load(f)
            
            file_recipients = email_config.get('recipients', [])
            for recipient in file_recipients:
                if recipient not in recipients:  # Evitar duplicados
                    recipients.append(recipient)
            
            logger.info(f"Destinatarios cargados desde archivo: {len(file_recipients)}")
            
            # Mostrar lista para depuración
            if file_recipients:
                logger.info(f"Lista de destinatarios: {file_recipients}")
            else:
                logger.warning(f"El archivo {email_path} existe pero no contiene destinatarios")
                
        except Exception as e:
            logger.error(f"Error al cargar destinatarios: {str(e)}")
    else:
        logger.warning(f"Archivo de configuración de emails no encontrado: {email_path}")
    
    # Si no hay destinatarios, intentar usar la dirección del remitente como último recurso
    if not recipients:
        logger.warning("No se encontraron destinatarios configurados, intentando usar remitente")
        
        # Buscar archivo de configuración SMTP en la ubicación estándar
        smtp_config_path = os.path.join(app_dir, 'data', 'smtp_config.json')
        if os.path.exists(smtp_config_path):
            try:
                with open(smtp_config_path, 'r', encoding='utf-8') as f:
                    smtp_config = json.load(f)
                
                from_email = smtp_config.get('from_email') or smtp_config.get('username')
                if from_email and '@' in from_email:
                    recipients.append(from_email)
                    logger.info(f"Usando remitente como destinatario: {from_email}")
            except Exception as e:
                logger.error(f"Error al obtener remitente: {str(e)}")
    
    if not recipients:
        logger.error("No se encontraron destinatarios en ninguna fuente")
    
    return recipients

def test_notification(smtp_config: Dict[str, Any], recipients: List[str], test_type: str = 'basic'):
    """
    Realiza una prueba de notificación.
    
    Args:
        smtp_config (Dict[str, Any]): Configuración SMTP
        recipients (List[str]): Lista de destinatarios
        test_type (str): Tipo de prueba ('basic', 'error', 'summary')
    """
    # Importar el notificador
    sys.path.append(get_application_path())
    try:
        from core.notification import EmailNotifier
        notifier = EmailNotifier(smtp_config)
    except ImportError:
        # Si no se puede importar desde core, intentar importar directamente
        import importlib.util
        
        # Buscar en posibles ubicaciones
        app_dir = get_application_path()
        possible_paths = [
            os.path.join(app_dir, 'core', 'notification.py'),
            os.path.join(app_dir, 'notification.py'),
            os.path.join(app_dir, '..', 'core', 'notification.py')
        ]
        
        module_path = None
        for path in possible_paths:
            if os.path.exists(path):
                module_path = path
                break
        
        if not module_path:
            logger.error("No se pudo encontrar el módulo notification.py")
            return False
            
        # Cargar módulo dinámicamente
        spec = importlib.util.spec_from_file_location("notification", module_path)
        notification_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(notification_module)
        
        # Crear instancia de notificador
        notifier = notification_module.EmailNotifier(smtp_config)
    
    # Realizar prueba según el tipo
    if test_type == 'basic':
        logger.info("Realizando prueba básica de notificación...")
        
        # Mensaje simple
        subject = "Prueba de sistema de notificaciones SOAP Monitor"
        content = f"""
        Esta es una prueba del sistema de notificaciones.
        
        Fecha y hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        Modo de ejecución: {'Aplicación compilada' if getattr(sys, 'frozen', False) else 'Script Python'}
        
        Si ha recibido este mensaje, el sistema de notificaciones funciona correctamente.
        """
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .success {{ color: green; background-color: #e8f5e9; padding: 10px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <h2 class="success">Prueba de sistema de notificaciones exitosa</h2>
            <p>Esta es una prueba del sistema de notificaciones.</p>
            <p><strong>Fecha y hora:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>Modo de ejecución:</strong> {'Aplicación compilada' if getattr(sys, 'frozen', False) else 'Script Python'}</p>
            <p>Si ha recibido este mensaje, el sistema de notificaciones funciona correctamente.</p>
        </body>
        </html>
        """
        
        result = notifier.send_notification(recipients, subject, content, html_content)
        
    elif test_type == 'error':
        logger.info("Realizando prueba de notificación de error...")
        
        # Simular error de servicio
        error_details = {
            'error': 'Este es un error simulado para prueba de notificaciones',
            'status': 'test_error',
            'timestamp': datetime.now().isoformat(),
            'type': 'SOAP',
            'group': 'Pruebas'
        }
        
        result = notifier.send_service_failure_notification(recipients, "Servicio de Prueba", error_details)
        
    elif test_type == 'summary':
        logger.info("Realizando prueba de notificación de resumen diario...")
        
        # Simular estadísticas
        service_stats = {
            'total': 10,
            'ok': 7,
            'failed': 1,
            'warning': 1,
            'error': 1,
            'not_checked': 0,
            'failed_services': [
                {
                    'name': 'Servicio de Prueba 1',
                    'status': 'failed',
                    'error': 'Error simulado 1'
                },
                {
                    'name': 'Servicio de Prueba 2',
                    'status': 'warning',
                    'error': 'Advertencia simulada'
                }
            ]
        }
        
        result = notifier.send_daily_summary(recipients, service_stats)
        
    else:
        logger.error(f"Tipo de prueba no válido: {test_type}")
        return False
    
    if result:
        logger.info(f"✅ Notificación enviada correctamente a {len(recipients)} destinatarios")
        return True
    else:
        logger.error("❌ Error al enviar notificación")
        return False

def main():
    """Función principal"""
    # Configurar argumentos
    parser = argparse.ArgumentParser(description='Prueba del sistema de notificaciones')
    parser.add_argument('--config', help='Ruta al archivo de configuración SMTP')
    parser.add_argument('--email-config', help='Ruta al archivo de configuración de emails')
    parser.add_argument('--recipient', help='Destinatario adicional para la prueba')
    parser.add_argument('--type', choices=['basic', 'error', 'summary'], default='basic',
                        help='Tipo de prueba: básica, error o resumen')
    parser.add_argument('--debug', action='store_true', help='Activar modo de depuración')
    
    args = parser.parse_args()
    
    # Configurar nivel de logging
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Modo de depuración activado")
    
    # Mostrar información del entorno
    app_path = get_application_path()
    logger.info(f"Directorio de la aplicación: {app_path}")
    logger.info(f"Modo de ejecución: {'Aplicación compilada' if getattr(sys, 'frozen', False) else 'Script Python'}")
    
    # Buscar y cargar configuración SMTP
    config_file = find_config_file(args.config)
    if not config_file:
        logger.error("No se pudo encontrar el archivo de configuración SMTP")
        return 1
    
    smtp_config = load_email_config(config_file)
    if not smtp_config:
        logger.error("No se pudo cargar la configuración SMTP")
        return 1
    
    # Buscar destinatarios
    recipients = find_recipients(args.email_config, args.recipient)
    if not recipients:
        logger.error("No se encontraron destinatarios para la prueba")
        return 1
    
    logger.info(f"Destinatarios de prueba: {recipients}")
    
    # Ejecutar prueba
    success = test_notification(smtp_config, recipients, args.type)
    
    # Mostrar resultado
    if success:
        print("\n✅ Prueba de notificación completada con éxito")
        print(f"Se ha enviado un correo de prueba a {', '.join(recipients)}")
        return 0
    else:
        print("\n❌ Error en la prueba de notificación")
        print("Revise los logs para más detalles")
        return 1

if __name__ == "__main__":
    sys.exit(main())