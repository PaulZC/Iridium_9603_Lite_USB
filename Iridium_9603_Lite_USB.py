# Iridium 9603 Lite USB

# Tested with Python 2.7 on Windows 10 64-Bit

# 9603 power is provided by LTC3225 supercapacitor charger (charged from USB port)
# 9603 module is interfaced via a Cypress CY7C65213:
# GPIO_0 is Tx/Rx LED
# GPIO_1 is connected to 9603 ON_OFF (High=On Low=Off)
# GPIO_4 is connected to LTC3225 SHDN (High=On Low=Off)
# LTC3225 PGOOD is connected to GPIO_2 (High = Power Is Good)
# 9603 Network Available is connected to GPIO_3 (High = Network Is Available)
# All eight UART signals are connected (TXD, RXD, RTS, CTS, DTR, DSR, DCD, RI)

import serial
import time
from cy7c65213 import CyUSBSerial, CyGPIO

# Define serial port
# Check Device Manager for the correct port name (on Windows)
serport = 'COM1'

class IridiumUSBport(object):
    
    def __init__(self):
        print 'Opening GPIO...'
        # Load DLL provided by Cypress (Windows notation)
        self.dll = "C:\\Program Files (x86)\\Cypress\\USB-Serial SDK\\library\\cyusbserial\\x64\\cyusbserial.dll"
        self.lib = CyUSBSerial(lib = self.dll)
        #self.dev = self.lib.find().next() # Use first device found
        self.dev = self.lib.find(vid=0x04B4,pid=0x0003).next() # Look for a specific vendor and product id
        # Access GPIO
        self.gpio = CyGPIO(self.dev)
        self.ON_pin = self.gpio.pin(1) # 9603 ON/OFF = GPIO_1
        self.PGOOD_pin = self.gpio.pin(2) # LTC3225 PGOOD = GPIO_2
        self.NET_pin = self.gpio.pin(3) # 9603 Network Available = GPIO_3
        self.SHDN_pin = self.gpio.pin(4) # LTC3225 Shutdown = GPIO_4
        
        print 'Opening serial port...'
        self.ser = serial.Serial(serport,19200,timeout=1)

        self.CSQ = int(0)
        self.MOF = int(0)
        self.MTF = int(0)
        self.MOS = int(0)
        self.MTS = int(0)
        self.MTQ = int(0)
        
    def writeAndWait(self, data, exp):
        print 'Writing ' + data + ' Expecting ' + exp
        self.ser.write(data+'\r')
        for i in range(30):
            resp = self.ser.readline()
            if resp != '':
                if data in resp:
                    print resp[:-1]
                if exp in resp:
                    print resp[:-1]
                    break
        return resp[:-1]

    def queueMessage(self, mesg):
        print 'Queueing: ' + mesg
        self.ser.write('AT+SBDWT='+mesg+'\r')
        result = False
        for i in range(30):
            resp = self.ser.readline()
            if resp != '':
                if 'SBDWT' in resp: # AT+SBDWT is returned _after_ the OK!
                    print resp[:-1]
                    break
                if 'OK' in resp:
                    print resp[:-1]
                    result = True
                    #break
                if 'ERROR' in resp:
                    print resp[:-1]
                    break
        return result

    def initiateSBD(self):
        print 'Initiating SBD session!'
        resp = self.writeAndWait('AT+SBDI','SBDI:')
        try:
            resp_list = resp.split(",")
            mos = int(resp_list[0][-1])
            mts = int(resp_list[2][-1])
            mtq = int(resp_list[5][1:])
        except:
            mos = int(0)
            mts = int(0)
            mtq = int(0)
        self.MOS = mos
        self.MTS = mts
        self.MTQ = mtq

    def readSBD(self):
        print 'Reading text message...'
        self.ser.write('AT+SBDRT\r')
        msg = ''
        seq = 0
        for i in range(30):
            resp = self.ser.readline()
            if resp != '':
                if (seq == 2) and ('OK' in resp):
                    break
                elif (seq == 1):
                    msg = resp[:-2]
                    seq = 2
                elif (seq == 0) and ('SBDRT:' in resp):
                    seq = 1
        return msg
        
    def set_RTS(self, rts):
        self.ser.setRTS(rts)

    def set_DTR(self, dtr):
        self.ser.setDTR(dtr)

    def set_SHDN(self, shdn):
        self.SHDN_pin.set(shdn)

    def set_ON(self, onoff):
        self.ON_pin.set(onoff)

    def get_CTS(self):
        return self.ser.getCTS()

    def get_DSR(self):
        return self.ser.getDSR()

    def get_DCD(self):
        return self.ser.getDCD()

    def get_RI(self):
        return self.ser.getRI()

    def get_PGOOD(self):
        return self.PGOOD_pin.get()

    def get_NET(self):
        return self.NET_pin.get()

    def check_CSQ(self):
        resp = self.writeAndWait('AT+CSQ','CSQ:')
        try:
            csq = int(resp[-2])
        except:
            csq = int(0)
        self.CSQ = csq

    def check_SBDS(self):
        resp = self.writeAndWait('AT+SBDS','SBDS:')
        try:
            resp_list = resp.split(",")
            mof = int(resp_list[0][-1])
            mtf = int(resp_list[2][-1])
        except:
            mof = int(0)
            mtf = int(0)
        self.MOF = mof
        self.MTF = mtf

    def close(self):
        print 'Closing port...'
        self.ser.close()

