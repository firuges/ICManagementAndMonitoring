import sys
import ctypes
import logging
import os
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
                # Obtener el ejecutable actual
                if getattr(sys, 'frozen', False):
                    # Estamos ejecutando desde .exe
                    executable = sys.executable
                    # Para .exe, no pasar argumentos de Python, solo argumentos de la aplicación
                    app_args = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else ''
                else:
                    # Estamos ejecutando desde script Python
                    executable = sys.executable
                    # Incluir el script principal y sus argumentos
                    app_args = ' '.join(sys.argv)
                
                logging.info(f"Reiniciando como admin: {executable} con argumentos: {app_args}")
                
                # Usar ShellExecute para reiniciar con UAC
                result = ctypes.windll.shell32.ShellExecuteW(
                    None,           # hwnd
                    "runas",        # lpVerb (ejecutar como admin)
                    executable,     # lpFile (ejecutable)
                    app_args,       # lpParameters (argumentos)
                    None,           # lpDirectory
                    1               # nShowCmd (SW_SHOWNORMAL)
                )
                
                if result > 32:  # Éxito en ShellExecute
                    # Salir de la instancia actual solo si el reinicio fue exitoso
                    logging.info("Reinicio como administrador exitoso, cerrando instancia actual")
                    sys.exit(0)
                else:
                    # Error en ShellExecute
                    error_msg = f"Error al reiniciar como administrador. Código: {result}"
                    logging.error(error_msg)
                    QMessageBox.critical(self, "Error", error_msg)
                    
            except Exception as e:
                logging.error(f"Error al reiniciar como administrador: {str(e)}", exc_info=True)
                QMessageBox.critical(self, "Error", 
                    f"No se pudo reiniciar la aplicación como administrador.\n\n"
                    f"Error: {str(e)}\n\n"
                    f"Por favor, cierre la aplicación y ejecútela manualmente como administrador.")

def should_show_admin_dialog():
    """
    Determina si se debe mostrar el diálogo de verificación de administrador.
    
    Returns:
        bool: True si se debe mostrar el diálogo
    """
    # No mostrar si se pasan argumentos de línea de comandos (modo headless)
    if len(sys.argv) > 1:
        # Verificar si hay argumentos que indiquen modo headless
        headless_args = ['--headless', '--check', '--check-all', '--scheduled-task']
        for arg in sys.argv[1:]:
            if any(headless_arg in arg for headless_arg in headless_args):
                return False
            # Si el primer argumento no empieza con '-', podría ser un nombre de servicio
            if not arg.startswith('-'):
                return False
    
    return True