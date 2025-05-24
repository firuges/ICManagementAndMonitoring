Monitor de Servicios SOAP y REST - Documentación Técnica Avanzada 🚀
Última Actualización: Configuración Avanzada de Tareas Programadas v2.0
Una aplicación empresarial completa para gestión y monitoreo de servicios SOAP/REST con interfaz gráfica responsiva, validación avanzada de respuestas, notificaciones inteligentes por correo electrónico y sistema de programación de tareas con configuración horaria granular.

🎯 Características Principales
Core Funcional

Gestión Dual: Soporte completo para servicios SOAP y REST con validación específica por protocolo
Monitoreo Continuo: Verificación automática con configuración de horarios empresariales
Validación Inteligente: Patrones configurables con soporte para advertencias, fallos y validación flexible
Notificaciones Contextuales: Sistema de alertas por email con adjuntos de diagnóstico completos
Programación Empresarial: Integración avanzada con Task Scheduler (Windows) y crontab (Unix)

Interfaz y Experiencia de Usuario

Diseño Responsivo: Adaptación automática desde pantallas 1366x768 hasta 4K
Configuración Visual: Interfaz intuitiva para horarios de monitoreo empresarial
Diagnóstico Integrado: Herramientas de análisis de conectividad y validación en tiempo real
Modo Headless: Ejecución completa desde línea de comandos para automatización


📋 Requisitos Técnicos
Dependencias del Sistema
bashPython 3.7+ (Recomendado: 3.9+)
PyQt5 >= 5.12.0
Zeep >= 4.0.0 (Cliente SOAP)
Requests >= 2.25.0 (Cliente REST)
XMLtodict >= 0.12.0
Schedule >= 1.1.0
Compatibilidad de Plataforma

✅ Windows 10/11: Task Scheduler con configuración XML avanzada
✅ Linux/Unix: Crontab con scripts de verificación horaria
✅ macOS: Soporte básico con launchd (experimental)


🛠️ Instalación y Configuración
Instalación Estándar
bash# Clonar repositorio
git clone https://github.com/username/soap-rest-monitor.git
cd soap-rest-monitor

# Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
Configuración Inicial
bash# Verificar estructura de directorios
python app.py --check-environment

# Configurar permisos (recomendado ejecutar como administrador)
python app.py --setup-permissions

# Iniciar aplicación
python app.py

🚀 NUEVA FUNCIONALIDAD: Configuración Avanzada de Horarios
Características Empresariales Implementadas
1. Horarios de Negocio Configurables
json{
  "schedule_config": {
    "days_of_week": ["monday", "tuesday", "wednesday", "thursday", "friday"],
    "start_time": "08:00",
    "duration_hours": 11,
    "hidden": true,
    "run_when_logged_off": true,
    "highest_privileges": true
  }
}
2. Tareas del Sistema Optimizadas
Configuración XML Avanzada (Windows Task Scheduler):
xml<CalendarTrigger>
  <StartBoundary>2025-01-20T08:00:00</StartBoundary>
  <ScheduleByWeek>
    <DaysOfWeek>MondayTuesdayWednesdayThursdayFriday</DaysOfWeek>
    <WeeksInterval>1</WeeksInterval>
  </ScheduleByWeek>
  <Repetition>
    <Interval>PT15M</Interval>
    <Duration>PT11H</Duration>
    <StopAtDurationEnd>true</StopAtDurationEnd>
  </Repetition>
</CalendarTrigger>
Configuración de Seguridad Empresarial:

🔒 Tarea Oculta: <Hidden>true</Hidden> - No visible en lista principal
👤 Cuenta SYSTEM: <UserId>S-1-5-18</UserId> - Ejecución sin dependencia de usuario
🛡️ Máximos Privilegios: <RunLevel>HighestAvailable</RunLevel> - Acceso completo al sistema
🔄 Reintentos Automáticos: 3 intentos con intervalos de 1 minuto


