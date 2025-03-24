import sys
import ctypes
import logging
from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QPushButton, 
    QApplication, QDialog, QMessageBox
)
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import Qt

class AdminCheckDialog(QDialog):
    """Diálogo que verifica y avisa sobre permisos de administrador al iniciar"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Verificación de permisos")
        self.setFixedSize(500, 280)
        
        # Evitar que se cierre con Escape
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self._create_ui()
    
    def _create_ui(self):
        """Crea la interfaz del diálogo"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Determinar si se ejecuta como administrador
        is_admin = self._check_admin()
        
        # Título
        title_label = QLabel("Verificación de permisos de administrador")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Separador
        separator = QLabel()
        separator.setFrameShape(QLabel.HLine)
        separator.setFrameShadow(QLabel.Sunken)
        layout.addWidget(separator)
        
        # Mensaje de estado
        if is_admin:
            status_label = QLabel("✅ La aplicación se está ejecutando con permisos de administrador")
            status_label.setStyleSheet("color: green; font-weight: bold; font-size: 14px; margin: 10px 0;")
        else:
            status_label = QLabel("⚠️ La aplicación se está ejecutando sin permisos de administrador")
            status_label.setStyleSheet("color: #CC6600; font-weight: bold; font-size: 14px; margin: 10px 0;")
        layout.addWidget(status_label)
        
        # Información adicional
        info_text = """
        <p>Para utilizar todas las funcionalidades de la aplicación, especialmente la programación de tareas en el sistema, se recomienda ejecutar como administrador.</p>
        
        <p><b>Si continúa sin permisos de administrador:</b></p>
        <ul>
            <li>Podrá usar todas las funciones de monitoreo dentro de la aplicación</li>
            <li>No podrá crear automáticamente tareas en el programador de Windows</li>
            <li>Podrá exportar los archivos necesarios para crear tareas manualmente</li>
        </ul>
        """
        
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Botones
        buttons_layout = QVBoxLayout()
        
        if not is_admin and sys.platform.startswith('win'):
            # Botón para reiniciar como administrador
            restart_btn = QPushButton("Reiniciar como administrador")
            restart_btn.setStyleSheet("""
                background-color: #4a86e8;
                color: white;
                padding: 8px;
                font-weight: bold;
                border-radius: 4px;
            """)
            restart_btn.clicked.connect(self._restart_as_admin)
            buttons_layout.addWidget(restart_btn)
        
        # Botón para continuar
        continue_btn = QPushButton("Continuar de todos modos")
        if not is_admin:
            continue_btn.setStyleSheet("""
                background-color: #f0f0f0;
                padding: 8px;
                border-radius: 4px;
            """)
        else:
            continue_btn.setStyleSheet("""
                background-color: #4a86e8;
                color: white;
                padding: 8px;
                font-weight: bold;
                border-radius: 4px;
            """)
        continue_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(continue_btn)
        
        layout.addLayout(buttons_layout)
    
    def _check_admin(self):
        """
        Verifica si la aplicación está ejecutándose con permisos de administrador.
        
        Returns:
            bool: True si se ejecuta como administrador, False en caso contrario.
        """
        try:
            if sys.platform.startswith('win'):
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else:
                # En sistemas Unix, verificar si el UID es 0 (root)
                return os.geteuid() == 0
        except:
            return False
    
    def _restart_as_admin(self):
        """Reinicia la aplicación con permisos de administrador (solo Windows)"""
        if sys.platform.startswith('win'):
            try:
                # Usar ShellExecute para reiniciar con UAC
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, " ".join(sys.argv), None, 1)
                # Salir de la instancia actual
                sys.exit(0)
            except Exception as e:
                logging.error(f"Error al reiniciar como administrador: {str(e)}")
                QMessageBox.critical(self, "Error", 
                    "No se pudo reiniciar la aplicación como administrador.\n\n"
                    "Por favor, cierre la aplicación y ejecútela manualmente como administrador.")

# Modificar en app.py, dentro de la función main():

def main():
    """Función principal de la aplicación"""
    # Configurar logging
    logger = setup_logging()
    
    # Parsear argumentos
    args = parse_arguments()
    
    try:
        # Determinar modo de ejecución
        if args.headless or args.check or args.check_all:
            run_headless(args, logger)
        else:
            # Verificar permisos antes de iniciar la GUI
            app = QApplication(sys.argv)
            
            # Mostrar diálogo de verificación de administrador si no se especificó --no-admin-check
            if not getattr(args, 'no_admin_check', False):
                admin_dialog = AdminCheckDialog()
                if admin_dialog.exec_() != QDialog.Accepted:
                    sys.exit(0)
            
            run_gui()
    except Exception as e:
        logger.error(f"Error en la aplicación: {str(e)}", exc_info=True)
        sys.exit(1)