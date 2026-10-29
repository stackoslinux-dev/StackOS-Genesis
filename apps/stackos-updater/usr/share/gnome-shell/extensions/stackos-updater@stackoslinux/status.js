// Estado visual do indicador. Nunca considera um cache ausente como atualizado.
export function indicatorState(data) {
    if (!data || typeof data !== 'object' || !Array.isArray(data.packages))
        return ['yellow', 'Ainda não verificado'];
    if (data.service_error) return ['red', 'Erro na verificação'];
    if (data.reboot_required) return ['red', 'Reinicialização necessária'];
    const count = data.packages.length;
    const critical = Math.max(Number(data.critical_count) || 0,
        data.packages.filter(p => p && p.critical).length);
    if (critical > 0 || data.status === 'red')
        return ['red', `${critical} atualização(ões) de segurança/crítica(s)`];
    if (!data.checked_at) return ['yellow', 'Ainda não verificado'];
    if (count > 0) return ['yellow', `${count} atualização(ões) disponível(is)`];
    if (Array.isArray(data.blocked) && data.blocked.length)
        return ['yellow', `${data.blocked.length} pacote(s) bloqueado(s)`];
    if (data.status && data.status !== 'green') return ['yellow', 'Verificação pendente'];
    return ['green', 'Sistema atualizado'];
}