📊 Interfaz de Usuario Mejorada
Panel de Configuración de Monitoreo Avanzado
Sección 1: Configuración Básica
┌─ Configuración Básica ─────────────────────────────────┐
│ Intervalo (min): [15▼]  Timeout (seg): [30▼]  Reintentos: [1▼] │
└────────────────────────────────────────────────────────┘
Sección 2: Horarios Empresariales ⭐ NUEVO
┌─ Configuración de Horarios ───────────────────────────┐
│ Hora inicio: [08:00]  Duración (hrs): [11▼]  Fin: 19:00    │
│                                                         │
│ Días activos: ☑Lun ☑Mar ☑Mié ☑Jue ☑Vie ☐Sáb ☐Dom     │
│ [Laborales] [Todos] [Ninguno]                          │
└─────────────────────────────────────────────────────────┘
Sección 3: Opciones de Sistema ⭐ EXPANDIDO
┌─ Configuración de Sistema ────────────────────────────┐
│ ☑ Activar monitoreo automático                        │
│ ☑ Añadir al programador de tareas                     │
│ ☑ Tarea oculta                                        │
│ ☑ Ejecutar sin usuario conectado                      │
│ ☑ Máximos privilegios                                 │
│                                                        │
│ [Verificar Estado] [Exportar Config] [Vista Previa]   │
│                                            ✓ Admin     │
└────────────────────────────────────────────────────────┘
Funcionalidades Interactivas
Vista Previa de Horario 🔍
┌─ Vista Previa del Horario de Monitoreo ─────────────────┐
│                                                          │
│ Configuración General:                                   │
│ • Intervalo: Cada 15 minutos                            │
│ • Horario activo: 08:00 - 19:00                         │
│ • Días: Lunes a Viernes                                 │
│                                                          │
│ Próximas Ejecuciones:                                    │
│ ┌─────────┬───────────────┬──────────────┬──────────────┐ │
│ │   Día   │ Primera Ejec. │ Última Ejec. │ Total Verif. │ │
│ ├─────────┼───────────────┼──────────────┼──────────────┤ │
│ │ Lunes   │     08:00     │    18:45     │      45      │ │
│ │ Martes  │     08:00     │    18:45     │      45      │ │
│ │   ...   │      ...      │     ...      │     ...      │ │
│ └─────────┴───────────────┴──────────────┴──────────────┘ │
└──────────────────────────────────────────────────────────┘
Verificación de Estado ⚡
┌─ Estado de Tarea: NombreServicio ──────────────────────┐
│                                                         │
│ Estado en Sistema: ✓ Existe                           │
│ Tipo de Programación: Semanal                         │
│ Intervalo: Cada 15 minutos                            │
│ Estado Interno: ✓ Programado                          │
│                                                         │
│ Próxima ejecución: Lunes 08:00                        │
│ Última ejecución: Viernes 18:45 (Exitosa)            │
│                                                         │
│ [Actualizar] ──────────────────────────── [Cerrar]    │
└─────────────────────────────────────────────────────────┘

