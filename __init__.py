def classFactory(iface):
    from .jgraph_plugin import JGraphPlugin
    return JGraphPlugin(iface)
