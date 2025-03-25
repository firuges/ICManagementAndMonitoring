import os
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QMenu,
    QCheckBox, QSpinBox, QComboBox, QGroupBox, QSplitter, QTextBrowser,
    QDialog, QTextEdit, QDialogButtonBox, QApplication, QProgressBar,QProgressDialog
    
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QEventLoop, QSize, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QFont, QIcon, QMovie

# Importar módulos de la aplicación
from core.persistence import PersistenceManager
from core.soap_client import SOAPClient
from core.scheduler import SOAPMonitorScheduler
from core.rest_client import RESTClient
from core.notification import EmailNotifier

# Constantes de estado - añadir al inicio de la clase MonitoringPanel
STATUS_IDLE = 0
STATUS_CHECKING = 1
STATUS_OK = 2
STATUS_WARNING = 3
STATUS_ERROR = 4

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('monitoring_panel')

class MonitoringPanel(QWidget):
    """Panel de monitoreo de servicios SOAP"""
    
    def __init__(self, persistence: PersistenceManager, soap_client: SOAPClient, 
                scheduler: SOAPMonitorScheduler):
        """
        Inicializa el panel de monitoreo.
        
        Args:
            persistence (PersistenceManager): Gestor de persistencia
            soap_client (SOAPClient): Cliente SOAP
            scheduler (SOAPMonitorScheduler): Programador de tareas
        """
        super().__init__()
        
        self.persistence = persistence
        self.soap_client = soap_client
        self.scheduler = scheduler
        self.rest_client = RESTClient()
        self.notifier = EmailNotifier()
        self.selected_service = None 
        
        # Cargar configuración SMTP
        self._load_smtp_config()
        
        # Crear interfaz
        self._create_ui()
        
        # Cargar lista de servicios
        self.refresh_services_list()
        
        # Crear temporizador para actualizar lista
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_services_list)
        self.refresh_timer.start(30000)  # Actualizar cada 30 segundos
        
        logger.info("Panel de monitoreo inicializado")
    
    def _create_ui(self):
        """Crea la interfaz de usuario"""
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # Estilos CSS generales
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                background-color: #f9f9f9;
            }
            QPushButton {
                background-color: #4a86e8;
                color: white;
                border: none;
                padding: 6px 10px;
                border-radius: 4px;
                min-height: 25px;
            }
            QPushButton:hover {
                background-color: #3a76d8;
            }
            QPushButton:pressed {
                background-color: #2a66c8;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
            QTableWidget {
                gridline-color: #e0e0e0;
                selection-background-color: #e8f0ff;
                selection-color: black;
            }
            QHeaderView::section {
                background-color: #f0f0f2;
                padding: 5px;
                border: 1px solid #d0d0d0;
                font-weight: bold;
            }
            QTextBrowser {
                border: 1px solid #cccccc;
                border-radius: 3px;
            }
            QComboBox {
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 3px;
                min-height: 25px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #cccccc;
            }
        """)
        
        # Sección superior (tabla y detalles)
        upper_section = QSplitter(Qt.Horizontal)
        
        # PANEL IZQUIERDO: Tabla de servicios
        services_widget = QWidget()
        services_layout = QVBoxLayout()
        services_widget.setLayout(services_layout)
        
        # Título con estilo
        title_label = QLabel("<h2>Servicios Monitoreados</h2>")
        title_label.setStyleSheet("color: #2d2d2d; margin-bottom: 10px;")
        services_layout.addWidget(title_label)
        
        # Filtro de grupos con estilo mejorado
        filter_container = QGroupBox("Filtros")
        filter_layout = QHBoxLayout()
        filter_container.setLayout(filter_layout)
        
        filter_layout.addWidget(QLabel("Grupo:"))
        
        self.group_filter = QComboBox()
        self.group_filter.addItem("Todos los grupos")
        self.group_filter.setMinimumWidth(180)
        self.group_filter.currentIndexChanged.connect(self._filter_by_group)
        filter_layout.addWidget(self.group_filter)
        
        # Agregar botón de restablecer filtros
        reset_filter_btn = QPushButton("Restablecer")
        reset_filter_btn.setProperty("secondary", True)
        reset_filter_btn.setStyleSheet("""
            QPushButton[secondary="true"] {
                background-color: #f0f0f0;
                color: #333333;
                border: 1px solid #d0d0d0;
            }
            QPushButton[secondary="true"]:hover {
                background-color: #e0e0e0;
            }
        """)
        reset_filter_btn.clicked.connect(self._reset_filters)
        filter_layout.addWidget(reset_filter_btn)
        
        filter_layout.addStretch()
        services_layout.addWidget(filter_container)
        
        # Tabla de servicios
        self.services_table = QTableWidget(0, 6)
        self.services_table.setHorizontalHeaderLabels([
            "Servicio", "Tipo", "Estado", "Última Verificación", "Intervalo", "Acciones"
        ])
        self.services_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.services_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.services_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.services_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.services_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.services_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.services_table.setColumnWidth(5, 120)
        self.services_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.services_table.setSelectionMode(QTableWidget.SingleSelection)
        self.services_table.itemClicked.connect(self._on_service_selected)
        self.services_table.setAlternatingRowColors(True)
        services_layout.addWidget(self.services_table)
        
        table_buttons_layout = QHBoxLayout()
        
        self.btn_refresh = QPushButton("Actualizar")
        self.btn_refresh.setIcon(QIcon.fromTheme("view-refresh", QIcon()))
        self.btn_refresh.clicked.connect(self.refresh_services_list)
        table_buttons_layout.addWidget(self.btn_refresh)
        
        self.btn_check_all = QPushButton("Verificar Grupo")
        self.btn_check_all.setIcon(QIcon.fromTheme("system-run", QIcon()))
        self.btn_check_all.setToolTip("Verificar todos los servicios en el grupo seleccionado")
        self.btn_check_all.clicked.connect(self.check_all_services)
        table_buttons_layout.addWidget(self.btn_check_all)
        
        services_layout.addLayout(table_buttons_layout)
        
        # PANEL DERECHO: Detalles del servicio
        details_widget = QWidget()
        details_layout = QVBoxLayout()
        details_widget.setLayout(details_layout)
        
        details_title = QLabel("<h2>Detalles del Servicio</h2>")
        details_title.setStyleSheet("color: #2d2d2d; margin-bottom: 10px;")
        details_layout.addWidget(details_title)
        
        # Información del servicio
        info_group = QGroupBox("Información general")
        info_layout = QVBoxLayout()
        info_group.setLayout(info_layout)
        
        self.service_info = QTextBrowser()
        self.service_info.setOpenExternalLinks(False)
        info_layout.addWidget(self.service_info)
        
        details_layout.addWidget(info_group)
        
        # Última respuesta
        response_group = QGroupBox("Última Respuesta")
        response_layout = QVBoxLayout()
        response_group.setLayout(response_layout)
        
        self.service_response = QTextBrowser()
        self.service_response.setFont(QFont("Courier New", 10))
        response_layout.addWidget(self.service_response)
        
        details_layout.addWidget(response_group)
        
        # Botones de diagnóstico
        diagnostics_layout = QHBoxLayout()
        
        self.btn_show_structure = QPushButton("Diagnóstico")
        self.btn_show_structure.setIcon(QIcon.fromTheme("utilities-system-monitor", QIcon()))
        self.btn_show_structure.setToolTip("Muestra la estructura detallada de la respuesta para diagnóstico")
        self.btn_show_structure.clicked.connect(self._show_response_structure)
        diagnostics_layout.addWidget(self.btn_show_structure)
        
        self.btn_view_xml = QPushButton("Ver XML")
        self.btn_view_xml.setIcon(QIcon.fromTheme("text-xml", QIcon()))
        self.btn_view_xml.setToolTip("Muestra el XML de respuesta original")
        self.btn_view_xml.clicked.connect(self._view_response_xml)
        diagnostics_layout.addWidget(self.btn_view_xml)
        
        details_layout.addLayout(diagnostics_layout)
        
        # Añadir panels al splitter
        upper_section.addWidget(services_widget)
        upper_section.addWidget(details_widget)
        upper_section.setSizes([600, 400])
        
        main_layout.addWidget(upper_section, 3)
        
        # Sección inferior (log de eventos)
        log_group = QGroupBox("Log de Eventos")
        log_layout = QVBoxLayout()
        log_group.setLayout(log_layout)
        
        self.event_log = QTextBrowser()
        self.event_log.setMaximumHeight(150)
        self.event_log.setFont(QFont("Courier New", 9))
        log_layout.addWidget(self.event_log)
        
        # Botones de log
        log_buttons_layout = QHBoxLayout()
        self.btn_clear_log = QPushButton("Limpiar Log")
        self.btn_clear_log.setProperty("secondary", True)
        self.btn_clear_log.setStyleSheet("""
            QPushButton[secondary="true"] {
                background-color: #f0f0f0;
                color: #333333;
                border: 1px solid #d0d0d0;
            }
            QPushButton[secondary="true"]:hover {
                background-color: #e0e0e0;
            }
        """)
        self.btn_clear_log.clicked.connect(self.event_log.clear)
        log_buttons_layout.addWidget(self.btn_clear_log)
        
        log_layout.addLayout(log_buttons_layout)
        
        main_layout.addWidget(log_group, 1)

    def _load_smtp_config(self):
        """Carga la configuración SMTP para notificaciones"""
        try:
            # Verificar si existe archivo de configuración SMTP
            smtp_config_path = os.path.join(self.persistence.base_path, 'smtp_config.json')
            
            if os.path.exists(smtp_config_path):
                with open(smtp_config_path, 'r', encoding='utf-8') as f:
                    smtp_config = json.load(f)
                
                # Configurar notificador
                self.notifier.configure(smtp_config)
                logger.info("Configuración SMTP cargada correctamente")
            else:
                logger.warning("No se encontró archivo de configuración SMTP")
                
            # Cargar política de notificaciones
            notify_config_path = os.path.join(self.persistence.base_path, 'notification_config.json')
            
            if os.path.exists(notify_config_path):
                with open(notify_config_path, 'r', encoding='utf-8') as f:
                    self.notify_config = json.load(f)
                logger.info("Configuración de notificaciones cargada correctamente")
            else:
                # Usar valores predeterminados
                self.notify_config = {
                    'notify_on_error': True,
                    'notify_on_validation': True,
                    'notify_daily_summary': False,
                }
                logger.warning("Usando configuración de notificaciones por defecto")
                
        except Exception as e:
            logger.error(f"Error al cargar configuración de notificaciones: {str(e)}")
            self.notify_config = {
                'notify_on_error': True,
                'notify_on_validation': True,
                'notify_daily_summary': False,
            }
    
    def _send_notification(self, service_name: str, error_details: Dict[str, Any], level: str = 'error'):
        """
        Envía una notificación de error por correo electrónico si está habilitado.
        
        Args:
            service_name (str): Nombre del servicio con error
            error_details (Dict[str, Any]): Detalles del error
            level (str): Nivel de error ('error', 'validation', etc.)
        """
        try:
            # Verificar política de notificaciones
            should_notify = False
            
            if level == 'error' and self.notify_config.get('notify_on_error', True):
                should_notify = True
            elif level == 'validation' and self.notify_config.get('notify_on_validation', True):
                should_notify = True
            elif level == 'warning' and self.notify_config.get('notify_on_validation', True):
                should_notify = True
            
            if not should_notify:
                logger.info(f"Notificación no enviada para {service_name} (nivel: {level}) según política configurada")
                return False
            
            # Cargar lista de destinatarios
            email_config = self.persistence.load_email_config()
            recipients = email_config.get('recipients', [])
            
            if not recipients:
                logger.warning("No hay destinatarios configurados para notificaciones")
                return False
            
            # Obtener más detalles del servicio
            service_data = None
            try:
                service_data = self.persistence.load_soap_request(service_name)
            except:
                pass
                
            # Mejorar detalles del error
            error_data = error_details.copy()
            
            if service_data:
                error_data['type'] = service_data.get('type', 'SOAP')
                error_data['group'] = service_data.get('group', 'General')
                
            if not error_data.get('timestamp'):
                error_data['timestamp'] = datetime.now().isoformat()
            
            # Enviar notificación
            result = self.notifier.send_service_failure_notification(recipients, service_name, error_data)
            
            if result:
                self._log_event(f"Notificación enviada para {service_name}")
                return True
            else:
                self._log_event(f"Error al enviar notificación para {service_name}", "warning")
                return False
                
        except Exception as e:
            logger.error(f"Error al procesar notificación: {str(e)}")
            self._log_event(f"Error al procesar notificación: {str(e)}", "error")
            return False
    
    def _reset_filters(self):
        """Restablece todos los filtros aplicados"""
        # Restablecer filtro de grupo
        index = self.group_filter.findText("Todos los grupos")
        if index >= 0:
            self.group_filter.setCurrentIndex(index)
        
        # Mostrar todas las filas
        for row in range(self.services_table.rowCount()):
            self.services_table.setRowHidden(row, False)
        
        self._log_event("Filtros restablecidos")
        
    def _filter_by_group(self):
        """Filtra los servicios por grupo seleccionado"""
        selected_group = self.group_filter.currentText()
        
        # Actualizar texto del botón de verificar
        if selected_group == "Todos los grupos":
            self.btn_check_all.setText("Verificar Todos")
            # Mostrar todas las filas
            for row in range(self.services_table.rowCount()):
                self.services_table.setRowHidden(row, False)
            self._log_event("Mostrando todos los servicios")
            return
        else:
            self.btn_check_all.setText(f"Verificar '{selected_group}'")
        
        # Contar servicios visibles
        shown_count = 0
        
        # Ocultar filas que no pertenecen al grupo seleccionado
        for row in range(self.services_table.rowCount()):
            item = self.services_table.item(row, 0)
            if item:
                service_data = item.data(Qt.UserRole)
                service_group = service_data.get('group', 'General')
                
                # Ocultar o mostrar según el grupo
                is_hidden = service_group != selected_group
                self.services_table.setRowHidden(row, is_hidden)
                
                if not is_hidden:
                    shown_count += 1
        
        self._log_event(f"Filtrado por grupo '{selected_group}': {shown_count} servicios")
    
    
    def _show_response_structure(self):
        """Muestra la estructura detallada de la respuesta para diagnóstico"""
        if not self.selected_service:
            QMessageBox.information(self, "Información", "Seleccione un servicio primero")
            return
            
        # Verificar si hay respuesta
        if 'last_response' not in self.selected_service:
            QMessageBox.information(self, "Información", "No hay respuesta disponible")
            return
        
        try:
            # Obtener datos de respuesta
            response = self.selected_service.get('last_response', {}).get('response', {})
            
            # Crear cliente SOAP para usar sus métodos
            from core.soap_client import SOAPClient
            soap_client = SOAPClient()
            
            # Obtener estructura aplanada
            flat_structure = soap_client._flatten_dict(response)
            
            dialog = QDialog(self)
            self._style_dialog(dialog, "Estructura de Respuesta - Diagnóstico", 800, 600)
            
            layout = QVBoxLayout()
            dialog.setLayout(layout)
            
            # Título con estilo
            title_label = QLabel(f"Diagnóstico de Respuesta: {self.selected_service.get('name')}")
            title_label.setProperty("title", True)
            layout.addWidget(title_label)
            
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setFontFamily("Courier New")
            
            # Formatear texto
            text = "ESTRUCTURA DETALLADA DE RESPUESTA\n"
            text += "=================================\n\n"
            text += f"Servicio: {self.selected_service.get('name')}\n"
            text += f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            # Añadir estructura completa
            text += "ESTRUCTURA JERÁRQUICA:\n"
            text += soap_client.dump_object_structure(response)
            
            text += "\n\nESTRUCTURA APLANADA:\n"
            for key in sorted(flat_structure.keys()):
                value = flat_structure[key]
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:100] + "..."
                text += f"{key} = {value_str}\n"
            
            text_edit.setText(text)
            layout.addWidget(text_edit)
            
            # Botones para cerrar y copiar
            buttons_layout = QHBoxLayout()
            
            copy_btn = QPushButton("Copiar al Portapapeles")
            copy_btn.setIcon(QIcon.fromTheme("edit-copy", QIcon()))
            copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(text_edit.toPlainText()))
            buttons_layout.addWidget(copy_btn)
            
            buttons_layout.addStretch()
            
            close_btn = QPushButton("Cerrar")
            close_btn.clicked.connect(dialog.accept)
            buttons_layout.addWidget(close_btn)
            
            layout.addLayout(buttons_layout)
            
            dialog.exec_()
            
        except Exception as e:
            logger.error(f"Error mostrando estructura: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error al mostrar estructura: {str(e)}")
        
    def _view_response_xml(self):
        """Muestra el XML de respuesta original si está disponible"""
        if not self.selected_service:
            QMessageBox.information(self, "Información", "Seleccione un servicio primero")
            return
        
        try:
            # Buscar archivos XML de respuesta para este servicio
            debug_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'debug')
            service_name = self.selected_service.get('name', '')
            
            xml_files = []
            if os.path.exists(debug_dir):
                for filename in os.listdir(debug_dir):
                    if filename.endswith('_response.xml') and (service_name.lower() in filename.lower() or 
                                                            'direct_call' in filename.lower()):
                        xml_files.append(os.path.join(debug_dir, filename))
            
            if not xml_files:
                QMessageBox.information(self, "Información", "No se encontraron archivos XML de respuesta para este servicio")
                return
            
            # Ordenar por fecha (más reciente primero)
            xml_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            # Leer el XML más reciente
            with open(xml_files[0], 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # Crear ventana de diálogo para mostrar XML
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QApplication
            from PyQt5.QtCore import Qt
            
            dialog = QDialog(self)
            self._style_dialog(dialog, f"XML de Respuesta - {os.path.basename(xml_files[0])}", 800, 600)
            
            layout = QVBoxLayout()
            dialog.setLayout(layout)
            
            # Título con estilo
            title_label = QLabel(f"XML de respuesta: {self.selected_service.get('name')}")
            title_label.setProperty("title", True)
            layout.addWidget(title_label)
            
            # Campo de texto formateado
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setFontFamily("Courier New")
            
            # Formatear el XML para mejor legibilidad
            try:
                import xml.dom.minidom as md
                pretty_xml = md.parseString(xml_content).toprettyxml(indent="  ")
                text_edit.setText(pretty_xml)
            except:
                # Si falla el formateo, mostrar como está
                text_edit.setText(xml_content)
                
            layout.addWidget(text_edit)
            
            # Botones para cerrar y copiar
            buttons_layout = QHBoxLayout()
            
            copy_btn = QPushButton("Copiar al Portapapeles")
            copy_btn.setIcon(QIcon.fromTheme("edit-copy", QIcon()))
            copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(text_edit.toPlainText()))
            buttons_layout.addWidget(copy_btn)
            
            buttons_layout.addStretch()
            
            close_btn = QPushButton("Cerrar")
            close_btn.clicked.connect(dialog.accept)
            buttons_layout.addWidget(close_btn)
            
            layout.addLayout(buttons_layout)
            
            dialog.exec_()
            
        except Exception as e:
            logger.error(f"Error mostrando XML: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error al mostrar XML: {str(e)}")
    
    def _safe_serialize_response(self, response_data):
        """
        Serializa de forma segura respuestas complejas con manejo especial para tipos problemáticos.
        
        Args:
            response_data: Datos de respuesta a serializar
            
        Returns:
            str: Representación JSON o textual de los datos
        """
        try:
            # Implementar una conversión recursiva manual
            def convert_for_json(obj):
                if isinstance(obj, (datetime, datetime.date)):
                    return obj.isoformat()
                elif isinstance(obj, dict):
                    return {k: convert_for_json(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_for_json(i) for i in obj]
                elif hasattr(obj, '__dict__'):  # Para objetos personalizados
                    return convert_for_json(obj.__dict__)
                else:
                    return str(obj)  # Convertir cualquier otro tipo a string
            
            # Convertir el objeto completo
            safe_data = convert_for_json(response_data)
            
            # Intentar serializar el objeto convertido
            return json.dumps(safe_data, indent=2)
        except Exception as e:
            logger.error(f"Error en serialización de seguridad: {str(e)}")
            # Último recurso: convertir a string directamente
            return f"Respuesta recibida (no serializable a JSON):\n{str(response_data)}"
        
    
    def refresh_services_list(self):
        """Actualiza la lista de servicios manteniendo el filtro actual"""
        try:
            # Log detallado para diagnóstico
            logger.info("Iniciando actualización de lista de servicios")
            
            # Guardar grupo seleccionado y servicio seleccionado actual
            current_group = self.group_filter.currentText()
            selected_service_name = None
            if self.selected_service:
                selected_service_name = self.selected_service.get('name')
            
            # Obtener lista de servicios
            requests = self.persistence.list_all_requests()
            logger.info(f"Servicios encontrados: {len(requests)}")
            
            # Actualizar conjunto de grupos
            groups = set(["Todos los grupos"])
            for req in requests:
                if 'group' in req and req['group']:
                    groups.add(req['group'])
            
            # Guardar índice actual del combo para restaurarlo después
            current_group_index = self.group_filter.currentIndex()
            
            # Actualizar combo de grupos preservando la selección
            self.group_filter.blockSignals(True)  # Evitar que se dispare evento de cambio
            self.group_filter.clear()
            self.group_filter.addItems(sorted(list(groups)))
            
            # Restaurar grupo seleccionado
            new_index = self.group_filter.findText(current_group)
            if new_index >= 0:
                self.group_filter.setCurrentIndex(new_index)
            self.group_filter.blockSignals(False)
            
            # Guardar la fila seleccionada actualmente
            current_row = -1
            
            # Limpiar tabla
            self.services_table.setRowCount(0)
            
            # Llenar tabla con servicios
            for i, request in enumerate(sorted(requests, key=lambda x: x.get('name', ''))):
                # VERIFICACIÓN: Asegurar campos mínimos
                if 'name' not in request or not request.get('name'):
                    logger.warning(f"Servicio sin nombre detectado, ignorando: {request}")
                    continue
                    
                self.services_table.insertRow(i)
                
                # Nombre del servicio con CustomTableWidgetItem
                name_item = CustomTableWidgetItem(request.get('name', 'Sin nombre'))
                name_item.setData(Qt.UserRole, request)  # Almacenar datos completos
                
                # Verificar si el servicio está siendo verificado actualmente
                if hasattr(self, '_checking_services') and request.get('name') in self._checking_services:
                    name_item.setStatus(STATUS_CHECKING)
                
                self.services_table.setItem(i, 0, name_item)
                
                # Agregar columna de tipo (SOAP/REST)
                service_type = request.get('type', 'SOAP')
                type_item = QTableWidgetItem(service_type)
                # Dar estilo visual según el tipo
                if service_type == 'REST':
                    type_item.setBackground(QBrush(QColor(230, 245, 255)))  # Azul claro para REST
                else:
                    type_item.setBackground(QBrush(QColor(240, 255, 240)))  # Verde claro para SOAP
                self.services_table.setItem(i, 1, type_item)
                
                # Estado con estilos mejorados
                status = request.get('status', 'sin verificar')
                status_item = QTableWidgetItem(status)
                
                # Colorear según estado
                if status == 'ok':
                    status_item.setBackground(QBrush(QColor(200, 255, 200)))  # Verde claro
                    status_item.setForeground(QBrush(QColor(0, 120, 0)))      # Texto verde oscuro
                    status_item.setFont(QFont("Arial", 9, QFont.Bold))
                elif status == 'warning':
                    status_item.setBackground(QBrush(QColor(255, 240, 180)))  # Amarillo suave
                    status_item.setForeground(QBrush(QColor(150, 100, 0)))    # Texto marrón
                    status_item.setFont(QFont("Arial", 9, QFont.Bold))
                elif status == 'failed':
                    status_item.setBackground(QBrush(QColor(255, 200, 200)))  # Rojo suave
                    status_item.setForeground(QBrush(QColor(180, 0, 0)))      # Texto rojo
                    status_item.setFont(QFont("Arial", 9, QFont.Bold))
                elif status == 'error':
                    status_item.setBackground(QBrush(QColor(255, 200, 200)))  # Rojo suave
                    status_item.setForeground(QBrush(QColor(180, 0, 0)))      # Texto rojo
                    status_item.setFont(QFont("Arial", 9, QFont.Bold))
                elif status == 'invalid':
                    status_item.setBackground(QBrush(QColor(255, 220, 200)))  # Naranja suave
                    status_item.setForeground(QBrush(QColor(200, 100, 0)))    # Texto naranja oscuro
                    status_item.setFont(QFont("Arial", 9, QFont.Bold))
                else:
                    # Sin verificar u otros estados
                    status_item.setBackground(QBrush(QColor(240, 240, 240)))  # Gris claro
                    status_item.setForeground(QBrush(QColor(100, 100, 100)))  # Texto gris
                
                self.services_table.setItem(i, 2, status_item)
                
                # Última verificación
                last_checked = request.get('last_checked', '')
                
                if last_checked:
                    try:
                        dt = datetime.fromisoformat(last_checked)
                        last_checked = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except Exception as e:
                        logger.warning(f"Error al formatear fecha: {str(e)}")
                        # Mantener el valor original si hay error
                
                self.services_table.setItem(i, 3, QTableWidgetItem(last_checked))
                
                # Intervalo - Ahora en columna 4
                interval = request.get('monitor_interval', 15)
                self.services_table.setItem(i, 4, QTableWidgetItem(f"{interval} min"))
                
                # Modificar la celda de acciones para incluir múltiples botones
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(2, 2, 2, 2)
                actions_layout.setSpacing(2)
                
                check_button = QPushButton("Verificar")
                check_button.setMaximumWidth(80)
                check_button.clicked.connect(lambda checked, name=request.get('name'): 
                                            self.check_service(name))
                
                diagnostic_button = QPushButton("Diagnóstico")
                diagnostic_button.setMaximumWidth(80)
                diagnostic_button.clicked.connect(lambda checked, name=request.get('name'): 
                                                self._diagnose_connection(name))

                
                # Botón de Enable/Disable con mejor estilo visual
                is_enabled = request.get('monitor_enabled', True)
                toggle_button = QPushButton()
                toggle_button.setMaximumWidth(30)
                toggle_button.setToolTip("Habilitar/Deshabilitar monitoreo")
                
                # Establecer estilo según estado
                if is_enabled:
                    toggle_button.setText("✓")
                    toggle_button.setStyleSheet("""
                        background-color: #8CED99;
                        border-radius: 4px;
                        font-weight: bold;
                        color: #006400;
                    """)
                else:
                    toggle_button.setText("✗")
                    toggle_button.setStyleSheet("""
                        background-color: #FF9B9B;
                        border-radius: 4px;
                        font-weight: bold;
                        color: #8B0000;
                    """)
                
                toggle_button.clicked.connect(lambda checked, name=request.get('name'): 
                                            self._toggle_service_status(name))
                
                # Añadir botones al layout
                actions_layout.addWidget(check_button)
                actions_layout.addWidget(toggle_button)
                actions_layout.addWidget(diagnostic_button)
                
                
                # Ajustar propiedades del widget
                actions_widget.setLayout(actions_layout)
                self.services_table.setCellWidget(i, 5, actions_widget)
                
                # Si este es el servicio que estaba seleccionado, guardar índice
                if selected_service_name and request.get('name') == selected_service_name:
                    current_row = i
                    logger.debug(f"Servicio anteriormente seleccionado encontrado: {selected_service_name}")
            
            # Restaurar selección si es posible
            if current_row >= 0 and current_row < self.services_table.rowCount():
                self.services_table.selectRow(current_row)
                self._on_service_selected(self.services_table.item(current_row, 0))
                logger.debug(f"Restaurada selección: fila {current_row}")
            else:
                # Limpiar detalles
                self.selected_service = None
                self.service_info.clear()
                self.service_response.clear()
                logger.debug("No se pudo restaurar selección, detalles limpiados")
            
            # Aplicar filtro de grupo si no es "Todos los grupos"
            if current_group != "Todos los grupos":
                self._filter_by_group()
                
            # Actualizar botón de Verificar Grupo
            if current_group == "Todos los grupos":
                self.btn_check_all.setText("Verificar Todos")
            else:
                self.btn_check_all.setText(f"Verificar '{current_group}'")
            
            self._log_event(f"Lista de servicios actualizada. {len(requests)} servicios cargados.")
            
        except Exception as e:
            logger.error(f"Error crítico al actualizar lista de servicios: {str(e)}", exc_info=True)
            self._log_event(f"Error al actualizar lista: {str(e)}", "error")
    
    def _toggle_service_status(self, service_name: str):
        """Habilita o deshabilita el monitoreo de un servicio"""
        try:
            # Cargar datos del servicio
            service_data = self.persistence.load_soap_request(service_name)
            
            if not service_data:
                self._log_event(f"Error: No se pudo cargar servicio {service_name}", "error")
                return
            
            # Cambiar estado de monitoreo
            is_enabled = service_data.get('monitor_enabled', True)
            service_data['monitor_enabled'] = not is_enabled
            
            # Guardar cambios
            self.persistence.save_service_request(service_data)
            
            # Actualizar vista
            self.refresh_services_list()
            
            # Actualizar programación si corresponde
            if service_data['monitor_enabled']:
                self._log_event(f"Servicio {service_name} habilitado para monitoreo", "info")
                # Si también está configurado para sistema, actualizar
                if service_data.get('add_to_system', False):
                    if self.scheduler.generate_system_task(service_name, service_data.get('monitor_interval', 15)):
                        self._log_event(f"Tarea del sistema actualizada para {service_name}", "info")
            else:
                self._log_event(f"Servicio {service_name} deshabilitado para monitoreo", "info")
                # Eliminar tarea del sistema si existe
                if service_data.get('add_to_system', False):
                    if self.scheduler.remove_system_task(service_name):
                        self._log_event(f"Tarea del sistema eliminada para {service_name}", "info")
            
        except Exception as e:
            logger.error(f"Error al cambiar estado de servicio {service_name}: {str(e)}")
            self._log_event(f"Error al cambiar estado: {str(e)}", "error")
    
    def _on_service_selected(self, item):
        """
        Manejador para selección de servicio en la tabla.
        
        Args:
            item (QTableWidgetItem): Elemento seleccionado
        """
        if item is None:
            return
        
        # Obtener datos del servicio
        service_data = item.data(Qt.UserRole)
        self.selected_service = service_data
        
        # Mostrar información en panel de detalles
        self._display_service_details(service_data)
    
    def _display_service_details(self, service_data: Dict[str, Any]):
        """
        Muestra los detalles de un servicio.
        
        Args:
            service_data (Dict[str, Any]): Datos del servicio
        """
        if not service_data:
            return
        
        # Añadir información de monitoreo
        
        
        # Determinar tipo de servicio
        service_type = service_data.get('type', 'SOAP')
        
        # Construir HTML con detalles y estilos mejorados
        html = """
        <style>
        body { 
            font-family: Arial, sans-serif; 
            color: #333333;
            margin: 0;
            padding: 10px;
        }
        h3 { 
            color: #2d2d2d; 
            border-bottom: 1px solid #e0e0e0;
            padding-bottom: 5px;
            margin-bottom: 15px;
        }
        .container {
            background-color: #f9f9f9;
            border: 1px solid #e0e0e0;
            border-radius: 5px;
            padding: 10px;
            margin-bottom: 15px;
        }
        .label { 
            font-weight: bold; 
            color: #555555;
            width: 140px;
            display: inline-block;
            vertical-align: top;
        }
        .value { 
            display: inline-block;
            margin-left: 5px;
            max-width: calc(100% - 150px);
            vertical-align: top;
        }
        .ok { 
            color: #198754; 
            font-weight: bold;
            background-color: #d1e7dd;
            padding: 2px 6px;
            border-radius: 3px;
        }
        .failed { 
            color: #842029; 
            font-weight: bold;
            background-color: #f8d7da;
            padding: 2px 6px;
            border-radius: 3px;
        }
        .error { 
            color: #842029; 
            font-weight: bold;
            background-color: #f8d7da;
            padding: 2px 6px;
            border-radius: 3px;
        }
        .warning { 
            color: #664d03; 
            font-weight: bold;
            background-color: #fff3cd;
            padding: 2px 6px;
            border-radius: 3px;
        }
        .invalid { 
            color: #6c4a00; 
            font-weight: bold;
            background-color: #ffe5d0;
            padding: 2px 6px;
            border-radius: 3px;
        }
        .unknown { 
            color: #41464b; 
            font-weight: bold;
            background-color: #e2e3e5;
            padding: 2px 6px;
            border-radius: 3px;
        }
        .badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.9em;
        }
        .badge-soap {
            background-color: #e0f7ea;
            color: #0d6832;
        }
        .badge-rest {
            background-color: #e1f0ff;
            color: #0a55a5;
        }
        .monitoreo-on {
            background-color: #d1e7dd;
            color: #0f5132;
        }
        .monitoreo-off {
            background-color: #f8d7da;
            color: #842029;
        }
        </style>
        """
        
        html += f"<h3>{service_data.get('name', 'Sin nombre')}</h3>"
        
        html += "<div class='container'>"
        
        # Primera fila: Grupo y Tipo
        html += "<p>"
        html += f"<span class='label'>Grupo:</span>"
        html += f"<span class='value'>{service_data.get('group', 'General')}</span>"
        html += "</p>"
        
        # Tipo de servicio con badge
        html += "<p>"
        html += f"<span class='label'>Tipo:</span>"
        if service_type == 'SOAP':
            html += f"<span class='value'><span class='badge badge-soap'>SOAP</span></span>"
        else:
            html += f"<span class='value'><span class='badge badge-rest'>REST</span></span>"
        html += "</p>"
        
        # Descripción
        html += "<p>"
        html += f"<span class='label'>Descripción:</span>"
        html += f"<span class='value'>{service_data.get('description', 'Sin descripción')}</span>"
        html += "</p>"
        
        # Estado de monitoreo
        monitor_enabled = service_data.get('monitor_enabled', True)
        html += "<p>"
        html += f"<span class='label'>Monitoreo:</span>"
        if monitor_enabled:
            html += f"<span class='value'><span class='badge monitoreo-on'>Habilitado</span></span>"
        else:
            html += f"<span class='value'><span class='badge monitoreo-off'>Deshabilitado</span></span>"
        html += "</p>"
        
        html += "</div>"
        
        # Sección segunda: Detalles técnicos
        html += "<div class='container'>"
        
        # Detalles específicos según tipo
        if service_type == "SOAP":
            # URL WSDL
            html += "<p>"
            html += f"<span class='label'>URL WSDL:</span>"
            html += f"<span class='value'>{service_data.get('wsdl_url', 'No disponible')}</span>"
            html += "</p>"
        else:  # REST
            # URL y método
            html += "<p>"
            html += f"<span class='label'>URL:</span>"
            html += f"<span class='value'>{service_data.get('url', 'No disponible')}</span>"
            html += "</p>"
            
            html += "<p>"
            html += f"<span class='label'>Método:</span>"
            html += f"<span class='value'>{service_data.get('method', 'GET')}</span>"
            html += "</p>"
            
            # Headers (si hay)
            headers = service_data.get('headers', {})
            if headers:
                html += "<p>"
                html += f"<span class='label'>Headers:</span>"
                html += "<span class='value'>"
                for key, value in headers.items():
                    html += f"{key}: {value}<br>"
                html += "</span></p>"
            
            # Params (si hay)
            params = service_data.get('params', {})
            if params:
                html += "<p>"
                html += f"<span class='label'>Parámetros:</span>"
                html += "<span class='value'>"
                for key, value in params.items():
                    html += f"{key}={value}<br>"
                html += "</span></p>"
        
        html += "</div>"
        
        # Sección tercera: Estado y monitoreo
        html += "<div class='container'>"
        
        # Estado
        status = service_data.get('status', 'desconocido')
        status_class = {
            'ok': 'ok',
            'failed': 'failed',
            'error': 'error',
            'warning': 'warning',
            'invalid': 'invalid'
        }.get(status, 'unknown')
        
        html += "<p>"
        html += f"<span class='label'>Estado:</span>"
        html += f"<span class='value {status_class}'>{status.upper()}</span>"
        html += "</p>"
        
        # Última verificación
        last_checked = service_data.get('last_checked', 'Nunca')
        
        if last_checked != 'Nunca':
            try:
                dt = datetime.fromisoformat(last_checked)
                last_checked = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass
        
        html += "<p>"
        html += f"<span class='label'>Última verificación:</span>"
        html += f"<span class='value'>{last_checked}</span>"
        html += "</p>"
        
        # Intervalo de monitoreo
        html += "<p>"
        html += f"<span class='label'>Intervalo de monitoreo:</span>"
        html += f"<span class='value'>{service_data.get('monitor_interval', 15)} minutos</span>"
        html += "</p>"
        
        html += "</div>"
        
        # Si hay error, mostrar detalles en una sección separada
        if status in ['failed', 'error', 'invalid', 'warning'] and 'last_response' in service_data:
            html += "<div class='container' style='border-color: #f0ad4e;'>"
            html += "<h4 style='color: #8a6d3b; margin-top: 0;'>Detalles del diagnóstico</h4>"
            
            if 'error' in service_data['last_response']:
                html += "<p>"
                html += f"<span class='label'>Error:</span>"
                html += f"<span class='value failed'>{service_data['last_response']['error']}</span>"
                html += "</p>"
            
            if 'validation_error' in service_data['last_response']:
                html += "<p>"
                html += f"<span class='label'>Error de validación:</span>"
                html += f"<span class='value invalid'>{service_data['last_response']['validation_error']}</span>"
                html += "</p>"
                
            if 'validation_message' in service_data['last_response']:
                html += "<p>"
                html += f"<span class='label'>Mensaje:</span>"
                html += f"<span class='value warning'>{service_data['last_response']['validation_message']}</span>"
                html += "</p>"
                
            html += "</div>"
        
        # Mostrar información en el panel
        self.service_info.setHtml(html)
        
        # Mostrar última respuesta si existe
        if 'last_response' in service_data and 'response' in service_data['last_response']:
            try:
                from core.soap_client import json_serial
                response_text = json.dumps(
                    service_data['last_response']['response'], 
                    indent=2, 
                    default=json_serial
                )
                self.service_response.setText(response_text)
            except Exception as e:
                # Utilizar serialización segura como fallback
                response_text = self._safe_serialize_response(service_data['last_response']['response'])
                self.service_response.setText(response_text)
        else:
            self.service_response.setText("No hay respuesta disponible")
        
        self._log_event(f"Servicio seleccionado: {service_data.get('name')}")
    
    def check_service(self, service_name: str, show_progress: bool = True):
        """
        Verifica un servicio específico usando un thread en segundo plano.
        
        Args:
            service_name (str): Nombre del servicio a verificar
            show_progress (bool): Si se debe mostrar indicador de progreso
            
        Returns:
            bool: True si la verificación fue iniciada correctamente
        """
        # Evitar verificaciones múltiples simultáneas
        if hasattr(self, '_checking_services') and service_name in self._checking_services:
            self._log_event(f"Servicio {service_name} ya está siendo verificado", "warning")
            return False
        
        # Inicializar diccionario de servicios en verificación si no existe
        if not hasattr(self, '_checking_services'):
            self._checking_services = {}
        
        # Inicializar diccionario de hilos de verificación si no existe
        if not hasattr(self, '_checker_threads'):
            self._checker_threads = {}
        
        self._log_event(f"Verificando servicio: {service_name}")
        
        try:
            # Cargar datos del servicio
            service_data = self.persistence.load_soap_request(service_name)
            
            if not service_data:
                self._log_event(f"Error: No se pudo cargar servicio {service_name}", "error")
                return False
            
            # Buscar la fila correspondiente en la tabla
            service_row = -1
            for row in range(self.services_table.rowCount()):
                item = self.services_table.item(row, 0)
                if item and item.text() == service_name:
                    service_row = row
                    break
            
            if service_row >= 0 and show_progress:
                # Actualizar estado visual a "verificando"
                name_item = self.services_table.item(service_row, 0)
                if isinstance(name_item, CustomTableWidgetItem):
                    name_item.setStatus(STATUS_CHECKING)
                else:
                    # Reemplazar con item personalizado
                    original_text = name_item.text()
                    original_data = name_item.data(Qt.UserRole)
                    
                    new_item = CustomTableWidgetItem(original_text, STATUS_CHECKING)
                    new_item.setData(Qt.UserRole, original_data)
                    
                    self.services_table.setItem(service_row, 0, new_item)
                
                # Actualizar celda de estado con spinner
                status_item = self.services_table.item(service_row, 2)
                if status_item:
                    status_text = status_item.text()
                    
                    # Crear spinner widget
                    spinner = SpinnerWidget()
                    spinner.status_label.setText("Verificando...")
                    spinner.start()
                    
                    # Reemplazar celda con spinner
                    self.services_table.setCellWidget(service_row, 2, spinner)
                
                # Desactivar botón verificar
                actions_widget = self.services_table.cellWidget(service_row, 5)
                if actions_widget:
                    for button in actions_widget.findChildren(QPushButton):
                        if "Verificar" in button.text():
                            button.setEnabled(False)
                            break
            
            # Marcar servicio como en verificación
            self._checking_services[service_name] = {
                'row': service_row,
                'start_time': datetime.now()
            }
            
            # Crear y configurar hilo de verificación
            thread = ServiceCheckerThread(
                self, service_name, service_data, 
                self.soap_client, self.rest_client, self.persistence
            )
            
            # Conectar señales
            thread.finished.connect(self._on_service_check_finished)
            thread.progress.connect(self._on_service_check_progress)
            
            # Guardar referencia al hilo
            self._checker_threads[service_name] = thread
            
            # Iniciar verificación en segundo plano
            thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"Error al iniciar verificación de {service_name}: {str(e)}", exc_info=True)
            self._log_event(f"Error al iniciar verificación de {service_name}: {str(e)}", "error")
            
            # Limpiar estado si hubo error
            if service_name in self._checking_services:
                del self._checking_services[service_name]
            
            return False
        
    # 6. Método para manejar el progreso de verificación
    def _on_service_check_progress(self, service_name, status_message):
        """Maneja actualizaciones de progreso de verificación de servicio"""
        # Registrar mensaje en log de eventos
        self._log_event(f"Servicio {service_name}: {status_message}")
        
        # Actualizar mensaje en spinner si existe
        if service_name in self._checking_services:
            row = self._checking_services[service_name]['row']
            if row >= 0 and row < self.services_table.rowCount():
                spinner = self.services_table.cellWidget(row, 2)
                if spinner and hasattr(spinner, 'status_label'):
                    spinner.status_label.setText(status_message)
    
    # 7. Método para manejar la finalización de verificación
    def _on_service_check_finished(self, service_name, success, message):
        """Maneja la finalización de verificación de servicio"""
        # Registrar resultado en log
        if success:
            self._log_event(f"Servicio {service_name} verificado: {message}")
        else:
            self._log_event(f"Error en servicio {service_name}: {message}", "error")
        
            # Enviar notificación si es un error
            try:
                # Determinar tipo de error
                level = "error"
                if "validación" in message.lower():
                    level = "validation"
                elif "advertencia" in message.lower():
                    level = "warning"
                
                # Obtener detalles
                error_details = {
                    'error': message,
                    'status': 'failed',
                    'timestamp': datetime.now().isoformat()
                }
                
                # Enviar notificación
                self._send_notification(service_name, error_details, level)
            except Exception as e:
                logger.error(f"Error al preparar notificación: {str(e)}")
                
        # Actualizar interfaz
        if service_name in self._checking_services:
            row = self._checking_services[service_name]['row']
            if row >= 0 and row < self.services_table.rowCount():
                # Restaurar celda de estado
                self.services_table.removeCellWidget(row, 2)
                
                # Actualizar estado visual
                name_item = self.services_table.item(row, 0)
                if isinstance(name_item, CustomTableWidgetItem):
                    if success:
                        name_item.setStatus(STATUS_IDLE)  # Restaurar estado normal
                    else:
                        name_item.setStatus(STATUS_ERROR if "Error" in message else STATUS_WARNING)
                
                # Re-habilitar botón verificar
                actions_widget = self.services_table.cellWidget(row, 5)
                if actions_widget:
                    for button in actions_widget.findChildren(QPushButton):
                        if "Verificar" in button.text():
                            button.setEnabled(True)
                            break
        
        # Limpiar referencias
        if service_name in self._checking_services:
            del self._checking_services[service_name]
        
        if service_name in self._checker_threads:
            self._checker_threads[service_name].deleteLater()
            del self._checker_threads[service_name]
        
        # Actualizar la lista de servicios
        self.refresh_services_list()
    
    def _restore_service_from_backup(self, service_name: str, backup_data: Dict[str, Any]) -> bool:
        """
        Restaura un servicio desde datos de respaldo en caso de pérdida.
        
        Args:
            service_name (str): Nombre del servicio
            backup_data (Dict[str, Any]): Datos de respaldo
            
        Returns:
            bool: True si se restauró correctamente
        """
        try:
            if not backup_data:
                logger.error(f"No hay datos de backup para restaurar {service_name}")
                return False
                
            # Guardar directamente usando la función save_service_request
            self.persistence.save_service_request(backup_data)
            logger.info(f"Servicio {service_name} restaurado desde backup")
            self._log_event(f"Servicio {service_name} restaurado automáticamente", "info")
            return True
        except Exception as e:
            logger.error(f"Error al restaurar servicio {service_name}: {str(e)}")
            return False
        
    def check_all_services(self):
        """Verifica todos los servicios del grupo seleccionado"""
        selected_group = self.group_filter.currentText()
        group_filter_active = selected_group != "Todos los grupos"
        
        self._log_event(f"Iniciando verificación de servicios {('del grupo ' + selected_group) if group_filter_active else ''}")
        
        # Desactivar botones durante la verificación
        self.btn_check_all.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        
        try:
            # Obtener lista de servicios
            all_requests  = self.persistence.list_all_requests()
            
            # Filtrar por grupo si es necesario
            if group_filter_active:
                requests_to_check = [r for r in all_requests if r.get('group', 'General') == selected_group and r.get('monitor_enabled', True)]
            else:
                requests_to_check = [r for r in all_requests if r.get('monitor_enabled', True)]
            
            total_services = len(requests_to_check)
            
            if total_services == 0:
                self._log_event("No hay servicios para verificar en este grupo")
                self.btn_check_all.setEnabled(True)
                self.btn_refresh.setEnabled(True)
                return
            
            # Crear diálogo de progreso
            progress = QProgressDialog(f"Verificando servicios {'del grupo ' + selected_group if group_filter_active else ''}...", 
                                    "Cancelar", 0, total_services, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setWindowTitle("Verificando Servicios")
            progress.setMinimumDuration(0)  # Mostrar inmediatamente
            progress.setAutoClose(True)
            progress.setAutoReset(True)
            
            # Contador para estadísticas
            checked = 0
            success = 0
            failed = 0
            
            # Verificar cada servicio
            for i, service in enumerate(requests_to_check):
                service_name = service.get('name')
                
                # Actualizar diálogo de progreso
                progress.setValue(i)
                progress.setLabelText(f"Verificando ({i+1}/{total_services}): {service_name}")
                
                # Si el usuario canceló, salir
                if progress.wasCanceled():
                    self._log_event("Verificación cancelada por el usuario")
                    break
                
                # Verificar el servicio
                if service_name:
                    result = self.check_service(service_name, show_progress=False)  # No mostrar progreso individual
                    checked += 1
                    if result:
                        success += 1
                    else:
                        failed += 1
                
                # Procesar eventos para mantener la UI responsiva
                QApplication.processEvents()
            
            # Completar progreso
            progress.setValue(total_services)
            
            # Registrar estadísticas
            self._log_event(f"Verificación completada: {checked} servicios verificados, {success} exitosos, {failed} con errores")
            
            # Actualizar la lista de servicios
            self.refresh_services_list()
            
        except Exception as e:
            logger.error(f"Error al verificar servicios: {str(e)}")
            self._log_event(f"Error al verificar servicios: {str(e)}", "error")
        finally:
            # Re-habilitar botones
            self.btn_check_all.setEnabled(True)
            self.btn_refresh.setEnabled(True)
    
    def _log_event(self, message: str, level: str = "info"):
        """
        Registra un evento en el log con formato mejorado.
        
        Args:
            message (str): Mensaje a registrar
            level (str): Nivel de log (info, warning, error)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Determinar color e icono según nivel
        styling = {
            "info": {"color": "#0066cc", "icon": "ℹ️", "background": "#f0f7ff"},
            "warning": {"color": "#856404", "icon": "⚠️", "background": "#fff3cd"},
            "error": {"color": "#721c24", "icon": "❌", "background": "#f8d7da"}
        }.get(level, {"color": "black", "icon": "•", "background": "transparent"})
        
        # Crear entrada HTML con estilo mejorado
        html = f"<div style='background-color: {styling['background']}; padding: 3px; margin: 2px 0; border-radius: 3px;'>"
        html += f"<span style='color:gray; font-size: 0.9em;'>[{timestamp}]</span> "
        html += f"<span style='color:{styling['color']}; font-weight: bold;'>{styling['icon']} {message}</span>"
        html += "</div>"
        
        # Añadir al log
        self.event_log.append(html)
        
        # Desplazar al final
        self.event_log.verticalScrollBar().setValue(
            self.event_log.verticalScrollBar().maximum()
        )
        
        # También registrar en el logger del sistema según el nivel
        if level == "warning":
            logger.warning(message)
        elif level == "error":
            logger.error(message)
        else:
            logger.info(message)
        
    def _create_validation_editor(self):
        """Crea un editor avanzado para la configuración de validación"""
        validation_group = QGroupBox("Configuración de Validación Avanzada")
        validation_layout = QVBoxLayout()
        validation_group.setLayout(validation_layout)
        
        # Añadir descripción
        validation_layout.addWidget(QLabel("Defina reglas personalizadas para validar respuestas:"))
        
        # Editor de JSON para configuración avanzada
        self.validation_editor = QTextEdit()
        self.validation_editor.setFont(QFont("Courier New", 10))
        validation_layout.addWidget(self.validation_editor)
        
        # Plantillas predefinidas
        template_layout = QHBoxLayout()
        template_label = QLabel("Plantillas:")
        template_layout.addWidget(template_label)
        
        self.template_combo = QComboBox()
        self.template_combo.addItems([
            "Básica (status: ok)", 
            "Código de mensaje (codMensaje: 00000)",
            "Con advertencias (codMensaje múltiple)",
            "Ruta alternativa",
            "Modo permisivo"
        ])
        self.template_combo.currentIndexChanged.connect(self._apply_validation_template)
        template_layout.addWidget(self.template_combo)
        
        btn_apply_template = QPushButton("Aplicar plantilla")
        btn_apply_template.clicked.connect(self._apply_selected_template)
        template_layout.addWidget(btn_apply_template)
        
        validation_layout.addLayout(template_layout)
        
        return validation_group

    def _apply_selected_template(self):
        """Aplica la plantilla de validación seleccionada"""
        index = self.template_combo.currentIndex()
        self._apply_validation_template(index)

    def _apply_validation_template(self, index):
        """Aplica una plantilla de validación predefinida"""
        templates = [
            # Básica
            {
                "status": "ok"
            },
            
            # Código de mensaje
            {
                "success_field": "codMensaje",
                "success_values": ["00000"],
                "expected_fields": {
                    "fechaProximoCorte": None
                }
            },
            
            # Con advertencias
            {
                "success_field": "codMensaje",
                "success_values": ["00000"],
                "warning_values": ["2001", "2002"],
                "validation_strategy": "flexible"
            },
            
            # Ruta alternativa
            {
                "success_field": "codMensaje",
                "success_values": ["00000"],
                "alternative_paths": [
                    {
                        "field": "status",
                        "success_values": ["OK", "SUCCESS"]
                    }
                ]
            },
            
            # Modo permisivo
            {
                "validation_strategy": "permissive",
                "treat_empty_as_success": true
            }
        ]
        
        if 0 <= index < len(templates):
            template = templates[index]
            self.validation_editor.setText(json.dumps(template, indent=2))
    
    def _style_dialog(self, dialog, title="Información", width=600, height=400):
        """Aplica estilos consistentes a un diálogo"""
        dialog.setWindowTitle(title)
        dialog.setMinimumSize(width, height)
        
        # Aplicar estilos CSS
        dialog.setStyleSheet("""
            QDialog {
                background-color: #f5f5f7;
                border: 1px solid #dcdcdc;
            }
            QLabel {
                font-size: 12px;
                color: #333333;
            }
            QLabel[title="true"] {
                font-size: 14px;
                font-weight: bold;
                color: #2d2d2d;
                padding: 5px 0;
            }
            QPushButton {
                background-color: #4a86e8;
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a76d8;
            }
            QPushButton:pressed {
                background-color: #2a66c8;
            }
            QPushButton[secondary="true"] {
                background-color: #e0e0e0;
                color: #333333;
            }
            QPushButton[secondary="true"]:hover {
                background-color: #d0d0d0;
            }
            QTextEdit, QTextBrowser {
                border: 1px solid #cccccc;
                border-radius: 3px;
                background-color: white;
                font-family: "Courier New";
                padding: 5px;
            }
        """)
        
        return dialog
    
    def _diagnose_connection(self, service_name: str):
        """Diagnostica problemas de conexión para un servicio específico"""
        try:
            # Cargar datos del servicio
            service_data = self.persistence.load_soap_request(service_name)
            
            if not service_data:
                self._log_event(f"Error: No se pudo cargar servicio {service_name}", "error")
                return
            
            # Determinar tipo y URL
            service_type = service_data.get('type', 'SOAP')
            
            if service_type == 'SOAP':
                url = service_data.get('wsdl_url', '')
            else:  # REST
                url = service_data.get('url', '')
            
            if not url:
                self._log_event(f"Error: URL no encontrada para servicio {service_name}", "error")
                return
            
            # Crear diálogo de progreso
            self._log_event(f"Ejecutando diagnóstico de conexión para {service_name}...", "info")
            
            # Importar utilidad de validación
            from utils import validate_endpoint_url
            
            # Probar con diferentes timeouts
            result = {
                "url": url,
                "service_name": service_name,
                "service_type": service_type,
                "tests": []
            }
            
            timeouts = [5, 15, 30]
            for timeout in timeouts:
                start_time = time.time()
                success = validate_endpoint_url(url, timeout=timeout)
                elapsed = time.time() - start_time
                
                result["tests"].append({
                    "timeout": timeout,
                    "success": success,
                    "elapsed": elapsed
                })
                
                self._log_event(f"Prueba con timeout={timeout}s: {'Éxito' if success else 'Fallido'} en {elapsed:.2f}s", 
                            "info" if success else "warning")
            
            # Mostrar resultados en diálogo
            if any(test["success"] for test in result["tests"]):
                # Si alguna prueba tuvo éxito
                best_test = next(test for test in result["tests"] if test["success"])
                self._log_event(f"Conectividad confirmada con timeout={best_test['timeout']}s. "
                            f"Actualice la configuración del servicio.", "info")
            else:
                # Si todas las pruebas fallaron
                self._log_event(f"Error de conexión confirmado para {url}. "
                            f"Verifique la red o la disponibilidad del servicio.", "error")
            
            return result
            
        except Exception as e:
            self._log_event(f"Error en diagnóstico: {str(e)}", "error")

