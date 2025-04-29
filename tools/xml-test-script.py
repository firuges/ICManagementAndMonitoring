#!/usr/bin/env python
"""
Script de prueba para validar el manejo mejorado de namespaces complejos.
Usa las funciones mejoradas de _flatten_dict y validate_response_advanced.

Uso: python test_validation_improvements.py
"""

import logging
import json
import xmltodict
from typing import Dict, Any, Tuple, Optional

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('validation_test')

# XML de prueba con namespace problemático v1.:
XML_CASE_1 = """
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
   <soapenv:Header xmlns:v11="http://xmlns.example.com/schema/servicios/CabeceraBanca/v1.0" xmlns:v1="http://xmlns.example.com/schema/servicios/ValidarOtp/v1.0"/>
   <soapenv:Body xmlns:v11="http://xmlns.example.com/schema/servicios/CabeceraBanca/v1.0" xmlns:v1="http://xmlns.example.com/schema/servicios/ValidarOtp/v1.0">
      <ns2:cabeceraSalida xmlns:ns2="http://xmlns.example.com/schema/operacion/manejarError/v1.0">
         <v1.:codMensaje xmlns:v1.="http://xmlns.example.com/schema/servicios/CabeceraBanca/v1.0">2001</v1.:codMensaje>
         <v1.:mensajeUsuario xmlns:v1.="http://xmlns.example.com/schema/servicios/CabeceraBanca/v1.0">Mensaje de error de prueba</v1.:mensajeUsuario>
      </ns2:cabeceraSalida>
   </soapenv:Body>
</soapenv:Envelope>
"""

# XML de prueba con valor de éxito anidado en elemento con atributos
XML_CASE_2 = """
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
   <soapenv:Header/>
   <soapenv:Body>
      <ns1:respuesta xmlns:ns1="http://example.com/api">
         <cabecera>
            <codMensaje tipo="resultado">00000</codMensaje>
            <timestamp>2023-01-01T12:34:56</timestamp>
         </cabecera>
         <datos>
            <campo1>valor1</campo1>
            <campo2>valor2</campo2>
         </datos>
      </ns1:respuesta>
   </soapenv:Body>
</soapenv:Envelope>
"""

# XML con estructura compleja de codMensaje cómo texto con atributos
XML_CASE_3 = """
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
   <soapenv:Header/>
   <soapenv:Body>
      <respuesta>
         <cabecera>
            <codMensaje xmlns:v1="http://example.com/schema">
               <v1:texto>00000</v1:texto>
               <v1:detalle>Operación exitosa</v1:detalle>
            </codMensaje>
         </cabecera>
      </respuesta>
   </soapenv:Body>
</soapenv:Envelope>
"""

