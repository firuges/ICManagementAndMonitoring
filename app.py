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
from PyQt5.QtWidgets import QApplication, QDialog
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

def get_application_path():
    """Obtiene el directorio base de la aplicación, compatible con .exe"""
    if getattr(sys, 'frozen', False):
        # Estamos ejecutando en aplicación compilada
        return os.path.dirname(sys.executable)
    else:
        # Estamos ejecutando en modo script
        return os.path.dirname(os.path.abspath(__file__))

# Configurar directorio raíz
application_path = get_application_path()
current_dir = application_path
sys.path.append(current_dir)

# Crear directorios clave si no existen
data_dir = os.path.join(application_path, 'data')
logs_dir = os.path.join(application_path, 'logs')
debug_dir = os.path.join(application_path, 'debug')

os.makedirs(data_dir, exist_ok=True)
os.makedirs(logs_dir, exist_ok=True)
os.makedirs(debug_dir, exist_ok=True)

# Verificar si la aplicación se está ejecutando como un script o como un .exe
is_compiled = getattr(sys, 'frozen', False)
run_mode = "compiled" if is_compiled else "script"

def check_data_integrity():
    from core.persistence import PersistenceManager
    persistence = PersistenceManager(base_path=data_dir)
    report = persistence.repair_requests_directory()
    logger.info(f"Informe de integridad de datos: {report}")
    
# Llamar a esta función en main()
# Configuración de logging
def setup_logging():
    """Configura el sistema de logging"""
    log_file = os.path.join(logs_dir, 'soap_monitor.log')
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ]
    )
    
    logger = logging.getLogger('app')
    logger.info(f"=== Iniciando aplicación (modo: {run_mode}) ===")
    logger.info(f"Directorio base: {application_path}")
    logger.info(f"Directorio datos: {data_dir}")
    logger.info(f"Directorio logs: {logs_dir}")
    logger.info(f"Python executable: {sys.executable}")
    try:
        from core.notification import setup_notification_log
        setup_notification_log(logs_dir)
        logger.info("Log especializado para notificaciones configurado correctamente")
    except ImportError:
        logger.warning("No se pudo configurar log especializado para notificaciones")
    
    return logger

# Después de setup_logging()
def setup_detailed_logging():
    """Configura logging detallado para diagnóstico de problemas de persistencia"""
    persistence_logger = logging.getLogger('persistence')
    persistence_logger.setLevel(logging.DEBUG)
    
    monitor_logger = logging.getLogger('monitoring_panel')
    monitor_logger.setLevel(logging.DEBUG)
    
    # Log detallado a archivo separado
    debug_handler = logging.FileHandler(os.path.join(logs_dir, 'debug.log'))
    debug_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    debug_handler.setFormatter(debug_formatter)
    
    persistence_logger.addHandler(debug_handler)
    monitor_logger.addHandler(debug_handler)

# Llamar a esta función en main()

