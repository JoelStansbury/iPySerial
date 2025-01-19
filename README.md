# iPySerial
Interactive widget for connecting to serial devices such as an Arduino inside of jupyterlab or a jupyter notebook.

## Features
* Dropdown for available ports (updates once a second)
* Dropdown for selecting baudrate
* Connect/Disconnect button
* Text field for manual input (`Enter` to send)
* Text area for Output (Continuously listens for messages sent from the Arduino via `Serial.print`)

![image](https://github.com/user-attachments/assets/53569290-2c75-4151-a9be-59644de9fbe8)


* The `Serial` object is stored in `SerialBridge().device`