💡 Guías de Uso Avanzado
1. Configuración de Servicios Empresariales
Servicio SOAP con Horario Personalizado
python# Configuración recomendada para entornos productivos
service_config = {
    "name": "ValidacionClientes",
    "type": "SOAP",
    "wsdl_url": "https://api.empresa.com/clientes?wsdl",
    "schedule_config": {
        "days_of_week": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "start_time": "07:30",        # Inicio temprano
        "duration_hours": 12,         # Hasta 19:30
        "hidden": True,               # Oculta para producción
        "run_when_logged_off": True,  # Funcionamiento 24/7
        "highest_privileges": True    # Acceso completo
    },
    "validation_pattern": {
        "success_field": "estadoRespuesta",
        "success_values": ["OK", "EXITOSO"],
        "warning_values": ["PENDIENTE", "EN_PROCESO"],
        "validation_strategy": "flexible"
    }
}
Servicio REST con Configuración de Fin de Semana
python# Monitoreo de sistemas críticos 24/7
critical_service_config = {
    "name": "HealthCheckBaseDatos",
    "type": "REST",
    "url": "https://api.empresa.com/health",
    "method": "GET",
    "schedule_config": {
        "days_of_week": ["saturday", "sunday"],  # Solo fines de semana
        "start_time": "00:00",                   # Todo el día
        "duration_hours": 24,
        "hidden": True,
        "run_when_logged_off": True,
        "highest_privileges": True
    }
}
2. Patrones de Validación Empresarial
Validación Bancaria Compleja
json{
  "success_field": "cabecera.codRespuesta",
  "success_values": ["00000", "00001"],
  "warning_values": ["20001", "20002", "20003"],
  "failed_values": ["50000", "50001", "99999"],
  "expected_fields": {
    "cabecera.fechaOperacion": null,
    "cabecera.numeroTransaccion": null,
    "cuerpo.saldoDisponible": null
  },
  "alternative_paths": [
    {
      "field": "resultado.estado",
      "success_values": ["APROBADO", "EXITOSO"]
    }
  ],
  "validation_strategy": "flexible"
}
Validación REST con Múltiples Criterios
json{
  "success_field": "status",
  "success_values": [200, "OK", "SUCCESS"],
  "warning_values": [202, "ACCEPTED", "PENDING"],
  "expected_fields": {
    "data": null,
    "timestamp": null,
    "correlation_id": null
  },
  "validation_strategy": "strict"
}
3. Configuración de Notificaciones Contextuales
Configuración SMTP Empresarial
json{
  "server": "smtp.empresa.com",
  "port": 587,
  "use_tls": true,
  "username": "monitoreo@empresa.com",
  "password": "password_aplicacion",
  "from_email": "sistemas-monitoreo@empresa.com"
}
Destinatarios por Nivel de Servicio
json{
  "recipients": [
    "equipo-desarrollo@empresa.com",
    "infraestructura@empresa.com",
    "gerencia-ti@empresa.com"
  ],
  "notify_on_error": true,
  "notify_on_validation": true,
  "notify_daily_summary": true
}

🔧 Herramientas de Diagnóstico Avanzado
1. Validación de Configuración
bash# Verificar integridad de servicios
python tools/validation_tester.py "NombreServicio"

# Análisis de consistencia entre validaciones
python tools/validation_parity.py

# Diagnóstico de conectividad avanzado
python tools/connection_diagnostics.py --service "NombreServicio" --full-report
2. Monitoreo de Rendimiento
bash# Estadísticas de ejecución
python tools/performance_monitor.py --days 7

# Análisis de tiempos de respuesta
python tools/response_time_analyzer.py --service "NombreServicio"
3. Exportación de Configuraciones
bash# Exportar todas las configuraciones para backup
python tools/config_exporter.py --output ./backup/

# Importar configuraciones desde backup
python tools/config_importer.py --input ./backup/

📈 Casos de Uso Empresariales
Escenario 1: Institución Financiera
yamlRequerimiento: Monitoreo de servicios críticos durante horario bancario
Configuración:
  - Horario: 06:00 - 22:00 (16 horas)
  - Días: Lunes a Sábado
  - Intervalo: 5 minutos
  - Reintentos: 3
  - Notificaciones: Inmediatas en caso de fallo
Implementación:

192 verificaciones por día por servicio
Notificaciones con adjuntos de diagnóstico completo
Tareas ocultas para evitar interferencia del usuario
Ejecución con máximos privilegios para acceso a logs del sistema

Escenario 2: E-commerce 24/7
yamlRequerimiento: Monitoreo continuo de APIs de pago y inventario
Configuración:
  - Horario: 00:00 - 23:59 (24 horas)
  - Días: Todos los días
  - Intervalo: 2 minutos
  - Escalamiento: Notificaciones progresivas
