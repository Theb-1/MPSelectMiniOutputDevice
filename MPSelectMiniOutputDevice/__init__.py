from . import MPSelectMiniOutputDevicePlugin

from UM.i18n import i18nCatalog
catalog = i18nCatalog("uranium")

def getMetaData():
    return {
        "plugin": {
            "name": catalog.i18nc("@label", "MP Select Mini Output Device"),
            "description": catalog.i18nc("@info:whatsthis", "Enables uploading to the MonoPrice Select Mini 3D's http server."),
            "author": "Ryan Tyler",
            "version": "1.0",
            "api": 3,
        }
    }

def register(app):
    return { "output_device": MPSelectMiniOutputDevicePlugin.MPSelectMiniOutputDevicePlugin() }
