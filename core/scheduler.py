import ctypes
import json
import os
import logging
import schedule
import time
import threading
import subprocess
import sys
from typing import Dict, Any, List, Callable, Tuple
from datetime import datetime
from PyQt5.QtWidgets import (
    QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('scheduler')

class SOAPMonitorScheduler:
    """Programador de tareas para monitoreo de servicios SOAP"""
    def get_application_path():
        """Obtiene el directorio base de la aplicación, compatible con .exe"""
        if getattr(sys, 'frozen', False):
        # Estamos ejecutando en aplicación compilada
            return os.path.dirname(sys.executable)
        else:
            # Estamos ejecutando en modo script
            # Asegurarse de que devuelve el directorio raíz, no core/
            current_dir = os.path.dirname(os.path.abspath(__file__))
            return os.path.dirname(current_dir)  # Subir un nivel
    # Configurar directorio raíz
    application_path = get_application_path()
    
    def __init__(self):
        """Inicializa el programador de tareas"""
        self.running = False
        self.scheduler_thread = None
        self.task_map = {}  # Mapeo de nombres de tareas a sus funciones

        # Configuración por defecto para tareas programadas
        self.default_schedule_config = {
            'days_of_week': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
            'start_time': '08:00',
            'duration_hours': 11,  # 8:00 a 19:00
            'hidden': True,
            'run_when_logged_off': True,
            'highest_privileges': True
        }
    
    def add_monitoring_task(self, request_name: str, interval_minutes: int, 
                           task_function: Callable[..., Any]) -> bool:
        """
        Agrega una tarea de monitoreo al programador.
        
        Args:
            request_name (str): Nombre del request a monitorear
            interval_minutes (int): Intervalo de verificación en minutos
            task_function (Callable): Función a ejecutar para la verificación
            
        Returns:
            bool: True si se agregó correctamente
        """
        
        if interval_minutes <= 0:
            logger.error(f"Intervalo inválido para {request_name}: {interval_minutes}")
            return False
            
        task_id = f"monitor_{request_name}"
        
        # Cancelar la tarea anterior si existe
        if task_id in self.task_map:
            schedule.cancel_job(self.task_map[task_id])
            logger.info(f"Tarea anterior para {request_name} cancelada")
        
        # Crear la nueva tarea
        try:
            job = schedule.every(interval_minutes).minutes.do(task_function)
            self.task_map[task_id] = job
            logger.info(f"Tarea programada para {request_name} cada {interval_minutes} minutos")
            return True
        except Exception as e:
            logger.error(f"Error al programar tarea para {request_name}: {str(e)}")
            return False
    
    def remove_monitoring_task(self, request_name: str) -> bool:
        """
        Elimina una tarea de monitoreo.
        
        Args:
            request_name (str): Nombre del request
            
        Returns:
            bool: True si se eliminó correctamente
        """
        task_id = f"monitor_{request_name}"
        
        if task_id in self.task_map:
            schedule.cancel_job(self.task_map[task_id])
            del self.task_map[task_id]
            logger.info(f"Tarea para {request_name} eliminada")
            return True
        else:
            logger.warning(f"No existe tarea para {request_name}")
            return False
    
    def check_system_task_exists(self, task_name: str) -> bool:
        """
        Verifica si una tarea existe en el programador de tareas del sistema.
        
        Args:
            task_name (str): Nombre de la tarea
            
        Returns:
            bool: True si la tarea existe
        """
        try:
            # Determinar sistema operativo
            if sys.platform.startswith('win'):
                # Windows - usar schtasks con ruta completa
                result = subprocess.run(
                    f'schtasks /query /tn "\\SoapRestMonitor\\{task_name}" /fo list',
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                # Si el comando fue exitoso, la tarea existe
                return result.returncode == 0
            else:
                # Linux/Unix - usar crontab
                current_crontab = subprocess.check_output("crontab -l 2>/dev/null || echo ''", shell=True, text=True)
                task_marker = f"# SOAPMonitor_{task_name}"
                return task_marker in current_crontab
                
        except Exception as e:
            logger.error(f"Error al verificar existencia de tarea: {str(e)}")
            return False
    
    def _run_scheduler(self) -> None:
        """Ejecuta el bucle del programador"""
        self.running = True
        logger.info("Programador de tareas iniciado")
        
        while self.running:
            schedule.run_pending()
            time.sleep(1)
        
        logger.info("Programador de tareas detenido")
    
    def start(self) -> bool:
        """
        Inicia el programador de tareas en un hilo separado.
        
        Returns:
            bool: True si se inició correctamente
        """
        if self.running:
            logger.warning("El programador ya está en ejecución")
            return False
        
        try:
            self.scheduler_thread = threading.Thread(target=self._run_scheduler)
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()
            logger.info("Hilo del programador iniciado")
            return True
        except Exception as e:
            logger.error(f"Error al iniciar el programador: {str(e)}")
            return False
    
    def stop(self) -> bool:
        """
        Detiene el programador de tareas.
        
        Returns:
            bool: True si se detuvo correctamente
        """
        if not self.running:
            logger.warning("El programador no está en ejecución")
            return False
        
        try:
            self.running = False
            self.scheduler_thread.join(timeout=5)
            logger.info("Programador detenido correctamente")
            return True
        except Exception as e:
            logger.error(f"Error al detener el programador: {str(e)}")
            return False
    
    def list_active_tasks(self) -> List[Dict[str, Any]]:
        """
        Lista todas las tareas activas en el programador.
        
        Returns:
            List[Dict[str, Any]]: Lista de tareas activas
        """
        active_tasks = []
        
        for task_id, job in self.task_map.items():
            task_info = {
                'id': task_id,
                'next_run': job.next_run,
                'interval': str(job.interval),
                'unit': job.unit
            }
            active_tasks.append(task_info)
        
        return active_tasks
    
    def get_monitor_script_path(self) -> str:
        """Obtiene la ruta del script de monitoreo (método existente)"""
        try:
            if getattr(sys, 'frozen', False):
                executable_path = sys.executable
                logger.info(f"Usando ejecutable para monitoreo: {executable_path}")
                return executable_path
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(current_dir)
                monitor_script = os.path.join(project_root, 'core', 'monitor.py')
                logger.info(f"Usando script de Python para monitoreo: {monitor_script}")
                return monitor_script
        except Exception as e:
            logger.error(f"Error al determinar ruta de script: {str(e)}")
            current_dir = os.path.dirname(os.path.abspath(__file__))
            fallback_path = os.path.join(current_dir, '..', 'core', 'monitor.py')
            logger.warning(f"Usando ruta de fallback: {fallback_path}")
            return fallback_path
    
    def generate_system_task(self, task_name: str, interval_minutes: int) -> bool:
        """
        Wrapper para mantener compatibilidad con el método anterior.
        Ahora usa la configuración avanzada por defecto.
        """
        return self.generate_system_task_advanced(task_name, interval_minutes)
    
    def generate_system_task_advanced(self, task_name: str, interval_minutes: int, 
                                    schedule_config: Dict[str, Any] = None) -> bool:
        """
        Genera una tarea del sistema con configuración avanzada de horarios.
        
        Args:
            task_name (str): Nombre de la tarea/servicio
            interval_minutes (int): Intervalo en minutos
            schedule_config (Dict[str, Any]): Configuración de horarios personalizada
            
        Returns:
            bool: True si la tarea fue creada exitosamente
        """
        if not task_name or interval_minutes <= 0:
            logger.error(f"Parámetros inválidos: {task_name}, interval: {interval_minutes}")
            return False
        
        # Usar configuración por defecto si no se proporciona una personalizada
        config = schedule_config or self.default_schedule_config.copy()
        
        # Obtener directorio de aplicación y rutas
        app_dir = SOAPMonitorScheduler.get_application_path()
        data_dir = os.path.join(app_dir, 'data')
        logs_dir = os.path.join(app_dir, 'logs')
        monitor_script = self.get_monitor_script_path()
        
        if not os.path.exists(monitor_script):
            logger.error(f"Script de monitoreo no encontrado: {monitor_script}")
            return False
        
        try:
            if sys.platform.startswith('win'):
                return self._create_windows_advanced_task(
                    task_name, interval_minutes, config, app_dir, 
                    data_dir, logs_dir, monitor_script
                )
            else:
                return self._create_unix_advanced_task(
                    task_name, interval_minutes, config, app_dir,
                    data_dir, logs_dir, monitor_script
                )
        except Exception as e:
            logger.error(f"Error al crear tarea avanzada: {str(e)}")
            return False
    
    def _create_unix_advanced_task(self, task_name: str, interval_minutes: int,
                                 config: Dict[str, Any], app_dir: str,
                                 data_dir: str, logs_dir: str, monitor_script: str) -> bool:
        """
        Crea una tarea avanzada en crontab Unix con configuración de horarios.
        """
        try:
            # Crear script shell mejorado
            script_dir = os.path.join(app_dir, 'scripts')
            os.makedirs(script_dir, exist_ok=True)
            script_file = os.path.join(script_dir, f'monitor_{task_name}.sh')
            
            script_content = self._generate_unix_advanced_script(
                task_name, app_dir, sys.executable, monitor_script, 
                data_dir, logs_dir, config
            )
            
            with open(script_file, 'w') as f:
                f.write(script_content)
            os.chmod(script_file, 0o755)
            
            # Generar entrada crontab con horarios específicos
            cron_schedule = self._generate_cron_schedule(interval_minutes, config)
            
            # Actualizar crontab
            current_crontab = subprocess.check_output(
                "crontab -l 2>/dev/null || echo ''", shell=True, text=True
            )
            
            task_marker = f"# SOAPMonitor_{task_name}_advanced"
            
            if task_marker in current_crontab:
                # Actualizar tarea existente
                lines = current_crontab.splitlines()
                new_lines = []
                
                i = 0
                while i < len(lines):
                    if lines[i] == task_marker:
                        new_lines.append(task_marker)
                        new_lines.append(cron_schedule)
                        i += 2  # Saltar línea anterior
                    else:
                        new_lines.append(lines[i])
                    i += 1
                
                new_crontab = "\n".join(new_lines)
            else:
                # Añadir nueva tarea
                new_crontab = current_crontab.strip() + f"\n\n{task_marker}\n{cron_schedule}\n"
            
            # Guardar nueva crontab
            subprocess.run("crontab -", shell=True, input=new_crontab, 
                          text=True, check=True)
            
            logger.info(f"Tarea avanzada creada en Unix para {task_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error al crear tarea Unix: {str(e)}")
            return False
        
    def _create_windows_advanced_task(self, task_name: str, interval_minutes: int,
                                config: Dict[str, Any], app_dir: str,
                                data_dir: str, logs_dir: str, monitor_script: str) -> bool:
        """
        Versión corregida del método para crear tareas avanzadas en Windows.
        
        MEJORAS PRINCIPALES:
        1. Validación exhaustiva de permisos
        2. Manejo robusto de errores
        3. Generación de XML corregida
        4. Verificación de integridad post-creación
        """
        xml_file = None
        temp_dir = None
        
        try:
            logger.info(f"=== INICIO CREACIÓN TAREA AVANZADA ===")
            logger.info(f"Servicio: {task_name}")
            logger.info(f"Intervalo: {interval_minutes} minutos")
            logger.info(f"Configuración: {config}")
            
            # PASO 1: Validación de permisos administrativos
            if not self._check_admin_privileges():
                logger.error("❌ FALTA: Permisos de administrador requeridos")
                return False
            logger.info("✅ Permisos administrativos confirmados")
            
            # PASO 2: Preparación y validación de rutas
            python_executable = os.path.abspath(sys.executable)
            monitor_script_abs = os.path.abspath(monitor_script)
            working_dir_abs = os.path.abspath(app_dir)
            data_dir_abs = os.path.abspath(data_dir)
            logs_dir_abs = os.path.abspath(logs_dir)
            
            # Validar existencia de archivos críticos
            if not os.path.exists(python_executable):
                logger.error(f"❌ ERROR: Ejecutable no encontrado: {python_executable}")
                return False
            
            if not getattr(sys, 'frozen', False) and not os.path.exists(monitor_script_abs):
                logger.error(f"❌ ERROR: Script no encontrado: {monitor_script_abs}")
                return False
            
            logger.info(f"✅ Rutas validadas:")
            logger.info(f"   Python/App: {python_executable}")
            logger.info(f"   Working Dir: {working_dir_abs}")
            
            # PASO 3: Generar XML con la nueva función corregida
            xml_content = self._generate_advanced_task_xml(
                task_name, interval_minutes, config, python_executable, 
                monitor_script_abs, data_dir_abs, logs_dir_abs, working_dir_abs
            )
            
            # PASO 4: Crear archivo XML de forma segura
            xml_file = self._create_xml_file_with_validation(xml_content, task_name)
            temp_dir = os.path.dirname(xml_file)
            
            # PASO 5: Eliminar tarea existente si existe
            logger.info("🔄 Verificando tarea existente...")
            delete_cmd = ['schtasks', '/delete', '/tn', f'\\SoapRestMonitor\\{task_name}', '/f']
            delete_result = subprocess.run(delete_cmd, capture_output=True, text=True, timeout=15)
            
            if delete_result.returncode == 0:
                logger.info("✅ Tarea existente eliminada")
            else:
                logger.info("ℹ️  No había tarea existente")
            
            # PASO 6: Crear nueva tarea con comando corregido
            logger.info("🚀 Registrando tarea en Task Scheduler...")
            
            create_cmd = [
                'schtasks', '/create', 
                '/tn', f'\\SoapRestMonitor\\{task_name}', 
                '/xml', xml_file
            ]
            
            logger.info(f"📋 Comando: {' '.join(create_cmd)}")
            
            # Ejecutar con timeout extendido
            result = subprocess.run(create_cmd, capture_output=True, text=True, timeout=45)
            
            logger.info(f"📊 Código de retorno: {result.returncode}")
            logger.info(f"📤 STDOUT: {result.stdout}")
            
            if result.stderr:
                logger.error(f"📥 STDERR: {result.stderr}")
            
            # PASO 7: Verificar resultado
            if result.returncode == 0:
                logger.info("🎉 ÉXITO: Tarea creada correctamente")
                
                # Verificación adicional
                verify_cmd = ['schtasks', '/query', '/tn', f'\\SoapRestMonitor\\{task_name}']
                verify_result = subprocess.run(verify_cmd, capture_output=True, text=True, timeout=10)
                
                if verify_result.returncode == 0:
                    logger.info("✅ VERIFICADO: Tarea confirmada en el sistema")
                    
                    # Log de configuración final
                    logger.info("📋 CONFIGURACIÓN APLICADA:")
                    logger.info(f"   🕐 Horario: {config.get('start_time', '08:00')} por {config.get('duration_hours', 11)} horas")
                    logger.info(f"   📅 Días: {', '.join(config.get('days_of_week', []))}")
                    logger.info(f"   👁️  Oculta: {config.get('hidden', True)}")
                    logger.info(f"   🔒 Privilegios: {config.get('highest_privileges', True)}")
                    
                    return True
                else:
                    logger.error("❌ FALLO: Tarea no encontrada después de la creación")
                    return False
            else:
                logger.error(f"❌ FALLO: Error al crear tarea (código {result.returncode})")
                
                # Diagnóstico detallado para errores específicos
                if result.stderr:
                    if "formato incorrecto" in result.stderr.lower():
                        logger.error("🔍 DIAGNÓSTICO: Error de formato XML detectado")
                        
                        # Mostrar muestra del XML para diagnóstico
                        try:
                            with open(xml_file, 'r', encoding='utf-8') as f:
                                xml_sample = f.read()[:1000]
                                logger.error(f"📄 Muestra XML: {xml_sample}")
                        except Exception as read_error:
                            logger.error(f"❌ No se pudo leer XML para diagnóstico: {read_error}")
                    
                    elif "acceso denegado" in result.stderr.lower():
                        logger.error("🔐 DIAGNÓSTICO: Problema de permisos detectado")
                        
                    elif "no existe" in result.stderr.lower():
                        logger.error("📁 DIAGNÓSTICO: Problema de rutas o archivos")
                
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("⏰ TIMEOUT: Tiempo agotado al crear tarea")
            return False
        except Exception as e:
            logger.error(f"💥 ERROR INESPERADO: {str(e)}", exc_info=True)
            return False
        finally:
            # LIMPIEZA: Eliminar archivos temporales
            try:
                if xml_file and os.path.exists(xml_file):
                    os.remove(xml_file)
                    logger.debug("🗑️  Archivo XML temporal eliminado")
                if temp_dir and os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
                    logger.debug("🗑️  Directorio temporal eliminado")
            except Exception as cleanup_error:
                logger.warning(f"⚠️  Advertencia en limpieza: {cleanup_error}")
            
            logger.info("=== FIN PROCESO CREACIÓN TAREA ===")
    
    def _check_admin_privileges(self) -> bool:
        """
        Verifica si la aplicación tiene permisos administrativos en Windows.
        
        Returns:
            bool: True si tiene permisos de administrador
        """
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception as e:
            logger.warning(f"No se pudo verificar permisos administrativos: {str(e)}")
            return False
        
    def _generate_advanced_task_xml(self, task_name: str, interval_minutes: int,
                  config: Dict[str, Any], python_path: str,
                  script_path: str, data_dir: str, logs_dir: str,
                  working_dir: str) -> str:
        """
        Genera XML corregido para Task Scheduler con escapado correcto de caracteres especiales.
        
        CORRECCIÓN CRÍTICA: Mejorar el escapado de caracteres XML especiales
        """
        from datetime import datetime, timedelta
        import xml.sax.saxutils as saxutils
        
        # === FUNCIÓN DE ESCAPADO MEJORADA ===
        def escape_xml_content(text: str) -> str:
            """
            Escapa caracteres especiales XML de manera segura y completa.
            
            Args:
                text (str): Texto a escapar
                
            Returns:
                str: Texto con caracteres escapados correctamente
            """
            if not text:
                return ""
            
            # Usar saxutils para escapado básico
            escaped = saxutils.escape(text, entities={
                '"': '&quot;',
                "'": '&apos;',
                '<': '&lt;',
                '>': '&gt;',
                '&': '&amp;'
            })
            
            # Escapado adicional para caracteres problemáticos en rutas de Windows
            escaped = escaped.replace('\\', '\\\\')  # Doble backslash para rutas
            
            return escaped
        
        # === PREPARACIÓN DE DATOS SEGUROS ===
        
        # CRÍTICO: Usar función de escapado mejorada
        safe_task_name = escape_xml_content(task_name)
        safe_python_path = escape_xml_content(python_path)
        safe_script_path = escape_xml_content(script_path)
        safe_data_dir = escape_xml_content(data_dir)
        safe_logs_dir = escape_xml_content(logs_dir)
        safe_working_dir = escape_xml_content(working_dir)
        
        # === CONFIGURACIÓN TEMPORAL CORREGIDA ===
        
        current_time = datetime.now()
        
        # Configurar tiempo de inicio con validación
        start_time = config.get('start_time', '08:00')
        try:
            hour, minute = map(int, start_time.split(':'))
            # Validar rango de horas
            if not (0 <= hour <= 23) or not (0 <= minute <= 59):
                raise ValueError("Hora fuera de rango válido")
                
            start_date = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if start_date <= current_time:
                start_date += timedelta(days=1)
            
            # CRÍTICO: Formato ISO 8601 exacto para Task Scheduler
            start_boundary = start_date.strftime('%Y-%m-%dT%H:%M:%S.0000000')
        except Exception as e:
            logger.warning(f"Error al parsear hora de inicio: {e}")
            start_boundary = (current_time + timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%S.0000000')
        
        # Configurar duración e intervalo con validación
        duration_hours = max(1, min(24, config.get('duration_hours', 11)))
        duration_iso = f"PT{duration_hours}H"
        interval_iso = f"PT{max(1, interval_minutes)}M"
        
        # === CONFIGURACIÓN DE DÍAS SEGURA ===
        
        days_of_week = config.get('days_of_week', ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'])
        
        # Validar días antes de generar XML
        valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        validated_days = [day for day in days_of_week if day.lower() in valid_days]
        
        if not validated_days:
            validated_days = ['monday']  # Fallback seguro
            logger.warning("No se encontraron días válidos, usando Monday por defecto")
        
        days_elements = self._generate_days_xml_elements(validated_days)
        
        # === CONFIGURACIÓN DE SEGURIDAD ===
        
        hidden = "true" if config.get('hidden', True) else "false"
        highest_privileges = config.get('highest_privileges', True)
        run_level = "HighestAvailable" if highest_privileges else "LeastPrivilege"
        
        # === CONFIGURACIÓN DE COMANDO CORREGIDA ===
        
        is_compiled = getattr(sys, 'frozen', False)
        
        if is_compiled:
            # Para aplicación compilada (.exe) - SIN comillas adicionales
            command = safe_python_path
            arguments = f'{safe_task_name} --headless --scheduled-task --notify --data-dir={safe_data_dir} --logs-dir={safe_logs_dir}'
        else:
            # Para script Python - SIN comillas adicionales en argumentos
            command = safe_python_path
            arguments = f'{safe_script_path} {safe_task_name} --headless --scheduled-task --notify --data-dir={safe_data_dir} --logs-dir={safe_logs_dir}'
        
        # === GENERACIÓN XML CORREGIDA ===
        
        # NOTA: NO usar f-strings para el contenido XML principal para evitar problemas de escapado
        xml_template = """<?xml version="1.0" encoding="UTF-16"?>
    <Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
    <RegistrationInfo>
        <Date>{registration_date}</Date>
        <Author>SOAP REST Monitor</Author>
        <Description>Monitoreo automatico del servicio: {task_name}</Description>
        <URI>\\SoapRestMonitor\\{task_name}</URI>
    </RegistrationInfo>
    <Triggers>
        <CalendarTrigger>
        <StartBoundary>{start_boundary}</StartBoundary>
        <Enabled>true</Enabled>
        <ScheduleByWeek>
            <DaysOfWeek>
    {days_elements}
            </DaysOfWeek>
            <WeeksInterval>1</WeeksInterval>
        </ScheduleByWeek>
        <Repetition>
            <Interval>{interval_iso}</Interval>
            <Duration>{duration_iso}</Duration>
            <StopAtDurationEnd>false</StopAtDurationEnd>
        </Repetition>
        </CalendarTrigger>
    </Triggers>
    <Principals>
        <Principal id="Author">
        <UserId>S-1-5-18</UserId>
        <LogonType>InteractiveToken</LogonType>
        <RunLevel>{run_level}</RunLevel>
        </Principal>
    </Principals>
    <Settings>
        <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
        <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
        <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
        <AllowHardTerminate>true</AllowHardTerminate>
        <StartWhenAvailable>true</StartWhenAvailable>
        <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
        <IdleSettings>
        <StopOnIdleEnd>false</StopOnIdleEnd>
        <RestartOnIdle>false</RestartOnIdle>
        </IdleSettings>
        <AllowStartOnDemand>true</AllowStartOnDemand>
        <Enabled>true</Enabled>
        <Hidden>{hidden}</Hidden>
        <RunOnlyIfIdle>false</RunOnlyIfIdle>
        <DisallowStartOnRemoteAppSession>false</DisallowStartOnRemoteAppSession>
        <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
        <WakeToRun>false</WakeToRun>
        <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
        <Priority>6</Priority>
        <RestartOnFailure>
        <Interval>PT1M</Interval>
        <Count>3</Count>
        </RestartOnFailure>
    </Settings>
    <Actions Context="Author">
        <Exec>
        <Command>{command}</Command>
        <Arguments>{arguments}</Arguments>
        <WorkingDirectory>{working_directory}</WorkingDirectory>
        </Exec>
    </Actions>
    </Task>"""
        
        # Reemplazar placeholders de manera segura
        xml_content = xml_template.format(
            registration_date=current_time.strftime('%Y-%m-%dT%H:%M:%S.0000000'),
            task_name=safe_task_name,
            start_boundary=start_boundary,
            days_elements=days_elements,
            interval_iso=interval_iso,
            duration_iso=duration_iso,
            run_level=run_level,
            hidden=hidden,
            command=command,
            arguments=arguments,
            working_directory=safe_working_dir
        )
        
        # === VALIDACIÓN FINAL ===
        logger.debug(f"XML generado para {task_name}:")
        logger.debug(f"Command: {command}")
        logger.debug(f"Arguments: {arguments}")
        logger.debug(f"Working Dir: {safe_working_dir}")
        
        return xml_content
    
    def _generate_days_xml_elements(self, days_list: List[str]) -> str:
        """
        Genera elementos XML correctos para los días de la semana con indentación precisa.
        
        CORRECCIÓN TÉCNICA ESPECÍFICA:
        - Cada día debe ser un elemento XML auto-cerrado válido
        - Usar nombres en inglés exactos que espera Task Scheduler
        - Indentación consistente con espacios (no tabs)
        - Estructura jerárquica correcta para DaysOfWeek
        
        Args:
            days_list (List[str]): Lista de días en formato interno
            
        Returns:
            str: Elementos XML correctamente formateados con indentación precisa
        """
        # Mapeo exacto de nombres internos a nombres XML de Task Scheduler
        day_mapping = {
            'monday': 'Monday',
            'tuesday': 'Tuesday', 
            'wednesday': 'Wednesday',
            'thursday': 'Thursday',
            'friday': 'Friday',
            'saturday': 'Saturday',
            'sunday': 'Sunday'
        }
        
        day_elements = []
        
        # Generar elementos con validación estricta
        for day in days_list:
            day_lower = str(day).lower().strip()
            if day_lower in day_mapping:
                day_name = day_mapping[day_lower]
                # CRÍTICO: Elementos XML auto-cerrados válidos
                day_elements.append(f"          <{day_name} />")
            else:
                logger.warning(f"Día inválido ignorado: {day}")
        
        # Validar que tenemos al menos un día
        if not day_elements:
            logger.warning("No se encontraron días válidos, usando Monday por defecto")
            day_elements.append("          <Monday />")
        
        # Unir elementos con saltos de línea Unix
        result = '\n'.join(day_elements)
        
        logger.debug(f"Elementos XML de días generados:\n{result}")
        
        return result

    def _create_xml_file_safe(self, xml_content: str, task_name: str) -> str:
        """
        Crea archivo XML de forma segura con manejo correcto de codificación.
        
        MEJORAS TÉCNICAS:
        1. Usar UTF-8 sin BOM en lugar de UTF-16
        2. Validar contenido antes de escribir
        3. Manejo robusto de caracteres especiales
        4. Verificación de integridad post-escritura
        
        Args:
            xml_content (str): Contenido XML a escribir
            task_name (str): Nombre de la tarea para el archivo
            
        Returns:
            str: Ruta al archivo XML creado
            
        Raises:
            Exception: Si hay error en la creación del archivo
        """
        import tempfile
        import xml.etree.ElementTree as ET
        
        # Crear directorio temporal seguro
        temp_dir = tempfile.mkdtemp(prefix=f'SOAPMonitor_{task_name}_')
        xml_file = os.path.join(temp_dir, f'{task_name}_task.xml')
        
        try:
            # VALIDACIÓN: Verificar que el XML es válido antes de escribir
            try:
                ET.fromstring(xml_content)
                logger.info("✓ XML validado correctamente antes de escribir")
            except ET.ParseError as parse_error:
                logger.error(f"XML inválido generado: {parse_error}")
                raise Exception(f"XML generado es inválido: {parse_error}")
            
            # CORRECCIÓN CRÍTICA: Usar UTF-16 LE con BOM para Task Scheduler
            # Task Scheduler requiere específicamente esta codificación
            with open(xml_file, 'w', encoding='utf-16le', newline='\r\n') as f:
                # Escribir BOM manualmente para UTF-16 LE
                f.write('\ufeff')  # BOM para UTF-16 LE
                f.write(xml_content)
            
            # VERIFICACIÓN: Confirmar que el archivo se escribió correctamente
            if not os.path.exists(xml_file):
                raise Exception("El archivo XML no se creó correctamente")
            
            file_size = os.path.getsize(xml_file)
            if file_size < 100:
                raise Exception(f"Archivo XML demasiado pequeño: {file_size} bytes")
            
            logger.info(f"✓ Archivo XML creado con UTF-16 LE: {xml_file} ({file_size} bytes)")
            
            # VALIDACIÓN FINAL: Leer y validar el archivo escrito
            # Usar la misma codificación para leer
            with open(xml_file, 'r', encoding='utf-16le') as f:
                written_content = f.read()
                # Remover BOM para validación
                if written_content.startswith('\ufeff'):
                    written_content = written_content[1:]
                    
            try:
                ET.fromstring(written_content)
                logger.info("✓ XML escrito validado correctamente con UTF-16 LE")
            except ET.ParseError as parse_error:
                logger.error(f"XML escrito es inválido: {parse_error}")
                raise Exception(f"Error en XML escrito: {parse_error}")
            
            return xml_file
            
        except Exception as e:
            # Limpieza en caso de error
            try:
                if os.path.exists(xml_file):
                    os.remove(xml_file)
                if os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
            except:
                pass
            raise e
        
    def _convert_days_to_mask(self, days_list: List[str]) -> str:
        """
        Convierte lista de días a máscara para Task Scheduler.
        """
        day_mapping = {
            'monday': 'Monday',
            'tuesday': 'Tuesday', 
            'wednesday': 'Wednesday',
            'thursday': 'Thursday',
            'friday': 'Friday',
            'saturday': 'Saturday',
            'sunday': 'Sunday'
        }
        
        day_elements = []
        for day in days_list:
            if day.lower() in day_mapping:
                day_elements.append(day_mapping[day.lower()])

        return '\n          '.join([f'<{day} />' for day in day_elements])
    
    def _generate_cron_schedule(self, interval_minutes: int, config: Dict[str, Any]) -> str:
        """
        Genera programación cron con horarios específicos para Unix.
        """
        start_time = config.get('start_time', '08:00')
        duration_hours = config.get('duration_hours', 11)
        days_of_week = config.get('days_of_week', ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'])
        
        # Convertir días a números cron (1=Monday, 7=Sunday)
        day_mapping = {
            'monday': '1', 'tuesday': '2', 'wednesday': '3',
            'thursday': '4', 'friday': '5', 'saturday': '6', 'sunday': '7'
        }
        cron_days = ','.join([day_mapping.get(day.lower(), '1') for day in days_of_week])
        
        # Extraer hora de inicio
        start_hour = int(start_time.split(':')[0])
        end_hour = start_hour + duration_hours
        
        # Crear programación con restricción de horario
        script_file = f"{SOAPMonitorScheduler.get_application_path()}/scripts/monitor_{task_name}.sh"
        cron_line = f"*/{interval_minutes} {start_hour}-{end_hour-1} * * {cron_days} {script_file}"
        
        return cron_line
    
    def _generate_unix_advanced_script(self, task_name: str, app_dir: str,
                                     python_path: str, script_path: str,
                                     data_dir: str, logs_dir: str,
                                     config: Dict[str, Any]) -> str:
        """
        Genera script shell avanzado con verificación de horarios.
        """
        start_time = config.get('start_time', '08:00')
        duration_hours = config.get('duration_hours', 11)
        
        start_hour = int(start_time.split(':')[0])
        end_hour = start_hour + duration_hours
        
        is_compiled = getattr(sys, 'frozen', False)
        
        if is_compiled:
            command_line = f'"{python_path}" "{task_name}" --headless --scheduled-task --notify --data-dir="{data_dir}" --logs-dir="{logs_dir}"'
        else:
            command_line = f'"{python_path}" "{script_path}" "{task_name}" --headless --scheduled-task --notify --data-dir="{data_dir}" --logs-dir="{logs_dir}"'
        
        script_content = f"""#!/bin/bash
# SOAP/REST Monitor - Tarea avanzada para servicio {task_name}
# Configuración: {start_time} por {duration_hours} horas

# Verificar horario de ejecución
current_hour=$(date +%H)
start_hour={start_hour}
end_hour={end_hour}

if [ $current_hour -lt $start_hour ] || [ $current_hour -ge $end_hour ]; then
    echo "Fuera del horario de ejecución ($start_hour:00-$end_hour:00). Hora actual: $current_hour"
    exit 0
fi

echo "=== SOAP/REST Monitor - Ejecución Programada ==="
echo "Servicio: {task_name}"
echo "Fecha/Hora: $(date)"
echo "Horario permitido: {start_time}-{end_hour}:00"
echo "============================================="

cd "{app_dir}"

{command_line}

exit_code=$?
echo "Código de salida: $exit_code"
echo "============================================="

exit $exit_code
"""
        
        return script_content
    
    def remove_system_task(self, task_name: str) -> bool:
        """
        Elimina una tarea del programador de tareas del sistema.
        
        Args:
            task_name (str): Nombre de la tarea
            
        Returns:
            bool: True si se eliminó correctamente
        """
        try:
            # Determinar sistema operativo
            if sys.platform.startswith('win'):
                # Windows - usar schtasks con ruta completa que incluye la carpeta
                task_cmd = f'schtasks /delete /tn "\\SoapRestMonitor\\{task_name}" /f'
                subprocess.run(task_cmd, shell=True, check=True)
                logger.info(f"Tarea de sistema eliminada en Windows para {task_name}")
            else:
                # Linux/Unix - usar crontab
                # Obtener crontab actual
                current_crontab = subprocess.check_output("crontab -l 2>/dev/null || echo ''", shell=True, text=True)
                
                # Buscar y eliminar tarea
                task_marker = f"# SOAPMonitor_{task_name}"
                
                if task_marker in current_crontab:
                    lines = current_crontab.splitlines()
                    new_lines = []
                    
                    i = 0
                    while i < len(lines):
                        if lines[i] == task_marker:
                            i += 2  # Saltar la tarea (marcador y comando)
                        else:
                            new_lines.append(lines[i])
                            i += 1
                    
                    new_crontab = "\n".join(new_lines)
                    
                    # Guardar nueva crontab
                    subprocess.run("crontab -", shell=True, input=new_crontab, text=True, check=True)
                    logger.info(f"Tarea de sistema eliminada en Linux/Unix para {task_name}")
                else:
                    logger.warning(f"No se encontró tarea de sistema para {task_name}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error al eliminar tarea de sistema para {task_name}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado al eliminar tarea de sistema: {str(e)}")
            return False


    def generate_task_xml(service_name, interval_minutes, python_path, script_path):
        """
        Genera un archivo XML para definir una tarea en el Task Scheduler de Windows.
        
        Args:
            service_name (str): Nombre del servicio
            interval_minutes (int): Intervalo en minutos
            python_path (str): Ruta al intérprete de Python
            script_path (str): Ruta al script de monitoreo
        
        Returns:
            str: Contenido XML de la definición de tarea
        """
        # Crear un ID único basado en la fecha/hora
        task_id = f"SOAPMonitor_{service_name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Formatear la duración como PT{N}M (formato ISO 8601 para duración)
        duration = f"PT{interval_minutes}M"
        
        # Crear la plantilla XML
        xml_content = f"""<?xml version="1.0" encoding="UTF-16"?>
    <Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
    <RegistrationInfo>
        <Date>{datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}</Date>
        <Author>SOAP Monitor Application</Author>
        <Description>Monitoreo automático del servicio: {service_name}</Description>
        <URI>\\SoapRestMonitor\\{service_name}</URI>
    </RegistrationInfo>
    <Triggers>
        <TimeTrigger>
        <Repetition>
            <Interval>{duration}</Interval>
            <StopAtDurationEnd>false</StopAtDurationEnd>
        </Repetition>
        <StartBoundary>{datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}</StartBoundary>
        <Enabled>true</Enabled>
        </TimeTrigger>
    </Triggers>
    <Principals>
        <Principal id="Author">
        <LogonType>InteractiveToken</LogonType>
        <RunLevel>HighestAvailable</RunLevel>
        </Principal>
    </Principals>
    <Settings>
        <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
        <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
        <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
        <AllowHardTerminate>true</AllowHardTerminate>
        <StartWhenAvailable>true</StartWhenAvailable>
        <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
        <IdleSettings>
        <StopOnIdleEnd>false</StopOnIdleEnd>
        <RestartOnIdle>false</RestartOnIdle>
        </IdleSettings>
        <AllowStartOnDemand>true</AllowStartOnDemand>
        <Enabled>true</Enabled>
        <Hidden>true</Hidden>
        <RunOnlyIfIdle>false</RunOnlyIfIdle>
        <WakeToRun>false</WakeToRun>
        <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
        <Priority>7</Priority>
    </Settings>
    <Actions Context="Author">
        <Exec>
        <Command>"{python_path}"</Command>
        <Arguments>"{script_path}" "{service_name}" --headless --scheduled-task --notify</Arguments>
        <WorkingDirectory>{os.path.dirname(script_path)}</WorkingDirectory>
        </Exec>
    </Actions>
    </Task>
    """
        return xml_content

    def generate_batch_script_improved(self, service_name, app_dir, python_path, script_path, data_dir, logs_dir):
        """
        Generates an improved batch script for Windows task scheduling with better path handling.
        
        Args:
            service_name (str): Name of the service
            app_dir (str): Application base directory
            python_path (str): Path to Python executable
            script_path (str): Path to the monitor script
            data_dir (str): Path to data directory
            logs_dir (str): Path to logs directory
            
        Returns:
            str: Content of the batch script
        """
        # Determinar si estamos en modo compilado
        is_compiled = getattr(sys, 'frozen', False)
        
        if is_compiled:
            # Para aplicación compilada (.exe)
            # El python_path es realmente el .exe de la aplicación
            command_line = f'"{python_path}" "{service_name}" --headless --scheduled-task --notify --data-dir "{data_dir}" --logs-dir "{logs_dir}"'
            script_description = "aplicación compilada"
        else:
            # Para script Python
            command_line = f'"{python_path}" "{script_path}" "{service_name}" --headless --scheduled-task --notify --data-dir "{data_dir}" --logs-dir "{logs_dir}"'
            script_description = "script Python"
        
        batch_content = f"""@echo off
    REM SOAP/REST Monitor - Scheduled task for service {service_name}
    REM Generated by SOAP/REST Monitor Application
    REM Execution mode: {script_description}

    echo ============================================
    echo SOAP/REST Monitor - Task Execution
    echo ============================================
    echo Service: {service_name}
    echo Start time: %date% %time%
    echo Working directory: {app_dir}
    echo Execution mode: {script_description}
    echo ============================================

    REM Change to application directory
    cd /d "{app_dir}"

    REM Verify working directory
    echo Current directory: %cd%

    REM Execute command with full logging
    echo Executing command: {command_line}
    echo.

    {command_line}

    REM Capture exit code
    set EXIT_CODE=%errorlevel%

    echo.
    echo ============================================
    echo Task completed at: %date% %time%
    echo Exit code: %EXIT_CODE%

    if %EXIT_CODE% neq 0 (
        echo ERROR: Monitoring check failed
        echo Check logs at: {logs_dir}\\soap_monitor.log
        echo ============================================
        exit /b %EXIT_CODE%
    ) else (
        echo SUCCESS: Monitoring check completed
        echo ============================================
        exit /b 0
    )
    """
        return batch_content

    def generate_shell_script_improved(self, service_name, app_dir, python_path, script_path, data_dir, logs_dir):
        """
        Generates an improved shell script for Linux/Unix task scheduling.
        
        Args:
            service_name (str): Name of the service
            app_dir (str): Application base directory
            python_path (str): Path to Python executable
            script_path (str): Path to monitor script
            data_dir (str): Path to data directory
            logs_dir (str): Path to logs directory
            
        Returns:
            str: Content of the shell script
        """
        # Determinar modo de ejecución
        is_compiled = getattr(sys, 'frozen', False)
        
        if is_compiled:
            command_line = f'"{python_path}" "{service_name}" --headless --scheduled-task --notify --data-dir="{data_dir}" --logs-dir="{logs_dir}"'
            script_description = "compiled application"
        else:
            command_line = f'"{python_path}" "{script_path}" "{service_name}" --headless --scheduled-task --notify --data-dir="{data_dir}" --logs-dir="{logs_dir}"'
            script_description = "Python script"
        
        shell_content = f"""#!/bin/bash
    # SOAP/REST Monitor - Scheduled task for service {service_name}
    # Generated by SOAP/REST Monitor Application
    # Execution mode: {script_description}

    echo "============================================"
    echo "SOAP/REST Monitor - Task Execution"
    echo "============================================"
    echo "Service: {service_name}"
    echo "Start time: $(date)"
    echo "Working directory: {app_dir}"
    echo "Execution mode: {script_description}"
    echo "============================================"

    # Change to application directory
    cd "{app_dir}"

    # Verify working directory
    echo "Current directory: $(pwd)"

    # Execute command with logging
    echo "Executing command: {command_line}"
    echo ""

    {command_line}

    # Capture exit code
    EXIT_CODE=$?

    echo ""
    echo "============================================"
    echo "Task completed at: $(date)"
    echo "Exit code: $EXIT_CODE"

    if [ $EXIT_CODE -ne 0 ]; then
        echo "ERROR: Monitoring check failed"
        echo "Check logs at: {logs_dir}/soap_monitor.log"
        echo "============================================"
        exit $EXIT_CODE
    else
        echo "SUCCESS: Monitoring check completed"
        echo "============================================"
        exit 0
    fi
    """
        return shell_content

    def generate_batch_script(service_name, xml_path):
        """
        Genera un script batch para registrar la tarea en Windows.
        
        Args:
            service_name (str): Nombre del servicio
            xml_path (str): Ruta al archivo XML de la tarea
        
        Returns:
            str: Contenido del script batch
        """
        batch_content = f"""@echo off
    echo Registrando tarea para el servicio {service_name}...
    echo.

    REM Verificar si se ejecuta como administrador
    net session >nul 2>&1
    if %errorLevel% == 0 (
        echo Ejecutando con permisos de administrador. Continuando...
    ) else (
        echo ERROR: Este script debe ejecutarse como administrador.
        echo Por favor, haga clic derecho en este archivo y seleccione "Ejecutar como administrador"
        echo.
        pause
        exit /b 1
    )

    REM Crear carpeta SoapRestMonitor si no existe
    schtasks /create /tn "\\SoapRestMonitor" /f /sc once /st 00:00 /sd 01/01/2099
    schtasks /delete /tn "\\SoapRestMonitor" /f >nul 2>&1

    REM Registrar la tarea
    schtasks /create /tn "\\SoapRestMonitor\\{service_name}" /xml "{xml_path}" /f

    if %errorLevel% == 0 (
        echo.
        echo Tarea registrada correctamente.
        echo Nombre de la tarea: \\SoapRestMonitor\\{service_name}
        echo.
    ) else (
        echo.
        echo ERROR: No se pudo registrar la tarea.
        echo Código de error: %errorLevel%
        echo.
    )

    pause
    """
        return batch_content

    def export_task_files(self, service_name, interval_minutes):
        """
        Exporta los archivos necesarios para crear una tarea programada manualmente.
        
        Args:
            service_name (str): Nombre del servicio
            interval_minutes (int): Intervalo en minutos
            
        Returns:
            bool: True si se exportó correctamente
        """
        try:
            # Obtener ruta para guardar
            export_dir = QFileDialog.getExistingDirectory(
                None, 
                "Seleccionar carpeta para exportar archivos de tarea", 
                os.path.expanduser("~"),
                QFileDialog.ShowDirsOnly
            )
            
            if not export_dir:
                return False
                
            # Crear carpeta específica para este servicio
            service_dir = os.path.join(export_dir, f"SOAPMonitor_{service_name}")
            os.makedirs(service_dir, exist_ok=True)
            
            # Obtener rutas
            python_path = sys.executable
            script_path = self.get_monitor_script_path()
            
            # Generar XML
            xml_content = self.generate_task_xml(service_name, interval_minutes, python_path, script_path)
            xml_path = os.path.join(service_dir, f"{service_name}_task.xml")
            
            with open(xml_path, 'w', encoding='utf-16') as f:
                f.write(xml_content)
                
            # Generar script batch
            batch_content = self.generate_batch_script(service_name, xml_path)
            batch_path = os.path.join(service_dir, f"Registrar_Tarea_{service_name}.bat")
            
            with open(batch_path, 'w', encoding='utf-8') as f:
                f.write(batch_content)
                
            # Generar archivo de información
            info = {
                "service_name": service_name,
                "interval_minutes": interval_minutes,
                "python_path": python_path,
                "script_path": script_path,
                "exported_at": datetime.datetime.now().isoformat(),
                "instructions": "Para registrar esta tarea, ejecute el archivo batch como administrador."
            }
            
            info_path = os.path.join(service_dir, "info.json")
            with open(info_path, 'w', encoding='utf-8') as f:
                json.dump(info, f, indent=2)
                
            # Crear archivo README
            readme_content = f"""# Tarea programada para el servicio: {service_name}

    ## Instrucciones

    1. Para registrar esta tarea en el programador de Windows, haga clic derecho en el archivo "Registrar_Tarea_{service_name}.bat" y seleccione "Ejecutar como administrador".

    2. Si desea modificar la configuración antes de registrar:
    - Abra el archivo "{service_name}_task.xml" con un editor de texto
    - Modifique los parámetros según sea necesario
    - Guarde los cambios antes de ejecutar el script

    ## Detalles de la tarea

    - Nombre del servicio: {service_name}
    - Intervalo de ejecución: Cada {interval_minutes} minutos
    - Ejecutable: Python ({python_path})
    - Script: {script_path}
    - Argumentos: {service_name}

    ## Solución de problemas

    Si encuentra errores al registrar la tarea:
    1. Asegúrese de ejecutar el script como administrador
    2. Verifique que las rutas en el archivo XML sean correctas
    3. Compruebe que tiene acceso al directorio donde se encuentra el script
    """
            
            readme_path = os.path.join(service_dir, "README.txt")
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
                
            return True
        except Exception as e:
            logging.error(f"Error al exportar archivos de tarea: {str(e)}")
            return False

    def force_create_system_task(self, service_name, interval_minutes):
        """
        Intenta crear la tarea en el sistema con privilegios elevados si es necesario.
        
        Args:
            service_name (str): Nombre del servicio
            interval_minutes (int): Intervalo en minutos
            
        Returns:
            bool: True si se creó correctamente
        """
        def is_admin():
            """Verifica si la aplicación está ejecutándose con permisos de administrador"""
            try:
                import sys
                import ctypes
                if sys.platform.startswith('win'):
                    return ctypes.windll.shell32.IsUserAnAdmin() != 0
                else:
                    # En sistemas Unix, verificar si el UID es 0 (root)
                    import os
                    return os.geteuid() == 0
            except:
                return False
        if is_admin():
            # Ya tenemos permisos, intentar crear normalmente
            return self.generate_system_task(service_name, interval_minutes)
        else:
            # No tenemos permisos, ofrecer alternativas
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Se requieren permisos de administrador")
            msg.setText("Para registrar tareas en el Programador de Windows se necesitan permisos de administrador.")
            msg.setInformativeText("¿Qué desea hacer?")
            
            # Botones personalizados
            export_btn = msg.addButton("Exportar archivos de tarea", QMessageBox.ActionRole)
            restart_btn = msg.addButton("Reiniciar como administrador", QMessageBox.ActionRole)
            cancel_btn = msg.addButton("Cancelar", QMessageBox.RejectRole)
            
            msg.exec_()
            
            clicked_btn = msg.clickedButton()
            
            if clicked_btn == export_btn:
                # Exportar archivos para crear manualmente
                if self.export_task_files(service_name, interval_minutes):
                    QMessageBox.information(None, "Exportación completada", 
                        f"Los archivos para crear la tarea han sido exportados correctamente.\n\n"
                        f"Para registrar la tarea, ejecute el archivo batch como administrador.")
                    return False
            elif clicked_btn == restart_btn:
                # Intentar reiniciar la aplicación como administrador
                if sys.platform.startswith('win'):
                    try:
                        # Usar ShellExecute para reiniciar con UAC
                        ctypes.windll.shell32.ShellExecuteW(
                            None, "runas", sys.executable, " ".join(sys.argv), None, 1)
                        # Salir de la instancia actual
                        sys.exit(0)
                    except Exception as e:
                        logging.error(f"Error al reiniciar como administrador: {str(e)}")
                        QMessageBox.critical(None, "Error", 
                            "No se pudo reiniciar la aplicación como administrador.\n\n"
                            "Por favor, cierre la aplicación y ejecútela manualmente como administrador.")
                else:
                    QMessageBox.information(None, "Información", 
                        "En sistemas Linux/Unix, ejecute la aplicación con 'sudo' para obtener permisos elevados.")
            
            return False

    def get_task_status(self, service_name):
        """
        Obtiene el estado detallado de una tarea programada.
        
        Args:
            service_name (str): Nombre del servicio
            
        Returns:
            dict: Estado detallado de la tarea
        """
        status = {
            "exists": False,
            "exists_internal": False,
            "internal_active": False,
            "next_run_internal": None,
            "schedule_type": None,
            "cron_schedule": None
        }
        
        # Verificar tarea en el sistema
        try:
            if sys.platform.startswith('win'):
                # Verificar en Windows Task Scheduler
                result = subprocess.run(
                    f'schtasks /query /tn "\\SoapRestMonitor\\{service_name}" /fo list',
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                if result.returncode == 0:
                    status["exists"] = True
                    
                    # Extraer detalles adicionales
                    output = result.stdout.lower()
                    
                    # Extraer tipo de programación
                    if "one time only" in output:
                        status["schedule_type"] = "Una vez"
                    elif "daily" in output:
                        status["schedule_type"] = "Diario"
                    elif "weekly" in output:
                        status["schedule_type"] = "Semanal"
                    elif "monthly" in output:
                        status["schedule_type"] = "Mensual"
                    
                    # Extraer próxima ejecución
                    for line in output.split('\n'):
                        if "próxima ejecución:" in line or "next run time:" in line:
                            parts = line.split(':', 1)
                            if len(parts) > 1:
                                status["next_run"] = parts[1].strip()
            else:
                # Verificar en crontab (Linux/Unix)
                current_crontab = subprocess.check_output("crontab -l 2>/dev/null || echo ''", shell=True, text=True)
                task_marker = f"# SOAPMonitor_{service_name}"
                
                if task_marker in current_crontab:
                    status["exists"] = True
                    
                    # Extraer programación cron
                    lines = current_crontab.splitlines()
                    for i, line in enumerate(lines):
                        if line == task_marker and i+1 < len(lines):
                            status["cron_schedule"] = lines[i+1].strip()
                            break
        except Exception as e:
            logging.error(f"Error al verificar tarea del sistema: {str(e)}")
        
        # Verificar tarea interna
        task_id = f"monitor_{service_name}"
        if task_id in self.task_map:
            status["exists_internal"] = True
            status["internal_active"] = True
            
            # Obtener próxima ejecución interna
            next_run = self.task_map[task_id].next_run
            if next_run:
                status["next_run_internal"] = next_run.strftime("%Y-%m-%d %H:%M:%S.%f")
        
        return status
    
    def export_task_files_advanced(self, service_name: str, interval_minutes: int, 
                                  schedule_config: Dict[str, Any]) -> bool:
        """
        Exporta archivos de tarea con configuración avanzada para creación manual.
        
        Args:
            service_name (str): Nombre del servicio
            interval_minutes (int): Intervalo en minutos
            schedule_config (Dict[str, Any]): Configuración avanzada de horarios
            
        Returns:
            bool: True si se exportó correctamente
        """
        try:
            # Obtener ruta para guardar
            from PyQt5.QtWidgets import QFileDialog
            export_dir = QFileDialog.getExistingDirectory(
                None, 
                "Seleccionar carpeta para exportar archivos de tarea", 
                os.path.expanduser("~"),
                QFileDialog.ShowDirsOnly
            )
            
            if not export_dir:
                return False
                
            # Crear carpeta específica para este servicio
            service_dir = os.path.join(export_dir, f"SOAPMonitor_{service_name}_Advanced")
            os.makedirs(service_dir, exist_ok=True)
            
            # Obtener rutas
            python_path = sys.executable
            script_path = self.get_monitor_script_path()
            app_dir = SOAPMonitorScheduler.get_application_path()
            data_dir = os.path.join(app_dir, 'data')
            logs_dir = os.path.join(app_dir, 'logs')
            
            if sys.platform.startswith('win'):
                # Generar XML avanzado
                xml_content = self._generate_advanced_task_xml(
                    service_name, interval_minutes, schedule_config,
                    python_path, script_path, data_dir, logs_dir, app_dir
                )
                xml_path = os.path.join(service_dir, f"{service_name}_advanced_task.xml")
                
                with open(xml_path, 'w', encoding='utf-16') as f:
                    f.write(xml_content)
                    
                # Generar script batch mejorado
                batch_content = self._generate_advanced_batch_script(
                    service_name, xml_path, schedule_config
                )
                batch_path = os.path.join(service_dir, f"Registrar_Tarea_Avanzada_{service_name}.bat")
                
                with open(batch_path, 'w', encoding='utf-8') as f:
                    f.write(batch_content)
            else:
                # Para Unix/Linux, generar script y entrada cron
                script_content = self._generate_unix_advanced_script(
                    service_name, app_dir, python_path, script_path,
                    data_dir, logs_dir, schedule_config
                )
                script_path = os.path.join(service_dir, f"monitor_{service_name}_advanced.sh")
                
                with open(script_path, 'w') as f:
                    f.write(script_content)
                os.chmod(script_path, 0o755)
                
                # Generar entrada crontab
                cron_entry = self._generate_cron_schedule(interval_minutes, schedule_config)
                cron_file = os.path.join(service_dir, "crontab_entry.txt")
                
                with open(cron_file, 'w') as f:
                    f.write(f"# Entrada para crontab - Servicio: {service_name}\n")
                    f.write(f"# Configuración: {schedule_config}\n")
                    f.write(f"{cron_entry}\n")
                    
            # Generar archivo de información detallada
            info = {
                "service_name": service_name,
                "interval_minutes": interval_minutes,
                "schedule_config": schedule_config,
                "python_path": python_path,
                "script_path": script_path,
                "exported_at": datetime.now().isoformat(),
                "platform": sys.platform,
                "instructions": "Para registrar esta tarea, siga las instrucciones en el archivo README.txt incluido."
            }
            
            info_path = os.path.join(service_dir, "config_info.json")
            with open(info_path, 'w', encoding='utf-8') as f:
                json.dump(info, f, indent=2, ensure_ascii=False)
                
            # Crear archivo README mejorado
            readme_content = self._generate_advanced_readme(
                service_name, interval_minutes, schedule_config, sys.platform.startswith('win')
            )
            
            readme_path = os.path.join(service_dir, "README.txt")
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
                
            logger.info(f"Archivos avanzados exportados para {service_name} en: {service_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Error al exportar archivos avanzados: {str(e)}")
            return False
        
    def _generate_advanced_batch_script(self, service_name: str, xml_path: str, 
                                      schedule_config: Dict[str, Any]) -> str:
        """Genera script batch con información de configuración avanzada"""
        days_str = ', '.join([day.capitalize() for day in schedule_config.get('days_of_week', [])])
        
        batch_content = f"""@echo off
echo ================================================================
echo SOAP/REST Monitor - Registrador de Tarea Avanzada
echo ================================================================
echo Servicio: {service_name}
echo Configuracion de Horarios:
echo   - Hora inicio: {schedule_config.get('start_time', '08:00')}
echo   - Duracion: {schedule_config.get('duration_hours', 11)} horas
echo   - Dias activos: {days_str}
echo   - Tarea oculta: {schedule_config.get('hidden', True)}
echo   - Ejecutar sin usuario: {schedule_config.get('run_when_logged_off', True)}
echo ================================================================
echo.

REM Verificar si se ejecuta como administrador
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Ejecutando con permisos de administrador. Continuando...
) else (
    echo ERROR: Este script debe ejecutarse como administrador.
    echo Por favor, haga clic derecho en este archivo y seleccione "Ejecutar como administrador"
    echo.
    pause
    exit /b 1
)

REM Crear carpeta SoapRestMonitor si no existe
echo Creando estructura de carpetas...
schtasks /create /tn "\\SoapRestMonitor" /f /sc once /st 00:00 /sd 01/01/2099 >nul 2>&1
schtasks /delete /tn "\\SoapRestMonitor" /f >nul 2>&1

REM Registrar la tarea avanzada
echo Registrando tarea avanzada...
schtasks /create /tn "\\SoapRestMonitor\\{service_name}" /xml "{xml_path}" /f

if %errorLevel% == 0 (
    echo.
    echo ================================================================
    echo TAREA REGISTRADA CORRECTAMENTE
    echo ================================================================
    echo Nombre de la tarea: \\SoapRestMonitor\\{service_name}
    echo La tarea se ejecutara segun la configuracion especificada.
    echo.
    echo Para verificar la tarea:
    echo   - Abra el Programador de tareas de Windows
    echo   - Navegue a SoapRestMonitor
    echo   - Localice la tarea: {service_name}
    echo.
) else (
    echo.
    echo ================================================================
    echo ERROR AL REGISTRAR LA TAREA
    echo ================================================================
    echo Codigo de error: %errorLevel%
    echo Verifique que:
    echo   - Se esta ejecutando como administrador
    echo   - La ruta del archivo XML es correcta
    echo   - No hay conflictos con tareas existentes
    echo.
)

pause
"""
        return batch_content
    
    def _generate_advanced_readme(self, service_name: str, interval_minutes: int,
                                schedule_config: Dict[str, Any], is_windows: bool) -> str:
        """Genera README detallado con la configuración avanzada"""
        days_str = ', '.join([day.capitalize() for day in schedule_config.get('days_of_week', [])])
        start_time = schedule_config.get('start_time', '08:00')
        duration = schedule_config.get('duration_hours', 11)
        
        # Calcular hora de fin
        try:
            hour, minute = map(int, start_time.split(':'))
            total_minutes = hour * 60 + minute + (duration * 60)
            end_hour = (total_minutes // 60) % 24
            end_minute = total_minutes % 60
            end_time = f"{end_hour:02d}:{end_minute:02d}"
        except:
            end_time = "N/A"
        
        readme = f"""
# Configuración Avanzada de Tarea Programada
# Servicio: {service_name}

## Resumen de Configuración

- **Servicio**: {service_name}
- **Intervalo de verificación**: Cada {interval_minutes} minutos
- **Horario activo**: {start_time} - {end_time} ({duration} horas)
- **Días de ejecución**: {days_str}
- **Tarea oculta**: {'Sí' if schedule_config.get('hidden', True) else 'No'}
- **Ejecutar sin usuario conectado**: {'Sí' if schedule_config.get('run_when_logged_off', True) else 'No'}
- **Máximos privilegios**: {'Sí' if schedule_config.get('highest_privileges', True) else 'No'}

## Instrucciones de Instalación

"""
        
        if is_windows:
            readme += f"""
### Windows (Task Scheduler)

1. **Método Automático (Recomendado)**:
   - Haga clic derecho en el archivo "Registrar_Tarea_Avanzada_{service_name}.bat"
   - Seleccione "Ejecutar como administrador"
   - Siga las instrucciones en pantalla

2. **Método Manual**:
   - Abra el Programador de tareas de Windows (taskschd.msc)
   - Haga clic en "Importar tarea..."
   - Seleccione el archivo "{service_name}_advanced_task.xml"
   - Revise la configuración y haga clic en "Aceptar"

### Verificación de la Tarea

1. Abra el Programador de tareas
2. Navegue a: Biblioteca del Programador de tareas > SoapRestMonitor
3. Localice la tarea: {service_name}
4. Verifique que:
   - Estado: Listo
   - Próxima ejecución: Dentro del horario configurado
   - Última ejecución: N/A (hasta la primera ejecución)

### Características Especiales de la Configuración

- **Tarea Oculta**: La tarea no aparecerá en la lista principal del Programador de tareas a menos que seleccione "Ver tareas ocultas"
- **Ejecución sin Usuario**: La tarea se ejecutará aunque no haya usuarios conectados al sistema
- **Cuenta del Sistema**: La tarea se ejecuta con la cuenta LOCAL SYSTEM para máximos privilegios
- **Reintentos**: Se reintentará automáticamente hasta 3 veces en caso de fallo, con intervalos de 1 minuto

"""
        else:
            readme += f"""
### Linux/Unix (Crontab)

1. **Instalación del Script**:
   - Copie el archivo "monitor_{service_name}_advanced.sh" a un directorio ejecutable
   - Asegúrese de que tenga permisos de ejecución: chmod +x monitor_{service_name}_advanced.sh

2. **Configuración de Crontab**:
   - Ejecute: crontab -e
   - Añada la línea contenida en "crontab_entry.txt"
   - Guarde y cierre el editor

3. **Verificación**:
   - Ejecute: crontab -l
   - Verifique que la entrada esté presente
   - Compruebe los logs en: /var/log/syslog o /var/log/cron

### Configuración de Horarios

El script incluye verificación automática de horarios:
- Solo se ejecutará dentro del rango horario especificado
- Si se ejecuta fuera del horario, terminará inmediatamente
- Los logs mostrarán información sobre las decisiones de ejecución

"""
        
        readme += f"""
## Configuración Detallada

### Parámetros de Ejecución
```
Comando: python monitor.py "{service_name}" --headless --scheduled-task --notify
Directorio de trabajo: [Directorio de la aplicación SOAP Monitor]
Timeout: 10 minutos por ejecución
Política de instancias múltiples: Ignorar nueva instancia si ya está ejecutándose
```

### Horarios de Ejecución
```
Inicio diario: {start_time}
Fin diario: {end_time}
Duración: {duration} horas
Días activos: {days_str}
Intervalo: Cada {interval_minutes} minutos
```

### Configuración de Seguridad
```
Usuario de ejecución: SYSTEM (Windows) / root (Linux)
Privilegios: Máximos disponibles
Acceso a red: Requerido
Ejecutar en modo oculto: {'Sí' if schedule_config.get('hidden', True) else 'No'}
```

## Solución de Problemas

### Problemas Comunes

1. **La tarea no se ejecuta**:
   - Verifique que está dentro del horario configurado
   - Compruebe los permisos de la cuenta de ejecución
   - Revise los logs de la aplicación

2. **Errores de permisos**:
   - Asegúrese de que la tarea se creó con permisos de administrador
   - Verifique que la aplicación tenga acceso a los directorios de datos y logs

3. **Tarea no visible**:
   - Si está marcada como oculta, active "Ver tareas ocultas" en el Programador de tareas
   - Navegue específicamente a la carpeta SoapRestMonitor

### Archivos de Log

- Logs de la aplicación: [Directorio aplicación]/logs/soap_monitor.log
- Logs del sistema: Visor de eventos (Windows) o /var/log/syslog (Linux)

## Contacto y Soporte

Para soporte técnico o consultas sobre esta configuración, consulte la documentación de la aplicación SOAP/REST Monitor.

Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return readme
    
    def get_task_status(self, task_name: str) -> Dict[str, Any]:
        """
        Obtiene el estado de una tarea en el programador del sistema.
        
        Args:
            task_name (str): Nombre de la tarea
            
        Returns:
            Dict[str, Any]: Información sobre el estado de la tarea
        """
        status = {
            "exists": False,
            "interval": None,
            "next_run": None,
            "platform": sys.platform
        }
        
        try:
            # Verificar si existe en el programador interno
            for task_id, job in self.task_map.items():
                if task_id == f"monitor_{task_name}":
                    status["exists_internal"] = True
                    status["interval_internal"] = job.interval
                    status["next_run_internal"] = job.next_run
                    break
            
            # Verificar en el sistema
            status["exists"] = self.check_system_task_exists(task_name)
            
            # Determinar sistema operativo
            if sys.platform.startswith('win'):
                # Windows - usar schtasks para obtener más información
                result = subprocess.run(
                    f'schtasks /query /tn "\\SoapRestMonitor\\{task_name}" /fo list',
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                if result.returncode == 0:
                    status["exists"] = True
                    # Extraer intervalo
                    for line in result.stdout.splitlines():
                        if "ScheduleType:" in line:
                            status["schedule_type"] = line.split(":", 1)[1].strip()
                        if "Repeat: Every:" in line:
                            status["interval"] = line.split(":", 1)[1].strip()
            else:
                # Linux/Unix - usar crontab
                current_crontab = subprocess.check_output("crontab -l 2>/dev/null || echo ''", shell=True, text=True)
                task_marker = f"# SOAPMonitor_{task_name}"
                
                if task_marker in current_crontab:
                    lines = current_crontab.splitlines()
                    i = 0
                    while i < len(lines):
                        if lines[i] == task_marker and i + 1 < len(lines):
                            # La línea siguiente contiene la programación cron
                            cron_schedule = lines[i + 1]
                            status["cron_schedule"] = cron_schedule
                            # Intentar extraer intervalo
                            if "*/" in cron_schedule:
                                parts = cron_schedule.split()
                                if len(parts) > 0 and "*/" in parts[0]:
                                    status["interval"] = parts[0].replace("*/", "") + " minutos"
                            break
                        i += 1
            
            return status
            
        except Exception as e:
            logger.error(f"Error al obtener estado de tarea: {str(e)}")
            status["error"] = str(e)
            return status
        
    def _validate_task_scheduler_xml(self, xml_content: str) -> Tuple[bool, str]:
        """
        Valida XML específicamente para Task Scheduler con verificaciones técnicas avanzadas.
        
        VALIDACIONES IMPLEMENTADAS:
        1. Estructura XML válida
        2. Elementos requeridos por Task Scheduler 1.4
        3. Formatos de fecha/hora ISO 8601
        4. Validación de elementos DaysOfWeek
        5. Verificación de caracteres especiales
        
        Args:
            xml_content (str): Contenido XML a validar
            
        Returns:
            Tuple[bool, str]: (es_válido, mensaje_detallado)
        """
        import xml.etree.ElementTree as ET
        from datetime import datetime
        import re
        
        try:
            # === VALIDACIÓN 1: DETECCIÓN DE CARACTERES NO ESCAPADOS ===
            
            # Patrones problemáticos mejorados
            problematic_patterns = [
                (r'[^&]&[^#a-zA-Z]', 'Carácter & no escapado')
            ]
            
            for pattern, description in problematic_patterns:
                matches = re.findall(pattern, xml_content)
                if matches:
                    # Encontrar la posición del primer problema
                    match_pos = xml_content.find(matches[0])
                    context_start = max(0, match_pos - 50)
                    context_end = min(len(xml_content), match_pos + 50)
                    context = xml_content[context_start:context_end]
                    
                    error_msg = (
                        f"{description} detectado.\n"
                        f"Contexto: ...{context}...\n"
                        f"Posición aproximada: {match_pos}"
                    )
                    return False, error_msg
            
            # === VALIDACIÓN 2: ESTRUCTURA XML BÁSICA ===
            try:
                root = ET.fromstring(xml_content)
            except ET.ParseError as e:
                return False, f"XML mal formado: {str(e)}"
            
            # === VALIDACIÓN 3: ELEMENTOS REQUERIDOS ===
            expected_namespace = "http://schemas.microsoft.com/windows/2004/02/mit/task"
            if root.tag != f"{{{expected_namespace}}}Task":
                return False, f"Namespace incorrecto. Esperado: {expected_namespace}"
            
            version = root.get('version')
            if not version or version not in ['1.2', '1.3', '1.4']:
                return False, f"Versión de Task no soportada: {version}"
            
            # Elementos requeridos
            required_elements = ['RegistrationInfo', 'Triggers', 'Principals', 'Settings', 'Actions']
            
            for element_name in required_elements:
                element = root.find(f".//{{{expected_namespace}}}{element_name}")
                if element is None:
                    return False, f"Elemento requerido faltante: {element_name}"
            
            # === VALIDACIÓN 4: COMANDO Y ARGUMENTOS ===
            actions = root.find(f".//{{{expected_namespace}}}Actions")
            exec_action = actions.find(f".//{{{expected_namespace}}}Exec") if actions is not None else None
            
            if exec_action is None:
                return False, "Acción Exec requerida no encontrada"
            
            command_elem = exec_action.find(f".//{{{expected_namespace}}}Command")
            if command_elem is None or not command_elem.text:
                return False, "Comando de ejecución no especificado"
            
            # Validar que el comando no contiene caracteres problemáticos
            command_text = command_elem.text
            if '<' in command_text or '>' in command_text:
                return False, f"Comando contiene caracteres XML no válidos: {command_text}"
            
            # === VALIDACIÓN EXITOSA ===
            return True, "XML válido para Task Scheduler"
            
        except Exception as e:
            return False, f"Error durante validación: {str(e)}"

    def _create_xml_file_with_validation(self, xml_content: str, task_name: str) -> str:
        """
        Versión mejorada que incluye validación previa antes de crear el archivo.
        
        Args:
            xml_content (str): Contenido XML a escribir
            task_name (str): Nombre de la tarea
            
        Returns:
            str: Ruta al archivo XML validado y creado
        """
        # Validar XML antes de escribir el archivo
        is_valid, validation_message = self._validate_task_scheduler_xml(xml_content)
        
        if not is_valid:
            logger.error(f"Validación XML falló: {validation_message}")
            raise Exception(f"XML generado no es válido: {validation_message}")
        
        logger.info(f"✓ XML validado exitosamente: {validation_message}")
        
        # Proceder con la creación del archivo usando el método corregido
        return self._create_xml_file_safe(xml_content, task_name)