Implementación:

720 verificaciones por día por servicio
Validación con patrones específicos por tipo de transacción
Integración con sistemas de alerta externos
Backup automático de configuraciones

Escenario 3: Organización Gubernamental
yamlRequerimiento: Monitoreo de servicios ciudadanos con alta disponibilidad
Configuración:
  - Horario: 07:00 - 20:00 (13 horas)
  - Días: Lunes a Viernes
  - Intervalo: 10 minutos
  - Compliance: Logs detallados y auditables
Implementación:

78 verificaciones por día por servicio
Archivos de log estructurados para auditoría
Exportación automática de reportes de disponibilidad
Configuración granular de validaciones por regulaciones


🏗️ Arquitectura Técnica Detallada
Componentes del Sistema
┌─ Capa de Presentación ────────────────────────────────┐
│  PyQt5 UI (Responsiva)                                 │
│  ├─ RequestForm (Configuración avanzada)              │
│  ├─ MonitoringPanel (Dashboard en tiempo real)        │
│  └─ EmailForm (Gestión de notificaciones)             │
└────────────────────────────────────────────────────────┘
┌─ Capa de Lógica de Negocio ───────────────────────────┐
│  ├─ SOAPClient (Zeep + validación avanzada)           │
│  ├─ RESTClient (Requests + Headers configurables)     │
│  ├─ SOAPMonitorScheduler (Task scheduling avanzado)   │
│  └─ EmailNotifier (SMTP + adjuntos contextuales)      │
└────────────────────────────────────────────────────────┘
┌─ Capa de Persistencia ────────────────────────────────┐
│  ├─ PersistenceManager (JSON + integridad)            │
│  ├─ ConfigurationManager (Backup automático)          │
│  └─ LogManager (Logs estructurados)                   │
└────────────────────────────────────────────────────────┘
┌─ Integración del Sistema ─────────────────────────────┐
│  ├─ Windows Task Scheduler (XML avanzado)             │
│  ├─ Unix Crontab (Scripts con validación horaria)     │
│  └─ SMTP Server (Notificaciones empresariales)        │
└────────────────────────────────────────────────────────┘
Flujo de Ejecución Optimizado
mermaidgraph TD
    A[Inicio Aplicación] --> B{Modo de Ejecución}
    B -->|GUI| C[Interfaz Gráfica]
    B -->|Headless| D[Línea de Comandos]
    
    C --> E[Configurar Servicios]
    E --> F[Configurar Horarios]
    F --> G[Crear Tareas del Sistema]
    
    D --> H[Verificar Servicio]
    H --> I{Dentro del Horario?}
    I -->|Sí| J[Ejecutar Verificación]
    I -->|No| K[Finalizar Silenciosamente]
    
    J --> L{Resultado OK?}
    L -->|Sí| M[Actualizar Estado]
    L -->|No| N[Enviar Notificación]
    
    G --> O[Task Scheduler/Crontab]
    O --> P[Ejecución Programada]
    P --> H
    
    N --> Q[Email con Adjuntos]
    M --> R[Log de Éxito]
    Q --> S[Log de Error]

🔐 Consideraciones de Seguridad
Configuración de Permisos
Windows (Recomendaciones de Producción)
xml<!-- Cuenta de servicio con mínimos privilegios necesarios -->
<Principal id="ServiceAccount">
  <UserId>NT AUTHORITY\SYSTEM</UserId>
  <LogonType>ServiceAccount</LogonType>
  <RunLevel>HighestAvailable</RunLevel>
</Principal>

<!-- Configuración de seguridad avanzada -->
<Settings>
  <DisallowStartOnRemoteAppSession>true</DisallowStartOnRemoteAppSession>
  <AllowHardTerminate>false</AllowHardTerminate>
  <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
  <DeleteExpiredTaskAfter>P30D</DeleteExpiredTaskAfter>
