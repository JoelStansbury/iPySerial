import time
import threading
import sys

from serial import Serial # pyserial
from serial.tools.list_ports import comports
from serial.tools.list_ports_common import ListPortInfo
import ipywidgets as ipyw
from traitlets import observe, Instance, link, Unicode

UNIX = sys.platform in ["linux", "darwin"]
WIN = sys.platform == "win"

STYLE = ipyw.HTML("""
<style>
.ipyserial-output-textbox-outter {
    max-height:400px;
    height: 400px;
    overflow-x: scroll;
    flex: end;
    flex-direction: column-reverse;
    width: 95%;
    border: 1px solid black;
}
.ipyserial-output-textbox-inner {
    height: fit-content;
    p {
        margin-top: -6px;
        margin-bottom: -6px;
    }
}
.ipyserial-input {
    width: 95%;
}        
</style>
""")

class UpdatePorts(threading.Thread):
    """
    Handles the continuous pinging of serial ports required to detect
    new connections.
    """
    def __init__(self, parent, on_error, polling_interval=1):
        """
        args:
            on_error <function>: What to do in the event of an error.
                Currently, this is only used to update the "Begin Stream" 
                button to reflect the fact that the stream is no longer 
                in progress.
        """
        threading.Thread.__init__(self)
        self.event = threading.Event()
        self.on_error = on_error
        self.parent = parent
        self.polling_interval = polling_interval
        
    def stop(self):
        self.event.set()
        
    def run(self):
        try:
            while True:
                self.parent.options = list(comports())
                time.sleep(self.polling_interval)
        except Exception as e:
            self.on_error()
            raise e


class SerialReader(threading.Thread):
    def __init__(self, device, pipe, on_error, polling_interval=0.001):
        """
        args:
            on_error <function>: What to do in the event of an error.
                Currently, this is only used to update the "Begin Stream" 
                button to reflect the fact that the stream is no longer 
                in progress.
        """
        threading.Thread.__init__(self)
        self.event = threading.Event()
        self.device = device
        self.polling_interval = polling_interval
        self.pipe = pipe
        self.on_error = on_error
        
    def stop(self):
        self.event.set()
        
    def run(self):
        try:
            while not self.event.is_set():
                res = self.device.readline()
                if res:
                    self.pipe(res.decode("utf-8"))
                time.sleep(self.polling_interval)
        except Exception as e:
            self.on_error(e)
            raise e


class Output(ipyw.VBox):
    value = Unicode()
    def __init__(self):
        super().__init__()

        self.listener = None
        self.disabled=True
        outter = ipyw.HTML().add_class("ipyserial-output-textbox-inner")
        link((outter, "value"),(self, "value"))
        self.children = [outter]
        self.add_class("ipyserial-output-textbox-outter")

    def start(self, device):
        self.value = ""
        if self.listener is not None:
            self.listener.stop()

        self.listener = SerialReader(
            device=device, 
            pipe=self.pipe,
            on_error=self.read_error,
        )
        self.listener.start()

    def read_error(self,e):
        self.value =  f"{self.value}<p>**Serial reader crash!\n\n {e}</p>"
    
    def stop(self):
        if self.listener is not None:
            self.listener.stop()

    def pipe(self, msg, color="black"):
        self.value = f"{self.value}<p style='color:{color}'>{msg}</p>"


