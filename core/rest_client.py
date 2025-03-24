import requests
import logging
import json
from typing import Dict, Any, Tuple, Optional

class RESTClient:
    """Cliente REST para enviar y validar requests"""
    
    def __init__(self):
        """Inicializa el cliente REST"""
        self.logger = logging.getLogger('rest_client')
    
    def send_request(self, url: str, method: str = 'GET', 
                headers: Dict[str, str] = None, 
                params: Dict[str, Any] = None,
                data: Any = None,
                json_data: Dict[str, Any] = None,
                timeout: int = 30,
                max_retries: int = 1) -> Tuple[bool, Dict[str, Any]]:
        """
        Envía un request REST.
        
        Args:
            url (str): URL del endpoint
            method (str): Método HTTP (GET, POST, PUT, DELETE, etc.)
            headers (Dict[str, str], optional): Cabeceras HTTP
            params (Dict[str, Any], optional): Parámetros de query string
            data (Any, optional): Datos para enviar en el body (string, bytes, etc.)
            json_data (Dict[str, Any], optional): Datos JSON para enviar en el body
            timeout (int, optional): Timeout en segundos
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (éxito, resultado/error)
        """
        retry_count = 0
    
        while retry_count <= max_retries:
            try:
                # Normalizar método a mayúsculas
                method = method.upper()
                
                # Configuración por defecto para headers
                if headers is None:
                    headers = {}
                
                # Agregar cabecera de Content-Type si no está especificada y enviamos JSON
                if json_data is not None and 'Content-Type' not in headers:
                    headers['Content-Type'] = 'application/json'
                
                # Log detallado antes de enviar la solicitud
                self.logger.info(f"Enviando request REST {method} a {url}")
                self.logger.debug(f"Headers: {headers}")
                self.logger.debug(f"Params: {params}")
                if json_data:
                    self.logger.debug(f"JSON data: {json_data}")
                    
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    data=data,
                    json=json_data,  # ¡Asegurarnos de enviar correctamente los datos JSON!
                    timeout=timeout,
                    verify=False  # Considerar cambiar a True en producción
                )
                
                # Log de respuesta
                self.logger.debug(f"Código de estado: {response.status_code}")
            
                # Intentar parsear la respuesta como JSON
                try:
                    response_data = response.json()
                except ValueError:
                    # Si no es JSON, devolver el texto
                    response_data = {'text': response.text}
                
                # Verificar código de estado
                if response.status_code >= 200 and response.status_code < 300:
                    return True, {
                        'status_code': response.status_code,
                        'headers': dict(response.headers),
                        'response': response_data,
                        'method': method
                    }
                else:
                    return False, {
                        'error': f"Error HTTP: {response.status_code}",
                        'status_code': response.status_code,
                        'headers': dict(response.headers),
                        'response': response_data,
                        'method': method
                    }
                    
            except requests.exceptions.Timeout:
                self.logger.error(f"Timeout en request REST a {url}")
                return False, {
                    'error': "Timeout en la petición",
                    'status': "timeout" 
                }
            except requests.exceptions.ConnectionError:
                self.logger.error(f"Error de conexión en request REST a {url}")
                return False, {
                    'error': "Error de conexión al servidor",
                    'status': "connection_error"
                }
            except Exception as e:
                self.logger.error(f"Error al enviar request REST: {str(e)}", exc_info=True)
                return False, {
                    'error': f"Error inesperado: {str(e)}",
                    'status': "error"
                }
        
    def validate_response(self, response: Dict[str, Any], 
                   validation_schema: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, str]:
        """
        Valida la respuesta REST con reglas avanzadas configurables.
        Delegación a SOAPClient para mantener consistencia.
        """
        from core.soap_client import SOAPClient
        soap_client = SOAPClient()
        return soap_client.validate_response_advanced(response, validation_schema)