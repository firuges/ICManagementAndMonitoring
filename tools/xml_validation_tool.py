#!/usr/bin/env python
"""
Herramienta de diagnóstico para validar parseo de XML con namespaces complejos.

Esta herramienta permite probar cómo se procesan los XML complejos,
especialmente aquellos con namespaces problemáticos como v1.:codMensaje.

Uso: python xml_validation_tool.py <archivo_xml> [--debug]
"""

import os
import sys
import logging
import argparse
import xmltodict
import json
from typing import Dict, Any, List, Optional

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('xml_validator')

def flatten_dict(d: Dict[str, Any], parent_key: str = '', 
                separator: str = '.') -> Dict[str, Any]:
    """
    Función mejorada para aplanar un diccionario anidado con manejo especial de namespaces.
    
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
            
        if isinstance(v, dict):
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
            items.append((clean_key, v))  # Versión simplificada
            # Para namespaces completos, agregar versión sin namespace
            if ':' in k or '.:' in k:
                items.append((clean_key, v))
    
    # Eliminar duplicados manteniendo el último valor
    result = {}
    for k, v in items:
        result[k] = v
        
    return result

def test_xml_parsing(xml_file: str, debug_mode: bool = False) -> None:
    """
    Prueba el parseo de un archivo XML con manejo de namespaces complejos.
    
    Args:
        xml_file (str): Ruta al archivo XML a validar
        debug_mode (bool): Activar modo de depuración extendida
    """
    try:
        print(f"\n===== DIAGNÓSTICO DE VALIDACIÓN XML: {os.path.basename(xml_file)} =====\n")
        
        # Verificar que el archivo existe
        if not os.path.exists(xml_file):
            print(f"Error: El archivo {xml_file} no existe.")
            return
        
        # Cargar el XML
        with open(xml_file, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        
        print(f"XML cargado: {len(xml_content)} caracteres")
        
        # Intentar parsearlo con xmltodict
        print("\n1. Procesando con xmltodict:")
        try:
            xml_dict = xmltodict.parse(xml_content)
            print("✅ Parseo XML exitoso")
            
            # Mostrar estructura de alto nivel
            print("\n   Estructura de alto nivel:")
            for key in xml_dict.keys():
                print(f"   - {key}")
                
            if debug_mode:
                print("\n   Contenido completo:")
                print(json.dumps(xml_dict, indent=2, default=str))
        except Exception as e:
            print(f"❌ Error en parseo XML: {str(e)}")
            return
        
        # Aplanar el diccionario para análisis
        print("\n2. Aplanando diccionario para análisis:")
        flat_dict = flatten_dict(xml_dict)
        print(f"   Generados {len(flat_dict)} campos aplanados")
        
        # Buscar campos problemáticos específicos
        print("\n3. Búsqueda de campos con namespace problemático:")
        problem_fields = []
        
        for key in flat_dict.keys():
            if ':' in key or '.:' in key:
                problem_fields.append(key)
                
        if problem_fields:
            print("   Campos con namespaces potencialmente problemáticos:")
            for field in sorted(problem_fields):
                value = flat_dict[field]
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:97] + "..."
                print(f"   - {field} = {value_str}")
        else:
            print("   No se encontraron campos con namespaces problemáticos")
            
        # Verificar campo específico de codMensaje
        print("\n4. Verificación específica de campo codMensaje:")
        cod_mensaje_fields = []
        
        for key in flat_dict.keys():
            if 'codMensaje' in key:
                cod_mensaje_fields.append(key)
                
        if cod_mensaje_fields:
            print("   Campos codMensaje encontrados:")
            for field in sorted(cod_mensaje_fields):
                value = flat_dict[field]
                print(f"   - {field} = {value}")
                
            # Sugerencia de patrón de validación para este XML
            cod_mensaje_key = cod_mensaje_fields[0]  # Usar el primero encontrado
            cod_mensaje_value = flat_dict[cod_mensaje_key]
            
            print("\n5. Sugerencia de patrón de validación:")
            validation_pattern = {
                "success_field": "codMensaje",
                "success_values": ["00000"],
                "warning_values": ["2001", "2002"],
                "validation_strategy": "flexible"
            }
            
            # Ajustar según el valor encontrado
            if cod_mensaje_value and str(cod_mensaje_value) != "00000":
                if str(cod_mensaje_value).startswith("2"):
                    validation_pattern["warning_values"].append(str(cod_mensaje_value))
                    print(f"   Se agregó {cod_mensaje_value} a warning_values")
                else:
                    validation_pattern["success_values"].append(str(cod_mensaje_value))
                    print(f"   Se agregó {cod_mensaje_value} a success_values")
            
            print("\n   Patrón de validación sugerido:")
            print(json.dumps(validation_pattern, indent=2))
        else:
            print("   No se encontraron campos codMensaje")
            
        # 6. Verificar si el XML está bien formado
        print("\n6. Verificación de formato XML correcto:")
        try:
            import xml.etree.ElementTree as ET
            ET.fromstring(xml_content)
            print("✅ XML bien formado")
        except Exception as e:
            print(f"❌ XML mal formado: {str(e)}")
        
        print("\n===== FIN DEL DIAGNÓSTICO =====")
            
    except Exception as e:
        print(f"\nError durante el diagnóstico: {str(e)}")
        if debug_mode:
            import traceback
            traceback.print_exc()

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description="Validador de XML con namespaces complejos")
    parser.add_argument("xml_file", help="Archivo XML a validar")
    parser.add_argument("--debug", action="store_true", help="Activar modo de depuración extendida")
    
    args = parser.parse_args()
    
    # Validar el XML
    test_xml_parsing(args.xml_file, args.debug)

if __name__ == "__main__":
    main()