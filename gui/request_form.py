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
    QStackedWidget, QTableWidget
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
        
        # Headers
        rest_layout.addWidget(QLabel("Headers:"))
        self.headers_table = QTableWidget(0, 2)
        self.headers_table.setHorizontalHeaderLabels(["Nombre", "Valor"])
        self.headers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.headers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        rest_layout.addWidget(self.headers_table)
        
        # Botones para headers
        headers_buttons = QHBoxLayout()
        self.btn_add_header = QPushButton("Añadir Header")
        self.btn_add_header.clicked.connect(self._add_header_row)
        headers_buttons.addWidget(self.btn_add_header)
        
        self.btn_remove_header = QPushButton("Eliminar Header")
        self.btn_remove_header.clicked.connect(self._remove_header_row)
        headers_buttons.addWidget(self.btn_remove_header)
        rest_layout.addLayout(headers_buttons)
        
        # Query Parameters
        rest_layout.addWidget(QLabel("Query Parameters:"))
        self.params_table = QTableWidget(0, 2)
        self.params_table.setHorizontalHeaderLabels(["Nombre", "Valor"])
        self.params_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.params_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        rest_layout.addWidget(self.params_table)
        
        # Botones para params
        params_buttons = QHBoxLayout()
        self.btn_add_param = QPushButton("Añadir Parámetro")
        self.btn_add_param.clicked.connect(self._add_param_row)
        params_buttons.addWidget(self.btn_add_param)
        
        self.btn_remove_param = QPushButton("Eliminar Parámetro")
        self.btn_remove_param.clicked.connect(self._remove_param_row)
        params_buttons.addWidget(self.btn_remove_param)
        rest_layout.addLayout(params_buttons)
        
        # Body JSON (para POST/PUT)
        rest_layout.addWidget(QLabel("Body JSON:"))
        self.json_body_input = QTextEdit()
        self.json_body_input.setPlaceholderText('{\n  "key": "value"\n}')
        self.json_body_input.setFont(font)
        rest_layout.addWidget(self.json_body_input)
        
        # Botón para formatear JSON
        self.btn_format_json = QPushButton("Formatear JSON")
        self.btn_format_json.clicked.connect(self._format_json)
        rest_layout.addWidget(self.btn_format_json)
        
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
    
    def _on_service_type_changed(self, index):
        """Actualiza la visibilidad de campos según el tipo de servicio seleccionado"""
        self.type_specific_container.setCurrentIndex(index)

    def _add_header_row(self):
        """Añade una fila a la tabla de headers"""
        row = self.headers_table.rowCount()
        self.headers_table.insertRow(row)
        self.headers_table.setItem(row, 0, QTableWidgetItem(""))
        self.headers_table.setItem(row, 1, QTableWidgetItem(""))

    def _remove_header_row(self):
        """Elimina la fila seleccionada de la tabla de headers"""
        selected_rows = self.headers_table.selectionModel().selectedRows()
        if not selected_rows:
            return
            
        for index in sorted(selected_rows, reverse=True):
            self.headers_table.removeRow(index.row())

    def _add_param_row(self):
        """Añade una fila a la tabla de parámetros"""
        row = self.params_table.rowCount()
        self.params_table.insertRow(row)
        self.params_table.setItem(row, 0, QTableWidgetItem(""))
        self.params_table.setItem(row, 1, QTableWidgetItem(""))

    def _remove_param_row(self):
        """Elimina la fila seleccionada de la tabla de parámetros"""
        selected_rows = self.params_table.selectionModel().selectedRows()
        if not selected_rows:
            return
            
        for index in sorted(selected_rows, reverse=True):
            self.params_table.removeRow(index.row())

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
                headers = {}
                for row in range(self.headers_table.rowCount()):
                    key = self.headers_table.item(row, 0).text().strip()
                    value = self.headers_table.item(row, 1).text().strip()
                    if key:
                        headers[key] = value
                
                # Recopilar query params
                params = {}
                for row in range(self.params_table.rowCount()):
                    key = self.params_table.item(row, 0).text().strip()
                    value = self.params_table.item(row, 1).text().strip()
                    if key:
                        params[key] = value
                
                # Procesar JSON body
                json_body = self.json_body_input.toPlainText().strip()
                json_data = None
                if json_body:
                    try:
                        json_data = json.loads(json_body)
                    except json.JSONDecodeError as e:
                        QMessageBox.warning(self, "Error", f"El JSON del body no es válido: {str(e)}")
                        return
                
                # Añadir datos específicos de REST
                request_data.update({
                    'url': rest_url,
                    'method': rest_method,
                    'headers': headers,
                    'params': params,
                    'json_data': json_data
                })
            
            # Guardar request
            self.persistence.save_soap_request(request_data)
            
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
            
            # Cargar headers
            self.headers_table.setRowCount(0)
            headers = request_data.get('headers', {})
            for key, value in headers.items():
                row = self.headers_table.rowCount()
                self.headers_table.insertRow(row)
                self.headers_table.setItem(row, 0, QTableWidgetItem(key))
                self.headers_table.setItem(row, 1, QTableWidgetItem(str(value)))
            
            # Cargar params
            self.params_table.setRowCount(0)
            params = request_data.get('params', {})
            for key, value in params.items():
                row = self.params_table.rowCount()
                self.params_table.insertRow(row)
                self.params_table.setItem(row, 0, QTableWidgetItem(key))
                self.params_table.setItem(row, 1, QTableWidgetItem(str(value)))
            
            # Cargar JSON body
            json_data = request_data.get('json_data')
            if json_data:
                try:
                    self.json_body_input.setText(json.dumps(json_data, indent=2))
                except:
                    self.json_body_input.setText(str(json_data))
            else:
                self.json_body_input.setText("")
        
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
                if isinstance(validation_pattern, str):
                    try:
                        # Intentar convertir a diccionario si es un string con formato JSON
                        import json
                        validation_schema = json.loads(validation_pattern)
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
            self.refresh_services_list()
            
        except Exception as e:
            logger.error(f"Error al verificar servicio {service_name}: {str(e)}", exc_info=True)
            self._log_event(f"Error al verificar {service_name}: {str(e)}", "error")
            
            # Registrar error
            self.persistence.update_request_status(service_name, 'error', {
                'error': str(e)
            })
            
            # Actualizar lista
            self.refresh_services_list()
        
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
    
    def _on_request_selected(self, current, previous):
        """Manejador para selección de request en la lista"""
        if current is None:
            return
        
        # Obtener datos del request seleccionado
        request_data = current.data(Qt.UserRole)
        self.current_request = request_data
        
        # Cargar datos en el formulario
        self.name_input.setText(request_data.get('name', ''))
        self.description_input.setText(request_data.get('description', ''))
        self.wsdl_url_input.setText(request_data.get('wsdl_url', ''))
        self.request_xml_input.setText(request_data.get('request_xml', ''))
        
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
            # Recopilar headers
            headers = {}
            for row in range(self.headers_table.rowCount()):
                key = self.headers_table.item(row, 0).text().strip()
                value = self.headers_table.item(row, 1).text().strip()
                if key:
                    headers[key] = value
            
            # Recopilar query params
            params = {}
            for row in range(self.params_table.rowCount()):
                key = self.params_table.item(row, 0).text().strip()
                value = self.params_table.item(row, 1).text().strip()
                if key:
                    params[key] = value
            
            # Procesar JSON body para métodos que lo necesitan
            json_data = None
            if method in ['POST', 'PUT', 'PATCH']:
                json_body = self.json_body_input.toPlainText().strip()
                if json_body:
                    try:
                        json_data = json.loads(json_body)
                    except json.JSONDecodeError as e:
                        QMessageBox.warning(self, "Error", f"El JSON del body no es válido: {str(e)}")
                        return
            
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
    
    def _save_request(self):
        """Guarda el request actual"""
        # Obtener datos del formulario
        name = self.name_input.text().strip()
        description = self.description_input.toPlainText().strip()
        wsdl_url = self.wsdl_url_input.text().strip()
        request_xml = self.request_xml_input.toPlainText().strip()
        
        # Validar datos mínimos
        if not name:
            QMessageBox.warning(self, "Información", "Ingrese un nombre para el request")
            return
        
        if not wsdl_url:
            QMessageBox.warning(self, "Información", "Especifique la URL del WSDL")
            return
        
        if not request_xml:
            QMessageBox.warning(self, "Información", "Ingrese el XML del request")
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
            
            # Crear datos del request
            request_data = {
                'name': name,
                'description': description,
                'wsdl_url': wsdl_url,
                'request_xml': request_xml,
                'validation_pattern': validation_data,
                'monitor_interval': self.monitor_interval.value(),
                'monitor_enabled': self.monitor_enabled.isChecked(),
                'add_to_system': self.add_to_system.isChecked(),
                'status': 'active'  # Estado inicial
            }
            
            # Guardar request
            self.persistence.save_soap_request(request_data)
            
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