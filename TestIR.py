from machine import Pin
from ir_tx.nec import NEC     # Empfängerklasse

ir_tx = NEC(Pin(4, Pin.OUT))

print("Senden Starten")
ir_tx.transmit(1,2)
print("Sendung abgeschlossen")
