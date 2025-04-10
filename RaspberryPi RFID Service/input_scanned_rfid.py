import signal
import sys
import time
import RPi.GPIO as GPIO
from pirc522 import RFID
import subprocess

#Following script runs as a service on the raspberry pi

#Function for when a shutdown is detected``
def onShutdown(signal, frame):
    #Reset GPIO pins on the RPi
    GPIO.cleanup()
    #Quits the script with code 0 (Success)
    sys.exit(0)

def typeText(text):
    try:
        #Using wtype which allows keyboard simulation for wayland display managers
        #Couldn't use pynput because it didn't recognise the focused window
        subprocess.run(['/usr/bin/wtype', text])
    except Exception as e:
        print(f"Error sending text: {e}")

#Listening to shutdown, SIGTERM is for service shutdowns
signal.signal(signal.SIGTERM, onShutdown)
#Init RFID scanner with default GPIO pins, SDA = 8, SCK = 11, MOSI = 10, MISO = 9, RST= 25
scanner = RFID(pin_irq=None)


try:
    while True:
        #Reader.read returns other information, only concerned with UID
        print("Waiting...")
        (error, tag_type) = scanner.request() #Checking for tag
        if not error:
            (error, uid) = scanner.anticoll()
            if not error:
                uid = uid[:4] #Only read first 4 bytes, same as esp32 MFRC522 library
                uid = ''.join(format(number, '02X') for number in uid) #Get array of decimal numbers into hexidecimal as a string
                decimalUID = int(uid,16) #Python will convert the hex into decimal
                #Convert to string for input, \n will submit after string is typed
                decimalUID = str(decimalUID) + "\n"
                #Typing RFID uid
                typeText(decimalUID)
                #Delay to prevent multiple inputs
                time.sleep(5)
        time.sleep(0.5) #To slow polling rate 
except Exception as e:
    print(e)
    #Reset GPIO pins on the RPi
    GPIO.cleanup()
finally:
    #Reset GPIO pins on the RPi
    GPIO.cleanup()