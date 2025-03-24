#!/usr/bin/env python
"""
Herramienta para verificar la paridad en la validación entre servicios SOAP y REST.

Esta herramienta compara los mecanismos de validación utilizados para SOAP y REST,
asegurando que ambos tipos de servicios se validen de manera consistente y flexible.

Uso: python validation_parity.py
"""

import os
import sys
import json
import logging
import inspect
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

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
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('validation_parity')

class ValidationParityChecker:
    """Comprobador de paridad de validación entre SOAP y REST"""
    
    def __init__(self):
        """Inicializa el comprobador de paridad"""
        self.persistence = PersistenceManager(base_path=os.path.join(project_root, 'data'))
        self.soap_client = SOAPClient()
        self.rest_client = RESTClient()
        
        # Cargar todos los servicios
        self.all_services = self.persistence.list_all_requests()
        
        # Separar por tipo
        self.soap_services = [s for s in self.all_services if s.get('type', 'SOAP') == 'SOAP']
        self.rest_services = [s for s in self.all_services if s.get('type', 'SOAP') == 'REST']
        
        logger.info(f"Total de servicios: {len(self.all_services)}")
        logger.info(f"Servicios SOAP: {len(self.soap_services)}")
        logger.info(f"Servicios REST: {len(self.rest_services)}")
    
    def analyze_validation_patterns(self):
        """Analiza los patrones de validación utilizados en todos los servicios"""
        print("\n===== ANÁLISIS DE PATRONES DE VALIDACIÓN =====\n")
        
        soap_patterns = self._extract_patterns(self.soap_services)
        rest_patterns = self._extract_patterns(self.rest_services)
        
        # Resumen de patrones SOAP
        print(f"Análisis de {len(soap_patterns)} patrones SOAP:")
        self._analyze_patterns(soap_patterns, "SOAP")
        
        # Resumen de patrones REST
        print(f"\nAnálisis de {len(rest_patterns)} patrones REST:")
        self._analyze_patterns(rest_patterns, "REST")
        
        # Verificar referencias cruzadas y consistencia
        print("\n===== VERIFICACIÓN DE CONSISTENCIA =====\n")
        self._check_cross_validation_compatibility(soap_patterns, rest_patterns)
    
    def _extract_patterns(self, services: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extrae patrones de validación de una lista de servicios.
        
        Args:
            services: Lista de servicios
            
        Returns:
            Lista de patrones de validación
        """
        patterns = []
        
        for service in services:
            pattern = service.get('validation_pattern', {})
            
            # Convertir strings JSON a diccionarios si es necesario
            if isinstance(pattern, str):
                try:
                    pattern = json.loads(pattern)
                except:
                    pattern = {"raw_text": pattern}
            
            # Añadir información del servicio para referencia
            pattern_info = {
                "service_name": service.get('name', 'Unknown'),
                "service_type": service.get('type', 'SOAP'),
                "pattern": pattern
            }
            
            patterns.append(pattern_info)
        
        return patterns
    
    def _analyze_patterns(self, patterns: List[Dict[str, Any]], service_type: str):
        """
        Analiza los patrones de validación y muestra estadísticas.
        
        Args:
            patterns: Lista de patrones de validación
            service_type: Tipo de servicio (SOAP o REST)
        """
        # Contar tipos de configuración
        strategies = {}
        fields_used = {}
        success_values = set()
        warning_values = set()
        failed_values = set()
        flexible_count = 0
        
        for p in patterns:
            pattern = p["pattern"]
            
            # Si no es un diccionario, omitir
            if not isinstance(pattern, dict):
                continue
                
            # Contar estrategias de validación
            strategy = pattern.get('validation_strategy', 'default')
            strategies[strategy] = strategies.get(strategy, 0) + 1
            
            # Contar campos utilizados para validación
            field = pattern.get('success_field', 'unknown')
            fields_used[field] = fields_used.get(field, 0) + 1
            
            # Recolectar valores de éxito/advertencia/fallo
            for val in pattern.get('success_values', []):
                success_values.add(str(val))
            
            for val in pattern.get('warning_values', []):
                warning_values.add(str(val))
                
            for val in pattern.get('failed_values', []):
                failed_values.add(str(val))
            
            # Contar servicios con validación flexible
            if strategy == 'flexible' or pattern.get('treat_empty_as_success', False):
                flexible_count += 1
        
        # Mostrar resultados
        print(f"Estrategias de validación:")
        for strategy, count in strategies.items():
            print(f"   - {strategy}: {count} servicios")
        
        print(f"\nCampos de éxito más comunes:")
        for field, count in sorted(fields_used.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"   - {field}: {count} servicios")
        
        print(f"\nValores de éxito comunes: {', '.join(list(success_values)[:5])}")
        print(f"Valores de advertencia comunes: {', '.join(list(warning_values)[:5])}")
        print(f"Valores de fallo comunes: {', '.join(list(failed_values)[:5])}")
        
        # Calcular porcentaje de flexibilidad con manejo seguro
        if patterns:
            flex_percentage = (flexible_count / len(patterns)) * 100
        else:
            flex_percentage = 0
            
        print(f"\nServicios con validación flexible: {flexible_count} de {len(patterns)} ({flex_percentage:.1f}%)")
        
        # Identificar servicios sin validación flexible
        if flexible_count < len(patterns):
            print("\nServicios sin validación flexible:")
            for p in patterns:
                pattern = p["pattern"]
                if isinstance(pattern, dict):
                    strategy = pattern.get('validation_strategy', 'default')
                    treat_empty = pattern.get('treat_empty_as_success', False)
                    
                    if strategy != 'flexible' and not treat_empty:
                        print(f"   - {p['service_name']}")
    
    def _check_cross_validation_compatibility(self, soap_patterns: List[Dict[str, Any]], 
                                             rest_patterns: List[Dict[str, Any]]):
        """
        Verifica la compatibilidad cruzada entre validaciones SOAP y REST.
        
        Args:
            soap_patterns: Patrones de validación SOAP
            rest_patterns: Patrones de validación REST
        """
        # Extraer campos utilizados en cada tipo
        soap_fields = self._extract_common_fields(soap_patterns)
        rest_fields = self._extract_common_fields(rest_patterns)
        
        # Verificar similitudes y diferencias
        print("Campos comunes en ambos tipos de servicios:")
        common_fields = set(soap_fields.keys()) & set(rest_fields.keys())
        for field in common_fields:
            print(f"   - {field}: SOAP ({soap_fields[field]}), REST ({rest_fields[field]})")
        
        print("\nCampos únicos en servicios SOAP:")
        soap_unique = set(soap_fields.keys()) - set(rest_fields.keys())
        for field in soap_unique:
            print(f"   - {field}: {soap_fields[field]}")
        
        print("\nCampos únicos en servicios REST:")
        rest_unique = set(rest_fields.keys()) - set(soap_fields.keys())
        for field in rest_unique:
            print(f"   - {field}: {rest_fields[field]}")
        
        # Verificar mecanismos de validación
        print("\nVerificación de mecanismos de validación:")
        
        # 1. Comprobar que ambos tipos usen validate_response_advanced
        soap_method_source = self._inspect_validation_method(self.soap_client)
        rest_method_source = self._inspect_validation_method(self.rest_client)
        
        if soap_method_source == rest_method_source:
            print("✓ Ambos tipos utilizan la misma función de validación")
        else:
            print("✗ Diferencias detectadas en la función de validación:")
            print(f"   - SOAP: {soap_method_source}")
            print(f"   - REST: {rest_method_source}")
        
        # 2. Proponer recomendaciones de estandarización
        self._suggest_standardization(soap_patterns, rest_patterns)
    
    def _extract_common_fields(self, patterns: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Extrae campos comunes de validación con sus recuentos.
        
        Args:
            patterns: Lista de patrones de validación
            
        Returns:
            Campos comunes y su frecuencia
        """
        fields = {}
        
        for p in patterns:
            pattern = p["pattern"]
            if isinstance(pattern, dict):
                field = pattern.get('success_field')
                if field:
                    fields[field] = fields.get(field, 0) + 1
        
        return fields
    
    def _inspect_validation_method(self, client) -> str:
        """
        Inspecciona el método de validación utilizado por un cliente.
        
        Args:
            client: Cliente (SOAP o REST)
            
        Returns:
            Identificador del método de validación
        """
        # Obtener el método de validación
        if hasattr(client, 'validate_response_advanced'):
            return "validate_response_advanced"
        elif hasattr(client, 'validate_response'):
            return "validate_response"
        else:
            return "unknown"
    
    def _suggest_standardization(self, soap_patterns: List[Dict[str, Any]], 
                               rest_patterns: List[Dict[str, Any]]):
        """
        Sugiere estandarizaciones para mejorar la consistencia entre SOAP y REST.
        
        Args:
            soap_patterns: Patrones de validación SOAP
            rest_patterns: Patrones de validación REST
        """
        print("\n===== RECOMENDACIONES DE ESTANDARIZACIÓN =====\n")
        
        # Generar patrón estandarizado para cada tipo
        print("Patrones de validación recomendados:")
        
        # Patrón para SOAP
        soap_std_pattern = self._generate_standard_pattern(soap_patterns, "SOAP")
        print("\nPatrón estándar para SOAP:")
        print(json.dumps(soap_std_pattern, indent=2))
        
        # Patrón para REST
        rest_std_pattern = self._generate_standard_pattern(rest_patterns, "REST")
        print("\nPatrón estándar para REST:")
        print(json.dumps(rest_std_pattern, indent=2))
        
        # Lista de servicios que necesitan actualización
        self._list_services_needing_update()
    
    def _generate_standard_pattern(self, patterns: List[Dict[str, Any]], service_type: str) -> Dict[str, Any]:
        """
        Genera un patrón de validación estándar basado en patrones existentes.
        
        Args:
            patterns: Lista de patrones de validación
            service_type: Tipo de servicio (SOAP o REST)
            
        Returns:
            Patrón de validación estándar
        """
        # Determinar campo más común
        fields = {}
        for p in patterns:
            pattern = p["pattern"]
            if isinstance(pattern, dict):
                field = pattern.get('success_field')
                if field:
                    fields[field] = fields.get(field, 0) + 1
        
        # Encontrar el más común
        common_field = None
        if fields:
            common_field = max(fields.items(), key=lambda x: x[1])[0]
        
        # Si es SOAP, usar codMensaje por defecto
        if service_type == "SOAP" and not common_field:
            common_field = "codMensaje"
        
        # Si es REST, usar status por defecto
        if service_type == "REST" and not common_field:
            common_field = "status"
        
        # Recolectar valores comunes
        success_values = set()
        warning_values = set()
        failed_values = set()
        
        for p in patterns:
            pattern = p["pattern"]
            if isinstance(pattern, dict):
                for val in pattern.get('success_values', []):
                    success_values.add(str(val))
                
                for val in pattern.get('warning_values', []):
                    warning_values.add(str(val))
                    
                for val in pattern.get('failed_values', []):
                    failed_values.add(str(val))
        
        # Generar patrón estándar
        standard_pattern = {
            "success_field": common_field,
            "success_values": list(success_values)[:5] if success_values else (["00000"] if service_type == "SOAP" else ["200", "OK"]),
            "warning_values": list(warning_values)[:5] if warning_values else (["2001", "2002"] if service_type == "SOAP" else ["PENDING", "IN_PROGRESS"]),
            "failed_values": list(failed_values)[:5] if failed_values else (["5000", "9999"] if service_type == "SOAP" else ["ERROR", "FAILED"]),
            "validation_strategy": "flexible",
            "alternative_paths": [],
            "expected_fields": {}
        }
        
        # Agregar caminos alternativos según el tipo
        if service_type == "SOAP":
            standard_pattern["alternative_paths"].append({
                "field": "estadoRespuesta",
                "success_values": ["OK", "SUCCESS"]
            })
        else:  # REST
            standard_pattern["alternative_paths"].append({
                "field": "code",
                "success_values": ["200", "201", "OK"]
            })
        
        return standard_pattern
    
    def _list_services_needing_update(self):
        """Lista servicios que necesitan actualizarse a patrones flexibles"""
        print("\nServicios que necesitan ser actualizados a patrones flexibles:")
        
        count = 0
        for service in self.all_services:
            pattern = service.get('validation_pattern', {})
            
            # Convertir strings JSON a diccionarios si es necesario
            if isinstance(pattern, str):
                try:
                    pattern = json.loads(pattern)
                except:
                    pattern = {}
            
            # Verificar si usa validación flexible
            if isinstance(pattern, dict):
                strategy = pattern.get('validation_strategy', 'default')
                if strategy != 'flexible':
                    print(f"   - {service.get('name')} ({service.get('type', 'SOAP')})")
                    count += 1
        
        if count == 0:
            print("   ✓ Todos los servicios ya utilizan patrones flexibles")
    
    def test_validation_functions(self):
        """
        Prueba las funciones de validación para SOAP y REST.
        """
        print("\n===== PRUEBA DE FUNCIONES DE VALIDACIÓN =====\n")
        
        # Crear respuestas de prueba
        test_responses = [
            {
                "name": "Respuesta SOAP típica con codMensaje",
                "response": {
                    "cabecera": {
                        "codMensaje": "00000",
                        "fechaProceso": "2023-01-01"
                    },
                    "datos": {
                        "valor": "test"
                    }
                }
            },
            {
                "name": "Respuesta REST típica con status",
                "response": {
                    "status": "success",
                    "code": 200,
                    "data": {
                        "id": 123,
                        "name": "test"
                    }
                }
            },
            {
                "name": "Respuesta con campos anidados",
                "response": {
                    "result": {
                        "status": {
                            "code": "00",
                            "message": "OK"
                        }
                    },
                    "data": [1, 2, 3]
                }
            },
            {
                "name": "Respuesta con estadoRespuesta",
                "response": {
                    "estadoRespuesta": "OK",
                    "result": {
                        "value": 123
                    }
                }
            }
        ]
        
        # Crear patrones de validación para probar
        test_patterns = [
            {
                "name": "Patrón simple con status",
                "pattern": {
                    "status": "ok"
                }
            },
            {
                "name": "Patrón SOAP estándar",
                "pattern": {
                    "success_field": "codMensaje",
                    "success_values": ["00000", "OK"],
                    "validation_strategy": "flexible"
                }
            },
            {
                "name": "Patrón REST estándar",
                "pattern": {
                    "success_field": "status",
                    "success_values": ["success", "OK", 200],
                    "validation_strategy": "flexible"
                }
            },
            {
                "name": "Patrón con rutas alternativas",
                "pattern": {
                    "success_field": "codMensaje",
                    "success_values": ["00000"],
                    "alternative_paths": [
                        {
                            "field": "estadoRespuesta",
                            "success_values": ["OK"]
                        },
                        {
                            "field": "result.status.code",
                            "success_values": ["00"]
                        }
                    ],
                    "validation_strategy": "flexible"
                }
            }
        ]
        
        # Matriz de pruebas
        print("Ejecutando pruebas de validación cruzada con ambos clientes:")
        print(f"{'Respuesta':<30} {'Patrón':<30} {'SOAP Client':<15} {'REST Client':<15}")
        print("-" * 90)
        
        for resp in test_responses:
            for pat in test_patterns:
                try:
                    # Probar con SOAPClient
                    soap_valid, soap_msg, soap_level = self.soap_client.validate_response_advanced(
                        resp["response"], pat["pattern"]
                    )
                    
                    # Probar con RESTClient
                    rest_valid, rest_msg, rest_level = self.rest_client.validate_response(
                        resp["response"], pat["pattern"]
                    )
                    
                    # Mostrar resultados de la prueba
                    soap_result = f"{soap_level.upper()}"
                    rest_result = f"{rest_level.upper()}"
                    
                    # Resaltar diferencias
                    parity = "✓" if soap_valid == rest_valid and soap_level == rest_level else "✗"
                    
                    print(f"{resp['name'][:29]:<30} {pat['name'][:29]:<30} {soap_result:<15} {rest_result:<15} {parity}")
                except Exception as e:
                    print(f"{resp['name'][:29]:<30} {pat['name'][:29]:<30} ERROR: {str(e)}")
        
        # Recomendar ajustes si hay diferencias
        self._recommend_client_adjustments()
    
    def _recommend_client_adjustments(self):
        """Recomienda ajustes si hay diferencias entre los clientes SOAP y REST"""
        print("\nRecomendaciones para la paridad de validación:")
        
        # Verificar si los métodos son idénticos
        if hasattr(self.soap_client, 'validate_response_advanced') and hasattr(self.rest_client, 'validate_response'):
            # Verificar si son diferentes funciones
            soap_code = None
            rest_code = None
            
            if hasattr(self.soap_client.validate_response_advanced, '__code__'):
                soap_code = self.soap_client.validate_response_advanced.__code__.co_code
                
            if hasattr(self.rest_client.validate_response, '__code__'):
                rest_code = self.rest_client.validate_response.__code__.co_code
            
            if soap_code and rest_code and soap_code != rest_code:
                print("   ✗ Se detectaron diferencias en los métodos de validación.")
                print("   Recomendación: Actualizar RESTClient para que use el mismo método validate_response_advanced.")
                print("""
def validate_response(self, response: Dict[str, Any], 
                     validation_schema: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, str]:
    \"\"\"
    Valida la respuesta REST con reglas avanzadas configurables.
    Delegación al método del SOAPClient para mantener la consistencia.
    
    Args:
        response (Dict[str, Any]): Respuesta REST a validar
        validation_schema (Dict[str, Any], optional): Esquema de validación
        
    Returns:
        Tuple[bool, str, str]: (éxito, mensaje, nivel: 'success'|'warning'|'failed'|'error')
    \"\"\"
    from core.soap_client import SOAPClient
    soap_client = SOAPClient()
    return soap_client.validate_response_advanced(response, validation_schema)
                """)
            else:
                print("   ✓ Ambos clientes utilizan funciones de validación compatibles.")
        else:
            print("   ✗ Los clientes utilizan métodos de validación diferentes.")
            print("   Recomendación: Asegurar que ambos clientes implementen validate_response_advanced.")

    def suggest_updates(self):
        """Sugiere actualizaciones específicas para cada servicio"""
        print("\n===== SUGERENCIAS DE ACTUALIZACIÓN =====\n")
        
        # Servicios que requieren actualización
        services_to_update = []
        
        for service in self.all_services:
            pattern = service.get('validation_pattern', {})
            
            # Convertir strings JSON a diccionarios si es necesario
            if isinstance(pattern, str):
                try:
                    pattern = json.loads(pattern)
                except:
                    pattern = {}
            
            # Verificar si usa validación flexible
            update_needed = False
            if isinstance(pattern, dict):
                strategy = pattern.get('validation_strategy', '')
                if strategy != 'flexible':
                    update_needed = True
            else:
                update_needed = True
            
            if update_needed:
                services_to_update.append(service)
        
        if not services_to_update:
            print("✓ No se requieren actualizaciones, todos los servicios utilizan patrones flexibles.")
            return
        
        print(f"Se encontraron {len(services_to_update)} servicios que requieren actualización:")
        
        for service in services_to_update:
            service_name = service.get('name', 'Unknown')
            service_type = service.get('type', 'SOAP')
            
            print(f"\n{service_name} ({service_type}):")
            
            # Patrón actual
            current_pattern = service.get('validation_pattern', {})
            print("   Patrón actual:")
            if isinstance(current_pattern, dict):
                print(f"   {json.dumps(current_pattern, indent=2)}")
            else:
                print(f"   {current_pattern}")
            
            # Sugerir actualización
            suggested_pattern = self._suggest_pattern_for_service(service)
            print("   Patrón sugerido:")
            print(f"   {json.dumps(suggested_pattern, indent=2)}")
            
            # Generar línea de comando para actualizar
            print("\n   Para actualizar, ejecutar:")
            print(f"   python tools/update_validation_pattern.py \"{service_name}\"")

    def _suggest_pattern_for_service(self, service: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sugiere un patrón de validación para un servicio específico.
        
        Args:
            service: Datos del servicio
            
        Returns:
            Patrón de validación sugerido
        """
        service_type = service.get('type', 'SOAP')
        current_pattern = service.get('validation_pattern', {})
        
        # Base para el nuevo patrón
        suggested = {
            "validation_strategy": "flexible"
        }
        
        # Si ya es un diccionario, preservar los campos existentes
        if isinstance(current_pattern, dict):
            for key, value in current_pattern.items():
                if key != 'validation_strategy':
                    suggested[key] = value
        
        # Si no tiene success_field, agregar uno según el tipo
        if 'success_field' not in suggested:
            if service_type == 'SOAP':
                suggested['success_field'] = "codMensaje"
                suggested['success_values'] = ["00000", "0", "OK"]
            else:  # REST
                suggested['success_field'] = "status"
                suggested['success_values'] = ["success", "OK", "200"]
        
        # Agregar campos comunes según el tipo
        if service_type == 'SOAP':
            # Si no tiene rutas alternativas, agregar algunas
            if 'alternative_paths' not in suggested:
                suggested['alternative_paths'] = [
                    {
                        "field": "estadoRespuesta",
                        "success_values": ["OK", "SUCCESS"]
                    }
                ]
            
            # Si no tiene valores de advertencia, agregar algunos
            if 'warning_values' not in suggested:
                suggested['warning_values'] = ["2001", "2002", "WARN"]
        else:  # REST
            # Si no tiene rutas alternativas, agregar algunas
            if 'alternative_paths' not in suggested:
                suggested['alternative_paths'] = [
                    {
                        "field": "code",
                        "success_values": ["200", "201", "OK"]
                    }
                ]
            
            # Si no tiene valores de advertencia, agregar algunos
            if 'warning_values' not in suggested:
                suggested['warning_values'] = ["PENDING", "IN_PROGRESS", "WARNING"]
        
        return suggested

def main():
    """Función principal"""
    checker = ValidationParityChecker()
    
    # Analizar patrones de validación
    checker.analyze_validation_patterns()
    
    # Probar funciones de validación
    checker.test_validation_functions()
    
    # Sugerir actualizaciones específicas
    checker.suggest_updates()

if __name__ == "__main__":
    main()