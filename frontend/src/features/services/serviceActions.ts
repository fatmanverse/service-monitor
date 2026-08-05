import type { ProbeResult, Service } from '../../types'


export function attachProbeNames(result: ProbeResult, service: Service): ProbeResult {
  const names = new Map(service.probes.map((probe) => [probe.key, probe.name]))
  return {
    ...result,
    probes: result.probes.map((probe) => ({
      ...probe,
      name: probe.name || names.get(probe.key) || probe.key,
    })),
  }
}


export function canOfferRestart(result: ProbeResult, service: Service, isAdmin: boolean) {
  return result.success === false && isAdmin && Boolean(service.start_command)
}
