# you need to install crc8 module -> pip3 install crc8
import binascii
import socket
import sys
import crc8
import json
import io
import shutil
import os
import pwd
import grp

if os.path.isdir("/home/homeassistant/.homeassistant"):
  CONFIG = "/home/homeassistant/.homeassistant/.storage/"
else:
  CONFIG = "/config/.storage/"
#CONFIG = "/home/homeassistant/.homeassistant/.storage/" #uncomment this line if you are on Hassbian
#CONFIG = "/config/.storage/" # uncomment this line if you are on Hass.io
def invert(id):
    """The Api_ID must be sent in reversed order"""
    k1 = id[14:16]
    k2 = id[12:14]
    k3 = id[10:12]
    k4 = id[8:10]
    k5 = id[6:8]
    k6 = id[4:6]
    k7 = id[2:4]
    k8 = id[0:2]
    return k1+k2+k3+k4+k5+k6+k7+k8

def print_info():
    print('Devices type list:')
    print('Climate devices:')
    print('TH1120RF (3000W, 4000W) -- 10')
    print('TH1300RF (floor)        -- 20')
    print('TH1400RF (low voltage)  -- 21')
    print('TH1500RF (Double-pole)  -- 20')
    print('Light devices:')
    print('SW2500RF (switch)       -- 102')
    print('DM2500RF (dimmer)       -- 112')
    print('Power switch devices:')
    print('RM3250RF (50 A)         -- 120')
    print('RM3200RF (40 A)         -- 120') 

def crc_count(bufer):
        hash = crc8.crc8()
        hash.update(bufer)
        return hash.hexdigest()

def crc_check(bufer):
        hash = crc8.crc8()
        hash.update(bufer)
        if(hash.hexdigest() == "00"):
          return "00"
        return None

def get_device_id():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = (SERVER, PORT)
    sock.connect(server_address)
    try:
      sock.sendall(login_request())
      answer = sock.recv(1024)
      status = bytearray(answer).hex()[0:14]
      if status == "55000c001101ff":
        print('Login fail, please check your Api_Key')
      else:
        print('Login ok !')
        print('Please push the two buttons on the device you want to identify')
        datarec = sock.recv(1024)
        id = bytearray(datarec).hex()[14:22]
        return id
    finally:
      sock.close()

def send_ping_request(data):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = (SERVER, PORT)
    if SERVER == 'XXX.XXX.XXX.XXX':
      print("Please enter your GT125 IP address on line 12")
      raise SystemExit
    else:
      sock.connect(server_address)
      try:
        sock.sendall(data)
        reply = sock.recv(1024)
        if crc_check(reply):
          return reply
      finally:
        sock.close()

def ping_request():
    ping_data = "550002001200"
    ping_crc = bytes.fromhex(crc_count(bytes.fromhex(ping_data)))
    return bytes.fromhex(ping_data)+ping_crc
  
def key_request(serial):
    key_data = "55000A000A01"+serial
    key_crc = bytes.fromhex(crc_count(bytes.fromhex(key_data)))
    return bytes.fromhex(key_data)+key_crc

def retreive_key(data):
    binary = data[18:]
    key = binary[:16]
    if key == b'0000000000000000':
      print('key request failed. Check your Api_ID')
    return key

def login_request():
    login_data = "550012001001"+invert(Api_ID)+Api_Key
    login_crc = bytes.fromhex(crc_count(bytes.fromhex(login_data)))
    return bytes.fromhex(login_data)+login_crc

def send_key_request(data):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = (SERVER, PORT)
    sock.connect(server_address)
    try:
      print('Sending key request...')
      sock.sendall(data)
      reply = sock.recv(1024)
      return reply    
    finally:
      sock.close()

def write_config(ip,key,id,port):
    with open(CONFIG+'sinope_devices.json', 'w', encoding='utf8') as outfile:
      data = '["'+ip+'", "'+key+'", "'+id+'", '+str(port)+']' 
      outfile.write(data)
      outfile.write('\n')
      data2 = '["id", "name", "type", "watt"]'
      outfile.write(data2)
    outfile.close()
    return True
  
def read_config():
    conf_list = []
    with open(CONFIG+'sinope_devices.json') as f:
        for line in f:
            conf_list.append(json.loads(line))         
    f.close()
    return conf_list[0]
  
def get_ip():
    ip = ""
    while ip == "":
      print('What is your GT125 IP address: xxx.xxx.xxx.xxx')
      ip = input()
      if ip == "":
        print("You must enter a valid IP address")
      else:
        return ip
     
def get_id():
    id = ""
    while id == "":
      print('What is your GT125 ID (written on the back of the device)')
      id = input()
      if id == "":
        print("You must enter a valid ID code")
      else:
        return id

def get_port():
    port = 0
    while port == 0:
      print("Write your GT125 port number (default: 4550)")
      port = input()
      print("port="+port)
      if port == "":
        print("You must enter a valid port number")
        port = 0
      else:
        return int(port)

# send ping to GT125 
try:
  CONFIG
except NameError:
  print("Please edit device.py, line 13,14 and select the CONFIG directory according to your installation!\n")

if os.path.exists(CONFIG+'sinope_devices.json') == False:
  SERVER = get_ip()
  PORT = get_port()
  Api_ID = get_id()
  Api_Key = None
else:
  conf = read_config()
  PORT = int("{}".format(conf[3]))
  SERVER = "{}".format(conf[0])
  Api_Key ="{}".format(conf[1])
  Api_ID = "{}".format(conf[2])

if binascii.hexlify(send_ping_request(ping_request())) == b'55000200130021':
    if Api_Key == None:
        print("ok we can send the api_key request\n")
        print("push the GT125 <web> button")
        Api_Key = retreive_key(binascii.hexlify(send_key_request(key_request(invert(Api_ID)))))[0:16].decode("utf-8")
        print('Api key : ',Api_Key)
        print("Writing config to file "+CONFIG+"sinope_devices.json ...")
        write_config(SERVER,Api_Key,Api_ID,PORT)
        if CONFIG == "/home/homeassistant/.homeassistant/.storage/":
          owner='homeassistant'
          group='homeassistant'
          uid = pwd.getpwnam(owner).pw_uid
          gid = grp.getgrnam(group).gr_gid
          os.chown(CONFIG+"sinope_devices.json",uid,gid)
        print("Run this program again to add your devices")
    else:
      # finding device ID, one by one
      while True:
        dev = get_device_id()
        # setup data line
        if dev is not None:
          print('your device ID is : ',dev)
          print('Add a name for this device or leave empty')
          name = input()
          if name == "":
            name = " "
          print('Add device type (Enter "h" for devices list), or leave empty')
          type = input()
          if type == "h":
            print_info()
            print('\nAdd device type, or leave empty')
            type = input()
          elif type == "":    
            type = " "
          print('Add connected watt load if it is a light or switch device, or leave empty')
          watt = input()
          if watt == "":
            watt = " "
          print('Device '+dev+' has been added to the file devices.json')
          data = '["'+dev+'", "'+name+'", "'+type+'", "'+watt+'"]'
          # write data device to file
          with io.open(CONFIG+'sinope_devices.json', 'a', encoding='utf8') as outfile:
            outfile.write('\n')
            outfile.write(data)
          outfile.close()
          print('Type <q> to quit or just <enter> to continue with next device')
          quit = input()
          if quit == "q":
            break
      print('Once finished, edit file '+CONFIG+'sinope_devices.json to add more information about your devices.')
      print('Device type are listed in climate.py, light.py and switch.py')
