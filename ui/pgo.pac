function FindProxyForURL(url,host) {
  if (dnsDomainIs(host, "pgorelease.nianticlabs.com") || dnsDomainIs(host, "mitm.it"))
    return "PROXY 10.0.1.200:8888";

  return "DIRECT";
}
