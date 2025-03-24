import os
import logging
import schedule
import time
import threading
import subprocess
import sys
from typing import Dict, Any, List, Callable
from datetime import datetime
from PyQt5.QtWidgets import (
    QPushButton, QFileDialog, QMessageBox, QDialog, QVBoxLayout, 
    QLabel, QCheckBox, QDialogButtonBox, QHBoxLayout
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
    
    def __init__(self):
        """Inicializa el programador de tareas"""
        self.running = False
        self.scheduler_thread = None
        self.task_map = {}  # Mapeo de nombres de tareas a sus funciones
    
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
                # Windows - usar schtasks
                result = subprocess.run(
                    f'schtasks /query /tn "SOAPMonitor_{task_name}" /fo list',
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
        """
        Obtiene la ruta del script de monitoreo para el programador de tareas.
        
        Returns:
            str: Ruta completa al script
        """
        # Obtener la ruta del directorio actual
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Subir un nivel para llegar al directorio raíz del proyecto
        project_root = os.path.dirname(current_dir)
        
        # Construir la ruta al script de monitoreo
        monitor_script = os.path.join(project_root,'core', 'monitor.py')
        
        return monitor_script
    
    def generate_system_task(self, task_name: str, interval_minutes: int) -> bool:
        """
        Genera una tarea en el programador de tareas del sistema.
        
        Args:
            task_name (str): Nombre de la tarea
            interval_minutes (int): Intervalo en minutos
            
        Returns:
            bool: True si se generó correctamente
        """
        if not task_name or interval_minutes <= 0:
            logger.error(f"Parámetros inválidos para tarea: {task_name}, intervalo: {interval_minutes}")
            return False
            
        monitor_script = self.get_monitor_script_path()
        
        if not os.path.exists(monitor_script):
            logger.error(f"Script de monitoreo no encontrado: {monitor_script}")
            return False
        
        try:
            # Comando Python para ejecutar el script de monitoreo
            python_cmd = sys.executable
            cmd_args = [task_name]
            
            # Crear comando completo
            full_cmd = f'"{python_cmd}" "{monitor_script}" {" ".join(cmd_args)}'
            
            # Determinar sistema operativo
            if sys.platform.startswith('win'):
                # 1. Crear script batch temporal para ejecutar el comando
                batch_dir = os.path.join(os.environ['TEMP'], 'SOAPMonitor')
                os.makedirs(batch_dir, exist_ok=True)
                batch_file = os.path.join(batch_dir, f'run_{task_name}.bat')
                
                # 2. Escribir el comando en un archivo .bat
                with open(batch_file, 'w') as f:
                    f.write(f'@echo off\n')
                    f.write(f'"{python_cmd}" "{monitor_script}" {task_name}\n')
                
                # 3. Crear la tarea usando el archivo .bat (sin espacios problemáticos)
                task_cmd = f'schtasks /create /tn "SOAPMonitor_{task_name}" /tr "{batch_file}" /sc minute /mo {interval_minutes} /f'
                subprocess.run(task_cmd, shell=True, check=True)
                logger.info(f"Tarea de sistema creada en Windows para {task_name} usando script: {batch_file}")
                
                return True
            else:
                # Linux/Unix - usar crontab
                cron_schedule = f"*/{interval_minutes} * * * * {full_cmd}"
                
                # Obtener crontab actual
                current_crontab = subprocess.check_output("crontab -l 2>/dev/null || echo ''", shell=True, text=True)
                
                # Buscar y reemplazar tarea existente o agregar nueva
                task_marker = f"# SOAPMonitor_{task_name}"
                
                if task_marker in current_crontab:
                    # Actualizar tarea existente
                    lines = current_crontab.splitlines()
                    new_lines = []
                    
                    i = 0
                    while i < len(lines):
                        if lines[i] == task_marker:
                            new_lines.append(task_marker)
                            new_lines.append(cron_schedule)
                            i += 2  # Saltar la línea anterior
                        else:
                            new_lines.append(lines[i])
                        i += 1
                    
                    new_crontab = "\n".join(new_lines)
                else:
                    # Agregar nueva tarea
                    new_crontab = current_crontab.strip() + f"\n\n{task_marker}\n{cron_schedule}\n"
                
                # Guardar nueva crontab
                subprocess.run("crontab -", shell=True, input=new_crontab, text=True, check=True)
                logger.info(f"Tarea de sistema creada en Linux/Unix para {task_name}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error al crear tarea de sistema para {task_name}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado al crear tarea de sistema: {str(e)}")
            return False
    
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
                # Windows - usar schtasks
                task_cmd = f'schtasks /delete /tn "SOAPMonitor_{task_name}" /f'
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
        
    # Añadir al final de scheduler.py
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
                    f'schtasks /query /tn "SOAPMonitor_{task_name}" /fo list',
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if result.returncode == 0:
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
        <URI>\\SOAPMonitor\\{service_name}</URI>
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
        <Hidden>false</Hidden>
        <RunOnlyIfIdle>false</RunOnlyIfIdle>
        <WakeToRun>false</WakeToRun>
        <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
        <Priority>7</Priority>
    </Settings>
    <Actions Context="Author">
        <Exec>
        <Command>"{python_path}"</Command>
        <Arguments>"{script_path}" "{service_name}"</Arguments>
        <WorkingDirectory>{os.path.dirname(script_path)}</WorkingDirectory>
        </Exec>
    </Actions>
    </Task>
    """
        return xml_content

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

    REM Registrar la tarea
    schtasks /create /tn "SOAPMonitor_{service_name}" /xml "{xml_path}" /f

    if %errorLevel% == 0 (
        echo.
        echo Tarea registrada correctamente.
        echo Nombre de la tarea: SOAPMonitor_{service_name}
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
            xml_content = generate_task_xml(service_name, interval_minutes, python_path, script_path)
            xml_path = os.path.join(service_dir, f"{service_name}_task.xml")
            
            with open(xml_path, 'w', encoding='utf-16') as f:
                f.write(xml_content)
                
            # Generar script batch
            batch_content = generate_batch_script(service_name, xml_path)
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
                    f'schtasks /query /tn "SOAPMonitor_{service_name}" /fo list',
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