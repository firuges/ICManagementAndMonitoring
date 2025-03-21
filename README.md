# Monitor de Servicios SOAP

Una aplicación de gestión y monitoreo de servicios SOAP con interfaz gráfica, validación de respuestas, notificaciones por correo electrónico y programación de tareas.

## Características Principales

- **Gestión de Servicios SOAP**: Crear, editar y gestionar múltiples servicios SOAP.
- **Monitoreo Continuo**: Verificar periódicamente el estado de los servicios.
- **Validación de Respuestas**: Definir patrones de validación para verificar respuestas.
- **Notificaciones por Email**: Envío automático de alertas ante fallos.
- **Programación de Tareas**: Integración con el programador del sistema operativo.
- **Interfaz Gráfica Intuitiva**: Gestión visual de todos los servicios.
- **Modo Headless**: Ejecución desde línea de comandos sin interfaz gráfica.

## Requisitos

- Python 3.7 o superior
- PyQt5
- Zeep (Cliente SOAP)
- Bibliotecas adicionales (ver `requirements.txt`)

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

## Guía de Usuario

### 1. Gestión de Requests SOAP

Para crear un nuevo request SOAP:

1. Ir a la pestaña "Gestión de Requests"
2. Completar los campos:
   - **Nombre**: Identificador descriptivo del servicio
   - **Descripción**: Detalle del propósito del servicio
   - **URL WSDL**: Dirección del WSDL del servicio
   - **Request XML**: Estructura XML del request SOAP
   - **Patrones de Validación**: Reglas para validar respuestas (formato JSON)
3. Configurar opciones de monitoreo:
   - **Intervalo**: Frecuencia de verificación en minutos
   - **Activar monitoreo**: Habilitar verificación automática
4. Hacer clic en "Guardar"

### 2. Configuración de Notificaciones

Para configurar las notificaciones por email:

1. Ir a la pestaña "Configuración de Notificaciones"
2. Completar la configuración SMTP:
   - **Servidor SMTP**: Dirección del servidor de correo
   - **Puerto**: Puerto de conexión (normalmente 587 para TLS)
   - **Usuario y Contraseña**: Credenciales de acceso
3. Añadir destinatarios de correo electrónico
4. Configurar opciones de notificación:
   - **Notificar errores de conexión**: Alertar problemas de conectividad
   - **Notificar errores de validación**: Alertar respuestas incorrectas
5. Hacer clic en "Guardar configuración"

### 3. Monitoreo de Servicios

La pestaña "Monitoreo" muestra:

- **Tabla de Servicios**: Lista de todos los servicios configurados
- **Detalles del Servicio**: Información detallada del servicio seleccionado
- **Última Respuesta**: Contenido de la última respuesta recibida
- **Log de Eventos**: Registro de actividades y errores

Funciones disponibles:
- **Verificar**: Comprobar un servicio específico
- **Verificar Todos**: Comprobar todos los servicios
- **Actualizar**: Refrescar la lista de servicios

## Estructura del Proyecto

```
soap_monitor/
│
├── app.py                  # Punto de entrada de la aplicación
├── requirements.txt        # Dependencias
│
├── core/                   # Componentes del núcleo
│   ├── persistence.py      # Gestión de archivos JSON
│   ├── soap_client.py      # Cliente SOAP y validación
│   ├── notification.py     # Sistema de notificaciones
│   ├── scheduler.py        # Programador de tareas
│   └── monitor.py          # Script de monitoreo independiente
│
├── gui/                    # Componentes de interfaz gráfica
│   ├── main_window.py      # Ventana principal
│   ├── request_form.py     # Formulario de requests
│   ├── email_form.py       # Formulario de emails
│   └── monitoring_panel.py # Panel de monitoreo
│
├── data/                   # Almacenamiento de datos
│   ├── requests/           # Requests individuales (JSON)
│   ├── email_config.json   # Configuración de destinatarios
│   └── smtp_config.json    # Configuración SMTP
│
├── logs/                   # Registros de la aplicación
│
└── examples/               # Scripts de ejemplo
    └── create_ejectransfinter_request.py  # Creación de request de ejemplo
```

## Configuración de Patrones de Validación

Los patrones de validación permiten verificar si la respuesta del servicio es correcta. Se definen en formato JSON:

```json
{
  "campo.anidado": "valor_esperado",
  "otro_campo": null
}
```

Donde:
- `"campo.anidado": "valor_esperado"`: Verifica que el campo exista y tenga el valor exacto.
- `"otro_campo": null`: Verifica únicamente que el campo exista.

## Integración con el Sistema de Tareas

La aplicación puede registrar tareas en el programador del sistema operativo:

- En Windows: Usa el programador de tareas (Task Scheduler)
- En Linux/Unix: Usa crontab

Para activar esta función, marque la opción "Añadir al programador de tareas del sistema" al crear o editar un request.

## Solución de Problemas

### Errores de Conexión SMTP

1. Verifique que el servidor SMTP esté correctamente configurado
2. Si usa Gmail, habilite "Acceso de aplicaciones menos seguras" o use una "Contraseña de aplicación"

### Errores en Servicios SOAP

1. Verifique que la URL del WSDL sea accesible
2. Compruebe que el formato del XML sea correcto
3. Verifique que los namespaces sean correctos

### Problemas con la Validación

1. Revise que el formato JSON de los patrones de validación sea correcto
2. Use el botón "Probar Request" para verificar manualmente la respuesta

## Licencia

[MIT License](LICENSE)

## Contacto

Para soporte o consultas:
- Email: soporte@ejemplo.com
- Repositorio: https://github.com/username/soap-monitor



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



Ejemplo Incluido
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
Ejemplo 1: Validación con Advertencias
Para un servicio que considera "2001" como advertencia y no como error:
jsonCopiar{
  "success_field": "codMensaje",
  "success_values": ["00000"],
  "warning_values": ["2001"],
  "expected_fields": {
    "fechaProximoCorte": null
  },
  "validation_strategy": "flexible"
}
Ejemplo 2: Validación con Campo Alternativo
Para un servicio que usa un campo diferente para indicar éxito:
jsonCopiar{
  "success_field": "estadoRespuesta",
  "success_values": ["OK", "EXITO", "COMPLETADO"],
  "expected_fields": {
    "datosSolicitados": null
  }
}
Ejemplo 3: Validación con Múltiples Rutas
Para servicios que pueden tener estructuras de respuesta variables:
jsonCopiar{
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
1. Mejora del Esquema de Validación
Primero, expandiremos el formato de validation_pattern para soportar reglas más complejas:
pythonCopiar# Ejemplo de estructura mejorada:
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
1. Retrocompatibilidad
La implementación mantiene compatibilidad con el formato simple {"status": "ok"} para no romper configuraciones existentes.
2. Rendimiento
La validación flexible implica más comprobaciones, pero el impacto en rendimiento es mínimo ya que:

Se utiliza un diccionario aplanado para búsquedas O(1)
Las validaciones se ejecutan secuencialmente hasta encontrar coincidencia
La caché de respuestas aplanadas evita reprocesamiento

3. Extensibilidad
El diseño permite añadir nuevas estrategias y reglas de validación sin modificar la estructura base:
pythonCopiar# Ejemplo de extensión futura: validación con expresiones regulares
if validation_schema.get("use_regex", False):
    import re
    pattern = validation_schema.get("regex_pattern")
    field_value_str = str(field_value)
    if pattern and re.match(pattern, field_value_str):
        return True, f"Validación exitosa mediante expresión regular", "success"
4. Manejo de Errores
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