</Settings>
Protección de Credenciales

✅ Almacenamiento encriptado de passwords SMTP
✅ Tokens de aplicación en lugar de contraseñas de usuario
✅ Rotación automática de credenciales (configuración manual)
✅ Logs sin exposición de datos sensibles

Hardening del Sistema
bash# Permisos restrictivos en archivos de configuración
chmod 600 data/smtp_config.json
chmod 600 data/email_config.json

# Logs con rotación automática
logrotate /etc/logrotate.d/soap-monitor

# Firewall rules para SMTP saliente únicamente
ufw allow out 587/tcp
ufw allow out 465/tcp

📊 Monitoreo y Métricas
KPIs del Sistema
Disponibilidad de Servicios
python# Métricas automáticas calculadas
availability_metrics = {
    "uptime_percentage": 99.95,
    "total_checks": 10080,        # Checks por semana
    "successful_checks": 10075,
    "failed_checks": 5,
    "average_response_time": "245ms",
    "max_response_time": "1.2s"
}
Eficiencia de Notificaciones
pythonnotification_metrics = {
    "alerts_sent": 12,
    "delivery_success_rate": 100.0,
    "average_delivery_time": "3.2s",
    "escalation_triggered": 2
}
Dashboard de Métricas (Futuras Mejoras)
yamlMétricas Propuestas:
  - Gráficos de tendencia de disponibilidad
  - Heatmap de horarios de mayor actividad
  - Distribución de tipos de error
  - Comparativa de rendimiento por servicio
  - Análisis de patrones de fallo

🚀 Roadmap de Desarrollo
Versión 2.1 (Próxima Release)

 Dashboard Web: Interfaz web complementaria para móviles
 API REST: Endpoints para integración con sistemas externos
 Machine Learning: Detección de anomalías predictivas
 Clustering: Soporte para múltiples instancias coordinadas

Versión 2.2 (Futuro)

 Contenedores: Soporte completo para Docker/Kubernetes
 Métricas Avanzadas: Integración con Prometheus/Grafana
 Autoscaling: Ajuste automático de intervalos según carga
 Blockchain Logging: Logs inmutables para auditoría crítica

Versión 3.0 (Visión a Largo Plazo)

 IA Generativa: Configuración automática de validaciones
 Multi-tenant: Soporte para múltiples organizaciones
 Edge Computing: Distribución de monitoreo en edge nodes
 Quantum-Ready: Preparación para encriptación cuántica


🛠️ Solución de Problemas Avanzada
Diagnóstico de Problemas Comunes
1. Tareas No Se Ejecutan
Síntomas:

Tarea visible en Task Scheduler pero sin ejecuciones
Estado "Listo" pero sin historial

Diagnóstico:
bash# Verificar logs del sistema
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-TaskScheduler/Operational'}

# Verificar permisos
schtasks /query /tn "\SoapRestMonitor\NombreServicio" /v /fo list
Soluciones:

Verificar cuenta de ejecución tiene permisos necesarios
Comprobar que los archivos de la aplicación son accesibles
Validar que las rutas en la configuración XML son correctas
Revisar configuración de red y firewalls

2. Notificaciones No Llegan
Síntomas:

Errores detectados pero sin emails
Logs muestran intentos de envío fallidos

Diagnóstico:
python# Test de conectividad SMTP
python -c "
import smtplib
smtp = smtplib.SMTP('smtp.empresa.com', 587)
smtp.starttls()
smtp.login('usuario', 'password')
print('Conexión SMTP exitosa')
"
Soluciones:

Verificar configuración de firewall para puertos SMTP
Validar credenciales y configuración de autenticación
Comprobar políticas de seguridad del servidor SMTP
Revisar logs de servidor SMTP para bloqueos

3. Validaciones Fallan Incorrectamente
Síntomas:

Servicios funcionando pero marcados como fallidos
Patrones de validación no reconocen respuestas válidas

