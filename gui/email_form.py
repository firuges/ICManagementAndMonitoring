import os
import re
import logging
import json
from typing import Dict, Any, List
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, 
    QPushButton, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QCheckBox, QSpinBox, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QRegExp
from PyQt5.QtGui import QRegExpValidator

# Importar módulos de la aplicación
from core.persistence import PersistenceManager
from core.notification import EmailNotifier

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('email_form')

class EmailForm(QWidget):
    """Formulario para configuración de notificaciones por email"""
    
    config_saved = pyqtSignal()  # Señal emitida cuando se guarda la configuración
    
    def __init__(self, persistence: PersistenceManager, notifier: EmailNotifier):
        """
        Inicializa el formulario de configuración de emails.
        
        Args:
            persistence (PersistenceManager): Gestor de persistencia
            notifier (EmailNotifier): Notificador por email
        """
        super().__init__()
        
        self.persistence = persistence
        self.notifier = notifier
        
        # Crear interfaz
        self._create_ui()
        
        # Cargar configuración existente
        self._load_config()
        
        logger.info("Formulario de configuración de emails inicializado")
    
    def _create_ui(self):
        """Crea la interfaz de usuario"""
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # Grupo para configuración SMTP
        smtp_group = QGroupBox("Configuración de Servidor SMTP")
        smtp_layout = QFormLayout()
        smtp_group.setLayout(smtp_layout)
        
        # Campos de configuración SMTP
        self.smtp_server = QLineEdit()
        self.smtp_server.setPlaceholderText("smtp.gmail.com")
        smtp_layout.addRow("Servidor SMTP:", self.smtp_server)
        
        self.smtp_port = QSpinBox()
        self.smtp_port.setRange(1, 65535)
        self.smtp_port.setValue(587)
        smtp_layout.addRow("Puerto:", self.smtp_port)
        
        self.smtp_use_tls = QCheckBox("Usar TLS")
        self.smtp_use_tls.setChecked(True)
        smtp_layout.addRow("", self.smtp_use_tls)
        
        self.smtp_username = QLineEdit()
        self.smtp_username.setPlaceholderText("usuario@gmail.com")
        smtp_layout.addRow("Usuario:", self.smtp_username)
        
        self.smtp_password = QLineEdit()
        self.smtp_password.setEchoMode(QLineEdit.Password)
        self.smtp_password.setPlaceholderText("Contraseña o token de aplicación")
        smtp_layout.addRow("Contraseña:", self.smtp_password)
        
        self.from_email = QLineEdit()
        self.from_email.setPlaceholderText("notificaciones@ejemplo.com")
        smtp_layout.addRow("Email Remitente:", self.from_email)
        
        # Botón de prueba SMTP
        self.btn_test_smtp = QPushButton("Probar Conexión")
        self.btn_test_smtp.clicked.connect(self._test_smtp_connection)
        smtp_layout.addRow("", self.btn_test_smtp)
        
        main_layout.addWidget(smtp_group)
        
        # Grupo para destinatarios de correo
        recipients_group = QGroupBox("Destinatarios de Notificaciones")
        recipients_layout = QVBoxLayout()
        recipients_group.setLayout(recipients_layout)
        
        # Tabla de destinatarios
        self.recipients_table = QTableWidget(0, 2)
        self.recipients_table.setHorizontalHeaderLabels(["Email", "Acciones"])
        self.recipients_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.recipients_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.recipients_table.setColumnWidth(1, 100)
        recipients_layout.addWidget(self.recipients_table)
        
        # Formulario para añadir destinatario
        add_layout = QHBoxLayout()
        
        self.new_recipient = QLineEdit()
        self.new_recipient.setPlaceholderText("nuevo@destinatario.com")
        
        # Validador de email
        email_regex = QRegExp(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        email_validator = QRegExpValidator(email_regex)
        self.new_recipient.setValidator(email_validator)
        
        self.btn_add_recipient = QPushButton("Añadir")
        self.btn_add_recipient.clicked.connect(self._add_recipient)
        
        add_layout.addWidget(self.new_recipient)
        add_layout.addWidget(self.btn_add_recipient)
        
        recipients_layout.addLayout(add_layout)
        
        main_layout.addWidget(recipients_group)
        
        # Grupo para configuración de notificaciones
        notify_group = QGroupBox("Configuración de Notificaciones")
        notify_layout = QFormLayout()
        notify_group.setLayout(notify_layout)
        
        self.notify_on_error = QCheckBox("Notificar errores de conexión")
        self.notify_on_error.setChecked(True)
        notify_layout.addRow("", self.notify_on_error)
        
        self.notify_on_validation = QCheckBox("Notificar errores de validación")
        self.notify_on_validation.setChecked(True)
        notify_layout.addRow("", self.notify_on_validation)
        
        self.notify_daily_summary = QCheckBox("Enviar resumen diario")
        notify_layout.addRow("", self.notify_daily_summary)
        
        main_layout.addWidget(notify_group)
        
        # Botones de acción
        buttons_layout = QHBoxLayout()
        
        self.btn_reset = QPushButton("Restaurar valores")
        self.btn_reset.clicked.connect(self._load_config)
        buttons_layout.addWidget(self.btn_reset)
        
        self.btn_save = QPushButton("Guardar configuración")
        self.btn_save.clicked.connect(self._save_config)
        self.btn_save.setDefault(True)
        buttons_layout.addWidget(self.btn_save)
        
        main_layout.addLayout(buttons_layout)
    
    def _load_config(self):
        """Carga la configuración existente"""
        try:
            # Cargar configuración SMTP
            smtp_config_path = os.path.join(self.persistence.base_path, 'smtp_config.json')
            
            if os.path.exists(smtp_config_path):
                with open(smtp_config_path, 'r', encoding='utf-8') as f:
                    smtp_config = json.load(f)
                
                self.smtp_server.setText(smtp_config.get('server', ''))
                self.smtp_port.setValue(int(smtp_config.get('port', 587)))
                self.smtp_use_tls.setChecked(smtp_config.get('use_tls', True))
                self.smtp_username.setText(smtp_config.get('username', ''))
                self.smtp_password.setText(smtp_config.get('password', ''))
                self.from_email.setText(smtp_config.get('from_email', ''))
                
                # Configurar notificador con estos valores
                self.notifier.configure(smtp_config)
            
            # Cargar configuración de notificaciones
            notify_config_path = os.path.join(self.persistence.base_path, 'notification_config.json')
            
            if os.path.exists(notify_config_path):
                with open(notify_config_path, 'r', encoding='utf-8') as f:
                    notify_config = json.load(f)
                
                self.notify_on_error.setChecked(notify_config.get('notify_on_error', True))
                self.notify_on_validation.setChecked(notify_config.get('notify_on_validation', True))
                self.notify_daily_summary.setChecked(notify_config.get('notify_daily_summary', False))
            
            # Cargar destinatarios
            self._load_recipients()
            
            logger.info("Configuración cargada correctamente")
            
        except Exception as e:
            logger.error(f"Error al cargar configuración: {str(e)}")
            QMessageBox.warning(self, "Error", f"Error al cargar configuración: {str(e)}")
    
    def _load_recipients(self):
        """Carga la lista de destinatarios"""
        try:
            # Cargar configuración de emails
            email_config = self.persistence.load_email_config()
            recipients = email_config.get('recipients', [])
            
            # Limpiar tabla
            self.recipients_table.setRowCount(0)
            
            # Añadir destinatarios a la tabla
            for email in recipients:
                self._add_recipient_to_table(email)
            
            logger.info(f"Cargados {len(recipients)} destinatarios")
            
        except Exception as e:
            logger.error(f"Error al cargar destinatarios: {str(e)}")
    
    def _add_recipient_to_table(self, email: str):
        """
        Añade un destinatario a la tabla.
        
        Args:
            email (str): Dirección de correo a añadir
        """
        # Añadir nueva fila
        row = self.recipients_table.rowCount()
        self.recipients_table.insertRow(row)
        
        # Añadir email
        email_item = QTableWidgetItem(email)
        email_item.setFlags(email_item.flags() & ~Qt.ItemIsEditable)  # No editable
        self.recipients_table.setItem(row, 0, email_item)
        
        # Añadir botón de eliminar
        btn_delete = QPushButton("Eliminar")
        btn_delete.clicked.connect(lambda: self._remove_recipient(row))
        self.recipients_table.setCellWidget(row, 1, btn_delete)
    
    def _add_recipient(self):
        """Añade un nuevo destinatario"""
        email = self.new_recipient.text().strip()
        
        if not email:
            return
        
        # Validar formato de email con regex
        email_regex = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        if not email_regex.match(email):
            QMessageBox.warning(self, "Error", "Email con formato incorrecto")
            return
        
        # Verificar si ya existe
        for row in range(self.recipients_table.rowCount()):
            if self.recipients_table.item(row, 0).text() == email:
                QMessageBox.information(self, "Información", "Este email ya está en la lista")
                return
        
        # Añadir a la tabla
        self._add_recipient_to_table(email)
        
        # Limpiar campo
        self.new_recipient.clear()
        
        logger.info(f"Destinatario añadido: {email}")
    
    def _remove_recipient(self, row: int):
        """
        Elimina un destinatario de la tabla.
        
        Args:
            row (int): Fila a eliminar
        """
        if 0 <= row < self.recipients_table.rowCount():
            email = self.recipients_table.item(row, 0).text()
            self.recipients_table.removeRow(row)
            logger.info(f"Destinatario eliminado: {email}")
    
    def _save_config(self):
        """Guarda la configuración"""
        try:
            # Guardar configuración SMTP
            smtp_config = {
                'server': self.smtp_server.text().strip(),
                'port': self.smtp_port.value(),
                'use_tls': self.smtp_use_tls.isChecked(),
                'username': self.smtp_username.text().strip(),
                'password': self.smtp_password.text().strip(),
                'from_email': self.from_email.text().strip(),
            }
            
            # Validar datos mínimos
            if self.smtp_server.text().strip() and self.smtp_username.text().strip():
                # Guardar en archivo
                smtp_config_path = os.path.join(self.persistence.base_path, 'smtp_config.json')
                
                with open(smtp_config_path, 'w', encoding='utf-8') as f:
                    json.dump(smtp_config, f, indent=2, ensure_ascii=False)
                
                # Configurar notificador
                self.notifier.configure(smtp_config)
                
                logger.info("Configuración SMTP guardada")
            
            # Guardar configuración de notificaciones
            notify_config = {
                'notify_on_error': self.notify_on_error.isChecked(),
                'notify_on_validation': self.notify_on_validation.isChecked(),
                'notify_daily_summary': self.notify_daily_summary.isChecked(),
            }
            
            notify_config_path = os.path.join(self.persistence.base_path, 'notification_config.json')
            
            with open(notify_config_path, 'w', encoding='utf-8') as f:
                json.dump(notify_config, f, indent=2, ensure_ascii=False)
            
            logger.info("Configuración de notificaciones guardada")
            
            # Guardar destinatarios
            recipients = []
            
            for row in range(self.recipients_table.rowCount()):
                email = self.recipients_table.item(row, 0).text()
                recipients.append(email)
            
            email_config = {
                'recipients': recipients
            }
            
            self.persistence.save_email_config(email_config)
            
            logger.info(f"Guardados {len(recipients)} destinatarios")
            
            # Emitir señal
            self.config_saved.emit()
            
            QMessageBox.information(self, "Información", "Configuración guardada correctamente")
            
        except Exception as e:
            logger.error(f"Error al guardar configuración: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error al guardar configuración: {str(e)}")
    
    def _test_smtp_connection(self):
        """Prueba la conexión SMTP"""
        # Obtener datos de configuración
        smtp_config = {
            'server': self.smtp_server.text().strip(),
            'port': self.smtp_port.value(),
            'use_tls': self.smtp_use_tls.isChecked(),
            'username': self.smtp_username.text().strip(),
            'password': self.smtp_password.text().strip(),
            'from_email': self.from_email.text().strip() or self.smtp_username.text().strip(),
        }
        
        # Validar datos mínimos
        if not smtp_config['server']:
            QMessageBox.warning(self, "Información", "Especifique el servidor SMTP")
            return
        
        if not smtp_config['username'] or not smtp_config['password']:
            QMessageBox.warning(self, "Información", "Especifique usuario y contraseña")
            return
        
        try:
            # Configurar notificador con estos valores
            self.notifier.configure(smtp_config)
            
            # Enviar correo de prueba
            test_subject = "Prueba de Conexión SMTP"
            test_content = "Este es un correo de prueba enviado desde el Monitor de Servicios SOAP."
            
            # Obtener destinatarios de prueba
            test_recipients = []
            
            if self.recipients_table.rowCount() > 0:
                # Usar el primer destinatario configurado
                test_recipients.append(self.recipients_table.item(0, 0).text())
            else:
                # Usar el email del remitente
                test_recipients.append(smtp_config['from_email'])
            
            # Enviar correo
            success = self.notifier.send_notification(
                test_recipients, test_subject, test_content
            )
            
            if success:
                QMessageBox.information(
                    self, "Información", 
                    f"Conexión exitosa. Correo de prueba enviado a {test_recipients[0]}"
                )
                logger.info(f"Correo de prueba enviado a {test_recipients[0]}")
            else:
                QMessageBox.warning(
                    self, "Advertencia", 
                    "No se pudo enviar el correo de prueba. Verifique la configuración."
                )
                logger.warning("No se pudo enviar el correo de prueba")
            
        except Exception as e:
            logger.error(f"Error en prueba SMTP: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error en la conexión: {str(e)}")
            
    def get_email_recipients(self) -> List[str]:
        """
        Obtiene la lista de destinatarios de correo.
        
        Returns:
            List[str]: Lista de direcciones de correo
        """
        recipients = []
        
        for row in range(self.recipients_table.rowCount()):
            email = self.recipients_table.item(row, 0).text()
            recipients.append(email)
        
        return recipients