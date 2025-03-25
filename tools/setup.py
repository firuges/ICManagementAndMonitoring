#!/usr/bin/env python
"""
Script de instalación y configuración para el monitor de servicios SOAP.
Este script prepara el entorno para la aplicación, creando los directorios
necesarios y configurando archivos básicos.

Uso: python setup.py [--data-dir=dir] [--smtp=archivo_config]
"""

import os
import sys
import json
import shutil
import logging
import argparse
from datetime import datetime
from typing import Dict, Any

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('setup')

# Función para determinar directorio base
def get_application_path():
    """Obtiene el directorio base de la aplicación, compatible con .exe"""
    if getattr(sys, 'frozen', False):
        # Estamos ejecutando en aplicación compilada
        return os.path.dirname(sys.executable)
    else:
        # Estamos ejecutando en modo script
        return os.path.dirname(os.path.abspath(__file__))

def create_directory_structure(base_dir: str) -> Dict[str, str]:
    """
    Crea la estructura de directorios necesaria para la aplicación.
    
    Args:
        base_dir (str): Directorio base donde crear la estructura
        
    Returns:
        Dict[str, str]: Diccionario con rutas de los directorios creados
    """
    logger.info(f"Creando estructura de directorios en: {base_dir}")
    
    # Definir directorios
    dirs = {
        'data': os.path.join(base_dir, 'data'),
        'logs': os.path.join(base_dir, 'logs'),
        'debug': os.path.join(base_dir, 'debug'),
        'requests': None  # Se asignará después
    }
    
    # Crear directorio data
    os.makedirs(dirs['data'], exist_ok=True)
    
    # Crear subdirectorio requests
    dirs['requests'] = os.path.join(dirs['data'], 'requests')
    os.makedirs(dirs['requests'], exist_ok=True)
    
    # Crear directorio logs
    os.makedirs(dirs['logs'], exist_ok=True)
    
    # Crear directorio debug
    os.makedirs(dirs['debug'], exist_ok=True)
    
    # Verificar que los directorios existen
    for name, path in dirs.items():
        if os.path.exists(path):
            logger.info(f"✓ Directorio {name} creado: {path}")
        else:
            logger.error(f"✗ Error al crear directorio {name}: {path}")
    
    return dirs