def flatten_dict(d: Dict[str, Any], parent_key: str = '', 
                separator: str = '.') -> Dict[str, Any]:
    """
    Aplana un diccionario anidado y maneja namespaces XML complejos correctamente.
    Soporte mejorado para namespaces problemáticos como v1.: y valores anidados.
    
    Args:
        d (Dict[str, Any]): Diccionario a aplanar
        parent_key (str): Clave padre para la recursión
        separator (str): Separador para claves anidadas
        
    Returns:
        Dict[str, Any]: Diccionario aplanado
    """
    items = []
    if not isinstance(d, dict):
        return {}
        
    for k, v in d.items():
        # Manejo mejorado de namespaces incluyendo formatos atípicos
        clean_key = k
        
        # Eliminar namespaces como 'ns2:', 'v1:', etc.
        if ':' in k:
            clean_key = k.split(':')[-1]
        
        # Manejar casos específicos como 'v1.:'
        elif '.:' in k:
            clean_key = k.split('.:')[-1]
        
        # Manejar casos donde el namespace está al final como '.:codMensaje'
        if clean_key.startswith('.:'):
            clean_key = clean_key[2:]
            
        new_key = f"{parent_key}{separator}{clean_key}" if parent_key else clean_key
        
        # También registrar la clave original para compatibilidad
        if parent_key:
            original_key = f"{parent_key}{separator}{k}"
        else:
            original_key = k
            
        # Manejar el caso especial de '#text' para nodos XML con valores de texto
        if isinstance(v, dict) and '#text' in v:
            # Registrar el valor de texto directamente con la clave actual
            items.append((new_key, v['#text']))
            items.append((clean_key, v['#text']))
            # Pero también aplanar el diccionario completo (para mantener atributos, etc.)
            flat_dict = flatten_dict(v, new_key, separator)
            items.extend(flat_dict.items())
        elif isinstance(v, dict):
            # Procesar diccionario recursivamente
            flat_dict = flatten_dict(v, new_key, separator)
            items.extend(flat_dict.items())
            # También almacenar el campo completo
            items.append((new_key, v))
            items.append((clean_key, v))  # Agregar la versión simplificada
        elif isinstance(v, list):
            # Manejar listas - procesar cada elemento si son diccionarios
            if all(isinstance(item, dict) for item in v if item is not None):
                for i, item in enumerate(v):
                    if item is not None:  # Validar que no sea None antes de procesar
                        list_key = f"{new_key}{separator}{i}"
                        items.extend(flatten_dict(item, list_key, separator).items())
            
            # Almacenar la lista completa también
            items.append((new_key, v))
            items.append((clean_key, v))  # Versión simplificada
        else:
            # Valores simples
            items.append((new_key, v))
            items.append((original_key, v))  # Versión con namespace original
            items.append((clean_key, v))  # Versión simplificada
    
    # Eliminar duplicados manteniendo el último valor
    result = {}
    for k, v in items:
        result[k] = v
        
    return result

def validate_response_advanced(response: Dict[str, Any], 
                              validation_schema: Dict[str, Any]) -> Tuple[bool, str, str]:
    """
    Valida la respuesta SOAP con reglas avanzadas y configurables.
    Mejorado para manejar namespaces complejos como v1.:codMensaje.
    
    Args:
        response (Dict[str, Any]): Respuesta SOAP a validar
        validation_schema (Dict[str, Any]): Esquema de validación avanzado
        
    Returns:
        Tuple[bool, str, str]: (éxito, mensaje, nivel: 'success'|'warning'|'error')
    """
    # Aplanar respuesta para búsqueda flexible de campos
    flat_response = flatten_dict(response)
    
    # Log detallado para diagnóstico (solo primeros 10 campos)
    print("\nCampos en la respuesta aplanada (primeros 10):")
    for i, (key, value) in enumerate(flat_response.items()):
        if i >= 10: break
        if isinstance(value, str) and len(value) > 50:
            print(f"  {key} = {value[:50]}...")
        else:
            print(f"  {key} = {value}")
    
    # Obtener configuración del esquema
    success_field = validation_schema.get("success_field", "codMensaje")
    success_values = validation_schema.get("success_values", ["00000"])
    warning_values = validation_schema.get("warning_values", [])
    failed_values = validation_schema.get("failed_values", [])
    validation_strategy = validation_schema.get("validation_strategy", "flexible")
    
    # Convertir valores a cadenas para comparación consistente
    success_values = [str(v).strip() for v in success_values]
    warning_values = [str(v).strip() for v in warning_values]
    failed_values = [str(v).strip() for v in failed_values]
    
    print(f"\nConfiguración de validación:")
    print(f"  - Campo de éxito: {success_field}")
    print(f"  - Valores de éxito: {success_values}")
    print(f"  - Valores de advertencia: {warning_values}")
    print(f"  - Valores de fallo: {failed_values}")
    print(f"  - Estrategia: {validation_strategy}")
    
    # Buscar el campo principal de éxito/error
    field_value = None
    field_found = False
    field_key = None
    
    # 1. Búsqueda exacta
    if success_field in flat_response:
        field_value = flat_response[success_field]
        field_key = success_field
        field_found = True
        print(f"\nCampo '{success_field}' encontrado directamente")
    else:
        # 2. Búsqueda flexible
        possible_keys = []
        for key in flat_response.keys():
            # Coincidencia al final de la clave o clave parcial
            if key.endswith(success_field) or success_field in key.split('.'):
                possible_keys.append(key)
        
        # Si hay múltiples claves posibles, usamos la mejor coincidencia
        if possible_keys:
            # Ordenar por longitud de clave (más corta primero) y sin namespace preferentemente
            possible_keys.sort(key=lambda k: (len(k), ":" in k or ".:" in k))
            field_key = possible_keys[0]
            field_value = flat_response[field_key]
            field_found = True
            print(f"\nCampo '{success_field}' encontrado como '{field_key}'")
            
            # Mostrar todas las posibles claves
            if len(possible_keys) > 1:
                print("Todas las posibles claves encontradas:")
                for key in possible_keys:
                    print(f"  - {key} = {flat_response[key]}")
    
    if field_found:
        # Convertir a string para comparación consistente
        str_value = str(field_value).strip()
        print(f"\nValor encontrado: '{str_value}'")
        
        # MEJORA CLAVE: Verificar si algún valor de éxito está CONTENIDO en la cadena
        if any(value in str_value for value in success_values):
            print("Resultado: ÉXITO - Valor de éxito encontrado en la cadena")
            return True, "Respuesta validada correctamente", "success"
        elif any(value in str_value for value in warning_values):
            print("Resultado: ADVERTENCIA - Valor de advertencia encontrado en la cadena")
            return True, f"Respuesta con código de advertencia: {field_value}", "warning"
        elif any(value in str_value for value in failed_values):
            print("Resultado: FALLO - Valor de fallo encontrado en la cadena")
            return False, f"Respuesta con código de fallo: {field_value}", "failed"
        else:
            print("Resultado: ERROR - Ningún valor esperado encontrado en la cadena")
            return False, f"Valor incorrecto para '{success_field}'. Esperado: {success_values}, Obtenido: {field_value}", "error"
    else:
        print("\nError: Campo de validación no encontrado")
        return False, f"Campo de validación '{success_field}' no encontrado en la respuesta", "error"