class CustomTableWidgetItem(QTableWidgetItem):
    """Item de tabla personalizado con soporte para estados"""
    
    def __init__(self, text="", status=STATUS_IDLE):
        super().__init__(text)
        self._status = status
        self._updateStyle()
    
    def setStatus(self, status):
        """Establece el estado del item y actualiza su estilo"""
        self._status = status
        self._updateStyle()
    
    def _updateStyle(self):
        """Actualiza el estilo visual según el estado"""
        if self._status == STATUS_CHECKING:
            self.setBackground(QBrush(QColor(240, 240, 255)))  # Azul muy claro
            self.setForeground(QBrush(QColor(70, 70, 180)))    # Azul oscuro
            self.setFont(QFont("Arial", 9, QFont.Bold))
            self.setText(self.text() + " (Verificando...)")
        elif self._status == STATUS_OK:
            self.setBackground(QBrush(QColor(200, 255, 200)))  # Verde claro
            self.setForeground(QBrush(QColor(0, 120, 0)))      # Verde oscuro
            self.setFont(QFont("Arial", 9, QFont.Bold))
        elif self._status == STATUS_WARNING:
            self.setBackground(QBrush(QColor(255, 240, 180)))  # Amarillo
            self.setForeground(QBrush(QColor(150, 100, 0)))    # Marrón
            self.setFont(QFont("Arial", 9, QFont.Bold))
        elif self._status == STATUS_ERROR:
            self.setBackground(QBrush(QColor(255, 200, 200)))  # Rojo claro
            self.setForeground(QBrush(QColor(180, 0, 0)))      # Rojo
            self.setFont(QFont("Arial", 9, QFont.Bold))
        else:  # STATUS_IDLE
            self.setBackground(QBrush(QColor(255, 255, 255)))  # Blanco
            self.setForeground(QBrush(QColor(0, 0, 0)))        # Negro
            self.setFont(QFont("Arial", 9))

