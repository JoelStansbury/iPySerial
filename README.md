# pyserialWidget
Interactive widget for connecting to serial devices such as an Arduino inside of jupyterlab or a jupyter notebook.

## Features
* Dropdown for available ports (updates once a second)
* Dropdown for selecting baudrate
* Connect/Disconnect button
* Text field for manual input (`Enter` to send)
* Text area for Output (Continuously listens for messages sent from the Arduino via `Serial.print`)

![image](https://user-images.githubusercontent.com/48299585/116491322-9b90fb80-a867-11eb-82cd-08488827f9f7.png)
