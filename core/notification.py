import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional

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
    
    def configure(self, smtp_config: Dict[str, Any]) -> None:
        """
        Configura el servidor SMTP.
        
        Args:
            smtp_config (Dict[str, Any]): Configuración SMTP
        """
        self.smtp_config.update(smtp_config)
    
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
        if not recipients:
            logger.warning("No se especificaron destinatarios para la notificación")
            return False
        
        if not self.smtp_config.get('username') or not self.smtp_config.get('password'):
            logger.error("Configuración SMTP incompleta. No se envió la notificación.")
            return False
        
        try:
            # Crear mensaje
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
            
            # Conectar al servidor SMTP
            smtp = smtplib.SMTP(self.smtp_config['server'], self.smtp_config['port'])
            
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
            logger.error(f"Error al enviar notificación: {str(e)}")
            return False
    
    def send_service_failure_notification(self, recipients: List[str], 
                                         service_name: str, error_details: Dict[str, Any]) -> bool:
        """
        Envía una notificación de fallo de servicio.
        
        Args:
            recipients (List[str]): Lista de destinatarios
            service_name (str): Nombre del servicio que falló
            error_details (Dict[str, Any]): Detalles del error
            
        Returns:
            bool: True si se envió correctamente, False en caso contrario
        """
        subject = f"ALERTA: Fallo en el servicio SOAP '{service_name}'"
        
        # Contenido en texto plano
        content = f"""
        Se ha detectado un fallo en el servicio SOAP: {service_name}
        
        Detalles del error:
        - Estado: {error_details.get('status', 'desconocido')}
        - Mensaje: {error_details.get('error', 'No disponible')}
        - Fecha y hora: {error_details.get('timestamp', 'No disponible')}
        
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
            </style>
        </head>
        <body>
            <h2 class="alert">Alerta: Fallo en servicio SOAP</h2>
            <p>Se ha detectado un fallo en el servicio SOAP: <strong>{service_name}</strong></p>
            
            <div class="details">
                <h3>Detalles del error:</h3>
                <ul>
                    <li><strong>Estado:</strong> {error_details.get('status', 'desconocido')}</li>
                    <li><strong>Mensaje:</strong> {error_details.get('error', 'No disponible')}</li>
                    <li><strong>Fecha y hora:</strong> {error_details.get('timestamp', 'No disponible')}</li>
                </ul>
            </div>
            
            <p>Por favor, verifique el estado del servicio lo antes posible.</p>
            
            <div class="footer">
                Este es un mensaje automático generado por el sistema de monitoreo SOAP.
            </div>
        </body>
        </html>
        """
        
        return self.send_notification(recipients, subject, content, html_content)