#!/usr/bin/env python
"""
Herramienta de diagnóstico para probar la validación de respuestas SOAP y REST.

Esta herramienta permite verificar cómo se procesan los patrones de validación
para un servicio específico y ver cómo se comportaría en el monitoreo.

Uso: python validation_tester.py <nombre_servicio>
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, Any

# Configurar directorio raíz
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# Importar módulos de la aplicación
from core.persistence import PersistenceManager
from core.soap_client import SOAPClient
from core.rest_client import RESTClient

# Configuración de logging
logging.basicConfig(
    level=logging.DEBUG,  # Nivel DEBUG para ver más detalles
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('validation_tester')

def test_service_validation(service_name: str, debug_mode: bool = False) -> None:
    """
    Prueba la validación de un servicio específico en modo diagnóstico.
    
    Args:
        service_name (str): Nombre del servicio a probar
        debug_mode (bool): Si se debe activar el modo de depuración extendida
    """
    try:
        print(f"\n===== DIAGNÓSTICO DE VALIDACIÓN: {service_name} =====\n")
        
        # Inicializar componentes
        persistence = PersistenceManager(base_path=os.path.join(project_root, 'data'))
        soap_client = SOAPClient()
        rest_client = RESTClient()
        
        # 1. Cargar datos del servicio
        print("1. Cargando datos del servicio...")
        
        # Eliminar la extensión .json si fue incluida
        if service_name.endswith('.json'):
            service_name = service_name[:-5]
        
        # Intentar cargar el servicio
        try:
            service_data = persistence.load_soap_request(service_name)
        except ValueError:
            # Intentar también con variantes del nombre
            alternatives = [
                service_name.lower(),
                service_name.lower().replace(' ', '_'),
                service_name.upper(),
                service_name.capitalize()
            ]
            
            service_data = None
            for alt_name in alternatives:
                try:
                    print(f"   Intentando alternativa: {alt_name}")
                    service_data = persistence.load_soap_request(alt_name)
                    if service_data:
                        service_name = alt_name
                        print(f"   ✓ Servicio encontrado como: {alt_name}")
                        break
                except:
                    continue
            
            if not service_data:
                print(f"\nERROR: Servicio '{service_name}' no encontrado después de probar alternativas.")
                return
        
        service_type = service_data.get('type', 'SOAP')
        print(f"   - Tipo de servicio: {service_type}")
        print(f"   - Descripción: {service_data.get('description', 'No disponible')}")
        
        # 2. Extraer y mostrar el patrón de validación
        validation_pattern = service_data.get('validation_pattern', {})
        print("\n2. Patrón de validación configurado:")
        if isinstance(validation_pattern, dict):
            print(json.dumps(validation_pattern, indent=2))
        else:
            print(f"   {validation_pattern}")
        
        # 3. Comprobar si hay última respuesta disponible
        if 'last_response' not in service_data:
            print("\nERROR: No hay respuesta disponible para analizar.")
            print("Ejecute el servicio primero para obtener una respuesta.")
            return
        
        # 4. Analizar la respuesta
        response = service_data.get('last_response', {}).get('response', {})
        print("\n3. Análisis de la última respuesta:")
        
        # Aplanar respuesta para análisis
        flat_response = soap_client._flatten_dict(response)
        
        # Mostrar los primeros 20 campos de la respuesta aplanada
        print("   Campos disponibles (primeros 20):")
        for i, (key, value) in enumerate(flat_response.items()):
            if i >= 20:
                print(f"   ... y {len(flat_response) - 20} campos más")
                break
            print(f"   - {key} = {value}")
        
        # 5. Simular validación
        print("\n4. Simulación de validación:")
        
        # Procesar el esquema de validación si es necesario
        if isinstance(validation_pattern, str):
            try:
                validation_pattern = json.loads(validation_pattern)
                print("   (Convertido de string JSON a diccionario)")
            except:
                print("   (No es un JSON válido, usando como texto)")
        
        # Prueba de validación según el tipo de servicio
        if service_type == 'SOAP':
            valid, message, level = soap_client.validate_response_advanced(response, validation_pattern)
        else:  # REST
            valid, message, level = rest_client.validate_response(response, validation_pattern)
        
        # Mostrar resultados
        status_text = {
            True: "EXITOSO",
            False: "FALLIDO"
        }
        
        level_text = {
            "success": "ÉXITO",
            "warning": "ADVERTENCIA",
            "error": "ERROR",
            "failed": "FALLO"
        }
        
        print(f"\n   Resultado: {status_text[valid]}")
        print(f"   Nivel: {level_text.get(level, level)}")
        print(f"   Mensaje: {message}")
        
        # 6. Sugerencias según el resultado
        print("\n5. Diagnóstico y sugerencias:")
        if not valid:
            # Verificar casos comunes de error
            if "no encontrado" in message.lower():
                print("   PROBLEMA: Campo de validación no encontrado en la respuesta.")
                print("   SUGERENCIA: Verifique el nombre del campo 'success_field' en su configuración.")
                
                # Sugerir campos posibles basados en la respuesta
                suggestions = find_potential_fields(flat_response, validation_pattern)
                if suggestions:
                    print("\n   Campos potenciales detectados que podría utilizar:")
                    for field, suggestion in suggestions.items():
                        print(f"   - '{field}' con valor actual: {suggestion}")
            elif "incorrecto" in message.lower():
                print("   PROBLEMA: El valor del campo no coincide con los valores esperados.")
                print("   SUGERENCIA: Verifique los valores en 'success_values' o considere agregar el valor actual a 'warning_values'.")
                
                # Mostrar el valor actual para ayudar en la corrección
                if field_found:
                    print(f"\n   Valor actual en '{success_field}': {field_value}")
                    print(f"   Valores esperados: {success_values}")
        
        # 7. Propuesta de configuración mejorada
        if not valid or level != "success":
            print("\n6. Propuesta de configuración mejorada:")
            suggested_config = suggest_improved_config(validation_pattern, flat_response, service_type)
            print(json.dumps(suggested_config, indent=2))
            
            # Ofrecer actualizar la configuración
            if input("\n¿Desea actualizar a esta configuración mejorada? (s/n): ").lower() == 's':
                service_data['validation_pattern'] = suggested_config
                persistence.save_service_request(service_data)
                print("¡Configuración actualizada correctamente!")
                
                # Verificar nuevamente con la configuración actualizada
                print("\n7. Verificando nuevamente con la configuración actualizada:")
                if service_type == 'SOAP':
                    valid, message, level = soap_client.validate_response_advanced(response, suggested_config)
                else:  # REST
                    valid, message, level = rest_client.validate_response(response, suggested_config)
                
                print(f"   Resultado: {status_text[valid]}")
                print(f"   Nivel: {level_text.get(level, level)}")
                print(f"   Mensaje: {message}")
        
    except Exception as e:
        print(f"\nERROR durante el diagnóstico: {str(e)}")
        import traceback
        traceback.print_exc()

def find_potential_fields(flat_response: Dict[str, Any], validation_pattern: Dict[str, Any]) -> Dict[str, Any]:
    """
    Busca campos potenciales en la respuesta que podrían usarse para validación.
    
    Args:
        flat_response: Respuesta aplanada
        validation_pattern: Patrón de validación actual
        
    Returns:
        Dict[str, Any]: Campos sugeridos con sus valores
    """
    suggestions = {}
    
    # Buscar campos que podrían indicar estado
    status_keywords = ['status', 'estado', 'code', 'codigo', 'codMensaje', 'estadoRespuesta', 'result']
    
    # Buscar coincidencias en los campos de la respuesta
    for key in flat_response.keys():
        # Verificar por palabras clave en el nombre del campo
        for keyword in status_keywords:
            if keyword.lower() in key.lower():
                suggestions[key] = flat_response[key]
    
    return suggestions

def suggest_improved_config(current_config: Dict[str, Any], flat_response: Dict[str, Any], service_type: str) -> Dict[str, Any]:
    """
    Sugiere una configuración mejorada basada en la respuesta actual.
    
    Args:
        current_config: Configuración actual
        flat_response: Respuesta aplanada
        service_type: Tipo de servicio (SOAP o REST)
        
    Returns:
        Dict[str, Any]: Configuración sugerida
    """
    # Crear una base a partir de la configuración actual
    if not isinstance(current_config, dict):
        current_config = {"status": "ok"}
    
    # Crear una copia para no modificar el original
    suggested = current_config.copy()
    
    # Buscar mejores campos para success_field
    potential_fields = find_potential_fields(flat_response, current_config)
    
    # Extraer variables del patrón actual para referencia en las sugerencias
    success_field = current_config.get("success_field") if isinstance(current_config, dict) else None
    field_value = flat_response.get(success_field) if success_field and success_field in flat_response else None
    
    # Si encontramos campos potenciales, usar el primero
    if potential_fields and "success_field" not in suggested:
        first_key = list(potential_fields.keys())[0]
        suggested["success_field"] = first_key
        suggested["success_values"] = [str(potential_fields[first_key])]
    
    # Si el campo actual existe pero no es válido, agregar su valor actual a success_values
    elif success_field and field_value is not None:
        if "success_values" in suggested and isinstance(suggested["success_values"], list):
            if str(field_value) not in [str(v) for v in suggested["success_values"]]:
                suggested["success_values"].append(str(field_value))
        else:
            suggested["success_values"] = [str(field_value)]
    
    # Agregar estrategia de validación flexible
    if "validation_strategy" not in suggested:
        suggested["validation_strategy"] = "flexible"
    
    # Asegurar que tengamos listas de valores
    if "success_values" not in suggested:
        suggested["success_values"] = ["OK", "SUCCESS", "00000"] if service_type == "SOAP" else ["OK", "SUCCESS", "200"]
    
    if "warning_values" not in suggested:
        suggested["warning_values"] = ["WARNING", "2001", "2002"] if service_type == "SOAP" else ["WARNING", "PENDING"]
    
    # Establecer campos esperados si no los hay
    if "expected_fields" not in suggested:
        suggested["expected_fields"] = {}
        
        # Agregar algunos campos comunes encontrados
        for key in flat_response.keys():
            if key.endswith("result") or key.endswith("data") or key.endswith("response"):
                suggested["expected_fields"][key] = None
                break
    
    # Agregar rutas alternativas si no las hay
    if "alternative_paths" not in suggested:
        suggested["alternative_paths"] = []
        
        # Agregar rutas alternativas basadas en campos detectados
        for field in potential_fields:
            if field != suggested.get("success_field"):
                suggested["alternative_paths"].append({
                    "field": field,
                    "success_values": [str(potential_fields[field])]
                })
    
    return suggested

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python validation_tester.py <nombre_servicio> [--debug]")
        sys.exit(1)
    
    service_name = sys.argv[1]
    debug_mode = "--debug" in sys.argv
    
    test_service_validation(service_name, debug_mode)