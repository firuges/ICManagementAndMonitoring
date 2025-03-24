import os
import re
import logging
import json
import datetime
import sys
from typing import Dict, Any, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, 
    QTextEdit, QPushButton, QComboBox, QSpinBox, QCheckBox, QGroupBox,
    QMessageBox, QSplitter, QListWidget, QListWidgetItem, QTabWidget,
    QTableWidgetItem, QHeaderView,QFileDialog, QDialog, QApplication,
    QStackedWidget, QTableWidget, QTextBrowser,QMenu, QDialogButtonBox, QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal, QRegExp
from PyQt5.QtGui import QRegExpValidator, QFont, QIcon

# Importar módulos de la aplicación
from core.persistence import PersistenceManager
from core.soap_client import SOAPClient

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('request_form')

class RequestForm(QWidget):
    """Formulario para gestionar requests SOAP"""
    
    request_saved = pyqtSignal(str)  # Señal emitida cuando se guarda un request
    
    def __init__(self, persistence: PersistenceManager, soap_client: SOAPClient):
        """
        Inicializa el formulario de requests SOAP.
        
        Args:
            persistence (PersistenceManager): Gestor de persistencia
            soap_client (SOAPClient): Cliente SOAP
        """
        super().__init__()
        
        self.persistence = persistence
        self.soap_client = soap_client
        # Inicializar propiedades REST
        self.headers = {}
        self.params = {}
        self.json_data = None
        
        # Añadir el cliente REST
        from core.rest_client import RESTClient
        self.rest_client = RESTClient()
        
        # Añadir el programador de tareas
        from core.scheduler import SOAPMonitorScheduler
        self.scheduler = SOAPMonitorScheduler()
        
        self.current_request = None  # Request actual en edición
        
        # Crear interfaz
        self._create_ui()
        
        # Cargar lista de requests existentes
        self._load_requests_list()
        
        logger.info("Formulario de requests inicializado")
    
    def _create_ui(self):
        """Crea la interfaz de usuario"""
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)
        # Estilos CSS para mejorar la apariencia
        style = """
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
            QTextBrowser, QTextEdit {
                border: 1px solid #cccccc;
                border-radius: 3px;
                background-color: white;
                padding: 4px;
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
            QLineEdit, QSpinBox {
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 4px;
                min-height: 20px;
            }
        """
        self.setStyleSheet(style)
        
        # Sección izquierda (lista de requests)
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        
        # Lista de requests
        self.requests_list = QListWidget()
        self.requests_list.currentItemChanged.connect(self._on_request_selected)
        left_layout.addWidget(QLabel("Servicios:"))  # Cambiado de "Requests SOAP" a "Servicios"
        left_layout.addWidget(self.requests_list)
        
        # Botones de acción de lista
        list_buttons_layout = QHBoxLayout()
        
        self.btn_refresh_list = QPushButton("Actualizar")
        self.btn_refresh_list.clicked.connect(self._load_requests_list)
        list_buttons_layout.addWidget(self.btn_refresh_list)
        
        self.btn_delete_request = QPushButton("Eliminar")
        self.btn_delete_request.clicked.connect(self._delete_request)
        list_buttons_layout.addWidget(self.btn_delete_request)
        
        left_layout.addLayout(list_buttons_layout)
        
        # Sección derecha (formulario)
        right_panel = QWidget()
        form_layout = QVBoxLayout()  # Cambiado de QFormLayout a QVBoxLayout
        right_panel.setLayout(form_layout)
        
        # Contenedor para los campos básicos en dos columnas
        basic_info_group = QGroupBox("Información del Servicio")
        basic_info_layout = QHBoxLayout()
        basic_info_group.setLayout(basic_info_layout)
        
        # Columna izquierda de información básica
        left_column = QFormLayout()
        left_column.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        
        # Campos para la columna izquierda
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Nombre descriptivo del servicio")
        left_column.addRow("Nombre:", self.name_input)
        
        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(60)
        self.description_input.setPlaceholderText("Descripción del propósito del servicio")
        left_column.addRow("Descripción:", self.description_input)
        
        # Columna derecha de información básica
        right_column = QFormLayout()
        right_column.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        
        # Campos para la columna derecha
        self.group_input = QComboBox()
        self.group_input.setEditable(True)  # Permitir ingresar grupos personalizados
        self.group_input.addItems(["General", "Financiero", "Clientes", "Productos", "Seguridad", "Monitoreo", "Soap Caja Social"])
        right_column.addRow("Grupo:", self.group_input)
        
        # Tipo de servicio (SOAP/REST)
        self.service_type = QComboBox()
        self.service_type.addItems(["SOAP", "REST"])
        self.service_type.currentIndexChanged.connect(self._on_service_type_changed)
        right_column.addRow("Tipo de servicio:", self.service_type)
        
        # Añadir las columnas al layout principal
        basic_info_layout.addLayout(left_column, 1)
        basic_info_layout.addLayout(right_column, 1)
        
        # Añadir el groupbox a la sección principal
        form_layout.addWidget(basic_info_group)
        
        # Contenedor para campos específicos de cada tipo
        self.type_specific_container = QStackedWidget()
        
        # ---------- CONTENEDOR PARA SOAP ----------
        self.soap_widget = QWidget()
        soap_layout = QVBoxLayout()
        self.soap_widget.setLayout(soap_layout)
        
        # URL del WSDL (solo para SOAP)
        self.wsdl_url_input = QLineEdit()
        self.wsdl_url_input.setPlaceholderText("URL del WSDL del servicio (ej: http://ejemplo.com/servicio?wsdl)")
        soap_layout.addWidget(QLabel("URL WSDL:"))
        soap_layout.addWidget(self.wsdl_url_input)
        
        # Crear tabs para XML y validación SOAP
        soap_tabs = QTabWidget()
        
        # Tab para Request XML
        xml_tab = QWidget()
        xml_layout = QVBoxLayout()
        xml_tab.setLayout(xml_layout)
        
        self.request_xml_input = QTextEdit()
        self.request_xml_input.setPlaceholderText("<soap:Envelope>\n  <!-- Contenido del request SOAP -->\n</soap:Envelope>")
        font = QFont("Courier New", 10)
        self.request_xml_input.setFont(font)
        xml_layout.addWidget(QLabel("Request XML:"))
        xml_layout.addWidget(self.request_xml_input)
        
        # Botones para XML
        xml_buttons_layout = QHBoxLayout()
        
        self.btn_load_xml = QPushButton("Cargar desde archivo")
        self.btn_load_xml.clicked.connect(self._load_xml_from_file)
        xml_buttons_layout.addWidget(self.btn_load_xml)
        
        self.btn_format_xml = QPushButton("Formatear XML")
        self.btn_format_xml.clicked.connect(self._format_xml)
        xml_buttons_layout.addWidget(self.btn_format_xml)
        
        self.btn_test_request = QPushButton("Probar Request")
        self.btn_test_request.clicked.connect(self._test_request)
        xml_buttons_layout.addWidget(self.btn_test_request)
        
        xml_layout.addLayout(xml_buttons_layout)
        
        # Agregar tab de XML
        soap_tabs.addTab(xml_tab, "Request XML")
        
        # Añadir tabs a layout de SOAP
        soap_layout.addWidget(soap_tabs)
        
        # ---------- CONTENEDOR PARA REST MEJORADO ----------
        self.rest_widget = QWidget()
        rest_main_layout = QVBoxLayout()
        self.rest_widget.setLayout(rest_main_layout)
        
        # Grupo de configuración REST con dos columnas
        rest_config_group = QGroupBox("Configuración REST")
        rest_config_layout = QHBoxLayout()
        rest_config_group.setLayout(rest_config_layout)
        
        # Columna izquierda para URL y método
        rest_left_column = QFormLayout()
        
        # URL Base (para REST)
        self.rest_url_input = QLineEdit()
        self.rest_url_input.setPlaceholderText("URL del endpoint (ej: https://api.ejemplo.com/v1/recurso)")
        rest_left_column.addRow("URL:", self.rest_url_input)
        
        # Columna derecha para método HTTP
        rest_right_column = QFormLayout()
        
        # Método HTTP
        self.rest_method = QComboBox()
        self.rest_method.addItems(["GET", "POST", "PUT", "DELETE", "PATCH"])
        rest_right_column.addRow("Método HTTP:", self.rest_method)
        
        # Añadir columnas al grupo de configuración
        rest_config_layout.addLayout(rest_left_column, 2)  # 2/3 del espacio para URL
        rest_config_layout.addLayout(rest_right_column, 1)  # 1/3 del espacio para método
        
        # Añadir grupo de configuración al layout principal
        rest_main_layout.addWidget(rest_config_group)
        
        # Sección mejorada de Headers y Parameters
        headers_params_group = QGroupBox("Headers y Parameters")
        headers_params_layout = QHBoxLayout()  # Cambiado a horizontal para mostrar en dos columnas
        headers_params_group.setLayout(headers_params_layout)

        # Panel de Headers con tabla
        headers_container = QVBoxLayout()
        headers_label = QLabel("<b>Headers</b>")
        headers_container.addWidget(headers_label)

        # Tabla para Headers
        self.headers_table = QTableWidget(0, 2)
        self.headers_table.setHorizontalHeaderLabels(["Nombre", "Valor"])
        self.headers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.headers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.headers_table.setMinimumHeight(120)
        self.headers_table.setAlternatingRowColors(True)
        headers_container.addWidget(self.headers_table)

        # Botón para editar headers
        headers_btn_layout = QHBoxLayout()
        headers_btn_layout.addStretch()
        self.btn_edit_headers = QPushButton("Editar Headers")
        self.btn_edit_headers.clicked.connect(self._edit_headers_dialog)
        self.btn_edit_headers.setMaximumWidth(120)
        headers_btn_layout.addWidget(self.btn_edit_headers)
        headers_container.addLayout(headers_btn_layout)

        # Panel de Query Parameters con tabla
        params_container = QVBoxLayout()
        params_label = QLabel("<b>Query Parameters</b>")
        params_container.addWidget(params_label)

        # Tabla para Parameters
        self.params_table = QTableWidget(0, 2)
        self.params_table.setHorizontalHeaderLabels(["Nombre", "Valor"])
        self.params_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.params_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.params_table.setMinimumHeight(120)
        self.params_table.setAlternatingRowColors(True)
        params_container.addWidget(self.params_table)

        # Botón para editar parámetros
        params_btn_layout = QHBoxLayout()
        params_btn_layout.addStretch()
        self.btn_edit_params = QPushButton("Editar Parámetros")
        self.btn_edit_params.clicked.connect(self._edit_params_dialog)
        self.btn_edit_params.setMaximumWidth(120)
        params_btn_layout.addWidget(self.btn_edit_params)
        params_container.addLayout(params_btn_layout)

        # Añadir ambos contenedores al layout principal de Headers y Parameters
        headers_params_layout.addLayout(headers_container)
        headers_params_layout.addLayout(params_container)

        # Añadir el grupo al layout principal de REST
        rest_main_layout.addWidget(headers_params_group)
        
        # Sección de Body JSON
        json_group = QGroupBox("Body JSON")
        json_layout = QVBoxLayout()
        json_group.setLayout(json_layout)
        
        self.json_preview = QTextBrowser()
        self.json_preview.setFont(QFont("Courier New", 10))
        self.json_preview.setMinimumHeight(150)
        self.json_preview.setPlaceholderText("No hay JSON configurado")
        json_layout.addWidget(self.json_preview)
        
        json_btn_layout = QHBoxLayout()
        json_btn_layout.addStretch()
        self.btn_edit_json = QPushButton("Editar JSON")
        self.btn_edit_json.clicked.connect(self._edit_json_dialog)
        self.btn_edit_json.setMaximumWidth(120)
        json_btn_layout.addWidget(self.btn_edit_json)
        json_layout.addLayout(json_btn_layout)
        
        # Añadir grupo de JSON al layout principal
        rest_main_layout.addWidget(json_group)
        
        # Botón para probar REST
        test_layout = QHBoxLayout()
        test_layout.addStretch()
        self.btn_test_rest = QPushButton("Probar REST")
        self.btn_test_rest.clicked.connect(self._test_rest_request)
        self.btn_test_rest.setMinimumWidth(120)
        test_layout.addWidget(self.btn_test_rest)
        
        # Añadir botón de prueba al layout principal
        rest_main_layout.addLayout(test_layout)
        
        # Añadir al contenedor de tipos específicos
        self.type_specific_container.addWidget(self.soap_widget)
        self.type_specific_container.addWidget(self.rest_widget)
        
        # Añadir el contenedor al layout principal
        form_layout.addWidget(self.type_specific_container)
        
        # Sección de validación en dos columnas
        validation_group = QGroupBox("Validación de Respuestas")
        validation_layout = QHBoxLayout()  # Cambiado a horizontal para las dos columnas
        validation_group.setLayout(validation_layout)

        # Columna izquierda: Editor de patrones
        validation_left = QVBoxLayout()

        # Título y botón de ayuda
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("<b>Patrones de Validación:</b>"))

        # Botón de ayuda
        help_btn = QPushButton("?")
        help_btn.setToolTip("Mostrar ayuda sobre patrones de validación")
        help_btn.setMaximumWidth(25)
        help_btn.setMaximumHeight(25)
        help_btn.setStyleSheet("""
            QPushButton {
                border-radius: 12px;
                background-color: #4a86e8;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a76d8;
            }
        """)
        help_btn.clicked.connect(self._show_validation_help)
        header_layout.addStretch()
        header_layout.addWidget(help_btn)
        validation_left.addLayout(header_layout)

        # Editor de patrones
        self.validation_pattern_input = QTextEdit()
        self.validation_pattern_input.setPlaceholderText('{\n  "success_field": "codMensaje",\n  "success_values": ["00000"],\n  "expected_fields": {\n    "campo1": "valor_esperado",\n    "campo2": null\n  }\n}')
        self.validation_pattern_input.setFont(QFont("Courier New", 10))
        validation_left.addWidget(self.validation_pattern_input)

        # Columna derecha: Ejemplos y opciones
        validation_right = QVBoxLayout()

        # Selector de ejemplos
        validation_right.addWidget(QLabel("<b>Ejemplos Predefinidos:</b>"))

        templates_combo = QComboBox()
        templates_combo.addItems([
            "Seleccione un ejemplo...",
            "Validación básica",
            "Con advertencias (codMensaje)",
            "Verificación de campos",
            "Respuesta REST estándar"
        ])
        validation_right.addWidget(templates_combo)

        # Botón de aplicar
        apply_btn_layout = QHBoxLayout()
        apply_btn_layout.addStretch()
        apply_template_btn = QPushButton("Aplicar Ejemplo")
        apply_template_btn.clicked.connect(lambda: self._apply_validation_template(templates_combo.currentText()))
        apply_template_btn.setMaximumWidth(150)
        apply_btn_layout.addWidget(apply_template_btn)
        validation_right.addLayout(apply_btn_layout)

        # Añadir espacio expandible al final
        validation_right.addStretch()

        # Añadir ambas columnas al layout principal de validación
        validation_layout.addLayout(validation_left, 2)  # Proporción 2 para el editor
        validation_layout.addLayout(validation_right, 1)  # Proporción 1 para la explicación

        # Añadir grupo de validación al layout principal
        form_layout.addWidget(validation_group)
        
        # Opciones de monitoreo en diseño de grid más eficiente
        monitoring_group = QGroupBox("Opciones de Monitoreo")
        monitoring_layout = QGridLayout()
        monitoring_group.setLayout(monitoring_layout)

        self._update_monitoring_group(monitoring_layout)
        form_layout.addWidget(monitoring_group)

        # Primera fila: Intervalo y verificación
        monitoring_layout.addWidget(QLabel("Intervalo (minutos):"), 0, 0)
        self.monitor_interval = QSpinBox()
        self.monitor_interval.setMinimum(1)
        self.monitor_interval.setMaximum(1440)
        self.monitor_interval.setValue(15)
        monitoring_layout.addWidget(self.monitor_interval, 0, 1)

        # Botón de verificación a la derecha
        verify_task_btn = QPushButton("Verificar Estado")
        verify_task_btn.clicked.connect(lambda: self._check_task_status(self.name_input.text().strip()))
        monitoring_layout.addWidget(verify_task_btn, 0, 2, 1, 2)  # Extender a 2 columnas

        # Segunda fila: Opciones de timeout y reintentos
        monitoring_layout.addWidget(QLabel("Timeout (seg):"), 1, 0)
        self.request_timeout = QSpinBox()
        self.request_timeout.setMinimum(5)
        self.request_timeout.setMaximum(300)
        self.request_timeout.setValue(30)  # 30 segundos por defecto
        self.request_timeout.setToolTip("Tiempo máximo de espera para la respuesta en segundos")
        monitoring_layout.addWidget(self.request_timeout, 1, 1)

        monitoring_layout.addWidget(QLabel("Reintentos:"), 1, 2)
        self.max_retries = QSpinBox()
        self.max_retries.setMinimum(0)
        self.max_retries.setMaximum(5)
        self.max_retries.setValue(1)  # 1 reintento por defecto
        self.max_retries.setToolTip("Número de reintentos si falla la conexión")
        monitoring_layout.addWidget(self.max_retries, 1, 3)

        # Segunda fila: Checkboxes
        self.monitor_enabled = QCheckBox("Activar monitoreo automático")
        self.monitor_enabled.setChecked(True)
        monitoring_layout.addWidget(self.monitor_enabled, 2, 0, 1, 2)

        self.add_to_system = QCheckBox("Añadir al programador de tareas del sistema")
        monitoring_layout.addWidget(self.add_to_system, 2, 2, 1, 2)
        
        # Añadir grupo de monitoreo al layout principal
        form_layout.addWidget(monitoring_group)
        
        # Botones de acción
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.clicked.connect(self.clear_form)
        self.btn_clear.setMinimumWidth(100)
        buttons_layout.addWidget(self.btn_clear)
        
        self.btn_save = QPushButton("Guardar")
        self.btn_save.clicked.connect(self._save_request)
        self.btn_save.setDefault(True)
        self.btn_save.setMinimumWidth(100)
        buttons_layout.addWidget(self.btn_save)
        
        # Añadir botones al layout principal
        form_layout.addLayout(buttons_layout)
        
        # Crear un splitter para poder redimensionar paneles
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([200, 700])  # Tamaños iniciales
        
        main_layout.addWidget(splitter)
    
    def _show_validation_help(self):
        """Muestra ayuda sobre los patrones de validación en un diálogo modal"""
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle("Ayuda de Validación")
        help_dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout()
        help_dialog.setLayout(layout)
        
        # Contenido de ayuda con estilos
        help_text = QTextBrowser()
        help_text.setHtml("""
        <h3>Formato de Patrones de Validación</h3>
        <p>Los patrones de validación utilizan formato JSON para definir cómo se validan las respuestas:</p>
        
        <h4>Campos Principales:</h4>
        <ul>
            <li><b>success_field</b>: Campo que indica éxito/error (ej: "estadoRespuesta")</li>
            <li><b>success_values</b>: Lista de valores que indican éxito (ej: ["OK", "SUCCESS"])</li>
            <li><b>warning_values</b>: Lista de valores que se tratan como advertencia (ej: ["2001", "2002"])</li>
            <li><b>expected_fields</b>: Campos adicionales que deben existir en la respuesta</li>
        </ul>
        
        <h4>Reglas de Validación:</h4>
        <ul>
            <li>Si el valor es <code>null</code>: Solo se valida que el campo exista</li>
            <li>Si se especifica un valor: Se valida que coincida exactamente</li>
            <li>Campos anidados: Usar notación con punto (ej: <code>cabecera.codMensaje</code>)</li>
        </ul>
        
        <h4>Ejemplo Completo:</h4>
        <pre>
    {
    "success_field": "estadoRespuesta",
    "success_values": ["OK"],
    "warning_values": ["2001", "2002"],
    "expected_fields": {
        "datos": null,
        "cabecera.codMensaje": "0"
    }
    }
        </pre>
        """)
        
        layout.addWidget(help_text)
        
        # Botón de cerrar
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(help_dialog.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        help_dialog.exec_()
    
    # Añadir un nuevo método en request_form.py para verificar estado de tareas
    def _check_task_status(self, service_name: str) -> None:
        """Verifica y muestra el estado de la tarea programada en el sistema"""
        try:
            status = self.scheduler.get_task_status(service_name)
            
            message = f"Estado de la tarea: {service_name}\n\n"
            
            if status["exists"]:
                message += "✅ La tarea existe en el sistema\n"
                if status.get("interval"):
                    message += f"⏱️ Intervalo: {status['interval']}\n"
            else:
                message += "❌ La tarea NO existe en el sistema\n"
            
            if status.get("exists_internal", False):
                message += "✅ La tarea existe en el programador interno\n"
                if status.get("next_run_internal"):
                    message += f"⏱️ Próxima ejecución: {status['next_run_internal']}\n"
            
            # Mostrar detalles específicos del sistema
            if sys.platform.startswith('win'):
                message += "\nDetalles en Windows Task Scheduler:\n"
                if status.get("schedule_type"):
                    message += f"Tipo: {status['schedule_type']}\n"
            else:
                message += "\nDetalles en crontab:\n"
                if status.get("cron_schedule"):
                    message += f"Programación: {status['cron_schedule']}\n"
            
            # Mostrar mensaje
            QMessageBox.information(self, "Estado de la Tarea", message)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo verificar el estado de la tarea: {str(e)}")
            
    def _apply_validation_template(self, template_name):
        """Aplica una plantilla de validación predefinida"""
        templates = {
            "Validación básica": {
                "status": "ok"
            },
            "Con advertencias (codMensaje)": {
                "success_field": "codMensaje",
                "success_values": ["00000"],
                "warning_values": ["2001", "2002"],
                "validation_strategy": "flexible"
            },
            "Verificación de campos": {
                "success_field": "codMensaje",
                "success_values": ["00000"],
                "expected_fields": {
                    "fechaOperacion": None,
                    "identificador": None,
                    "estado": "ACTIVO"
                }
            },
            "Respuesta REST estándar": {
                "success_field": "status",
                "success_values": [200, "OK", "SUCCESS"],
                "expected_fields": {
                    "data": None,
                    "message": "Operation completed successfully"
                },
                "validation_strategy": "flexible"
            }
        }
        
        if template_name in templates:
            template = templates.get(template_name)
            if template:
                formatted_json = json.dumps(template, indent=2)
                self.validation_pattern_input.setText(formatted_json)
            
    def _edit_headers_dialog(self):
        """Abre un diálogo para editar los headers HTTP"""
        dialog = QDialog(self)
        self._style_dialog(dialog, "Editar Headers HTTP", 600, 400)
        
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        
        # Tabla para editar headers
        headers_table = QTableWidget(0, 2)
        headers_table.setHorizontalHeaderLabels(["Nombre", "Valor"])
        headers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        headers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        headers_table.setAlternatingRowColors(True)
        layout.addWidget(headers_table)
        
        # Cargar headers existentes
        existing_headers = self._get_current_headers()
        for key, value in existing_headers.items():
            row = headers_table.rowCount()
            headers_table.insertRow(row)
            headers_table.setItem(row, 0, QTableWidgetItem(key))
            headers_table.setItem(row, 1, QTableWidgetItem(value))
        
        # Si no hay headers, añadir fila vacía
        if headers_table.rowCount() == 0:
            headers_table.insertRow(0)
        
        # Botones para gestionar headers
        buttons_layout = QHBoxLayout()
        
        add_btn = QPushButton("Añadir Fila")
        add_btn.clicked.connect(lambda: headers_table.insertRow(headers_table.rowCount()))
        buttons_layout.addWidget(add_btn)
        
        remove_btn = QPushButton("Eliminar Fila")
        remove_btn.clicked.connect(lambda: headers_table.removeRow(headers_table.currentRow()) 
                                if headers_table.currentRow() >= 0 else None)
        buttons_layout.addWidget(remove_btn)
        
        # Botones para predefinidos
        preset_btn = QPushButton("Headers Predefinidos")
        preset_menu = QMenu()
        
        common_headers = {
            "Content-Type: application/json": {"Content-Type": "application/json"},
            "Accept: application/json": {"Accept": "application/json"},
            "Authorization: Bearer": {"Authorization": "Bearer "},
            "Accept-Language: es": {"Accept-Language": "es"}
        }
        
        for label, header in common_headers.items():
            action = preset_menu.addAction(label)
            action.triggered.connect(lambda checked, h=header: self._add_preset_header(headers_table, h))
        
        preset_btn.setMenu(preset_menu)
        buttons_layout.addWidget(preset_btn)
        
        layout.addLayout(buttons_layout)
        
        # Botones de aceptar/cancelar
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog_buttons.accepted.connect(dialog.accept)
        dialog_buttons.rejected.connect(dialog.reject)
        layout.addWidget(dialog_buttons)
        
        # Ejecutar diálogo
        if dialog.exec_() == QDialog.Accepted:
            # Guardar headers
            headers = {}
            for row in range(headers_table.rowCount()):
                name_item = headers_table.item(row, 0)
                value_item = headers_table.item(row, 1)
                
                if name_item and value_item and name_item.text().strip():
                    headers[name_item.text().strip()] = value_item.text().strip()
            
            # Actualizar la tabla
            self._update_headers_table(headers)
    
    def _update_headers_table(self, headers):
        """Actualiza la tabla de headers con los datos proporcionados"""
        self.headers = headers  # Guardar internamente
        
        # Limpiar tabla
        self.headers_table.setRowCount(0)
        
        if not headers:
            return
        
        # Añadir headers a la tabla
        for row, (key, value) in enumerate(headers.items()):
            self.headers_table.insertRow(row)
            self.headers_table.setItem(row, 0, QTableWidgetItem(key))
            self.headers_table.setItem(row, 1, QTableWidgetItem(value))

    def _update_params_table(self, params):
        """Actualiza la tabla de parámetros con los datos proporcionados"""
        self.params = params  # Guardar internamente
        
        # Limpiar tabla
        self.params_table.setRowCount(0)
        
        if not params:
            return
        
        # Añadir parámetros a la tabla
        for row, (key, value) in enumerate(params.items()):
            self.params_table.insertRow(row)
            self.params_table.setItem(row, 0, QTableWidgetItem(key))
            self.params_table.setItem(row, 1, QTableWidgetItem(str(value)))
        
    def _add_preset_header(self, table, header):
        """Añade un header predefinido a la tabla"""
        for name, value in header.items():
            # Buscar si ya existe
            for row in range(table.rowCount()):
                name_item = table.item(row, 0)
                if name_item and name_item.text() == name:
                    # Actualizar valor
                    table.setItem(row, 1, QTableWidgetItem(value))
                    return
            
            # Si no existe, añadir nuevo
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(name))
            table.setItem(row, 1, QTableWidgetItem(value))

    def _get_current_headers(self):
        """Obtiene los headers actuales"""
        # Si estamos editando un servicio existente
        if hasattr(self, 'current_request') and self.current_request:
            return self.current_request.get('headers', {})
        
        # Por defecto, headers básicos
        return {"Content-Type": "application/json", "Accept": "application/json"}

    def _update_headers_preview(self, headers):
        """Actualiza la vista previa de headers"""
        self.headers = headers  # Guardar internamente
        
        if not headers:
            self.headers_list.setHtml("<p style='color: #777; text-align: center; margin-top: 10px;'>No hay headers configurados</p>")
            return
        
        html = "<table style='width: 100%; border-collapse: collapse;'>"
        html += "<tr style='background-color: #f5f5f5;'><th style='text-align: left; padding: 3px; border-bottom: 1px solid #ddd;'>Nombre</th><th style='text-align: left; padding: 3px; border-bottom: 1px solid #ddd;'>Valor</th></tr>"
        
        for key, value in headers.items():
            html += f"<tr><td style='padding: 3px; border-bottom: 1px solid #f0f0f0;'>{key}</td><td style='padding: 3px; border-bottom: 1px solid #f0f0f0;'>{value}</td></tr>"
        
        html += "</table>"
        
        self.headers_list.setHtml(html)
    
    def _edit_params_dialog(self):
        """Abre un diálogo para editar los parámetros de query"""
        dialog = QDialog(self)
        self._style_dialog(dialog, "Editar Query Parameters", 600, 400)
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        
        # Tabla para editar parámetros
        params_table = QTableWidget(0, 2)
        params_table.setHorizontalHeaderLabels(["Nombre", "Valor"])
        params_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        params_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        params_table.setAlternatingRowColors(True)
        layout.addWidget(params_table)
        
        # Cargar parámetros existentes
        existing_params = self._get_current_params()
        for key, value in existing_params.items():
            row = params_table.rowCount()
            params_table.insertRow(row)
            params_table.setItem(row, 0, QTableWidgetItem(key))
            params_table.setItem(row, 1, QTableWidgetItem(str(value)))
        
        # Si no hay parámetros, añadir fila vacía
        if params_table.rowCount() == 0:
            params_table.insertRow(0)
        
        # Botones para gestionar parámetros
        buttons_layout = QHBoxLayout()
        
        add_btn = QPushButton("Añadir Fila")
        add_btn.clicked.connect(lambda: params_table.insertRow(params_table.rowCount()))
        buttons_layout.addWidget(add_btn)
        
        remove_btn = QPushButton("Eliminar Fila")
        remove_btn.clicked.connect(lambda: params_table.removeRow(params_table.currentRow()) 
                                if params_table.currentRow() >= 0 else None)
        buttons_layout.addWidget(remove_btn)
        
        layout.addLayout(buttons_layout)
        
        # Botones de aceptar/cancelar
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog_buttons.accepted.connect(dialog.accept)
        dialog_buttons.rejected.connect(dialog.reject)
        layout.addWidget(dialog_buttons)
        
        # Ejecutar diálogo
        if dialog.exec_() == QDialog.Accepted:
            # Guardar parámetros
            params = {}
            for row in range(params_table.rowCount()):
                name_item = params_table.item(row, 0)
                value_item = params_table.item(row, 1)
                
                if name_item and value_item and name_item.text().strip():
                    params[name_item.text().strip()] = value_item.text().strip()
            
            # Actualizar la tabla
            self._update_params_table(params)

    def _get_current_params(self):
        """Obtiene los parámetros actuales"""
        if hasattr(self, 'current_request') and self.current_request:
            return self.current_request.get('params', {})
        return {}

    def _update_params_preview(self, params):
        """Actualiza la vista previa de parámetros"""
        self.params = params  # Guardar internamente
        
        if not params:
            self.params_list.setHtml("<p style='color: #777; text-align: center; margin-top: 10px;'>No hay parámetros configurados</p>")
            return
        
        html = "<table style='width: 100%; border-collapse: collapse;'>"
        html += "<tr style='background-color: #f5f5f5;'><th style='text-align: left; padding: 3px; border-bottom: 1px solid #ddd;'>Nombre</th><th style='text-align: left; padding: 3px; border-bottom: 1px solid #ddd;'>Valor</th></tr>"
        
        for key, value in params.items():
            html += f"<tr><td style='padding: 3px; border-bottom: 1px solid #f0f0f0;'>{key}</td><td style='padding: 3px; border-bottom: 1px solid #f0f0f0;'>{value}</td></tr>"
        
        html += "</table>"
        
        self.params_list.setHtml(html)
    
    def _edit_json_dialog(self):
        """Abre un diálogo para editar el JSON del body"""
        dialog = QDialog(self)
        self._style_dialog(dialog, "Editar Body JSON", 800, 600)
        
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        
        # Editor de JSON
        json_editor = QTextEdit()
        json_editor.setFont(QFont("Courier New", 10))
        json_editor.setPlaceholderText('{\n  "key": "value"\n}')
        layout.addWidget(json_editor)
        
        # Cargar JSON existente
        existing_json = self._get_current_json()
        if existing_json:
            try:
                formatted_json = json.dumps(existing_json, indent=2)
                json_editor.setText(formatted_json)
            except Exception as e:
                json_editor.setText(str(existing_json))
        
        # Botones de acción
        actions_layout = QHBoxLayout()
        
        format_btn = QPushButton("Formatear JSON")
        format_btn.clicked.connect(lambda: self._format_json_in_editor(json_editor))
        actions_layout.addWidget(format_btn)
        
        validate_btn = QPushButton("Validar JSON")
        validate_btn.clicked.connect(lambda: self._validate_json_in_editor(json_editor))
        actions_layout.addWidget(validate_btn)
        
        clear_btn = QPushButton("Limpiar")
        clear_btn.clicked.connect(json_editor.clear)
        actions_layout.addWidget(clear_btn)
        
        layout.addLayout(actions_layout)
        
        # Templates predefinidos (ejemplos comunes)
        templates_layout = QHBoxLayout()
        templates_layout.addWidget(QLabel("Templates:"))
        
        templates_combo = QComboBox()
        templates_combo.addItems([
            "Seleccione un template...",
            "Login Request",
            "Create User",
            "Data Update",
            "Search Query"
        ])
        templates_layout.addWidget(templates_combo)
        
        apply_template_btn = QPushButton("Aplicar")
        apply_template_btn.clicked.connect(lambda: self._apply_json_template(templates_combo.currentText(), json_editor))
        templates_layout.addWidget(apply_template_btn)
        
        layout.addLayout(templates_layout)
        
        # Botones de aceptar/cancelar
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog_buttons.accepted.connect(dialog.accept)
        dialog_buttons.rejected.connect(dialog.reject)
        layout.addWidget(dialog_buttons)
        
        # Ejecutar diálogo
        if dialog.exec_() == QDialog.Accepted:
            # Guardar JSON
            json_text = json_editor.toPlainText().strip()
            if json_text:
                try:
                    json_data = json.loads(json_text)
                    # Actualizar la vista previa
                    self._update_json_preview(json_data)
                except json.JSONDecodeError as e:
                    QMessageBox.warning(self, "Error", f"JSON inválido: {str(e)}")
            else:
                self._update_json_preview(None)

    def _format_json_in_editor(self, editor):
        """Formatea el JSON en el editor"""
        json_text = editor.toPlainText().strip()
        if not json_text:
            return
        
        try:
            parsed_json = json.loads(json_text)
            formatted_json = json.dumps(parsed_json, indent=2)
            editor.setText(formatted_json)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al formatear JSON: {str(e)}")

    def _validate_json_in_editor(self, editor):
        """Valida el JSON en el editor"""
        json_text = editor.toPlainText().strip()
        if not json_text:
            QMessageBox.information(self, "Validación", "No hay JSON para validar")
            return
        
        try:
            json.loads(json_text)
            QMessageBox.information(self, "Validación", "JSON válido")
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "Error", f"JSON inválido: {str(e)}")

    def _apply_json_template(self, template_name, editor):
        """Aplica un template JSON predefinido"""
        templates = {
            "Login Request": {
                "username": "user@example.com",
                "password": "password123",
                "remember": True
            },
            "Create User": {
                "firstName": "John",
                "lastName": "Doe",
                "email": "john.doe@example.com",
                "role": "user",
                "active": True
            },
            "CheckSiteStatus": {
                "DocumentTypeId": "NI",
                "DocumentNumber": 8605011452,
                "SiteName": "booster036"
            },
            "Data Update": {
                "id": 12345,
                "fields": {
                    "status": "active",
                    "lastModified": "2023-01-01T12:00:00Z"
                }
            }
        }
        
        if template_name in templates:
            formatted_json = json.dumps(templates[template_name], indent=2)
            editor.setText(formatted_json)

    def _get_current_json(self):
        """Obtiene el JSON actual"""
        if hasattr(self, 'current_request') and self.current_request:
            return self.current_request.get('json_data')
        return None

    def _update_json_preview(self, json_data):
        """Actualiza la vista previa de JSON"""
        self.json_data = json_data  # Guardar internamente
        
        if not json_data:
            self.json_preview.setHtml("<p style='color: #777; text-align: center; margin-top: 30px;'>No hay JSON configurado</p>")
            return
        
        try:
            preview_text = json.dumps(json_data, indent=2)
            
            # Formatear JSON con colores para mejor visualización
            formatted_html = "<pre style='margin: 0; padding: 5px;'>"
            for line in preview_text.split('\n'):
                # Destacar llaves y corchetes
                line = line.replace("{", "<span style='color: #0000CC;'>{</span>")
                line = line.replace("}", "<span style='color: #0000CC;'>}</span>")
                line = line.replace("[", "<span style='color: #0000CC;'>[</span>")
                line = line.replace("]", "<span style='color: #0000CC;'>]</span>")
                
                # Destacar comillas y contenido
                if ":" in line:
                    parts = line.split(":", 1)
                    # Clave
                    key = parts[0]
                    key = re.sub(r'"(.*?)"', r'<span style="color: #008800;">"</span><span style="color: #880000; font-weight: bold;">\1</span><span style="color: #008800;">"</span>', key)
                    
                    # Valor
                    value = parts[1]
                    # Strings
                    value = re.sub(r'"(.*?)"', r'<span style="color: #008800;">"</span><span style="color: #0000BB;">\1</span><span style="color: #008800;">"</span>', value)
                    # Números
                    value = re.sub(r'(\s*?)(\d+)', r'\1<span style="color: #AA0000;">\2</span>', value)
                    # Boolean
                    value = re.sub(r'(true|false)', r'<span style="color: #AA6600;">\1</span>', value)
                    
                    line = key + ":" + value
                
                formatted_html += line + "\n"
            formatted_html += "</pre>"
            
            # Limitar tamaño para preview
            if len(preview_text) > 1000:
                formatted_html += "<p style='text-align: center; color: #666;'>[... Ver más en el editor ...]</p>"
                
            self.json_preview.setHtml(formatted_html)
        except Exception as e:
            self.json_preview.setPlainText(f"Error al mostrar JSON: {str(e)}")
    
    def _toggle_json_editor_size(self):
        """Alterna entre tamaño normal y expandido para el editor JSON"""
        current_height = self.json_body_input.height()
        
        if current_height <= 200:
            # Expandir el editor
            self.json_body_input.setMinimumHeight(500)
            self.json_body_input.setMaximumHeight(700)
            self.btn_expand_json.setText("Contraer Editor")
        else:
            # Contraer el editor
            self.json_body_input.setMinimumHeight(300)
            self.json_body_input.setMaximumHeight(300)
            self.btn_expand_json.setText("Expandir Editor")
        
        # Forzar actualización de layouts
        self.json_body_input.updateGeometry()
        if self.rest_widget and self.rest_widget.layout():
            self.rest_widget.layout().update()
            self.rest_widget.layout().activate()
        
        # Procesar eventos inmediatamente para ver el cambio
        QApplication.processEvents()
        
    def _on_service_type_changed(self, index):
        """Actualiza la visibilidad de campos según el tipo de servicio seleccionado"""
        self.type_specific_container.setCurrentIndex(index)
        
        # Si se seleccionó REST, inicializar
        if index == 1:  # REST
            self._initialize_rest_tables()

    def _format_json(self):
        """Formatea el JSON para mejor legibilidad"""
        json_text = self.json_body_input.toPlainText()
        
        if not json_text.strip():
            return
        
        try:
            parsed_json = json.loads(json_text)
            formatted_json = json.dumps(parsed_json, indent=2)
            self.json_body_input.setText(formatted_json)
            logger.info("JSON formateado correctamente")
            
        except Exception as e:
            logger.error(f"Error al formatear JSON: {str(e)}")
            QMessageBox.warning(self, "Error", f"Error al formatear JSON: {str(e)}")

    # Modificar el método _save_request para manejar tanto SOAP como REST
    def _save_request(self):
        """Guarda el request actual"""
        # Obtener datos del formulario
        name = self.name_input.text().strip()
        description = self.description_input.toPlainText().strip()
        service_type = self.service_type.currentText()  # "SOAP" o "REST"
        
        # Validar datos mínimos
        if not name:
            QMessageBox.warning(self, "Información", "Ingrese un nombre para el request")
            return
        
        interval = self.monitor_interval.value()
        if interval <= 0:
            QMessageBox.warning(self, "Información", "El intervalo de monitoreo debe ser mayor a 0 minutos")
            return
        
        try:
            # Procesar patrones de validación
            validation_pattern = self.validation_pattern_input.toPlainText().strip()
            validation_data = {}
            
            if validation_pattern:
                try:
                    validation_data = json.loads(validation_pattern)
                except:
                    # Si no es JSON válido, guardar como texto
                    validation_data = validation_pattern
            
            # Crear datos básicos del request
            request_data = {
                'name': name,
                'description': description,
                'group': self.group_input.currentText(),  # Añadir grupo
                'type': service_type,
                'validation_pattern': validation_data,
                'monitor_interval': self.monitor_interval.value(),
                'monitor_enabled': self.monitor_enabled.isChecked(),
                'add_to_system': self.add_to_system.isChecked(),
                'request_timeout': self.request_timeout.value(),  # Nuevo campo
                'max_retries': self.max_retries.value(),          # Nuevo campo
                'status': 'active'  # Estado inicial
            }
            
            # Datos específicos según tipo de servicio
            if service_type == "SOAP":
                wsdl_url = self.wsdl_url_input.text().strip()
                request_xml = self.request_xml_input.toPlainText().strip()
                
                if not wsdl_url:
                    QMessageBox.warning(self, "Información", "Especifique la URL del WSDL")
                    return
                
                if not request_xml:
                    QMessageBox.warning(self, "Información", "Ingrese el XML del request")
                    return
                    
                # Añadir datos específicos de SOAP
                request_data.update({
                    'wsdl_url': wsdl_url,
                    'request_xml': request_xml
                })
            else:  # REST
                rest_url = self.rest_url_input.text().strip()
                rest_method = self.rest_method.currentText()
                
                if not rest_url:
                    QMessageBox.warning(self, "Información", "Especifique la URL del endpoint REST")
                    return
                    
                # Recopilar headers
                headers = getattr(self, 'headers', {})
                params = getattr(self, 'params', {})
                json_data = getattr(self, 'json_data', None)
                
                # Añadir datos específicos de REST
                request_data.update({
                    'url': rest_url,
                    'method': rest_method,
                    'headers': headers,
                    'params': params,
                    'json_data': json_data
                })
            
            # Guardar request
            self.persistence.save_service_request(request_data)
            
            if self.monitor_enabled.isChecked():
                # Programar la tarea si está habilitado el monitoreo
                monitor_function = lambda: self.monitoring_panel.check_service(name) if hasattr(self, 'monitoring_panel') else None
                try:
                    success = self.scheduler.add_monitoring_task(name, interval, monitor_function)
                    if success:
                        logger.info(f"Tarea de monitoreo programada para {name} cada {interval} minutos")
                    else:
                        logger.warning(f"No se pudo programar la tarea de monitoreo para {name}")
                except Exception as e:
                    logger.error(f"Error al programar tarea: {str(e)}")
            if self.add_to_system.isChecked():
                try:
                    # Generar o actualizar la tarea del sistema
                    if self.scheduler.generate_system_task(name, self.monitor_interval.value()):
                        logger.info(f"Servicio '{name}' añadido al programador de tareas del sistema")
                    else:
                        logger.warning(f"No se pudo añadir el servicio '{name}' al programador de tareas")
                except Exception as scheduler_error:
                    logger.error(f"Error al crear tarea programada: {str(scheduler_error)}")
            # Emitir señal y actualizar lista
            self.request_saved.emit(name)
            self._load_requests_list()
            
            # Seleccionar el request guardado
            for i in range(self.requests_list.count()):
                item = self.requests_list.item(i)
                if item.text() == name:
                    self.requests_list.setCurrentItem(item)
                    break
            
            QMessageBox.information(self, "Información", f"Request '{name}' guardado correctamente")
            logger.info(f"Request guardado: {name}")
            
        except Exception as e:
            logger.error(f"Error al guardar request: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error al guardar request: {str(e)}")
    
    def _on_request_selected(self, current, previous):
        """Manejador para selección de request en la lista"""
        if current is None:
            return
        
        # Obtener datos del request seleccionado
        request_data = current.data(Qt.UserRole)
        self.current_request = request_data
        
        # Cargar datos comunes
        self.name_input.setText(request_data.get('name', ''))
        self.description_input.setText(request_data.get('description', ''))
        
        # Cargar datos timeout y reintentos
        request_timeout = request_data.get('request_timeout', 30)  # Default 30 segundos
        self.request_timeout.setValue(request_timeout)

        max_retries = request_data.get('max_retries', 1)  # Default 1 reintento
        self.max_retries.setValue(max_retries)

        # Determinar tipo y seleccionar
        service_type = request_data.get('type', 'SOAP')  # Por defecto SOAP para compatibilidad
        type_index = 0 if service_type == 'SOAP' else 1
        self.service_type.setCurrentIndex(type_index)
        
        # Cargar datos específicos según tipo
        if service_type == 'SOAP':
            self.wsdl_url_input.setText(request_data.get('wsdl_url', ''))
            self.request_xml_input.setText(request_data.get('request_xml', ''))
        else:  # REST
            self.rest_url_input.setText(request_data.get('url', ''))
        
            # Seleccionar método HTTP
            method_index = self.rest_method.findText(request_data.get('method', 'GET'))
            if method_index >= 0:
                self.rest_method.setCurrentIndex(method_index)
            
            # Guardar y actualizar headers en la tabla
            self.headers = request_data.get('headers', {})
            self._update_headers_table(self.headers)
            
            # Guardar y actualizar parámetros en la tabla
            self.params = request_data.get('params', {})
            self._update_params_table(self.params)
            
            # Actualizar JSON
            self.json_data = request_data.get('json_data')
            self._update_json_preview(self.json_data)
        
        # Cargar el grupo
        group = request_data.get('group', 'General')
        index = self.group_input.findText(group)
        if index >= 0:
            self.group_input.setCurrentIndex(index)
        else:
            self.group_input.setCurrentText(group)
            
        # Cargar patrones de validación
        validation_pattern = request_data.get('validation_pattern', {})
        if isinstance(validation_pattern, dict) and validation_pattern:
            self.validation_pattern_input.setText(json.dumps(validation_pattern, indent=2))
        else:
            self.validation_pattern_input.setText(str(validation_pattern))
        
        # Cargar opciones de monitoreo
        monitor_interval = request_data.get('monitor_interval', 15)
        self.monitor_interval.setValue(monitor_interval)
        
        monitor_enabled = request_data.get('monitor_enabled', True)
        self.monitor_enabled.setChecked(monitor_enabled)
        
        add_to_system = request_data.get('add_to_system', False)
        self.add_to_system.setChecked(add_to_system)
        
        logger.info(f"Request cargado en formulario: {request_data.get('name')}")
        
        if self.add_to_system.isChecked():
            # Verificar si la tarea ya existe en el sistema
            task_exists = self.scheduler.check_system_task_exists(request_data.get('name', ''))
            if not task_exists:
                # La tarea está marcada para existir pero no existe en el sistema
                # Puedes decidir si recrearla automáticamente o simplemente informar
                logger.warning(f"Servicio {request_data.get('name')} marcado para programación del sistema pero la tarea no existe")
    
    def check_service(self, service_name: str):
        """
        Verifica un servicio específico con validación avanzada.
        
        Args:
            service_name (str): Nombre del servicio a verificar
        """
        self._log_event(f"Verificando servicio: {service_name}")
        
        try:
            # Cargar datos del servicio
            service_data = self.persistence.load_soap_request(service_name)
            
            if not service_data:
                self._log_event(f"Error: No se pudo cargar servicio {service_name}", "error")
                return
            
            # Obtener configuración de timeout y reintentos
            timeout = service_data.get('request_timeout', 30)  # Default 30 segundos
            max_retries = service_data.get('max_retries', 1)   # Default 1 reintento
            
            self._log_event(f"Configuración: Timeout={timeout}s, Reintentos={max_retries}", "info")

            # Verificar tipo de servicio
            service_type = service_data.get('type', 'SOAP')
            
            # Guardar una copia completa del servicio para restaurar en caso de error
            service_backup = service_data.copy()
            
            if service_type == 'SOAP':
                # Verificar que tenga los datos necesarios
                if not service_data.get('wsdl_url') or not service_data.get('request_xml'):
                    self._log_event(f"Error: Faltan datos para verificar {service_name}", "error")
                    return
                    
                # Enviar request con timeout y reintentos
                wsdl_url = service_data.get('wsdl_url')
                request_xml = service_data.get('request_xml')
                
                success, result = self.soap_client.send_raw_request(
                    wsdl_url, 
                    request_xml,
                    timeout=timeout, 
                    max_retries=max_retries
                )
            else:  # REST
                # Configuración REST
                url = service_data.get('url')
                method = service_data.get('method', 'GET')
                headers = service_data.get('headers', {})
                params = service_data.get('params', {})
                json_data = service_data.get('json_data')
                
                # Enviar request REST con timeout y reintentos
                success, result = self.rest_client.send_request(
                    url=url,
                    method=method,
                    headers=headers,
                    params=params,
                    json_data=json_data,
                    timeout=timeout,
                    max_retries=max_retries
                )
            
            # Verificar que tenga los datos necesarios
            if not service_data.get('wsdl_url') or not service_data.get('request_xml'):
                self._log_event(f"Error: Faltan datos para verificar {service_name}", "error")
                return
            
            # Guardar una copia completa del servicio para restaurar en caso de error
            service_backup = service_data.copy()
            
            # Enviar request
            wsdl_url = service_data.get('wsdl_url')
            request_xml = service_data.get('request_xml')
            
            success, result = self.soap_client.send_raw_request(wsdl_url, request_xml)
            
            if not success:
                # Guardar resultado de error
                self.persistence.update_request_status(service_name, 'failed', result)
                self._log_event(f"Error en servicio {service_name}: {result.get('error')}", "error")
            else:
                # Extraer esquema de validación (puede ser el formato anterior o el nuevo)
                validation_schema = service_data.get('validation_pattern', {})
                if isinstance(validation_schema, str):
                    try:
                        # Intentar convertir a diccionario si es un string con formato JSON
                        import json
                        validation_schema = json.loads(validation_schema)
                    except:
                        # Si no es un JSON válido, usar un esquema por defecto
                        validation_schema = {"status": "ok"}
                else:
                    # Ya es un diccionario o algo similar
                    validation_schema = validation_pattern
                    
                # Validar la respuesta con el esquema avanzado si existe
                valid, message, level = self.soap_client.validate_response_advanced(
                    result['response'], validation_schema
                )
                
                if not valid:
                    # La respuesta no cumple con las reglas esperadas
                    self.persistence.update_request_status(service_name, 'invalid', {
                        'response': result['response'],
                        'validation_error': message
                    })
                    self._log_event(f"Validación fallida para {service_name}: {message}", "warning")
                elif level == "warning":
                    # Validación exitosa pero con advertencias
                    self.persistence.update_request_status(service_name, 'warning', {
                        'response': result['response'],
                        'validation_message': message
                    })
                    self._log_event(f"Servicio {service_name} validado con advertencias: {message}", "warning")
                else:
                    # Todo está bien
                    self.persistence.update_request_status(service_name, 'ok', {
                        'response': result['response']
                    })
                    self._log_event(f"Servicio {service_name} verificado correctamente: {message}")

            # Verificar integridad del archivo
            file_path = os.path.join(self.persistence.requests_path, 
                                    f"{service_name.lower().replace(' ', '_')}.json")
            if not os.path.exists(file_path):
                self._log_event(f"ALERTA: El archivo del servicio desapareció después de actualizar", "error")
                self._restore_service_from_backup(service_name, service_backup)
            
            # Actualizar lista y detalles
            self._load_requests_list()
            
        except Exception as e:
            logger.error(f"Error al verificar servicio {service_name}: {str(e)}", exc_info=True)
            self._log_event(f"Error al verificar {service_name}: {str(e)}", "error")
            
            # Registrar error
            self.persistence.update_request_status(service_name, 'error', {
                'error': str(e)
            })
            
            # Actualizar lista
            self._load_requests_list()
    
    
    def _initialize_rest_tables(self):
        """Inicializa las tablas REST con valores predeterminados"""
        # Configurar headers predeterminados
        default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Actualizar tabla de headers
        self._update_headers_table(default_headers)
        
        # Inicializar params vacíos
        self.params = {}
        self._update_params_table(self.params)
        
        # Inicializar JSON vacío
        self.json_data = None
        self._update_json_preview(self.json_data)
        
        logger.debug("Inicializadas tablas REST con valores predeterminados")
    
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
            return True
        except Exception as e:
            logger.error(f"Error al restaurar servicio {service_name}: {str(e)}")
            return False
    
    def _log_event(self, message: str, level: str = "info"):
        """
        Registra un evento en el log.
        
        Args:
            message (str): Mensaje a registrar
            level (str): Nivel de log (info, warning, error)
        """
        # Registrar en el logger según el nivel
        if level == "warning":
            logger.warning(message)
        elif level == "error":
            logger.error(message)
        else:
            logger.info(message)
            
    def _load_requests_list(self):
        """Carga la lista de requests existentes"""
        self.requests_list.clear()
        
        try:
            requests = self.persistence.list_all_requests()
            
            for request in sorted(requests, key=lambda x: x.get('name', '')):
                item = QListWidgetItem(request.get('name', 'Sin nombre'))
                item.setData(Qt.UserRole, request)  # Almacenar datos completos
                
                # Establecer tooltip con información
                tooltip = f"Descripción: {request.get('description', 'N/A')}\n"
                tooltip += f"Estado: {request.get('status', 'N/A')}"
                
                if 'last_checked' in request:
                    tooltip += f"\nÚltima verificación: {request['last_checked']}"
                
                item.setToolTip(tooltip)
                
                # Establecer color según estado
                if request.get('status') == 'failed' or request.get('status') == 'error':
                    item.setForeground(Qt.red)
                elif request.get('status') == 'invalid':
                    item.setForeground(Qt.darkYellow)
                
                self.requests_list.addItem(item)
            
            logger.info(f"Cargados {len(requests)} requests")
            
        except Exception as e:
            logger.error(f"Error al cargar lista de requests: {str(e)}")
            QMessageBox.warning(self, "Error", f"Error al cargar lista de requests: {str(e)}")
    
    def _delete_request(self):
        """Elimina el request seleccionado"""
        current_item = self.requests_list.currentItem()
        if current_item is None:
            QMessageBox.information(self, "Información", "Seleccione un request para eliminar")
            return
        
        request_name = current_item.text()
        
        # Confirmar eliminación
        reply = QMessageBox.question(
            self, 'Confirmar Eliminación',
            f"¿Está seguro de eliminar el request '{request_name}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Eliminar archivo
                safe_name = request_name.lower().replace(' ', '_')
                file_path = os.path.join(self.persistence.requests_path, f"{safe_name}.json")
                
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Request eliminado: {file_path}")
                    # Eliminar la tarea del sistema si existe
                    try:
                        from core.scheduler import SOAPMonitorScheduler
                        scheduler = SOAPMonitorScheduler()
                        
                        if scheduler.remove_system_task(request_name):
                            logger.info(f"Tarea del sistema para '{request_name}' eliminada correctamente")
                        else:
                            logger.warning(f"No se encontró tarea del sistema para '{request_name}'")
                    except Exception as e:
                        logger.error(f"Error al eliminar tarea del sistema: {str(e)}")
                    # Actualizar lista
                    self._load_requests_list()
                    self.clear_form()
                else:
                    logger.warning(f"Archivo no encontrado: {file_path}")
                    QMessageBox.warning(self, "Error", f"Archivo no encontrado: {file_path}")
            
            except Exception as e:
                logger.error(f"Error al eliminar request: {str(e)}")
                QMessageBox.critical(self, "Error", f"Error al eliminar request: {str(e)}")
    
    def _load_xml_from_file(self):
        """Carga XML desde archivo"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Cargar XML", "", "Archivos XML (*.xml);;Todos los archivos (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    xml_content = f.read()
                
                self.request_xml_input.setText(xml_content)
                logger.info(f"XML cargado desde: {file_path}")
                
                # Extraer nombre del servicio del XML si es posible
                if not self.name_input.text():
                    file_name = os.path.basename(file_path)
                    name, _ = os.path.splitext(file_name)
                    self.name_input.setText(name)
                
            except Exception as e:
                logger.error(f"Error al cargar XML: {str(e)}")
                QMessageBox.critical(self, "Error", f"Error al cargar XML: {str(e)}")
    
    def _format_xml(self):
        """Formatea el XML para mejor legibilidad"""
        xml_text = self.request_xml_input.toPlainText()
        
        if not xml_text.strip():
            return
        
        try:
            import xml.dom.minidom as md
            
            # Formatear XML
            formatted_xml = md.parseString(xml_text).toprettyxml(indent="  ")
            
            # Eliminar líneas vacías
            formatted_xml = "\n".join([line for line in formatted_xml.split("\n") if line.strip()])
            
            self.request_xml_input.setText(formatted_xml)
            logger.info("XML formateado correctamente")
            
        except Exception as e:
            logger.error(f"Error al formatear XML: {str(e)}")
            QMessageBox.warning(self, "Error", f"Error al formatear XML: {str(e)}")
    
    def _test_rest_request(self):
        """Prueba el request REST actual"""
        url = self.rest_url_input.text().strip()
        method = self.rest_method.currentText()
        
        if not url:
            QMessageBox.warning(self, "Información", "Especifique la URL del endpoint REST")
            return
        
        try:
            # Usar los headers y parámetros guardados
            headers = getattr(self, 'headers', {})
            params = getattr(self, 'params', {})
            json_data = getattr(self, 'json_data', None)
            
            # Diagnóstico detallado
            logger.info(f"Probando request REST: {url}")
            logger.info(f"Método: {method}")
            logger.info(f"Headers: {headers}")
            if json_data:
                logger.info(f"JSON data: {json.dumps(json_data)}")
                
            # Mostrar indicador de progreso
            QApplication.setOverrideCursor(Qt.WaitCursor)
            
            # Verificar que exista el cliente REST o crearlo
            if not hasattr(self, 'rest_client'):
                from core.rest_client import RESTClient
                self.rest_client = RESTClient()
            
            # Enviar request
            success, result = self.rest_client.send_request(
                url=url,
                method=method,
                headers=headers,
                params=params,
                json_data=json_data
            )
            
            # Restaurar cursor
            QApplication.restoreOverrideCursor()
            
            # Mostrar diálogo de respuesta
            self._show_response_dialog(success, result)
            
        except Exception as e:
            # Asegurar que el cursor se restaura
            QApplication.restoreOverrideCursor()
            
            logger.error(f"Error al probar request REST: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error al probar request REST: {str(e)}")
    

    
    
    def _test_request(self):
        """Prueba el request SOAP actual"""
        wsdl_url = self.wsdl_url_input.text().strip()
        request_xml = self.request_xml_input.toPlainText().strip()
        
        if not wsdl_url:
            QMessageBox.warning(self, "Información", "Especifique la URL del WSDL")
            return
        
        if not request_xml:
            QMessageBox.warning(self, "Información", "Ingrese el XML del request")
            return
        
        try:
            # Mostrar indicador de progreso
            QApplication.setOverrideCursor(Qt.WaitCursor)
            
            # Enviar request
            success, result = self.soap_client.send_raw_request(wsdl_url, request_xml)
            
            # Restaurar cursor
            QApplication.restoreOverrideCursor()
            
            # Mostrar diálogo de respuesta
            self._show_response_dialog(success, result)
            
        except Exception as e:
            # Asegurar que el cursor se restaura
            QApplication.restoreOverrideCursor()
            
            logger.error(f"Error al probar request: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error al probar request: {str(e)}")
    
    def _safe_serialize_response(self, response_data):
        """Serializa de forma segura respuestas complejas con manejo especial para tipos problemáticos.
        
        Args:
            response_data: Datos de respuesta a serializar
            
        Returns:
            str: Representación JSON o textual de los datos
        """
        try:
            # Implementar una conversión recursiva manual
            def convert_for_json(obj):
                if isinstance(obj, (datetime.datetime, datetime.date)):
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
    
    def clear_form(self):
        """Limpia el formulario"""
        self.current_request = None
        self.name_input.clear()
        self.description_input.clear()
        self.wsdl_url_input.clear()
        self.request_xml_input.clear()
        self.validation_pattern_input.clear()
        self.monitor_interval.setValue(15)
        self.monitor_enabled.setChecked(True)
        self.add_to_system.setChecked(False)
        
        # Deseleccionar en la lista
        self.requests_list.clearSelection()
        
        logger.info("Formulario limpiado")
    
    def set_request_xml(self, xml_content: str):
        """
        Establece el contenido XML en el formulario.
        
        Args:
            xml_content (str): Contenido XML
        """
        self.request_xml_input.setText(xml_content)
        
    def _show_response_dialog(self, success, result):
        """Muestra un diálogo con los resultados de la prueba de request.
        
        Args:
            success (bool): Indica si la solicitud fue exitosa
            result (dict): Resultado de la solicitud
        """
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit
        from PyQt5.QtGui import QFont
        
        # Crear diálogo personalizado
        dialog = QDialog(self)
        self._style_dialog(dialog, "Respuesta del Servicio SOAP", 800, 600)
        
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        
        # Título y estado
        if success:
            status_label = QLabel("<h3 style='color: green;'>El servicio respondió correctamente</h3>")
        else:
            status_label = QLabel("<h3 style='color: red;'>Error en la respuesta del servicio</h3>")
        layout.addWidget(status_label)
        
        # Preparar contenido de respuesta
        try:
            if success:
                # Utilizar el serializador seguro
                from core.soap_client import json_serial
                try:
                    content = json.dumps(result, indent=2, default=json_serial)
                except:
                    content = self._safe_serialize_response(result)
            else:
                # Mostrar detalles del error
                content = f"Error: {result.get('error', 'Error desconocido')}\n"
                if 'response_text' in result:
                    content += f"\nRespuesta original:\n{result['response_text']}"
        except Exception as e:
            content = f"Error al procesar respuesta: {str(e)}"
        
        # Área de texto para mostrar la respuesta
        response_text = QTextEdit()
        response_text.setReadOnly(True)
        response_text.setFont(QFont("Courier New", 10))
        response_text.setText(content)
        layout.addWidget(response_text)
        
        # Botones de acción
        buttons_layout = QHBoxLayout()
        
        # Botón para copiar al portapapeles
        copy_btn = QPushButton("Copiar Respuesta")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(content))
        buttons_layout.addWidget(copy_btn)
        
        # Botón para cerrar
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(dialog.accept)
        buttons_layout.addWidget(close_btn)
        
        layout.addLayout(buttons_layout)
        
        # Mostrar diálogo
        dialog.exec_()
        
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
    
    def _show_validation_help(self):
        """Muestra ayuda sobre los patrones de validación en un diálogo modal"""
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle("Ayuda de Validación")
        help_dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout()
        help_dialog.setLayout(layout)
        
        # Contenido de ayuda con estilos
        help_text = QTextBrowser()
        help_text.setHtml("""
        <h3>Formato de Patrones de Validación</h3>
        <p>Los patrones de validación utilizan formato JSON para definir cómo se validan las respuestas:</p>
        
        <h4>Campos Principales:</h4>
        <ul>
            <li><b>success_field</b>: Campo que indica éxito/error (ej: "estadoRespuesta")</li>
            <li><b>success_values</b>: Lista de valores que indican éxito (ej: ["OK", "SUCCESS"])</li>
            <li><b>warning_values</b>: Lista de valores que se tratan como advertencia (ej: ["2001", "2002"])</li>
            <li><b>expected_fields</b>: Campos adicionales que deben existir en la respuesta</li>
        </ul>
        
        <h4>Reglas de Validación:</h4>
        <ul>
            <li>Si el valor es <code>null</code>: Solo se valida que el campo exista</li>
            <li>Si se especifica un valor: Se valida que coincida exactamente</li>
            <li>Campos anidados: Usar notación con punto (ej: <code>cabecera.codMensaje</code>)</li>
        </ul>
        
        <h4>Ejemplo Completo:</h4>
        <pre style="background-color: #f8f8f8; padding: 10px; border-radius: 5px;">
    {
    "success_field": "estadoRespuesta",
    "success_values": ["OK"],
    "warning_values": ["2001", "2002"],
    "expected_fields": {
        "datos": null,
        "cabecera.codMensaje": "0"
    }
    }
        </pre>
        """)
        
        layout.addWidget(help_text)
        
        # Botón de cerrar
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(help_dialog.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        help_dialog.exec_()
    
    def _update_monitoring_group(self, monitoring_layout):
        """Actualiza el grupo de opciones de monitoreo con nuevos botones"""
        # Esta función debe llamarse desde _create_ui() después de crear monitoring_group
        
        # Botones adicionales para manejo de tareas
        task_buttons_layout = QHBoxLayout()
        
        # Botón para exportar tarea
        self.btn_export_task = QPushButton("Exportar tarea")
        self.btn_export_task.setIcon(QIcon.fromTheme("document-save", QIcon()))
        self.btn_export_task.setToolTip("Exporta los archivos necesarios para crear manualmente una tarea programada")
        self.btn_export_task.clicked.connect(self._export_task_files)
        task_buttons_layout.addWidget(self.btn_export_task)
        
        # Botón para forzar creación de tarea
        self.btn_force_task = QPushButton("Forzar creación")
        self.btn_force_task.setIcon(QIcon.fromTheme("system-run", QIcon()))
        self.btn_force_task.setToolTip("Intenta crear la tarea en el sistema con privilegios elevados")
        self.btn_force_task.clicked.connect(self._force_create_task)
        task_buttons_layout.addWidget(self.btn_force_task)
        
        # Añadir los nuevos botones al layout del grupo de monitoreo
        monitoring_layout.addLayout(task_buttons_layout, 3, 0, 1, 4)  # Ocupa toda la fila 3
        
        # Indicador de estado de administrador
        admin_layout = QHBoxLayout()

         # Función local para verificar permisos admin
        def is_admin():
            try:
                import sys
                import ctypes
                if sys.platform.startswith('win'):
                    return ctypes.windll.shell32.IsUserAnAdmin() != 0
                else:
                    import os
                    return os.geteuid() == 0
            except:
                return False
        # Verificar si se ejecuta como administrador
        is_running_as_admin = is_admin()
        
        admin_indicator = QLabel()
        if is_running_as_admin:
            admin_indicator.setText("✓ Ejecutando como administrador")
            admin_indicator.setStyleSheet("color: green; font-weight: bold;")
        else:
            admin_indicator.setText("❗ Ejecutando sin privilegios de administrador")
            admin_indicator.setStyleSheet("color: #CC6600; font-weight: bold;")
        
        admin_layout.addWidget(admin_indicator)
        admin_layout.addStretch()
        
        # Añadir indicador de admin al layout del grupo de monitoreo
        monitoring_layout.addLayout(admin_layout, 4, 0, 1, 4)  # Ocupa toda la fila 4

    def _export_task_files(self):
        """Manejador para exportar archivos de tarea programada"""
        # Verificar que tengamos un nombre de servicio
        service_name = self.name_input.text().strip()
        if not service_name:
            QMessageBox.warning(self, "Advertencia", "Debe especificar un nombre para el servicio")
            return
        
        # Obtener intervalo
        interval = self.monitor_interval.value()
        
        # Usar la función de exportación del scheduler
        success = self.scheduler.export_task_files(service_name, interval)
        
        if success:
            QMessageBox.information(self, "Exportación completada", 
                f"Los archivos para crear la tarea programada para '{service_name}' han sido exportados.\n\n"
                f"Para registrar la tarea, siga las instrucciones en el archivo README.txt incluido.")
        else:
            QMessageBox.warning(self, "Error", 
                "No se pudieron exportar los archivos de tarea. Verifique los logs para más detalles.")

    def _force_create_task(self):
        """Manejador para forzar la creación de una tarea programada"""
        # Verificar que tengamos un nombre de servicio
        service_name = self.name_input.text().strip()
        if not service_name:
            QMessageBox.warning(self, "Advertencia", "Debe especificar un nombre para el servicio")
            return
        
        # Obtener intervalo
        interval = self.monitor_interval.value()
        
        # Intentar forzar la creación
        success = self.scheduler.force_create_system_task(service_name, interval)
        
        if success:
            QMessageBox.information(self, "Tarea creada", 
                f"La tarea programada para '{service_name}' ha sido creada exitosamente en el programador de Windows.")