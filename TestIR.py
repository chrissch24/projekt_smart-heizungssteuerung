from machine import Pin, PWM
import time

# IR-Sendediode an Pin 4
ir_sender = Pin(4, Pin.OUT)
#ir_sender = PWM(Pin(4))
#ir_sender.freq(38000)  # Standard-Trägerfrequenz für IR-Signale (38 kHz)
#ir_sender.duty(512)    # 50% Tastverhältnis

# IR-Empfänger an Pin 5
ir_receiver = Pin(5, Pin.IN)

def send_pulse(duration_ms=100):
    """Sendet einen IR-Puls für die gegebene Dauer."""
    ir_sender.duty(512)
    time.sleep_ms(duration_ms)
    ir_sender.duty(0)

def read_signal():
    """Liest den IR-Empfänger und gibt das Signal aus."""
    while True:
        print("Empfangenes Signal:", ir_receiver.value())
        time.sleep(0.1)

try:
    while True:
        #send_pulse(100)  # Sende einen kurzen Puls
        ir_sender.value(1)
        print("Signal Ein")
        time.sleep(1)    # Warte 1 Sekunde
        ir_sender.value(0)
        print("Signal Aus")
        time.sleep(1)
except KeyboardInterrupt:
    ir_sender.deinit()  # PWM deaktivieren
    print("Programm beendet.")
