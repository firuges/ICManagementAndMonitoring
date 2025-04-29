# Monitor de Servicios SOAP y REST

Una aplicación de gestión y monitoreo de servicios SOAP con interfaz gráfica, validación de respuestas, notificaciones por correo electrónico y programación de tareas.

## Características Principales

- **Gestión de Servicios SOAP y REST **: Crear, editar y gestionar múltiples servicios SOAP y REST.
- **Monitoreo Continuo**: Verificar periódicamente el estado de los servicios.
- **Validación de Respuestas**: Definir patrones de validación para verificar respuestas.
- **Notificaciones por Email**: Envío automático de alertas ante fallos.
- **Programación de Tareas**: Integración con el programador del sistema operativo.
- **Interfaz Gráfica Intuitiva**: Gestión visual de todos los servicios.
- **Modo Headless**: Ejecución desde línea de comandos sin interfaz gráfica.
- **Herramientas de Diagnostico**: Utilidades para resolver problemas de validación.

## Requisitos

- Python 3.7 o superior
- PyQt5
- Zeep (Cliente SOAP)
- Requests (Cliente REST)
- Bibliotecas adicionales (ver requirements.txt)

## Instalación

1. Clonar el repositorio:
   ```bash
   git clone https://github.com/username/soap-monitor.git
   cd soap-monitor
   ```

