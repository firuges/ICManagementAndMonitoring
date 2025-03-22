import os
import sys
import logging
from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QTabWidget, QMessageBox,
    QStatusBar, QAction, QMenu, QToolBar, QFileDialog
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QSize, QTimer

# Importar módulos de la aplicación
from gui.request_form import RequestForm
from gui.email_form import EmailForm
from gui.monitoring_panel import MonitoringPanel
from core.persistence import PersistenceManager
from core.soap_client import SOAPClient
from core.notification import EmailNotifier
from core.scheduler import SOAPMonitorScheduler

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('main_window')

class MainWindow(QMainWindow):
    """Ventana principal de la aplicación"""
    
    def __init__(self):
        """Inicializa la ventana principal"""
        super().__init__()
        
        # Configurar propiedades de la ventana
        self.setWindowTitle("Monitor de Servicios SOAP")
        self.setMinimumSize(900, 700)
        
        # Inicializar componentes del núcleo
        self.persistence = PersistenceManager()
        self.soap_client = SOAPClient()
        self.notifier = EmailNotifier()
        self.scheduler = SOAPMonitorScheduler()
        
        # Crear interfaz
        self._create_ui()
        
        # Iniciar programador
        self.scheduler.start()
        
        # Configurar temporizador para actualizar panel de monitoreo
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_monitoring)
        self.refresh_timer.start(30000)  # Actualizar cada 30 segundos
        
        logger.info("Ventana principal inicializada")
    
    def _create_ui(self):
        """Crea la interfaz de usuario"""
        # Crear barra de menú
        self._create_menu()
        
        # Crear barra de herramientas
        self._create_toolbar()
        
        # Crear contenedor de pestañas
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        
        # Pestaña de monitoreo
        self.monitoring_panel = MonitoringPanel(
            self.persistence, self.soap_client, self.scheduler
        )
        self.tab_widget.addTab(self.monitoring_panel, "Monitoreo")
        
        # Pestaña de gestión de requests
        self.request_form = RequestForm(self.persistence, self.soap_client)
        self.tab_widget.addTab(self.request_form, "Gestión de Requests")
        
        # Pestaña de configuración de notificaciones
        self.email_form = EmailForm(self.persistence, self.notifier)
        self.tab_widget.addTab(self.email_form, "Configuración de Notificaciones")
        
        # Barra de estado
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Listo")
    
    def _create_menu(self):
        """Crea la barra de menú"""
        self.menuBar().setStyleSheet("""
            QMenuBar {
                background-color: #f0f0f2;
                border-bottom: 1px solid #d8d8d8;
                padding: 2px;
            }
            QMenuBar::item {
                spacing: 5px;
                padding: 5px 15px;
                background: transparent;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background: #e0e0e5;
            }
            QMenuBar::item:pressed {
                background: #d0d0d5;
            }
            QMenu {
                background-color: #ffffff;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 25px 5px 30px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #e8f0ff;
                color: #000000;
            }
            QMenu::separator {
                height: 1px;
                background: #d0d0d0;
                margin: 5px 15px;
            }
            QMenu::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        
        # Menú Archivo
        file_menu = self.menuBar().addMenu("&Archivo")
        
        # Acción Nuevo Request
        new_action = QAction(QIcon("icons/new.png"), "&Nuevo Request", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._new_request)
        file_menu.addAction(new_action)
        
        # Acción Importar Request
        import_action = QAction("&Importar Request", self)
        import_action.triggered.connect(self._import_request)
        file_menu.addAction(import_action)
        
        file_menu.addSeparator()
        
        # Acción Salir
        exit_action = QAction("&Salir", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Menú Monitor
        monitor_menu = self.menuBar().addMenu("&Monitor")
        
        # Acción Verificar Ahora
        check_action = QAction("&Verificar Ahora", self)
        check_action.setShortcut("F5")
        check_action.triggered.connect(self._check_now)
        monitor_menu.addAction(check_action)
        
        # Acción Actualizar Lista
        refresh_action = QAction("&Actualizar Lista", self)
        refresh_action.setShortcut("F6")
        refresh_action.triggered.connect(self._refresh_monitoring)
        monitor_menu.addAction(refresh_action)
        
        # Menú Ayuda
        help_menu = self.menuBar().addMenu("A&yuda")
        
        # Acción Acerca de
        about_action = QAction("&Acerca de", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _create_toolbar(self):
        """Crea la barra de herramientas"""
        toolbar = QToolBar("Barra de herramientas principal")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # Acción Nuevo Request
        new_action = QAction("Nuevo", self)
        new_action.setStatusTip("Crear nuevo request SOAP")
        new_action.triggered.connect(self._new_request)
        toolbar.addAction(new_action)
        
        # Acción Verificar Ahora
        check_action = QAction("Verificar", self)
        check_action.setStatusTip("Verificar servicios SOAP ahora")
        check_action.triggered.connect(self._check_now)
        toolbar.addAction(check_action)
        
        # Separador
        toolbar.addSeparator()
        
        # Acción Actualizar
        refresh_action = QAction("Actualizar", self)
        refresh_action.setStatusTip("Actualizar panel de monitoreo")
        refresh_action.triggered.connect(self._refresh_monitoring)
        toolbar.addAction(refresh_action)
    
    def _new_request(self):
        """Manejador para crear un nuevo request"""
        self.tab_widget.setCurrentWidget(self.request_form)
        self.request_form.clear_form()
        self.statusBar.showMessage("Nuevo request SOAP")
    
    def _import_request(self):
        """Manejador para importar un request desde archivo"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Importar Request", "", "Archivos XML (*.xml);;Todos los archivos (*)"
        )
        
        if file_path:
            try:
                # Cargar archivo XML
                with open(file_path, 'r', encoding='utf-8') as f:
                    xml_content = f.read()
                
                # Mostrar en formulario de request
                self.tab_widget.setCurrentWidget(self.request_form)
                self.request_form.set_request_xml(xml_content)
                self.statusBar.showMessage(f"XML importado: {os.path.basename(file_path)}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error de Importación", 
                                    f"Error al importar XML: {str(e)}")
                logger.error(f"Error al importar XML: {str(e)}")
    
    def _check_now(self):
        """Manejador para verificar servicios ahora"""
        self.statusBar.showMessage("Verificando servicios SOAP...")
        self.monitoring_panel.check_all_services()
        self.statusBar.showMessage("Verificación completada", 5000)
    
    def _refresh_monitoring(self):
        """Manejador para actualizar panel de monitoreo"""
        self.monitoring_panel.refresh_services_list()
        self.statusBar.showMessage("Panel de monitoreo actualizado", 3000)
    
    def _show_about(self):
        """Muestra información acerca de la aplicación"""
        QMessageBox.about(
            self,
            "Acerca de Monitor de Servicios SOAP",
            "<h2>Monitor de Servicios SOAP</h2>"
            "<p>Aplicación para monitorear y validar servicios SOAP.</p>"
            "<p>Versión 1.0</p>"
            "<p>&copy; 2025 - Todos los derechos reservados</p>"
        )
    
    def closeEvent(self, event):
        """Manejador para evento de cierre de ventana"""
        # Detener programador
        self.scheduler.stop()
        logger.info("Aplicación cerrada correctamente")
        event.accept()

if __name__ == "__main__":
    # Crear aplicación Qt
    app = QApplication(sys.argv)
    
    # Crear y mostrar ventana principal
    window = MainWindow()
    window.show()
    
    # Ejecutar bucle de eventos
    sys.exit(app.exec_())