def create_config_files(dirs: Dict[str, str], smtp_config_file: str = None) -> None:
    """
    Crea archivos de configuración básicos para la aplicación.
    
    Args:
        dirs (Dict[str, str]): Diccionario con las rutas de los directorios
        smtp_config_file (str, optional): Ruta a un archivo de configuración SMTP existente
    """
    data_dir = dirs['data']
    
    # 1. Crear o copiar configuración SMTP
    smtp_config_path = os.path.join(data_dir, 'smtp_config.json')
    
    if smtp_config_file and os.path.exists(smtp_config_file):
        # Copiar archivo existente
        shutil.copy2(smtp_config_file, smtp_config_path)
        logger.info(f"Archivo de configuración SMTP copiado desde: {smtp_config_file}")
    else:
        # Crear plantilla básica
        smtp_config = {
            'server': 'smtp.gmail.com',
            'port': 587,
            'use_tls': True,
            'username': '',
            'password': '',
            'from_email': ''
        }
        
        with open(smtp_config_path, 'w', encoding='utf-8') as f:
            json.dump(smtp_config, f, indent=2)
        
        logger.info(f"Plantilla de configuración SMTP creada: {smtp_config_path}")
    
    # 2. Crear configuración de notificaciones
    notify_config_path = os.path.join(data_dir, 'notification_config.json')
    
    if not os.path.exists(notify_config_path):
        notify_config = {
            'notify_on_error': True,
            'notify_on_validation': True,
            'notify_daily_summary': False
        }
        
        with open(notify_config_path, 'w', encoding='utf-8') as f:
            json.dump(notify_config, f, indent=2)
        
        logger.info(f"Configuración de notificaciones creada: {notify_config_path}")
    
    # 3. Crear configuración de emails
    email_config_path = os.path.join(data_dir, 'email_config.json')
    
    if not os.path.exists(email_config_path):
        email_config = {
            'recipients': []
        }
        
        with open(email_config_path, 'w', encoding='utf-8') as f:
            json.dump(email_config, f, indent=2)
        
        logger.info(f"Configuración de emails creada: {email_config_path}")
    
    # 4. Crear archivo de configuración general
    config_path = os.path.join(data_dir, 'config.json')
    
    if not os.path.exists(config_path):
        config = {
            'app_name': 'SOAP Monitor',
            'version': '1.0',
            'data_dir': data_dir,
            'logs_dir': dirs['logs'],
            'debug_dir': dirs['debug'],
            'created_at': datetime.now().isoformat(),
            'last_config_update': datetime.now().isoformat()
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Configuración general creada: {config_path}")

def update_config(data_dir: str, key: str, value: Any) -> None:
    """
    Actualiza un valor en el archivo de configuración general.
    
    Args:
        data_dir (str): Directorio de datos
        key (str): Clave a actualizar
        value (Any): Nuevo valor
    """
    config_path = os.path.join(data_dir, 'config.json')
    
    if os.path.exists(config_path):
        try:
            # Cargar configuración actual
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Actualizar valor
            config[key] = value
            config['last_config_update'] = datetime.now().isoformat()
            
            # Guardar configuración
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Configuración actualizada: {key} = {value}")
            
        except Exception as e:
            logger.error(f"Error al actualizar configuración: {str(e)}")
    else:
        logger.error(f"Archivo de configuración no encontrado: {config_path}")

def configure_smtp(data_dir: str) -> None:
    """
    Asistente para configurar SMTP interactivamente.
    
    Args:
        data_dir (str): Directorio de datos
    """
    print("\n=== Configuración de Servidor SMTP ===\n")
    
    # Cargar configuración actual si existe
    smtp_config_path = os.path.join(data_dir, 'smtp_config.json')
    current_config = {}
    
    if os.path.exists(smtp_config_path):
        try:
            with open(smtp_config_path, 'r', encoding='utf-8') as f:
                current_config = json.load(f)
            print("Configuración SMTP actual cargada")
        except Exception as e:
            logger.error(f"Error al cargar configuración SMTP: {str(e)}")
    
    # Solicitar datos
    server = input(f"Servidor SMTP [{current_config.get('server', 'smtp.gmail.com')}]: ")
    if not server:
        server = current_config.get('server', 'smtp.gmail.com')
    
    port_str = input(f"Puerto [{current_config.get('port', 587)}]: ")
    if not port_str:
        port = current_config.get('port', 587)
    else:
        port = int(port_str)
    
    use_tls_str = input(f"Usar TLS (y/n) [{current_config.get('use_tls', True) and 'y' or 'n'}]: ")
    if not use_tls_str:
        use_tls = current_config.get('use_tls', True)
    else:
        use_tls = use_tls_str.lower() in ['y', 'yes', 's', 'si', 'sí']
    
    username = input(f"Usuario [{current_config.get('username', '')}]: ")
    if not username:
        username = current_config.get('username', '')
    
    password = input(f"Contraseña [{'*' * 8 if current_config.get('password') else ''}]: ")
    if not password:
        password = current_config.get('password', '')
    
    from_email = input(f"Email remitente [{current_config.get('from_email', username)}]: ")
    if not from_email:
        from_email = current_config.get('from_email', username)
    
    # Crear nueva configuración
    smtp_config = {
        'server': server,
        'port': port,
        'use_tls': use_tls,
        'username': username,
        'password': password,
        'from_email': from_email
    }
    
    # Guardar configuración
    with open(smtp_config_path, 'w', encoding='utf-8') as f:
        json.dump(smtp_config, f, indent=2)
    
    print(f"\n✓ Configuración SMTP guardada en: {smtp_config_path}")

def configure_recipients(data_dir: str) -> None:
    """
    Asistente para configurar destinatarios de correo interactivamente.
    
    Args:
        data_dir (str): Directorio de datos
    """
    print("\n=== Configuración de Destinatarios de Correo ===\n")
    
    # Cargar configuración actual
    email_config_path = os.path.join(data_dir, 'email_config.json')
    
    if os.path.exists(email_config_path):
        try:
            with open(email_config_path, 'r', encoding='utf-8') as f:
                email_config = json.load(f)
            
            current_recipients = email_config.get('recipients', [])
            
            if current_recipients:
                print("Destinatarios actuales:")
                for i, recipient in enumerate(current_recipients, 1):
                    print(f"  {i}. {recipient}")
                print("")
        except Exception as e:
            logger.error(f"Error al cargar destinatarios: {str(e)}")
            current_recipients = []
    else:
        current_recipients = []
    
    # Menú de opciones
    while True:
        print("\nOpciones:")
        print("1. Añadir destinatario")
        print("2. Eliminar destinatario")
        print("3. Guardar y salir")
        
        option = input("\nSeleccione una opción (1-3): ")
        
        if option == '1':
            # Añadir destinatario
            email = input("Ingrese email: ")
            if email:
                # Validar formato básico
                if '@' in email and '.' in email:
                    if email not in current_recipients:
                        current_recipients.append(email)
                        print(f"✓ Destinatario añadido: {email}")
                    else:
                        print("Este email ya está en la lista")
                else:
                    print("Formato de email inválido")
        
        elif option == '2':
            # Eliminar destinatario
            if current_recipients:
                print("Destinatarios actuales:")
                for i, recipient in enumerate(current_recipients, 1):
                    print(f"  {i}. {recipient}")
                
                try:
                    index = int(input("\nIngrese número de destinatario a eliminar: ")) - 1
                    if 0 <= index < len(current_recipients):
                        removed = current_recipients.pop(index)
                        print(f"✓ Destinatario eliminado: {removed}")
                    else:
                        print("Índice fuera de rango")
                except ValueError:
                    print("Ingrese un número válido")
            else:
                print("No hay destinatarios para eliminar")
        
        elif option == '3':
            # Guardar y salir
            email_config = {'recipients': current_recipients}
            
            with open(email_config_path, 'w', encoding='utf-8') as f:
                json.dump(email_config, f, indent=2)
            
            print(f"\n✓ Configuración de destinatarios guardada ({len(current_recipients)} emails)")
            break
        
        else:
            print("Opción no válida")

def test_notifications(data_dir: str) -> None:
    """
    Realiza una prueba de notificaciones.
    
    Args:
        data_dir (str): Directorio de datos
    """
    print("\n=== Prueba de Notificaciones ===\n")
    
    # Verificar si existe el script de prueba
    app_dir = get_application_path()
    test_script = os.path.join(app_dir, 'test_notification.py')
    
    if not os.path.exists(test_script):
        # Crear script de prueba
        from test_notification_script import get_script_content
        
        try:
            with open(test_script, 'w', encoding='utf-8') as f:
                f.write(get_script_content())
            
            print(f"Script de prueba creado: {test_script}")
        except Exception as e:
            logger.error(f"Error al crear script de prueba: {str(e)}")
            print("No se pudo crear el script de prueba. Verifique los logs.")
            return
    
    # Ejecutar prueba
    print("\nTipos de prueba disponibles:")
    print("1. Básica - Envía un correo simple de prueba")
    print("2. Error - Simula una notificación de error de servicio")
    print("3. Resumen - Simula un resumen diario de servicios")
    
    option = input("\nSeleccione una opción (1-3): ")
    
    if option == '1':
        test_type = 'basic'
    elif option == '2':
        test_type = 'error'
    elif option == '3':
        test_type = 'summary'
    else:
        print("Opción no válida")
        return
    
    # Preparar comando
    smtp_config = os.path.join(data_dir, 'smtp_config.json')
    email_config = os.path.join(data_dir, 'email_config.json')
    
    if not os.path.exists(smtp_config):
        print(f"Archivo de configuración SMTP no encontrado: {smtp_config}")
        return
    
    if not os.path.exists(email_config):
        print(f"Archivo de configuración de emails no encontrado: {email_config}")
        return
    
    # Ejecutar prueba
    import subprocess
    
    try:
        cmd = [
            sys.executable,
            test_script,
            f'--config={smtp_config}',
            f'--email-config={email_config}',
            f'--type={test_type}'
        ]
        
        print(f"\nEjecutando prueba {test_type}...\n")
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        # Mostrar salida
        print(process.stdout)
        
        if process.stderr:
            print("Errores encontrados:")
            print(process.stderr)
        
        if process.returncode == 0:
            print("\n✓ Prueba de notificación completada con éxito")