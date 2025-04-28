import logging
import smtplib
import os
import sys
import traceback
import tempfile
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional, Tuple, Union
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
    
    # Añadir al inicio de notification.py, después de configurar logging
    def setup_notification_log(log_dir: str = None) -> None:
        """
        Configura un registro especializado para notificaciones con formato detallado.
        
        Args:
            log_dir (str, optional): Directorio para logs. Si es None, usa el directorio
                                    predeterminado de logs.
        """
        global notification_logger
        
        if log_dir is None:
            # Determinar directorio de logs basado en ubicación del script
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_dir = os.path.join(app_dir, 'logs')
        
        # Crear directorio de logs si no existe
        os.makedirs(log_dir, exist_ok=True)
        
        # Definir archivo de log específico para notificaciones
        notification_log_file = os.path.join(log_dir, 'notification_details.log')
        
        # Configurar logger específico
        notification_logger = logging.getLogger('notification_details')
        notification_logger.setLevel(logging.DEBUG)
        
        # Evitar duplicación de handlers
        if not notification_logger.handlers:
            # Crear un handler para archivo
            file_handler = logging.FileHandler(notification_log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            
            # Crear un formato detallado
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s\n'
                '------------------------------------------------------\n'
                '%(details)s\n'
                '======================================================\n'
            )
            file_handler.setFormatter(formatter)
            
            # Añadir handler al logger
            notification_logger.addHandler(file_handler)
            
            # Añadir mensaje de inicio
            notification_logger.info("Sistema de log para notificaciones iniciado", 
                                extra={'details': f"Archivo de logs: {notification_log_file}"})
        
        logger.info(f"Log especializado de notificaciones configurado en: {notification_log_file}")
    
    def log_notification_attempt(self, service_name: str, success: bool, 
                           recipients: List[str], attachments: List[Dict] = None) -> None:
        """
        Registra un intento de notificación con detalles completos para diagnóstico.
        
        Args:
            service_name (str): Nombre del servicio
            success (bool): Si la notificación fue exitosa
            recipients (List[str]): Destinatarios
            attachments (List[Dict], optional): Adjuntos enviados
        """
        try:
            # Asegurar que el logger especializado esté disponible
            notification_logger = logging.getLogger('notification_details')
            
            # Preparar información de adjuntos
            attachment_info = []
            if attachments:
                for att in attachments:
                    # Limitar la longitud de los datos para el log
                    data_preview = "..."
                    if isinstance(att['data'], str):
                        if len(att['data']) < 200:
                            data_preview = att['data']
                        else:
                            data_preview = att['data'][:197] + "..."
                    else:
                        data_preview = f"[Datos binarios: {len(att['data'])} bytes]"
                    
                    attachment_info.append({
                        'filename': att.get('filename', 'sin_nombre'),
                        'mime_type': att.get('mime_type', 'application/octet-stream'),
                        'size': len(att['data']) if isinstance(att['data'], str) else len(att['data']),
                        'preview': data_preview
                    })
            
            # Compilar detalles completos del intento
            details = (
                f"Evento: {'Notificación enviada correctamente' if success else 'Error al enviar notificación'}\n"
                f"Servicio: {service_name}\n"
                f"Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Destinatarios: {', '.join(recipients)}\n"
                f"\nConfiguración SMTP:\n"
                f"  Servidor: {self.smtp_config.get('server')}\n"
                f"  Puerto: {self.smtp_config.get('port')}\n"
                f"  Usuario: {self.smtp_config.get('username')}\n"
                f"  TLS: {self.smtp_config.get('use_tls', True)}\n"
                f"  Remitente: {self.smtp_config.get('from_email') or self.smtp_config.get('username')}\n"
                f"\nAdjuntos ({len(attachment_info) if attachment_info else 0}):\n"
            )
            
            # Añadir detalles de adjuntos
            for i, att in enumerate(attachment_info):
                details += (
                    f"  {i+1}. {att['filename']} ({att['mime_type']}, {att['size']} bytes)\n"
                    f"     Vista previa: {att['preview']}\n\n"
                )
            
            # Usar logger especializado
            notification_logger.info(
                f"{'✓ Notificación enviada' if success else '✗ Error de notificación'} - {service_name}", 
                extra={'details': details}
            )
        except Exception as e:
            logger.error(f"Error al registrar intento de notificación: {str(e)}")
        
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
        
        # Crear parte alternativa para contenido texto/html
        alt_part = MIMEMultipart('alternative')
        
        # Añadir contenido texto plano
        text_part = MIMEText(content, 'plain', 'utf-8')
        alt_part.attach(text_part)
        
        if html_content:
            html_part = MIMEText(html_content, 'html', 'utf-8')
            alt_part.attach(html_part)
        
        # Adjuntar la parte alternativa al mensaje principal
        msg.attach(alt_part)
        
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
                     content: str, html_content: Optional[str] = None,
                     attachments: Optional[List[Dict[str, Any]]] = None) -> bool:
        """
        Envía una notificación por correo electrónico con soporte para adjuntos.
        
        Args:
            recipients (List[str]): Lista de destinatarios
            subject (str): Asunto del correo
            content (str): Contenido del correo en texto plano
            html_content (str, optional): Contenido del correo en HTML
            attachments (List[Dict], optional): Lista de adjuntos en formato:
                                            [{'data': bytes|str, 'filename': str, 'mime_type': str}]
            
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
        
        # Lista para rastrear archivos temporales creados (para limpiarlos al final)
        temp_files = []
        
        try:
            # Crear mensaje
            msg = self._create_email_message(recipients, subject, content, html_content)
            
            # Añadir adjuntos si existen
            if attachments:
                for attachment in attachments:
                    try:
                        # Determinar tipo de datos y crear parte de mensaje adecuada
                        if isinstance(attachment['data'], str):
                            # Crear archivo temporal para el adjunto
                            # Determinar extensión apropiada
                            suffix = os.path.splitext(attachment['filename'])[1]
                            if not suffix:
                                suffix = '.txt'
                                
                            temp_file = self._create_temp_file_for_attachment(
                                attachment['data'], 
                                suffix=suffix
                            )
                            
                            if temp_file:
                                temp_files.append(temp_file)
                                
                                # Leer el archivo como binario para el adjunto
                                with open(temp_file, 'rb') as f:
                                    attachment_data = f.read()
                                    
                                # Crear parte del mensaje
                                mime_type = attachment.get('mime_type', 'text/plain')
                                main_type, sub_type = mime_type.split('/', 1)
                                
                                attachment_part = MIMEApplication(
                                    attachment_data,
                                    _subtype=sub_type
                                )
                            else:
                                # Si falló la creación del archivo temporal, adjuntar texto directamente
                                attachment_data = attachment['data'].encode('utf-8')
                                attachment_part = MIMEApplication(attachment_data)
                        else:
                            # Ya es bytes, usar directamente
                            attachment_part = MIMEApplication(attachment['data'])
                        
                        # Añadir cabeceras
                        attachment_part.add_header(
                            'Content-Disposition', 
                            f'attachment; filename="{attachment["filename"]}"'
                        )
                        msg.attach(attachment_part)
                        logger.debug(f"Adjunto añadido: {attachment['filename']}")
                    except Exception as att_err:
                        logger.error(f"Error al procesar adjunto {attachment.get('filename', 'desconocido')}: {str(att_err)}")
                        # Continuar con los otros adjuntos
            
            # Implementación de reintentos para la conexión SMTP
            max_retries = 3
            retry_delay = 2  # segundos iniciales
            
            for retry in range(max_retries):
                try:
                    # Conectar al servidor SMTP con timeout aumentado para evitar problemas de conexión
                    smtp = smtplib.SMTP(self.smtp_config['server'], self.smtp_config['port'], timeout=15)
                    
                    # Habilitar modo debug si estamos en nivel DEBUG
                    if logger.level <= logging.DEBUG:
                        smtp.set_debuglevel(1)
                    
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
                
                except smtplib.SMTPServerDisconnected as disconnect_err:
                    # Error específico de desconexión
                    logger.warning(f"Servidor SMTP desconectado (intento {retry+1}/{max_retries}): {str(disconnect_err)}")
                    
                    if retry < max_retries - 1:
                        # Esperar antes de reintentar con backoff exponencial
                        sleep_time = retry_delay * (2 ** retry)
                        logger.info(f"Esperando {sleep_time} segundos antes de reintentar...")
                        time.sleep(sleep_time)
                    else:
                        # Último intento fallido
                        logger.error(f"Error al enviar notificación después de {max_retries} intentos: {str(disconnect_err)}")
                        return False
                
                except smtplib.SMTPException as smtp_err:
                    # Otros errores SMTP
                    logger.error(f"Error SMTP (intento {retry+1}/{max_retries}): {str(smtp_err)}")
                    
                    if retry < max_retries - 1:
                        # Esperar antes de reintentar con backoff exponencial
                        sleep_time = retry_delay * (2 ** retry)
                        logger.info(f"Esperando {sleep_time} segundos antes de reintentar...")
                        time.sleep(sleep_time)
                    else:
                        # Último intento fallido
                        logger.error(f"Error al enviar notificación después de {max_retries} intentos: {str(smtp_err)}")
                        return False
                
                except Exception as e:
                    # Error general no específico de SMTP
                    logger.error(f"Error al enviar notificación: {str(e)}")
                    return False
            
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Error al enviar notificación: {str(e)}\n{error_details}")
            return False
        finally:
            # Limpiar archivos temporales
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                    logger.debug(f"Archivo temporal eliminado: {temp_file}")
                except Exception as clean_err:
                    logger.warning(f"Error al eliminar archivo temporal {temp_file}: {str(clean_err)}")
    
    def send_service_failure_notification(self, recipients: List[str], 
                                     service_name: str, 
                                     error_details: Dict[str, Any]) -> bool:
        """
        Envía una notificación de fallo de servicio con los datos de la solicitud y respuesta adjuntos.
        
        Args:
            recipients (List[str]): Lista de destinatarios
            service_name (str): Nombre del servicio que falló
            error_details (Dict[str, Any]): Detalles del error
            
        Returns:
            bool: True si se envió correctamente, False en caso contrario
        """
        logger.debug(f"[DEBUG_FLOW] Recibida solicitud de notificación para {service_name}")
        logger.debug(f"[DEBUG_FLOW] Tipo de servicio: {error_details.get('type', 'No especificado')}")
    
    
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
        
        Se han adjuntado los datos de la solicitud y la respuesta para análisis.
        
        Este es un mensaje automático generado por el sistema de monitoreo SOAP/REST.
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
            <p>Se han adjuntado los datos de la solicitud y la respuesta para análisis.</p>
            
            <div class="footer">
                Este es un mensaje automático generado por el sistema de monitoreo SOAP/REST.
            </div>
        </body>
        </html>
        """
        
        # Preparar adjuntos
        logger.debug(f"[DEBUG_FLOW] Preparando adjuntos para servicio tipo {service_type}")
        attachments = []
    
        # Procesar diferente según el tipo de servicio
        service_type = error_details.get('type', 'SOAP')
        if service_type == 'SOAP':
            logger.debug(f"[DEBUG_FLOW] Llamando a _prepare_soap_attachments")
            self._prepare_soap_attachments(service_name, error_details, attachments)
        else:  # REST
            logger.debug(f"[DEBUG_FLOW] Llamando a _prepare_rest_attachments")
            self._prepare_rest_attachments(service_name, error_details, attachments)
            
        logger.debug(f"[DEBUG_FLOW] Adjuntos preparados: {len(attachments)}")
        # Enviar la notificación
        success = self.send_notification(recipients, subject, content, html_content, attachments)
        
        # Registrar el intento para diagnóstico
        self.log_notification_attempt(service_name, success, recipients, attachments)
        
        return success
    
    def _prepare_soap_attachments(self, service_name: str, error_details: Dict[str, Any], 
                             attachments: List[Dict[str, Any]]) -> None:
        """
        Prepara los adjuntos para notificaciones de servicios SOAP.
        
        Args:
            service_name (str): Nombre del servicio
            error_details (Dict[str, Any]): Detalles del error
            attachments (List[Dict[str, Any]]): Lista de adjuntos a modificar
        """
        try:
            # 1. Adjuntar el XML de solicitud si está disponible
            request_xml = error_details.get('request_xml')
            if request_xml:
                attachments.append({
                    'data': request_xml,
                    'filename': f"{service_name}_request.xml",
                    'mime_type': 'application/xml'
                })
                logger.debug(f"XML de solicitud añadido para {service_name}")
            
            # 2. Adjuntar la respuesta sin procesar si está disponible
            response_text = error_details.get('response_text', '')
            
            # Intentar obtener de otras fuentes si no está disponible directamente
            if not response_text:
                if 'raw_response_xml' in error_details:
                    response_text = error_details['raw_response_xml']
                elif 'response' in error_details and isinstance(error_details['response'], str):
                    response_text = error_details['response']
                
            if response_text:
                # Determinar si es XML válido para elegir la extensión adecuada
                is_xml = False
                try:
                    if response_text.strip().startswith('<') and '>' in response_text:
                        # Verificación básica para determinar si parece XML
                        is_xml = True
                except:
                    is_xml = False
                    
                # Elegir extensión adecuada
                ext = 'xml' if is_xml else 'txt'
                mime_type = 'application/xml' if is_xml else 'text/plain'
                
                attachments.append({
                    'data': response_text,
                    'filename': f"{service_name}_response_raw.{ext}",
                    'mime_type': mime_type
                })
                logger.debug(f"Respuesta sin procesar añadida para {service_name} (formato: {ext})")
            
            # 3. Si hay una respuesta procesada como diccionario y es diferente a la respuesta sin procesar
            response = error_details.get('response')
            if isinstance(response, dict) and response:
                # Verificar si ya tenemos el contenido de la respuesta como texto
                if not response_text or response_text != str(response):
                    try:
                        # Intentar convertir a XML formateado
                        import dicttoxml
                        xml_response = dicttoxml.dicttoxml(response, custom_root='response', attr_type=False)
                        response_dict_text = xml_response.decode('utf-8')
                        
                        # Intentar formatear XML para mejor legibilidad
                        try:
                            import xml.dom.minidom as md
                            response_dict_text = md.parseString(response_dict_text).toprettyxml(indent="  ")
                        except:
                            pass
                        
                        attachments.append({
                            'data': response_dict_text,
                            'filename': f"{service_name}_response_processed.xml",
                            'mime_type': 'application/xml'
                        })
                        logger.debug(f"Respuesta procesada (XML) añadida para {service_name}")
                    except ImportError:
                        # Si dicttoxml no está disponible, usar JSON
                        import json
                        try:
                            response_dict_text = json.dumps(response, indent=2, default=str)
                            
                            attachments.append({
                                'data': response_dict_text,
                                'filename': f"{service_name}_response_processed.json",
                                'mime_type': 'application/json'
                            })
                            logger.debug(f"Respuesta procesada (JSON) añadida para {service_name}")
                        except Exception as json_err:
                            logger.warning(f"Error al convertir respuesta a JSON: {str(json_err)}")
            
            # 4. Buscar archivos de debug existentes para este servicio
            debug_files = self._find_debug_files(service_name, 'response')
            
            for debug_file in debug_files:
                # Evitar duplicar contenido
                content_already_added = False
                for att in attachments:
                    if isinstance(att['data'], str) and att['data'] == debug_file['content']:
                        content_already_added = True
                        break
                
                if not content_already_added:
                    attachments.append({
                        'data': debug_file['content'],
                        'filename': debug_file['filename'],
                        'mime_type': debug_file['mime_type']
                    })
                    logger.debug(f"Archivo de debug añadido: {debug_file['filename']}")

            logger.debug(f"Adjuntos preparados para {service_name}: {len(attachments)} archivos")
            for i, att in enumerate(attachments):
                filename = att.get('filename', 'sin_nombre')
                size = len(att['data']) if isinstance(att['data'], str) else len(att['data'])
                logger.debug(f"  {i+1}. {filename} ({size} bytes)")
        except Exception as e:
            logger.error(f"Error al preparar adjuntos SOAP: {str(e)}")
        
    def _prepare_rest_attachments(self, service_name: str, error_details: Dict[str, Any], 
                             attachments: List[Dict[str, Any]]) -> None:
        """
        Prepara los adjuntos para notificaciones de servicios REST.
        
        Args:
            service_name (str): Nombre del servicio
            error_details (Dict[str, Any]): Detalles del error
            attachments (List[Dict[str, Any]]): Lista de adjuntos a modificar
        """
        try:
            # 1. Adjuntar el JSON del request si está disponible
            request_body = None
            
            # Intentar obtener el cuerpo de solicitud desde varias fuentes posibles
            if 'request_body' in error_details:
                request_body = error_details['request_body']
            elif 'request_details' in error_details and 'request_body' in error_details['request_details']:
                request_body = error_details['request_details']['request_body']
            elif 'json_data' in error_details:
                request_body = error_details['json_data']
                
            if request_body:
                # Determinar si es un diccionario (JSON) o texto
                if isinstance(request_body, dict):
                    import json
                    request_text = json.dumps(request_body, indent=2, default=str)
                    filename = f"{service_name}_request.json"
                    mime_type = 'application/json'
                else:
                    request_text = str(request_body)
                    # Verificar si parece JSON
                    try:
                        import json
                        json.loads(request_text)
                        filename = f"{service_name}_request.json"
                        mime_type = 'application/json'
                    except (json.JSONDecodeError, TypeError):
                        filename = f"{service_name}_request.txt"
                        mime_type = 'text/plain'
                    
                attachments.append({
                    'data': request_text,
                    'filename': filename,
                    'mime_type': mime_type
                })
                logger.debug(f"Request body añadido para {service_name}")
            
            # 2. Adjuntar la respuesta REST sin normalizar
            response_text = error_details.get('response_text', '')
            
            # Si tenemos texto de respuesta sin procesar
            if response_text:
                # Determinar el formato de la respuesta
                mime_type = 'text/plain'
                filename = f"{service_name}_response_raw.txt"
                
                # Intentar determinar si es JSON
                try:
                    import json
                    json.loads(response_text)  # Solo para verificar
                    filename = f"{service_name}_response_raw.json"
                    mime_type = 'application/json'
                except (json.JSONDecodeError, TypeError):
                    # Verificar si parece XML
                    if response_text.strip().startswith('<') and '>' in response_text:
                        filename = f"{service_name}_response_raw.xml"
                        mime_type = 'application/xml'
                
                attachments.append({
                    'data': response_text,
                    'filename': filename,
                    'mime_type': mime_type
                })
                logger.debug(f"Respuesta REST sin procesar añadida para {service_name} (formato: {filename.split('.')[-1]})")
            
            # 3. Si hay una respuesta procesada como diccionario, también incluirla
            response = error_details.get('response', {})
            
            if isinstance(response, dict) and response:
                try:
                    import json
                    processed_response = json.dumps(response, indent=2, default=str)
                    
                    # Verificar si este contenido ya está en algún otro adjunto para evitar duplicados
                    content_already_added = False
                    for att in attachments:
                        if isinstance(att['data'], str) and att['data'] == processed_response:
                            content_already_added = True
                            break
                    
                    if not content_already_added:
                        attachments.append({
                            'data': processed_response,
                            'filename': f"{service_name}_response_processed.json",
                            'mime_type': 'application/json'
                        })
                        logger.debug(f"Respuesta REST procesada añadida para {service_name}")
                except Exception as json_err:
                    logger.warning(f"Error al procesar respuesta JSON: {str(json_err)}")
            
            # 4. Si hay headers de respuesta, incluirlos
            response_headers = None
            
            # Intentar obtener headers desde varias fuentes posibles
            if 'headers' in error_details:
                response_headers = error_details['headers']
            elif 'response_headers' in error_details:
                response_headers = error_details['response_headers']
            
            if response_headers:
                try:
                    import json
                    headers_text = json.dumps(response_headers, indent=2, default=str)
                    
                    attachments.append({
                        'data': headers_text,
                        'filename': f"{service_name}_response_headers.json",
                        'mime_type': 'application/json'
                    })
                    logger.debug(f"Headers de respuesta añadidos para {service_name}")
                except Exception as headers_err:
                    logger.warning(f"Error al procesar headers: {str(headers_err)}")
            
            # 5. Buscar archivos de debug existentes para este servicio
            debug_files = self._find_debug_files(service_name, 'response')
            
            for debug_file in debug_files:
                # Evitar duplicar contenido
                content_already_added = False
                for att in attachments:
                    if isinstance(att['data'], str) and att['data'] == debug_file['content']:
                        content_already_added = True
                        break
                
                if not content_already_added:
                    attachments.append({
                        'data': debug_file['content'],
                        'filename': debug_file['filename'],
                        'mime_type': debug_file['mime_type']
                    })
                    logger.debug(f"Archivo de debug añadido: {debug_file['filename']}")
            logger.debug(f"Adjuntos preparados para {service_name}: {len(attachments)} archivos")
            for i, att in enumerate(attachments):
                filename = att.get('filename', 'sin_nombre')
                size = len(att['data']) if isinstance(att['data'], str) else len(att['data'])
                logger.debug(f"  {i+1}. {filename} ({size} bytes)")
        except Exception as e:
            logger.error(f"Error al preparar adjuntos REST: {str(e)}", exc_info=True)
            
    
    def _find_debug_files(self, service_name: str, file_type: str) -> List[Dict[str, Any]]:
        """
        Encuentra archivos de debug relacionados con un servicio para adjuntar.
        
        Args:
            service_name (str): Nombre del servicio
            file_type (str): Tipo de archivo ('request' o 'response')
            
        Returns:
            List[Dict[str, Any]]: Lista de archivos encontrados con sus metadatos
        """
        found_files = []
        
        try:
            # Normalizar el nombre del servicio para búsqueda en nombres de archivo
            normalized_name = service_name.lower().replace(' ', '_')
            
            # Buscar en directorio de debug
            debug_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'debug')
            
            if not os.path.exists(debug_dir):
                logger.debug(f"Directorio de debug no encontrado: {debug_dir}")
                return found_files
                
            # Buscar archivos que coincidan con el patrón
            for filename in os.listdir(debug_dir):
                # Verificar si el archivo corresponde al servicio y tipo especificado
                if (normalized_name in filename.lower() or 
                    'direct_call' in filename.lower()) and f"_{file_type}." in filename:
                    
                    file_path = os.path.join(debug_dir, filename)
                    
                    # Verificar extensión para determinar tipo MIME
                    _, ext = os.path.splitext(filename)
                    
                    if ext.lower() == '.xml':
                        mime_type = 'application/xml'
                    elif ext.lower() == '.json':
                        mime_type = 'application/json'
                    else:
                        mime_type = 'text/plain'
                    
                    # Leer contenido del archivo
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        # Añadir a lista de archivos encontrados
                        found_files.append({
                            'path': file_path,
                            'filename': filename,
                            'content': content,
                            'mime_type': mime_type,
                            'modified': os.path.getmtime(file_path)
                        })
                    except Exception as read_err:
                        logger.warning(f"Error al leer archivo de debug {filename}: {str(read_err)}")
            
            # Ordenar por fecha de modificación (más reciente primero)
            found_files.sort(key=lambda x: x['modified'], reverse=True)
            
            # Limitar a los 2 archivos más recientes para evitar sobrecarga
            return found_files[:2]
            
        except Exception as e:
            logger.error(f"Error al buscar archivos de debug: {str(e)}")
            return found_files
    
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
    
    # Añadir al fondo de EmailNotifier
    def log_notification_attempt(self, service_name: str, success: bool, 
                            recipients: List[str], attachments: List[Dict] = None) -> None:
        """
        Registra un intento de notificación con detalles completos para diagnóstico.
        
        Args:
            service_name (str): Nombre del servicio
            success (bool): Si la notificación fue exitosa
            recipients (List[str]): Destinatarios
            attachments (List[Dict], optional): Adjuntos enviados
        """
        try:
            # Preparar información de adjuntos
            attachment_info = []
            if attachments:
                for att in attachments:
                    # Limitar la longitud de los datos para el log
                    data_preview = "..."
                    if isinstance(att['data'], str) and len(att['data']) < 200:
                        data_preview = att['data']
                    
                    attachment_info.append({
                        'filename': att['filename'],
                        'mime_type': att.get('mime_type', 'text/plain'),
                        'size': len(att['data']) if isinstance(att['data'], str) else 'binary data',
                        'preview': data_preview
                    })
            
            # Compilar detalles
            details = (
                f"Servicio: {service_name}\n"
                f"Estado: {'Exitoso' if success else 'Fallido'}\n"
                f"Destinatarios: {', '.join(recipients)}\n"
                f"Configuración SMTP:\n"
                f"  Servidor: {self.smtp_config.get('server')}\n"
                f"  Puerto: {self.smtp_config.get('port')}\n"
                f"  Usuario: {self.smtp_config.get('username')}\n"
                f"  TLS: {self.smtp_config.get('use_tls', True)}\n"
                f"Adjuntos ({len(attachment_info) if attachment_info else 0}):\n"
            )
            
            # Añadir detalles de adjuntos
            for i, att in enumerate(attachment_info):
                details += (
                    f"  {i+1}. {att['filename']} ({att['mime_type']}, {att['size']} bytes)\n"
                    f"     Preview: {att['preview']}\n"
                )
            
            # Usar logger especializado
            import logging
            notification_logger = logging.getLogger('notification_detail')
            notification_logger.info(
                f"{'Notificación enviada' if success else 'Error de notificación'} - {service_name}", 
                extra={'details': details}
            )
        except Exception as e:
            logger.error(f"Error al registrar intento de notificación: {str(e)}")
            
    def _create_temp_file_for_attachment(self, data: Union[str, bytes], 
                                     suffix: str = '.txt') -> Optional[str]:
        """
        Crea un archivo temporal para un adjunto.
        
        Args:
            data (Union[str, bytes]): Datos a escribir en el archivo
            suffix (str, optional): Extensión del archivo. Por defecto '.txt'
            
        Returns:
            Optional[str]: Ruta al archivo temporal o None si hay error
        """
        try:
            # Crear archivo temporal
            fd, temp_path = tempfile.mkstemp(suffix=suffix)
            
            # Determinar si los datos son string o bytes
            if isinstance(data, str):
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(data)
            else:
                with os.fdopen(fd, 'wb') as f:
                    f.write(data)
            
            return temp_path
        except Exception as e:
            logger.error(f"Error al crear archivo temporal para adjunto: {str(e)}")
            # Intentar cerrar el descriptor de archivo si se creó
            if 'fd' in locals():
                try:
                    os.close(fd)
                except:
                    pass
            return None