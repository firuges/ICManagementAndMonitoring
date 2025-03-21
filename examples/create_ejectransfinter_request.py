#!/usr/bin/env python
"""
Script de ejemplo para crear un Request SOAP para el servicio EjecTransfInter

Este script crea automáticamente un archivo JSON con la configuración de monitoreo
para el servicio EjecTransfInter, basado en el XML WSDL proporcionado.
"""

import os
import sys
import json
import logging
from datetime import datetime

# Configurar directorio raíz
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# Importar módulos de la aplicación
from core.persistence import PersistenceManager

# XML de ejemplo para el request
EXAMPLE_REQUEST_XML = '''
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ns1:EjecTransfInterRequest xmlns:ns1="http://xmlns.bancocajasocial.com/co/canales/schema/servicios/EjecTransfInter/v1.0">
      <ns1:cabeceraEntrada>
        <ns2:invocador xmlns:ns2="http://xmlns.bancocajasocial.com/co/canales/schema/servicios/CabeceraBanca/v2.0">
          <ns2:canalOrigen>WEB</ns2:canalOrigen>
          <ns2:codigoATM>001</ns2:codigoATM>
          <ns2:codigoOficina>001</ns2:codigoOficina>
          <ns2:codigoTerminal>001</ns2:codigoTerminal>
          <ns2:direccionIpCliente>127.0.0.1</ns2:direccionIpCliente>
          <ns2:direccionIpServidor>127.0.0.1</ns2:direccionIpServidor>
          <ns2:direccionMacCliente>00:00:00:00:00:00</ns2:direccionMacCliente>
          <ns2:direccionMacServidor>00:00:00:00:00:00</ns2:direccionMacServidor>
          <ns2:llaveSesion>SESSION123456</ns2:llaveSesion>
          <ns2:pais>CO</ns2:pais>
          <ns2:procesoId>PROC001</ns2:procesoId>
          <ns2:red>RED001</ns2:red>
          <ns2:subcanal>01</ns2:subcanal>
          <ns2:usuario>USUARIO001</ns2:usuario>
        </ns2:invocador>
      </ns1:cabeceraEntrada>
      <ns1:identificadorProductoBanco>001001001</ns1:identificadorProductoBanco>
      <ns1:numeroCuentaCredito>9876543210</ns1:numeroCuentaCredito>
      <ns1:tipoProductoCredito>AHO</ns1:tipoProductoCredito>
      <ns1:bancoCuentaCredito>001</ns1:bancoCuentaCredito>
      <ns1:nombreBeneficiarioCuentaCredito>Juan Pérez</ns1:nombreBeneficiarioCuentaCredito>
      <ns1:tipoDocumentoBeneficiarioCuentaCredito>CC</ns1:tipoDocumentoBeneficiarioCuentaCredito>
      <ns1:documentoBeneficiarioCuentaCredito>1234567890</ns1:documentoBeneficiarioCuentaCredito>
      <ns1:monto>1000.00</ns1:monto>
      <ns1:valorComision>0.00</ns1:valorComision>
      <ns1:concepto>Transferencia de prueba</ns1:concepto>
    </ns1:EjecTransfInterRequest>
  </soap:Body>
</soap:Envelope>
'''

# Patrón de validación para la respuesta
VALIDATION_PATTERN = {
    "idAutorización": None,  # Verificar que exista el campo
    "cabeceraSalida.codMensaje": "00"  # Verificar que el código sea 00 (éxito)
}

def create_ejectransfinter_request():
    """Crea un request para el servicio EjecTransfInter"""
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('example')
    
    try:
        # Inicializar gestor de persistencia
        persistence = PersistenceManager()
        
        # Crear datos del request
        request_data = {
            'name': 'EjecTransfInter',
            'description': 'Servicio de Ejecución de Transferencias Interbancarias',
            'wsdl_url': 'http://192.168.64.82:8080/canales/EjecTransfInter/v1?wsdl',
            'request_xml': EXAMPLE_REQUEST_XML,
            'validation_pattern': VALIDATION_PATTERN,
            'monitor_interval': 15,
            'monitor_enabled': True,
            'add_to_system': False,
            'status': 'active',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Guardar request
        file_path = persistence.save_soap_request(request_data)
        
        logger.info(f"Request EjecTransfInter creado correctamente: {file_path}")
        print(f"Request EjecTransfInter creado correctamente: {file_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error al crear request: {str(e)}")
        print(f"Error al crear request: {str(e)}")
        return False

if __name__ == "__main__":
    create_ejectransfinter_request()