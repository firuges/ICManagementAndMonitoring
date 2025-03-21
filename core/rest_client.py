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
                     timeout: int = 30) -> Tuple[bool, Dict[str, Any]]:
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
        try:
            # Normalizar método a mayúsculas
            method = method.upper()
            
            # Configuración por defecto para headers
            if headers is None:
                headers = {}
            
            # Agregar cabecera de Content-Type si no está especificada y enviamos JSON
            if json_data is not None and 'Content-Type' not in headers:
                headers['Content-Type'] = 'application/json'
            
            # Realizar la petición
            self.logger.info(f"Enviando request REST {method} a {url}")
            
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                json=json_data,
                timeout=timeout,
                verify=True  # Podría ser configurable para entornos de desarrollo
            )
            
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
        
        Args:
            response (Dict[str, Any]): Respuesta REST a validar
            validation_schema (Dict[str, Any], optional): Esquema de validación
            
        Returns:
            Tuple[bool, str, str]: (éxito, mensaje, nivel: 'success'|'warning'|'failed'|'error')
        """
        # Implementación similar a tu validate_response_advanced en SOAPClient
        # Pero adaptada a las estructuras típicas de REST (JSON)
        
        # Ejemplo simplificado:
        if not validation_schema:
            # Si no hay esquema, verificamos solo el status_code
            if 'status_code' in response and 200 <= response['status_code'] < 300:
                return True, "Respuesta HTTP correcta", "success"
            else:
                return False, f"Status code incorrecto: {response.get('status_code', 'desconocido')}", "error"
        
        # El resto de la implementación sería similar a tu función actual
        # Adaptándola a las convenciones REST