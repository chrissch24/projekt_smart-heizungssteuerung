from pzem import PZEM
from machine import UART, Pin
import time

# UART Kommunikation
uart = UART(2, baudrate=9600, tx=Pin(6), rx=Pin(5))  

# PZEM Initalisieren
sensor_pzem = PZEM(uart=uart, addr=0x05)

# Hauptschleife: Alle 2 Sekunden messen und ausgeben
while True:
    if sensor_pzem.read():
        # Einzelwerte holen
        voltage = sensor_pzem.getVoltage()
        current = sensor_pzem.getCurrent()
        power   = sensor_pzem.getActivePower()

        # Werte ausgeben
        print("Spannung [V]:", voltage)
        print("Strom    [A]:", current)
        print("Leistung [W]:", power)
    else:
        print("Fehler beim Lesen vom PZEM-Modul!")

    time.sleep(2)