Diagnóstico:
bash# Análisis detallado de respuesta
python tools/response_analyzer.py "NombreServicio" --verbose

# Test de patrón de validación
python tools/validation_tester.py "NombreServicio" --pattern-debug
Soluciones:

Usar herramienta de diagnóstico integrada para analizar estructura de respuesta
Ajustar patrones de validación con estrategia "flexible"
Implementar rutas alternativas para casos edge
Revisar logs de XML crudo para identificar cambios en formato

Logs de Diagnóstico Avanzado
Estructura de Logs Mejorada
log2025-01-20 08:15:23 [INFO] scheduler - Iniciando verificación programada
2025-01-20 08:15:23 [DEBUG] scheduler - Servicio: ValidacionClientes
2025-01-20 08:15:23 [DEBUG] scheduler - Horario: 08:00-19:00, Día: monday ✓
2025-01-20 08:15:24 [INFO] soap_client - Enviando request a: https://api.empresa.com/clientes?wsdl
2025-01-20 08:15:25 [DEBUG] soap_client - Respuesta recibida: 1.2KB en 1.1s
2025-01-20 08:15:25 [INFO] validation - Validando con patrón: flexible
2025-01-20 08:15:25 [SUCCESS] validation - Campo 'estadoRespuesta': OK ✓
2025-01-20 08:15:25 [INFO] persistence - Estado actualizado: ok
2025-01-20 08:15:25 [DEBUG] scheduler - Próxima ejecución: 08:30:23

📧 Soporte y Contacto
Recursos de Ayuda
Documentación Técnica

📚 Wiki Técnico: Ejemplos detallados y casos de uso
🎥 Video Tutoriales: Configuración paso a paso
📋 FAQ Técnico: Soluciones a problemas comunes
🔧 API Reference: Documentación completa de métodos

Comunidad y Soporte

💬 Foro de Usuarios: Intercambio de experiencias y soluciones
🐛 Issue Tracker: Reporte de bugs y solicitudes de funcionalidades
📊 Roadmap Público: Transparencia en el desarrollo futuro
🤝 Contribuciones: Guías para desarrolladores colaboradores

Contacto Directo

📧 Email Técnico: soporte-tecnico@soap-monitor.com
🚨 Soporte Crítico: urgente@soap-monitor.com (SLA 4h)
📱 Telegram: @SoapMonitorSupport (Horario comercial)


📜 Información Legal y Licencias
Licencia del Software
MIT License

Copyright (c) 2025 SOAP/REST Monitor Development Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

[Texto completo de licencia MIT]
Dependencias y Atribuciones

PyQt5: GPL/Commercial License
Zeep: MIT License
Requests: Apache 2.0 License
Iconografía: Material Design Icons (Apache 2.0)

Cumplimiento Normativo

✅ GDPR: No almacenamiento de datos personales
✅ SOX: Logs auditables y trazabilidad completa
✅ ISO 27001: Prácticas de seguridad implementadas
✅ ITIL: Gestión de servicios empresariales


🏆 Créditos y Reconocimientos
Equipo de Desarrollo Principal

Arquitecto Principal: Diseño de sistema y arquitectura técnica
Desarrollador Senior: Implementación core y optimizaciones
Especialista UI/UX: Diseño responsivo y experiencia de usuario
Especialista DevOps: Integración de sistemas y automatización

Contribuciones de la Comunidad

Beta Testers: Validación en entornos empresariales reales
Traductores: Localización e internacionalización
Documentadores: Mejora continua de documentación técnica


Versión de Documentación: 2.0.1
Última Actualización: 20 de Enero, 2025
Próxima Revisión Programada: 20 de Febrero, 2025

Esta documentación representa el estado actual del sistema SOAP/REST Monitor con las mejoras implementadas en la versión 2.0. Para obtener la información más actualizada, consulte el repositorio oficial y los canales de comunicación del proyecto.