def parse_arguments():
    """Parsea los argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(description='Monitor de servicios SOAP')
    
    # Hacer que request_name sea completamente opcional
    parser.add_argument('request_name', nargs='?', default=None, 
                       help='Nombre del request a verificar')
    parser.add_argument('--notify', action='store_true', 
                       help='Forzar envío de notificaciones')
    parser.add_argument('--data-dir', help='Directorio de datos de la aplicación')
    parser.add_argument('--logs-dir', help='Directorio de logs de la aplicación')
    parser.add_argument('--headless', action='store_true', 
                       help='Ejecutar en modo sin interfaz gráfica')
    parser.add_argument('--check', metavar='SERVICE_NAME', type=str, 
                       help='Verificar un servicio específico')
    parser.add_argument('--check-all', action='store_true', 
                       help='Verificar todos los servicios')
    parser.add_argument('--scheduled-task', action='store_true', 
                       help='Indica que la ejecución proviene del programador de tareas')
    parser.add_argument('--no-admin-check', action='store_true', 
                       help='Omitir la verificación de permisos de administrador')
    return parser.parse_args()

def run_headless(args, logger):
    """
    Ejecuta la aplicación en modo sin interfaz gráfica.
    
    Args:
        args: Argumentos de línea de comandos
        logger: Logger configurado
    """
    # Inicializar componentes con rutas absolutas
    from core.persistence import PersistenceManager
    from core.soap_client import SOAPClient
    from core.notification import EmailNotifier
    
    persistence = PersistenceManager(base_path=data_dir)
    soap_client = SOAPClient()
    notifier = EmailNotifier()
    
    # Cargar configuración SMTP para notificaciones
    try:
        smtp_config_path = os.path.join(data_dir, 'smtp_config.json')
        if os.path.exists(smtp_config_path):
            import json
            with open(smtp_config_path, 'r', encoding='utf-8') as f:
                smtp_config = json.load(f)
            notifier.configure(smtp_config)
            logger.info("Configuración SMTP cargada correctamente")
    except Exception as e:
        logger.error(f"Error al cargar configuración SMTP: {str(e)}")
    
    logger.info("Ejecutando en modo sin interfaz gráfica")
    
    # Determinar qué servicio verificar
    service_to_check = None
    
    if args.check:
        service_to_check = args.check
    elif args.request_name:
        service_to_check = args.request_name
    
    if service_to_check:
        # Verificar un servicio específico
        from core.monitor import check_request
        
        logger.info(f"Verificando servicio: {service_to_check}")
        result = check_request(persistence, soap_client, service_to_check)
        
        if result['status'] != 'ok':
            logger.error(f"Error en servicio {service_to_check}: {result.get('error', 'Error desconocido')}")
            
            # Enviar notificación si se solicita
            if args.notify or getattr(args, 'scheduled_task', False):
                logger.info("Enviando notificación por error detectado")
                from core.monitor import notify_failures
                notify_failures(notifier, persistence, [result])
                
            sys.exit(1)
        else:
            logger.info(f"Servicio {service_to_check} verificado correctamente")
            sys.exit(0)
    
    elif args.check_all:
        # Verificar todos los servicios
        from core.monitor import main as run_monitor
        
        logger.info("Verificando todos los servicios")
        # Modificar sys.argv para pasar --notify si es necesario
        if args.notify or getattr(args, 'scheduled_task', False):
            if '--notify' not in sys.argv:
                sys.argv.append('--notify')
        
        run_monitor()
        sys.exit(0)
    
    else:
        logger.error("Modo headless solicitado pero no se especificó una acción válida")
        logger.error("Use --check <servicio>, --check-all, o proporcione un nombre de servicio")
        sys.exit(1)

def run_gui_with_app(app):
    """Ejecuta la aplicación con interfaz gráfica usando la app ya creada"""
    # Importar módulos de la aplicación
    from gui.main_window import MainWindow
    
    # Configurar directorios y rutas
    os.environ['SOAP_MONITOR_DATA_DIR'] = data_dir
    os.environ['SOAP_MONITOR_LOGS_DIR'] = logs_dir
    os.environ['SOAP_MONITOR_DEBUG_DIR'] = debug_dir
    
    # Crear y mostrar ventana principal con rutas absolutas
    window = MainWindow(data_path=data_dir, logs_path=logs_dir)
    window.show()
    
    # Ejecutar bucle de eventos
    sys.exit(app.exec_())

def run_gui():
    """Ejecuta la aplicación con interfaz gráfica (versión legacy)"""
    # Crear aplicación Qt
    app = QApplication(sys.argv)
    app.setApplicationName("Monitor de Servicios SOAP")
    
    run_gui_with_app(app)

def main():
    """Función principal de la aplicación"""
    global logger
    
    # Configurar logging
    logger = setup_logging()
    
    # Verificar entorno e integridad
    check_environment()
    check_data_integrity()
    
    # Configurar logging detallado
    setup_detailed_logging()
    
    # Parsear argumentos
    args = parse_arguments()
    
    logger.info(f"Argumentos recibidos: {sys.argv}")
    logger.info(f"Args parseados: {args}")
    logger.info(f"Headless: {args.headless}")
    logger.info(f"Check: {args.check}")
    logger.info(f"Check-all: {args.check_all}")
    logger.info(f"Request name: {args.request_name}")
    logger.info(f"Scheduled task: {getattr(args, 'scheduled_task', False)}")

    try:
        should_run_headless = determine_execution_mode(args)
        
        if should_run_headless:
            logger.info("Ejecutando en modo headless")
            run_headless(args, logger)
        else:
            logger.info("Ejecutando modo GUI")
            
            # Crear aplicación Qt primero
            app = QApplication(sys.argv)
            
            # Verificar si se debe mostrar el diálogo de administrador
            from gui.admin_check_dialog import should_show_admin_dialog
            
            if not args.no_admin_check and should_show_admin_dialog():
                from gui.admin_check_dialog import AdminCheckDialog
                admin_dialog = AdminCheckDialog()
                
                # Si el usuario cancela o cierra el diálogo, salir
                if admin_dialog.exec_() != QDialog.Accepted:
                    logger.info("Usuario canceló la verificación de administrador")
                    sys.exit(0)
            
            # Continuar con la GUI
            run_gui_with_app(app)
            
    except Exception as e:
        logger.error(f"Error en la aplicación: {str(e)}", exc_info=True)
        sys.exit(1)

def determine_execution_mode(args) -> bool:
    """
    Determina si la aplicación debe ejecutarse en modo headless o GUI.
    
    Args:
        args: Argumentos parseados de línea de comandos
        
    Returns:
        bool: True si debe ejecutarse en modo headless, False para GUI
    """
    logger = logging.getLogger('execution_mode')
    
    # Casos explícitos de modo headless
    explicit_headless_flags = [
        args.headless,
        args.check is not None,
        args.check_all,
        getattr(args, 'scheduled_task', False)
    ]
    
    # Si cualquier flag explícito de headless está presente
    if any(explicit_headless_flags):
        logger.info(f"Modo headless por flags explícitos: {explicit_headless_flags}")
        return True
    
    # Si se proporciona un request_name sin otros flags, también es headless
    if args.request_name and not any([args.headless, args.check, args.check_all]):
        logger.info(f"Modo headless por request_name posicional: {args.request_name}")
        return True
    
    # Verificar si hay argumentos que indiquen ejecución programada
    # (esto es para casos donde el programador de tareas no pase --scheduled-task)
    if len(sys.argv) > 1:
        # Si el primer argumento parece ser un nombre de servicio (sin guiones)
        first_arg = sys.argv[1]
        if not first_arg.startswith('-') and first_arg not in ['--help', '-h']:
            # Verificar si este argumento corresponde a un servicio existente
            try:
                from core.persistence import PersistenceManager
                persistence = PersistenceManager(base_path=data_dir)
                requests = persistence.list_all_requests()
                service_names = [req.get('name', '') for req in requests]
                
                if first_arg in service_names:
                    logger.info(f"Modo headless por nombre de servicio válido: {first_arg}")
                    return True
            except Exception as e:
                logger.warning(f"No se pudo verificar servicios existentes: {str(e)}")
    
    # Por defecto, ejecutar en modo GUI
    logger.info("Modo GUI por defecto")
    return False

# Añadir esto a app.py para diagnóstico de entorno
def check_environment():
    """Verifica el entorno de ejecución para diagnóstico"""
    logger = logging.getLogger('environment')
    
    # Comprobar directorios esenciales
    logger.info(f"Directorio actual: {os.getcwd()}")
    logger.info(f"Directorio de datos existe: {os.path.exists(data_dir)}")
    logger.info(f"Directorio logs existe: {os.path.exists(logs_dir)}")
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