2. Crear un entorno virtual (recomendado):
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```

3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

## Uso

### Iniciar la Aplicación con Interfaz Gráfica

```bash
python app.py
```

### Modo Headless (sin interfaz gráfica)

Verificar un servicio específico:
```bash
python app.py --check "NombreServicio"
```

Verificar todos los servicios:
```bash
python app.py --check-all
```

Guía de Usuario
1. Gestión de Servicios
Para crear un nuevo servicio SOAP o REST:

  1. Ir a la pestaña "Gestión de Requests"
  2. Seleccionar el tipo de servicio (SOAP o REST)
  3. Completar los campos según el tipo:

Para SOAP:

  * Nombre: Identificador descriptivo del servicio
  * Descripción: Detalle del propósito del servicio
  * URL WSDL: Dirección del WSDL del servicio
  * Request XML: Estructura XML del request SOAP

Para REST:

  * Nombre: Identificador descriptivo del servicio
  * Descripción: Detalle del propósito del servicio
  * URL: Endpoint del servicio REST
  * Método HTTP: GET, POST, PUT, DELETE, etc.
  * Headers: Cabeceras HTTP requeridas
  * Query Parameters: Parámetros de consulta
  * Body JSON: Datos a enviar en formato JSON (para POST/PUT)


  4. Configurar patrones de validación:

    * Definir cómo se validarán las respuestas (ver sección "Patrones de Validación")


  5. Configurar opciones de monitoreo:

    * Intervalo: Frecuencia de verificación en minutos
    * Timeout: Tiempo máximo de espera para la respuesta
    * Reintentos: Número de intentos en caso de fallo de conexión
    * Activar monitoreo: Habilitar verificación automática
    * Añadir al programador de tareas: Registrar en el sistema operativo


  6. Hacer clic en "Guardar"

## 2. Patrones de Validación
Los patrones de validación permiten verificar si la respuesta del servicio es correcta. Se configuran en formato JSON:
{
  "success_field": "codMensaje",
  "success_values": ["00000", "0", "OK"],
  "warning_values": ["2001", "2002"],
  "validation_strategy": "flexible",
  "alternative_paths": [
    {
      "field": "estadoRespuesta",
      "success_values": ["OK", "SUCCESS"]
    }
  ],
  "expected_fields": {
    "resultado": null
  }
}

Donde:

 * success_field: Campo que indica éxito/error (ej: "codMensaje" o "status")
 * success_values: Lista de valores que indican éxito
 * warning_values: Lista de valores que se tratan como advertencia
 * failed_values: Lista de valores que indican fallo conocido
 * validation_strategy: Estrategia de validación ("strict", "flexible", "permissive")
 * alternative_paths: Rutas alternativas para validación
 * expected_fields: Campos adicionales que deben existir, con valores específicos o null (solo verificar existencia)

## 3. Configuración de Notificaciones
Para configurar las notificaciones por email:

  1. Ir a la pestaña "Configuración de Notificaciones"
  2. Completar la configuración SMTP:

    * Servidor SMTP: Dirección del servidor de correo
    * Puerto: Puerto de conexión (normalmente 587 para TLS)
    * Usuario y Contraseña: Credenciales de acceso


  3. Añadir destinatarios de correo electrónico
  4. Configurar opciones de notificación:

    * Notificar errores de conexión: Alertar problemas de conectividad
    * Notificar errores de validación: Alertar respuestas incorrectas


  5. Hacer clic en "Guardar configuración"

## Contenido de las Notificaciones
Las notificaciones por correo electrónico incluyen:

  * Detalles del error ocurrido
  * Solicitud XML/JSON original (como adjunto)
  * Respuesta recibida (como adjunto)
  * Información de diagnóstico

## 4. Monitoreo de Servicios
La pestaña "Monitoreo" muestra:

  * Tabla de Servicios: Lista de todos los servicios configurados
  * Detalles del Servicio: Información detallada del servicio seleccionado
  * Última Respuesta: Contenido de la última respuesta recibida
  * Log de Eventos: Registro de actividades y errores

Funciones disponibles:

  * Verificar: Comprobar un servicio específico
  * Verificar Todos: Comprobar todos los servicios
  * Actualizar: Refrescar la lista de servicios
  * Filtrar por Grupo: Ver solo servicios de un grupo específico

## 5. Herramientas de Diagnóstico
El sistema incluye herramientas para diagnosticar y solucionar problemas:

  * validation_tester.py: Prueba la validación de un servicio específico
    - python tools/validation_tester.py "NombreServicio"

  * validation_parity.py: Verifica la consistencia entre validaciones SOAP y REST
    - python tools/validation_parity.py

  * update_validation_pattern.py: Actualiza patrones de validación existentes
    - python tools/update_validation_pattern.py "NombreServicio"

  * xml_validation_tool.py: Diagnostica problemas con XML complejos
    - python tools/xml_validation_tool.py archivo.xml

  * Script de prueba para validar el manejo mejorado de namespaces complejos
    - python test_validation_improvements.py
## Estructura del Proyecto
soap_rest_monitor/
│
├── app.py                  # Punto de entrada de la aplicación
├── requirements.txt        # Dependencias
│
├── core/                   # Componentes del núcleo
│   ├── persistence.py      # Gestión de archivos JSON
│   ├── soap_client.py      # Cliente SOAP y validación
│   ├── rest_client.py      # Cliente REST
│   ├── notification.py     # Sistema de notificaciones
│   ├── scheduler.py        # Programador de tareas
│   ├── monitor.py          # Script de monitoreo independiente
│   └── utils.py            # Utilidades generales
│
├── gui/                    # Componentes de interfaz gráfica
│   ├── main_window.py      # Ventana principal
│   ├── request_form.py     # Formulario de requests
│   ├── email_form.py       # Formulario de emails
│   ├── monitoring_panel.py # Panel de monitoreo
│   └── admin_check_dialog.py # Verificación de permisos
│
├── data/                   # Almacenamiento de datos
│   ├── requests/           # Configuraciones de servicios (JSON)
│   ├── email_config.json   # Configuración de destinatarios
│   └── smtp_config.json    # Configuración SMTP
│
├── logs/                   # Registros de la aplicación
│
├── debug/                  # Archivos de diagnóstico
│
├── tools/                  # Herramientas de utilidad
│   ├── validation_tester.py       # Diagnóstico de validación
│   ├── validation_parity.py       # Verificación de consistencia
│   ├── update_validation_pattern.py # Actualización de patrones
│   └── xml_validation_tool.py     # Herramienta de análisis XML
│
├── task_templates/         # Plantillas para tareas programadas
│
└── examples/               # Scripts de ejemplo
    └── create_service_request.py  # Creación de request de ejemplo


##  Integración con el Sistema de Tareas
La aplicación puede registrar tareas en el programador del sistema operativo:

  * En Windows: Usa el programador de tareas (Task Scheduler)
  * En Linux/Unix: Usa crontab

Para activar esta función, marque la opción "Añadir al programador de tareas del sistema" al crear o editar un servicio.

## Solución de Problemas
  Errores de Validación

  * Si un servicio está fallando en validación, use las herramientas de diagnóstico:
    - python tools/validation_tester.py "NombreServicio"
  * Para actualizar a un patrón de validación flexible:
    - python tools/update_validation_pattern.py "NombreServicio"


## Errores de Conexión SMTP

  * Verifique que el servidor SMTP esté correctamente configurado
Si usa Gmail, habilite "Acceso de aplicaciones menos seguras" o use una "Contraseña de aplicación"

## Errores en Servicios SOAP/REST

  * Verifique que las URLs sean accesibles
  * Compruebe que el formato del XML/JSON sea correcto
  * Verifique que los namespaces/headers sean correctos
  * Ajuste los valores de timeout y reintentos si el servicio es lento

## Estrategias de Validación
La aplicación soporta varias estrategias de validación:

  * strict: Todos los criterios deben cumplirse exactamente
  * flexible: Permite distintas estructuras y valores alternativos
  * permissive: Acepta casi cualquier respuesta no vacía

Los patrones de validación flexible pueden procesar:

  * Estructuras XML/JSON anidadas
  * Múltiples rutas para campo de éxito
  * Namespaces complejos (como v1.)
  * Valores de advertencia que no indican errores críticos

Licencia
MIT License
Contacto
Para soporte o consultas:

Email: maximilianocesan@gmail.com
Repositorio: https://github.com/firuges/soap-rest-monitor



Resumen de la Aplicación Desarrollada
He creado una aplicación completa para el monitoreo y gestión de servicios SOAP con las siguientes características y componentes:
Estructura y Componentes Principales

Módulo Core: Implementa la lógica principal de la aplicación

persistence.py: Sistema de persistencia para almacenar configuraciones en JSON
soap_client.py: Cliente SOAP para enviar peticiones y validar respuestas
notification.py: Sistema de notificaciones por email
scheduler.py: Programador de tareas para verificaciones periódicas
monitor.py: Script para ejecutar monitoreo independiente


Interfaz Gráfica: Proporciona una experiencia de usuario intuitiva

main_window.py: Ventana principal de la aplicación
request_form.py: Formulario para gestionar requests SOAP
email_form.py: Configuración de notificaciones
monitoring_panel.py: Panel de monitoreo con tabla de servicios y detalles


Funcionalidades Principales:

Gestión de múltiples servicios SOAP
Validación de respuestas mediante patrones configurables
Notificaciones por email cuando un servicio falla
Programación de tareas (integración con el sistema operativo)
Modo headless para ejecución desde línea de comandos



Características Destacadas

Validación Personalizada: Define exactamente qué esperar en las respuestas
Interfaz Visual: Monitoreo en tiempo real con información detallada
Persistencia: Almacenamiento eficiente de configuraciones en formato JSON
Notificaciones: Alertas automáticas por email ante problemas
Flexibilidad: Uso tanto con interfaz gráfica como por línea de comandos

Instrucciones de Uso

Instalación:

Instalar dependencias con pip install -r requirements.txt
Ejecutar python app.py para iniciar la aplicación


Configuración de Servicios:

Usa la pestaña "Gestión de Requests" para crear servicios SOAP
Define el XML del request y URL del WSDL
Configura patrones de validación para las respuestas


Configuración de Notificaciones:

Configura el servidor SMTP para envío de emails
Añade destinatarios para recibir notificaciones


Monitoreo:

Usa la pestaña "Monitoreo" para verificar servicios
Los servicios se verifican automáticamente según el intervalo configurado


Ejecución Headless:

Usa python app.py --check-all para verificar todos los servicios desde CLI
Útil para integraciones con otros sistemas



## Ejemplo Incluido
Se ha incluido un script de ejemplo (examples/create_ejectransfinter_request.py) que crea automáticamente una configuración para el servicio EjecTransfInter basado en el WSDL que proporcionaste. Esto facilita comenzar a usar la aplicación rápidamente.
Próximos Pasos

Ejecutar el script de ejemplo para crear la configuración inicial:
Copiarpython examples/create_ejectransfinter_request.py

Iniciar la aplicación y verificar que el servicio esté configurado:
Copiarpython app.py

Configurar las notificaciones por email en la pestaña correspondiente
Utilizar el panel de monitoreo para verificar el estado del servicio

Esta aplicación proporciona una solución completa para el monitoreo de servicios SOAP, cumpliendo con todos los requerimientos especificados inicialmente y ofreciendo una experiencia de usuario intuitiva y funcional.


Ejemplos Prácticos de Implementación
## Ejemplo 1: Validación con Advertencias
Para un servicio que considera "2001" como advertencia y no como error:
{
  "success_field": "codMensaje",
  "success_values": ["00000"],
  "warning_values": ["2001"],
  "expected_fields": {
    "fechaProximoCorte": null
  },
  "validation_strategy": "flexible"
}
## Ejemplo 2: Validación con Campo Alternativo
Para un servicio que usa un campo diferente para indicar éxito:
{
  "success_field": "estadoRespuesta",
  "success_values": ["OK", "EXITO", "COMPLETADO"],
  "expected_fields": {
    "datosSolicitados": null
  }
}
## Ejemplo 3: Validación con Múltiples Rutas
Para servicios que pueden tener estructuras de respuesta variables:
{
  "success_field": "codMensaje",
  "success_values": ["00000"],
  "alternative_paths": [
    {
      "field": "cabecera.estado",
      "success_values": ["CORRECTO"]
    },
    {
      "field": "response.status",
      "success_values": ["200", "OK"]
    }
  ],
  "validation_strategy": "flexible"
}

Ultimos cambios que realizamos de tecnicas avanzadas
Estrategias Avanzadas para Validación Flexible de Respuestas SOAP
Análisis de Requerimientos
Has planteado dos escenarios clave que requieren mayor flexibilidad en la validación de respuestas SOAP:

Ignorar códigos específicos: Necesitas que ciertos códigos de mensaje (como "2001") se traten como advertencias, no como errores.
Adaptabilidad a diferentes estructuras: Algunos servicios podrían utilizar campos distintos a codMensaje o valores diferentes a "0000" para indicar éxito.

Estas necesidades plantean un requerimiento de diseño más sofisticado para el sistema de validación, orientado a reglas configurables por servicio.
Arquitectura de Solución Propuesta
Implementaré un sistema de validación basado en reglas con la flexibilidad de definir diferentes estrategias por servicio. Esta arquitectura consta de:

Esquema de configuración extensible
Motor de reglas de validación
Estrategias personalizables por servicio
Sistema de clasificación de respuestas (éxito/error/advertencia)

Implementación Detallada
## 1. Mejora del Esquema de Validación
Primero, expandiremos el formato de validation_pattern para soportar reglas más complejas:
# Ejemplo de estructura mejorada:
validation_schema = {
    # Configuración general
    "success_field": "codMensaje",  # Campo que indica éxito/error
    "success_values": ["00000"],    # Valores que indican éxito
    "warning_values": ["2001"],     # Valores que se tratan como advertencia
    
    # Campos opcionales a verificar en respuesta exitosa
    "expected_fields": {
        "fechaProximoCorte": None,  # Solo verifica existencia
        "puntosDisponibles": None   # Solo verifica existencia
    },
    
    # Configuración alternativa (otras rutas de validación)
    "alternative_paths": [
        {
            "field": "response.status",
            "success_values": ["OK", "SUCCESS"]
        }
    ],
    
    # Configuración avanzada
    "validation_strategy": "flexible",  # strict, flexible, permissive
    "treat_empty_as_success": false     # Considerar respuesta vacía como éxito
}
Consideraciones Técnicas
## 1. Retrocompatibilidad
La implementación mantiene compatibilidad con el formato simple {"status": "ok"} para no romper configuraciones existentes.
## 2. Rendimiento
La validación flexible implica más comprobaciones, pero el impacto en rendimiento es mínimo ya que:

Se utiliza un diccionario aplanado para búsquedas O(1)
Las validaciones se ejecutan secuencialmente hasta encontrar coincidencia
La caché de respuestas aplanadas evita reprocesamiento

## 3. Extensibilidad
El diseño permite añadir nuevas estrategias y reglas de validación sin modificar la estructura base:
pythonCopiar# Ejemplo de extensión futura: validación con expresiones regulares
if validation_schema.get("use_regex", False):
    import re
    pattern = validation_schema.get("regex_pattern")
    field_value_str = str(field_value)
    if pattern and re.match(pattern, field_value_str):
        return True, f"Validación exitosa mediante expresión regular", "success"
## 4. Manejo de Errores
La implementación incluye manejo robusto de errores, con registro detallado y recuperación automática en caso de fallos.
Instrucciones de Implementación

Añadir los métodos de validación avanzada en core/soap_client.py
Actualizar el método de verificación en gui/monitoring_panel.py
Implementar la interfaz de configuración en gui/request_form.py
Añadir soporte visual para el nuevo estado "warning" en todas las vistas

Conclusión
Esta implementación proporciona un sistema de validación altamente flexible y adaptable a diferentes estructuras de respuesta SOAP. Las características principales son:

Reglas personalizables por servicio - Cada servicio puede tener su propia lógica de validación
Soporte para códigos de advertencia - Permite distinguir entre errores y advertencias
Múltiples estrategias de validación - Desde estricta hasta permisiva según necesidades
Rutas alternativas de validación - Para servicios con estructuras variables
Interfaz intuitiva - Plantillas predefinidas para facilitar la configuración

Esta arquitectura no solo resuelve los escenarios planteados, sino que proporciona un marco extensible para manejar prácticamente cualquier tipo de respuesta SOAP que puedas encontrar en entornos empresariales complejos.


Aquí tienes varias opciones de JSON para las validaciones, con diferentes configuraciones según distintos escenarios:
## 1. Configuración básica de éxito/error
{
  "success_field": "codMensaje",
  "success_values": ["00000"],
  "validation_strategy": "flexible"
}
## 2. Configuración con manejo de advertencias
{
  "success_field": "codMensaje",
  "success_values": ["00000"],
  "warning_values": ["2001", "2002", "2003"],
  "validation_strategy": "flexible"
}
## 3. Configuración completa con éxito/advertencia/fallo
{
  "success_field": "codMensaje",
  "success_values": ["00000", "00001"],
  "warning_values": ["2001", "2002", "2003"],
  "failed_values": ["5000", "5001", "9999"],
  "validation_strategy": "flexible"
}
## 4. Validación estricta con campos esperados
{
  "success_field": "codMensaje",
  "success_values": ["00000"],
  "expected_fields": {
    "fechaProximoCorte": null,
    "mensajeUsuario": null
  },
  "validation_strategy": "strict"
}
## 5. Validación con campos esperados y valores específicos
{
  "success_field": "codMensaje",
  "success_values": ["00000"],
  "expected_fields": {
    "estado": "ACTIVO",
    "tipoCliente": "PREFERENCIAL"
  },
  "validation_strategy": "flexible"
}
## 6. Validación de respuestas con estructura XML compleja
{
  "success_field": "Envelope.Body.cabeceraSalida.codMensaje",
  "success_values": ["00000"],
  "warning_values": ["2001"],
  "validation_strategy": "flexible"
}
## 7. Validación para servicios con múltiples rutas de respuesta posibles
{
  "success_field": "codMensaje",
  "success_values": ["00000"],
  "alternative_paths": [
    {
      "field": "cabecera.estado",
      "success_values": ["OK", "CORRECTO"]
    },
    {
      "field": "response.status",
      "success_values": ["200", "OK"]
    }
  ],
  "validation_strategy": "flexible"
}
## 8. Validación para servicios con errores específicos de negocio
{
  "success_field": "codMensaje",
  "success_values": ["00000"],
  "warning_values": ["2001", "2002"],
  "failed_values": ["4001", "4002", "4003", "4004"],
  "expected_fields": {
    "mensajeUsuario": null,
    "codigoOperacion": null
  }
}
## 9. Validación permisiva para servicios poco fiables
{
  "validation_strategy": "permissive",
  "treat_empty_as_success": true,
  "success_field": "codMensaje",
  "success_values": ["00000", "00001", "00002"]
}
## 10. Validación para servicios que retornan listas
{
  "success_field": "cabecera.codMensaje",
  "success_values": ["00000"],
  "expected_fields": {
    "lista.elementos": null,
    "lista.totalRegistros": null
  }
}
## 11. Validación para respuestas con namespace
{
  "success_field": "v1.:codMensaje",
  "success_values": ["00000"],
  "warning_values": ["2001", "2002"],
  "validation_strategy": "flexible"
}
## 12. Validación con enfoque en texto del mensaje de usuario
{
  "success_field": "codMensaje",
  "success_values": ["00000"],
  "expected_fields": {
    "mensajeUsuario": "Operación realizada correctamente"
  },
  "validation_strategy": "flexible"
}
## 13. Validación de servicios de consulta
{
  "success_field": "codMensaje",
  "success_values": ["00000"],
  "warning_values": ["2001"],
  "failed_values": ["3001", "3002"],
  "expected_fields": {
    "resultadoConsulta": null,
    "fechaConsulta": null
  }
}
## 14. Validación específica para servicio ValidarOtp
{
  "success_field": "codMensaje",
  "success_values": ["00000"],
  "warning_values": ["2001"],
  "failed_values": ["5001", "5002", "5003", "5004"],
  "expected_fields": {
    "mensajeUsuario": null
  },
  "validation_strategy": "flexible"
}
## 15. Validación con manejo de texto en XML
{
  "success_field": "codMensaje.#text",
  "success_values": ["00000"],
  "warning_values": ["2001"],
  "validation_strategy": "flexible"
}
Estos ejemplos cubren una amplia variedad de escenarios y te permitirán adaptar las validaciones a las necesidades específicas de cada servicio. Puedes ajustar los valores según los códigos reales que utilicen tus servicios SOAP.