# examples/rest_examples.py

import json
import os
from core.persistence import PersistenceManager

def crear_ejemplo_checksite():
        """Crea un ejemplo de servicio REST para CheckSiteStatus"""
        
        # Crear administrador de persistencia
        persistence = PersistenceManager()
        
        # Datos del servicio
        servicio = {
            'name': 'CheckSiteStatus',
            'description': 'Servicio para verificar el estado de un sitio',
            'type': 'REST',
            'url': 'https://localhost:5005/api/sitesCustom/CheckSiteStatus',
            'method': 'POST',
            'headers': {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            'params': {},
            'json_data': {
                'DocumentTypeId': 'NI',
                'DocumentNumber': 8605011452,
                'SiteName': 'booster036'
            },
            'validation_pattern': {
                'success_field': 'status',
                'success_values': ['OK', 'SUCCESS', 200],
                'validation_strategy': 'flexible'
            },
            'monitor_interval': 15,
            'monitor_enabled': True,
            'status': 'active'
        }
        
        # Guardar servicio
        persistence.save_soap_request(servicio)
        
        print("Servicio CheckSiteStatus creado correctamente")
    

def crear_ejemplos_rest(persistence):
    """Crea ejemplos de servicios REST"""
    
    # Ejemplo 1: API pública de usuarios
    ejemplo1 = {
        'name': 'API Usuarios',
        'description': 'Consulta de información de usuarios',
        'type': 'REST',
        'url': 'https://reqres.in/api/users',
        'method': 'GET',
        'headers': {
            'Accept': 'application/json'
        },
        'params': {
            'page': '1'
        },
        'validation_pattern': {
            'success_field': 'data',
            'status_code': {
                'success': [200]
            },
            'expected_fields': {
                'page': None,
                'data': None,
                'total': None
            },
            'validation_strategy': 'flexible'
        },
        'monitor_interval': 15,
        'monitor_enabled': True,
        'status': 'active'
    }
    
    # Ejemplo 2: API con autenticación Bearer
    ejemplo2 = {
        'name': 'API Posts',
        'description': 'Crear post',
        'type': 'REST',
        'url': 'https://jsonplaceholder.typicode.com/posts',
        'method': 'POST',
        'headers': {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': 'Bearer tu_token_aqui'
        },
        'params': {},
        'json_data': {
            'title': 'Test Post',
            'body': 'Este es un post de prueba',
            'userId': 1
        },
        'validation_pattern': {
            'status_code': {
                'success': [200, 201]
            },
            'expected_fields': {
                'id': None,
                'title': 'Test Post'
            },
            'validation_strategy': 'flexible'
        },
        'monitor_interval': 30,
        'monitor_enabled': True,
        'status': 'active'
    }
    
    # Guardar ejemplos
    persistence.save_service_request(ejemplo1)
    persistence.save_service_request(ejemplo2)
    
    print("Ejemplos REST creados correctamente")

if __name__ == "__main__":
    # Crear administrador de persistencia
    persistence = PersistenceManager()
    crear_ejemplos_rest(persistence)
    crear_ejemplo_checksite(persistence)