class SpinnerWidget(QWidget):
    """Widget de spinner para indicar carga"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        
        # Crear label para el spinner
        self.spinner_label = QLabel()
        
        # Cargar GIF animado (asegúrate de crear/conseguir este archivo)
        # Puedes usar un GIF existente o crear uno
        self.spinner = QMovie("icons/spinner.gif")
        self.spinner.setScaledSize(QSize(36, 36))
        self.spinner_label.setMovie(self.spinner)
        
        # Texto de estado
        self.status_label = QLabel("Verificando...")
        
        # Añadir al layout
        layout.addWidget(self.spinner_label)
        layout.addWidget(self.status_label)
        layout.addStretch()
        
        self.setLayout(layout)
        
    def start(self):
        """Inicia la animación"""
        self.spinner.start()
        self.show()
        
    def stop(self):
        """Detiene la animación"""
        self.spinner.stop()
        self.hide()
        
class ServiceCheckerThread(QThread):
    """Thread para verificar servicios en segundo plano"""
    
    # Señales para comunicar resultados
    finished = pyqtSignal(str, bool, str)  # service_name, success, message
    progress = pyqtSignal(str, str)        # service_name, status_message
    
    def __init__(self, parent, service_name, service_data, soap_client, rest_client, persistence):
        super().__init__(parent)
        self.service_name = service_name
        self.service_data = service_data
        self.soap_client = soap_client
        self.rest_client = rest_client
        self.persistence = persistence
        
    def run(self):
        """Ejecuta la verificación del servicio en segundo plano"""
        try:
            # Emitir progreso
            self.progress.emit(self.service_name, "Iniciando verificación...")
            
            # Determinar el tipo de servicio
            service_type = self.service_data.get('type', 'SOAP')
            
            # Obtener configuraciones de timeout y reintentos
            timeout = self.service_data.get('request_timeout', 30)
            max_retries = self.service_data.get('max_retries', 1)
            
            # Verificar según tipo
            if service_type == 'SOAP':
                # Verificar datos requeridos
                if not self.service_data.get('wsdl_url') or not self.service_data.get('request_xml'):
                    self.finished.emit(self.service_name, False, "Faltan datos para verificar servicio SOAP")
                    return
                
                # Emitir progreso
                self.progress.emit(self.service_name, "Conectando al servicio SOAP...")
                
                # Enviar request SOAP
                wsdl_url = self.service_data.get('wsdl_url')
                request_xml = self.service_data.get('request_xml')
                
                success, result = self.soap_client.send_raw_request(
                    wsdl_url, 
                    request_xml,
                    timeout=timeout,
                    max_retries=max_retries
                )
            else:  # REST
                # Verificar datos requeridos
                if not self.service_data.get('url'):
                    self.finished.emit(self.service_name, False, "Falta URL para verificar servicio REST")
                    return
                
                # Emitir progreso
                self.progress.emit(self.service_name, "Conectando al servicio REST...")
                
                # Preparar parámetros REST
                url = self.service_data.get('url')
                method = self.service_data.get('method', 'GET')
                headers = self.service_data.get('headers', {})
                params = self.service_data.get('params', {})
                json_data = self.service_data.get('json_data')
                
                # Enviar request REST
                success, result = self.rest_client.send_request(
                    url=url,
                    method=method,
                    headers=headers,
                    params=params,
                    json_data=json_data,
                    timeout=timeout,
                    max_retries=max_retries
                )
            
            # Emitir progreso
            self.progress.emit(self.service_name, "Procesando respuesta...")
            
            # Proceso de validación
            if not success:
                # Guardar resultado de error
                self.persistence.update_request_status(self.service_name, 'failed', result)
                self.finished.emit(self.service_name, False, result.get('error', 'Error desconocido'))
            else:
                # Validar respuesta
                validation_schema = self.service_data.get('validation_pattern', {})
                
                valid, message, level = self.soap_client.validate_response_advanced(
                    result['response'], validation_schema
                )
                
                if not valid:
                    if level == "failed":
                        # Fallo conocido
                        self.persistence.update_request_status(self.service_name, 'failed', {
                            'response': result['response'],
                            'validation_message': message
                        })
                        self.finished.emit(self.service_name, False, f"Fallo: {message}")
                    else:
                        # Error de validación
                        self.persistence.update_request_status(self.service_name, 'invalid', {
                            'response': result['response'],
                            'validation_error': message
                        })
                        self.finished.emit(self.service_name, False, f"Validación fallida: {message}")
                elif level == "warning":
                    # Advertencia
                    self.persistence.update_request_status(self.service_name, 'warning', {
                        'response': result['response'],
                        'validation_message': message
                    })
                    self.finished.emit(self.service_name, True, f"Advertencia: {message}")
                else:
                    # Éxito
                    self.persistence.update_request_status(self.service_name, 'ok', {
                        'response': result['response']
                    })
                    self.finished.emit(self.service_name, True, "Verificación exitosa")
            
        except Exception as e:
            # Error general
            self.persistence.update_request_status(self.service_name, 'error', {
                'error': str(e)
            })
            self.finished.emit(self.service_name, False, str(e))