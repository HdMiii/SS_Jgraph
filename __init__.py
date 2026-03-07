def classFactory(iface):
    from .jgraph_plugin import JGraphPlugin
    return JGraphPlugin(iface)


def serverClassFactory(serverIface):
    from .jgraph_plugin import JGraphPlugin
    return JGraphPlugin(serverIface)
