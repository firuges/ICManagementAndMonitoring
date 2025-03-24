import os
import logging
import xml.etree.ElementTree as ET
import xmltodict
import zeep
import json
import datetime
import requests
from typing import Dict, Any, Tuple, Optional, Union, List
from zeep.exceptions import TransportError, XMLSyntaxError
def json_serial(obj):
        """Serializador JSON para objetos no serializables por defecto."""
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")


# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('soap_client')

class SOAPClient:
    """Cliente SOAP para enviar y validar requests"""
    
    def __init__(self):
        """Inicializa el cliente SOAP"""
        self.clients_cache = {}  # Cache de clientes SOAP por URL WSDL
    
    def get_client(self, wsdl_url: str) -> zeep.Client:
        """
        Obtiene un cliente SOAP para una URL WSDL, utilizando caché.
        
        Args:
            wsdl_url (str): URL del WSDL del servicio
            
        Returns:
            zeep.Client: Cliente SOAP inicializado
        """
        if wsdl_url not in self.clients_cache:
            try:
                logger.info(f"Creando nuevo cliente SOAP para {wsdl_url}")
                self.clients_cache[wsdl_url] = zeep.Client(wsdl=wsdl_url)
            except Exception as e:
                logger.error(f"Error al crear cliente SOAP para {wsdl_url}: {str(e)}")
                raise
        
        return self.clients_cache[wsdl_url]
    
    def send_raw_request(self, wsdl_url: str, request_xml: str, 
                    timeout: int = 30, 
                    max_retries: int = 3,
                    validate_url: bool = True) -> Tuple[bool, Dict[str, Any]]:
        """
        Envía un request SOAP XML directamente con manejo robusto de operaciones.
        
        Args:
            wsdl_url (str): URL del WSDL del servicio
            request_xml (str): XML del request SOAP
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (éxito, resultado/error)
        """
        if validate_url:
            from .utils import validate_endpoint_url
            if not validate_endpoint_url(wsdl_url, timeout=5):
                return False, {
                    "error": f"URL del WSDL no accesible: {wsdl_url}",
                    "status": "url_error"
                }
        retry_count = 0
        while retry_count <= max_retries:
            try:
                # Parsear el XML para obtener el método y los parámetros
                request_dict = xmltodict.parse(request_xml)
                
                # Extraer el nombre del método (primer elemento del Body)
                envelope_key = None
                for k in request_dict.keys():
                    if k.endswith('Envelope'):
                        envelope_key = k
                        break
                        
                if not envelope_key:
                    return False, {"error": "No se encontró el elemento Envelope en el XML SOAP"}
                    
                envelope = request_dict[envelope_key]
                
                # Encontrar la clave del Body con gestión de namespaces
                body_key = None
                for k in envelope.keys():
                    if k.endswith('Body'):
                        body_key = k
                        break
                        
                if not body_key or not envelope[body_key]:
                    return False, {"error": "No se encontró el elemento Body en el XML SOAP"}
                    
                body = envelope[body_key]
                
                # El primer elemento del Body es el método
                if not body or len(body) == 0:
                    return False, {"error": "Body vacío en el XML SOAP"}
                    
                # Extraer el nombre del método eliminando prefijo de namespace
                method_full_name = list(body.keys())[0]
                method_name = method_full_name.split(':')[-1]
                
                # Eliminar 'Request' del nombre del método si existe
                if method_name.endswith('Request'):
                    method_name = method_name[:-7]  # Remover 'Request'
                    
                logger.info(f"Método SOAP determinado: {method_name}")
                
                # Extraer los parámetros
                method_params = body[method_full_name]
                
                # Obtener cliente
                client = self.get_client(wsdl_url)
                
                transport = zeep.Transport(timeout=timeout)
                self.clients_cache[wsdl_url] = zeep.Client(wsdl=wsdl_url, transport=transport)
                
                # PARTE CRÍTICA: Manejo seguro de las operaciones
                available_methods = []
                try:
                    # Intentar obtener operaciones de manera segura
                    if hasattr(client.service, '_operations'):
                        operations = client.service._operations
                        # Verificar si operations es un diccionario (caso común)
                        if isinstance(operations, dict):
                            available_methods = list(operations.keys())
                        # Verificar si es un objeto con atributos name
                        elif hasattr(operations, '__iter__'):
                            try:
                                available_methods = [op.name for op in operations if hasattr(op, 'name')]
                            except (AttributeError, TypeError):
                                # Fallback si hay algún problema accediendo a 'name'
                                available_methods = []
                    
                    # Fallback: obtener métodos directamente de los servicios
                    if not available_methods and hasattr(client, 'wsdl'):
                        for service in client.wsdl.services.values():
                            for port in service.ports.values():
                                for operation in port.binding._operations.values():
                                    available_methods.append(operation.name)
                                    
                    logger.debug(f"Métodos disponibles: {available_methods}")
                except Exception as e:
                    logger.warning(f"No se pudieron determinar los métodos disponibles: {str(e)}")
                    available_methods = []
                
                # Buscar coincidencia del método
                method_match = None
                
                # Comprobación exacta
                if method_name in available_methods:
                    method_match = method_name
                else:
                    # Búsqueda por coincidencia parcial (case insensitive)
                    for available_method in available_methods:
                        if method_name.lower() in available_method.lower():
                            method_match = available_method
                            logger.info(f"Usando método por coincidencia parcial: {method_match}")
                            break
                
                # Si no encontramos coincidencia pero hay métodos disponibles, usar el primero
                if not method_match and available_methods:
                    method_match = available_methods[0]
                    logger.warning(f"Usando método predeterminado: {method_match}")
                
                # Si no hay métodos disponibles, intentar usar el método extraído directamente
                if not method_match:
                    method_match = method_name
                    logger.warning(f"No se encontraron métodos disponibles. Usando: {method_match}")
                
                # Ejecutar la llamada SOAP con manejo robusto de errores
                try:
                    # Normalizar parámetros eliminando prefijos de namespace
                    normalized_params = self._normalize_params(method_params) if isinstance(method_params, dict) else {}
                    
                    # Intentar ejecutar el método
                    response = None
                    if hasattr(client.service, method_match):
                        # Ejecución mediante atributo
                        service_method = getattr(client.service, method_match)
                        if callable(service_method):
                            response = service_method(**normalized_params)
                    else:
                        # Ejecución mediante índice
                        try:
                            # Configurar historial para capturar la respuesta XML
                            history = []
                            
                            # Crear plugin para capturar respuesta
                            class CapturePlugin(zeep.Plugin):
                                def ingress(self, envelope, http_headers, operation):
                                    # Capturar respuesta XML
                                    xml_string = etree.tostring(envelope, encoding='unicode')
                                    history.append(xml_string)
                                    return envelope
                            
                            # Añadir plugin al cliente
                            plugins = [CapturePlugin()]
                            transport = client.transport
                            transport.session.auth = None  # Evitar posibles problemas de autenticación
                            
                            # Ejecutar llamada con plugins
                            response = client.service[method_name](**normalized_params, _plugins=plugins)
                            
                            # Procesar la respuesta con el método normal
                            response_dict = self._zeep_object_to_dict(response)
                            
                            # Si la respuesta está vacía pero tenemos XML capturado, procesar el XML directamente
                            if (not response_dict or response_dict == {}) and history:
                                logger.info("Respuesta Zeep vacía, procesando XML directamente")
                                xml_response = history[-1]  # Última respuesta capturada
                                direct_response = self._extract_soap_response_xml(xml_response)
                                
                                # Combinar resultados
                                result = {
                                    "method": method_name,
                                    "response": direct_response or response_dict,
                                    "status": "ok",
                                    "_raw_xml_available": bool(history)
                                }
                                
                                # Guardar XML para diagnóstico
                                self._save_debug_xml(method_name, request_xml, xml_response)
                                
                                return True, result
                            else:
                                # Respuesta normal procesada correctamente
                                return True, {
                                    "method": method_name,
                                    "response": response_dict,
                                    "status": "ok"
                                }
                        except Exception as call_error:
                            logger.error(f"Error al llamar al método {method_match}: {str(call_error)}")
                            # Intento alternativo: enviar directamente el XML
                            return self._send_direct_xml(wsdl_url, request_xml)
                    
                    if response is None:
                        return False, {
                            "error": f"No se obtuvo respuesta del método {method_match}",
                            "status": "no_response"
                        }
                    
                    # Convertir respuesta a diccionario
                    response_dict = self._zeep_object_to_dict(response)
                    
                    return True, {
                        "method": method_match,
                        "response": response_dict,
                        "status": "ok"
                    }
                except requests.exceptions.Timeout:  
                    retry_count += 1
                    if retry_count <= max_retries:
                        logger.warning(f"Timeout al intentar conectar con el servicio. Reintentando ({retry_count}/{max_retries})...")
                        time.sleep(1 * retry_count)  # Esperar más tiempo en cada reintento
                    else:
                        logger.error(f"Error de timeout después de {max_retries} reintentos")
                        return False, {
                            "error": f"Timeout al intentar conectar con el servicio después de {max_retries} reintentos: {wsdl_url}",
                            "status": "timeout"
                        }
                except (requests.exceptions.ConnectionError, ConnectionError, ConnectionRefusedError, ConnectionAbortedError) as e:
                    # Errores de conexión
                    retry_count += 1
                    if retry_count <= max_retries:
                        logger.warning(f"Error de conexión. Reintentando ({retry_count}/{max_retries})...")
                        time.sleep(1 * retry_count)  # Esperar más tiempo en cada reintento
                    else:
                        logger.error(f"Error al enviar request SOAP: {str(e)}", exc_info=True)
                        return False, {
                            "error": f"Error de conexión: {str(e)}",
                            "status": "connection_error"
                        }
                except zeep.exceptions.Fault as fault:
                    # SOAP Faults
                    logger.error(f"Error SOAP Fault: {str(fault)}")
                    return False, {
                        "error": f"SOAP Fault: {str(fault)}",
                        "status": "soap_fault" 
                    }
                except Exception as e:
                    retry_count += 1
                    
                    # Determinar si el error es de tipo timeout o conexión
                    is_timeout = "timeout" in str(e).lower() or isinstance(e, requests.exceptions.Timeout)
                    is_connection = isinstance(e, (requests.exceptions.ConnectionError, ConnectionError, 
                                            ConnectionRefusedError, ConnectionAbortedError))
                    
                    # Si es un error recuperable y no excedimos los reintentos
                    if retry_count <= max_retries and (is_timeout or is_connection):
                        error_type = "timeout" if is_timeout else "conexión"
                        logger.warning(f"Error de {error_type}. Reintentando ({retry_count}/{max_retries})...")
                        time.sleep(1 * retry_count)  # Esperar más tiempo en cada reintento
                    else:
                        # Error no recuperable o máximo de reintentos alcanzado
                        if is_timeout:
                            status = "timeout"
                            error_msg = f"Timeout al intentar conectar con el servicio después de {max_retries} reintentos"
                        elif is_connection:
                            status = "connection_error"
                            error_msg = f"Error de conexión después de {max_retries} reintentos"
                        elif isinstance(e, zeep.exceptions.Fault):
                            status = "soap_fault"
                            error_msg = f"SOAP Fault: {str(e)}"
                        else:
                            status = "error"
                            error_msg = f"Error inesperado: {str(e)}"
                            
                        logger.error(f"{error_msg}", exc_info=True)
                        return False, {
                            "error": error_msg,
                            "status": status
                        }
                    
            except Exception as e:
                logger.error(f"Error al enviar request SOAP: {str(e)}", exc_info=True)
                return False, {
                    "error": f"Error inesperado: {str(e)}",
                    "status": "error"
                }
    
    def _validate_wsdl_url(self, wsdl_url: str) -> bool:
        """
        Valida que la URL del WSDL sea accesible.
        
        Args:
            wsdl_url (str): URL del WSDL
            
        Returns:
            bool: True si la URL es accesible
        """
        try:
            import requests
            # Intento HEAD primero para no descargar todo el WSDL
            response = requests.head(wsdl_url, timeout=5, verify=False)
            
            # Si HEAD falla, puede ser porque el servidor no lo soporta
            if response.status_code >= 400:
                # Intentar con GET
                response = requests.get(wsdl_url, timeout=5, verify=False)
                
            return response.status_code < 400
        except Exception as e:
            logger.warning(f"Error al validar URL del WSDL {wsdl_url}: {str(e)}")
            return False
    
    def _save_debug_xml(self, service_name: str, request_xml: str, response_xml: str) -> None:
        """
        Guarda XMLs de request y response para diagnóstico.
        
        Args:
            service_name (str): Nombre del servicio
            request_xml (str): XML de request
            response_xml (str): XML de response
        """
        try:
            # Crear directorio debug si no existe
            debug_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'debug')
            os.makedirs(debug_dir, exist_ok=True)
            
            # Nombre de archivo con timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{service_name}_{timestamp}"
            
            # Guardar request
            with open(os.path.join(debug_dir, f"{filename}_request.xml"), 'w', encoding='utf-8') as f:
                f.write(request_xml)
                
            # Guardar response
            with open(os.path.join(debug_dir, f"{filename}_response.xml"), 'w', encoding='utf-8') as f:
                f.write(response_xml)
                
            logger.info(f"Debug XML guardado en {debug_dir}/{filename}_*.xml")
        except Exception as e:
            logger.error(f"Error guardando debug XML: {str(e)}")
    
    def _normalize_params(self, params_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza los parámetros eliminando prefijos de namespace.
        
        Args:
            params_dict (Dict[str, Any]): Diccionario con parámetros de entrada
            
        Returns:
            Dict[str, Any]: Diccionario normalizado
        """
        if not params_dict or not isinstance(params_dict, dict):
            return {}
            
        normalized = {}
        
        for key, value in params_dict.items():
            # Eliminar prefijo de namespace si existe
            clean_key = key.split(':')[-1]
            
            # Procesar recursivamente los diccionarios anidados
            if isinstance(value, dict):
                normalized[clean_key] = self._normalize_params(value)
            elif isinstance(value, list):
                # Procesar listas de diccionarios
                if all(isinstance(item, dict) for item in value):
                    normalized[clean_key] = [self._normalize_params(item) for item in value]
                else:
                    normalized[clean_key] = value
            else:
                normalized[clean_key] = value
                
        return normalized
    
    def _send_direct_xml(self, wsdl_url: str, request_xml: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Método alternativo: envía el XML directamente al endpoint SOAP sin procesamiento.
        
        Args:
            wsdl_url (str): URL del WSDL del servicio
            request_xml (str): XML completo del request
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (éxito, resultado)
        """
        try:
            # Obtener cliente SOAP
            client = self.get_client(wsdl_url)
            
            # Determinar la dirección del servicio de manera robusta
            service_url = self._extract_service_url(client, wsdl_url)
                    
            if not service_url:
                return False, {
                    "error": "No se pudo determinar la URL del servicio",
                    "status": "url_error"
                }
            
            logger.info(f"Realizando llamada directa XML a: {service_url}")
            
            # Configurar cabeceras HTTP
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': '""'
            }
            
            # Realizar petición HTTP directamente
            import requests
            import time
            
            # Configuración mejorada para manejo de reintentos
            max_retries = 3
            retry_delay = 2  # segundos
            verify_ssl = False  # Considera cambiar a True en producción
        
            for retry in range(max_retries):
                try:
                    response = requests.post(
                        service_url,
                        data=request_xml,
                        headers=headers,
                        verify=verify_ssl,
                        timeout=30
                    )
                    break  # Salir del bucle si la petición es exitosa
                except (requests.exceptions.Timeout, 
                        requests.exceptions.ConnectionError) as conn_err:
                    if retry < max_retries - 1:
                        logger.warning(f"Intento {retry+1}/{max_retries} falló: {str(conn_err)}. Reintentando en {retry_delay}s...")
                        time.sleep(retry_delay)
                        # Incrementar el tiempo de espera para el siguiente intento
                        retry_delay *= 2
                    else:
                        # Si es el último intento, propagar el error
                        raise
            
            # Verificar si la respuesta es exitosa
            if response.status_code != 200:
                return False, {
                    "error": f"Error HTTP: {response.status_code}",
                    "response_text": response.text[:500],  # Limitar longitud
                    "status": "http_error"
                }
            
            # Procesar respuesta XML
            try:
                # Guardar respuesta XML para diagnóstico
                self._save_debug_xml("direct_call", request_xml, response.text)
                
                # Parsear la respuesta de manera segura
                response_dict = xmltodict.parse(response.text)
                
                # Buscar un posible error SOAP en la respuesta
                soap_fault = self._extract_soap_fault(response_dict)
                if soap_fault:
                    return False, {
                        "error": f"SOAP Fault en respuesta directa: {soap_fault}",
                        "response": response_dict,
                        "status": "soap_fault"
                    }
                
                return True, {
                    "method": "direct_xml_call",
                    "response": response_dict,
                    "status": "ok"
                }
            except Exception as xml_parse_error:
                logger.error(f"Error al parsear respuesta XML: {str(xml_parse_error)}")
                return False, {
                    "error": f"Error al parsear respuesta: {str(xml_parse_error)}",
                    "response_text": response.text[:500],  # Limitar longitud
                    "status": "parse_error"
                }
                
        except Exception as e:
            logger.error(f"Error en llamada directa XML: {str(e)}", exc_info=True)
            return False, {
                "error": f"Error en llamada directa: {str(e)}",
                "status": "direct_call_error"
            }
    
    def _extract_service_url(self, client: zeep.Client, wsdl_url: str) -> Optional[str]:
        """
        Extrae la URL del servicio SOAP desde el cliente zeep de manera robusta.
        
        Args:
            client (zeep.Client): Cliente SOAP inicializado
            wsdl_url (str): URL del WSDL original
            
        Returns:
            Optional[str]: URL del servicio o None si no se puede determinar
        """
        service_url = None
        
        # Estrategia 1: Buscar en servicios y puertos
        try:
            services = list(client.wsdl.services.values())
            
            for service in services:
                ports = list(service.ports.values())
                
                for port in ports:
                    # Intentar diferentes ubicaciones de la URL
                    if hasattr(port, 'binding_options') and isinstance(port.binding_options, dict):
                        address = port.binding_options.get('address', {})
                        if isinstance(address, dict) and 'location' in address:
                            service_url = address['location']
                            logger.debug(f"URL encontrada en binding_options: {service_url}")
                            return service_url
                    
                    # Alternativa: buscar en binding.soap_address
                    if hasattr(port, 'binding') and hasattr(port.binding, 'soap_address'):
                        if hasattr(port.binding.soap_address, 'location'):
                            service_url = port.binding.soap_address.location
                            logger.debug(f"URL encontrada en soap_address: {service_url}")
                            return service_url
                            
                    # Intentar obtenerla de binding._operations
                    if hasattr(port, 'binding') and hasattr(port.binding, '_operations'):
                        operations = port.binding._operations
                        for op in operations.values():
                            if hasattr(op, 'location'):
                                service_url = op.location
                                logger.debug(f"URL encontrada en operation: {service_url}")
                                return service_url
        except Exception as e:
            logger.warning(f"Error buscando URL en servicios: {str(e)}")
        
        # Estrategia 2: Buscar directamente en metadatos de cliente
        try:
            if hasattr(client, 'service') and hasattr(client.service, '_binding') and hasattr(client.service._binding, 'address'):
                service_url = client.service._binding.address
                logger.debug(f"URL encontrada en client.service._binding: {service_url}")
                return service_url
        except Exception as e:
            logger.warning(f"Error buscando URL en binding: {str(e)}")
        
        # Estrategia 3: Extraer de la URL del WSDL
        if not service_url:
            try:
                if "?wsdl" in wsdl_url.lower():
                    service_url = wsdl_url.split("?")[0]
                    logger.debug(f"URL extraída del WSDL: {service_url}")
                    return service_url
            except Exception:
                pass
        
        # Fallback: usar la URL del WSDL completa
        if not service_url:
            service_url = wsdl_url
            logger.debug(f"Usando URL de WSDL como fallback: {service_url}")
            
        return service_url
    
    def _extract_soap_fault(self, response_dict: Dict[str, Any]) -> Optional[str]:
        """
        Extrae mensajes de error SOAP Fault de la respuesta.
        
        Args:
            response_dict (Dict[str, Any]): Diccionario de respuesta XML
            
        Returns:
            Optional[str]: Mensaje de error o None si no hay error
        """
        try:
            # Buscar Envelope
            for key, value in response_dict.items():
                if key.endswith('Envelope') and isinstance(value, dict):
                    envelope = value
                    
                    # Buscar Body
                    for body_key, body_value in envelope.items():
                        if body_key.endswith('Body') and isinstance(body_value, dict):
                            body = body_value
                            
                            # Buscar Fault
                            for fault_key, fault_value in body.items():
                                if fault_key.endswith('Fault') and isinstance(fault_value, dict):
                                    # Extraer mensaje de error del Fault
                                    if 'faultstring' in fault_value:
                                        return fault_value['faultstring']
                                    elif 'faultcode' in fault_value:
                                        return f"Código: {fault_value['faultcode']}"
                                    else:
                                        return "SOAP Fault encontrado (sin detalle)"
            return None
        except Exception:
            return None
    
    def _log_soap_details(self, request_dict: Dict[str, Any], method_name: str) -> None:
        """
        Registra detalles del proceso de determinación del método SOAP.
        
        Args:
            request_dict (Dict[str, Any]): Diccionario del request
            method_name (str): Nombre del método determinado
        """
        try:
            # Extraer estructura básica para logging
            envelope_keys = [k for k in request_dict.keys()]
            logger.debug(f"Claves del Envelope: {envelope_keys}")
            
            if len(envelope_keys) > 0:
                envelope = request_dict[envelope_keys[0]]
                body_keys = [k for k in envelope.keys() if k.endswith('Body')]
                
                if body_keys:
                    body = envelope[body_keys[0]]
                    logger.debug(f"Claves del Body: {list(body.keys())}")
                    
            logger.info(f"Método SOAP determinado: {method_name}")
            
        except Exception as e:
            logger.error(f"Error al registrar detalles SOAP: {str(e)}")
    
    
    # Esta función debe reemplazar la función validate_response en rest_client.py

    def validate_response(self, response: Dict[str, Any], 
                        validation_schema: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, str]:
        """
        Valida la respuesta REST con reglas avanzadas configurables.
        Funciona de manera idéntica a validate_response_advanced en SOAPClient.
        
        Args:
            response (Dict[str, Any]): Respuesta REST a validar
            validation_schema (Dict[str, Any], optional): Esquema de validación
            
        Returns:
            Tuple[bool, str, str]: (éxito, mensaje, nivel: 'success'|'warning'|'failed'|'error')
        """
        # Si no hay esquema de validación, éxito por defecto
        if not validation_schema:
            return True, "Respuesta recibida (sin validación de reglas)", "success"
        
        # Inicialización segura del esquema
        if validation_schema is None:
            validation_schema = {}
        elif isinstance(validation_schema, str):
            try:
                # Intentar convertir a diccionario si es un string JSON
                import json
                validation_schema = json.loads(validation_schema)
            except:
                # Si no es un JSON válido, usar esquema simple
                validation_schema = {"status": "ok"}
        
        # Depuración detallada del esquema recibido
        self.logger.debug(f"Esquema de validación: {validation_schema}")
        
        # Caso especial: esquema simple heredado
        if len(validation_schema) == 1 and "status" in validation_schema:
            if validation_schema["status"] == "ok":
                return True, "El servicio respondió correctamente", "success"
        
        # Aplanar respuesta para búsqueda flexible de campos
        # Importar la función del SOAPClient para mantener consistencia
        from core.soap_client import SOAPClient
        soap_client = SOAPClient()
        flat_response = soap_client._flatten_dict(response)
        
        # Depuración: Mostrar campos disponibles en la respuesta
        self.logger.debug(f"Campos disponibles en respuesta: {list(flat_response.keys())[:20]}")
        
        # Obtener configuración del esquema
        success_field = validation_schema.get("success_field", "status")  # Por defecto "status" para REST
        success_values = validation_schema.get("success_values", ["200", "OK", "success"])
        warning_values = validation_schema.get("warning_values", [])
        failed_values = validation_schema.get("failed_values", [])
        expected_fields = validation_schema.get("expected_fields", {})
        validation_strategy = validation_schema.get("validation_strategy", "flexible")
        
        # Convertir valores a cadenas para comparación consistente
        if success_values and not isinstance(success_values, list):
            success_values = [str(success_values)]
        if warning_values and not isinstance(warning_values, list):
            warning_values = [str(warning_values)]
        if failed_values and not isinstance(failed_values, list):
            failed_values = [str(failed_values)]
        
        # Estos deben ser listas
        success_values = [str(v) for v in success_values]
        warning_values = [str(v) for v in warning_values]
        failed_values = [str(v) for v in failed_values]
        
        # Buscar el campo principal de éxito/error
        field_value = None
        field_found = False
        
        # 1. Búsqueda exacta
        if success_field in flat_response:
            field_value = flat_response[success_field]
            field_found = True
            self.logger.debug(f"Campo '{success_field}' encontrado directamente")
        else:
            # 2. Búsqueda flexible
            for key in flat_response.keys():
                # Coincidencia al final de la clave o clave parcial
                if key.endswith(success_field) or success_field in key.split('.'):
                    field_value = flat_response[key]
                    field_found = True
                    self.logger.debug(f"Campo '{success_field}' encontrado como '{key}'")
                    break
        
        # Evaluar resultado según el campo principal
        if field_found:
            # Convertir a string para comparación consistente
            str_value = str(field_value).strip()
            self.logger.debug(f"Valor encontrado: '{str_value}', comparando con success_values: {success_values}")
            
            # Verificar si es éxito
            if str_value in success_values:
                # Verificar campos adicionales si están definidos
                if expected_fields:
                    for field_name, expected_value in expected_fields.items():
                        # Buscar el campo esperado
                        field_exists = False
                        actual_value = None
                        
                        # Búsqueda exacta
                        if field_name in flat_response:
                            field_exists = True
                            actual_value = flat_response[field_name]
                        else:
                            # Búsqueda flexible
                            for key in flat_response.keys():
                                if key.endswith(field_name) or field_name in key.split('.'):
                                    field_exists = True
                                    actual_value = flat_response[key]
                                    break
                        
                        # Verificar existencia del campo
                        if not field_exists:
                            if validation_strategy == "strict":
                                return False, f"Campo esperado '{field_name}' no encontrado", "error"
                            self.logger.warning(f"Campo esperado '{field_name}' no encontrado, pero estrategia es '{validation_strategy}'")
                        
                        # Verificar valor si se especificó
                        elif expected_value is not None:
                            str_expected = str(expected_value).strip()
                            str_actual = str(actual_value).strip()
                            
                            if str_expected != str_actual and validation_strategy == "strict":
                                return False, f"Valor incorrecto para '{field_name}'. Esperado: {expected_value}, Obtenido: {actual_value}", "error"
                            elif str_expected != str_actual:
                                self.logger.warning(f"Valor incorrecto para '{field_name}', pero estrategia es '{validation_strategy}'")
                
                # Todos los criterios cumplidos
                return True, f"Respuesta validada correctamente", "success"
                
            # Verificar si es advertencia
            elif str_value in warning_values:
                return True, f"Respuesta con código de advertencia: {field_value}", "warning"
                
            # Verificar si es fallo (nueva categoría)
            elif str_value in failed_values:
                return False, f"Respuesta con código de fallo: {field_value}", "failed"
                
            # Es un error
            else:
                return False, f"Valor incorrecto para '{success_field}'. Esperado: {success_values}, Obtenido: {field_value}", "error"
        
        # Si no encontramos el campo principal pero hay rutas alternativas
        if "alternative_paths" in validation_schema:
            for alt_path in validation_schema["alternative_paths"]:
                alt_field = alt_path.get("field")
                alt_values = alt_path.get("success_values", [])
                
                # Búsqueda del campo alternativo
                alt_found = False
                alt_value = None
                
                # Búsqueda exacta
                if alt_field in flat_response:
                    alt_found = True
                    alt_value = flat_response[alt_field]
                else:
                    # Búsqueda flexible
                    for key in flat_response.keys():
                        if key.endswith(alt_field) or alt_field in key.split('.'):
                            alt_found = True
                            alt_value = flat_response[key]
                            break
                
                if alt_found:
                    str_alt_value = str(alt_value).strip()
                    if str_alt_value in [str(v).strip() for v in alt_values]:
                        return True, f"Validación exitosa mediante ruta alternativa: {alt_field}", "success"
        
        # Si llegamos aquí, no encontramos validación exitosa
        
        # Modo permisivo - cualquier respuesta no vacía es éxito
        if validation_strategy == "permissive":
            return True, "Respuesta aceptada en modo permisivo", "success"
            
        # Verificar opción para tratar respuestas vacías como éxito
        if validation_schema.get("treat_empty_as_success", False) and not response:
            return True, "Respuesta vacía aceptada como válida", "success"
        
        # Validación fallida
        if not field_found:
            self.logger.warning(f"Campo de validación '{success_field}' no encontrado en la respuesta. Claves disponibles: {list(flat_response.keys())[:20]}")
            return False, f"Campo de validación '{success_field}' no encontrado en la respuesta", "error"
        else:
            return False, f"Valor no esperado en '{success_field}': {field_value}", "error"
    
    # Localizar la función _zeep_object_to_dict en soap_client.py
    def _zeep_object_to_dict(self, obj) -> Dict[str, Any]:
        """
        Convierte un objeto Zeep a un diccionario Python con preservación mejorada de estructura.
        
        Args:
            obj: Objeto Zeep a convertir
            
        Returns:
            Dict[str, Any]: Diccionario con los datos
        """
        # Caso especial para manejo de None
        if obj is None:
            return None
            
        # Caso para objetos con atributos (tipo clase)
        if hasattr(obj, '__dict__'):
            # Primero verificar si es un tipo especial
            if hasattr(obj, '_xsd_type') and hasattr(obj, '__values__'):
                # Este es un objeto zeep.objects.CompoundValue
                result = {}
                for key, value in obj.__values__.items():
                    result[key] = self._zeep_object_to_dict(value)
                return result
                
            # Manejo estándar de objetos python
            return {key: self._zeep_object_to_dict(value) 
                    for key, value in obj.__dict__.items() 
                    if not key.startswith('_')}
                    
        # Manejo de listas
        elif isinstance(obj, list):
            return [self._zeep_object_to_dict(item) for item in obj]
            
        # Manejo de diccionarios
        elif isinstance(obj, dict):
            return {key: self._zeep_object_to_dict(value) 
                    for key, value in obj.items()}
                    
        # Manejo directo de tipos XML
        elif hasattr(obj, 'tag') and hasattr(obj, 'text'):
            # Nodo XML
            result = {'_tag': obj.tag, '_text': obj.text}
            # Añadir atributos si existen
            if hasattr(obj, 'attrib') and obj.attrib:
                result['_attrib'] = obj.attrib
            return result
            
        # Valores simples
        else:
            return obj
    
    def _extract_soap_response_xml(self, response_text: str) -> Dict[str, Any]:
        """
        Extrae y procesa la respuesta SOAP directamente del XML.
        
        Args:
            response_text (str): Texto XML de la respuesta SOAP
            
        Returns:
            Dict[str, Any]: Datos procesados
        """
        try:
            # Convertir XML a diccionario usando xmltodict
            response_dict = xmltodict.parse(response_text)
            
            # Extraer Body y Response
            envelope_key = [k for k in response_dict.keys() if k.endswith('Envelope')][0]
            envelope = response_dict[envelope_key]
            
            body_key = [k for k in envelope.keys() if k.endswith('Body')][0]
            body = envelope[body_key]
            
            # Extraer Response (primer elemento en body)
            if body and isinstance(body, dict):
                response_key = next(iter(body.keys()))
                response = body[response_key]
                return response
                
            return response_dict
            
        except Exception as e:
            logger.error(f"Error procesando XML directamente: {str(e)}")
            return {"_raw_xml": response_text}
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = '', 
                separator: str = '.') -> Dict[str, Any]:
        """
        Aplana un diccionario anidado y maneja namespaces XML correctamente.
        
        Args:
            d (Dict[str, Any]): Diccionario a aplanar
            parent_key (str): Clave padre para la recursión
            separator (str): Separador para claves anidadas
            
        Returns:
            Dict[str, Any]: Diccionario aplanado
        """
        items = []
        for k, v in d.items():
            # Manejo mejorado de namespaces
            clean_key = k
            
            # Eliminar namespaces como 'ns2:', 'v1.:', etc.
            if ':' in k:
                clean_key = k.split(':')[-1]
            elif '.' in k and k.split('.')[-1] == '':
                # Manejar casos como 'v1.'
                parts = k.split('.')
                if len(parts) > 1:
                    clean_key = parts[0]
                    
            new_key = f"{parent_key}{separator}{clean_key}" if parent_key else clean_key
            
            # Almacenar también con la clave original para compatibilidad
            original_key = f"{parent_key}{separator}{k}" if parent_key else k
            
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, separator).items())
                # También almacenar versión simple del campo
                items.append((clean_key, v))
            elif isinstance(v, list):
                # Manejar listas - procesar cada elemento para arrays de objetos
                if len(v) > 0 and all(isinstance(item, dict) for item in v):
                    for i, item in enumerate(v):
                        list_key = f"{new_key}{separator}{i}"
                        items.extend(self._flatten_dict(item, list_key, separator).items())
                items.append((new_key, v))
                items.append((clean_key, v))
            else:
                items.append((new_key, v))
                items.append((clean_key, v))
                # También añadir versión sin namespaces
                items.append((clean_key, v))
            
        # Eliminar posibles duplicados manteniendo el último valor
        result = {}
        for k, v in items:
            result[k] = v
                
        return result
    
    def extract_validation_patterns(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrae patrones de validación del request.
        
        Args:
            request_data (Dict[str, Any]): Datos del request
            
        Returns:
            Dict[str, Any]: Patrones de validación
        """
        patterns = {}
        
        # Extraer patrones de validación si existen
        validation_pattern = request_data.get('validation_pattern', {})
        
        if isinstance(validation_pattern, dict):
            patterns = validation_pattern
        elif isinstance(validation_pattern, str) and validation_pattern.strip():
            # Intentar parsear patrones de validación en formato XML o JSON
            try:
                patterns = xmltodict.parse(validation_pattern)
            except:
                try:
                    import json
                    patterns = json.loads(validation_pattern)
                except:
                    logger.warning(f"No se pudo parsear el patrón de validación: {validation_pattern}")
        
        return patterns

    # Localiza la función _flatten_dict en soap_client.py y modifícala así:
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = '', 
                    separator: str = '.') -> Dict[str, Any]:
        """
        Aplana un diccionario anidado y maneja namespaces XML correctamente.
        
        Args:
            d (Dict[str, Any]): Diccionario a aplanar
            parent_key (str): Clave padre para la recursión
            separator (str): Separador para claves anidadas
            
        Returns:
            Dict[str, Any]: Diccionario aplanado
        """
        items = []
        for k, v in d.items():
            # Eliminar prefijos de namespace si existen
            if ':' in k:
                k = k.split(':')[-1]
                
            new_key = f"{parent_key}{separator}{k}" if parent_key else k
            
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, separator).items())
            elif isinstance(v, list):
                # Manejar listas - tomar el primer elemento para validación simple
                if len(v) > 0 and isinstance(v[0], dict):
                    items.extend(self._flatten_dict(v[0], new_key, separator).items())
                else:
                    items.append((new_key, v))
            else:
                items.append((new_key, v))
        return dict(items)
    
    def test_soap_request(xml_file_path: str, wsdl_url: str) -> None:
        """
        Prueba un request SOAP con un archivo XML.
        
        Args:
            xml_file_path (str): Ruta al archivo XML
            wsdl_url (str): URL del WSDL
        """
        try:
            # Cargar XML
            with open(xml_file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # Crear cliente SOAP
            client = SOAPClient()
            
            # Enviar request
            success, result = client.send_raw_request(wsdl_url, xml_content)
            
            if success:
                print(f"✅ Request exitoso:")
                print(f"  - Método: {result['method']}")
                print(f"  - Respuesta: {json.dumps(result['response'], indent=2)[:200]}...")
            else:
                print(f"❌ Error en request:")
                print(f"  - Error: {result['error']}")
                print(f"  - Estado: {result['status']}")
                
        except Exception as e:
            print(f"❌ Error de ejecución: {str(e)}")
            
    def debug_response_structure(self, response: Dict[str, Any]) -> str:
        """
        Genera una representación detallada de la estructura de la respuesta para depuración.
        
        Args:
            response (Dict[str, Any]): Respuesta SOAP a analizar
            
        Returns:
            str: Información de estructura en formato texto
        """
        flat = self._flatten_dict(response)
        
        # Ordenar claves para mejor visualización
        sorted_keys = sorted(flat.keys())
        
        result = "=== ESTRUCTURA DE RESPUESTA ===\n"
        result += f"Total de campos: {len(sorted_keys)}\n\n"
        
        # Mostrar hasta 50 campos para no sobrecargar el log
        for key in sorted_keys[:50]:
            value = flat[key]
            # Limitar longitud de valores muy largos
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:100] + "..."
                
            result += f"{key} = {value_str}\n"
            
        if len(sorted_keys) > 50:
            result += f"\n... y {len(sorted_keys) - 50} campos más ...\n"
            
        return result
    
    def _save_debug_xml(self, prefix: str, request_xml: str, response_xml: str) -> None:
        """
        Guarda XMLs de request y response para diagnóstico.
        
        Args:
            prefix (str): Prefijo para los nombres de archivo
            request_xml (str): XML de request
            response_xml (str): XML de response
        """
        try:
            # Crear directorio debug si no existe
            debug_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'debug')
            os.makedirs(debug_dir, exist_ok=True)
            
            # Nombre de archivo con timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{prefix}_{timestamp}"
            
            # Guardar request
            with open(os.path.join(debug_dir, f"{filename}_request.xml"), 'w', encoding='utf-8') as f:
                f.write(request_xml)
                
            # Guardar response
            with open(os.path.join(debug_dir, f"{filename}_response.xml"), 'w', encoding='utf-8') as f:
                f.write(response_xml)
                
            logger.info(f"Debug XML guardado en {debug_dir}/{filename}_*.xml")
        except Exception as e:
            logger.error(f"Error guardando debug XML: {str(e)}")

    # Añadir en core/soap_client.py

    def dump_object_structure(self, obj, max_depth=3, current_depth=0, prefix=''):
        """
        Genera una representación de la estructura de un objeto Python para depuración.
        
        Args:
            obj: Objeto a analizar
            max_depth: Profundidad máxima de recursión
            current_depth: Profundidad actual en la recursión
            prefix: Prefijo para la indentación
            
        Returns:
            str: Representación textual de la estructura
        """
        if current_depth >= max_depth:
            return f"{prefix}[Profundidad máxima alcanzada]"
        
        try:
            # Verificar tipo de objeto
            if obj is None:
                return f"{prefix}None"
            elif isinstance(obj, (str, int, float, bool)):
                # Para valores simples, mostrar tipo y valor
                return f"{prefix}{type(obj).__name__}: {obj}"
            elif isinstance(obj, (datetime.datetime, datetime.date)):
                # Manejo especial para fechas
                return f"{prefix}datetime: {obj.isoformat()}"
            elif isinstance(obj, list):
                # Para listas, mostrar cada elemento
                result = [f"{prefix}Lista[{len(obj)}]:"]
                
                if obj:
                    # Limitar elementos mostrados para listas grandes
                    max_items = min(5, len(obj))
                    for i in range(max_items):
                        item_str = self.dump_object_structure(
                            obj[i], max_depth, current_depth + 1, f"{prefix}  [{i}] "
                        )
                        result.append(item_str)
                    
                    if len(obj) > max_items:
                        result.append(f"{prefix}  ... y {len(obj) - max_items} elementos más")
                
                return "\n".join(result)
            elif isinstance(obj, dict):
                # Para diccionarios, mostrar pares clave-valor
                result = [f"{prefix}Diccionario[{len(obj)}]:"]
                
                # Limitar elementos mostrados
                items = list(obj.items())[:5]
                for key, value in items:
                    item_str = self.dump_object_structure(
                        value, max_depth, current_depth + 1, f"{prefix}  '{key}': "
                    )
                    result.append(item_str)
                
                if len(obj) > 5:
                    result.append(f"{prefix}  ... y {len(obj) - 5} pares clave-valor más")
                
                return "\n".join(result)
            elif hasattr(obj, '__dict__'):
                # Para objetos con atributos, mostrar estructura
                class_name = obj.__class__.__name__
                result = [f"{prefix}Objeto {class_name}:"]
                
                # Extraer atributos no privados
                attrs = {k: v for k, v in vars(obj).items() if not k.startswith('_')}
                items = list(attrs.items())[:5]
                
                for key, value in items:
                    item_str = self.dump_object_structure(
                        value, max_depth, current_depth + 1, f"{prefix}  .{key}: "
                    )
                    result.append(item_str)
                
                if len(attrs) > 5:
                    result.append(f"{prefix}  ... y {len(attrs) - 5} atributos más")
                
                return "\n".join(result)
            else:
                # Para otros tipos de objetos
                return f"{prefix}Objeto {type(obj).__name__} (sin estructura interna)"
        except Exception as e:
            # Capturar excepciones durante la introspección
            return f"{prefix}[Error analizando objeto: {str(e)}]"
    
    def validate_response_advanced(self, response: Dict[str, Any], 
                              validation_schema: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, str]:
        """
        Valida la respuesta SOAP con reglas avanzadas y configurables.
        
        Args:
            response (Dict[str, Any]): Respuesta SOAP a validar
            validation_schema (Dict[str, Any], optional): Esquema de validación avanzado
            
        Returns:
            Tuple[bool, str, str]: (éxito, mensaje, nivel: 'success'|'warning'|'error')
        """
        # Si no hay esquema de validación, éxito por defecto
        if not validation_schema:
            return True, "Respuesta recibida (sin validación de reglas)", "success"
        
        if validation_schema is None:
            validation_schema = {}
        elif isinstance(validation_schema, str):
            try:
                # Intentar convertir a diccionario si es un string JSON
                import json
                validation_schema = json.loads(validation_schema)
            except:
                # Si no es un JSON válido, usar esquema simple
                validation_schema = {"status": "ok"}
            
        # Caso especial: esquema simple heredado
        if len(validation_schema) == 1 and "status" in validation_schema:
            if validation_schema["status"] == "ok":
                return True, "El servicio respondió correctamente", "success"
        
        # Aplanar respuesta para búsqueda flexible de campos
        flat_response = self._flatten_dict(response)
        
        # Obtener configuración del esquema
        success_field = validation_schema.get("success_field", "codMensaje")
        success_values = validation_schema.get("success_values", ["00000"])
        warning_values = validation_schema.get("warning_values", [])
        failed_values = validation_schema.get("failed_values", [])
        expected_fields = validation_schema.get("expected_fields", {})
        validation_strategy = validation_schema.get("validation_strategy", "flexible")
        
        # Convertir valores a cadenas para comparación consistente
        if success_values and not isinstance(success_values, list):
            success_values = [str(success_values)]
        if warning_values and not isinstance(warning_values, list):
            warning_values = [str(warning_values)]
        if failed_values and not isinstance(failed_values, list):
            failed_values = [str(failed_values)]
        
        # Estos deben ser listas
        success_values = [str(v) for v in success_values]
        warning_values = [str(v) for v in warning_values]
        failed_values = [str(v) for v in failed_values]
        
        # Buscar el campo principal de éxito/error
        field_value = None
        field_found = False
        
        # 1. Búsqueda exacta
        if success_field in flat_response:
            field_value = flat_response[success_field]
            field_found = True
            logger.debug(f"Campo '{success_field}' encontrado directamente")
        else:
            # 2. Búsqueda flexible
            for key in flat_response.keys():
                # Coincidencia al final de la clave o clave parcial
                if key.endswith(success_field) or success_field in key.split('.'):
                    field_value = flat_response[key]
                    field_found = True
                    logger.debug(f"Campo '{success_field}' encontrado como '{key}'")
                    break
        
        # Evaluar resultado según el campo principal
        if field_found:
            # Convertir a string para comparación consistente
            str_value = str(field_value).strip()
            logger.debug(f"Valor encontrado: '{str_value}', comparando con success_values: {success_values}")
        
            # Verificar si es éxito
            if str_value in success_values:
                # Verificar campos adicionales si están definidos
                if expected_fields:
                    for field_name, expected_value in expected_fields.items():
                        # Buscar el campo esperado
                        field_exists = False
                        actual_value = None
                        
                        # Búsqueda exacta
                        if field_name in flat_response:
                            field_exists = True
                            actual_value = flat_response[field_name]
                        else:
                            # Búsqueda flexible
                            for key in flat_response.keys():
                                if key.endswith(field_name) or field_name in key.split('.'):
                                    field_exists = True
                                    actual_value = flat_response[key]
                                    break
                        
                        # Verificar existencia del campo
                        if not field_exists:
                            if validation_strategy == "strict":
                                return False, f"Campo esperado '{field_name}' no encontrado", "error"
                            logger.warning(f"Campo esperado '{field_name}' no encontrado, pero estrategia es '{validation_strategy}'")
                        
                        # Verificar valor si se especificó
                        elif expected_value is not None:
                            str_expected = str(expected_value).strip()
                            str_actual = str(actual_value).strip()
                            
                            if str_expected != str_actual and validation_strategy == "strict":
                                return False, f"Valor incorrecto para '{field_name}'. Esperado: {expected_value}, Obtenido: {actual_value}", "error"
                            elif str_expected != str_actual:
                                logger.warning(f"Valor incorrecto para '{field_name}', pero estrategia es '{validation_strategy}'")
                
                # Todos los criterios cumplidos
                return True, f"Respuesta validada correctamente", "success"
                
            # Verificar si es advertencia
            elif str_value in warning_values:
                return True, f"Respuesta con código de advertencia: {field_value}", "warning"
                
            # Verificar si es fallo (nueva categoría)
            elif str_value in failed_values:
                return False, f"Respuesta con código de fallo: {field_value}", "failed"
                
            # Es un error
            else:
                return False, f"Valor incorrecto para '{success_field}'. Esperado: {success_values}, Obtenido: {field_value}", "error"
        
        # Si no encontramos el campo principal pero hay rutas alternativas
        if "alternative_paths" in validation_schema:
            for alt_path in validation_schema["alternative_paths"]:
                alt_field = alt_path.get("field")
                alt_values = alt_path.get("success_values", [])
                
                # Búsqueda del campo alternativo
                alt_found, alt_value = self._find_field_by_path(alt_field, flat_response)
                
                if alt_found:
                    str_alt_value = str(alt_value).strip()
                    if str_alt_value in [str(v).strip() for v in alt_values]:
                        return True, f"Validación exitosa mediante ruta alternativa: {alt_field}", "success"
        
        # Si llegamos aquí, no encontramos validación exitosa
        
        # Modo permisivo - cualquier respuesta no vacía es éxito
        if validation_strategy == "permissive":
            return True, "Respuesta aceptada en modo permisivo", "success"
            
        # Verificar opción para tratar respuestas vacías como éxito
        if validation_schema.get("treat_empty_as_success", False) and not response:
            return True, "Respuesta vacía aceptada como válida", "success"
        
        # Validación fallida
        if not field_found:
            return False, f"Campo de validación '{success_field}' no encontrado en la respuesta", "error"
        else:
            return False, f"Valor no esperado en '{success_field}': {field_value}", "error"

    def _find_field_in_response(self, field_name: str, flat_response: Dict[str, Any]) -> bool:
        """
        Busca un campo en la respuesta aplanada con estrategias flexibles.
        
        Args:
            field_name (str): Nombre del campo a buscar
            flat_response (Dict[str, Any]): Respuesta aplanada
            
        Returns:
            bool: True si el campo se encuentra
        """
        # Búsqueda exacta
        if field_name in flat_response:
            return True
            
        # Búsqueda por terminación de clave
        for key in flat_response.keys():
            if key.endswith(field_name) or field_name in key.split('.'):
                return True
        
        return False

    def _find_field_by_path(self, field_path: str, flat_response: Dict[str, Any]) -> Tuple[bool, Any]:
        """
        Busca un campo por ruta con soporte mejorado para namespaces XML.
        
        Args:
            field_path (str): Ruta del campo a buscar
            flat_response (Dict[str, Any]): Respuesta aplanada
            
        Returns:
            Tuple[bool, Any]: (encontrado, valor)
        """
        # Búsqueda exacta
        if field_path in flat_response:
            return True, flat_response[field_path]
        
        # Extraer el nombre del campo sin namespace
        base_field = field_path.split('.')[-1]
        
        # Buscar por cualquier clave que termine con el nombre del campo
        for key, value in flat_response.items():
            # Buscar exactamente el nombre del campo al final de la clave
            if key.endswith(f".{base_field}") or key == base_field:
                return True, value
                
            # Buscar por nombre de campo con namespace al final
            if ':' in key and key.split(':')[-1] == base_field:
                return True, value
                
            # Buscar por campos con punto en namespace como "v1.:"
            if '.:' in key and key.endswith(f":{base_field}"):
                return True, value
        
        # Buscar alguna coincidencia parcial en namespaces complejos
        for key, value in flat_response.items():
            key_parts = key.split('.')
            for part in key_parts:
                if ':' in part:
                    _, field_name = part.split(':', 1)
                    if field_name == base_field:
                        return True, value
        
        return False, None
    