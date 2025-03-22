import os
import re
import logging
import json
import datetime
from typing import Dict, Any, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, 
    QTextEdit, QPushButton, QComboBox, QSpinBox, QCheckBox, QGroupBox,
    QMessageBox, QSplitter, QListWidget, QListWidgetItem, QTabWidget,
    QTableWidgetItem, QHeaderView,QFileDialog, QDialog, QApplication,
    QStackedWidget, QTableWidget, QTextBrowser,QMenu, QDialogButtonBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QRegExp
from PyQt5.QtGui import QRegExpValidator, QFont

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
        form_layout = QFormLayout()
        right_panel.setLayout(form_layout)
        
        # Nombre del Request
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Nombre descriptivo del servicio")
        form_layout.addRow("Nombre:", self.name_input)
        
        # Descripción
        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(100)
        self.description_input.setPlaceholderText("Descripción del propósito del servicio")
        form_layout.addRow("Descripción:", self.description_input)
        
        # Tipo de servicio (SOAP/REST)
        self.service_type = QComboBox()
        self.service_type.addItems(["SOAP", "REST"])
        self.service_type.currentIndexChanged.connect(self._on_service_type_changed)
        form_layout.addRow("Tipo de servicio:", self.service_type)
        
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
        
        # ---------- CONTENEDOR PARA REST ----------
        self.rest_widget = QWidget()
        rest_layout = QVBoxLayout()
        self.rest_widget.setLayout(rest_layout)

        # URL Base (para REST)
        self.rest_url_input = QLineEdit()
        self.rest_url_input.setPlaceholderText("URL del endpoint (ej: https://api.ejemplo.com/v1/recurso)")
        rest_layout.addWidget(QLabel("URL:"))
        rest_layout.addWidget(self.rest_url_input)

        # Método HTTP
        self.rest_method = QComboBox()
        self.rest_method.addItems(["GET", "POST", "PUT", "DELETE", "PATCH"])
        rest_layout.addWidget(QLabel("Método HTTP:"))
        rest_layout.addWidget(self.rest_method)

        # Headers - Lista de visualización con botones
        headers_group = QGroupBox("Headers")
        headers_layout = QVBoxLayout()
        headers_group.setLayout(headers_layout)
        headers_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        headers_group.setMinimumHeight(200)

        self.headers_list = QTextBrowser()
        self.headers_list.setMaximumHeight(150)
        self.headers_list.setPlaceholderText("No hay headers configurados")
        headers_layout.addWidget(self.headers_list)

        headers_buttons = QHBoxLayout()
        self.btn_edit_headers = QPushButton("Editar Headers")
        self.btn_edit_headers.clicked.connect(self._edit_headers_dialog)
        headers_buttons.addWidget(self.btn_edit_headers)
        headers_layout.addLayout(headers_buttons)
        rest_layout.addWidget(headers_group)

        # Query Parameters - Lista de visualización con botones
        params_group = QGroupBox("Query Parameters")
        params_layout = QVBoxLayout()
        params_group.setLayout(params_layout)

        self.params_list = QTextBrowser()
        self.params_list.setMaximumHeight(150)
        self.params_list.setPlaceholderText("No hay parámetros configurados")
        params_layout.addWidget(self.params_list)

        params_buttons = QHBoxLayout()
        self.btn_edit_params = QPushButton("Editar Parámetros")
        self.btn_edit_params.clicked.connect(self._edit_params_dialog)
        params_buttons.addWidget(self.btn_edit_params)
        params_layout.addLayout(params_buttons)
        rest_layout.addWidget(params_group)

        # Body JSON - Vista previa y botón de edición
        json_group = QGroupBox("Body JSON")
        json_layout = QVBoxLayout()
        json_group.setLayout(json_layout)

        self.json_preview = QTextBrowser()
        self.json_preview.setMaximumHeight(150)
        self.json_preview.setFont(QFont("Courier New", 10))
        self.json_preview.setPlaceholderText("No hay JSON configurado")
        json_layout.addWidget(self.json_preview)

        json_buttons = QHBoxLayout()
        self.btn_edit_json = QPushButton("Editar JSON")
        self.btn_edit_json.clicked.connect(self._edit_json_dialog)
        json_buttons.addWidget(self.btn_edit_json)
        json_layout.addLayout(json_buttons)
        rest_layout.addWidget(json_group)

        # Botón para probar REST
        self.btn_test_rest = QPushButton("Probar REST")
        self.btn_test_rest.clicked.connect(self._test_rest_request)
        rest_layout.addWidget(self.btn_test_rest)
        
        # Añadir widgets al contenedor específico de tipo
        self.type_specific_container.addWidget(self.soap_widget)
        self.type_specific_container.addWidget(self.rest_widget)
        form_layout.addRow(self.type_specific_container)
        
        # Tab para patrones de validación (común para ambos tipos)
        validation_tab = QWidget()
        validation_layout = QVBoxLayout()
        validation_tab.setLayout(validation_layout)
        
        validation_layout.addWidget(QLabel("Patrones de Validación:"))
        validation_layout.addWidget(QLabel("Defina cómo validar la respuesta del servicio"))
        
        self.validation_pattern_input = QTextEdit()
        self.validation_pattern_input.setPlaceholderText("{\n  \"campo1\": \"valor_esperado\",\n  \"campo2\": null\n}")
        self.validation_pattern_input.setFont(font)
        validation_layout.addWidget(self.validation_pattern_input)
        
        # Agregar explicación
        validation_layout.addWidget(QLabel(
            "Formato: JSON con campos esperados en la respuesta.\n"
            "- Si el valor es null, solo se valida que el campo exista.\n"
            "- Si se especifica un valor, se valida que coincida exactamente."
        ))
        
        # Crear tabs comunes para validación
        tabs = QTabWidget()
        tabs.addTab(validation_tab, "Validación")
        form_layout.addRow(tabs)
        
        # Opciones de monitoreo
        monitoring_group = QGroupBox("Opciones de Monitoreo")
        monitoring_layout = QFormLayout()
        monitoring_group.setLayout(monitoring_layout)
        
        # Intervalo de verificación
        self.monitor_interval = QSpinBox()
        self.monitor_interval.setMinimum(1)
        self.monitor_interval.setMaximum(1440)  # 24 horas en minutos
        self.monitor_interval.setValue(15)  # 15 minutos por defecto
        monitoring_layout.addRow("Intervalo (minutos):", self.monitor_interval)
        
        # Activar monitoreo
        self.monitor_enabled = QCheckBox("Activar monitoreo automático")
        self.monitor_enabled.setChecked(True)
        monitoring_layout.addRow("", self.monitor_enabled)
        
        # Añadir al sistema
        self.add_to_system = QCheckBox("Añadir al programador de tareas del sistema")
        monitoring_layout.addRow("", self.add_to_system)
        
        form_layout.addRow(monitoring_group)
        
        # Botones de acción
        buttons_layout = QHBoxLayout()
        
        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.clicked.connect(self.clear_form)
        buttons_layout.addWidget(self.btn_clear)
        
        self.btn_save = QPushButton("Guardar")
        self.btn_save.clicked.connect(self._save_request)
        self.btn_save.setDefault(True)
        buttons_layout.addWidget(self.btn_save)
        
        form_layout.addRow(buttons_layout)
        
        # Crear un splitter para poder redimensionar paneles
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([200, 700])  # Tamaños iniciales
        
        main_layout.addWidget(splitter)
    
    
    def _edit_headers_dialog(self):
        """Abre un diálogo para editar los headers HTTP"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Editar Headers HTTP")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(400)
        
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
            
            # Actualizar la vista previa
            self._update_headers_preview(headers)

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
            self.headers_list.setPlainText("No hay headers configurados")
            return
        
        text = ""
        for key, value in headers.items():
            text += f"{key}: {value}\n"
        
        self.headers_list.setPlainText(text)
    
    def _edit_params_dialog(self):
        """Abre un diálogo para editar los parámetros de query"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Editar Query Parameters")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(400)
        
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
            
            # Actualizar la vista previa
            self._update_params_preview(params)

    def _get_current_params(self):
        """Obtiene los parámetros actuales"""
        if hasattr(self, 'current_request') and self.current_request:
            return self.current_request.get('params', {})
        return {}

    def _update_params_preview(self, params):
        """Actualiza la vista previa de parámetros"""
        self.params = params  # Guardar internamente
        
        if not params:
            self.params_list.setPlainText("No hay parámetros configurados")
            return
        
        text = ""
        for key, value in params.items():
            text += f"{key}={value}\n"
        
        self.params_list.setPlainText(text)
    
    def _edit_json_dialog(self):
        """Abre un diálogo para editar el JSON del body"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Editar Body JSON")
        dialog.setMinimumWidth(800)
        dialog.setMinimumHeight(600)
        
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
            "Data Update": {
                "id": 12345,
                "fields": {
                    "status": "active",
                    "lastModified": "2023-01-01T12:00:00Z"
                }
            },
            "Search Query": {
                "query": "search term",
                "filters": {
                    "category": ["books", "electronics"],
                    "priceRange": {"min": 10, "max": 100}
                },
                "sort": {"field": "price", "order": "asc"},
                "pagination": {"page": 1, "limit": 20}
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
            self.json_preview.setPlainText("No hay JSON configurado")
            return
        
        try:
            preview_text = json.dumps(json_data, indent=2)
            # Limitar longitud para preview
            if len(preview_text) > 500:
                preview_text = preview_text[:500] + "...\n[Ver más en el editor]"
            self.json_preview.setPlainText(preview_text)
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
                'type': service_type,
                'validation_pattern': validation_data,
                'monitor_interval': self.monitor_interval.value(),
                'monitor_enabled': self.monitor_enabled.isChecked(),
                'add_to_system': self.add_to_system.isChecked(),
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
            
            # En _save_request, después de guardar el request:
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
            
            # Guardar los datos en las propiedades y actualizar vistas previas
            self.headers = request_data.get('headers', {})
            self._update_headers_preview(self.headers)
            
            self.params = request_data.get('params', {})
            self._update_params_preview(self.params)
            
            self.json_data = request_data.get('json_data')
            self._update_json_preview(self.json_data)
        
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
        """Inicializa las vistas previas REST con valores predeterminados útiles"""
        # Configurar headers predeterminados
        default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Actualizar vista previa de headers
        self._update_headers_preview(default_headers)
        
        # Guardar referencia interna
        self.headers = default_headers
        
        # Inicializar params vacíos
        self.params = {}
        self._update_params_preview(self.params)
        
        # Inicializar JSON vacío
        self.json_data = None
        self._update_json_preview(self.json_data)
        
        # Log
        logger.debug("Inicializadas vistas previas REST con valores predeterminados")
    
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
        dialog.setWindowTitle("Respuesta del Servicio SOAP")
        dialog.resize(800, 600)  # Tamaño más amplio para visualizar mejor la respuesta
        
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