def run_test_case(xml_content, validation_schema, test_name):
    """Ejecuta un caso de prueba con los parámetros dados"""
    print(f"\n===== CASO DE PRUEBA: {test_name} =====")
    
    # Parsear el XML
    xml_dict = xmltodict.parse(xml_content)
    
    # Ejecutar validación
    result = validate_response_advanced(xml_dict, validation_schema)
    
    # Mostrar resultado
    print(f"\nResultado final: ({result[0]}, '{result[1]}', '{result[2]}')")
    
    return result

def main():
    """Función principal"""
    print("=== PRUEBA DE MEJORAS EN VALIDACIÓN XML ===")
    
    # Caso 1: XML con namespace v1.:
    validation_schema_1 = {
        "success_field": "codMensaje",
        "success_values": ["00000"],
        "warning_values": ["5000", "5001"],
        "failed_values": ["2001", "2002", "9999"],
        "validation_strategy": "flexible"
    }
    run_test_case(XML_CASE_1, validation_schema_1, "Namespace v1.: en codMensaje (debería detectar FALLO)")
    
    # Caso 2: XML con codMensaje como atributo
    validation_schema_2 = {
        "success_field": "codMensaje",
        "success_values": ["00000"],
        "warning_values": ["2001"],
        "validation_strategy": "flexible"
    }
    run_test_case(XML_CASE_2, validation_schema_2, "codMensaje con atributos (debería detectar ÉXITO)")
    
    # Caso 3: Estructura anidada para codMensaje
    validation_schema_3 = {
        "success_field": "texto",
        "success_values": ["00000"],
        "validation_strategy": "flexible"
    }
    run_test_case(XML_CASE_3, validation_schema_3, "Estructura anidada para codMensaje (debería detectar ÉXITO)")

if __name__ == "__main__":
    main()