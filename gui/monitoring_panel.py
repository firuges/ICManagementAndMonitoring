import os
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QMenu,
    QCheckBox, QSpinBox, QComboBox, QGroupBox, QSplitter, QTextBrowser,
    QDialog, QTextEdit  # Añadir estas importaciones para los diálogos
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QBrush, QFont

# Importar módulos de la aplicación
from core.persistence import PersistenceManager
from core.soap_client import SOAPClient
from core.scheduler import SOAPMonitorScheduler

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
        self.selected_service = None  # Servicio seleccionado actualmente
        
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
        
        # Sección superior (tabla y detalles)
        upper_section = QSplitter(Qt.Horizontal)
        
        # PANEL IZQUIERDO: Tabla de servicios
        services_widget = QWidget()
        services_layout = QVBoxLayout()
        services_widget.setLayout(services_layout)
        
        services_layout.addWidget(QLabel("<h2>Servicios Monitoreados</h2>"))
        
        # Tabla de servicios
        self.services_table = QTableWidget(0, 5)
        self.services_table.setHorizontalHeaderLabels([
            "Servicio", "Estado", "Última Verificación", "Intervalo", "Acciones"
        ])
        self.services_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.services_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.services_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.services_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.services_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.services_table.setColumnWidth(4, 120)
        self.services_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.services_table.setSelectionMode(QTableWidget.SingleSelection)
        self.services_table.itemClicked.connect(self._on_service_selected)
        services_layout.addWidget(self.services_table)
        
        # Botones de acción para tabla
        table_buttons_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Actualizar")
        self.btn_refresh.clicked.connect(self.refresh_services_list)
        table_buttons_layout.addWidget(self.btn_refresh)
        
        self.btn_check_all = QPushButton("Verificar Todos")
        self.btn_check_all.clicked.connect(self.check_all_services)
        table_buttons_layout.addWidget(self.btn_check_all)
        
        services_layout.addLayout(table_buttons_layout)
        
        # PANEL DERECHO: Detalles del servicio
        details_widget = QWidget()
        details_layout = QVBoxLayout()
        details_widget.setLayout(details_layout)
        
        details_layout.addWidget(QLabel("<h2>Detalles del Servicio</h2>"))
        
        # Información del servicio
        self.service_info = QTextBrowser()
        self.service_info.setOpenExternalLinks(False)
        details_layout.addWidget(self.service_info)
        
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
        
        self.btn_show_structure = QPushButton("Diagnóstico de Estructura")
        self.btn_show_structure.setToolTip("Muestra la estructura detallada de la respuesta para diagnóstico")
        self.btn_show_structure.clicked.connect(self._show_response_structure)
        diagnostics_layout.addWidget(self.btn_show_structure)
        
        self.btn_view_xml = QPushButton("Ver XML")
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
        self.btn_clear_log.clicked.connect(self.event_log.clear)
        log_buttons_layout.addWidget(self.btn_clear_log)
        
        log_layout.addLayout(log_buttons_layout)
        
        main_layout.addWidget(log_group, 1)
    
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
            
            # Crear ventana de diálogo con texto
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
            
            dialog = QDialog(self)
            dialog.setWindowTitle("Estructura de Respuesta - Diagnóstico")
            dialog.resize(800, 600)
            
            layout = QVBoxLayout()
            dialog.setLayout(layout)
            
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
            
            # Botón para cerrar
            close_btn = QPushButton("Cerrar")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)
            
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
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
            
            dialog = QDialog(self)
            dialog.setWindowTitle(f"XML de Respuesta - {os.path.basename(xml_files[0])}")
            dialog.resize(800, 600)
            
            layout = QVBoxLayout()
            dialog.setLayout(layout)
            
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setFontFamily("Courier New")
            text_edit.setText(xml_content)
            layout.addWidget(text_edit)
            
            # Botón para cerrar
            close_btn = QPushButton("Cerrar")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)
            
            dialog.exec_()
            
        except Exception as e:
            logger.error(f"Error mostrando XML: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error al mostrar XML: {str(e)}")
        
    def refresh_services_list(self):
        """Actualiza la lista de servicios con manejo mejorado de errores y diagnóstico"""
        try:
            # Log detallado para diagnóstico
            logger.info("Iniciando actualización de lista de servicios")
            
            # Obtener lista de servicios
            requests = self.persistence.list_all_requests()
            logger.info(f"Servicios encontrados: {len(requests)}")
            
            # DEBUG: Listar detalles de servicios encontrados
            for req in requests:
                logger.debug(f"Servicio: {req.get('name')}, Estado: {req.get('status')}")
            
            # Guardar la fila seleccionada actualmente
            current_row = -1
            selected_service_name = None
            
            if self.selected_service:
                selected_service_name = self.selected_service.get('name')
            
            # Limpiar tabla
            self.services_table.setRowCount(0)
            
            # Llenar tabla con servicios
            for i, request in enumerate(sorted(requests, key=lambda x: x.get('name', ''))):
                # VERIFICACIÓN: Asegurar campos mínimos
                if 'name' not in request or not request.get('name'):
                    logger.warning(f"Servicio sin nombre detectado, ignorando: {request}")
                    continue
                    
                self.services_table.insertRow(i)
                
                # Nombre del servicio
                name_item = QTableWidgetItem(request.get('name', 'Sin nombre'))
                name_item.setData(Qt.UserRole, request)  # Almacenar datos completos
                self.services_table.setItem(i, 0, name_item)
                
                # Estado
                status = request.get('status', 'sin verificar')
                status_item = QTableWidgetItem(status)
                
               # Colorear según estado
                if status == 'ok':
                    status_item.setBackground(QBrush(QColor(200, 255, 200)))  # Verde claro
                elif status == 'warning':
                    status_item.setBackground(QBrush(QColor(255, 240, 180)))  # Amarillo suave
                elif status == 'failed':
                    status_item.setBackground(QBrush(QColor(255, 180, 180)))  # Rojo claro
                elif status == 'error':
                    status_item.setBackground(QBrush(QColor(255, 200, 200)))  # Rojo menos intenso
                elif status == 'invalid':
                    status_item.setBackground(QBrush(QColor(255, 220, 200)))  # Naranja suave
                
                self.services_table.setItem(i, 1, status_item)
                
                # Última verificación
                last_checked = request.get('last_checked', '')
                
                if last_checked:
                    try:
                        dt = datetime.fromisoformat(last_checked)
                        last_checked = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except Exception as e:
                        logger.warning(f"Error al formatear fecha: {str(e)}")
                        # Mantener el valor original si hay error
                
                self.services_table.setItem(i, 2, QTableWidgetItem(last_checked))
                
                # Intervalo
                interval = request.get('monitor_interval', 15)
                self.services_table.setItem(i, 3, QTableWidgetItem(f"{interval} min"))
                
                # Botón de verificar
                check_button = QPushButton("Verificar")
                check_button.clicked.connect(lambda checked, name=request.get('name'): 
                                            self.check_service(name))
                self.services_table.setCellWidget(i, 4, check_button)
                
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
            
            self._log_event(f"Lista de servicios actualizada. {len(requests)} servicios cargados.")
            
        except Exception as e:
            logger.error(f"Error crítico al actualizar lista de servicios: {str(e)}", exc_info=True)
            self._log_event(f"Error al actualizar lista: {str(e)}", "error")
    
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
        
        # Construir HTML con detalles
        html = "<style>"
        html += "body { font-family: Arial, sans-serif; }"
        html += ".label { font-weight: bold; color: #555; }"
        html += ".value { margin-left: 10px; }"
        html += ".ok { color: green; }"
        html += ".failed { color: darkred; }"
        html += ".error { color: red; }"
        html += ".warning { color: orange; }"
        html += ".invalid { color: darkorange; }"
        html += ".unknown { color: gray; }"
        html += "</style>"
        
        html += f"<h3>{service_data.get('name', 'Sin nombre')}</h3>"
        
        # Descripción
        html += "<p>"
        html += f"<span class='label'>Descripción:</span>"
        html += f"<span class='value'>{service_data.get('description', 'Sin descripción')}</span>"
        html += "</p>"
        
        # URL WSDL
        html += "<p>"
        html += f"<span class='label'>URL WSDL:</span>"
        html += f"<span class='value'>{service_data.get('wsdl_url', 'No disponible')}</span>"
        html += "</p>"
        
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
        
        # Si hay error, mostrar detalles
        if status in ['failed', 'error', 'invalid'] and 'last_response' in service_data:
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
                
                # Validar la respuesta con el esquema avanzado si existe
                valid, message, level = self.soap_client.validate_response_advanced(
                    result['response'], validation_schema
                )

                if not valid:
                    if level == "failed":
                        # La respuesta es un fallo conocido
                        self.persistence.update_request_status(service_name, 'failed', {
                            'response': result['response'],
                            'validation_message': message
                        })
                        self._log_event(f"Servicio {service_name} falló: {message}", "error")
                    else:
                        # La respuesta no cumple con las reglas esperadas (error de validación)
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
                
            # Guardar directamente usando la función save_soap_request
            self.persistence.save_soap_request(backup_data)
            logger.info(f"Servicio {service_name} restaurado desde backup")
            self._log_event(f"Servicio {service_name} restaurado automáticamente", "info")
            return True
        except Exception as e:
            logger.error(f"Error al restaurar servicio {service_name}: {str(e)}")
            return False
        
    def check_all_services(self):
        """Verifica todos los servicios"""
        self._log_event("Iniciando verificación de todos los servicios")
        
        try:
            # Obtener lista de servicios
            requests = self.persistence.list_all_requests()
            
            # Verificar cada servicio
            for request in requests:
                service_name = request.get('name')
                if service_name:
                    self.check_service(service_name)
            
            self._log_event("Verificación de todos los servicios completada")
            
        except Exception as e:
            logger.error(f"Error al verificar todos los servicios: {str(e)}")
            self._log_event(f"Error al verificar todos los servicios: {str(e)}", "error")
    
    def _log_event(self, message: str, level: str = "info"):
        """
        Registra un evento en el log.
        
        Args:
            message (str): Mensaje a registrar
            level (str): Nivel de log (info, warning, error)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Determinar color según nivel
        color = {
            "info": "black",
            "warning": "orange",
            "error": "red"
        }.get(level, "black")
        
        # Crear entrada HTML
        html = f"<span style='color:gray'>[{timestamp}]</span> "
        html += f"<span style='color:{color}'>{message}</span><br>"
        
        # Añadir al log
        self.event_log.append(html)
        
        # Desplazar al final
        self.event_log.verticalScrollBar().setValue(
            self.event_log.verticalScrollBar().maximum()
        )
        
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