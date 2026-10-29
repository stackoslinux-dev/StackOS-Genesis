"""Regras de apresentação; não alteram a política de pacotes do helper."""
def validate(data):
    if not isinstance(data, dict) or not isinstance(data.get('packages'), list):
        raise ValueError('Resposta sem lista de pacotes válida.')
    if not isinstance(data.get('blocked', []), list):
        raise ValueError('Lista de bloqueios inválida.')
    if any(not isinstance(p, dict) or not isinstance(p.get('name'), str) for p in data['packages'] + data.get('blocked', [])):
        raise ValueError('Pacote inválido na resposta.')
    result = dict(data)
    result['count'] = len(data['packages'])
    result['critical_count'] = sum(bool(p.get('critical')) for p in data['packages'])
    result['status'] = status(result)
    return result

def status(data):
    if data.get('service_error') or data.get('reboot_required') or data.get('critical_count', 0) or any(p.get('critical') for p in data.get('packages', [])):
        return 'red'
    if data.get('packages') or data.get('blocked') or not data.get('checked_at'):
        return 'yellow'
    return 'green'

def filtered(packages, query='', mode='all'):
    query = query.casefold().strip()
    return [p for p in packages if (not query or query in (p.get('name','')+' '+p.get('description','')).casefold()) and (mode!='critical' or p.get('critical'))]
