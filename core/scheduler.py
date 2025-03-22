import os
import logging
import schedule
import time
import threading
import subprocess
import sys
from typing import Dict, Any, List, Callable
from datetime import datetime

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
        monitor_script = os.path.join(project_root, 'monitor.py')
        
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
                # Windows - usar schtasks
                task_cmd = f'schtasks /create /tn "SOAPMonitor_{task_name}" /tr "{full_cmd}" /sc minute /mo {interval_minutes} /f'
                subprocess.run(task_cmd, shell=True, check=True)
                logger.info(f"Tarea de sistema creada en Windows para {task_name}")
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