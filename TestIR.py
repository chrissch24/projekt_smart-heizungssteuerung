from machine import Pin
from ir_tx.nec import NEC           # Senderklasse
from ir_rx.nec import NEC_16        # Empfängerklasse
import time

def callback(data, addr, ctrl):
    if data > 0:
        print("Data {:02x} Addr {:04x}".format(data, addr))

ir = NEC_16(Pin(4, Pin.IN), callback)

