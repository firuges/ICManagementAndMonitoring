# Punto de entrada de la aplicación

#!/usr/bin/env python
"""
Aplicación de Monitoreo de Servicios SOAP

Esta aplicación permite gestionar, monitorear y validar servicios SOAP,
generar notificaciones por correo electrónico y crear tareas programadas.

Autor: [Tu Nombre]
Versión: 1.0
Fecha: [Fecha]
"""

import os
import sys
import logging
import argparse
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

# Configurar directorio raíz
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug')
os.makedirs(debug_dir, exist_ok=True)

# Importar módulos de la aplicación
from gui.main_window import MainWindow
from core.persistence import PersistenceManager
from core.soap_client import SOAPClient
from core.notification import EmailNotifier
from core.scheduler import SOAPMonitorScheduler
# Verificar integridad de datos al inicio de la aplicación
def check_data_integrity():
    persistence = PersistenceManager()
    report = persistence.repair_requests_directory()
    print(f"Informe de integridad de datos: {report}")
    
# Llamar a esta función en main()
# Configuración de logging
def setup_logging():
    """Configura el sistema de logging"""
    logs_dir = os.path.join(current_dir, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    log_file = os.path.join(logs_dir, 'soap_monitor.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger('app')
    logger.info("=== Iniciando aplicación ===")
    
    return logger

# Después de setup_logging()
def setup_detailed_logging():
    """Configura logging detallado para diagnóstico de problemas de persistencia"""
    persistence_logger = logging.getLogger('persistence')
    persistence_logger.setLevel(logging.DEBUG)
    
    monitor_logger = logging.getLogger('monitoring_panel')
    monitor_logger.setLevel(logging.DEBUG)
    
    # Log detallado a archivo separado
    debug_handler = logging.FileHandler(os.path.join('logs', 'debug.log'))
    debug_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    debug_handler.setFormatter(debug_formatter)
    
    persistence_logger.addHandler(debug_handler)
    monitor_logger.addHandler(debug_handler)

# Llamar a esta función en main()

def parse_arguments():
    """Parsea los argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(description='Monitor de Servicios SOAP')
    
    parser.add_argument('--headless', action='store_true', 
                       help='Ejecutar en modo sin interfaz gráfica')
    
    parser.add_argument('--check', metavar='SERVICE_NAME', type=str,
                       help='Verificar un servicio específico')
    
    parser.add_argument('--check-all', action='store_true',
                       help='Verificar todos los servicios')
    
    return parser.parse_args()

def run_headless(args, logger):
    """
    Ejecuta la aplicación en modo sin interfaz gráfica.
    
    Args:
        args: Argumentos de línea de comandos
        logger: Logger configurado
    """
    # Inicializar componentes
    persistence = PersistenceManager()
    soap_client = SOAPClient()
    notifier = EmailNotifier()
    
    logger.info("Ejecutando en modo sin interfaz gráfica")
    
    if args.check:
        # Verificar un servicio específico
        from core.monitor import check_request
        
        logger.info(f"Verificando servicio: {args.check}")
        result = check_request(persistence, soap_client, args.check)
        
        if result['status'] != 'ok':
            logger.error(f"Error en servicio {args.check}: {result.get('error', 'Error desconocido')}")
            sys.exit(1)
        else:
            logger.info(f"Servicio {args.check} verificado correctamente")
            sys.exit(0)
    
    elif args.check_all:
        # Verificar todos los servicios
        from core.monitor import main as run_monitor
        
        logger.info("Verificando todos los servicios")
        run_monitor()
        sys.exit(0)
    
    else:
        logger.error("Debe especificar una acción: --check o --check-all")
        sys.exit(1)

def run_gui():
    """Ejecuta la aplicación con interfaz gráfica"""
    # Crear aplicación Qt
    app = QApplication(sys.argv)
    app.setApplicationName("Monitor de Servicios SOAP")
    
    # Verificar directorios de datos
    data_dir = os.path.join(current_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(os.path.join(data_dir, 'requests'), exist_ok=True)
    
    # Crear y mostrar ventana principal
    window = MainWindow()
    window.show()
    
    # Ejecutar bucle de eventos
    sys.exit(app.exec_())

def main():
    """Función principal de la aplicación"""
    # Configurar logging
    logger = setup_logging()
    
    # Parsear argumentos
    args = parse_arguments()
    
    try:
        # Determinar modo de ejecución
        if args.headless or args.check or args.check_all:
            run_headless(args, logger)
        else:
            run_gui()
    except Exception as e:
        logger.error(f"Error en la aplicación: {str(e)}", exc_info=True)
        sys.exit(1)
        
# Añadir esto a app.py para diagnóstico de entorno
def check_environment():
    """Verifica el entorno de ejecución para diagnóstico"""
    logger = logging.getLogger('environment')
    
    # Comprobar directorios esenciales
    logger.info(f"Directorio actual: {os.getcwd()}")
    
    data_dir = os.path.join(os.getcwd(), 'data')
    debug_dir = os.path.join(os.getcwd(), 'debug')
    
    logger.info(f"Directorio de datos existe: {os.path.exists(data_dir)}")
    logger.info(f"Directorio debug existe: {os.path.exists(debug_dir)}")
    
    # Comprobar permisos
    try:
        test_file = os.path.join(data_dir, 'test_write.tmp')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        logger.info("Permisos de escritura verificados correctamente")
    except Exception as e:
        logger.error(f"Error al verificar permisos: {str(e)}")

# Configurar serializador JSON global para manejar fechas
def setup_json_serialization():
    """Configura la serialización JSON global para manejar tipos especiales"""
    from core.soap_client import json_serial
    import functools
    
    # Monkey patch la función dumps de json para usar nuestro serializador por defecto
    original_dumps = json.dumps
    json.dumps = functools.partial(original_dumps, default=json_serial)
    
    logger.info("Serialización JSON configurada para manejar fechas")

# Llamar a esta función al inicio de main()
if __name__ == "__main__":
    main()