import time
import logging
from typing import Callable, Any, Dict, Tuple

logger = logging.getLogger('retry_handler')

class RetryHandler:
    """Gestor centralizado de reintentos para solicitudes HTTP/SOAP"""
    
    @staticmethod
    def execute_with_retry(operation: Callable, 
                          max_retries: int = 3, 
                          initial_delay: float = 1.0,
                          backoff_factor: float = 2.0,
                          exception_types: tuple = Exception) -> Tuple[bool, Dict[str, Any]]:
        """
        Ejecuta una operación con política de reintentos.
        
        Args:
            operation: Función a ejecutar
            max_retries: Número máximo de reintentos
            initial_delay: Tiempo inicial de espera entre reintentos (segundos)
            backoff_factor: Factor de incremento del tiempo de espera
            exception_types: Tipos de excepción que provocarán reintento
            
        Returns:
            (éxito, resultado/error)
        """
        retry_count = 0
        current_delay = initial_delay
        
        while True:
            try:
                # Ejecutar la operación
                result = operation()
                # Si llegamos aquí, la operación fue exitosa
                return True, result
                
            except exception_types as e:
                retry_count += 1
                
                # Si excedimos los reintentos, reportar el error
                if retry_count > max_retries:
                    logger.error(f"Error después de {max_retries} reintentos: {str(e)}")
                    return False, {
                        "error": f"Error después de {max_retries} reintentos: {str(e)}",
                        "status": "max_retries_exceeded"
                    }
                
                # Registrar y esperar antes del siguiente intento
                logger.warning(f"Intento {retry_count}/{max_retries} falló: {str(e)}. "
                              f"Reintentando en {current_delay}s...")
                time.sleep(current_delay)
                
                # Incrementar el tiempo de espera para el próximo intento
                current_delay *= backoff_factor