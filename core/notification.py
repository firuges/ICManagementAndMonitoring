import logging
import smtplib
import os
import sys
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('notification')

class EmailNotifier:
    """Sistema de notificaciones por correo electrónico"""
    
    def __init__(self, smtp_config: Optional[Dict[str, Any]] = None):
        """
        Inicializa el sistema de notificaciones.
        
        Args:
            smtp_config (Dict[str, Any], optional): Configuración SMTP
        """
        # Configuración por defecto
        self.smtp_config = smtp_config or {
            'server': 'smtp.gmail.com',
            'port': 587,
            'use_tls': True,
            'username': '',
            'password': '',
            'from_email': ''
        }
        
        # Mantener registro de errores para evitar spam
        self.error_log = {}
        self.notification_count = 0
        self.last_notification_time = None
        
        # Verificar si hay archivo de configuración
        self._load_config_from_file()
    
    def _load_config_from_file(self):
        """Intenta cargar la configuración desde un archivo"""
        try:
            # Buscar archivo de configuración en varias ubicaciones
            possible_paths = [
                'smtp_config.json',  # En el directorio actual
                os.path.join('data', 'smtp_config.json'),  # En subdirectorio data
                os.path.join('..', 'data', 'smtp_config.json'),  # Un nivel arriba
            ]
            
            # Si estamos en entorno compilado, buscar en el directorio del ejecutable
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
                possible_paths.append(os.path.join(app_dir, 'data', 'smtp_config.json'))
            
            # Iterar por posibles ubicaciones
            for path in possible_paths:
                if os.path.exists(path):
                    import json
                    with open(path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    self.configure(config)
                    logger.info(f"Configuración SMTP cargada desde {path}")
                    return
                    
        except Exception as e:
            logger.warning(f"No se pudo cargar configuración SMTP desde archivo: {str(e)}")
    
    
    def configure(self, smtp_config: Dict[str, Any]) -> None:
        """
        Configura el servidor SMTP.
        
        Args:
            smtp_config (Dict[str, Any]): Configuración SMTP
        """
        # Actualizar solo los campos proporcionados
        for key, value in smtp_config.items():
            if key in self.smtp_config:
                self.smtp_config[key] = value
        
        # Verificar consistencia de configuración
        if not self.smtp_config.get('from_email'):
            self.smtp_config['from_email'] = self.smtp_config.get('username', '')
        
        # Registrar configuración (sin mostrar contraseña)
        safe_config = self.smtp_config.copy()
        if 'password' in safe_config:
            safe_config['password'] = '********' if safe_config['password'] else '(vacío)'
        
        logger.info(f"Configuración SMTP actualizada: {safe_config}")
    
    def _create_email_message(self, 
                             recipients: List[str], 
                             subject: str, 
                             content: str, 
                             html_content: Optional[str] = None) -> MIMEMultipart:
        """
        Crea un mensaje de correo electrónico.
        
        Args:
            recipients (List[str]): Lista de destinatarios
            subject (str): Asunto del correo
            content (str): Contenido en texto plano
            html_content (str, optional): Contenido HTML
            
        Returns:
            MIMEMultipart: Mensaje preparado
        """
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.smtp_config.get('from_email') or self.smtp_config.get('username')
        msg['To'] = ', '.join(recipients)
        
        # Añadir contenido texto plano
        text_part = MIMEText(content, 'plain')
        msg.attach(text_part)
        
        # Añadir contenido HTML si se proporciona
        if html_content:
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
        
        return msg
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Prueba la conexión al servidor SMTP.
        
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        if not self.smtp_config.get('username') or not self.smtp_config.get('password'):
            return False, "Configuración SMTP incompleta: falta usuario o contraseña"
    
        try:
            # Conectar al servidor SMTP con timeout reducido
            smtp = smtplib.SMTP(self.smtp_config['server'], self.smtp_config['port'], timeout=5)
            
            # Usar TLS si está configurado
            if self.smtp_config.get('use_tls', True):
                smtp.starttls()
            
            # Iniciar sesión
            smtp.login(self.smtp_config['username'], self.smtp_config['password'])
            
            # Cerrar conexión
            smtp.quit()
            
            return True, "Conexión exitosa al servidor SMTP"
            
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Error al probar conexión SMTP: {str(e)}\n{error_details}")
            return False, f"Error de conexión: {str(e)}"
    
    
    def send_notification(self, recipients: List[str], subject: str, 
                         content: str, html_content: Optional[str] = None) -> bool:
        """
        Envía una notificación por correo electrónico.
        
        Args:
            recipients (List[str]): Lista de destinatarios
            subject (str): Asunto del correo
            content (str): Contenido del correo en texto plano
            html_content (str, optional): Contenido del correo en HTML
            
        Returns:
            bool: True si se envió correctamente, False en caso contrario
        """
        # Control de frecuencia de notificaciones
        current_time = datetime.now()
        if self.last_notification_time:
            # Si han pasado menos de 5 segundos desde la última notificación
            time_diff = (current_time - self.last_notification_time).total_seconds()
            if time_diff < 5 and self.notification_count > 5:
                logger.warning(f"Demasiadas notificaciones en poco tiempo ({time_diff}s). Espaciando envíos.")
                return False
        
        self.last_notification_time = current_time
        self.notification_count += 1
        
        if not recipients:
            logger.warning("No se especificaron destinatarios para la notificación")
            return False
        
        if not self.smtp_config.get('username') or not self.smtp_config.get('password'):
            logger.error("Configuración SMTP incompleta. No se envió la notificación.")
            return False
        
        try:
            # Crear mensaje
            msg = self._create_email_message(recipients, subject, content, html_content)
            
            # Conectar al servidor SMTP
            smtp = smtplib.SMTP(self.smtp_config['server'], self.smtp_config['port'], timeout=5)
            
            # Usar TLS si está configurado
            if self.smtp_config.get('use_tls', True):
                smtp.starttls()
            
            # Iniciar sesión
            smtp.login(self.smtp_config['username'], self.smtp_config['password'])
            
            # Enviar correo
            smtp.send_message(msg)
            smtp.quit()
            
            logger.info(f"Notificación enviada a {len(recipients)} destinatarios")
            return True
            
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Error al enviar notificación: {str(e)}\n{error_details}")
            return False
    
    
    def send_service_failure_notification(self, recipients: List[str], 
                                         service_name: str, 
                                         error_details: Dict[str, Any]) -> bool:
        """
        Envía una notificación de fallo de servicio.
        
        Args:
            recipients (List[str]): Lista de destinatarios
            service_name (str): Nombre del servicio que falló
            error_details (Dict[str, Any]): Detalles del error
            
        Returns:
            bool: True si se envió correctamente, False en caso contrario
        """
        # Control básico de duplicación (evitar spam)
        error_key = f"{service_name}:{error_details.get('status', 'unknown')}"
        current_time = datetime.now()
        
        if error_key in self.error_log:
            last_time, count = self.error_log[error_key]
            time_diff = (current_time - last_time).total_seconds()
            
            # Si han pasado menos de 5 minutos y ya enviamos 3 mensajes, omitir
            if time_diff < 300 and count >= 3:
                logger.info(f"Omitiendo notificación duplicada para {service_name} (enviada {count} veces en 5 min)")
                return False
            
            # Actualizar contador
            self.error_log[error_key] = (current_time, count + 1)
        else:
            # Primer error de este tipo
            self.error_log[error_key] = (current_time, 1)
        
        # Determinar estado a partir de los detalles
        status = error_details.get('status', 'desconocido')
        error_message = error_details.get('error', 'No disponible')
        timestamp = error_details.get('timestamp', datetime.now().isoformat())
        
        # Intentar formatear el timestamp si es una cadena ISO
        try:
            if isinstance(timestamp, str):
                timestamp_dt = datetime.fromisoformat(timestamp)
                formatted_timestamp = timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                formatted_timestamp = timestamp
        except:
            formatted_timestamp = timestamp
            
        # Obtener información adicional
        service_type = error_details.get('type', 'SOAP')
        service_group = error_details.get('group', '')
        
        subject = f"ALERTA: Fallo en el servicio {service_type} '{service_name}'"
        
        # Contenido en texto plano
        content = f"""
        Se ha detectado un fallo en el servicio {service_type}: {service_name}
        
        Detalles del error:
        - Estado: {status}
        - Mensaje: {error_message}
        - Fecha y hora: {formatted_timestamp}
        """
        
        if service_group:
            content += f"- Grupo: {service_group}\n"
        
        content += """
        Por favor, verifique el estado del servicio lo antes posible.
        
        Este es un mensaje automático generado por el sistema de monitoreo SOAP.
        """
        
        # Contenido HTML (más formateado)
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .alert {{ color: #D8000C; background-color: #FFD2D2; padding: 10px; border-radius: 5px; }}
                .details {{ margin: 20px 0; }}
                .footer {{ font-size: 12px; color: #666; margin-top: 30px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h2 class="alert">Alerta: Fallo en servicio {service_type}</h2>
            <p>Se ha detectado un fallo en el servicio: <strong>{service_name}</strong></p>
            
            <div class="details">
                <h3>Detalles del error:</h3>
                <table>
                    <tr>
                        <th>Estado</th>
                        <td>{status}</td>
                    </tr>
                    <tr>
                        <th>Mensaje</th>
                        <td>{error_message}</td>
                    </tr>
                    <tr>
                        <th>Fecha y hora</th>
                        <td>{formatted_timestamp}</td>
                    </tr>
        """
        
        if service_group:
            html_content += f"""
                    <tr>
                        <th>Grupo</th>
                        <td>{service_group}</td>
                    </tr>
            """
            
        html_content += """
                </table>
            </div>
            
            <p>Por favor, verifique el estado del servicio lo antes posible.</p>
            
            <div class="footer">
                Este es un mensaje automático generado por el sistema de monitoreo SOAP.
            </div>
        </body>
        </html>
        """
        
        return self.send_notification(recipients, subject, content, html_content)
    
    
    def send_daily_summary(self, recipients: List[str], 
                          service_stats: Dict[str, Any]) -> bool:
        """
        Envía un resumen diario del estado de los servicios.
        
        Args:
            recipients (List[str]): Lista de destinatarios
            service_stats (Dict[str, Any]): Estadísticas de los servicios
            
        Returns:
            bool: True si se envió correctamente, False en caso contrario
        """
        # Extraer estadísticas
        total_services = service_stats.get('total', 0)
        ok_count = service_stats.get('ok', 0)
        failed_count = service_stats.get('failed', 0)
        warning_count = service_stats.get('warning', 0)
        error_count = service_stats.get('error', 0)
        not_checked = service_stats.get('not_checked', 0)
        
        # Lista de servicios fallidos
        failed_services = service_stats.get('failed_services', [])
        
        # Crear asunto
        current_date = datetime.now().strftime("%Y-%m-%d")
        subject = f"Resumen de monitoreo de servicios - {current_date}"
        
        # Contenido texto plano
        content = f"""
        RESUMEN DIARIO DE MONITOREO DE SERVICIOS - {current_date}
        
        Estado general:
        - Total de servicios: {total_services}
        - Servicios correctos: {ok_count}
        - Servicios con advertencias: {warning_count}
        - Servicios con errores: {error_count + failed_count}
        - Servicios no verificados: {not_checked}
        
        """
        
        if failed_services:
            content += "Servicios con problemas:\n"
            for service in failed_services:
                content += f"- {service['name']}: {service['status']} - {service.get('error', 'No hay detalles')}\n"
        else:
            content += "No se detectaron problemas en los servicios.\n"
        
        content += """
        Este es un resumen automático generado por el sistema de monitoreo SOAP.
        """
        
        # Contenido HTML
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                h2 {{ color: #333; }}
                .summary {{ margin: 20px 0; }}
                .stats {{ margin-bottom: 20px; }}
                .ok {{ color: green; }}
                .warning {{ color: orange; }}
                .error {{ color: red; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                .footer {{ font-size: 12px; color: #666; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <h2>Resumen diario de monitoreo de servicios - {current_date}</h2>
            
            <div class="summary">
                <h3>Estado general:</h3>
                <div class="stats">
                    <p><strong>Total de servicios:</strong> {total_services}</p>
                    <p><strong>Servicios correctos:</strong> <span class="ok">{ok_count}</span></p>
                    <p><strong>Servicios con advertencias:</strong> <span class="warning">{warning_count}</span></p>
                    <p><strong>Servicios con errores:</strong> <span class="error">{error_count + failed_count}</span></p>
                    <p><strong>Servicios no verificados:</strong> {not_checked}</p>
                </div>
        """
        
        if failed_services:
            html_content += """
                <h3>Servicios con problemas:</h3>
                <table>
                    <tr>
                        <th>Servicio</th>
                        <th>Estado</th>
                        <th>Detalles</th>
                    </tr>
            """
            
            for service in failed_services:
                status_class = 'error' if service['status'] in ['failed', 'error'] else 'warning'
                html_content += f"""
                    <tr>
                        <td>{service['name']}</td>
                        <td class="{status_class}">{service['status']}</td>
                        <td>{service.get('error', 'No hay detalles')}</td>
                    </tr>
                """
                
            html_content += "</table>"
        else:
            html_content += """
                <h3>No se detectaron problemas en los servicios</h3>
                <p class="ok">Todos los servicios están funcionando correctamente.</p>
            """
            
        html_content += """
            </div>
            
            <div class="footer">
                Este es un resumen automático generado por el sistema de monitoreo SOAP.
            </div>
        </body>
        </html>
        """
        
        return self.send_notification(recipients, subject, content, html_content)