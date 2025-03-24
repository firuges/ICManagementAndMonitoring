def validate_endpoint_url(url: str, timeout: int = 5) -> bool:
    """
    Verifica si un endpoint (WSDL o REST) es accesible.
    
    Args:
        url: URL a verificar
        timeout: Tiempo máximo de espera en segundos
        
    Returns:
        True si la URL es accesible
    """
    try:
        import requests
        from urllib.parse import urlparse
        
        # Verificar formato básico de URL
        parsed = urlparse(url)
        if not all([parsed.scheme, parsed.netloc]):
            return False
        
        # Intentar HEAD primero
        try:
            response = requests.head(url, timeout=timeout, verify=False)
            if response.status_code < 400:
                return True
        except:
            pass  # Continuar con GET si HEAD falla
            
        # Intentar GET
        response = requests.get(url, timeout=timeout, verify=False)
        return response.status_code < 400
        
    except Exception as e:
        logging.warning(f"Error validando URL {url}: {str(e)}")
        return False