try:
    # Create object and open port
    ip = IridiumUSBport()

    # Set On/Off low to disable 9603 while supercapacitor charges
    ip.set_ON(0)

    # Set Shutdown high to enable LTC3225
    ip.set_SHDN(1)

    # Set RTS and DTR low
    ip.set_RTS(1) # 1 = Low
    ip.set_DTR(1) # 1 = Low

    # Keep reading PGOOD (GPIO_2) until it goes high
    pgood = ip.get_PGOOD()
    while pgood == 0:
        print 'Waiting for PGOOD to go high...'
        pgood = ip.get_PGOOD()
        time.sleep(1)

    # Now enable 9603
    ip.set_ON(1)
    time.sleep(2)

    # Send ATtention code - response should be 'OK'
    ip.writeAndWait('AT','OK')

    # Enable Echo - response should be 'OK'
    ip.writeAndWait('ATE1','OK')

    # Ignore DTR - response should be 'OK'
    ip.writeAndWait('AT&D0','OK')

    # Disable flow control - response should be 'OK'
    ip.writeAndWait('AT&K0','OK')

    # Set SBD session timeout to 300 seconds
    ip.writeAndWait('AT+SBDST=300','OK')

    # Clear mobile originated message buffer - just in case!
    ip.writeAndWait('AT+SBDD0','OK')

    # Try for 300 seconds to get a CSQ of 5
    for i in range(100):

        # Check signal quality
        ip.check_CSQ()
        print 'CSQ is '+str(ip.CSQ)

        # If CSQ == 5 then move on
        if ip.CSQ == 5: break

        # Wait
        time.sleep(3)

    # If CSQ == 5, queue a message, initiate SBD session
    if ip.CSQ == 5:

        # Add a new Mobile Originated message to the queue
        # Comment the next two lines out if you don't want to send a message
        #  and only want to check for new Mobile Terminated messages
        message = 'This is a test message!'
        ip.queueMessage(message)
        
        ip.initiateSBD()
        if ip.MOS == 0: print 'No message to send...'
        if ip.MOS == 1: print 'MESSAGE SENT!'
        if ip.MOS == 2: print 'SEND ERROR!'
        if ip.MTS == 0: print 'No message to receive...'
        if ip.MTS == 2: print 'RECEIVE ERROR!'
        if ip.MTS == 1:
            print 'MESSAGE RECEIVED!'
            msg = ip.readSBD()
            print msg
            try:
                fp = open('Iridium_Rx_Log.txt','ab') # Append message to Iridium_Rx_Log.txt
                fp.write(msg+'\r\n')
                fp.close()
            except:
                print 'FILE WRITE ERROR!'
        print 'MTQ is',ip.MTQ

    # Clear mobile originated message buffer - just in case!
    ip.writeAndWait('AT+SBDD0','OK')

except KeyboardInterrupt:

    print 'Ctrl-C Received!'

finally:
    # Send 'Flush to Eeprom' - response should be 'OK'
    ip.writeAndWait('AT*F','OK')
    time.sleep(2)

    # 9603 is now ready to be powered down
    ip.set_ON(0) # Turn 9603 off
    ip.set_SHDN(0) # Disable LTC3225
    time.sleep(2)

    # Close port
    ip.close()

    print 'Bye!'
