#!/usr/bin/env python3
"""
Script de prueba para validar la creación de tareas programadas.
"""

import sys
import os
import logging
from datetime import datetime

# Añadir directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.scheduler import SOAPMonitorScheduler

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('test_task')

def test_task_creation():
    """Prueba la creación de una tarea de prueba"""
    
    scheduler = SOAPMonitorScheduler()
    
    # Configuración de prueba
    test_config = {
        'days_of_week': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
        'start_time': '09:00',
        'duration_hours': 8,
        'hidden': True,
        'run_when_logged_off': True,
        'highest_privileges': True
    }
    
    print("=== Prueba de Creación de Tarea ===")
    print(f"Servicio de prueba: TestService")
    print(f"Configuración: {test_config}")
    print("=" * 40)
    
    # Intentar crear tarea
    success = scheduler.generate_system_task_advanced(
        "TestService", 
        15,  # 15 minutos
        test_config
    )
    
    if success:
        print("✅ Tarea creada exitosamente")
        
        # Verificar estado
        status = scheduler.get_task_status("TestService")
        print(f"Estado de la tarea: {status}")
        
        # Limpiar (eliminar tarea de prueba)
        if scheduler.remove_system_task("TestService"):
            print("🧹 Tarea de prueba eliminada")
        
    else:
        print("❌ Error al crear la tarea")
        print("Revise los logs para más detalles")

if __name__ == "__main__":
    test_task_creation()