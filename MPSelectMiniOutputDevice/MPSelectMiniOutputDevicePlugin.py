import io
import socket

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices

from UM.Application import Application
from UM.Preferences import Preferences
from UM.Logger import Logger
from UM.Mesh.MeshWriter import MeshWriter
from UM.Message import Message
from UM.OutputDevice.OutputDevicePlugin import OutputDevicePlugin
from UM.OutputDevice.OutputDevice import OutputDevice
from UM.OutputDevice import OutputDeviceError

from UM.i18n import i18nCatalog
catalog = i18nCatalog("uranium")

# You can set the 'ip' and 'start_print' settings under [MPSelectMini] in cura.cfg
# Alternatively, you can uncomment and use the variables below:
#ip = '0.0.0.0'
#start_print = True

class MPSelectMiniOutputDevicePlugin(OutputDevicePlugin):
    def __init__(self):
        super().__init__()

        Preferences.getInstance().addPreference("MPSelectMini/ip", "")
        Preferences.getInstance().addPreference("MPSelectMini/start_print", "")

    def start(self):
        self.getOutputDeviceManager().addOutputDevice(MPSelectMiniOutputDevice())

    def stop(self):
        self.getOutputDeviceManager().removeOutputDevice("MPSelectMini")

class MPSelectMiniOutputDevice(OutputDevice):
    def __init__(self):
        super().__init__("MPSelectMini")

        self.setName(catalog.i18nc("@item:inmenu", "MP Select Mini"))
        self.setShortDescription(catalog.i18nc("@action:button", "Send to MP Select Mini"))
        self.setDescription(catalog.i18nc("@info:tooltip", "Send to MP Select Mini"))
        self.setIconName("save")

        self._writing = False

    def requestWrite(self, node, file_name = None, filter_by_machine = False):
        if self._writing:
            raise OutputDeviceError.DeviceBusyError()

        self._writing = True
        
        # load settings
        if Preferences.getInstance().getValue("MPSelectMini/ip"):
            ip = Preferences.getInstance().getValue("MPSelectMini/ip")
        if Preferences.getInstance().getValue("MPSelectMini/start_print"):
            start_print = Preferences.getInstance().getValue("MPSelectMini/start_print")

        try:
            start_print
        except NameError:
            start_print = False

        # check for valid ip
        if not ip:
            raise OutputDeviceError.WriteRequestFailedError(catalog.i18nc("@info:status", "Invalid IP"))        
        
        # Get GCode
        file_formats = Application.getInstance().getMeshFileHandler().getSupportedFileTypesWrite()
        mesh_writer = Application.getInstance().getMeshFileHandler().getWriterByMimeType("text/x-gcode")
        stream = io.StringIO()

        mesh_writer.write(stream, node, MeshWriter.OutputMode.TextMode)
        gcode = stream.getvalue()

        try:
            # Upload GCode
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((ip, 80))
            s.send(bytes('POST /upload HTTP/1.1\r\n', 'ascii'))
            s.send(bytes('Content-Type: multipart/form-data; boundary=------------------------2d30fc993bb09c6a\r\n', 'ascii'))
            s.send(bytes('\r\n', 'ascii'))
            s.send(bytes('--------------------------2d30fc993bb09c6a\r\n', 'ascii'))
            s.send(bytes('Content-Disposition: form-data; name="filedata"; filename="cache.gc"\r\n', 'ascii'))
            s.send(bytes('Content-Type: application/octet-stream\r\n', 'ascii'))
            s.send(bytes('\r\n', 'ascii'))
            s.send(bytes(gcode, 'ascii'))
            s.send(bytes('\r\n', 'ascii'))
            s.send(bytes('--------------------------2d30fc993bb09c6a--\r\n', 'ascii'))
            response = str(s.recv(1024), 'ascii')
            s.close()

            # Check upload response
            if response.startswith('HTTP/1.1 200 OK'):
                message = Message(catalog.i18nc("@info:status", "Upload Success"))
                message.show()
            else:
                Logger.log("e", "Invalid http response uploading gcode:\n" + response)
                raise OutputDeviceError.WriteRequestFailedError(catalog.i18nc("@info:status", "Upload Failed"))

            # Send cancel print (prevents upload bug where printer will start before heating extruder)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((ip, 80))
            s.send(bytes('GET /set?cmd={P:X} HTTP/1.1\r\n', 'ascii'))
            s.send(bytes('\r\n', 'ascii'))
            response = str(s.recv(1024), 'ascii')
            s.close()

            if start_print:
                # Send start print
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((ip, 80))
                s.send(bytes('GET /set?code=M565 HTTP/1.1\r\n', 'ascii'))
                s.send(bytes('\r\n', 'ascii'))
                response = str(s.recv(1024), 'ascii')
                s.close()

                # Check start print response
                if response.startswith('HTTP/1.1 200 OK'):
                    message = Message(catalog.i18nc("@info:status", "<b>Printing Started</b>"))
                    message.show()
                else:
                    Logger.log("e", "Invalid http response starting print job:\n" + response)
                    raise OutputDeviceError.WriteRequestFailedError(catalog.i18nc("@info:status", "Start Print Failed"))

        except (TimeoutError):
            raise OutputDeviceError.WriteRequestFailedError(catalog.i18nc("@info:status", "Connection Timeout"))
                
        self._writing = False