class SerialBridge(ipyw.VBox):
    """
    Provides an interface to safely connect and disconnect from serial ports.
    Useful for Arduino GUIs. Allows the user to select the COM port,
    Connect/Disconnect python from the port (freeing it up for code push via ArduinoIDE).
    Connect programatically via SerialBridge.connect(port=None, serial_number=None)
    pecify Serial Number of a specific board.
    """

    port = Instance(klass="serial.tools.list_ports_common.ListPortInfo", allow_none=True)
    inp = Unicode()
    def __init__(
        self, 
        baudrate=False,
        port=None,
        serial_number=None,
        auto_connect=False,
        auto_disconnect=True,
        auto_refresh_ports=True,
        eof="\n",
        ):
        self.auto_disconnect = auto_disconnect
        self.eof=eof
        super().__init__(_view_count=0)

        # Port Selector
        widgets = []
        self.port_selector = ipyw.Dropdown(description="Port:")
        widgets.append(self.port_selector)
        
        # Baudrate Selector
        valid_baudrates=[
            300,600,1200,2400,4800,9600,14400,19200,28800,38400,
            57600,115200,230400,460800,921600,1843200,3000000,
            3686400
        ]
        if not baudrate in valid_baudrates:
            valid_baudrates.append(baudrate)
        self.bd = ipyw.Dropdown(
            description="Baud Rate:",
            options=valid_baudrates,
            value = baudrate or 9600
        )
        widgets.append(self.bd)
        

        # Refresh Button
        self.auto_refresh_ports = auto_refresh_ports
        if auto_refresh_ports:
            self.begin_refresh_loop()
        else:
            refresh_ports_btn = ipyw.Button(icon="refresh")
            refresh_ports_btn.layout.width="50px"
            refresh_ports_btn.on_click(self.refresh_available_ports)
            widgets.append(refresh_ports_btn)

        # Connect Button
        self.connect_btn = ipyw.Button(
            description="Connect",
            tooltip="Attempts to open the selected serial port",
            icon="sign-in"
        )
        self.connect_btn.on_click(self.connect)
        widgets.append(self.connect_btn)


        self.port_selector.layout.width="400px"
        self.bd.layout.width="180px"
        self.connect_btn.layout.width="110px"

        self.device = None
        self.is_open = False

        self.output_stream = Output()
        self.input_text_box = ipyw.Text().add_class("ipyserial-input")
        self.input_text_box.on_submit(self._manual_input)
        link(
            source=(self.input_text_box,"value"),
            target=(self,"inp")
        )
        

        top = ipyw.HBox(widgets)
        self.children = [top, self.output_stream, self.input_text_box, STYLE]
        
        # Settings
        self.refresh_available_ports()
        if serial_number:
            valid = [
                p for p in self.port_selector.options
                if p.serial_number == serial_number
            ]
            assert valid, f"No device with SN: {serial_number}"
            self.port_selector.value=valid[0]

        elif port:
            valid = [
                p for p in self.port_selector.options
                if p.name == port
            ]
            assert valid, f"{port} not found."
            self.port_selector.value=valid[0]

        link(
            source=(self.port_selector,"value"),
            target=(self,"port"),
        )
        if auto_connect:
            self.connect()

    def _manual_input(self, src):
        self.device.write(bytes(f"{src.value.upper()}{self.eof}","utf-8"))
        self.output_stream.pipe(src.value, color="darkgreen")
        src.value=""
        
    def refresh_available_ports(self, _=None):
        self.port_selector.options = list(comports())
    
    def begin_refresh_loop(self):
        self.port_updater = UpdatePorts(
            parent = self.port_selector,
            on_error = self.begin_refresh_loop
            )
        self.port_updater.start()

    def connect(self, port=None, serial_number=None):
        # Use serial number if provided
        if UNIX:
            if serial_number:
                for p in self.port_selector.options:
                    if isinstance(p, ListPortInfo) and p.serial_number==serial_number:
                        port = f"/dev/{p.name}"
                        break
                else:
                    raise LookupError("Serial Number not found")
            # If this function was initiated by a button click
            elif not isinstance(serial_number,str):
                port = f"/dev/{self.port_selector.value.name}"
        elif WIN:
            if serial_number:
                for p in self.port_selector.options:
                    if isinstance(p, ListPortInfo) and p.serial_number==serial_number:
                        port = p.name
                        break
                else:
                    raise LookupError("Serial Number not found")
            # If this function was initiated by a button click
            elif not isinstance(serial_number,str):
                port = self.port_selector.value.name
        
        if self.device and self.device.is_open:
            self.device.close()
        if self.is_open:
            self.is_open = False
            self.port_selector.disabled = False
            self.bd.disabled = False
            self.connect_btn.description = "Connect"
            self.connect_btn.icon = "sign-in"
            return
        
        
        self.device = Serial(
            port=port,
            baudrate=self.bd.value, 
            timeout=.1
        )
        self.output_stream.start(self.device)
        self.port_selector.disabled = True
        self.bd.disabled = True
        self.connect_btn.icon = "sign-out"
        self.connect_btn.description = "Disconnect"
        self.is_open = True

    def close(self):
        if self.auto_refresh_ports:
            self.port_updater.stop()
        self.device.close()
        self.output_stream.close()
        self.is_open = False

    @observe("port")
    def _port_change(self, change):
        if self.is_open:
            if self.device.is_open:
                return
            self.output_stream.close()
            self.is_open = False
            self.port_selector.disabled = False
            self.bd.disabled = False
            self.connect_btn.description = "Connect"
            self.connect_btn.icon = "sign-in"
            

    @observe("_view_count")
    def _check_visibility(self, change):
        """
        Makeshift Deconstructor: Closes the serial connection on deletion

        __del__ doesn't work for widgets so this is the workaround.
        All widgets have a trait called `_view_count` which is None
        by default (not tracking). If we set it to 0 (as we have in 
        the __init__'s `super().__init__()`), then it will start 
        tracking how many copies of this instance are being displayed
        at the moment.
        """
        if self.auto_disconnect and change["old"]!=None and change["new"]==0:
            self.close()
