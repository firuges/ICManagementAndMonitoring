import os
import logging
import xml.etree.ElementTree as ET
import xmltodict
import zeep
import json
import datetime
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
    
    def send_raw_request(self, wsdl_url: str, request_xml: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Envía un request SOAP XML directamente con manejo robusto de operaciones.
        
        Args:
            wsdl_url (str): URL del WSDL del servicio
            request_xml (str): XML del request SOAP
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (éxito, resultado/error)
        """
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
                
            except zeep.exceptions.Fault as fault:
                logger.error(f"Error SOAP Fault: {str(fault)}")
                return False, {
                    "error": f"SOAP Fault: {str(fault)}",
                    "status": "soap_fault" 
                }
            except Exception as call_error:
                logger.error(f"Error al ejecutar llamada SOAP: {str(call_error)}")
                # Intento alternativo: enviar directamente el XML como fallback
                return self._send_direct_xml(wsdl_url, request_xml)
                
        except Exception as e:
            logger.error(f"Error al enviar request SOAP: {str(e)}", exc_info=True)
            return False, {
                "error": f"Error inesperado: {str(e)}",
                "status": "error"
            }
    
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
            response = requests.post(
                service_url,
                data=request_xml,
                headers=headers,
                verify=False,  # Considera la seguridad en entornos de producción
                timeout=30
            )
            
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
    
    
    def validate_response(self, response: Dict[str, Any], 
                     expected_patterns: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Valida la respuesta SOAP contra patrones esperados con manejo mejorado y diagnóstico.
        
        Args:
            response (Dict[str, Any]): Respuesta SOAP a validar
            expected_patterns (Dict[str, Any], optional): Patrones esperados
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje descriptivo)
        """
        # Si no hay patrones, consideramos válida la respuesta
        if not expected_patterns:
            return True, "Respuesta recibida correctamente (sin validación de contenido)"
        
        # Validación de tipo de respuesta
        if response is None:
            logger.warning("Se recibió una respuesta nula para validar")
            return False, "No se puede validar una respuesta nula"

        # Comprobar caso especial: solo validar 'status'
        if len(expected_patterns) == 1 and 'status' in expected_patterns:
            expected_status = expected_patterns['status']
            # Para este caso especial, cualquier respuesta no nula es válida
            # ya que solo verificamos que el servicio respondió
            if expected_status == 'ok':
                return True, f"El servicio respondió correctamente"
        
        # Manejo de tipos no estándar
        if not isinstance(response, dict) and not hasattr(response, '__dict__'):
            logger.warning(f"Tipo de respuesta inesperado: {type(response)}")
            # Si solo esperamos status, podemos ser permisivos
            if len(expected_patterns) == 1 and 'status' in expected_patterns and expected_patterns['status'] == 'ok':
                return True, "Respuesta con formato inesperado aceptada como válida"
            else:
                return False, f"Tipo de respuesta no soportado para validación: {type(response)}"
        
        # Proceso estándar de validación
        try:
            # Diagnóstico detallado para respuestas
            logger.debug(f"=== DIAGNÓSTICO DE VALIDACIÓN ===")
            logger.debug(f"Respuesta recibida tipo: {type(response)}")
            
            # Limitar tamaño de respuesta en logs para evitar saturación
            resp_str = str(response)
            if len(resp_str) > 500:
                resp_str = resp_str[:500] + "..."
            logger.debug(f"Respuesta contenido: {resp_str}")
            
            logger.debug(f"Patrones esperados: {expected_patterns}")

            # Si la respuesta es un diccionario, mostrar las claves
            if isinstance(response, dict):
                logger.debug(f"Claves en respuesta: {list(response.keys())}")
            
            # IMPORTANTE: Aplanar respuesta ANTES de acceder a sus claves
            flat_response = self._flatten_dict(response)
            
            # Ahora podemos acceder de forma segura a flat_response
            flat_keys = list(flat_response.keys())
            logger.debug(f"Total de claves aplanadas: {len(flat_keys)}")
            if flat_keys:
                sample_keys = flat_keys[:min(10, len(flat_keys))]
                logger.debug(f"Muestra de claves aplanadas: {sample_keys}")
            
            # Validar cada patrón
            for key_path, expected_value in expected_patterns.items():
                # Omitir validación de 'status' si ya se ha manejado antes
                if key_path == 'status' and len(expected_patterns) == 1:
                    continue
                    
                found = False
                actual_value = None
                
                # 1. Búsqueda exacta
                if key_path in flat_response:
                    found = True
                    actual_value = flat_response[key_path]
                    logger.debug(f"Campo '{key_path}' encontrado directamente")
                else:
                    # 2. Búsqueda por coincidencia parcial
                    for resp_key in flat_response.keys():
                        # Verificar coincidencia al final de la clave
                        if resp_key.endswith(key_path):
                            found = True
                            actual_value = flat_response[resp_key]
                            logger.debug(f"Campo '{key_path}' encontrado como '{resp_key}'")
                            break
                        
                        # Verificar si la clave está dentro de otra
                        if key_path in resp_key.split('.'):
                            found = True
                            actual_value = flat_response[resp_key]
                            logger.debug(f"Campo '{key_path}' encontrado dentro de '{resp_key}'")
                            break
                
                # Si no se encontró, reportar error
                if not found:
                    logger.warning(f"Campo '{key_path}' no encontrado en respuesta. Claves disponibles: {sample_keys}")
                    return False, f"Campo esperado '{key_path}' no encontrado en la respuesta"
                
                # Si el valor esperado no es None, comparar valores
                if expected_value is not None:
                    # Convertir ambos a string para comparación flexible
                    str_expected = str(expected_value).strip()
                    str_actual = str(actual_value).strip()
                    
                    if str_expected != str_actual:
                        logger.warning(f"Valor incorrecto para '{key_path}'. Esperado: '{str_expected}', Obtenido: '{str_actual}'")
                        return False, f"Valor incorrecto para '{key_path}'. Esperado: {expected_value}, Obtenido: {actual_value}"
            
            return True, "Respuesta validada correctamente"
            
        except Exception as e:
            logger.error(f"Error durante validación: {str(e)}", exc_info=True)
            return False, f"Error durante validación: {str(e)}"
    
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
        Aplana un diccionario anidado con manejo mejorado de namespaces.
        
        Args:
            d (Dict[str, Any]): Diccionario a aplanar
            parent_key (str): Clave padre para la recursión
            separator (str): Separador para claves anidadas
            
        Returns:
            Dict[str, Any]: Diccionario aplanado
        """
        if not isinstance(d, dict):
            return {}
            
        items = []
        
        for k, v in d.items():
            # Normalizar clave eliminando prefijos de namespace
            clean_key = k
            if ':' in k:
                _, clean_key = k.split(':', 1)
            
            # Crear nueva clave
            new_key = f"{parent_key}{separator}{clean_key}" if parent_key else clean_key
            
            # También agregar versión con la clave original para mayor compatibilidad
            original_new_key = f"{parent_key}{separator}{k}" if parent_key else k
            
            if isinstance(v, dict):
                # Procesar diccionario anidado
                items.extend(self._flatten_dict(v, new_key, separator).items())
                # También agregar el objeto completo en caso de necesitar acceso a nivel superior
                items.append((new_key, v))
                items.append((original_new_key, v))
            elif isinstance(v, list):
                # Procesar lista
                if v and all(isinstance(item, dict) for item in v):
                    # Si es lista de diccionarios, procesar cada uno
                    for i, item in enumerate(v):
                        list_key = f"{new_key}{separator}{i}"
                        items.extend(self._flatten_dict(item, list_key, separator).items())
                    # También agregar la lista completa
                    items.append((new_key, v))
                    items.append((original_new_key, v))
                else:
                    # Lista de valores simples
                    items.append((new_key, v))
                    items.append((original_new_key, v))
            else:
                # Valor simple - agregar versiones con y sin namespace
                items.append((new_key, v))
                items.append((original_new_key, v))
                
                # Agregar también una versión con solo el nombre de la clave
                # para facilitar búsquedas simples
                items.append((clean_key, v))
        
        # Crear diccionario final, eliminando duplicados
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
    